"""Shared day_focus derivation.

Phase 1 / Spec 2 left day_focus computed at read time in team_scope.py. F4 moves
the write into plan_generator.py so rationale composition can read a persisted
value. Legacy rows fall back through this same helper.
"""
from typing import Iterable


_RECOVERY_TAGS = frozenset({"rest_day", "no_throw", "no_lifting", "no_throwing"})


def _tag_of(m) -> str:
    if isinstance(m, dict):
        return m.get("tag", "") or ""
    return m or ""


def derive_day_focus(plan: dict, modifications: Iterable) -> str | None:
    """Return 'bullpen' | 'throw' | 'lift' | 'recovery' | None.

    Priority:
      1. Explicit plan['day_focus'] (persisted write)
      2. plan['bullpen'] truthy → bullpen
      3. plan['throwing_plan'] truthy → throw
      4. plan['lifting'] truthy → lift
      5. modifications contain recovery-like tag → recovery
      6. None
    """
    if not isinstance(plan, dict):
        return None
    if plan.get("day_focus"):
        return plan["day_focus"]
    if plan.get("bullpen"):
        return "bullpen"
    if plan.get("throwing_plan"):
        return "throw"
    if plan.get("lifting"):
        return "lift"
    tags = {_tag_of(m) for m in (modifications or [])}
    if tags & _RECOVERY_TAGS:
        return "recovery"
    return None
