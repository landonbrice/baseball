"""Program Engine v1 — async authoring job (Sprint C).

Engine authoring is a compile step: 5–25 minutes of reasoning-model time
with retries. That never fits a request/response cycle (the mini-app fetch
dies at ~60s), so authoring runs as a fire-and-forget background task and
the pitcher gets a Telegram DM when the draft lands.

Entry points:
  - `/buildprogram [goal]` bot command (registered in bot/main.py) — kicks
    `asyncio.create_task(run_authoring_job(...))` and replies immediately.
  - Callable from any future API surface (Builder finalize behind
    PROGRAM_ENGINE_V1) with the same signature.

The job assembles the same inputs the proven demo path used: live knowledge
pack via `resolve_for_program_gen`, the goal's block_library template as the
fallback floor, and a full-library validation ctx with structural tags.
"""
from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

GOAL_WEEKS = {"velocity": 12, "return_to_play": 9}
DEFAULT_GOAL = "return_to_play"


def build_validation_ctx(profile: dict) -> dict:
    """Guardrail ctx from the canonical exercise library (git JSON — the same
    159 rows the live table is seeded from). Mirrors the demo's proven ctx."""
    from bot.services.program_engine.structural_invariants import derive_structural_tags

    lib_path = Path(__file__).resolve().parents[3] / "data" / "knowledge" / "exercise_library.json"
    lib = json.loads(lib_path.read_text())
    rows = lib if isinstance(lib, list) else lib.get("exercises", lib)
    tag_lookup = {}
    for r in rows:
        tags = derive_structural_tags(r)
        if tags:
            tag_lookup[r["id"]] = tags
    return {
        "exercises_rows": rows,
        "available_equipment": (profile.get("current_training") or {}).get("equipment", []),
        "active_modifications": list((profile.get("active_flags") or {}).get("modifications") or []),
        "tag_lookup": tag_lookup,
    }


def _program_row(program, template: dict, created_by: str, role: str) -> dict:
    return {
        "pitcher_id": program.pitcher_id,
        "parent_template_id": template.get("block_template_id"),
        "domain": template.get("domain") or "throwing",
        "tuned_spec_json": {"weeks": program.total_weeks},
        "generated_schedule_json": {
            "days": [d.model_dump() for d in program.days],
            "scaffold_kind": "engine_v1_authored",
        },
        "start_date": program.days[0].date,
        "nominal_end_date": program.days[-1].date,
        "current_day_index": 0,
        "held_days_count": 0,
        "status": "draft",
        "created_by": created_by,
        "created_by_role": role,
        "knowledge_version": program.knowledge_version,
        "generation_provenance": program.generation_provenance,
        "engine_version": program.engine_version,
    }


async def _dm(chat_id, text: str) -> None:
    if not chat_id:
        return
    try:
        from telegram import Bot

        from bot.config import TELEGRAM_BOT_TOKEN

        await Bot(token=TELEGRAM_BOT_TOKEN).send_message(chat_id=chat_id, text=text)
    except Exception:
        logger.warning("authoring_job: DM to %s failed", chat_id, exc_info=True)


async def run_authoring_job(
    pitcher_id: str,
    goal: str = DEFAULT_GOAL,
    *,
    chat_id: Optional[int] = None,
    created_by_role: str = "pitcher",
) -> Optional[str]:
    """Author → validate → persist a draft program; DM the outcome.

    Returns the persisted program_id (draft), or None on hard failure.
    Never raises — this runs detached via asyncio.create_task.
    """
    try:
        from bot.services import db
        from bot.services.context_manager import load_context, load_profile
        from bot.services.program_engine.orchestrator import author_validate_persist
        from bot.services.research_resolver import resolve_for_program_gen

        goal = goal if goal in GOAL_WEEKS else DEFAULT_GOAL
        weeks = GOAL_WEEKS[goal]
        start = date.today()
        goal_spec = {
            "tags": [goal],
            "target_weeks": weeks,
            "start_date": start.isoformat(),
            "target_date": (start + timedelta(days=weeks * 7 - 1)).isoformat(),
            "tunables": {},
        }
        profile = load_profile(pitcher_id)
        context = ""
        try:
            context = load_context(pitcher_id)
        except Exception:
            pass

        pack = resolve_for_program_gen(
            pitcher_profile=profile, pitcher_context=context, goal_spec=goal_spec,
        )
        templates = pack.get("templates") or []
        if not templates:
            await _dm(chat_id, f"Couldn't build a {goal.replace('_', ' ')} program — no matching template in the library.")
            return None
        template = templates[0]

        result = await author_validate_persist(
            pitcher_profile=profile,
            pitcher_context=context,
            goal_spec=goal_spec,
            knowledge_pack=pack,
            pitcher_validation_ctx=build_validation_ctx(profile),
            block_library_row=template,
            target_date=goal_spec["target_date"],
            max_reprompts=4,
        )
        program = result.program
        program_id = db.create_program(
            _program_row(program, template, created_by=pitcher_id, role=created_by_role)
        )

        if result.fallback_used:
            await _dm(
                chat_id,
                f"Your {weeks}-week {goal.replace('_', ' ')} draft is ready — built from the "
                f"proven template (the AI author's attempts didn't pass the safety checks this "
                f"time). Open the mini app → Programs → Drafts to review and activate.",
            )
        else:
            await _dm(
                chat_id,
                f"✅ Your {weeks}-week {goal.replace('_', ' ')} program is drafted — designed "
                f"specifically for you and validated by the safety guardrails. Open the mini "
                f"app → Programs → Drafts to review and activate.",
            )
        logger.info(
            "authoring_job_complete",
            extra={
                "pitcher_id": pitcher_id,
                "goal": goal,
                "program_id": program_id,
                "fallback_used": result.fallback_used,
                "attempts": len(result.attempts),
            },
        )
        return program_id
    except Exception:
        logger.error("authoring_job failed for %s", pitcher_id, exc_info=True)
        await _dm(chat_id, "Program authoring hit an error — nothing was saved. Try /buildprogram again later.")
        return None
