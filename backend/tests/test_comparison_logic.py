import pytest

from app.evaluation.ranking import Constraints, Weights, rank
from app.evaluation.regression import Thresholds, detect, incompatibilities, pair_models
from app.evaluation.summary import ResultRow, percentile, summarize

TH = Thresholds(
    quality_drop=0.03, failure_rise=0.02, p95_rise_pct=0.25, cost_rise_pct=0.20,
    quality_floor=0.5, min_samples=5,
)


def rows(n=10, quality=1.0, latency=100.0, cost=None, status="success"):
    return [ResultRow(status, latency, 10, 5, cost, quality, quality) for _ in range(n)]


@pytest.mark.parametrize(
    "values,p,expected",
    [
        ([], 50, None),
        ([7], 95, 7.0),
        ([1, 2, 3, 4], 50, 2.5),
        ([1, 2, 3, 4, 5], 50, 3.0),
        ([10, 20, 30, 40, 50], 95, 48.0),
        ([50, 10, 30], 100, 50.0),
    ],
)
def test_percentile(values, p, expected):
    assert percentile(values, p) == expected


def test_summary_core_rates_and_percentiles():
    data = rows(8, quality=1.0) + [ResultRow("timeout", 5000), ResultRow("provider_error")]
    s = summarize("m", data)
    assert (s.scheduled, s.successes, s.failures, s.skipped) == (10, 8, 2, 0)
    assert s.success_rate == 0.8 and s.failure_rate == 0.2
    assert s.latency_p50_ms == 100.0 and s.latency_n == 8  # failed attempts are excluded
    assert s.quality_score == 1.0 and s.quality_n == 8


def test_summary_skipped_pairs_are_not_failures():
    s = summarize("m", rows(3) + [ResultRow("skipped")] * 2)
    assert s.executed == 3 and s.skipped == 2
    assert s.failure_rate == 0.0 and s.success_rate == 1.0


def test_summary_missing_values_are_none_not_zero():
    data = [ResultRow("success", None, None, None, None, None, None)] * 4
    s = summarize("m", data)
    assert s.quality_score is None and s.quality_n == 0
    assert s.latency_p95_ms is None
    assert s.total_input_tokens is None and s.estimated_cost_usd is None
    assert s.cost_per_case_usd is None and s.cost_complete is False


def test_summary_unscored_cases_are_excluded_from_quality_denominator():
    data = rows(2, quality=1.0) + [ResultRow("success", 10, 1, 1, None, None, None)] * 2
    s = summarize("m", data)
    assert s.quality_score == 1.0 and s.quality_n == 2


def test_summary_partial_cost_is_flagged():
    data = rows(2, cost=0.02) + rows(2, cost=None)
    s = summarize("m", data)
    assert s.estimated_cost_usd == pytest.approx(0.04) and s.cost_n == 2
    assert s.cost_per_case_usd == pytest.approx(0.02) and s.cost_complete is False


def test_summary_empty_input():
    s = summarize("m", [])
    assert s.executed == 0 and s.success_rate == 0.0 and s.failure_rate == 0.0


def test_summary_all_failed_has_no_latency_or_quality():
    s = summarize("m", [ResultRow("provider_error")] * 5)
    assert s.failure_rate == 1.0 and s.quality_score is None and s.latency_p50_ms is None


def _s(**kw):
    n = kw.pop("n", 10)
    return summarize("m", rows(n, **kw))


def _cmp(base, cur, **kw):
    return {(f.metric_name, f.severity) for f in detect(base, cur, TH, **kw)}


def test_no_regression_when_equal():
    assert detect(_s(), _s(), TH) == []


def test_quality_drop_threshold_is_strictly_greater():
    base = summarize("m", rows(100, quality=1.0))
    exactly = summarize("m", rows(97, quality=1.0) + rows(3, quality=0.0))  # -3 points
    over = summarize("m", rows(96, quality=1.0) + rows(4, quality=0.0))  # -4 points
    assert detect(base, exactly, TH) == []
    assert ("quality_score", "warning") in _cmp(base, over)


def test_quality_below_floor_is_critical_not_warning():
    found = detect(_s(quality=1.0), _s(quality=0.4), TH)
    assert [(f.metric_name, f.severity) for f in found] == [("quality_score", "critical")]
    assert found[0].delta == pytest.approx(-0.6)


def test_quality_improvement_is_not_flagged():
    assert detect(_s(quality=0.8), _s(quality=0.95), TH) == []


def test_failure_rate_rise_warns():
    base = summarize("m", rows(10))
    cur = summarize("m", rows(8) + [ResultRow("timeout")] * 2)
    assert ("failure_rate", "warning") in _cmp(base, cur)


def test_p95_relative_threshold():
    base, same, slower = _s(latency=100), _s(latency=125), _s(latency=130)
    assert detect(base, same, TH) == []  # exactly +25%
    assert ("latency_p95_ms", "warning") in _cmp(base, slower)


def test_zero_baseline_latency_is_skipped():
    assert detect(_s(latency=0.0), _s(latency=500), TH) == []


def test_missing_quality_is_informational_not_a_regression():
    base = summarize("m", [ResultRow("success", 100, 10, 5, None, None, None)] * 10)
    found = detect(base, _s(quality=0.5), TH)
    assert [(f.metric_name, f.severity) for f in found] == [("quality_score", "info")]


