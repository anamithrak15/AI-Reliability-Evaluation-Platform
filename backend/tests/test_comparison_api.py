from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

import app.evaluation.orchestrator as orch
from app.models import CaseMetric, CaseResult, RegressionFinding, RunSummary, TestCase
from app.models.entities import utcnow
from app.repositories import run_repo
from tests.test_runs_api import RUNS, make_version, start_run


def finish_run(session_factory, run_id, data, final="completed"):
    """data: {alias: [(status, latency_ms, quality, cost)]}, one tuple per case in case_key order."""
    run_id = UUID(run_id)
    with session_factory() as s:
        run = run_repo.get_run(s, run_id)
        cases = s.scalars(
            select(TestCase).where(TestCase.dataset_version_id == run.dataset_version_id)
            .order_by(TestCase.case_key)
        ).all()
        for alias, rows in data.items():
            for case, (status, latency, quality, cost) in zip(cases, rows):
                r = CaseResult(
                    run_id=run_id, test_case_id=case.id, model_alias=alias, status=status,
                    latency_ms=latency, input_tokens=10, output_tokens=5, estimated_cost_usd=cost,
                )
                s.add(r)
                s.flush()
                if quality is not None:
                    s.add(CaseMetric(case_result_id=r.id, metric_name="quality", metric_value=quality))
        s.commit()
        run_repo.transition(s, run_id, {"queued"}, "running", started_at=utcnow())
        run_repo.transition(s, run_id, {"running"}, final, completed_at=utcnow())


def rows_with(qualities, latency=100, cost=None):
    return [("success", latency, q, cost) for q in qualities]


def run_with(client, session_factory, version_id, alias, qualities, latency=100, cost=None, **kw):
    run_id = start_run(client, version_id, model_aliases=[alias], **kw).json()["id"]
    finish_run(session_factory, run_id, {alias: rows_with(qualities, latency, cost)})
    return run_id


@pytest.fixture
def version(client):
    return make_version(client, n_cases=6)


def test_comparison_requires_a_finished_run(client, enqueued, version):
    run_id = start_run(client, version).json()["id"]
    resp = client.get(f"{RUNS}/{run_id}/comparison")
    assert resp.status_code == 409 and resp.json()["code"] == "run_not_finished"
    assert client.get(f"{RUNS}/{uuid4()}/comparison").status_code == 404


def test_comparison_reports_metrics_and_never_fabricates_cost(client, enqueued, session_factory, version):
    run_id = run_with(client, session_factory, version, "fast-model", [1, 1, 1, 1, 0, 0],
                      latency=120)
    body = client.get(f"{RUNS}/{run_id}/comparison").json()
    (m,) = body["models"]
    assert m["quality_score"] == pytest.approx(4 / 6) and m["quality_n"] == 6
    assert m["latency_p50_ms"] == 120 and m["latency_p95_ms"] == 120
    assert m["total_input_tokens"] == 60 and m["total_output_tokens"] == 30
    assert m["estimated_cost_usd"] is None and m["cost_per_case_usd"] is None
    assert m["failure_rate"] == 0 and m["executed"] == 6
    assert body["ranking"]["recommended"] == "fast-model"
    assert "workload and test dataset" in body["ranking"]["notes"][-1]
    assert body["dataset_version_number"] == 1


def test_comparison_summary_is_persisted_once(client, enqueued, session_factory, version):
    run_id = run_with(client, session_factory, version, "fast-model", [1] * 6)
    client.get(f"{RUNS}/{run_id}/comparison")
    client.get(f"{RUNS}/{run_id}/comparison")
    with session_factory() as s:
        assert s.scalar(select(func.count()).select_from(RunSummary)) == 1


def test_orchestrator_stores_summaries_on_finalize(client, enqueued, session_factory, no_backoff, version):
    run_id = start_run(client, version, model_aliases=["fast-model", "accurate-model"]).json()["id"]
    orch.execute_run(session_factory, UUID(run_id))
    with session_factory() as s:
        stored = {r.model_alias for r in s.scalars(select(RunSummary))}
    assert stored == {"fast-model", "accurate-model"}
    body = client.get(f"{RUNS}/{run_id}/comparison").json()
    assert [m["model_alias"] for m in body["models"]] == ["fast-model", "accurate-model"]


