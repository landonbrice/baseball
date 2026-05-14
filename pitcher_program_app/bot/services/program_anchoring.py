"""Scheduled-throw anchoring (spec Section 3, Plan 5).

Templates can declare two day-shape modes:
  - calendar-relative: day N = start_date + N (fixed offset; recompute is no-op)
  - anchor-relative:   day N = N days before/after the next future scheduled throw
                       (re-positions when a throw is added/moved/deleted)

This module exposes one public function:

    recompute_program_schedule(program, scheduled_throws) -> generated_schedule_json

Past days (day_index < program.current_day_index) are frozen verbatim and
copied through unchanged. Future days are re-anchored (anchor-relative)
or pass through (calendar-relative).

Day-level anchor declaration (v1):
    {
        "day_index": int,
        "template_key": str,
        "date": "YYYY-MM-DD",          # original calendar-relative date
        "anchor_kind": str | None,     # e.g. "T-3_from_next_bullpen", "bullpen_day"
    }

Supported `anchor_kind` values today:
    "T-N_from_next_<kind>"   — N days before the next scheduled throw of <kind>
    "<kind>_day"             — the throw itself; re-positioned to the next future throw of <kind>

Caller is responsible for persisting via `db.update_program_schedule` and
for any audit logging beyond the `program_schedule_revisions` row that
helper writes.

UI integration (calling this from WeekArc.onAddThrow, conflict prompts,
override-event logging) defers to Plan 6.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Optional

# Calendar-relative scaffolds — recompute is a no-op for these.
_CALENDAR_RELATIVE_KINDS = {
    "calendar_relative_repeating_7day",
    "calendar_relative",
}

_ANCHOR_RE = re.compile(r"^T-(\d+)_from_next_(.+)$")


def _parse_anchor_kind(anchor_kind: Optional[str]) -> Optional[tuple[str, int, str]]:
    """Return (mode, offset_days, throw_kind) or None.

    mode is "before" for "T-N_from_next_<kind>" or "exact" for "<kind>_day".
    """
    if not anchor_kind:
        return None
    m = _ANCHOR_RE.match(anchor_kind)
    if m:
        return ("before", int(m.group(1)), m.group(2))
    if anchor_kind.endswith("_day"):
        return ("exact", 0, anchor_kind[: -len("_day")])
    return None


def _next_throw_on_or_after(
    scheduled_throws: list[dict], target_kind: str, on_or_after: date
) -> Optional[date]:
    """Return the date of the next scheduled throw of `target_kind` >= on_or_after, or None.

    Assumes `scheduled_throws` is sorted ascending by date but does not require it.
    """
    candidates = []
    for t in scheduled_throws or []:
        kind = t.get("kind")
        d_str = t.get("date")
        if not kind or not d_str:
            continue
        if kind != target_kind:
            continue
        try:
            d = date.fromisoformat(d_str)
        except (ValueError, TypeError):
            continue
        if d >= on_or_after:
            candidates.append(d)
    return min(candidates) if candidates else None


def recompute_program_schedule(program: dict, scheduled_throws: list[dict]) -> dict:
    """Return a new generated_schedule_json with future days re-anchored.

    Past days (day_index < program.current_day_index) are frozen verbatim.
    Calendar-relative templates pass through unchanged.
    Anchor-relative days re-position around the next future scheduled_throw
    of the matching kind. If no matching future throw exists, the day's
    original calendar-relative `date` is preserved.

    `scheduled_throws` shape: [{date: "YYYY-MM-DD", kind: "bullpen"|"outing"|"long_toss"}].
    Order is not assumed — sorted internally as needed.

    Returns a new dict; the input is not mutated. Caller is responsible for
    persisting via `db.update_program_schedule(...)` AND for any additional
    audit beyond the `program_schedule_revisions` row that helper writes.
    """
    schedule = program.get("generated_schedule_json") or {}
    scaffold_kind = schedule.get("scaffold_kind")
    days = list(schedule.get("days") or [])
    current_day_index = int(program.get("current_day_index", 0) or 0)

    # Calendar-relative → no-op pass-through (still return the same dict shape).
    if scaffold_kind in _CALENDAR_RELATIVE_KINDS:
        return schedule

    # Anchor-relative path. Build a new day list; freeze past days verbatim.
    new_days: list[dict] = []
    # `today_floor` for "future throws only" is keyed off the date of the day at
    # current_day_index, so re-anchoring tracks the real calendar (spec: anchors
    # track real calendar — bullpens stay where they are; T-N days slide if the
    # pitcher is held).
    today_floor: Optional[date] = None
    for d in days:
        if d.get("day_index") == current_day_index and d.get("date"):
            try:
                today_floor = date.fromisoformat(d["date"])
            except (ValueError, TypeError):
                today_floor = None
            break

    for day in days:
        idx = int(day.get("day_index", -1))
        if idx < current_day_index:
            # Frozen — copy verbatim.
            new_days.append(dict(day))
            continue

        parsed = _parse_anchor_kind(day.get("anchor_kind"))
        if parsed is None:
            # No anchor declaration — leave as-is (treat as calendar-relative).
            new_days.append(dict(day))
            continue

        mode, offset_days, throw_kind = parsed
        # "Future" throws are those on or after today_floor (or the day's own date if floor unknown).
        floor = today_floor or (
            date.fromisoformat(day["date"]) if day.get("date") else date.today()
        )
        anchor_date = _next_throw_on_or_after(scheduled_throws, throw_kind, floor)

        new_day = dict(day)
        if anchor_date is None:
            # No future throw of this kind — fall back to original calendar date.
            new_days.append(new_day)
            continue

        if mode == "before":
            new_day["date"] = (anchor_date - timedelta(days=offset_days)).isoformat()
        else:  # "exact"
            new_day["date"] = anchor_date.isoformat()
        new_days.append(new_day)

    return {**schedule, "days": new_days}
