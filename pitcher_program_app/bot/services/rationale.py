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
    """Return bare tier name. Provisional suffix handled by callers that wrap in parens."""
    return _TIER_LABELS.get(tier, "Standard")


def _tier_parenthetical(tier: int, baseline_state: str) -> str | None:
    """Return the parenthetical addition to a status line, or None when default (Standard + full)."""
    label = _TIER_LABELS.get(tier, "Standard")
    is_default = tier == 2 and baseline_state != "provisional"
    if is_default:
        return None
    if baseline_state == "provisional":
        return f"({label}, provisional)"
    return f"({label})"


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


def build_qa_rationale_context(pitcher_id: str) -> str:
    """Return a CONTEXT block string for QA prompts, or empty string if no rationale today.

    Reads today's daily entry for the pitcher, extracts the persisted rationale_detail,
    sanitizes coach vocabulary, and formats it as a CONTEXT block the LLM can use to
    ground its answer without quoting verbatim.
    """
    try:
        from bot.services.db import get_daily_entry
        from datetime import datetime
        from bot.config import CHICAGO_TZ
        today = datetime.now(CHICAGO_TZ).strftime("%Y-%m-%d")
        entry = get_daily_entry(pitcher_id, today) or {}
        detail = (entry.get("rationale") or {}).get("rationale_detail")
        if not detail:
            return ""
        sanitized = sanitize_for_llm(detail)
        return (
            "\n\nCONTEXT (today's program rationale — ground your answer in it, do not quote literally):\n"
            f"- Status: {sanitized.get('status_line', '')}\n"
            f"- Signal: {sanitized.get('signal_line', '')}\n"
            f"- Response: {sanitized.get('response_line', '')}\n"
        )
    except Exception:
        logger.exception("build_qa_rationale_context_failed | pitcher=%s", pitcher_id)
        return ""


# ---------------------------------------------------------------------------
# Composition helpers (Task 7)
# ---------------------------------------------------------------------------

_TISSUE_TIEBREAK_ORDER = ["tissue", "recovery", "load"]  # A12


def _dominant_category(category_scores: dict, baseline_mean: float = 8.0) -> str:
    """Return category with widest NEGATIVE gap from baseline. Tiebreak ±0.3 → tissue > recovery > load."""
    gaps = {c: baseline_mean - (category_scores.get(c, baseline_mean) or baseline_mean)
            for c in _TISSUE_TIEBREAK_ORDER}
    max_gap = max(gaps.values())
    within_band = [c for c in _TISSUE_TIEBREAK_ORDER if max_gap - gaps[c] <= 0.3]
    # within_band is already in priority order
    return within_band[0]


def _phrase_short(tag: str, pa: dict) -> str:
    phrases = _load_phrases()
    entry = phrases.get(tag, {})
    template = entry.get("short", tag)
    return _fill_pct(template, pa)


def _phrase_detail(tag: str, pa: dict) -> str:
    phrases = _load_phrases()
    entry = phrases.get(tag, {})
    template = entry.get("detail", tag)
    return _fill_pct(template, pa)


def _fill_pct(template: str, pa: dict) -> str:
    if "{pct}" not in template:
        return template
    cap = (pa or {}).get("lifting_intensity_cap")
    if cap is None:
        return template.replace("{pct}", "")
    # cap is a decimal like 0.8 → show the DROP (20%)
    pct = round((1 - cap) * 100)
    return template.replace("{pct}", str(pct))


def _join_phrases(tags: list, pa: dict, kind: str) -> str:
    if not tags:
        return ""
    getter = _phrase_short if kind == "short" else _phrase_detail
    parts = [getter(t, pa) for t in tags if t]
    parts = [p for p in parts if p]
    return ", ".join(parts)


def _green_rationale(ctx: dict) -> dict:
    af = ctx.get("arm_feel")
    sleep = ctx.get("sleep_hours")
    signal_bits = []
    if af is not None:
        signal_bits.append(f"arm feel holding at {af}")
    if sleep is not None:
        signal_bits.append(f"sleep {sleep} hrs")
    if ctx.get("whoop_data"):
        signal_bits.append("recovery green")
    signal = ", ".join(signal_bits).capitalize() + "." if signal_bits else "All green signals."
    return {
        "short": "All systems good.",
        "detail": {
            "status_line": "Green",
            "signal_line": signal,
            "response_line": "Full program today.",
        },
    }


