"""Scrub obvious secrets before logs reach the LLM, the database or chat."""
import re

_PATTERNS = [
    (re.compile(r"(?i)\b(password|passwd|secret|token|api[_-]?key|authorization|client[_-]?secret)\b(\s*[:=]\s*|\s+)(\S+)"), r"\1\2[REDACTED]"),
    (re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"), "Bearer [REDACTED]"),
    (re.compile(r"\b(AKIA|ASIA)[A-Z0-9]{16}\b"), "[REDACTED_AWS_KEY]"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"), "[REDACTED_GH_TOKEN]"),
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"), "[REDACTED_SLACK_TOKEN]"),
    (re.compile(r"(?i)(sid|sessionid)=[A-Za-z0-9!._\-]{20,}"), r"\1=[REDACTED]"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[REDACTED_EMAIL]"),
]

def redact(text: str) -> str:
    for pat, rep in _PATTERNS:
        text = pat.sub(rep, text)
    return text
