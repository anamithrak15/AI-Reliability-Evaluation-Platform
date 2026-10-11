from uuid import uuid4

import pytest

from app.core.config import get_settings
from tests.test_dataset_schemas import make_case, make_dataset

RUNS = "/api/v1/runs"


def make_version(client, n_cases=3, keys=None):
    keys = keys or [f"case-{i}" for i in range(n_cases)]
    body = make_dataset([make_case(case_key=k) for k in keys], name=f"ds-{uuid4().hex[:6]}")
    created = client.post("/api/v1/datasets", json=body).json()
    return created["version"]["id"]


def start_run(client, version_id, **kw):
    payload = {"dataset_version_id": version_id, "model_aliases": ["fast-model", "accurate-model"]}
    payload.update(kw)
    return client.post(RUNS, json=payload)


def test_create_run_returns_202_and_enqueues(client, enqueued):
    resp = start_run(client, make_version(client))
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "queued"
    assert body["progress"] == {"total_pairs": 6, "completed_pairs": 0, "by_status": {}}
    assert enqueued == [__import__("uuid").UUID(body["id"])]


def test_server_enforces_hard_limits(client, enqueued):
    version_id = make_version(client, n_cases=5)
    body = start_run(client, version_id, max_concurrency=500, max_cases=2).json()
    assert body["config"]["max_concurrency"] == get_settings().max_concurrency_limit
    assert body["config"]["requested"]["max_concurrency"] == 500
    assert body["progress"]["total_pairs"] == 4


@pytest.mark.parametrize(
    "overrides,code",
    [
        ({"model_aliases": ["nope"]}, "unknown_model"),
        ({"evaluation_profile": "bogus"}, "unknown_evaluation_profile"),
        ({"model_aliases": ["fast-model", "fast-model"]}, "validation_error"),
        ({"model_aliases": []}, "validation_error"),
        ({"model_aliases": ["a", "b", "c", "d"]}, "validation_error"),
        ({"max_concurrency": 0}, "validation_error"),
    ],
)
def test_invalid_run_requests(client, enqueued, overrides, code):
    resp = start_run(client, make_version(client), **overrides)
    assert resp.status_code == 400
    assert resp.json()["code"] == code
    assert enqueued == []


def test_missing_version_and_baseline(client, enqueued):
    assert start_run(client, str(uuid4())).status_code == 404
    resp = start_run(client, make_version(client), baseline_run_id=str(uuid4()))
    assert resp.status_code == 404 and resp.json()["code"] == "baseline_run_not_found"


def test_idempotency_key_prevents_duplicates(client, enqueued):
    version_id = make_version(client)
    payload = {"dataset_version_id": version_id, "model_aliases": ["fast-model"]}
    a = client.post(RUNS, json=payload, headers={"Idempotency-Key": "k1"})
    b = client.post(RUNS, json=payload, headers={"Idempotency-Key": "k1"})
    assert a.status_code == b.status_code == 202
    assert a.json()["id"] == b.json()["id"]
    assert len(enqueued) == 1
    assert client.get(RUNS).json()["total"] == 1


def test_active_run_cap_returns_429(client, enqueued, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_active_runs", 1)
    version_id = make_version(client)
    assert start_run(client, version_id).status_code == 202
    resp = start_run(client, version_id)
    assert resp.status_code == 429 and resp.json()["code"] == "too_many_active_runs"


def test_enqueue_failure_returns_503_and_leaves_no_run(client, monkeypatch):
    def boom(run_id):
        raise ConnectionError("redis down")

    monkeypatch.setattr("app.services.run_service.enqueue_run", boom)
    resp = start_run(client, make_version(client))
    assert resp.status_code == 503 and resp.json()["code"] == "queue_unavailable"
    assert client.get(RUNS).json()["total"] == 0


def test_cancel_queued_then_conflict(client, enqueued):
    run_id = start_run(client, make_version(client)).json()["id"]
    resp = client.post(f"{RUNS}/{run_id}/cancel")
    assert resp.status_code == 200 and resp.json()["status"] == "cancelled"
    assert resp.json()["completed_at"] is not None
    again = client.post(f"{RUNS}/{run_id}/cancel")
    assert again.status_code == 409 and again.json()["code"] == "run_not_cancellable"


def test_list_get_and_404(client, enqueued):
    version_id = make_version(client)
    ids = [start_run(client, version_id).json()["id"] for _ in range(2)]
    page = client.get(RUNS, params={"limit": 1}).json()
    assert page["total"] == 2 and len(page["items"]) == 1
    assert client.get(RUNS, params={"status": "queued"}).json()["total"] == 2
    assert client.get(RUNS, params={"status": "completed"}).json()["total"] == 0
    assert client.get(RUNS, params={"status": "bogus"}).status_code == 400
    assert client.get(f"{RUNS}/{ids[0]}").json()["id"] == ids[0]
    assert client.get(f"{RUNS}/{uuid4()}").status_code == 404
    assert client.get(f"{RUNS}/{ids[0]}/results").json()["total"] == 0
    assert client.get(f"{RUNS}/{uuid4()}/results").status_code == 404


def test_models_and_profiles_catalog(client):
    aliases = {m["alias"] for m in client.get("/api/v1/models").json()}
    assert {"fast-model", "accurate-model", "flaky-model"} <= aliases
    assert any(p["name"] == "classification-v1" for p in client.get("/api/v1/evaluation-profiles").json())
