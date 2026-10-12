"""Per-model aggregation of case results. Pure functions; missing data is never treated as zero."""

from dataclasses import asdict, dataclass
from typing import Iterable

FAILED_STATUSES = {"provider_error", "timeout", "invalid_output"}


@dataclass(frozen=True)
class ResultRow:
    status: str
    latency_ms: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None
    quality: float | None = None
    accuracy: float | None = None


@dataclass(frozen=True)
class ModelSummary:
    model_alias: str
    scheduled: int
    successes: int
    failures: int
    skipped: int
    # Rates use executed pairs (scheduled minus skipped) as the denominator.
    success_rate: float
    failure_rate: float
    quality_score: float | None
    quality_n: int
    accuracy: float | None
    latency_p50_ms: float | None
    latency_p95_ms: float | None
    latency_n: int
    total_input_tokens: int | None
    total_output_tokens: int | None
    token_n: int
    estimated_cost_usd: float | None
    cost_n: int
    cost_per_case_usd: float | None
    cost_complete: bool

    @property
    def executed(self) -> int:
        return self.scheduled - self.skipped

    def as_dict(self) -> dict:
        return asdict(self) | {"executed": self.executed}


def percentile(values: Iterable[float], p: float) -> float | None:
    """Linear-interpolation percentile (p in 0..100); None for an empty sample."""
    data = sorted(values)
    if not data:
        return None
    if len(data) == 1:
        return float(data[0])
    rank = (len(data) - 1) * p / 100
    lo = int(rank)
    hi = min(lo + 1, len(data) - 1)
    return float(data[lo] + (data[hi] - data[lo]) * (rank - lo))


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def summarize(model_alias: str, rows: list[ResultRow]) -> ModelSummary:
    skipped = sum(1 for r in rows if r.status == "skipped")
    ok = [r for r in rows if r.status == "success"]
    failures = sum(1 for r in rows if r.status in FAILED_STATUSES)
    executed = len(rows) - skipped

    qualities = [r.quality for r in ok if r.quality is not None]
    accuracies = [r.accuracy for r in ok if r.accuracy is not None]
    # Latency population: successful calls only.
    latencies = [r.latency_ms for r in ok if r.latency_ms is not None]
    in_tok = [r.input_tokens for r in ok if r.input_tokens is not None]
    out_tok = [r.output_tokens for r in ok if r.output_tokens is not None]
    costs = [r.cost_usd for r in ok if r.cost_usd is not None]

    total_cost = sum(costs) if costs else None
    return ModelSummary(
        model_alias=model_alias,
        scheduled=len(rows),
        successes=len(ok),
        failures=failures,
        skipped=skipped,
        success_rate=len(ok) / executed if executed else 0.0,
        failure_rate=failures / executed if executed else 0.0,
        quality_score=_mean(qualities),
        quality_n=len(qualities),
        accuracy=_mean(accuracies),
        latency_p50_ms=percentile(latencies, 50),
        latency_p95_ms=percentile(latencies, 95),
        latency_n=len(latencies),
        total_input_tokens=sum(in_tok) if in_tok else None,
        total_output_tokens=sum(out_tok) if out_tok else None,
        token_n=min(len(in_tok), len(out_tok)),
        estimated_cost_usd=total_cost,
        cost_n=len(costs),
        cost_per_case_usd=total_cost / len(costs) if costs else None,
        cost_complete=bool(ok) and len(costs) == len(ok),
    )
