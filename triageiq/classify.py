"""Root-cause classification by the local LLM."""
import json, re
from dataclasses import dataclass, asdict
from . import llm
from .config import Config

CATEGORIES = ["test_failure", "missing_permission", "missing_dependency", "merge_conflict", "other"]

SYSTEM = f"""You are a CI/CD failure triage assistant. You read a failed pipeline or deployment log and identify the ROOT cause.
Choose exactly one category:
- test_failure: a test, assertion or quality gate failed (e.g. Apex test failure, coverage below threshold)
- missing_permission: access denied, insufficient privileges, unauthorized, missing permission set / profile / OAuth scope
- missing_dependency: a package, component, class, metadata item or library that is referenced but absent or not yet deployed
- merge_conflict: git merge/rebase conflict or conflicting changes to the same file/component
- other: none of the above
Ignore noise and warnings. Prefer the FIRST real error over follow-on errors it caused.
Respond with ONLY a JSON object:
{{"category": "<one of {CATEGORIES}>", "reason": "<one or two plain-language sentences for a developer>", "evidence": "<the single most telling log line, copied verbatim>", "confidence": <0.0-1.0>}}"""

ERROR_HINT = re.compile(r"(?i)error|fail|denied|unauthori[sz]ed|forbidden|conflict|not found|missing|cannot|exception|insufficient|invalid|no such|timeout")

@dataclass
class Diagnosis:
    category: str
    reason: str
    evidence: str
    confidence: float

    def to_dict(self):
        return asdict(self)

def condense(log: str, limit: int) -> str:
    """Keep the log small enough for a local model: all error-looking lines with context, else the tail."""
    if len(log) <= limit:
        return log
    lines = log.splitlines()
    keep = set()
    for i, ln in enumerate(lines):
        if ERROR_HINT.search(ln):
            keep.update(range(max(0, i - 1), min(len(lines), i + 2)))
    if not keep:
        return log[-limit:]
    picked = "\n".join(lines[i] for i in sorted(keep))
    if len(picked) <= limit:
        return picked
    # First errors usually carry the root cause; the tail carries the final verdict. Keep both.
    half = limit // 2
    return picked[:half] + "\n...[snipped]...\n" + picked[-half:]

def parse(raw: str) -> Diagnosis:
    m = re.search(r"\{.*\}", raw, re.S)
    try:
        d = json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        d = {}
    cat = d.get("category")
    if cat not in CATEGORIES:
        cat = "other"
    try:
        conf = max(0.0, min(1.0, float(d.get("confidence", 0.3))))
    except (TypeError, ValueError):
        conf = 0.3
    return Diagnosis(cat, str(d.get("reason") or "The model could not determine a clear cause.")[:400],
                     str(d.get("evidence") or "")[:300], conf)

def classify(cfg: Config, log: str, ctx: dict = None) -> Diagnosis:
    ctx = ctx or {}
    header = f"Pipeline: {ctx.get('pipeline','?')} | Environment: {ctx.get('environment','?')} | Stage: {ctx.get('stage','?')}\n"
    raw = llm.chat_json(cfg.ollama_url, cfg.model, SYSTEM,
                        header + "LOG:\n" + condense(log, cfg.max_log_chars), cfg.llm_timeout)
    return parse(raw)
