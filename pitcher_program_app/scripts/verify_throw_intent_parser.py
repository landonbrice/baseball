#!/usr/bin/env python3
"""Verification: throw intent parser against a corpus of real-ish messages."""

import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.services.throw_intent_parser import parse_throw_intent

# Reference today: Wednesday April 8 2026
TODAY = date(2026, 4, 8)

CASES = [
    # (message, expected dict or None)
    ("I'm throwing a bullpen Thursday",          {"date": "2026-04-09", "type": "bullpen"}),
    ("got a side session tomorrow",              {"date": "2026-04-09", "type": "side"}),
    ("planning long toss Friday",                {"date": "2026-04-10", "type": "long_toss"}),
    ("gonna throw a pen tmrw",                   {"date": "2026-04-09", "type": "bullpen"}),
    ("have a bullpen scheduled for Sat",         {"date": "2026-04-11", "type": "bullpen"}),
    ("doing my side work today",                 {"date": "2026-04-08", "type": "side"}),
    # Should NOT trigger
    ("I threw a bullpen yesterday",              None),  # past tense
    ("how's your bullpen looking",               None),  # no intent verb
    ("my arm feels good",                        None),  # no throw keyword
    ("had a side yesterday, arm sore",           None),  # past tense
    ("",                                          None),
]


def main() -> int:
    fails = 0
    for msg, expected in CASES:
        result = parse_throw_intent(msg, TODAY)
        if expected is None:
            ok = result is None
        else:
            ok = (
                result is not None
                and result["date"] == expected["date"]
                and result["type"] == expected["type"]
            )
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {msg!r:60} → {result}")
        if not ok:
            fails += 1
    print(f"\n{len(CASES) - fails}/{len(CASES)} cases passed")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
