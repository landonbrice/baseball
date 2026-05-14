"""Golden-snapshot lockdown for the legacy plan_generator python-fallback branch.

For each fixture in tests/fixtures/legacy_plan_generator/data/<case>.json,
re-run plan_generator.generate_plan with the same mocks + frozen time used
to capture the golden, and assert byte-exact JSON equality.

If you intentionally change the python-fallback output, regenerate goldens:

    cd pitcher_program_app && PYTHONPATH=. python -m scripts.capture_plan_generator_goldens
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from freezegun import freeze_time

from bot.services import plan_generator
from tests.fixtures.legacy_plan_generator._mocks import apply_legacy_mocks


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "legacy_plan_generator" / "data"
GOLDENS_DIR = Path(__file__).parent / "fixtures" / "legacy_plan_generator" / "goldens"

_CASES = sorted(p.stem for p in FIXTURES_DIR.glob("*.json"))


@pytest.mark.asyncio
@pytest.mark.parametrize("case_name", _CASES)
async def test_legacy_plan_generator_golden(case_name: str) -> None:
    fixture = json.loads((FIXTURES_DIR / f"{case_name}.json").read_text())
    expected = json.loads((GOLDENS_DIR / f"{case_name}.json").read_text())

    with apply_legacy_mocks(fixture, seed=fixture.get("random_seed", 0)), \
            freeze_time(fixture["frozen_time"]):
        actual = await plan_generator.generate_plan(
            fixture["pitcher_id"],
            fixture["triage_result"],
            fixture.get("checkin_inputs") or {},
        )

    # Normalize through json.dumps so default=str matches the capture script.
    actual_serialized = json.loads(json.dumps(actual, sort_keys=True, default=str))
    assert actual_serialized == expected, (
        f"Golden drift for case={case_name}.  "
        "Re-run scripts.capture_plan_generator_goldens if the change is intentional."
    )
