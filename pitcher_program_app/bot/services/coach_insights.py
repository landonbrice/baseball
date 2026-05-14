"""Coach Insights Engine — generates structured suggestions for coaches.

v0 ships with one category: pre_start_nudge.
Plan 7 / A4 adds three more rule-based generators:
  - program_drift          (active program > 5 days behind expected day index)
  - program_flag_mismatch  (high-intent program while flag is yellow/red)
  - team_program_lagging   (team-assigned block <50% average completion)

All A4 generators are RULE-BASED (L5/L6). LLM polish lives in Plan 8 — the
prompt files in bot/prompts/insight_*.md are placeholders for that pass.

Runs on a schedule after morning check-ins complete.
"""

import logging
from datetime import datetime, date, timedelta
from typing import Optional

from bot.config import CHICAGO_TZ
from bot.services.db import (
    get_client, get_training_model, get_daily_entry,
    get_pending_suggestions, upsert_suggestion,
)
from bot.services.team_scope import list_team_pitchers, get_pitcher_next_start

logger = logging.getLogger(__name__)


# Templates considered "high intent" for the mismatch generator — running these
# while flag is yellow/red is the signal we surface.
_HIGH_INTENT_TEMPLATES = frozenset({
    "velocity_12wk_v1",
    "offseason_base_4wk_v1",
})


def run_insights_for_team(team_id: str) -> list:
    """Generate all insight categories for a team. Returns list of new suggestions."""
    today_str = datetime.now(CHICAGO_TZ).strftime("%Y-%m-%d")
    new_suggestions = []

    # Category 1: Pre-start nudges
    new_suggestions.extend(_generate_pre_start_nudges(team_id, today_str))

    return new_suggestions


def _generate_pre_start_nudges(team_id: str, today_str: str) -> list:
    """Generate pre-start nudge suggestions for pitchers starting in the next 3 days.

    Checks if the pitcher's plan in the days leading up to the start
    looks heavier than typical pre-start ramp. If so, suggests lightening.
    """
    suggestions = []
    pitchers = list_team_pitchers(team_id)
    today = date.fromisoformat(today_str)

    # Expire old pre_start_nudge suggestions
    existing = get_pending_suggestions(team_id)
    for s in existing:
        if s.get("category") == "pre_start_nudge":
            if s.get("expires_at"):
                exp = datetime.fromisoformat(s["expires_at"].replace("Z", "+00:00"))
                if exp < datetime.now(CHICAGO_TZ):
                    s["status"] = "expired"
                    upsert_suggestion(s)

    for pitcher in pitchers:
        pid = pitcher["pitcher_id"]
        role = pitcher.get("role", "")
        if "starter" not in role:
            continue

        next_start = get_pitcher_next_start(pid, team_id, today_str)
        if not next_start:
            continue

        game_date = date.fromisoformat(next_start["game_date"])
        days_until = (game_date - today).days

        # Only nudge for starts 1-3 days away
        if days_until < 1 or days_until > 3:
            continue

        # Check if there's already a pending nudge for this pitcher + game
        already_exists = any(
            s.get("pitcher_id") == pid
            and s.get("category") == "pre_start_nudge"
            and s.get("status") == "pending"
            for s in existing
        )
        if already_exists:
            continue

        # Check today's plan — is it heavier than expected for a pre-start day?
        entry = get_daily_entry(pid, today_str)
        if not entry:
            continue

        plan = entry.get("plan_generated") or {}
        lifting = plan.get("exercise_blocks") or entry.get("lifting", {}).get("exercises", [])

        # Simple heuristic: count total sets in today's lifting
        total_sets = 0
        if isinstance(lifting, list):
            for block in lifting:
                exercises = block.get("exercises", []) if isinstance(block, dict) else []
                for ex in exercises:
                    total_sets += ex.get("sets", 0) if isinstance(ex, dict) else 0

        # Pre-start day (1-2 days out) should be light: < 12 total sets
        if days_until <= 2 and total_sets > 12:
            pitcher_name = pitcher.get("name", pid)
            opponent = next_start.get("opponent", "")

            suggestion = {
                "team_id": team_id,
                "pitcher_id": pid,
                "category": "pre_start_nudge",
                "title": f"Review {pitcher_name}'s lift before {game_date.strftime('%A')}'s start{' vs ' + opponent if opponent else ''}",
                "reasoning": (
                    f"{pitcher_name} starts {'tomorrow' if days_until == 1 else 'in 2 days'} "
                    f"but today's lift has {total_sets} total sets. "
                    f"Pre-start days typically have < 12 sets to preserve freshness. "
                    f"Consider reducing volume or swapping to lighter alternatives."
                ),
                "proposed_action": {
                    "type": "reduce_volume",
                    "description": f"Reduce today's lifting volume to pre-start level",
                },
                "status": "pending",
                "expires_at": (
                    datetime.combine(game_date, datetime.min.time())
                    .replace(tzinfo=CHICAGO_TZ)
                    .isoformat()
                ),
            }
            upsert_suggestion(suggestion)
            suggestions.append(suggestion)
            logger.info(f"Generated pre-start nudge for {pid} (starts {game_date})")

    return suggestions