def _category_status_line(flag: str, dominant: str, tier: int, baseline_state: str,
                          post_outing: bool = False, reliever_reset: bool = False) -> str:
    core = {
        "modified_green": "Modified green",
        "yellow": "Yellow",
        "red": "Red",
    }.get(flag, flag.title())

    # Reliever reset + post-outing bypass category framing per spec voice rules
    if reliever_reset and flag == "modified_green":
        descriptor = "reliever reset"
    elif post_outing and flag == "modified_green":
        descriptor = "post-outing protocol"
    else:
        label_map = {"tissue": "tissue concern", "load": "load concern", "recovery": "recovery concern"}
        descriptor = label_map.get(dominant, dominant)

    status = f"{core} — {descriptor}"
    paren = _tier_parenthetical(tier, baseline_state)
    if paren:
        status = f"{status} {paren}"
    return status


def _signal_line(ctx: dict, triage: dict, dominant: str) -> str:
    """Name specific values + windows. Non-WHOOP: silent on HRV/recovery."""
    parts = []
    af = ctx.get("arm_feel")
    sleep = ctx.get("sleep_hours")
    trajectory = triage.get("trajectory_context") or {}
    history = trajectory.get("arm_feel_recent") or []

    # Trend if present
    if history and af is not None and len(history) >= 2:
        arrow = " → ".join(str(h) for h in (list(history) + [af])[-3:])
        parts.append(f"Arm feel {arrow}")
    elif af is not None:
        parts.append(f"Arm feel {af}")

    if sleep is not None and sleep < 7.0:
        parts.append(f"sleep {sleep} hrs")

    whoop = ctx.get("whoop_data") or {}
    if whoop:
        hrv = whoop.get("hrv")
        hrv_avg = whoop.get("hrv_7day_avg")
        if hrv and hrv_avg:
            delta_pct = round((1 - hrv / hrv_avg) * 100)
            if delta_pct >= 10:
                parts.append(f"HRV {delta_pct}% below baseline")

    return ", ".join(parts) + "." if parts else ""


def _response_line(triage: dict) -> str:
    mods = [m if isinstance(m, str) else m.get("tag", "") for m in (triage.get("modifications") or [])]
    mods = [m for m in mods if m]
    pa = triage.get("protocol_adjustments") or {}
    if not mods:
        return "Full program today."
    # Detail phrases are complete sentences — period-joined (spec A32 voice)
    parts = [_phrase_detail(t, pa) for t in mods if t]
    parts = [p.rstrip(".").strip() for p in parts if p]
    if not parts:
        return "Full program today."
    return ". ".join(parts) + "."


def _post_outing_short(ctx: dict, triage: dict) -> str:
    dso = ctx.get("days_since_outing")
    af = ctx.get("arm_feel")
    pieces = [f"Recovery day — {dso} day{'s' if dso != 1 else ''} post-outing"]
    if af is not None:
        pieces.append(f"arm feel {af}")
    base = ", ".join(pieces) + "."
    if len(base) > 120:
        base = base[:117] + "..."
    return base


def _reset_short_reliever(ctx: dict) -> str:
    """Appearance-framed short line for reliever modified-green."""
    dsa = ctx.get("days_since_appearance", ctx.get("days_since_outing"))
    af = ctx.get("arm_feel")
    if dsa is not None:
        pieces = [f"Reset day — {dsa} day{'s' if dsa != 1 else ''} since last appearance"]
    else:
        pieces = ["Reset day"]
    if af is not None:
        pieces.append(f"arm feel {af}")
    s = ", ".join(pieces) + "."
    if len(s) > 120:
        s = s[:117] + "..."
    return s


def _compose_short(flag: str, ctx: dict, triage: dict, dominant: str) -> str:
    """Compose ≤ 120 char short line."""
    role = ctx.get("role", "starter")
    if flag == "modified_green":
        if role == "reliever":
            return _reset_short_reliever(ctx)
        if ctx.get("days_since_outing") in (0, 1):
            return _post_outing_short(ctx, triage)
    af = ctx.get("arm_feel")
    mods = [m if isinstance(m, str) else m.get("tag", "") for m in (triage.get("modifications") or [])]
    pa = triage.get("protocol_adjustments") or {}
    mod_phrase = _join_phrases(mods, pa, "short")

    prefix = {
        "modified_green": "Modified day",
        "yellow": "Yellow",
        "red": "Red",
    }.get(flag, flag.title())

    if dominant == "tissue" and af is not None:
        bits = [f"{prefix} — arm feel {af}"]
    elif dominant == "recovery":
        bits = [f"{prefix} — recovery drifting"]
    else:
        bits = [f"{prefix}"]
    if mod_phrase:
        bits.append(mod_phrase)
    short = ", ".join(bits) + "."
    if len(short) > 120:
        short = short[:117] + "..."
    return short


