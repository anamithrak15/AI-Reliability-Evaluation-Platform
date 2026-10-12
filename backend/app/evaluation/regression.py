"""Baseline compatibility and regression detection. Pure functions over ModelSummary values."""

from dataclasses import dataclass
from typing import Any

from app.core.config import Settings
from app.evaluation.summary import ModelSummary

SEVERITY_ORDER = {"info": 0, "warning": 1, "critical": 2}
_EPS = 1e-9


@dataclass(frozen=True)
class Thresholds:
    quality_drop: float
    failure_rise: float
    p95_rise_pct: float
    cost_rise_pct: float
    quality_floor: float
    min_samples: int

    @classmethod
    def from_settings(cls, s: Settings) -> "Thresholds":
        return cls(
            quality_drop=s.regression_quality_drop,
            failure_rise=s.regression_failure_rise,
            p95_rise_pct=s.regression_p95_rise_pct,
            cost_rise_pct=s.regression_cost_rise_pct,
            quality_floor=s.regression_quality_floor,
            min_samples=s.regression_min_samples,
        )


@dataclass(frozen=True)
class Finding:
    model_alias: str
    metric_name: str
    baseline_value: float | None
    current_value: float | None
    delta: float | None
    severity: str
    explanation: str


def incompatibilities(current_cfg: dict[str, Any], baseline_cfg: dict[str, Any]) -> list[str]:
    """Reasons the two runs cannot be compared; empty means compatible."""
    reasons = []
    if current_cfg.get("content_hash") != baseline_cfg.get("content_hash"):
        reasons.append(
            "dataset content differs "
            f"(baseline v{baseline_cfg.get('dataset_version_number')}, "
            f"current v{current_cfg.get('dataset_version_number')})"
        )
    if current_cfg.get("evaluation_profile") != baseline_cfg.get("evaluation_profile"):
        reasons.append(
            "evaluation profile differs "
            f"(baseline {baseline_cfg.get('evaluation_profile')}, "
            f"current {current_cfg.get('evaluation_profile')})"
        )
    return reasons


def pair_models(
    current: list[str], baseline: list[str]
) -> list[tuple[str, str, bool]]:
    """(current alias, baseline alias, cross_model). Same alias wins; two single-model runs are paired."""
    pairs = [(a, a, False) for a in current if a in baseline]
    if not pairs and len(current) == 1 and len(baseline) == 1:
        pairs = [(current[0], baseline[0], True)]
    return pairs


def _pp(value: float) -> str:
    return f"{value * 100:.1f} pts"


def detect(
    base: ModelSummary, cur: ModelSummary, th: Thresholds, cross_model: bool = False
) -> list[Finding]:
    alias = cur.model_alias
    prefix = f"Compared with baseline model {base.model_alias}: " if cross_model else ""
    out: list[Finding] = []

    def add(metric, b, c, severity, text):
        delta = None if b is None or c is None else c - b
        out.append(Finding(alias, metric, b, c, delta, severity, prefix + text))

    if min(base.executed, cur.executed) < th.min_samples:
        add(
            "sample_size", base.executed, cur.executed, "info",
            f"Too few executed cases to judge regressions (baseline {base.executed}, "
            f"current {cur.executed}, minimum {th.min_samples}); thresholds were not applied.",
        )
        return out
    if base.executed != cur.executed:
        add(
            "sample_size", base.executed, cur.executed, "info",
            f"Executed case counts differ (baseline {base.executed}, current {cur.executed}).",
        )

    if base.quality_score is None or cur.quality_score is None:
        add("quality_score", base.quality_score, cur.quality_score, "info",
            "Quality is unavailable for one side, so it was not compared.")
    else:
        drop = base.quality_score - cur.quality_score
        if cur.quality_score < th.quality_floor:
            add("quality_score", base.quality_score, cur.quality_score, "critical",
                f"Quality {cur.quality_score:.3f} is below the absolute minimum {th.quality_floor:.3f}.")
        elif drop > th.quality_drop + _EPS:
            add("quality_score", base.quality_score, cur.quality_score, "warning",
                f"Quality fell {_pp(drop)} (limit {_pp(th.quality_drop)}).")

    rise = cur.failure_rate - base.failure_rate
    if rise > th.failure_rise + _EPS:
        add("failure_rate", base.failure_rate, cur.failure_rate, "warning",
            f"Failure rate rose {_pp(rise)} (limit {_pp(th.failure_rise)}).")

    if base.latency_p95_ms is not None and cur.latency_p95_ms is not None and base.latency_p95_ms > 0:
        rel = (cur.latency_p95_ms - base.latency_p95_ms) / base.latency_p95_ms
        if rel > th.p95_rise_pct + _EPS:
            add("latency_p95_ms", base.latency_p95_ms, cur.latency_p95_ms, "warning",
                f"p95 latency rose {rel * 100:.0f}% (limit {th.p95_rise_pct * 100:.0f}%).")

    if base.cost_per_case_usd and cur.cost_per_case_usd is not None:
        rel = (cur.cost_per_case_usd - base.cost_per_case_usd) / base.cost_per_case_usd
        if rel > th.cost_rise_pct + _EPS:
            partial = "" if base.cost_complete and cur.cost_complete else " (partial cost data)"
            add("cost_per_case_usd", base.cost_per_case_usd, cur.cost_per_case_usd, "info",
                f"Estimated cost per case rose {rel * 100:.0f}% (limit {th.cost_rise_pct * 100:.0f}%){partial}.")
    return out
