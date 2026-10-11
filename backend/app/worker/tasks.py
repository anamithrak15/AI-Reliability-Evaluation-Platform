from uuid import UUID

from app.db.database import SessionLocal
from app.evaluation.llm_adapter import call_model
from app.evaluation.orchestrator import execute_run


def ping_job(model_alias: str = "fast-model") -> dict[str, object]:
    """Smoke job proving API -> Redis -> worker wiring."""
    r = call_model(
        model_alias, "ping", [{"role": "user", "content": "I was charged twice for my subscription."}], 1
    )
    return {"model": model_alias, "output": r.content}


def run_evaluation(run_id: str) -> None:
    execute_run(SessionLocal, UUID(run_id))
