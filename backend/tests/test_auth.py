from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
import pytest
from argon2 import PasswordHasher
from sqlalchemy import select

import app.core.rate_limit as rate_limit_module
import app.services.queue as queue_module
import app.services.resume as resume_module
from app.auth import passwords, tokens
from app.core.config import Settings, assert_safe_for_environment, get_settings
from app.core.rate_limit import RateLimiter
from app.models import Dataset, DatasetVersion, EvaluationRun, TestCase, User
from app.models.entities import utcnow
from tests.conftest import PASSWORD, new_client
from tests.test_comparison_api import finish_run, rows_with
from tests.test_hardening import MemoryCounter
from tests.test_runs_api import RUNS, make_version, start_run

AUTH = "/api/v1/auth"


def register(client, email="new@example.com", password=PASSWORD):
    return client.post(f"{AUTH}/register", json={"email": email, "password": password})


def login(client, email="new@example.com", password=PASSWORD):
    return client.post(f"{AUTH}/login", json={"email": email, "password": password})


# --- registration and login -------------------------------------------------------------------


def test_register_creates_an_account_and_signs_in(anonymous_client, session_factory):
    resp = register(anonymous_client, "Mixed.Case@Example.com")
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "mixed.case@example.com" and "password" not in str(body).lower()
    assert anonymous_client.get(f"{AUTH}/me").json()["id"] == body["id"]
    with session_factory() as s:
        stored = s.scalar(select(User.password_hash).where(User.email == "mixed.case@example.com"))
    assert stored.startswith("$argon2id$") and PASSWORD not in stored


def test_session_cookie_is_httponly_samesite_lax_and_scoped_to_root(anonymous_client):
    header = register(anonymous_client).headers["set-cookie"].lower()
    assert "session=" in header and "httponly" in header
    assert "samesite=lax" in header and "path=/" in header and "max-age=" in header
    assert "secure" not in header.replace("samesite", "")


def test_session_cookie_is_secure_when_configured(anonymous_client, monkeypatch):
    monkeypatch.setattr(get_settings(), "cookie_secure", True)
    assert "secure" in register(anonymous_client).headers["set-cookie"].lower().replace("samesite", "")


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "a@example.com", "password": "short"},
        {"email": "not-an-email", "password": PASSWORD},
        {"email": "a@example.com", "password": "x" * 129},
        {"email": "a@example.com", "password": PASSWORD, "is_admin": True},
        {"email": "a@example.com"},
    ],
)
def test_registration_validation(anonymous_client, payload):
    resp = anonymous_client.post(f"{AUTH}/register", json=payload)
    assert resp.status_code == 400 and resp.json()["code"] == "validation_error"
    assert "session" not in resp.headers.get("set-cookie", "")


def test_short_password_message_states_the_minimum(anonymous_client):
    resp = anonymous_client.post(f"{AUTH}/register", json={"email": "a@example.com", "password": "x"})
    assert "at least 10 characters" in resp.json()["details"][0]["message"]


def test_duplicate_email_is_rejected_case_insensitively(anonymous_client):
    assert register(anonymous_client, "dup@example.com").status_code == 201
    other = new_client()
    resp = register(other, "DUP@example.com")
    assert resp.status_code == 409 and resp.json()["code"] == "email_taken"


def test_registration_can_be_closed(anonymous_client, monkeypatch):
    monkeypatch.setattr(get_settings(), "allow_registration", False)
    resp = register(anonymous_client)
    assert resp.status_code == 403 and resp.json()["code"] == "registration_closed"


def test_login_logout_roundtrip(anonymous_client):
    register(anonymous_client)
    other = new_client()
    assert login(other).status_code == 200
    assert other.get(f"{AUTH}/me").status_code == 200
    out = other.post(f"{AUTH}/logout")
    assert out.status_code == 204 and "session=" in out.headers["set-cookie"].lower()
    assert other.get(f"{AUTH}/me").status_code == 401


def test_login_failures_are_indistinguishable(anonymous_client):
    register(anonymous_client)
    wrong_password = login(new_client(), password="not the password")
    unknown_email = login(new_client(), email="nobody@example.com")
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()
    assert wrong_password.json()["code"] == "invalid_credentials"
    assert "set-cookie" not in wrong_password.headers


