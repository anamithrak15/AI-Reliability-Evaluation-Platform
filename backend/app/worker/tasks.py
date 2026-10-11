from app.evaluation.mock_adapter import generate


def ping_job(model_alias: str = "fast-model") -> dict[str, object]:
    """Day 1 smoke job proving API -> Redis -> worker wiring."""
    response = generate(model_alias, "ping", "I was charged twice for my subscription.")
    return {"model": model_alias, "output": response.content}
