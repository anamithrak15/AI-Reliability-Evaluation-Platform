import json
from pathlib import Path
from uuid import uuid4

from app.core.config import get_settings
from tests.test_dataset_schemas import make_case, make_dataset

BASE = "/api/v1/datasets"


def _create(client, **kw):
    resp = client.post(BASE, json=make_dataset(**kw))
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_create_dataset_makes_version_one(client):
    body = _create(client)
    assert body["dataset"]["name"] == "ds"
    assert body["dataset"]["version_count"] == 1
    assert body["version"]["version_number"] == 1
    assert body["version"]["case_count"] == 1
    assert len(body["version"]["content_hash"]) == 64


def test_row_level_validation_errors(client):
    bad = make_dataset([make_case(), make_case(case_key="ok-2", evaluation_config={"type": "nope"})])
    resp = client.post(BASE, json=bad)
    assert resp.status_code == 400
    err = resp.json()
    assert err["code"] == "validation_error"
    assert any(d["loc"] == "cases.1.evaluation_config" for d in err["details"])


def test_duplicate_case_keys_returns_400(client):
    resp = client.post(BASE, json=make_dataset([make_case(), make_case()]))
    assert resp.status_code == 400
    assert "duplicate" in resp.json()["details"][0]["message"]


def test_too_many_cases_returns_400(client):
    limit = get_settings().max_cases_per_dataset
    cases = [make_case(case_key=f"c{i}") for i in range(limit + 1)]
    assert client.post(BASE, json=make_dataset(cases)).status_code == 400


def test_oversized_body_returns_413(client):
    resp = client.post(
        BASE, content=b"x" * (get_settings().max_request_bytes + 1),
        headers={"content-type": "application/json"},
    )
    assert resp.status_code == 413
    assert resp.json()["code"] == "payload_too_large"


def test_list_and_pagination(client):
    for i in range(3):
        _create(client, name=f"ds-{i}")
    page = client.get(BASE, params={"limit": 2, "offset": 0}).json()
    assert page["total"] == 3 and len(page["items"]) == 2
    rest = client.get(BASE, params={"limit": 2, "offset": 2}).json()
    assert len(rest["items"]) == 1
    assert client.get(BASE, params={"limit": 0}).status_code == 400


def test_get_dataset_and_404(client):
    created = _create(client)
    ds_id = created["dataset"]["id"]
    assert client.get(f"{BASE}/{ds_id}").json()["latest_version_number"] == 1
    missing = client.get(f"{BASE}/{uuid4()}")
    assert missing.status_code == 404 and missing.json()["code"] == "dataset_not_found"
    assert client.get(f"{BASE}/not-a-uuid").status_code == 400


def test_new_version_increments_and_old_version_is_immutable(client):
    ds_id = _create(client)["dataset"]["id"]
    new_case = make_case(case_key="billing-002")
    resp = client.post(
        f"{BASE}/{ds_id}/versions",
        json={"schema_version": "1.0", "cases": [make_case(), new_case]},
    )
    assert resp.status_code == 201
    assert resp.json()["version_number"] == 2 and resp.json()["case_count"] == 2

    v1 = client.get(f"{BASE}/{ds_id}/versions/1").json()
    v2 = client.get(f"{BASE}/{ds_id}/versions/2").json()
    assert [c["case_key"] for c in v1["cases"]] == ["billing-001"]
    assert [c["case_key"] for c in v2["cases"]] == ["billing-001", "billing-002"]

    versions = client.get(f"{BASE}/{ds_id}/versions").json()
    assert [v["version_number"] for v in versions] == [2, 1]
    assert client.get(f"{BASE}/{ds_id}").json()["version_count"] == 2


def test_identical_version_conflicts(client):
    ds_id = _create(client)["dataset"]["id"]
    resp = client.post(
        f"{BASE}/{ds_id}/versions", json={"schema_version": "1.0", "cases": [make_case()]}
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "duplicate_version"


def test_version_endpoints_404(client):
    ds_id = _create(client)["dataset"]["id"]
    assert client.get(f"{BASE}/{ds_id}/versions/99").json()["code"] == "version_not_found"
    resp = client.post(
        f"{BASE}/{uuid4()}/versions", json={"schema_version": "1.0", "cases": [make_case()]}
    )
    assert resp.status_code == 404


def test_demo_dataset_file_is_valid_and_importable(client):
    path = Path(get_settings().demo_dataset_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    resp = client.post(BASE, json=payload)
    assert resp.status_code == 201, resp.text
    assert resp.json()["version"]["case_count"] == 6
