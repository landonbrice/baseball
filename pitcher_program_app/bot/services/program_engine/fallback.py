"""Program Engine v1 — deterministic safe fallback floor (Task 2.5).

When LLM authoring fails (timeout, parse error, repeated guardrail rejection),
the orchestrator returns a deterministic program built from the live
`block_library` template. The fallback floor is STILL a real periodized
program (per §3c) — not the rotation-repeat slop. It validates as `valid`
through Phase 2.4 by construction.

Build approach:
- Read `block_library.velocity_12wk_v1.content.phases` (live, populated by
  migration 033).
- For each phase, lay out week_count × 7 days.
- Stamp `phase_name`, `intent_pct` (from phase.effort_pct), `is_deload`
  (from acwr_governor.deload_weeks_default), `template_key`.
- Throwing 5-tuple on the 3 weekly throwing days (from
  `content.lifting_integration.day_split` indices + `throws_per_week`).
- Lifting blocks from a default RIR table per the phase's lifting_phase mapping.
- Date arithmetic: start_date + day_index days.

Goal-agnostic — works for any block_library row with `content.phases` +
`content.lifting_integration`. v1 ships with velocity; future packs are
content changes, not engine changes.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Optional, Sequence

from bot.services.program_engine.schemas import (
    Day,
    LiftingBlock,
    LiftingExercise,
    PitcherProgram,
    Phase,
    ProgressionState,
    Rationale,
    ThrowingFiveTuple,
)

# Day-of-week the throwing sessions fall on (relative to phase start). 3
# sessions/week per `velocity_12wk_v1.content.throws_per_week=3`, spaced
# M/W/F-style.
_DEFAULT_THROWING_DAYS = (0, 2, 4)
# Lifting sessions land on M and Th per `lifting_integration.sessions_per_week=2`.
_DEFAULT_LIFTING_DAYS = (0, 3)

# Default exercise IDs by lifting_phase + day_split — pulled from the live
# library so the fallback is canonical. These are conservative seed picks; a
# Plan v2 enhancement would parameterize them.
_DEFAULT_LIFTING_EXERCISES: dict[tuple[str, str], list[tuple[str, int, str, str]]] = {
    # (lifting_phase, day_split) → [(ex_id, sets, reps, intensity), ...]
    ("hypertrophy", "posterior_chain"): [
        ("ex_004", 3, "8-10", "50-75% 1RM"),   # RFE Split Squat
        ("ex_005", 3, "8-10", "50-75% 1RM"),   # Romanian Deadlift
        ("ex_020", 3, "8-10", "50-75% 1RM"),   # Chest-Supported Row
        ("ex_070", 3, "12", "BW"),             # Flexor Pressout (FPM)
    ],
    ("hypertrophy", "push_pull"): [
        ("ex_025", 3, "8-10", "50-75% 1RM"),   # Neutral-Grip DB Bench Press
        ("ex_128", 3, "6-8", "BW"),            # Pull-Up
        ("ex_029", 3, "10", "BW"),             # Prone Y-T-W-A
        ("ex_041", 3, "12", "BW"),             # Pronator Teres Isolation (FPM)
    ],
    ("hypertrophy_to_strength", "posterior_chain"): [
        ("ex_001", 3, "6-8", "70-80% 1RM"),    # Trap Bar Deadlift
        ("ex_004", 3, "6-8", "70-80% 1RM"),
        ("ex_020", 3, "8-10", "70-80% 1RM"),
        ("ex_070", 3, "12", "BW"),
    ],
    ("hypertrophy_to_strength", "push_pull"): [
        ("ex_025", 3, "6-8", "75-85% 1RM"),
        ("ex_128", 3, "5-8", "BW"),
        ("ex_029", 2, "10", "BW"),
        ("ex_041", 3, "12", "BW"),
    ],
    ("strength", "posterior_chain"): [
        ("ex_001", 4, "4-6", "85% 1RM"),
        ("ex_004", 3, "6", "80% 1RM"),
        ("ex_020", 3, "6-8", "80% 1RM"),
        ("ex_070", 3, "10", "BW"),
    ],
    ("strength", "push_pull"): [
        ("ex_025", 4, "4-6", "85% 1RM"),
        ("ex_128", 4, "4-6", "BW"),
        ("ex_029", 2, "10", "BW"),
        ("ex_041", 3, "10", "BW"),
    ],
    ("strength_power", "posterior_chain"): [
        ("ex_001", 4, "3-5", "90% 1RM"),
        ("ex_014", 3, "5", "Near Maximal"),    # Rotational Med Ball
        ("ex_020", 3, "5-8", "80% 1RM"),
        ("ex_070", 3, "10", "BW"),
    ],
    ("strength_power", "push_pull"): [
        ("ex_025", 4, "3-5", "87-95% 1RM"),
        ("ex_128", 4, "3-5", "BW"),
        ("ex_145", 3, "5", "BW"),              # Plyometric Push-Up
        ("ex_041", 3, "10", "BW"),
    ],
}


def _parse_distance(s: str) -> int:
    """Parse '45ft' → 45; '90ft' → 90; 'full_progression' → 120; 'mound_work' → 60."""
    if not s:
        return 60
    s = str(s).lower()
    if "mound" in s:
        return 60
    if "full" in s:
        return 120
    import re
    m = re.match(r"(\d+)\s*ft", s)
    if m:
        return int(m.group(1))
    return 60


def _phase_mapping_for_week(
    content: dict,
    week_one_based: int,
) -> Optional[dict]:
    """Look up the `content.lifting_integration.phase_mapping[*]` entry whose
    `throwing_phase_weeks` includes `week_one_based`."""
    lifting = (content or {}).get("lifting_integration") or {}
    mapping = lifting.get("phase_mapping") or []
    for entry in mapping:
        wks = entry.get("throwing_phase_weeks") or []
        if week_one_based in wks:
            return entry
    return None


def _build_lifting_blocks(
    lifting_phase: str,
) -> list[LiftingBlock]:
    """Build the two-block lifting day (Block 1 + Block 2) for a given phase."""
    blocks: list[LiftingBlock] = []
    for split in ("posterior_chain", "push_pull"):
        key = (lifting_phase, split)
        if key not in _DEFAULT_LIFTING_EXERCISES:
            continue
        exercises = [
            LiftingExercise(exercise_id=ex_id, sets=sets, reps=reps, intensity=intensity)
            for (ex_id, sets, reps, intensity) in _DEFAULT_LIFTING_EXERCISES[key]
        ]
        blocks.append(LiftingBlock(block_name=split.replace("_", " ").title(), exercises=exercises))
    return blocks


def build_fallback_program(
    *,
    pitcher_id: str,
    goal_spec: dict,
    block_library_row: dict,
    knowledge_version: str,
    target_date: Optional[str] = None,
) -> PitcherProgram:
    """Construct a deterministic fallback `PitcherProgram` from a block_library row.

    Required `block_library_row` shape (matches the live velocity_12wk_v1 after
    migration 033):
      - content.phases: [{name, weeks, effort_pct, distances, total_throws_range}]
      - content.acwr_governor.deload_weeks_default: list[int]
      - content.lifting_integration.phase_mapping: per-phase lifting_phase + day_split
      - content.throws_per_week: int
      - content.day_type_taxonomy / phase_gates: optional context

    The returned program is valid by construction (intent never crosses 84 in
    the base phase, deload weeks marked, etc.) and passes Phase 2.4 validation
    without repair.
    """
    content = block_library_row.get("content") or {}
    phases_data = content.get("phases") or []
    if not phases_data:
        raise ValueError("block_library_row missing content.phases")

    deload_weeks = set((content.get("acwr_governor") or {}).get("deload_weeks_default") or [])
    throws_per_week = content.get("throws_per_week") or 3
    throwing_days_in_week = _DEFAULT_THROWING_DAYS[:throws_per_week]

    # Anchor calendar: target_date is the LAST day; back out the first day.
    total_weeks = sum(int(p.get("weeks") and len(p.get("weeks")) or 0) for p in phases_data) or 12
    if target_date:
        last = datetime.fromisoformat(target_date).date()
        start = last - timedelta(days=total_weeks * 7 - 1)
    else:
        start = date.today()
        last = start + timedelta(days=total_weeks * 7 - 1)

    # Walk weeks → days
    days: list[Day] = []
    phase_objs: list[Phase] = []
    day_idx = 0
    # Track prior phase's effort_pct + per_session_throws so we can ramp
    # smoothly INTO each phase rather than jumping at the boundary. This
    # keeps weekly ACWR inside the 1.5 hard-cap during phase transitions.
    prior_effort_pct: Optional[int] = None
    prior_throws: Optional[int] = None
    for p_idx, p in enumerate(phases_data):
        name = p.get("name") or f"Phase {p_idx+1}"
        week_list = p.get("weeks") or []
        effort_pct = int(p.get("effort_pct") or 50)
        distances = p.get("distances") or ["60ft"]
        max_distance = max(_parse_distance(d) for d in distances)
        throws_range = p.get("total_throws_range") or [40, 60]
        weekly_throw_target = (throws_range[0] + throws_range[1]) // 2
        per_session_throws = max(10, weekly_throw_target // throws_per_week)
        # Ramp-in: linearly interpolate from prior phase's max toward this
        # phase's max across the FULL phase span. This keeps weekly ACWR
        # inside the band at phase transitions even when the phase deltas
        # are large (e.g. Phase 1 50% → Phase 2 70%).
        if prior_effort_pct is not None and len(week_list) > 1:
            ramp_weeks = len(week_list)
        else:
            ramp_weeks = 0

        phase_objs.append(
            Phase(
                phase_id=name.lower().replace(" ", "_").replace("+", "plus").replace("__", "_"),
                name=name,
                week_count=len(week_list),
                phase_type="base" if p_idx == 0 else ("realization" if p_idx == len(phases_data) - 1 else "accumulation"),
                intent_summary=p.get("intent_notes") or f"{name} phase — {effort_pct}% intent target.",
                intent_kpis=[f"max_distance_{max_distance}ft", f"effort_{effort_pct}pct"],
                default_training_intent="lifting+throwing",
            )
        )

        for wk_idx_in_phase, week_one in enumerate(week_list):
            is_deload_week = week_one in deload_weeks
            mapping = _phase_mapping_for_week(content, week_one) or {}
            lifting_phase = mapping.get("lifting_phase") or "hypertrophy"
            # Within-phase ramp: interpolate from prior phase's max toward
            # this phase's max during the first ramp_weeks.
            if ramp_weeks > 0 and wk_idx_in_phase < ramp_weeks and prior_effort_pct is not None and prior_throws is not None:
                t = (wk_idx_in_phase + 1) / (ramp_weeks + 1)
                target_intent = int(prior_effort_pct + (effort_pct - prior_effort_pct) * t)
                target_throws = int(prior_throws + (per_session_throws - prior_throws) * t)
            else:
                target_intent = effort_pct
                target_throws = per_session_throws
            # Deload weeks reduce throwing volume + intent — this is what makes
            # the deload real (not just a flag) and keeps ACWR inside the band
            # at phase transitions (Wk4 & Wk7 in the velocity arc).
            deload_throw_factor = 0.65 if is_deload_week else 1.0
            deload_intent_drop = 10 if is_deload_week else 0
            base_intent = min(84, target_intent) if p_idx == 0 else target_intent
            wk_intent = max(30, base_intent - deload_intent_drop)
            wk_throws = max(10, int(target_throws * deload_throw_factor))
            for dow in range(7):
                d_date = start + timedelta(days=day_idx)
                throws: Optional[ThrowingFiveTuple] = None
                lifting_blocks: list[LiftingBlock] = []
                day_focus = None
                if dow in throwing_days_in_week:
                    throws = ThrowingFiveTuple(
                        distance_ft=max_distance,
                        throw_count=wk_throws,
                        intensity_pct=wk_intent,
                        drill=(p.get("drills") or ["long toss"])[0],
                    )
                    day_focus = f"{name}: {throws.intensity_pct}% throwing"
                if dow in _DEFAULT_LIFTING_DAYS:
                    lifting_blocks = _build_lifting_blocks(lifting_phase)
                    if not day_focus:
                        day_focus = f"{name}: {lifting_phase} lifting"
                days.append(
                    Day(
                        day_index=day_idx,
                        template_key=f"wk{week_one}_d{dow+1}_fallback",
                        date=d_date.isoformat(),
                        anchor_kind="calendar_relative",
                        phase_name=name,
                        intent_pct=throws.intensity_pct if throws else None,
                        is_deload=is_deload_week,
                        is_rest=throws is None and not lifting_blocks,
                        throwing_5tuple=throws,
                        lifting_blocks=lifting_blocks,
                        day_focus=day_focus,
                    )
                )
                day_idx += 1
        # End of this phase — record its max for the next phase's ramp-in.
        prior_effort_pct = effort_pct
        prior_throws = per_session_throws

    return PitcherProgram(
        pitcher_id=pitcher_id,
        goal=(goal_spec.get("tags") or ["unknown"])[0],
        domain="unified",
        knowledge_version=knowledge_version,
        engine_version="v1",
        generated_at=datetime.now().replace(microsecond=0).isoformat(),
        target_date=last.isoformat(),
        total_weeks=total_weeks,
        status="draft",
        phases=phase_objs,
        days=days,
        rationale=Rationale(
            phase_logic=(
                "Deterministic fallback derived from block_library template. "
                "Phases mirror the live content.phases. Deload weeks from "
                "content.acwr_governor.deload_weeks_default. Lifting per "
                "content.lifting_integration.phase_mapping."
            ),
            individualization_notes=(
                "Generated as the deterministic safety net when LLM authoring "
                "failed. Operator should review and may regenerate via the "
                "Builder UI to get a fully individualized program."
            ),
            cited_research_doc_ids=list(block_library_row.get("research_doc_ids") or []),
        ),
        progression_state=ProgressionState(),
        generation_provenance={
            "fallback_used": True,
            "template_id": block_library_row.get("block_template_id"),
        },
    )
