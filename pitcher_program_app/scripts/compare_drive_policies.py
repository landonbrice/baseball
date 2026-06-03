"""Phase 4.3 harness — compare the 3 candidate "drive" policies.

Per locked decision L7, v1 ships ≥3 policies + a comparison harness to
inform v2's policy choice. This script DOES NOT pick a policy.

For each scenario × policy combination it:
  1. Builds a sample 12-week velocity program via build_fallback_program.
  2. Walks the 10-day readiness sequence calling project() + regovern() on
     each day.
  3. Records metrics: final_goal_progress, total_load_delivered,
     weeks_disturbed, gate_outcomes.
  4. Emits a Markdown report at
     docs/superpowers/research/2026-06-01-drive-policy-comparison.md.

Exit 0 on success.
"""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path

# Make 'bot' importable when run with `python -m scripts.compare_drive_policies`.
_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from bot.services.program_engine.fallback import build_fallback_program  # noqa: E402
from bot.services.program_engine.governor import regovern  # noqa: E402
from bot.services.program_engine.load_math import daily_throwing_load  # noqa: E402
from bot.services.program_engine.projection import project  # noqa: E402

FIXTURE_PATH = _REPO / "tests" / "fixtures" / "drive_policy_fixtures.json"
REPORT_PATH = _REPO.parent / "docs" / "superpowers" / "research" / "2026-06-01-drive-policy-comparison.md"

POLICIES = ("silent_absorb", "immediate_repace", "banked_deviation")


def _velocity_block_for_demo() -> dict:
    """Minimal velocity_12wk_v1 block_library row shaped for build_fallback_program."""
    return {
        "block_template_id": "velocity_12wk_v1",
        "domain": "throwing",
        "goal_tags": ["velocity"],
        "research_doc_ids": ["velocity_progression_model"],
        "content": {
            "weeks": 12,
            "throws_per_week": 3,
            "phases": [
                {"name": "Base Building", "weeks": [1, 2, 3], "effort_pct": 50,
                 "distances": ["45ft", "60ft", "75ft"], "total_throws_range": [40, 60]},
                {"name": "Distance Extension", "weeks": [4, 5, 6], "effort_pct": 70,
                 "distances": ["75ft", "90ft", "105ft"], "total_throws_range": [50, 66]},
                {"name": "Compression+Pulldowns", "weeks": [7, 8, 9], "effort_pct": 80,
                 "distances": ["120ft"], "total_throws_range": [55, 70]},
                {"name": "Max Intent+Mound", "weeks": [10, 11, 12], "effort_pct": 90,
                 "distances": ["full_progression", "mound_work"], "total_throws_range": [60, 75]},
            ],
            "acwr_governor": {"deload_weeks_default": [4, 7]},
            "lifting_integration": {
                "phase_mapping": [
                    {"throwing_phase_weeks": [1, 2, 3], "lifting_phase": "hypertrophy"},
                    {"throwing_phase_weeks": [4, 5, 6], "lifting_phase": "hypertrophy_to_strength"},
                    {"throwing_phase_weeks": [7, 8, 9], "lifting_phase": "strength"},
                    {"throwing_phase_weeks": [10, 11, 12], "lifting_phase": "strength_power"},
                ],
            },
        },
    }


def _build_demo_program():
    return build_fallback_program(
        pitcher_id="landon_brice",
        goal_spec={"tags": ["velocity"]},
        block_library_row=_velocity_block_for_demo(),
        knowledge_version="harness_kv_12345678",
        target_date="2026-08-24",
    )


def _intended_total_g(program) -> float:
    """Sum of intended throwing G across the whole program."""
    return sum(
        daily_throwing_load(d.throwing_5tuple) if d.throwing_5tuple else 0.0
        for d in program.days
    )


def _gate_outcomes(program) -> dict:
    """Which phases STILL clear their effort_pct gates given delivered intents."""
    out = {}
    for phase in program.phases:
        # Find this phase's days. Phase order matches the wk_list ordering.
        phase_days = [d for d in program.days if d.phase_name == phase.name]
        if not phase_days:
            out[phase.name] = "no_days"
            continue
        max_intent = max((d.intent_pct or 0) for d in phase_days)
        out[phase.name] = f"max_intent={max_intent}"
    return out


