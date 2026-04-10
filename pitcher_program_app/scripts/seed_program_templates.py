#!/usr/bin/env python3
"""Seed program_templates from data/program_templates/*.json.

Idempotent — safe to re-run. Uses upsert on id.
Run: python -m scripts.seed_program_templates
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.services import db


TEMPLATES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "program_templates",
)


def main() -> int:
    if not os.path.isdir(TEMPLATES_DIR):
        print(f"ERROR: templates dir not found: {TEMPLATES_DIR}")
        return 1

    files = sorted(f for f in os.listdir(TEMPLATES_DIR) if f.endswith(".json"))
    if not files:
        print(f"ERROR: no .json files in {TEMPLATES_DIR}")
        return 1

    for fname in files:
        path = os.path.join(TEMPLATES_DIR, fname)
        with open(path) as fp:
            template = json.load(fp)
        required = {"id", "name", "role", "phase_type", "rotation_length", "phases"}
        missing = required - set(template.keys())
        if missing:
            print(f"  [SKIP] {fname}: missing fields {missing}")
            continue
        db.upsert_program_template(template)
        print(f"  [OK]   upserted {template['id']} ({template['name']})")

    print(f"\nSeeded {len(files)} templates from {TEMPLATES_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
