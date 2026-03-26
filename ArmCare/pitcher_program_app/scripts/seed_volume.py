"""Seed a persistent volume with pitcher data from the repo.

Called at startup. If the volume directory is empty (first deploy after
attaching the volume), copies all pitcher data from the repo's bundled
seed files. If the volume already has data, does nothing — the volume
is the source of truth.

This means:
- First deploy with volume: repo data seeds the volume
- Subsequent deploys: volume data persists, repo seed files are ignored
- To update a pitcher's seed data, you must do it on the volume (via
  the bot, API, or Railway shell), not by committing to the repo
"""

import json
import logging
import os
import shutil

logger = logging.getLogger(__name__)

# The repo bundles seed data here (baked into the Docker image)
REPO_SEED_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "pitchers"
)

# The volume mount point (set via PITCHERS_DIR env var or default)
# When a Railway volume is mounted at /app/pitcher_program_app/data/pitchers,
# this is where the persistent data lives.
VOLUME_DIR = os.environ.get(
    "PITCHERS_VOLUME_DIR",
    REPO_SEED_DIR,  # Falls back to repo dir if no volume configured
)


def seed_if_empty() -> None:
    """Copy repo seed data into the volume if it's empty or missing."""
    # If volume dir == repo dir, no volume is configured — nothing to do
    if os.path.realpath(VOLUME_DIR) == os.path.realpath(REPO_SEED_DIR):
        logger.info("No separate volume configured — using repo data directory")
        return

    os.makedirs(VOLUME_DIR, exist_ok=True)

    # Check if volume already has pitcher directories
    existing = [
        d for d in os.listdir(VOLUME_DIR)
        if os.path.isdir(os.path.join(VOLUME_DIR, d))
        and not d.startswith("example_")
        and not d.startswith(".")
    ]

    if existing:
        logger.info(
            f"Volume already has {len(existing)} pitcher(s) — skipping seed"
        )
        return

    # Volume is empty — seed from repo
    if not os.path.exists(REPO_SEED_DIR):
        logger.warning(f"Repo seed dir not found: {REPO_SEED_DIR}")
        return

    count = 0
    for entry in os.listdir(REPO_SEED_DIR):
        src = os.path.join(REPO_SEED_DIR, entry)
        dst = os.path.join(VOLUME_DIR, entry)
        if os.path.isdir(src) and not entry.startswith("example_"):
            shutil.copytree(src, dst, dirs_exist_ok=True)
            count += 1
        elif os.path.isfile(src):
            shutil.copy2(src, dst)

    logger.info(f"Seeded volume with {count} pitcher(s) from repo")
