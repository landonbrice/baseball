"""F4 — deterministic rationale composition.

Reads already-persisted triage + plan output; composes coach-register
conversational strings. Zero LLM calls. Non-fatal — callers catch exceptions
and persist null rationale.
"""
import logging
import re
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_PHRASES_PATH = Path(__file__).parent.parent.parent / "data" / "knowledge" / "modification_phrases.yaml"
_phrases_cache: dict | None = None


def _load_phrases() -> dict:
    global _phrases_cache
    if _phrases_cache is None:
        with open(_PHRASES_PATH) as f:
            _phrases_cache = yaml.safe_load(f) or {}
    return _phrases_cache


# Tier int → label (A30)
_TIER_LABELS = {1: "Sensitive", 2: "Standard", 3: "Resilient"}


def _tier_label(tier: int, baseline_state: str) -> str:
    label = _TIER_LABELS.get(tier, "Standard")
    if baseline_state == "provisional":
        return f"{label} (provisional)"
    return label


# ---------------------------------------------------------------------------
# Sanitizer (A21)
# ---------------------------------------------------------------------------

# Strips parenthesized coach-only context + bare words. Order matters: parens first.
_COACH_PAREN_RE = re.compile(
    r"\s*\((?:Sensitive|Standard|Resilient|provisional|baseline)(?:[,\s]+(?:Sensitive|Standard|Resilient|provisional|baseline))*\)",
    re.IGNORECASE,
)
_COACH_WORD_RE = re.compile(
    r"\b(?:Tier\s*[123]|Sensitive|Standard|Resilient|provisional|baseline)\b",
    re.IGNORECASE,
)


def sanitize_for_llm(rationale_detail: dict | None) -> dict:
    """Strip coach-only vocabulary from rationale_detail lines.

    Returns dict with same shape; missing/None yields empty strings."""
    if not rationale_detail:
        return {"status_line": "", "signal_line": "", "response_line": ""}
    out = {}
    for k in ("status_line", "signal_line", "response_line"):
        s = rationale_detail.get(k, "") or ""
        s = _COACH_PAREN_RE.sub("", s)
        s = _COACH_WORD_RE.sub("", s)
        s = re.sub(r"\s{2,}", " ", s).strip()
        out[k] = s
    return out


# ---------------------------------------------------------------------------
# Public API — filled in by Tasks 7-10
# ---------------------------------------------------------------------------

def generate_triage_rationale(triage_result: dict, pitcher_context: dict) -> dict:
    """Compose {short, detail{status, signal, response}} from triage output."""
    # Stubbed — composition branches land in Tasks 7-10. Skeleton returns
    # a safe default so structural tests pass.
    flag = triage_result.get("flag_level", "green")
    short = "All systems good." if flag == "green" else f"{flag.replace('_', ' ').title()} — see detail."
    detail = {
        "status_line": flag.replace("_", " ").title(),
        "signal_line": "",
        "response_line": "",
    }
    return {"short": short, "detail": detail}


def generate_exercise_rationale(exercise: dict, constraints_applied: list, plan_context: dict) -> str | None:
    """Per-exercise clause ≤ 60 chars. None if nothing meaningful to say."""
    return None  # stubbed


def generate_day_rationale(plan: dict, triage_result: dict, pitcher_context: dict) -> str | None:
    """One sentence summarizing the day's shape."""
    return "Full program today."  # stubbed default
