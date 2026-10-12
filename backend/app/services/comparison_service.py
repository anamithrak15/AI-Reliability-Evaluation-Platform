from collections import defaultdict
from dataclasses import asdict
from decimal import Decimal
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.evaluation import ranking as ranking_mod
from app.evaluation import regression as regression_mod
from app.evaluation.summary import ModelSummary, ResultRow, summarize
from app.models import EvaluationRun, RegressionFinding, RunSummary
from app.repositories import run_repo
from app.schemas.comparison import (
    ComparisonOut,
    FindingOut,
    ModelSummaryOut,
    RankedModelOut,
    RankingOut,
    RegressionsOut,
)
from app.services.run_state import TERMINAL_STATES

STORABLE_STATES = {"completed", "completed_with_errors", "failed"}
BASELINE_STATES = {"completed", "completed_with_errors"}


def _f(value: Decimal | float | None) -> float | None:
    return None if value is None else float(value)


def _d(value: float | None) -> Decimal | None:
    return None if value is None else Decimal(str(round(value, 8)))


def compute_summaries(session: Session, run: EvaluationRun) -> list[ModelSummary]:
    by_model: dict[str, list[ResultRow]] = defaultdict(list)
    for result, metrics in run_repo.results_with_metrics(session, run.id):
        by_model[result.model_alias].append(
            ResultRow(
                status=result.status,
                latency_ms=result.latency_ms,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                cost_usd=_f(result.estimated_cost_usd),
                quality=_f(metrics.get("quality")),
                accuracy=_f(metrics.get("accuracy")),
            )
        )
    aliases = list(run.config_snapshot.get("model_aliases", []))
    aliases += [a for a in by_model if a not in aliases]
    return [summarize(alias, by_model.get(alias, [])) for alias in aliases]


def store_summaries(session: Session, run: EvaluationRun) -> list[ModelSummary]:
    summaries = compute_summaries(session, run)
    session.execute(delete(RunSummary).where(RunSummary.run_id == run.id))
    session.add_all(
        RunSummary(
            run_id=run.id,
            model_alias=s.model_alias,
            quality_score=_d(s.quality_score),
            success_rate=_d(s.success_rate),
            failure_rate=_d(s.failure_rate),
            latency_p50_ms=_d(s.latency_p50_ms),
            latency_p95_ms=_d(s.latency_p95_ms),
            total_input_tokens=s.total_input_tokens,
            total_output_tokens=s.total_output_tokens,
            estimated_cost_usd=_d(s.estimated_cost_usd),
            summary_json=s.as_dict(),
        )
        for s in summaries
    )
    session.commit()
    return summaries


def get_summaries(session: Session, run: EvaluationRun) -> list[ModelSummary]:
    if run.status not in STORABLE_STATES:
        return compute_summaries(session, run)
    stored = session.scalars(select(RunSummary).where(RunSummary.run_id == run.id)).all()
    expected = len(run.config_snapshot.get("model_aliases", []))
    if expected and len(stored) == expected:
        by_alias = {
            r.model_alias: ModelSummary(**{k: v for k, v in r.summary_json.items() if k != "executed"})
            for r in stored
        }
        return [by_alias[a] for a in run.config_snapshot["model_aliases"]]
    return store_summaries(session, run)


def _require_finished(run: EvaluationRun) -> None:
    if run.status not in TERMINAL_STATES:
        raise AppError(409, "run_not_finished", "Run has not finished yet")


