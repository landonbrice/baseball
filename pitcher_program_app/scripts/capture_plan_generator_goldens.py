"""Capture golden snapshots for the legacy plan_generator python-fallback branch.

Run from repo root:

    cd pitcher_program_app && PYTHONPATH=. python -m scripts.capture_plan_generator_goldens

For each fixture under tests/fixtures/legacy_plan_generator/data/<case>.json,
this script:
  - applies the shared mock stack (data layer + LLM helpers raising TimeoutError)
  - freeze_time to fixture.frozen_time
  - awaits plan_generator.generate_plan(pitcher_id, triage_result, checkin_inputs)
  - writes the result to tests/fixtures/legacy_plan_generator/goldens/<case>.json
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from freezegun import freeze_time

# Make sure pitcher_program_app/ is on sys.path even when invoked from repo root.
HERE = Path(__file__).resolve().parent
APP_ROOT = HERE.parent
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from bot.services import plan_generator  # noqa: E402
from tests.fixtures.legacy_plan_generator._mocks import apply_legacy_mocks  # noqa: E402


FIXTURES_DIR = APP_ROOT / "tests" / "fixtures" / "legacy_plan_generator" / "data"
GOLDENS_DIR = APP_ROOT / "tests" / "fixtures" / "legacy_plan_generator" / "goldens"


async def _capture_one(fixture_path: Path) -> tuple[str, dict | None, str | None]:
    fixture = json.loads(fixture_path.read_text())
    case_name = fixture["case_name"]
    frozen = fixture["frozen_time"]
    pitcher_id = fixture["pitcher_id"]
    triage_result = fixture["triage_result"]
    checkin_inputs = fixture.get("checkin_inputs") or {}
    seed = fixture.get("random_seed", 0)

    try:
        with apply_legacy_mocks(fixture, seed=seed), freeze_time(frozen):
            result = await plan_generator.generate_plan(
                pitcher_id, triage_result, checkin_inputs
            )
        return case_name, result, None
    except Exception as e:  # noqa: BLE001
        import traceback
        return case_name, None, traceback.format_exc()


async def main() -> int:
    GOLDENS_DIR.mkdir(parents=True, exist_ok=True)
    fixtures = sorted(FIXTURES_DIR.glob("*.json"))
    if not fixtures:
        print(f"No fixtures found in {FIXTURES_DIR}")
        return 1

    failures = 0
    for fp in fixtures:
        case_name, result, err = await _capture_one(fp)
        if err:
            print(f"[FAIL] {case_name}\n{err}")
            failures += 1
            continue
        out = GOLDENS_DIR / f"{case_name}.json"
        out.write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")
        print(f"[OK]   {case_name} -> {out.relative_to(APP_ROOT)}")

    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