# ---------------------------------------------------------------------------
# Plan 7 / A4 — Rule-based program insight generators
#
# Output shape matches the live coach_suggestions schema:
#   team_id, pitcher_id, category, title, reasoning, proposed_action (jsonb),
#   status. Callers fill team_id where None is placeholder.
# ---------------------------------------------------------------------------


def _expected_day_index(program: dict, today: date) -> int:
    """Calendar days elapsed since program.start_date — what current_day_index
    SHOULD be if no holds had occurred.

    Returns 0 when start_date is missing or in the future.
    """
    raw_start = program.get("start_date")
    if not raw_start:
        return 0
    try:
        start = date.fromisoformat(raw_start)
    except (TypeError, ValueError):
        return 0
    return max(0, (today - start).days)


def generate_drift_insight_for_program(
    program: dict,
    today: Optional[date] = None,
) -> Optional[dict]:
    """Return a coach_suggestions row dict if the program has drifted >5 days.

    Drift = expected_day_index - current_day_index. A flat 5-day grace covers
    brief illnesses; sustained drift beyond that surfaces an insight.

    Returns None when within grace window, when start_date is missing, or when
    the program is somehow ahead of schedule.
    """
    today = today or date.today()
    expected = _expected_day_index(program, today)
    actual = int(program.get("current_day_index") or 0)
    drift_days = expected - actual
    if drift_days <= 5:
        return None

    domain = (program.get("domain") or "program").title()
    held = int(program.get("held_days_count") or 0)
    return {
        "team_id": None,  # caller fills in
        "pitcher_id": program["pitcher_id"],
        "category": "program_drift",
        "title": f"Program drifted {drift_days} days behind",
        "reasoning": (
            f"{domain} program {program.get('parent_template_id')} "
            f"is on day {actual + 1} but should be on day {expected + 1}. "
            f"Held {held} days lifetime. "
            "Consider archiving and rebuilding, or accepting the new pace."
        ),
        "proposed_action": {
            "type": "review_drift",
            "program_id": program.get("program_id"),
            "drift_days": drift_days,
            "expected_day": expected,
            "actual_day": actual,
        },
        "status": "pending",
    }


