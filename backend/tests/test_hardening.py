import json
import logging
from uuid import uuid4

import pytest

import app.main as main_module
from app.core.config import get_settings
from app.core.logging import JsonFormatter
from app.core.rate_limit import RateLimiter
from tests.test_comparison_api import finish_run, rows_with
from tests.test_runs_api import RUNS, make_version, start_run


class MemoryCounter:
    def __init__(self):
        self.counts: dict[str, int] = {}

    def incr(self, key, ttl):
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]


class BrokenCounter:
    def incr(self, key, ttl):
        raise ConnectionError("redis down")


class Clock:
    def __init__(self, now=1000.0):
        self.now = now

    def __call__(self):
        return self.now


def test_limiter_blocks_after_limit_and_reports_retry_after():
    clock = Clock(1000.0)  # 1000 % 60 == 40, so 20 seconds remain in the window
    limiter = RateLimiter(MemoryCounter(), 60, clock)
    assert [limiter.check("api", "1.2.3.4", 2)[0] for _ in range(3)] == [True, True, False]
    assert limiter.check("api", "1.2.3.4", 2) == (False, 20)


def test_limiter_resets_next_window_and_isolates_clients_and_buckets():
    clock = Clock(1000.0)
    limiter = RateLimiter(MemoryCounter(), 60, clock)
    limiter.check("api", "a", 1)
    assert limiter.check("api", "a", 1)[0] is False
    assert limiter.check("api", "b", 1)[0] is True
    assert limiter.check("other", "a", 1)[0] is True
    clock.now += 60
    assert limiter.check("api", "a", 1)[0] is True


def test_limiter_zero_limit_disables_and_backend_failure_fails_open():
    assert RateLimiter(MemoryCounter()).check("api", "a", 0) == (True, 0)
    assert RateLimiter(BrokenCounter()).check("api", "a", 1) == (True, 0)


@pytest.fixture
def limited(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_per_window", 3)
    monkeypatch.setattr(settings, "rate_limit_run_creates_per_window", 100)
    limiter = RateLimiter(MemoryCounter(), 60)
    monkeypatch.setattr(main_module, "get_limiter", lambda: limiter)
    return settings


def test_api_requests_over_the_limit_get_429_with_retry_after(client, limited):
    assert [client.get("/api/v1/models").status_code for _ in range(3)] == [200, 200, 200]
    blocked = client.get("/api/v1/models")
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "rate_limited"
    assert 1 <= int(blocked.headers["retry-after"]) <= 60
    assert blocked.headers["x-request-id"]


def test_health_endpoints_are_exempt(client, limited):
    assert all(client.get("/health").status_code == 200 for _ in range(10))


def test_run_creation_has_its_own_stricter_limit(client, enqueued, limited, monkeypatch):
    monkeypatch.setattr(limited, "rate_limit_per_window", 100)
    monkeypatch.setattr(limited, "rate_limit_run_creates_per_window", 1)
    version = make_version(client)  # dataset creation is not a run creation
    assert start_run(client, version).status_code == 202
    second = start_run(client, version)
    assert second.status_code == 429 and second.json()["code"] == "rate_limited"
    assert client.get("/api/v1/models").status_code == 200


def test_429_responses_still_carry_cors_headers(client, limited, monkeypatch):
    monkeypatch.setattr(limited, "rate_limit_per_window", 1)
    headers = {"Origin": "http://localhost:3000"}
    client.get("/api/v1/models", headers=headers)
    blocked = client.get("/api/v1/models", headers=headers)
    assert blocked.status_code == 429
    assert blocked.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "retry-after" in blocked.headers["access-control-expose-headers"]


def test_request_id_is_generated_echoed_and_sanitised(client):
    generated = client.get("/health").headers["x-request-id"]
    assert len(generated) == 36
    assert client.get("/health", headers={"X-Request-ID": "trace-123_a.b"}).headers["x-request-id"] == "trace-123_a.b"
    for bad in ("x" * 65, "has space", 'quote"'):
        replaced = client.get("/health", headers={"X-Request-ID": bad}).headers["x-request-id"]
        assert replaced != bad and len(replaced) == 36


def test_request_id_is_on_error_responses_and_security_header_is_set(client):
    missing = client.get(f"{RUNS}/{uuid4()}")
    assert missing.status_code == 404 and missing.headers["x-request-id"]
    assert missing.headers["x-content-type-options"] == "nosniff"


def test_access_log_is_structured_and_carries_the_request_id(client):
    lines: list[dict] = []
    handler = logging.Handler()
    handler.emit = lambda record: lines.append(json.loads(JsonFormatter().format(record)))
    logger = logging.getLogger("app.main")
    logger.addHandler(handler)
    try:
        client.get("/api/v1/models?secret=abc", headers={"X-Request-ID": "req-42"})
    finally:
        logger.removeHandler(handler)
    (entry,) = [e for e in lines if e["message"] == "request"]
    assert entry["request_id"] == "req-42" and entry["status"] == 200
    assert entry["method"] == "GET" and entry["path"] == "/api/v1/models"
    assert entry["duration_ms"] >= 0
    assert "secret" not in json.dumps(entry)  # query strings are never logged


def test_chunked_uploads_are_rejected_because_size_cannot_be_checked(client):
    resp = client.post("/api/v1/datasets", content=iter([b"{}"]))
    assert resp.status_code == 411 and resp.json()["code"] == "length_required"


def test_oversized_declared_body_is_rejected(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_request_bytes", 10)
    resp = client.post("/api/v1/datasets", content=b"x" * 50)
    assert resp.status_code == 413 and resp.json()["code"] == "payload_too_large"


def test_case_inspection_returns_prompt_expected_and_every_models_result(
    client, enqueued, session_factory
):
    version = make_version(client, keys=["a-case", "b-case"])
    run_id = start_run(client, version, model_aliases=["fast-model", "accurate-model"]).json()["id"]
    finish_run(
        session_factory, run_id,
        {
            "fast-model": rows_with([0, 1]),
            "accurate-model": [("success", 10, 1, None), ("provider_error", None, None, None)],
        },
        final="completed_with_errors",
    )
    body = client.get(f"{RUNS}/{run_id}/cases/a-case").json()
    assert body["case_key"] == "a-case"
    assert body["input"]["messages"][0]["role"] == "user"
    assert body["expected_output"] == {"category": "billing"}
    assert body["evaluation_config"]["type"] == "classification"
    by = {r["model_alias"]: r for r in body["results"]}
    assert set(by) == {"fast-model", "accurate-model"}
    assert float(by["fast-model"]["metrics"]["quality"]) == 0.0

    failed = client.get(f"{RUNS}/{run_id}/cases/b-case").json()
    assert {r["model_alias"]: r["status"] for r in failed["results"]}["accurate-model"] == "provider_error"


def test_case_inspection_not_found_cases(client, enqueued):
    version = make_version(client, keys=["only"])
    run_id = start_run(client, version).json()["id"]
    assert client.get(f"{RUNS}/{run_id}/cases/nope").json()["code"] == "case_not_found"
    assert client.get(f"{RUNS}/{uuid4()}/cases/only").json()["code"] == "run_not_found"
    assert client.get(f"{RUNS}/{run_id}/cases/{'x' * 201}").status_code == 400
    pending = client.get(f"{RUNS}/{run_id}/cases/only").json()
    assert pending["results"] == []  # an unfinished run has no results yet, which is not an error
