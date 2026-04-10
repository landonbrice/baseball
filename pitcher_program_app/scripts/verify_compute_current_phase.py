#!/usr/bin/env python3
"""Verification: compute_current_phase against fixed dates.

Prints PASS/FAIL for each case. Exits non-zero if any fail.
Run: python -m scripts.verify_compute_current_phase
"""

import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.services.programs import compute_current_phase


IN_SEASON_PROGRAM = {
    "start_date": "2026-02-15",
    "phases_snapshot": [
        {
            "phase_id": "in_season_main",
            "name": "Maintenance",
            "phase_type": "in_season",
            "week_count": 12,
            "default_training_intent": None,
            "microcycle": None,
        }
    ],
}

RTT_PROGRAM = {
    "start_date": "2026-04-01",
    "phases_snapshot": [
        {"phase_id": "rtt_acclimation", "name": "Acclimation", "phase_type": "return_to_throwing", "week_count": 2, "default_training_intent": "endurance", "microcycle": None},
        {"phase_id": "rtt_build", "name": "Build", "phase_type": "return_to_throwing", "week_count": 2, "default_training_intent": "hypertrophy", "microcycle": None},
        {"phase_id": "rtt_intent", "name": "Intent", "phase_type": "return_to_throwing", "week_count": 2, "default_training_intent": "strength", "microcycle": None},
    ],
}

CASES = [
    # (label, program, as_of, expected_phase_id, expected_week_in_phase, expected_week_in_program, expected_intent)
    ("In-season week 1 (start day)",       IN_SEASON_PROGRAM, date(2026, 2, 15), "in_season_main", 1, 1, None),
    ("In-season week 6",                   IN_SEASON_PROGRAM, date(2026, 3, 22), "in_season_main", 6, 6, None),
    ("In-season past end (week 13)",       IN_SEASON_PROGRAM, date(2026, 5, 10), "in_season_main", 12, 12, None),
    ("In-season before start",             IN_SEASON_PROGRAM, date(2026, 2, 1),  "in_season_main", 1, 1, None),
    ("RTT week 1 (acclimation start)",     RTT_PROGRAM,       date(2026, 4, 1),  "rtt_acclimation", 1, 1, "endurance"),
    ("RTT week 2 (acclimation end)",       RTT_PROGRAM,       date(2026, 4, 7),  "rtt_acclimation", 2, 2, "endurance"),
    ("RTT week 3 (build start)",           RTT_PROGRAM,       date(2026, 4, 15), "rtt_build", 1, 3, "hypertrophy"),
    ("RTT week 5 (intent start)",          RTT_PROGRAM,       date(2026, 4, 29), "rtt_intent", 1, 5, "strength"),
    ("RTT past end",                       RTT_PROGRAM,       date(2026, 6, 1),  "rtt_intent", 2, 6, "strength"),
]


def main() -> int:
    fails = 0
    for label, program, as_of, exp_pid, exp_wip, exp_wprog, exp_intent in CASES:
        result = compute_current_phase(program, as_of=as_of)
        ok = (
            result["phase_id"] == exp_pid
            and result["week_in_phase"] == exp_wip
            and result["week_in_program"] == exp_wprog
            and result["training_intent"] == exp_intent
        )
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {label}: got phase={result['phase_id']} wip={result['week_in_phase']} wprog={result['week_in_program']} intent={result['training_intent']}")
        if not ok:
            print(f"           expected phase={exp_pid} wip={exp_wip} wprog={exp_wprog} intent={exp_intent}")
            fails += 1

    print(f"\n{len(CASES) - fails}/{len(CASES)} cases passed")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