def test_disabled_account_cannot_log_in_or_use_an_existing_session(anonymous_client, session_factory):
    register(anonymous_client)
    with session_factory() as s:
        user = s.scalar(select(User))
        user.is_active = False
        s.commit()
    assert anonymous_client.get(f"{AUTH}/me").status_code == 401
    assert login(new_client()).status_code == 401


# --- session token hardening -----------------------------------------------------------------


def _cookie_client(token: str):
    c = new_client()
    c.cookies.set("session", token)
    return c


def _claims(user_id, **over):
    now = datetime.now(UTC)
    return {"sub": str(user_id), "ver": 0, "iat": now, "exp": now + timedelta(days=1), **over}


def test_valid_hand_made_token_works_and_bad_ones_do_not(anonymous_client, session_factory):
    uid = register(anonymous_client).json()["id"]
    secret = get_settings().secret_key
    assert _cookie_client(jwt.encode(_claims(uid), secret, "HS256")).get(f"{AUTH}/me").status_code == 200

    bad = {
        "wrong secret": jwt.encode(_claims(uid), "x" * 40, "HS256"),
        "expired": jwt.encode(_claims(uid, exp=datetime.now(UTC) - timedelta(seconds=5)), secret, "HS256"),
        "alg none": jwt.encode(_claims(uid), None, algorithm="none"),
        "no expiry": jwt.encode({"sub": uid, "ver": 0}, secret, "HS256"),
        "unknown user": jwt.encode(_claims(uuid4()), secret, "HS256"),
        "not a uuid": jwt.encode(_claims("abc"), secret, "HS256"),
        "garbage": "not.a.jwt",
    }
    for name, token in bad.items():
        assert _cookie_client(token).get(f"{AUTH}/me").status_code == 401, name


def test_bumping_token_version_revokes_existing_sessions(anonymous_client, session_factory):
    register(anonymous_client)
    assert anonymous_client.get(f"{AUTH}/me").status_code == 200
    with session_factory() as s:
        s.scalar(select(User)).token_version += 1
        s.commit()
    assert anonymous_client.get(f"{AUTH}/me").status_code == 401


def test_token_roundtrip_and_garbage(anonymous_client):
    uid = register(anonymous_client).json()["id"]
    user = User(id=UUID(uid), email="x@example.com", password_hash="h", token_version=3)
    claims = tokens.read_token(tokens.issue_token(user))
    assert claims["sub"] == uid and claims["ver"] == 3
    assert tokens.read_token("") is None and tokens.read_token("a.b.c") is None


def test_password_hashing_helpers():
    stored = passwords.hash_password("hunter2hunter2")
    assert passwords.verify_password(stored, "hunter2hunter2") == (True, None)
    assert passwords.verify_password(stored, "wrong") == (False, None)
    assert passwords.verify_password(None, "anything") == (False, None)
    assert passwords.verify_password("not-a-hash", "x") == (False, None)


def test_weak_hashes_are_upgraded_on_login(anonymous_client, session_factory, monkeypatch):
    register(anonymous_client)
    stronger = PasswordHasher(time_cost=2, memory_cost=16, parallelism=1)
    monkeypatch.setattr(passwords, "_hasher", stronger)
    assert login(new_client()).status_code == 200
    with session_factory() as s:
        assert "t=2" in s.scalar(select(User.password_hash))


# --- what needs a session ---------------------------------------------------------------------

PROTECTED_GET = [
    "/api/v1/models", "/api/v1/evaluation-profiles", "/api/v1/datasets", f"/api/v1/datasets/{uuid4()}",
    f"/api/v1/datasets/{uuid4()}/versions", RUNS, f"{RUNS}/{uuid4()}", f"{RUNS}/{uuid4()}/results",
    f"{RUNS}/{uuid4()}/comparison", f"{RUNS}/{uuid4()}/regressions", f"{RUNS}/{uuid4()}/report",
    f"{RUNS}/{uuid4()}/cases/a", f"{AUTH}/me",
]


@pytest.mark.parametrize("path", PROTECTED_GET)
def test_data_endpoints_require_a_session(anonymous_client, path):
    resp = anonymous_client.get(path)
    assert resp.status_code == 401 and resp.json()["code"] == "not_authenticated"


@pytest.mark.parametrize(
    "path", ["/api/v1/datasets", RUNS, f"{RUNS}/{uuid4()}/cancel", f"{RUNS}/{uuid4()}/baseline"]
)
def test_write_endpoints_require_a_session(anonymous_client, path):
    assert anonymous_client.post(path, json={}).status_code == 401


