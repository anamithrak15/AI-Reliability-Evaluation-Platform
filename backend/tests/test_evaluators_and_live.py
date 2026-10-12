from types import SimpleNamespace

import pytest

import app.evaluation.llm_adapter as adapter
from app.core.config import get_settings
from app.evaluation.errors import LLMProviderError, LLMTimeout
from app.evaluation.evaluators import evaluate

SCHEMA = {
    "type": "object",
    "required": ["category"],
    "properties": {"category": {"type": "string"}},
}


def q(cfg, expected, output):
    return {m.name: m.value for m in evaluate(cfg, expected, output)}


def test_exact_match_json_and_text_normalization():
    assert q({"type": "exact_match"}, {"a": 1}, '{"a": 1}')["quality"] == 1.0
    assert q({"type": "exact_match"}, {"a": 1}, '{"a": 2}')["quality"] == 0.0
    assert q({"type": "exact_match"}, {"a": 1}, "not json")["quality"] == 0.0
    cfg = {"type": "exact_match", "normalize": ["strip", "lowercase"]}
    assert q(cfg, {"text": "Yes"}, "  yes\n")["quality"] == 1.0
    assert q({"type": "exact_match"}, {"text": "Yes"}, "yes")["quality"] == 0.0


def test_contains_modes_and_case():
    cfg = {"type": "contains", "substrings": ["Refund", "sorry"]}
    assert q(cfg, None, "we are SORRY, refund issued")["quality"] == 1.0
    assert q(cfg, None, "refund issued")["quality"] == 0.0
    assert q({**cfg, "mode": "any"}, None, "refund issued")["quality"] == 1.0
    assert q({**cfg, "case_sensitive": True}, None, "refund sorry")["quality"] == 0.0


def test_regex():
    cfg = {"type": "regex", "pattern": r"^\d{3}$"}
    assert q(cfg, None, "123")["quality"] == 1.0
    assert q(cfg, None, "12a")["quality"] == 0.0
    assert q({**cfg, "pattern": "abc", "ignore_case": True}, None, "xABCx")["quality"] == 1.0


def test_json_schema_reports_validity_separately():
    cfg = {"type": "json_schema", "schema": SCHEMA}
    ok = q(cfg, None, '{"category": "billing"}')
    assert ok["json_valid"] == 1.0 and ok["schema_valid"] == 1.0 and ok["quality"] == 1.0
    wrong = q(cfg, None, '{"category": 5}')
    assert wrong["json_valid"] == 1.0 and wrong["schema_valid"] == 0.0 and wrong["quality"] == 0.0
    broken = q(cfg, None, "{oops")
    assert broken["json_valid"] == 0.0 and broken["quality"] == 0.0


def test_classification_normalizes_label_and_handles_bad_output():
    cfg = {"type": "classification"}
    exp = {"category": "billing", "priority": "medium"}
    assert q(cfg, exp, '{"category": " Billing "}')["quality"] == 1.0
    assert q(cfg, exp, '{"category": "technical"}')["quality"] == 0.0
    assert q(cfg, exp, "plain text")["quality"] == 0.0
    assert q(cfg, exp, '["billing"]')["quality"] == 0.0
    assert q({"type": "classification", "label_field": "priority"}, exp, '{"priority": "medium"}')["quality"] == 1.0


def test_classification_without_resolvable_label_is_unknown_not_zero():
    out = q({"type": "classification"}, {"a": 1, "b": 2}, '{"a": 1}')
    assert out["quality"] is None


def test_unknown_evaluator_is_unknown_not_zero():
    assert q({"type": "nope"}, None, "x")["quality"] is None


def _resp(content="hi", prompt=5, completion=2):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=prompt, completion_tokens=completion),
    )


@pytest.fixture
def live(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "enable_live_llm", True)
    monkeypatch.setattr(s, "live_models", {"gpt-mini": "openai/gpt-4o-mini"})
    import litellm

    return litellm


def test_live_call_maps_usage_and_cost(live, monkeypatch):
    seen = {}

    def fake_completion(**kw):
        seen.update(kw)
        return _resp()

    monkeypatch.setattr(live, "completion", fake_completion)
    monkeypatch.setattr(live, "completion_cost", lambda completion_response: 0.0003)
    r = adapter.call_model("gpt-mini", "k", [{"role": "user", "content": "x"}], 1)
    assert (r.content, r.input_tokens, r.output_tokens) == ("hi", 5, 2)
    assert str(r.estimated_cost_usd) == "0.0003"
    assert seen["model"] == "openai/gpt-4o-mini" and seen["num_retries"] == 0 and seen["timeout"]


def test_live_call_missing_usage_and_cost_stay_unknown(live, monkeypatch):
    monkeypatch.setattr(
        live, "completion",
        lambda **kw: SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))], usage=None
        ),
    )

    def no_price(**kw):
        raise ValueError("model not mapped")

    monkeypatch.setattr(live, "completion_cost", no_price)
    r = adapter.call_model("gpt-mini", "k", [{"role": "user", "content": "x"}], 1)
    assert r.input_tokens is None and r.output_tokens is None and r.estimated_cost_usd is None


@pytest.mark.parametrize(
    "exc_name,expected,transient",
    [
        ("Timeout", LLMTimeout, True),
        ("RateLimitError", LLMProviderError, True),
        ("AuthenticationError", LLMProviderError, False),
    ],
)
def test_live_call_error_classification(live, monkeypatch, exc_name, expected, transient):
    exc = getattr(live, exc_name)("secret sk-abc123def456ghi leaked", "openai", "gpt-4o-mini")

    def boom(**kw):
        raise exc

    monkeypatch.setattr(live, "completion", boom)
    with pytest.raises(expected) as info:
        adapter.call_model("gpt-mini", "k", [{"role": "user", "content": "x"}], 1)
    assert info.value.transient is transient
    assert "sk-abc123def456ghi" not in str(info.value)


def test_exhausted_credit_is_permanent_and_readable(live, monkeypatch):
    exc = live.RateLimitError("You have no credits remaining.", "openai", "gpt-4o-mini")

    def boom(**kw):
        raise exc

    monkeypatch.setattr(live, "completion", boom)
    with pytest.raises(LLMProviderError) as info:
        adapter.call_model("gpt-mini", "k", [{"role": "user", "content": "x"}], 1)
    assert info.value.code == "quota_exceeded" and info.value.transient is False
    assert "no credits remaining" in str(info.value)


def test_live_alias_rejected_when_flag_off(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "enable_live_llm", False)
    monkeypatch.setattr(s, "live_models", {"gpt-mini": "openai/gpt-4o-mini"})
    from app.evaluation import registry

    assert not registry.is_allowed_model("gpt-mini")
    with pytest.raises(ValueError):
        adapter.call_model("gpt-mini", "k", [], 1)


def test_live_alias_listed_when_enabled(live):
    from app.evaluation import registry

    assert registry.is_allowed_model("gpt-mini")
    assert "gpt-mini" in [m.alias for m in registry.list_models()]


def test_code_fenced_json_is_accepted():
    fenced = '```json\n{"category": "billing"}\n```'
    assert q({'type': 'classification'}, {'category': 'billing'}, fenced)['quality'] == 1.0

