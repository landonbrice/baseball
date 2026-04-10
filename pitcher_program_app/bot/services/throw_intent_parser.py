"""Detect throwing intent in chat messages.

Regex-only in v1 — high precision, modest recall. Returns None when ambiguous.
False-positives are recoverable via the bot's confirmation reply ("Got it —
bullpen Thursday added. Wrong? Tell me 'cancel'").
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Optional

THROW_TYPE_PATTERNS = {
    "bullpen": re.compile(r"\b(bullpen|bull\s*pen|pen)\b", re.IGNORECASE),
    "side":    re.compile(r"\b(side|side\s*work|side\s*session)\b", re.IGNORECASE),
    "long_toss": re.compile(r"\b(long\s*toss|long-toss|longtoss)\b", re.IGNORECASE),
    "catch":   re.compile(r"\b(play\s*catch|catch\s*play|just\s*catch)\b", re.IGNORECASE),
}

DAY_NAMES = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3, "thurs": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}

RELATIVE_DAYS = {
    "today": 0,
    "tomorrow": 1,
    "tmrw": 1,
    "tmw": 1,
}

INTENT_VERBS = re.compile(
    r"\b("
    r"throwing|throw|gonna throw|going to throw|"
    r"have a|got a|got my|i\s*'?\s*ve got|i have|"
    r"planning|planned|scheduled|set up|setting up|"
    r"doing|do my"
    r")\b",
    re.IGNORECASE,
)


def parse_throw_intent(message: str, today: date) -> Optional[dict]:
    """Detect throwing intent. Returns {date, type, notes} or None.

    `today` is the reference date for relative day resolution.
    """
    if not message:
        return None

    # Must have at least one throw-type keyword
    throw_type = None
    for ttype, pattern in THROW_TYPE_PATTERNS.items():
        if pattern.search(message):
            throw_type = ttype
            break
    if throw_type is None:
        return None

    # Must have at least one intent verb (filters out "I threw a bullpen yesterday")
    if not INTENT_VERBS.search(message):
        return None

    # Filter out past tense
    past_tense = re.compile(r"\b(threw|thrown|did|was|were|had)\b", re.IGNORECASE)
    if past_tense.search(message):
        return None

    # Resolve date
    target_date = _resolve_date(message, today)
    if target_date is None:
        return None

    return {
        "date": target_date.isoformat(),
        "type": throw_type,
        "notes": None,
    }


def _resolve_date(message: str, today: date) -> Optional[date]:
    msg = message.lower()

    for keyword, offset in RELATIVE_DAYS.items():
        if re.search(rf"\b{keyword}\b", msg):
            return today + timedelta(days=offset)

    for name, weekday in DAY_NAMES.items():
        if re.search(rf"\b{name}\b", msg):
            days_ahead = (weekday - today.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7  # "throwing Wednesday" said on a Wednesday → next Wednesday
            return today + timedelta(days=days_ahead)

    return None
