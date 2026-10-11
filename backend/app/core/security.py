import re

_PATTERNS = [
    (re.compile(r"sk-[A-Za-z0-9_-]{8,}"), "[REDACTED]"),
    (re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+"), "Bearer [REDACTED]"),
    (re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\b(\s*[=:]\s*)\S+"), r"\1\2[REDACTED]"),
]


def redact(text: str, max_len: int = 500) -> str:
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text[:max_len]