def test_health_and_auth_endpoints_stay_public(anonymous_client):
    assert anonymous_client.get("/health").status_code == 200
    assert register(anonymous_client).status_code == 201


def test_unsafe_requests_need_the_csrf_header_even_with_a_valid_session(client):
    no_header = {"X-Requested-With": ""}
    assert client.post("/api/v1/datasets", json={}, headers=no_header).status_code == 403
    assert client.post(f"{AUTH}/logout", headers=no_header).json()["code"] == "csrf_check_failed"
    assert client.get("/api/v1/datasets", headers=no_header).status_code == 200  # reads are safe


# --- accounts own their data ------------------------------------------------------------------


def test_each_account_only_sees_its_own_datasets_and_runs(client, other_client, enqueued):
    version = make_version(client)
    start_run(client, version)
    assert client.get("/api/v1/datasets").json()["total"] == 1
    assert client.get(RUNS).json()["total"] == 1
    assert other_client.get("/api/v1/datasets").json() == {"items": [], "total": 0, "limit": 20, "offset": 0}
    assert other_client.get(RUNS).json()["items"] == []


def test_other_accounts_resources_look_missing_not_forbidden(client, other_client, enqueued, session_factory):
    version = make_version(client, keys=["a", "b"])
    dataset_id = client.get("/api/v1/datasets").json()["items"][0]["id"]
    run_id = start_run(client, version, model_aliases=["fast-model"]).json()["id"]
    finish_run(session_factory, run_id, {"fast-model": rows_with([1, 1])})

    base = f"/api/v1/datasets/{dataset_id}"
    gets = [
        (base, "dataset_not_found"), (f"{base}/versions", "dataset_not_found"),
        (f"{base}/versions/1", "dataset_not_found"),
        (f"{RUNS}/{run_id}", "run_not_found"), (f"{RUNS}/{run_id}/results", "run_not_found"),
        (f"{RUNS}/{run_id}/comparison", "run_not_found"), (f"{RUNS}/{run_id}/regressions", "run_not_found"),
        (f"{RUNS}/{run_id}/report", "run_not_found"), (f"{RUNS}/{run_id}/cases/a", "run_not_found"),
    ]
    for path, code in gets:
        resp = other_client.get(path)
        assert resp.status_code == 404 and resp.json()["code"] == code, path
        assert client.get(path).status_code == 200, path

    new_version = {"schema_version": "1.0", "cases": [{
        "case_key": "z", "input": {"messages": [{"role": "user", "content": "hi"}]},
        "expected_output": {"category": "billing"}, "evaluation_config": {"type": "classification"}, "tags": [],
    }]}
    assert other_client.post(f"{base}/versions", json=new_version).status_code == 404
    assert other_client.post(f"{RUNS}/{run_id}/cancel").status_code == 404
    assert other_client.post(f"{RUNS}/{run_id}/baseline", json={"baseline_run_id": None}).status_code == 404
    assert start_run(other_client, version).json()["code"] == "dataset_version_not_found"


def test_another_accounts_run_cannot_be_a_baseline(client, other_client, enqueued, session_factory):
    shared_keys = ["a", "b"]
    v1 = make_version(client, keys=shared_keys)
    run_a = start_run(client, v1, model_aliases=["fast-model"]).json()["id"]
    finish_run(session_factory, run_a, {"fast-model": rows_with([1, 1])})

    v2 = make_version(other_client, keys=shared_keys)  # identical content, so only ownership differs
    created = start_run(other_client, v2, model_aliases=["fast-model"], baseline_run_id=run_a)
    assert created.status_code == 404 and created.json()["code"] == "baseline_run_not_found"

    own = start_run(other_client, v2, model_aliases=["fast-model"]).json()["id"]
    finish_run(session_factory, own, {"fast-model": rows_with([1, 1])})
    resp = other_client.post(f"{RUNS}/{own}/baseline", json={"baseline_run_id": run_a})
    assert resp.status_code == 404 and resp.json()["code"] == "baseline_run_not_found"


