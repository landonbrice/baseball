"""Scan xlsx files in past_arm_programs/ for YouTube hyperlinks and match them
to exercises in exercise_library.json.  Writes updated library + unmatched CSV.

Usage:
    python -m scripts.populate_youtube_links          # dry-run (prints matches)
    python -m scripts.populate_youtube_links --write   # writes exercise_library.json
"""

import argparse
import csv
import json
import os
import re
import sys

import openpyxl
from thefuzz import fuzz

XLSX_DIR = os.path.join(os.path.dirname(__file__), "..", "past_arm_programs")
LIBRARY_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "knowledge", "exercise_library.json")
UNMATCHED_CSV = os.path.join(os.path.dirname(__file__), "unmatched_youtube.csv")

# ── helpers ──────────────────────────────────────────────────────────────

def _normalize(name: str) -> str:
    """Lower-case, strip whitespace / punctuation for comparison."""
    return re.sub(r"[^a-z0-9 ]", "", name.lower()).strip()


def _extract_youtube_links(xlsx_dir: str) -> list[tuple[str, str, str]]:
    """Return list of (cell_text, youtube_url, source_file) from all xlsx files."""
    links = []
    for fname in sorted(os.listdir(xlsx_dir)):
        if fname.startswith("~") or not fname.endswith(".xlsx"):
            continue
        path = os.path.join(xlsx_dir, fname)
        try:
            wb = openpyxl.load_workbook(path)
        except Exception:
            continue
        for ws in wb.worksheets:
            for row in ws.iter_rows():
                for cell in row:
                    if cell.hyperlink and cell.hyperlink.target and "youtu" in cell.hyperlink.target:
                        text = str(cell.value or "").strip()
                        if text:
                            links.append((text, cell.hyperlink.target, fname))
    return links


def _build_lookup(exercises: list[dict]) -> dict:
    """Build a dict mapping normalized names/aliases → exercise dict."""
    lookup = {}
    for ex in exercises:
        lookup[_normalize(ex["name"])] = ex
        for alias in ex.get("aliases", []):
            lookup[_normalize(alias)] = ex
    return lookup


def _match_exercise(cell_text: str, lookup: dict, exercises: list[dict]) -> dict | None:
    """Try to match a cell text to an exercise.  Returns exercise dict or None."""
    norm = _normalize(cell_text)
    if not norm:
        return None

    # 1. Exact match on name or alias
    if norm in lookup:
        return lookup[norm]

    # 2. Containment — only if both sides are long enough to be meaningful
    if len(norm) >= 8:
        for key, ex in lookup.items():
            if len(key) >= 8 and (norm in key or key in norm):
                return ex

    # 3. Fuzzy match (token_set_ratio handles word-order differences)
    #    Require high score to avoid false positives on short names
    best_score, best_ex = 0, None
    for ex in exercises:
        candidates = [ex["name"]] + ex.get("aliases", [])
        for c in candidates:
            score = fuzz.token_set_ratio(norm, _normalize(c))
            if score > best_score:
                best_score = score
                best_ex = ex
    if best_score >= 80:
        return best_ex

    return None

# ── main ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="Write updated exercise_library.json")
    args = parser.parse_args()

    with open(LIBRARY_PATH) as f:
        library = json.load(f)
    exercises = library["exercises"]
    lookup = _build_lookup(exercises)

    raw_links = _extract_youtube_links(os.path.abspath(XLSX_DIR))
    # Deduplicate by (normalized_text, url)
    seen = set()
    links = []
    for text, url, src in raw_links:
        key = (_normalize(text), url)
        if key not in seen:
            seen.add(key)
            links.append((text, url, src))

    print(f"Found {len(links)} unique YouTube links across xlsx files.\n")

    matched, unmatched = [], []
    # Track which exercise got which URL (first wins for each exercise)
    assigned: dict[str, str] = {}

    for text, url, src in links:
        ex = _match_exercise(text, lookup, exercises)
        if ex:
            eid = ex["id"]
            if eid not in assigned:
                assigned[eid] = url
                matched.append((text, url, ex["name"], eid, src))
            # else: skip duplicate match for same exercise
        else:
            unmatched.append((text, url, src))

    print(f"Matched: {len(matched)}  |  Unmatched: {len(unmatched)}\n")

    print("── Matches ──")
    for text, url, name, eid, src in matched:
        print(f"  {eid} {name} ← \"{text}\" [{src}]")

    if unmatched:
        print(f"\n── Unmatched ({len(unmatched)}) ──")
        for text, url, src in unmatched:
            print(f"  \"{text}\" → {url}  [{src}]")

    if args.write:
        # Apply matches
        ex_by_id = {ex["id"]: ex for ex in exercises}
        updated = 0
        for _, url, _, eid, _ in matched:
            ex = ex_by_id[eid]
            if not ex.get("youtube_url"):
                ex["youtube_url"] = url
                updated += 1

        with open(LIBRARY_PATH, "w") as f:
            json.dump(library, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"\nWrote {updated} new YouTube URLs to exercise_library.json")

        # Write unmatched CSV
        if unmatched:
            with open(UNMATCHED_CSV, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["cell_text", "youtube_url", "source_file"])
                for text, url, src in unmatched:
                    w.writerow([text, url, src])
            print(f"Wrote {len(unmatched)} unmatched links to {UNMATCHED_CSV}")
    else:
        print("\nDry run — pass --write to update exercise_library.json")


if __name__ == "__main__":
    main()
