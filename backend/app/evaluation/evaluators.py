"""Deterministic evaluators. Pure functions: (case config, expected, output text) -> metrics."""

import json
import re
from dataclasses import dataclass
from typing import Any

from jsonschema import Draft202012Validator

MAX_REGEX_INPUT = 20_000  # bound work done by user-supplied patterns


@dataclass(frozen=True)
class Metric:
    name: str
    value: float | None  # None = not applicable / unknown, never coerced to 0
    details: dict[str, Any] | None = None


def _parse_json(text: str) -> tuple[bool, Any]:
    stripped = text.strip()
    # Chat models often wrap JSON in a markdown fence even when told not to.
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, re.DOTALL)
    try:
        return True, json.loads(fenced.group(1) if fenced else stripped)
    except (ValueError, TypeError):
        return False, None


def _normalize(text: str, steps: list[str]) -> str:
    for step in steps:
        if step == "strip":
            text = text.strip()
        elif step == "lowercase":
            text = text.lower()
        elif step == "collapse_whitespace":
            text = " ".join(text.split())
    return text


def _exact_match(cfg: dict[str, Any], expected: dict[str, Any] | None, text: str) -> list[Metric]:
    expected = expected or {}
    # {"text": "..."} compares plain strings; any other expected value compares parsed JSON.
    if set(expected) == {"text"} and isinstance(expected["text"], str):
        steps = cfg.get("normalize", [])
        ok = _normalize(text, steps) == _normalize(expected["text"], steps)
        return [Metric("exact_match", float(ok))]
    parsed_ok, parsed = _parse_json(text)
    return [Metric("exact_match", float(parsed_ok and parsed == expected))]


def _contains(cfg: dict[str, Any], _expected: Any, text: str) -> list[Metric]:
    haystack = text if cfg.get("case_sensitive", False) else text.lower()
    missing = [
        s for s in cfg["substrings"] if (s if cfg.get("case_sensitive", False) else s.lower()) not in haystack
    ]
    mode = cfg.get("mode", "all")
    ok = len(missing) < len(cfg["substrings"]) if mode == "any" else not missing
    return [Metric("contains", float(ok), {"missing": missing})]


def _regex(cfg: dict[str, Any], _expected: Any, text: str) -> list[Metric]:
    flags = re.IGNORECASE if cfg.get("ignore_case") else 0
    return [Metric("regex", float(re.search(cfg["pattern"], text[:MAX_REGEX_INPUT], flags) is not None))]


def _json_schema(cfg: dict[str, Any], _expected: Any, text: str) -> list[Metric]:
    parsed_ok, parsed = _parse_json(text)
    if not parsed_ok:
        return [
            Metric("json_valid", 0.0),
            Metric("schema_valid", 0.0, {"errors": ["output is not valid JSON"]}),
        ]
    errors = [
        f"{'/'.join(map(str, e.absolute_path)) or '$'}: {e.message}"[:200]
        for e in Draft202012Validator(cfg["schema"]).iter_errors(parsed)
    ]
    return [
        Metric("json_valid", 1.0),
        Metric("schema_valid", float(not errors), {"errors": errors[:5]} if errors else None),
    ]


def _label_field(cfg: dict[str, Any], expected: dict[str, Any]) -> str | None:
    field = cfg.get("label_field", "category")
    if field in expected:
        return field
    return next(iter(expected)) if len(expected) == 1 else None


def _classification(cfg: dict[str, Any], expected: dict[str, Any] | None, text: str) -> list[Metric]:
    expected = expected or {}
    field = _label_field(cfg, expected)
    if field is None:
        return [Metric("accuracy", None, {"reason": "label field not found in expected_output"})]
    parsed_ok, parsed = _parse_json(text)
    predicted = parsed.get(field) if parsed_ok and isinstance(parsed, dict) else None
    want = str(expected[field]).strip().lower()
    got = str(predicted).strip().lower() if predicted is not None else None
    return [Metric("accuracy", float(got == want), {"expected": expected[field], "predicted": predicted})]


_EVALUATORS = {
    "exact_match": _exact_match,
    "contains": _contains,
    "regex": _regex,
    "json_schema": _json_schema,
    "classification": _classification,
}

# Which metric is the case's normalized 0..1 quality score for each evaluator.
_PRIMARY = {
    "exact_match": "exact_match",
    "contains": "contains",
    "regex": "regex",
    "json_schema": "schema_valid",
    "classification": "accuracy",
}


def evaluate(cfg: dict[str, Any], expected: dict[str, Any] | None, output: str) -> list[Metric]:
    """Returns type-specific metrics plus a `quality` metric (normalized 0..1)."""
    kind = cfg.get("type")
    fn = _EVALUATORS.get(kind)
    if fn is None:
        return [Metric("quality", None, {"reason": f"unknown evaluator '{kind}'"})]
    metrics = fn(cfg, expected, output if isinstance(output, str) else json.dumps(output))
    primary = next((m for m in metrics if m.name == _PRIMARY[kind]), None)
    metrics.append(Metric("quality", primary.value if primary else None))
    return metrics