def test_idempotency_keys_are_private_to_each_account(client, other_client, enqueued):
    version_a = make_version(client)
    version_b = make_version(other_client)
    key = {"Idempotency-Key": "same-key-for-both"}
    body = {"dataset_version_id": version_a, "model_aliases": ["fast-model"]}
    a = client.post(RUNS, json=body, headers=key).json()
    again = client.post(RUNS, json=body, headers=key).json()
    assert again["id"] == a["id"]  # still idempotent for the same account
    b = other_client.post(
        RUNS, json={"dataset_version_id": version_b, "model_aliases": ["fast-model"]}, headers=key
    )
    assert b.status_code == 202 and b.json()["id"] != a["id"]
    assert other_client.get(f"{RUNS}/{a['id']}").status_code == 404


def test_runs_are_stamped_with_their_owner(client, enqueued, session_factory):
    start_run(client, make_version(client))
    with session_factory() as s:
        owner = s.scalar(select(User.id).where(User.email == "user-a@example.com"))
        assert s.scalar(select(EvaluationRun.user_id)) == owner
        assert s.scalar(select(Dataset.user_id)) == owner


# --- quotas ------------------------------------------------------------------------------------


def test_dataset_quota_is_per_account(client, other_client, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_datasets_per_user", 2)
    make_version(client)
    make_version(client)
    from tests.test_dataset_schemas import make_case, make_dataset

    over = client.post("/api/v1/datasets", json=make_dataset([make_case()], name="third"))
    assert over.status_code == 429 and over.json()["code"] == "quota_exceeded"
    assert other_client.post("/api/v1/datasets", json=make_dataset([make_case()], name="mine")).status_code == 201


def test_active_run_cap_is_per_account_and_global(client, other_client, enqueued, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_active_runs", 1)
    monkeypatch.setattr(get_settings(), "max_active_runs_global", 2)
    mine, theirs = make_version(client), make_version(other_client)
    assert start_run(client, mine).status_code == 202
    again = start_run(client, mine)
    assert again.status_code == 429 and again.json()["code"] == "too_many_active_runs"
    assert start_run(other_client, theirs).status_code == 202  # their own allowance is untouched

    monkeypatch.setattr(get_settings(), "max_active_runs", 5)
    busy = start_run(client, mine)
    assert busy.status_code == 429 and busy.json()["code"] == "service_busy"


# --- first account and demo data ----------------------------------------------------------------


def test_first_account_claims_data_created_before_accounts_existed(anonymous_client, session_factory):
    with session_factory() as s:
        legacy = Dataset(name="legacy", user_id=None)
        s.add(legacy)
        s.flush()
        version = DatasetVersion(dataset_id=legacy.id, version_number=1, schema_version="1.0", content_hash="h")
        s.add(version)
        s.flush()
        s.add(TestCase(dataset_version_id=version.id, case_key="k", input={"messages": []}, evaluation_config={}))
        s.add(EvaluationRun(dataset_version_id=version.id, status="completed", config_snapshot={}))
        s.commit()

    assert register(anonymous_client, "first@example.com").status_code == 201
    assert [d["name"] for d in anonymous_client.get("/api/v1/datasets").json()["items"]] == ["legacy"]
    assert anonymous_client.get(RUNS).json()["total"] == 1

    second = new_client()
    register(second, "second@example.com")
    assert second.get("/api/v1/datasets").json()["total"] == 0  # later accounts claim nothing


def test_registration_gives_each_account_a_private_copy_of_the_demo_dataset(anonymous_client, monkeypatch):
    monkeypatch.setattr(get_settings(), "demo_mode", True)
    register(anonymous_client, "one@example.com")
    two = new_client()
    register(two, "two@example.com")
    one_items = anonymous_client.get("/api/v1/datasets").json()["items"]
    two_items = two.get("/api/v1/datasets").json()["items"]
    assert [d["name"] for d in one_items] == [d["name"] for d in two_items] == ["support-ticket-classification"]
    assert one_items[0]["id"] != two_items[0]["id"]
    versions = anonymous_client.get(f"/api/v1/datasets/{one_items[0]['id']}/versions").json()
    assert versions[0]["case_count"] == 6


def test_a_broken_demo_seed_does_not_block_registration(anonymous_client, monkeypatch):
    monkeypatch.setattr(get_settings(), "demo_mode", True)
    monkeypatch.setattr(get_settings(), "demo_dataset_path", "/does/not/exist.json")
    assert register(anonymous_client).status_code == 201
    assert anonymous_client.get("/api/v1/datasets").json()["total"] == 0


# --- abuse controls -----------------------------------------------------------------------------


@pytest.fixture
def limited(monkeypatch):
    monkeypatch.setattr(get_settings(), "rate_limit_enabled", True)
    monkeypatch.setattr(get_settings(), "rate_limit_per_window", 1000)
    monkeypatch.setattr(rate_limit_module, "_limiter", RateLimiter(MemoryCounter(), 60))


def test_repeated_failed_logins_for_one_email_are_throttled(anonymous_client, limited, monkeypatch):
    monkeypatch.setattr(get_settings(), "auth_login_email_per_window", 3)
    monkeypatch.setattr(get_settings(), "auth_login_ip_per_window", 100)
    register(anonymous_client)
    codes = [login(new_client(), password="wrong password").status_code for _ in range(5)]
    assert codes == [401, 401, 401, 429, 429]
    # The right password is also refused while throttled, so guessing cannot continue.
    blocked = login(new_client())
    assert blocked.status_code == 429 and blocked.json()["code"] == "rate_limited"


def test_login_attempts_from_one_address_are_throttled_across_emails(anonymous_client, limited, monkeypatch):
    monkeypatch.setattr(get_settings(), "auth_login_ip_per_window", 2)
    codes = [login(new_client(), email=f"user{i}@example.com").status_code for i in range(4)]
    assert codes == [401, 401, 429, 429]


def test_account_creation_is_throttled_per_address(anonymous_client, limited, monkeypatch):
    monkeypatch.setattr(get_settings(), "auth_register_per_window", 2)
    statuses = [register(new_client(), f"bulk{i}@example.com").status_code for i in range(4)]
    assert statuses == [201, 201, 429, 429]


# --- single-service hosting ---------------------------------------------------------------------


def test_enqueue_uses_the_inline_executor_only_when_enabled(monkeypatch):
    submitted = []

    class FakePool:
        def submit(self, fn, *args):
            submitted.append((fn, args))

    pushed = []

    class FakeQueue:
        def __init__(self, *a, **k):
            pass

        def enqueue(self, *a, **k):
            pushed.append(a)

    monkeypatch.setattr(queue_module, "_inline_executor", lambda: FakePool())
    monkeypatch.setattr(queue_module, "Queue", FakeQueue)
    monkeypatch.setattr(queue_module.redis.Redis, "from_url", staticmethod(lambda url: object()))
    run_id = uuid4()

    monkeypatch.setattr(get_settings(), "run_worker_inline", True)
    queue_module.enqueue_run(run_id)
    assert submitted == [(queue_module._run_inline, (run_id,))] and pushed == []

    monkeypatch.setattr(get_settings(), "run_worker_inline", False)
    queue_module.enqueue_run(run_id)
    assert len(pushed) == 1 and len(submitted) == 1


def test_resume_hands_back_queued_and_in_flight_runs_only(client, enqueued, session_factory, monkeypatch):
    version = make_version(client)
    queued = start_run(client, version, model_aliases=["fast-model"]).json()["id"]
    running = start_run(client, version, model_aliases=["accurate-model"]).json()["id"]
    done = start_run(client, version, model_aliases=["flaky-model"]).json()["id"]
    with session_factory() as s:
        s.get(EvaluationRun, UUID(running)).status = "running"
        s.get(EvaluationRun, UUID(running)).started_at = utcnow()
        s.get(EvaluationRun, UUID(done)).status = "completed"
        s.commit()

    resumed = []
    monkeypatch.setattr(resume_module, "SessionLocal", session_factory)
    monkeypatch.setattr(resume_module, "enqueue_run", resumed.append)
    assert resume_module.resume_incomplete_runs() == 2
    assert {str(r) for r in resumed} == {queued, running}
    with session_factory() as s:
        age = utcnow() - s.get(EvaluationRun, UUID(running)).started_at
    assert age > timedelta(seconds=get_settings().stale_run_seconds)  # claimable straight away


def test_production_refuses_development_defaults():
    safe = dict(environment="production", secret_key="k" * 40, cookie_secure=True)
    assert_safe_for_environment(Settings(**safe))
    assert_safe_for_environment(Settings())  # development is permissive
    for bad in (
        {"secret_key": Settings().secret_key},
        {"secret_key": "short"},
        {"cookie_secure": False},
    ):
        with pytest.raises(RuntimeError, match="Unsafe production configuration"):
            assert_safe_for_environment(Settings(**{**safe, **bad}))
