"""Shared mock helper for plan_generator golden-snapshot tests.

# Data-layer / file-I/O / wall-clock / non-determinism call sites inside
# `bot.services.plan_generator.generate_plan` (not its helpers — the calls
# reachable from inside generate_plan):
#
#   load_profile(pitcher_id)                     -> bot.services.context_manager
#   load_context(pitcher_id)                     -> bot.services.context_manager
#   get_recent_entries(pitcher_id, n=7)          -> bot.services.context_manager
#   datetime.now(CHICAGO_TZ)                     -> wall clock, frozen via freezegun
#   resolve_team_block(...)                      -> bot.services.team_programs
#   compute_days_until_next_start(...)           -> bot.services.team_programs
#   get_today_mobility()                         -> bot.services.mobility   (ISO week + file I/O)
#   build_exercise_pool(...)                     -> bot.services.exercise_pool
#     -> internally calls _load_exercises() which hits Supabase.
#        We patch _load_exercises to return the JSON-seeded library.
#     -> uses random.random() for tie-breaking in _pick.  Seed before invoke.
#   get_recent_exercise_ids(pitcher_id, days=7)  -> bot.services.exercise_pool
#   resolve_research(profile, ctx, triage)       -> bot.services.research_resolver
#   call_llm / call_llm_reasoning                -> bot.services.llm
#     -> patched to raise asyncio.TimeoutError so the existing production
#        timeout-fallback branch runs (this is what hits the python_fallback
#        path we want to lock down).
#   record_and_check_emergency(...)              -> bot.services.health_monitor
#                                                    (stateful counter; mock returns None)
#   hydrate_exercises(items)                     -> real implementation kept,
#                                                    but with `_load_exercises` patched
#                                                    so the snapshot is deterministic.
#   load_template(name) reads data/templates/*.json -> deterministic, NOT mocked.
#
# Helpers inside plan_generator that read templates (_build_warmup_block,
# _build_throwing_plan, _build_arm_care_blocks, _select_plyocare) all go
# through load_template -> filesystem JSON which is checked into the repo
# and therefore deterministic.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import random
from pathlib import Path
from unittest.mock import AsyncMock, patch


REPO_ROOT = Path(__file__).resolve().parents[3]
EXERCISE_LIBRARY_PATH = REPO_ROOT / "data" / "knowledge" / "exercise_library.json"


def _load_exercise_library_rows() -> list:
    with open(EXERCISE_LIBRARY_PATH) as f:
        data = json.load(f)
    return data["exercises"]


class _ResearchPayloadStub:
    """Mimics the resolve_research return shape used by plan_generator."""
    combined_text = ""
    loaded_docs: list = []


@contextlib.contextmanager
def apply_legacy_mocks(fixture: dict, *, seed: int = 0):
    """Context manager applying every patch the python-fallback branch needs.

    Yields nothing; use as `with apply_legacy_mocks(fixture): ...`.

    `seed` controls random.seed() for deterministic _pick() tie-breaking.
    """
    data = fixture["data_layer"]
    profile = data["profile"]
    context = data["context"]
    recent_entries = data["recent_entries"]
    recent_exercise_ids = set(data["recent_exercise_ids"] or [])
    team_block = data["team_block"]
    days_until_start = data["days_until_start"]
    mobility_data = data["mobility_data"]

    exercise_rows = _load_exercise_library_rows()
    # Build snapshot keyed by id and slug (mirrors exercise_pool._refresh_snapshot)
    snapshot = {}
    for ex in exercise_rows:
        if ex.get("id"):
            snapshot[ex["id"]] = ex
        if ex.get("slug"):
            snapshot[ex["slug"]] = ex

    # LLM helpers — both raise asyncio.TimeoutError to exercise the existing
    # production timeout-fallback branch.  Two-tuple return signature is irrelevant
    # because the exception fires before any unpacking.
    async def _llm_timeout(*args, **kwargs):
        raise asyncio.TimeoutError("mocked timeout for golden snapshot")

    patches = [
        # context_manager
        patch("bot.services.plan_generator.load_profile", return_value=profile),
        patch("bot.services.plan_generator.load_context", return_value=context),
        patch("bot.services.plan_generator.get_recent_entries", return_value=recent_entries),

        # team_programs (imported lazily inside generate_plan via local import)
        patch("bot.services.team_programs.resolve_team_block", return_value=team_block),
        patch("bot.services.team_programs.compute_days_until_next_start", return_value=days_until_start),

        # mobility
        patch("bot.services.mobility.get_today_mobility", return_value=mobility_data),

        # exercise_pool — patch _load_exercises directly so the snapshot logic is bypassed.
        # Also patch the snapshot dict so hydrate_exercises (which uses _get_from_snapshot)
        # finds names without falling through to Supabase via the lazy-miss path.
        patch("bot.services.exercise_pool._load_exercises", return_value=exercise_rows),
        patch.dict("bot.services.exercise_pool._EXERCISE_SNAPSHOT", snapshot, clear=True),
        patch("bot.services.exercise_pool.get_recent_exercise_ids", return_value=recent_exercise_ids),
        # Also patch the lazy-miss path: get_exercise() -> Supabase.  Return None for
        # anything not already in the snapshot (the snapshot has 159 entries by id+slug).
        patch("bot.services.exercise_pool.get_exercise", return_value=None),
        # build_exercise_pool also reaches into bot.services.db for phase + model data
        patch("bot.services.db.get_current_phase", return_value=None),
        patch("bot.services.db.get_training_model", return_value={}),

        # research_resolver
        patch("bot.services.plan_generator.resolve_research", return_value=_ResearchPayloadStub()),

        # llm — both helpers patched to raise asyncio.TimeoutError
        patch("bot.services.plan_generator.call_llm", new=AsyncMock(side_effect=_llm_timeout)),
        patch("bot.services.plan_generator.call_llm_reasoning", new=AsyncMock(side_effect=_llm_timeout)),

        # health_monitor — emergency counter is stateful in production
        patch("bot.services.plan_generator.record_and_check_emergency", return_value=None),
    ]

    # Seed random for deterministic _pick tie-breaking
    random.seed(seed)

    with contextlib.ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        yield
