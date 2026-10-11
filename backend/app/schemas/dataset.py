import re
from datetime import datetime
from typing import Any, Generic, Literal, TypeVar
from uuid import UUID

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.config import get_settings

CASE_KEY_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,199}$"
EVALUATOR_TYPES = {"exact_match", "contains", "regex", "json_schema", "classification"}
NEEDS_EXPECTED_OUTPUT = {"exact_match", "classification"}
MESSAGE_ROLES = {"system", "user", "assistant"}
MAX_MESSAGE_CHARS = 10_000

T = TypeVar("T")


class TestCaseIn(BaseModel):
    __test__ = False  # not a pytest class
    model_config = ConfigDict(extra="forbid")

    case_key: str = Field(pattern=CASE_KEY_PATTERN)
    input: dict[str, Any]
    expected_output: dict[str, Any] | None = None
    evaluation_config: dict[str, Any]
    tags: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("tags")
    @classmethod
    def _tags(cls, tags: list[str]) -> list[str]:
        if any(not t or len(t) > 50 for t in tags):
            raise ValueError("tags must be 1-50 characters")
        return tags

    @field_validator("input")
    @classmethod
    def _input(cls, value: dict[str, Any]) -> dict[str, Any]:
        messages = value.get("messages")
        if not isinstance(messages, list) or not messages:
            raise ValueError("input.messages must be a non-empty list")
        for i, msg in enumerate(messages):
            if not isinstance(msg, dict) or msg.get("role") not in MESSAGE_ROLES:
                raise ValueError(f"input.messages[{i}].role must be one of {sorted(MESSAGE_ROLES)}")
            content = msg.get("content")
            if not isinstance(content, str) or not content.strip():
                raise ValueError(f"input.messages[{i}].content must be a non-empty string")
            if len(content) > MAX_MESSAGE_CHARS:
                raise ValueError(f"input.messages[{i}].content exceeds {MAX_MESSAGE_CHARS} characters")
        return value

    @field_validator("evaluation_config")
    @classmethod
    def _evaluation_config(cls, cfg: dict[str, Any]) -> dict[str, Any]:
        kind = cfg.get("type")
        if kind not in EVALUATOR_TYPES:
            raise ValueError(f"evaluation_config.type must be one of {sorted(EVALUATOR_TYPES)}")
        if kind == "regex":
            pattern = cfg.get("pattern")
            if not isinstance(pattern, str):
                raise ValueError("evaluation_config.pattern is required for regex")
            try:
                re.compile(pattern)
            except re.error as exc:
                raise ValueError(f"evaluation_config.pattern is not a valid regex: {exc}") from exc
        elif kind == "json_schema":
            schema = cfg.get("schema")
            if not isinstance(schema, dict):
                raise ValueError("evaluation_config.schema is required for json_schema")
            try:
                Draft202012Validator.check_schema(schema)
            except SchemaError as exc:
                raise ValueError(f"evaluation_config.schema is not a valid JSON Schema: {exc.message}") from exc
        elif kind == "contains":
            subs = cfg.get("substrings")
            if not isinstance(subs, list) or not subs or not all(isinstance(s, str) for s in subs):
                raise ValueError("evaluation_config.substrings must be a non-empty list of strings")
        return cfg

    @model_validator(mode="after")
    def _expected_output_required(self) -> "TestCaseIn":
        if self.evaluation_config.get("type") in NEEDS_EXPECTED_OUTPUT and self.expected_output is None:
            raise ValueError(
                f"expected_output is required for evaluator '{self.evaluation_config['type']}'"
            )
        return self


class CaseBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    cases: list[TestCaseIn]

    @field_validator("cases")
    @classmethod
    def _cases(cls, cases: list[TestCaseIn]) -> list[TestCaseIn]:
        limit = get_settings().max_cases_per_dataset
        if not cases:
            raise ValueError("at least one case is required")
        if len(cases) > limit:
            raise ValueError(f"at most {limit} cases are allowed")
        seen: set[str] = set()
        for case in cases:
            if case.case_key in seen:
                raise ValueError(f"duplicate case_key '{case.case_key}'")
            seen.add(case.case_key)
        return cases


class DatasetCreate(CaseBatch):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class VersionCreate(CaseBatch):
    pass


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class DatasetSummary(_Out):
    id: UUID
    name: str
    description: str | None
    created_at: datetime
    version_count: int
    latest_version_number: int | None


class VersionSummary(_Out):
    id: UUID
    dataset_id: UUID
    version_number: int
    schema_version: str
    content_hash: str
    case_count: int
    created_at: datetime


class CaseOut(_Out):
    id: UUID
    case_key: str
    input: dict[str, Any]
    expected_output: dict[str, Any] | None
    evaluation_config: dict[str, Any]
    tags: list[str]


class VersionDetail(VersionSummary):
    cases: list[CaseOut]


class DatasetCreated(BaseModel):
    dataset: DatasetSummary
    version: VersionSummary


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int