def generate_mismatch_insight_for_pitcher(
    profile: dict,
    flag_level: Optional[str],
    active_programs: list,
) -> Optional[dict]:
    """Return a coach_suggestions row if the pitcher's flag level is yellow/red
    AND they are running a high-intent program (velocity / off-season base).

    Pure / synchronous / rule-based. When Plan 8 introduces LLM polish, that
    PR can introduce its own async entry point — pre-building one here was
    YAGNI and silently dropped insights (`coroutine.send(None)` only worked
    while the body never awaited).

    `flag_level` is read separately from the profile because `db.get_pitcher`
    returns the raw pitcher row without the compat-layer `active_flags` nest.
    Caller passes the value sourced from `db.get_active_flags(...)`.
    """
    if flag_level not in ("yellow", "red", "critical_red"):
        return None
    risky_program = next(
        (p for p in active_programs
         if p.get("parent_template_id") in _HIGH_INTENT_TEMPLATES),
        None,
    )
    if not risky_program:
        return None

    pitcher_id = profile.get("pitcher_id") or risky_program.get("pitcher_id")
    name = profile.get("name") or pitcher_id
    template = risky_program.get("parent_template_id")
    return {
        "team_id": None,  # caller fills in
        "pitcher_id": pitcher_id,
        "category": "program_flag_mismatch",
        "title": f"{name} on high-intent program while {flag_level.upper()}",
        "reasoning": (
            f"Pitcher built {template} (high-intent phase) but current flag "
            f"level is {flag_level.upper()}. Consider scaling intent down via "
            "mutation preview, or archiving and rebuilding with a more "
            "conservative goal."
        ),
        "proposed_action": {
            "type": "review_mismatch",
            "program_id": risky_program.get("program_id"),
            "flag_level": flag_level,
            "template": template,
        },
        "status": "pending",
    }


def generate_team_completion_insight(
    team_assigned_block_row: dict,
    member_programs: list,
    today: Optional[date] = None,
) -> Optional[dict]:
    """For a team-assigned block, compute the average completion percent across
    member pitchers' programs. Flag if mean <50% AND at least one pitcher is
    individually <50%.

    The returned row is keyed to the first lagger as a *representative
    pitcher_id* — `coach_suggestions.pitcher_id` is NOT NULL + FK on
    `pitchers(pitcher_id)`, so we cannot persist a true team-scoped row
    without a schema migration. The full lagger list lives in
    ``proposed_action.lagger_pitcher_ids``; ``proposed_action.scope = "team"``
    marks the row as team-scoped so renderers know to show the team frame.

    Returns None when there are no member programs.
    """
    if not member_programs:
        return None

    today = today or date.today()
    completions = []
    laggers = []
    expected_sum = 0
    for p in member_programs:
        days = (p.get("generated_schedule_json") or {}).get("days") or []
        # 84d is a typical 12wk throwing program — used as fallback when the
        # summary projection trimmed generated_schedule_json out.
        total = len(days) or 84
        idx = int(p.get("current_day_index") or 0)
        pct = (idx / total) if total else 0.0
        completions.append(pct)
        expected_sum += _expected_day_index(p, today)
        if pct < 0.5:
            pid = p.get("pitcher_id")
            if pid:
                laggers.append(pid)

    mean_pct = sum(completions) / len(completions)
    if mean_pct >= 0.5 or not laggers:
        return None

    # Representative pitcher — stable (first in member_programs ordering, which
    # the caller fixes via list_member_programs_for_team_block).
    representative_pitcher_id = laggers[0]

    block_label = (
        team_assigned_block_row.get("block_template_id")
        or team_assigned_block_row.get("block_id")
        or "team block"
    )
    weeks_in = round((expected_sum / len(member_programs)) / 7, 1)

    return {
        "team_id": team_assigned_block_row.get("team_id"),
        # NOT NULL + FK on pitchers — must be a real pitcher_id. The insight is
        # logically team-scoped; see scope="team" in proposed_action below.
        "pitcher_id": representative_pitcher_id,
        "category": "team_program_lagging",
        "title": f"{len(laggers)} pitchers <50% on {block_label}",
        "reasoning": (
            f"Team is ~{weeks_in} weeks into {block_label}. "
            f"Average completion {round(mean_pct * 100)}%. "
            f"Behind: {', '.join(laggers)}."
        ),
        "proposed_action": {
            "type": "review_team_lag",
            "block_id": team_assigned_block_row.get("block_id"),
            "block_template_id": team_assigned_block_row.get("block_template_id"),
            "mean_completion_pct": round(mean_pct, 2),
            "lagger_pitcher_ids": laggers,
            # Flags this as a team-scoped insight despite the pitcher_id key.
            # Renderers (Insights UI / C6) read this to display team frame.
            "scope": "team",
        },
        "status": "pending",
    }
