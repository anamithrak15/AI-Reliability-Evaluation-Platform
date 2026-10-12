from datetime import timedelta
from uuid import UUID

from sqlalchemy import delete, func, select, update

import app.evaluation.orchestrator as orch
from app.core.config import get_settings
from app.evaluation.mock_adapter import scenario_for
from app.models import CaseMetric, CaseResult, EvaluationRun
from app.models.entities import utcnow
from app.repositories import run_repo
from tests.test_runs_api import RUNS, make_version, start_run


def _key(scenario):
    return next(k for k in (f"k{i}" for i in range(1000)) if scenario_for("flaky-model", k) == scenario)


KEYS = [_key("permanent_error"), _key("timeout"), _key("transient_then_ok"), _key("ok")]


def _results(client, run_id):
    return client.get(f"{RUNS}/{run_id}/results", params={"limit": 200}).json()["items"]


def _run(client, session_factory, **kw):
    version_id = make_version(client, keys=KEYS)
    run_id = start_run(client, version_id, model_aliases=["fast-model", "flaky-model"], **kw).json()["id"]
    orch.execute_run(session_factory, UUID(run_id))
    return run_id


def test_every_pair_terminal_and_failures_do_not_crash_run(client, enqueued, session_factory, no_backoff):
    run_id = _run(client, session_factory)
    run = client.get(f"{RUNS}/{run_id}").json()
    assert run["status"] == "completed_with_errors"
    assert run["started_at"] and run["completed_at"]
    assert run["progress"]["completed_pairs"] == run["progress"]["total_pairs"] == 8

    by = {(r["case_key"], r["model_alias"]): r for r in _results(client, run_id)}
    assert len(by) == 8
    assert all(by[(k, "fast-model")]["status"] == "success" for k in KEYS)

    perm = by[(KEYS[0], "flaky-model")]
    assert perm["status"] == "provider_error" and perm["attempt_count"] == 1
    assert perm["error_code"] == "mock_provider_error"

    timed_out = by[(KEYS[1], "flaky-model")]
    assert timed_out["status"] == "timeout"
    assert timed_out["attempt_count"] == 1 + get_settings().max_retries

    recovered = by[(KEYS[2], "flaky-model")]
    assert recovered["status"] == "success" and recovered["attempt_count"] == 2
    assert recovered["input_tokens"] and recovered["estimated_cost_usd"] is None


def test_duplicate_delivery_is_a_noop(client, enqueued, session_factory, no_backoff):
    run_id = _run(client, session_factory)
    before = _results(client, run_id)
    orch.execute_run(session_factory, UUID(run_id))
    after = _results(client, run_id)
    assert [r["id"] for r in before] == [r["id"] for r in after]


def test_stale_running_run_resumes_without_duplicates(client, enqueued, session_factory, no_backoff):
    run_id = _run(client, session_factory)
    with session_factory() as s:
        s.execute(
            update(EvaluationRun)
            .where(EvaluationRun.id == UUID(run_id))
            .values(status="running", completed_at=None, started_at=utcnow() - timedelta(hours=2))
        )
        victims = s.query(CaseResult.id).filter(CaseResult.run_id == UUID(run_id)).limit(3).all()
        ids = [v[0] for v in victims]
        s.execute(delete(CaseMetric).where(CaseMetric.case_result_id.in_(ids)))
        s.execute(delete(CaseResult).where(CaseResult.id.in_(ids)))
        s.commit()

    orch.execute_run(session_factory, UUID(run_id))
    results = _results(client, run_id)
    assert len(results) == 8 and len({(r["case_key"], r["model_alias"]) for r in results}) == 8
    assert client.get(f"{RUNS}/{run_id}").json()["status"] == "completed_with_errors"


def test_fresh_running_run_is_not_taken_over(client, enqueued, session_factory):
    run_id = start_run(client, make_version(client)).json()["id"]
    with session_factory() as s:
        run_repo.transition(s, UUID(run_id), {"queued"}, "running", started_at=utcnow())
    orch.execute_run(session_factory, UUID(run_id))
    assert _results(client, run_id) == []


def test_cancelled_queued_run_is_not_executed(client, enqueued, session_factory):
    run_id = start_run(client, make_version(client)).json()["id"]
    client.post(f"{RUNS}/{run_id}/cancel")
    orch.execute_run(session_factory, UUID(run_id))
    assert _results(client, run_id) == []
    assert client.get(f"{RUNS}/{run_id}").json()["status"] == "cancelled"


