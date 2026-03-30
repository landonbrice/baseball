"""Validate that all exercise IDs in template files exist in the Supabase exercises table.

Usage: python -m scripts.validate_templates
Exit code 0 = all valid, 1 = mismatches found.
"""

import json
import os
import sys
import glob

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()


def extract_exercise_ids(data, path=""):
    """Recursively extract all exercise_id values from a nested structure."""
    ids = []
    if isinstance(data, dict):
        if "exercise_id" in data:
            ids.append((data["exercise_id"], path))
        for k, v in data.items():
            ids.extend(extract_exercise_ids(v, f"{path}.{k}"))
    elif isinstance(data, list):
        for i, item in enumerate(data):
            ids.extend(extract_exercise_ids(item, f"{path}[{i}]"))
    return ids


def main():
    from bot.services.db import get_exercises

    templates_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "templates")
    template_files = glob.glob(os.path.join(templates_dir, "*.json"))

    # Load valid IDs from Supabase
    valid_ids = {e["id"] for e in get_exercises()}
    print(f"Exercise library: {len(valid_ids)} exercises")

    # Scan all templates
    all_ids = []
    for filepath in sorted(template_files):
        filename = os.path.basename(filepath)
        with open(filepath) as f:
            data = json.load(f)
        ids = extract_exercise_ids(data)
        all_ids.extend([(eid, filename, path) for eid, path in ids])

    unique_ids = {eid for eid, _, _ in all_ids}
    missing = unique_ids - valid_ids
    print(f"Template exercise IDs: {len(unique_ids)} unique across {len(template_files)} files")

    if missing:
        print(f"\n{len(missing)} MISSING exercise IDs:")
        for eid, filename, path in all_ids:
            if eid in missing:
                print(f"  {eid} — {filename} at {path}")
        sys.exit(1)
    else:
        print("All template exercise IDs exist in the library.")
        sys.exit(0)


if __name__ == "__main__":
    main()