def run_scenario(scenario: dict, policy: str, base_program) -> dict:
    """Walk the 10-day readiness sequence applying project+regovern."""
    program = deepcopy(base_program)
    total_delivered_g = 0.0
    weeks_touched: set[int] = set()
    banked = 0.0
    program_start = date.fromisoformat(program.days[0].date)

    for entry in scenario["readiness_sequence"]:
        day_offset = entry["day_offset"]
        d_date = program_start + timedelta(days=day_offset)
        readiness = dict(entry)
        readiness["banked_missed_g"] = banked

        try:
            projected = project(program, d_date, readiness, policy=policy)
        except ValueError:
            continue  # date out of program range — skip

        # Accumulate delivered G
        delivered_g = (
            daily_throwing_load(projected.delivered.throwing_5tuple)
            if projected.delivered.throwing_5tuple is not None
            else 0.0
        )
        total_delivered_g += delivered_g

        # Re-pace
        if projected.governor_signal:
            result = regovern(program, projected.governor_signal, policy, from_day_index=day_offset)
            program = result.program
            for change in result.changes:
                wk = change.get("week")
                if wk:
                    weeks_touched.add(wk)
            # Update banked tracker
            missed_today = projected.governor_signal.get("missed_g", 0.0)
            if policy == "banked_deviation":
                # Banked policy: only "small" deviations bank; medium/large flush via regovern.
                if projected.governor_signal.get("severity") == "small":
                    banked += missed_today
                else:
                    banked = 0.0
            else:
                # For immediate_repace, the bank doesn't accumulate (we always re-pace).
                banked = 0.0

    intended_total = _intended_total_g(base_program)
    delivered_in_window = sum(
        daily_throwing_load(d.throwing_5tuple) if d.throwing_5tuple else 0.0
        for d in base_program.days
        if 0 <= d.day_index < 10
    )
    intended_in_window = delivered_in_window  # before projection
    progress_fraction = (total_delivered_g / intended_in_window) if intended_in_window else 1.0

    return {
        "policy": policy,
        "scenario": scenario["name"],
        "total_delivered_g_10d": round(total_delivered_g, 1),
        "intended_g_10d": round(intended_in_window, 1),
        "progress_fraction_10d": round(progress_fraction, 3),
        "weeks_disturbed": sorted(weeks_touched),
        "gate_outcomes": _gate_outcomes(program),
    }


def render_report(rows: list[dict]) -> str:
    """Render the comparison Markdown."""
    lines = []
    lines.append("# Drive Policy Comparison — Phase 4.3 Harness Output")
    lines.append("")
    lines.append(f"_Generated 2026-06-01 by `pitcher_program_app/scripts/compare_drive_policies.py`. "
                 f"Source fixtures: `pitcher_program_app/tests/fixtures/drive_policy_fixtures.json`._")
    lines.append("")
    lines.append("## What this is")
    lines.append("")
    lines.append("Per locked decision **L7**, Program Engine v1 ships THREE candidate \"drive\" policies + this harness, but does NOT pick one. The harness exercises each policy against four readiness scenarios on a 12-week velocity program and records the metrics that the v2 decision will weigh.")
    lines.append("")
    lines.append("**Policies under test:**")
    lines.append("- `silent_absorb` — never re-paces; today's hit stays today's hit.")
    lines.append("- `immediate_repace` — every reduction emits a governor signal; remaining weeks adapt.")
    lines.append("- `banked_deviation` — small variance absorbs; structural deviation (cumulative or single-day >50%) triggers re-pacing.")
    lines.append("")
    lines.append("**Scenarios:**")
    lines.append("- `all_green` — perfect 10 days; no signals expected from any policy.")
    lines.append("- `mid_cycle_yellow` — days 3-5 YELLOW with low tissue, then recovery.")
    lines.append("- `late_phase_red` — days 7-9 RED with arm_feel=3 + active mod.")
    lines.append("- `repeated_low_tissue` — every day YELLOW with tissue=3.5 (chronic drift).")
    lines.append("")
    lines.append("**Metrics emitted:**")
    lines.append("- `progress_fraction_10d` — delivered throwing G / intended throwing G across the 10-day window. 1.00 = no compromise.")
    lines.append("- `weeks_disturbed` — list of program weeks the governor adjusted.")
    lines.append("- `gate_outcomes` — max intent reached per phase (after re-pacing). Tells you if the velocity gate cleared.")
    lines.append("")
    lines.append("## Comparison table")
    lines.append("")
    lines.append("| Scenario | Policy | progress_fraction_10d | weeks_disturbed | total_delivered_g_10d |")
    lines.append("|---|---|---|---|---|")
    for r in rows:
        lines.append(
            f"| `{r['scenario']}` | `{r['policy']}` | {r['progress_fraction_10d']:.3f} | "
            f"{r['weeks_disturbed'] or '—'} | {r['total_delivered_g_10d']:.0f} |"
        )
    lines.append("")
    lines.append("## Per-scenario gate outcomes")
    lines.append("")
    for scenario_name in ("all_green", "mid_cycle_yellow", "late_phase_red", "repeated_low_tissue"):
        lines.append(f"### `{scenario_name}`")
        lines.append("")
        lines.append("| Policy | Phase | max_intent |")
        lines.append("|---|---|---|")
        for r in rows:
            if r["scenario"] != scenario_name:
                continue
            for phase_name, outcome in r["gate_outcomes"].items():
                lines.append(f"| `{r['policy']}` | {phase_name} | {outcome} |")
        lines.append("")
    lines.append("## What this report DOES NOT do")
    lines.append("")
    lines.append("- Does not pick a policy. That decision is **explicitly deferred to v2** per L7.")
    lines.append("- Does not run on real pitcher check-in data — the readiness sequences are hand-crafted fixtures.")
    lines.append("- Does not account for lifting-side re-pacing. The throwing half is the primary driver in the velocity goal; lifting-side adjustments are a v2 concern.")
    lines.append("- Does not project forward beyond the 10-day window. Long-tail effects of `silent_absorb` (compounding deviation) require a longer-horizon harness — call that v2 work too.")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    fixtures = json.loads(FIXTURE_PATH.read_text())
    scenarios = fixtures["scenarios"]
    base_program = _build_demo_program()
    rows: list[dict] = []
    for scenario in scenarios:
        for policy in POLICIES:
            rows.append(run_scenario(scenario, policy, base_program))
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(render_report(rows))
    print(f"OK — wrote {REPORT_PATH}")
    print(f"     rows: {len(rows)} (4 scenarios × 3 policies)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
