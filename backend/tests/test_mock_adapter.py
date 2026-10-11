import json

import pytest

from app.evaluation.mock_adapter import generate


def test_deterministic():
    a = generate("fast-model", "billing-001", "I was charged twice")
    b = generate("fast-model", "billing-001", "I was charged twice")
    assert a == b


def test_output_is_valid_json_with_category():
    r = generate("accurate-model", "x", "I forgot my password")
    assert json.loads(r.content)["category"] in {"billing", "technical", "account_access"}
    assert r.input_tokens > 0 and r.output_tokens > 0


def test_unknown_model_rejected():
    with pytest.raises(ValueError):
        generate("nope", "x", "y")
