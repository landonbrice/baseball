"""Layer 4 of the Program Builder funnel: program lifecycle.

State machine:
  draft  → active   (confirm-then-archive existing active in same (pitcher, domain) slot)
  draft  → archived
  active → archived

The partial unique index `idx_programs_one_active_per_domain` enforces "one active
per (pitcher, domain)" at the DB level — this layer just sequences the swap.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional


def _get_program(program_id: str) -> Optional[dict]:
    from bot.services import db
    return db.get_program(program_id)


def _get_active_program_in_domain(pitcher_id: str, domain: str) -> Optional[dict]:
    from bot.services import db
    return db.get_active_program(pitcher_id, domain)


def _update_status(program_id: str, status: str, **extras) -> None:
    from bot.services import db
    db.update_program_status(program_id, status, **extras)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def activate(program_id: str, archive_reason: str = "superseded") -> dict:
    """Transition a program to status='active', archiving any existing active in the same domain."""
    program = _get_program(program_id)
    if not program:
        raise LookupError(f"program not found: {program_id}")

    if program["status"] == "archived":
        raise ValueError(f"cannot activate an archived program: {program_id}")

    if program["status"] == "active":
        return {"activated": program_id, "archived": None, "already_active": True}

    existing = _get_active_program_in_domain(program["pitcher_id"], program["domain"])
    archived_id = None
    if existing and existing["program_id"] != program_id:
        _update_status(existing["program_id"], "archived",
                       archived_at=_now_iso(), archive_reason=archive_reason)
        archived_id = existing["program_id"]

    _update_status(program_id, "active", activated_at=_now_iso())
    return {"activated": program_id, "archived": archived_id}


def archive(program_id: str, reason: str) -> dict:
    """Archive a draft or active program. Idempotent on already-archived."""
    program = _get_program(program_id)
    if not program:
        raise LookupError(f"program not found: {program_id}")
    if program["status"] == "archived":
        return {"archived": program_id, "already_archived": True}
    _update_status(program_id, "archived",
                   archived_at=_now_iso(), archive_reason=reason)
    return {"archived": program_id}