_UCL_KEYWORDS = re.compile(r"\b(ucl|ulnar\s+collateral)\b", re.IGNORECASE)


def _is_instant_red(triage_result: dict, pitcher_context: dict) -> tuple[bool, str | None]:
    """Return (is_instant, trigger_name). Keep in sync with triage.py instant-red logic.

    Current triage.py instant-red triggers (verified 2026-04-22):
      - arm_feel <= 2
      - ucl_sensation (keyword in arm_clarification)
    Do NOT add branches for triggers not yet in triage.
    """
    if triage_result.get("flag_level") != "red":
        return False, None
    af = pitcher_context.get("arm_feel")
    if af is not None and af <= 2:
        return True, "arm_feel"
    clar = pitcher_context.get("arm_clarification") or ""
    if _UCL_KEYWORDS.search(clar):
        return True, "ucl"
    return False, None


def _instant_red_rationale(trigger: str, ctx: dict, triage: dict) -> dict:
    af = ctx.get("arm_feel")
    sleep = ctx.get("sleep_hours")
    if trigger == "ucl":
        short = "Acute concern — UCL sensation reported on check-in."
        signal = "UCL sensation reported on this morning's check-in. Shutdown protocol."
        response = "No throwing. No lifting. Trainer consult required before next session."
    else:  # arm_feel
        bits = [f"arm feel dropped to {af}"]
        if sleep is not None and sleep < 6:
            bits.append(f"sleep {sleep} hrs")
        short = "Acute concern — " + ", ".join(bits) + "."
        signal_bits = [f"Arm feel {af} reported this morning"]
        if sleep is not None:
            signal_bits.append(f"sleep {sleep} hrs")
        whoop = ctx.get("whoop_data") or {}
        if whoop.get("hrv") and whoop.get("hrv_7day_avg"):
            delta = round((1 - whoop["hrv"] / whoop["hrv_7day_avg"]) * 100)
            if delta >= 10:
                signal_bits.append(f"HRV {delta}% below baseline")
        signal = ". ".join(signal_bits) + "."
        response = "Recovery-only day. Trainer consult recommended before next throwing session."

    # Fallback-plan suffix
    if ctx.get("plan_source") == "python_fallback":
        response = f"{response} (running on fallback plan — LLM review unavailable)"

    if len(short) > 120:
        short = short[:117] + "..."
    return {
        "short": short,
        "detail": {
            "status_line": "Red — acute concern",
            "signal_line": signal,
            "response_line": response,
        },
    }


# ---------------------------------------------------------------------------
# Public API — filled in by Tasks 7-10
# ---------------------------------------------------------------------------

