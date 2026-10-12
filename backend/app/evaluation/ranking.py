"""Constraint-gated model ranking with a documented weighted score. Pure functions."""

from dataclasses import dataclass, field

from app.core.config import Settings
from app.evaluation.summary import ModelSummary

NOTE = "This recommendation applies only to this workload and test dataset; it is not a production decision."


@dataclass(frozen=True)
class Constraints:
    min_quality: float
    max_failure_rate: float
    max_p95_ms: float  # 0 disables
    max_cost_per_case_usd: float  # 0 disables
    min_samples: int


@dataclass(frozen=True)
class Weights:
    quality: float
    latency: float
    cost: float

    def as_dict(self) -> dict[str, float]:
        return {"quality": self.quality, "latency": self.latency, "cost": self.cost}


def constraints_from_settings(s: Settings) -> Constraints:
    return Constraints(
        min_quality=s.rank_min_quality,
        max_failure_rate=s.rank_max_failure_rate,
        max_p95_ms=s.rank_max_p95_ms,
        max_cost_per_case_usd=s.rank_max_cost_per_case_usd,
        min_samples=s.rank_min_samples,
    )


def weights_from_settings(s: Settings) -> Weights:
    return Weights(s.rank_weight_quality, s.rank_weight_latency, s.rank_weight_cost)


@dataclass
class RankedModel:
    model_alias: str
    eligible: bool
    reasons: list[str] = field(default_factory=list)
    components: dict[str, float] = field(default_factory=dict)
    missing_components: list[str] = field(default_factory=list)
    overall_score: float | None = None
    rank: int | None = None


@dataclass
class Ranking:
    models: list[RankedModel]
    recommended: str | None
    explanation: str
    notes: list[str]


def _violations(s: ModelSummary, c: Constraints) -> list[str]:
    out = []
    if s.executed < c.min_samples:
        out.append(f"only {s.executed} executed cases (minimum {c.min_samples})")
    if c.min_quality > 0:
        if s.quality_score is None:
            out.append("quality unavailable")
        elif s.quality_score < c.min_quality:
            out.append(f"quality {s.quality_score:.3f} below minimum {c.min_quality:.3f}")
    if s.failure_rate > c.max_failure_rate:
        out.append(f"failure rate {s.failure_rate:.3f} above maximum {c.max_failure_rate:.3f}")
    if c.max_p95_ms > 0:
        if s.latency_p95_ms is None:
            out.append("p95 latency unavailable")
        elif s.latency_p95_ms > c.max_p95_ms:
            out.append(f"p95 latency {s.latency_p95_ms:.0f} ms above maximum {c.max_p95_ms:.0f} ms")
    if c.max_cost_per_case_usd > 0:
        if s.cost_per_case_usd is None:
            out.append("cost unavailable")
        elif s.cost_per_case_usd > c.max_cost_per_case_usd:
            out.append(f"cost per case ${s.cost_per_case_usd:.6f} above maximum ${c.max_cost_per_case_usd:.6f}")
    return out


def _lower_is_better(values: dict[str, float]) -> dict[str, float]:
    """Min-max over the compared models; 1 is best. Equal values all score 1."""
    if not values:
        return {}
    lo, hi = min(values.values()), max(values.values())
    if hi == lo:
        return {k: 1.0 for k in values}
    return {k: 1 - (v - lo) / (hi - lo) for k, v in values.items()}


def rank(summaries: list[ModelSummary], c: Constraints, w: Weights) -> Ranking:
    entries = {s.model_alias: RankedModel(s.model_alias, True, _violations(s, c)) for s in summaries}
    for e in entries.values():
        e.eligible = not e.reasons
    eligible = [s for s in summaries if entries[s.model_alias].eligible]

    scores = {
        "quality": {s.model_alias: s.quality_score for s in eligible if s.quality_score is not None},
        "latency": _lower_is_better(
            {s.model_alias: s.latency_p95_ms for s in eligible if s.latency_p95_ms is not None}
        ),
        "cost": _lower_is_better(
            {s.model_alias: s.cost_per_case_usd for s in eligible if s.cost_per_case_usd is not None}
        ),
    }
    weight = w.as_dict()
    for s in eligible:
        e = entries[s.model_alias]
        for name in ("quality", "latency", "cost"):
            if s.model_alias in scores[name]:
                e.components[name] = scores[name][s.model_alias]
            else:
                e.missing_components.append(name)
        used = sum(weight[n] for n in e.components)
        if e.components:
            e.overall_score = (
                sum(weight[n] * v for n, v in e.components.items()) / used
                if used > 0
                else sum(e.components.values()) / len(e.components)
            )

    ordered = sorted(
        (e for e in entries.values() if e.eligible),
        key=lambda e: (-(e.overall_score if e.overall_score is not None else -1), e.model_alias),
    )
    for i, e in enumerate(ordered, 1):
        e.rank = i
    models = ordered + sorted((e for e in entries.values() if not e.eligible), key=lambda e: e.model_alias)

    notes = [
        "Latency and cost scores are min-max normalized across the compared eligible models "
        "(1 = best); with one eligible model they are 1.",
        "Missing components are excluded and the remaining weights are renormalized; "
        "missing data is never treated as zero.",
    ]
    if len({tuple(e.missing_components) for e in ordered}) > 1:
        notes.append("Eligible models were scored on different component sets; compare scores with care.")
    notes.append(NOTE)

    if not ordered:
        why = "; ".join(f"{e.model_alias}: {', '.join(e.reasons)}" for e in models) or "no models"
        return Ranking(models, None, f"No model satisfies the constraints ({why}).", notes)
    top = ordered[0]
    parts = ", ".join(f"{n} {v:.2f}" for n, v in top.components.items())
    explanation = f"{top.model_alias} ranks first with an overall score of {top.overall_score:.3f} ({parts})."
    if len(ordered) == 1 and len(models) > 1:
        explanation += " It is the only model that satisfies the constraints."
    return Ranking(models, top.model_alias, explanation, notes)