def test_baseline_with_regression_creates_persisted_findings(client, enqueued, session_factory, version):
    baseline = run_with(client, session_factory, version, "accurate-model", [1] * 6)
    current = run_with(client, session_factory, version, "accurate-model", [1, 1, 1, 1, 1, 0],
                       baseline_run_id=baseline)
    body = client.get(f"{RUNS}/{current}/regressions").json()
    assert body["state"] == "evaluated" and body["baseline_run_id"] == baseline
    assert body["highest_severity"] == "warning"
    (f,) = [f for f in body["findings"] if f["metric_name"] == "quality_score"]
    assert f["baseline_value"] == 1.0 and f["current_value"] == pytest.approx(5 / 6, abs=1e-5)
    assert f["delta"] == pytest.approx(-1 / 6, abs=1e-5) and "fell" in f["explanation"]
    with session_factory() as s:
        n = s.scalar(select(func.count()).select_from(RegressionFinding).where(
            RegressionFinding.run_id == UUID(current)))
    assert n == len(body["findings"])
    again = client.get(f"{RUNS}/{current}/regressions").json()
    assert len(again["findings"]) == len(body["findings"])  # idempotent


def test_quality_below_floor_is_critical(client, enqueued, session_factory, version):
    baseline = run_with(client, session_factory, version, "accurate-model", [1] * 6)
    current = run_with(client, session_factory, version, "accurate-model", [1, 0, 0, 0, 0, 0],
                       baseline_run_id=baseline)
    assert client.get(f"{RUNS}/{current}/regressions").json()["highest_severity"] == "critical"


def test_no_regression_yields_empty_findings(client, enqueued, session_factory, version):
    baseline = run_with(client, session_factory, version, "accurate-model", [1] * 6)
    current = run_with(client, session_factory, version, "accurate-model", [1] * 6,
                       baseline_run_id=baseline)
    body = client.get(f"{RUNS}/{current}/regressions").json()
    assert body["state"] == "evaluated" and body["findings"] == [] and body["highest_severity"] is None


def test_cross_model_baseline_pairs_single_model_runs(client, enqueued, session_factory, version):
    baseline = run_with(client, session_factory, version, "accurate-model", [1] * 6)
    current = run_with(client, session_factory, version, "fast-model", [1, 1, 0, 0, 0, 0],
                       baseline_run_id=baseline)
    findings = client.get(f"{RUNS}/{current}/regressions").json()["findings"]
    assert findings and all(f["model_alias"] == "fast-model" for f in findings)
    assert "accurate-model" in findings[0]["explanation"]


def test_run_without_baseline(client, enqueued, session_factory, version):
    run_id = run_with(client, session_factory, version, "fast-model", [1] * 6)
    body = client.get(f"{RUNS}/{run_id}/regressions").json()
    assert body["state"] == "no_baseline" and body["findings"] == []
    # An unfinished run without a baseline is still answerable.
    queued = start_run(client, version).json()["id"]
    assert client.get(f"{RUNS}/{queued}/regressions").json()["state"] == "no_baseline"


def test_incompatible_baseline_is_rejected_at_creation(client, enqueued, session_factory, version):
    baseline = run_with(client, session_factory, version, "accurate-model", [1] * 6)
    other = make_version(client, keys=[f"other-{i}" for i in range(6)])
    resp = start_run(client, other, baseline_run_id=baseline)
    assert resp.status_code == 409 and resp.json()["code"] == "incompatible_baseline"
    assert "dataset content differs" in resp.json()["details"][0]["message"]


def test_profile_mismatch_is_incompatible(client, enqueued, session_factory, version):
    baseline = run_with(client, session_factory, version, "accurate-model", [1] * 6)
    resp = start_run(client, version, baseline_run_id=baseline, evaluation_profile="generic-v1")
    assert resp.status_code == 409 and "profile" in resp.json()["details"][0]["message"]


def test_baseline_must_be_finished(client, enqueued, version):
    queued = start_run(client, version).json()["id"]
    resp = start_run(client, version, baseline_run_id=queued)
    assert resp.status_code == 409 and resp.json()["code"] == "baseline_not_finished"


