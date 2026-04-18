"""Seed Supabase `exercises` table from data/knowledge/exercise_library.json.

Upsert-only (D12): adds new rows, updates changed rows, never deletes. Idempotent.
Run automatically by pre-commit hook when exercise_library.json is staged.
On Supabase connection failure: logs a warning and exits 0 (D11 — warn + proceed).

Manual invocation:
    cd pitcher_program_app && python -m scripts.seed_exercises_from_json
"""

import json
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("seed_exercises")

REPO_ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = REPO_ROOT / "data" / "knowledge" / "exercise_library.json"


def main() -> int:
    if not JSON_PATH.exists():
        logger.warning("No exercise_library.json at %s — nothing to seed", JSON_PATH)
        return 0

    with JSON_PATH.open() as f:
        data = json.load(f)

    exercises = data.get("exercises", data) if isinstance(data, dict) else data
    if not isinstance(exercises, list):
        logger.warning("exercise_library.json: unexpected shape, aborting seed")
        return 0

    try:
        # Ensure repo root is on sys.path so bot.services imports resolve
        sys.path.insert(0, str(REPO_ROOT))
        from bot.services.db import get_client
    except Exception as e:
        logger.warning("Could not import db client (Supabase creds missing?): %s", e)
        return 0  # D11: warn + proceed

    try:
        client = get_client()
    except Exception as e:
        logger.warning("Supabase client unavailable (creds missing?) — skipping seed (D11): %s", e)
        return 0
    if not client:
        logger.warning("Supabase client unavailable — skipping seed (D11)")
        return 0

    upserted = 0
    try:
        # Upsert in batches of 50 to avoid payload size surprises
        for i in range(0, len(exercises), 50):
            batch = exercises[i : i + 50]
            client.table("exercises").upsert(batch, on_conflict="id").execute()
            upserted += len(batch)
    except Exception as e:
        logger.warning("Seed failed mid-upsert after %d rows: %s", upserted, e)
        return 0  # warn + proceed

    logger.info("Seeded %d exercises (upsert, no deletes per D12)", upserted)
    return 0


if __name__ == "__main__":
    sys.exit(main())