def test_cancel_mid_run_skips_remaining_pairs(client, enqueued, session_factory, monkeypatch):
    run_id = start_run(
        client, make_version(client, n_cases=4), model_aliases=["fast-model"], max_concurrency=1
    ).json()["id"]
    real = orch.call_model
    calls = []

    def cancelling(*args, **kwargs):
        if not calls:
            calls.append(1)
            with session_factory() as s:
                run_repo.transition(s, UUID(run_id), {"running"}, "cancelled", completed_at=utcnow())
        return real(*args, **kwargs)

    monkeypatch.setattr(orch, "call_model", cancelling)
    orch.execute_run(session_factory, UUID(run_id))

    run = client.get(f"{RUNS}/{run_id}").json()
    assert run["status"] == "cancelled"
    statuses = sorted(r["status"] for r in _results(client, run_id))
    assert statuses == ["skipped", "skipped", "skipped", "success"]
    assert all(r["error_code"] == "cancelled" for r in _results(client, run_id) if r["status"] == "skipped")


def test_run_timeout_skips_everything_and_fails(client, enqueued, session_factory, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_run_seconds", 0)
    run_id = start_run(client, make_version(client)).json()["id"]
    orch.execute_run(session_factory, UUID(run_id))
    run = client.get(f"{RUNS}/{run_id}").json()
    assert run["status"] == "failed" and "skipped=6" in run["error_summary"]
    assert {r["error_code"] for r in _results(client, run_id)} == {"run_timeout"}


def test_unexpected_crash_marks_run_failed_with_redacted_summary(
    client, enqueued, session_factory, monkeypatch
):
    def explode(*args, **kwargs):
        raise RuntimeError("db exploded api_key=TOPSECRET")

    monkeypatch.setattr(orch, "_process", explode)
    run_id = start_run(client, make_version(client)).json()["id"]
    orch.execute_run(session_factory, UUID(run_id))
    run = client.get(f"{RUNS}/{run_id}").json()
    assert run["status"] == "failed"
    assert "TOPSECRET" not in run["error_summary"] and "[REDACTED]" in run["error_summary"]


def test_results_filtering_and_pagination(client, enqueued, session_factory, no_backoff):
    run_id = _run(client, session_factory)
    flaky = client.get(f"{RUNS}/{run_id}/results", params={"model_alias": "flaky-model"}).json()
    assert flaky["total"] == 4
    timeouts = client.get(f"{RUNS}/{run_id}/results", params={"status": "timeout"}).json()
    assert timeouts["total"] == 1
    page = client.get(f"{RUNS}/{run_id}/results", params={"limit": 3, "offset": 6}).json()
    assert page["total"] == 8 and len(page["items"]) == 2


def test_successful_results_are_scored_and_failures_are_not(client, enqueued, session_factory, no_backoff):
    run_id = _run(client, session_factory)
    items = _results(client, run_id)
    for r in items:
        if r["status"] == "success":
            assert float(r["metrics"]["quality"]) in (0.0, 1.0)
            assert r["metrics"]["quality"] == r["metrics"]["accuracy"]
        else:
            assert r["metrics"] == {}
    orch.execute_run(session_factory, UUID(run_id))  # redelivery must not duplicate metrics
    with session_factory() as s:
        n_metrics = s.scalar(select(func.count()).select_from(CaseMetric))
    assert n_metrics == 2 * sum(r["status"] == "success" for r in items)


def test_per_model_budget_skips_only_the_model_that_exceeded_it(
    client, enqueued, session_factory, no_backoff, monkeypatch
):
    from decimal import Decimal

    from app.evaluation.llm_adapter import LLMResult

    def priced(alias, case_key, messages, attempt):
        cost = Decimal("0.03") if alias == "fast-model" else None
        return LLMResult('{"category": "billing"}', 10, 5, 5, cost)

    monkeypatch.setattr(orch, "call_model", priced)
    monkeypatch.setattr(get_settings(), "live_budget_usd_per_model", 0.05)
    version_id = make_version(client, n_cases=5)
    run_id = start_run(
        client, version_id, model_aliases=["fast-model", "accurate-model"], max_concurrency=1
    ).json()["id"]
    orch.execute_run(session_factory, UUID(run_id))

    items = _results(client, run_id)
    fast = [r for r in items if r["model_alias"] == "fast-model"]
    assert sorted(r["status"] for r in fast) == ["skipped"] * 3 + ["success"] * 2
    assert {r["error_code"] for r in fast if r["status"] == "skipped"} == {"budget_exceeded"}
    assert all(r["status"] == "success" for r in items if r["model_alias"] == "accurate-model")
    assert client.get(f"{RUNS}/{run_id}").json()["status"] == "completed_with_errors"