def test_set_baseline_on_existing_run(client, enqueued, session_factory, version):
    baseline = run_with(client, session_factory, version, "accurate-model", [1] * 6)
    current = run_with(client, session_factory, version, "fast-model", [1, 1, 1, 0, 0, 0])
    resp = client.post(f"{RUNS}/{current}/baseline", json={"baseline_run_id": baseline})
    assert resp.status_code == 200 and resp.json()["baseline_run_id"] == baseline
    assert client.get(f"{RUNS}/{current}/regressions").json()["state"] == "evaluated"

    cleared = client.post(f"{RUNS}/{current}/baseline", json={"baseline_run_id": None})
    assert cleared.json()["baseline_run_id"] is None
    body = client.get(f"{RUNS}/{current}/regressions").json()
    assert body["state"] == "no_baseline"
    with session_factory() as s:
        assert s.scalar(select(func.count()).select_from(RegressionFinding)) == 0


def test_set_baseline_validation(client, enqueued, session_factory, version):
    run_id = run_with(client, session_factory, version, "fast-model", [1] * 6)
    own = client.post(f"{RUNS}/{run_id}/baseline", json={"baseline_run_id": run_id})
    assert own.status_code == 400 and own.json()["code"] == "invalid_baseline"
    missing = client.post(f"{RUNS}/{run_id}/baseline", json={"baseline_run_id": str(uuid4())})
    assert missing.status_code == 404
    assert client.post(f"{RUNS}/{uuid4()}/baseline", json={"baseline_run_id": None}).status_code == 404
    other = make_version(client, keys=[f"x-{i}" for i in range(6)])
    foreign = run_with(client, session_factory, other, "fast-model", [1] * 6)
    assert client.post(f"{RUNS}/{run_id}/baseline", json={"baseline_run_id": foreign}).status_code == 409
    assert client.post(f"{RUNS}/{run_id}/baseline", json={"extra": 1}).status_code == 400


def test_failed_baseline_cannot_be_used(client, enqueued, session_factory, version):
    run_id = start_run(client, version, model_aliases=["fast-model"]).json()["id"]
    finish_run(session_factory, run_id, {"fast-model": [("provider_error", None, None, None)] * 6},
               final="failed")
    resp = start_run(client, version, baseline_run_id=run_id)
    assert resp.status_code == 409 and resp.json()["code"] == "baseline_not_finished"


def test_all_failed_candidate_has_no_quality_and_is_not_recommended(
    client, enqueued, session_factory, version
):
    run_id = start_run(client, version, model_aliases=["fast-model", "accurate-model"]).json()["id"]
    finish_run(
        session_factory, run_id,
        {
            "fast-model": [("provider_error", None, None, None)] * 6,
            "accurate-model": rows_with([1] * 6),
        },
        final="completed_with_errors",
    )
    body = client.get(f"{RUNS}/{run_id}/comparison").json()
    by = {m["model_alias"]: m for m in body["models"]}
    assert by["fast-model"]["quality_score"] is None and by["fast-model"]["failure_rate"] == 1.0
    assert body["ranking"]["recommended"] == "accurate-model"
    ranked = {m["model_alias"]: m for m in body["ranking"]["models"]}
    assert ranked["fast-model"]["eligible"] is False and ranked["fast-model"]["reasons"]


def test_report_bundles_run_comparison_and_regressions(client, enqueued, session_factory, version):
    baseline = run_with(client, session_factory, version, "accurate-model", [1] * 6)
    current = run_with(client, session_factory, version, "accurate-model", [1] * 6,
                       baseline_run_id=baseline)
    report = client.get(f"{RUNS}/{current}/report").json()
    assert report["run"]["id"] == current and report["run"]["baseline_run_id"] == baseline
    assert report["comparison"]["models"][0]["model_alias"] == "accurate-model"
    assert report["regressions"]["state"] == "evaluated"
    assert report["generated_at"] and "workload" in report["note"]
    assert client.get(f"{RUNS}/{start_run(client, version).json()['id']}/report").status_code == 409
