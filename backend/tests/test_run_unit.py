import pytest

from app.core.security import redact
from app.evaluation.errors import LLMProviderError, LLMTimeout
from app.evaluation.mock_adapter import generate, scenario_for
from app.services.run_state import InvalidTransition, assert_transition, can_transition

ALLOWED = [
    ("queued", "running"),
    ("queued", "cancelled"),
    ("running", "completed"),
    ("running", "completed_with_errors"),
    ("running", "failed"),
    ("running", "cancelled"),
]


@pytest.mark.parametrize("a,b", ALLOWED)
def test_allowed_transitions(a, b):
    assert can_transition(a, b)
    assert_transition(a, b)


@pytest.mark.parametrize(
    "a,b",
    [
        ("queued", "completed"),
        ("queued", "failed"),
        ("completed", "running"),
        ("failed", "queued"),
        ("cancelled", "running"),
        ("running", "queued"),
        ("bogus", "running"),
    ],
)
def test_invalid_transitions(a, b):
    assert not can_transition(a, b)
    with pytest.raises(InvalidTransition):
        assert_transition(a, b)


def test_redact_removes_secrets():
    text = "failed: Bearer abc.def-123 with api_key=SECRET123 and sk-abcdefgh12345678"
    out = redact(text)
    assert "abc.def" not in out and "SECRET123" not in out and "sk-abcdefgh" not in out
    assert "[REDACTED]" in out


def test_redact_truncates():
    assert len(redact("x" * 1000)) == 500


def _key(alias, scenario):
    return next(k for k in (f"c{i}" for i in range(1000)) if scenario_for(alias, k) == scenario)


def test_non_flaky_models_always_ok():
    assert scenario_for("fast-model", "anything") == "ok"


def test_flaky_scenarios_raise_expected_errors():
    perm = _key("flaky-model", "permanent_error")
    with pytest.raises(LLMProviderError) as e:
        generate("flaky-model", perm, "x")
    assert not e.value.transient

    with pytest.raises(LLMTimeout):
        generate("flaky-model", _key("flaky-model", "timeout"), "x")

    t = _key("flaky-model", "transient_then_ok")
    with pytest.raises(LLMProviderError) as e:
        generate("flaky-model", t, "x", attempt=1)
    assert e.value.transient
    assert generate("flaky-model", t, "x", attempt=2).content