def generate_triage_rationale(triage_result: dict, pitcher_context: dict) -> dict:
    """Compose {short, detail} from a Phase 1 triage result + pitcher context."""
    flag = triage_result.get("flag_level", "green")
    ctx = pitcher_context or {}
    baseline = ctx.get("baseline") or {}
    baseline_state = baseline.get("baseline_state", "full")
    tier = triage_result.get("baseline_tier") or baseline.get("tier", 2)

    # Green → static phrase (A14)
    if flag == "green":
        out = _green_rationale(ctx)
        # Cold-start appendage (A3) — also applies to green detail
        total = baseline.get("total_check_ins", 0)
        if baseline_state == "no_baseline":
            out["detail"]["signal_line"] = (
                out["detail"]["signal_line"].rstrip() +
                f" Baseline establishing — {total}/14 check-ins."
            ).strip()
        elif baseline_state == "provisional":
            out["detail"]["signal_line"] = (
                out["detail"]["signal_line"].rstrip() +
                f" Tier classified from {total}/14 check-ins — may shift as more data arrives."
            ).strip()
        logger.info(
            "rationale | pitcher=%s | type=triage | path=green | tier=%s | state=%s | short_len=%d",
            ctx.get("pitcher_id"), tier, baseline_state, len(out["short"]),
        )
        return out

    # Instant-red branch (A4) — bypasses category framing
    is_instant, trigger = _is_instant_red(triage_result, ctx)
    if is_instant:
        out = _instant_red_rationale(trigger, ctx, triage_result)
        logger.info(
            "rationale | pitcher=%s | type=triage | path=instant_red_%s | short_len=%d",
            ctx.get("pitcher_id"), trigger, len(out["short"]),
        )
        return out

    # Non-green: category-driven
    scores = triage_result.get("category_scores") or {}
    baseline_mean = baseline.get("overall_mean", 8.0)
    dominant = _dominant_category(scores, baseline_mean)
    role = ctx.get("role", "starter")
    is_starter_post_outing = role == "starter" and ctx.get("days_since_outing") in (0, 1)
    is_reliever_reset = role == "reliever" and flag == "modified_green"
    status = _category_status_line(
        flag, dominant, tier, baseline_state,
        post_outing=is_starter_post_outing,
        reliever_reset=is_reliever_reset,
    )
    signal = _signal_line(ctx, triage_result, dominant)
    response = _response_line(triage_result)

    # Fallback-plan suffix (A20)
    if ctx.get("plan_source") == "python_fallback":
        response = f"{response} (running on fallback plan — LLM review unavailable)"

    # Cold-start appendage (A3)
    if baseline_state == "no_baseline":
        signal += f" Baseline establishing — {baseline.get('total_check_ins', 0)}/14 check-ins."
    elif baseline_state == "provisional":
        signal += f" Tier classified from {baseline.get('total_check_ins', 0)}/14 check-ins — may shift as more data arrives."

    short = _compose_short(flag, ctx, triage_result, dominant)

    logger.info(
        "rationale | pitcher=%s | type=triage | path=%s | tier=%s | state=%s | short_len=%d",
        ctx.get("pitcher_id"), flag, tier, baseline_state, len(short),
    )
    return {
        "short": short,
        "detail": {
            "status_line": status,
            "signal_line": signal.strip(),
            "response_line": response,
        },
    }


def generate_exercise_rationale(exercise: dict, constraints_applied: list, plan_context: dict) -> str | None:
    """Per-exercise clause ≤ 60 chars. None if nothing meaningful to say."""
    if not isinstance(exercise, dict):
        return None

    # 1. Constraint-driven — pick the primary constraint tag on this exercise
    if constraints_applied:
        first = constraints_applied[0]
        tag = first.get("tag") if isinstance(first, dict) else first
        cap = first.get("pct") if isinstance(first, dict) else None
        pa = {"lifting_intensity_cap": cap} if cap is not None else {}
        phrase = _phrase_short(tag, pa) if tag else ""
        if phrase:
            out = phrase.strip().rstrip(".")
            return out[:60]

    # 2. Progression note inline on the exercise
    note = exercise.get("progression_note")
    if note:
        out = f"progression — {note}"
        return out[:60]

    # 3. Template default → nothing to say
    return None


_DAY_PHRASES = {
    "lift": "Lift-focused day",
    "throw": "Throwing day",
    "bullpen": "Bullpen day",
    "recovery": "Recovery day",
}


def generate_day_rationale(plan: dict, triage_result: dict, pitcher_context: dict) -> str | None:
    """One sentence summarizing the day's shape."""
    flag = (triage_result or {}).get("flag_level", "green")
    day_focus = (plan or {}).get("day_focus") or "lift"
    phrase = _DAY_PHRASES.get(day_focus, "Training day")

    # Post-outing starter or reset reliever
    role = (pitcher_context or {}).get("role", "starter")
    dso = (pitcher_context or {}).get("days_since_outing")

    if day_focus == "recovery" and role == "starter" and dso in (0, 1):
        return f"Recovery day — {dso} day{'s' if dso != 1 else ''} post-outing, flush work only."

    if flag == "green":
        return f"{phrase} — full program."

    mods = triage_result.get("modifications") or []
    mod_tags = [m if isinstance(m, str) else m.get("tag", "") for m in mods if m]
    if mod_tags:
        pa = triage_result.get("protocol_adjustments") or {}
        mod_phrase = _join_phrases(mod_tags[:2], pa, "short")
        if mod_phrase:
            return f"{phrase} — {mod_phrase}."
    return f"{phrase} — adjusted based on today's signals."