def get_comparison(session: Session, run: EvaluationRun) -> ComparisonOut:
    _require_finished(run)
    settings = get_settings()
    summaries = get_summaries(session, run)
    constraints = ranking_mod.constraints_from_settings(settings)
    weights = ranking_mod.weights_from_settings(settings)
    ranked = ranking_mod.rank(summaries, constraints, weights)
    cfg = run.config_snapshot
    return ComparisonOut(
        run_id=run.id,
        status=run.status,
        dataset_name=cfg.get("dataset_name"),
        dataset_version_number=cfg.get("dataset_version_number"),
        content_hash=cfg.get("content_hash"),
        evaluation_profile=cfg.get("evaluation_profile"),
        models=[ModelSummaryOut(**s.as_dict()) for s in summaries],
        ranking=RankingOut(
            models=[RankedModelOut(**asdict(m)) for m in ranked.models],
            recommended=ranked.recommended,
            explanation=ranked.explanation,
            notes=ranked.notes,
            constraints=asdict(constraints),
            weights=weights.as_dict(),
        ),
    )


def validate_baseline(
    session: Session, baseline_id: UUID, current_cfg: dict, self_id: UUID | None = None
) -> EvaluationRun:
    if baseline_id == self_id:
        raise AppError(400, "invalid_baseline", "A run cannot be its own baseline")
    baseline = run_repo.get_run(session, baseline_id)
    if baseline is None:
        raise AppError(404, "baseline_run_not_found", "Baseline run not found")
    if baseline.status not in BASELINE_STATES:
        raise AppError(409, "baseline_not_finished", "Baseline run must be completed")
    reasons = regression_mod.incompatibilities(current_cfg, baseline.config_snapshot)
    if reasons:
        raise AppError(
            409, "incompatible_baseline", "Baseline is not comparable with this run",
            [{"loc": "baseline_run_id", "message": r} for r in reasons],
        )
    return baseline


def _evaluate(
    session: Session, run: EvaluationRun, baseline: EvaluationRun
) -> list[regression_mod.Finding]:
    th = regression_mod.Thresholds.from_settings(get_settings())
    current = {s.model_alias: s for s in get_summaries(session, run)}
    base = {s.model_alias: s for s in get_summaries(session, baseline)}
    pairs = regression_mod.pair_models(list(current), list(base))
    findings: list[regression_mod.Finding] = []
    for cur_alias, base_alias, cross in pairs:
        findings += regression_mod.detect(base[base_alias], current[cur_alias], th, cross)
    paired = {p[0] for p in pairs}
    for alias in current:
        if alias not in paired:
            findings.append(
                regression_mod.Finding(
                    alias, "model_pairing", None, None, None, "info",
                    "The baseline run has no results for this model, so it was not compared.",
                )
            )
    return findings


def refresh_regressions(session: Session, run: EvaluationRun) -> RegressionsOut:
    """Recompute and persist findings for a finished run; idempotent."""
    thresholds = {k: float(v) for k, v in asdict(regression_mod.Thresholds.from_settings(get_settings())).items()}
    session.execute(delete(RegressionFinding).where(RegressionFinding.run_id == run.id))
    state, reasons, findings = "no_baseline", [], []
    baseline = run_repo.get_run(session, run.baseline_run_id) if run.baseline_run_id else None
    if baseline is not None:
        reasons = regression_mod.incompatibilities(run.config_snapshot, baseline.config_snapshot)
        if reasons:
            state = "incompatible"
        else:
            state, findings = "evaluated", _evaluate(session, run, baseline)
            session.add_all(
                RegressionFinding(
                    run_id=run.id, model_alias=f.model_alias, metric_name=f.metric_name,
                    baseline_value=_d(f.baseline_value), current_value=_d(f.current_value),
                    delta=_d(f.delta), severity=f.severity, explanation=f.explanation,
                )
                for f in findings
            )
    session.commit()
    worst = max((f.severity for f in findings), key=regression_mod.SEVERITY_ORDER.get, default=None)
    return RegressionsOut(
        run_id=run.id,
        baseline_run_id=run.baseline_run_id,
        state=state,
        incompatibilities=reasons,
        thresholds=thresholds,
        findings=[FindingOut(**asdict(f)) for f in findings],
        highest_severity=worst,
    )


def get_regressions(session: Session, run: EvaluationRun) -> RegressionsOut:
    if run.baseline_run_id:
        _require_finished(run)
    return refresh_regressions(session, run)