def test_cost_rise_is_informational():
    found = detect(_s(cost=0.01), _s(cost=0.02), TH)
    assert [(f.metric_name, f.severity) for f in found] == [("cost_per_case_usd", "info")]


def test_unknown_cost_is_never_compared():
    assert detect(_s(cost=None), _s(cost=0.5), TH) == []
    assert detect(_s(cost=0.5), _s(cost=None), TH) == []


def test_small_samples_skip_thresholds_with_an_info_finding():
    found = detect(_s(n=3, quality=1.0), _s(n=3, quality=0.1), TH)
    assert [(f.metric_name, f.severity) for f in found] == [("sample_size", "info")]


def test_sample_size_difference_is_reported():
    assert ("sample_size", "info") in _cmp(_s(n=10), _s(n=8))


def test_cross_model_explanations_name_the_baseline_model():
    base = summarize("accurate-model", rows(10, quality=1.0))
    cur = summarize("fast-model", rows(10, quality=0.6))
    found = detect(base, cur, TH, cross_model=True)
    assert "accurate-model" in found[0].explanation


def test_incompatibilities():
    a = {"content_hash": "x", "evaluation_profile": "p", "dataset_version_number": 1}
    assert incompatibilities(a, dict(a)) == []
    assert len(incompatibilities(a, {**a, "content_hash": "y"})) == 1
    assert len(incompatibilities(a, {**a, "content_hash": "y", "evaluation_profile": "q"})) == 2


def test_pair_models():
    assert pair_models(["a", "b"], ["b", "c"]) == [("b", "b", False)]
    assert pair_models(["fast"], ["accurate"]) == [("fast", "accurate", True)]
    assert pair_models(["a", "b"], ["c"]) == []
    assert pair_models(["a", "b"], ["c", "d"]) == []


C = Constraints(min_quality=0.5, max_failure_rate=0.2, max_p95_ms=0, max_cost_per_case_usd=0, min_samples=5)
W = Weights(0.6, 0.25, 0.15)


def _named(alias, **kw):
    n = kw.pop("n", 10)
    return summarize(alias, rows(n, **kw))


def test_ranking_orders_by_weighted_score():
    result = rank(
        [
            _named("slow-good", quality=0.95, latency=900, cost=0.02),
            _named("fast-ok", quality=0.9, latency=100, cost=0.01),
        ],
        C, W,
    )
    assert result.recommended == "fast-ok"
    assert [m.model_alias for m in result.models] == ["fast-ok", "slow-good"]
    assert result.models[0].rank == 1 and result.models[0].components["latency"] == 1.0
    assert result.models[0].overall_score == pytest.approx(0.6 * 0.9 + 0.25 * 1 + 0.15 * 1)


def test_ranking_hard_constraints_exclude_models_with_reasons():
    result = rank(
        [
            summarize("best-but-flaky", rows(7) + [ResultRow("timeout")] * 3),
            _named("weak", quality=0.3),
            _named("tiny-sample", quality=1.0, n=3),
            _named("fine", quality=0.8),
        ],
        C, W,
    )
    assert result.recommended == "fine"
    reasons = {m.model_alias: " ".join(m.reasons) for m in result.models if not m.eligible}
    assert "failure rate" in reasons["best-but-flaky"]
    assert "below minimum" in reasons["weak"]
    assert "executed cases" in reasons["tiny-sample"]
    assert all(m.rank is None for m in result.models if not m.eligible)


def test_ranking_missing_cost_is_renormalized_not_zero():
    result = rank([_named("a", quality=0.8, latency=100)], C, W)
    m = result.models[0]
    assert m.missing_components == ["cost"] and "cost" not in m.components
    assert m.overall_score == pytest.approx((0.6 * 0.8 + 0.25 * 1) / 0.85)


def test_ranking_notes_mixed_component_sets():
    result = rank(
        [_named("priced", quality=0.9, latency=100, cost=0.01), _named("free", quality=0.9, latency=120)],
        C, W,
    )
    assert any("different component sets" in n for n in result.notes)


def test_ranking_optional_constraints_require_data_when_enabled():
    strict = Constraints(0.5, 0.2, max_p95_ms=500, max_cost_per_case_usd=0.01, min_samples=5)
    result = rank(
        [
            _named("no-cost", quality=0.9, latency=100),
            _named("too-slow", quality=0.9, latency=900, cost=0.001),
            _named("ok", quality=0.9, latency=100, cost=0.001),
        ],
        strict, W,
    )
    assert result.recommended == "ok"
    reasons = {m.model_alias: " ".join(m.reasons) for m in result.models if not m.eligible}
    assert "cost unavailable" in reasons["no-cost"] and "above maximum" in reasons["too-slow"]


def test_ranking_no_eligible_model():
    result = rank([_named("weak", quality=0.1)], C, W)
    assert result.recommended is None and "No model satisfies" in result.explanation


def test_ranking_ties_are_deterministic():
    result = rank([_named("b", quality=0.9), _named("a", quality=0.9)], C, W)
    assert [m.model_alias for m in result.models] == ["a", "b"]


def test_ranking_always_carries_the_scope_note():
    assert "workload and test dataset" in rank([_named("a")], C, W).notes[-1]
