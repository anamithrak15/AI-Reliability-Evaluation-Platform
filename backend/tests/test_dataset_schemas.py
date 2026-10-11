import pytest
from pydantic import ValidationError

from app.schemas.dataset import DatasetCreate, TestCaseIn
from app.services.dataset_service import compute_content_hash


def make_case(**overrides):
    base = {
        "case_key": "billing-001",
        "input": {"messages": [{"role": "user", "content": "I was charged twice."}]},
        "expected_output": {"category": "billing"},
        "evaluation_config": {"type": "classification"},
        "tags": ["billing"],
    }
    base.update(overrides)
    return base


def make_dataset(cases=None, **overrides):
    payload = {
        "name": "ds",
        "schema_version": "1.0",
        "cases": cases if cases is not None else [make_case()],
    }
    payload.update(overrides)
    return payload


def test_valid_dataset():
    ds = DatasetCreate.model_validate(make_dataset())
    assert len(ds.cases) == 1


@pytest.mark.parametrize(
    "overrides",
    [
        {"case_key": "bad key!"},
        {"case_key": ""},
        {"input": {"messages": []}},
        {"input": {"messages": [{"role": "robot", "content": "hi"}]}},
        {"input": {"messages": [{"role": "user", "content": "  "}]}},
        {"evaluation_config": {}},
        {"evaluation_config": {"type": "unknown"}},
        {"evaluation_config": {"type": "regex"}},
        {"evaluation_config": {"type": "regex", "pattern": "("}},
        {"evaluation_config": {"type": "json_schema"}},
        {"evaluation_config": {"type": "json_schema", "schema": {"type": "not-a-type"}}},
        {"evaluation_config": {"type": "contains", "substrings": []}},
        {"expected_output": None},
        {"tags": ["x"] * 21},
        {"unexpected": 1},
    ],
)
def test_invalid_case_rejected(overrides):
    with pytest.raises(ValidationError):
        TestCaseIn.model_validate(make_case(**overrides))


def test_json_schema_case_without_expected_output_is_valid():
    cfg = {"type": "json_schema", "schema": {"type": "object"}}
    TestCaseIn.model_validate(make_case(expected_output=None, evaluation_config=cfg))


def test_duplicate_case_keys_rejected():
    with pytest.raises(ValidationError, match="duplicate case_key"):
        DatasetCreate.model_validate(make_dataset([make_case(), make_case()]))


def test_empty_and_oversized_case_lists_rejected():
    with pytest.raises(ValidationError):
        DatasetCreate.model_validate(make_dataset(cases=[]))
    many = [make_case(case_key=f"c{i}") for i in range(101)]
    with pytest.raises(ValidationError, match="at most"):
        DatasetCreate.model_validate(make_dataset(many))


def test_unsupported_schema_version_rejected():
    with pytest.raises(ValidationError):
        DatasetCreate.model_validate(make_dataset(schema_version="2.0"))


def test_hash_is_order_independent_and_content_sensitive():
    a = make_case(case_key="a")
    b = make_case(case_key="b", input={"messages": [{"role": "user", "content": "other"}]})
    h1 = compute_content_hash(DatasetCreate.model_validate(make_dataset([a, b])))
    h2 = compute_content_hash(DatasetCreate.model_validate(make_dataset([b, a])))
    assert h1 == h2 and len(h1) == 64

    changed = make_case(case_key="a", tags=["different"])
    h3 = compute_content_hash(DatasetCreate.model_validate(make_dataset([changed, b])))
    assert h3 != h1


def test_hash_ignores_dataset_name():
    h1 = compute_content_hash(DatasetCreate.model_validate(make_dataset(name="one")))
    h2 = compute_content_hash(DatasetCreate.model_validate(make_dataset(name="two")))
    assert h1 == h2
