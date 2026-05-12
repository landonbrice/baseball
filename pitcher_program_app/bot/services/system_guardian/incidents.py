"""Incident upsert + status transitions per spec §8 / amendments A6.

The incident table is signature-keyed. The first time a signature is seen we
INSERT a fresh row with ``status=open``, ``count=1``, and the observation's
severity. Each subsequent occurrence increments ``count``, advances
``last_seen``, and escalates ``severity`` if the new observation outranks
what's stored.

Notification policy (A6) is enforced by which fields advance ``last_notified_at``:

* status change          → advance
* severity escalation    → advance
* count increment alone  → DOES NOT advance

The actual notification dispatch lives in PR-5 (notify.py); this module only
maintains the timestamps the dispatcher reads.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Iterable

from bot.config import CHICAGO_TZ
from bot.services.system_guardian.classify import (
    SEVERITY_RANK,
    max_severity,
    severity_at_least,
)

logger = logging.getLogger(__name__)

# Legal status transitions for ``transition_status``. Re-opens are allowed
# for the case where an incident was closed too early and the underlying
# signal returned.
_LEGAL_TRANSITIONS: dict[str, set[str]] = {
    "open": {"ack", "resolved", "muted"},
    "ack": {"resolved", "open", "muted"},
    "resolved": {"open"},
    "muted": {"open"},
}


def _now_iso() -> str:
    return datetime.now(CHICAGO_TZ).isoformat()


def _title_from_observation(obs: dict) -> str:
    msg = (obs.get("message") or "").strip()
    if not msg:
        msg = (obs.get("event_type") or "incident").strip() or "incident"
    if len(msg) > 120:
        msg = msg[:117] + "..."
    return msg


def build_incident_payload(obs: dict) -> dict:
    """Construct the row payload for a NEW incident from an observation.

    Used by ``store.upsert_incident``. Kept here (not in store.py) so it can
    be tested without a Supabase client present.
    """
    severity = obs.get("severity") or obs.get("severity_hint") or "info"
    if severity not in SEVERITY_RANK:
        severity = "info"
    category = obs.get("category") or "runtime_error"
    now = obs.get("observed_at") or _now_iso()

    services = obs.get("affected_services") or ([obs["service"]] if obs.get("service") else [])
    surfaces = obs.get("affected_surfaces") or ([obs["surface"]] if obs.get("surface") else [])

    sample_message = obs.get("message") or ""
    sample = [{"observed_at": now, "message": sample_message}] if sample_message else []

    return {
        "signature": obs["signature"],
        "title": _title_from_observation(obs),
        "status": "open",
        "severity": severity,
        "category": category,
        "first_seen": now,
        "last_seen": now,
        "count": 1,
        "affected_services": [s for s in services if s],
        "affected_surfaces": [s for s in surfaces if s],
        "affected_entities": obs.get("affected_entities") or {},
        "sample_messages": sample,
        "suspected_files": obs.get("suspected_files") or [],
        "debug_packet": obs.get("debug_packet") or {},
        "vision_flags": obs.get("vision_flags") or [],
        "last_notified_at": None,
    }


def merge_observation_into_incident(existing: dict, obs: dict) -> dict:
    """Compute the row payload for an UPDATE when ``signature`` already exists.

    Returns a partial dict suitable for an UPDATE. Per A6:

    * ``count`` advances by 1.
    * ``last_seen`` advances to the observation's timestamp.
    * ``severity`` escalates only when the observation severity outranks the
      stored severity. ``last_notified_at`` advances on escalation.
    * Sample messages list is appended, capped at 5 to keep the JSONB column
      small and readable in the digest.
    """
    obs_severity = obs.get("severity") or obs.get("severity_hint") or "info"
    if obs_severity not in SEVERITY_RANK:
        obs_severity = "info"
    stored_severity = existing.get("severity") or "info"
    new_severity = max_severity(stored_severity, obs_severity)
    severity_escalated = new_severity != stored_severity

    now = obs.get("observed_at") or _now_iso()
    samples: list[Any] = list(existing.get("sample_messages") or [])
    msg = obs.get("message")
    if msg:
        samples.append({"observed_at": now, "message": msg})
        if len(samples) > 5:
            samples = samples[-5:]

    services = set(existing.get("affected_services") or [])
    if obs.get("service"):
        services.add(obs["service"])
    for s in obs.get("affected_services") or []:
        if s:
            services.add(s)

    surfaces = set(existing.get("affected_surfaces") or [])
    if obs.get("surface"):
        surfaces.add(obs["surface"])
    for s in obs.get("affected_surfaces") or []:
        if s:
            surfaces.add(s)

    payload: dict[str, Any] = {
        "count": int(existing.get("count") or 1) + 1,
        "last_seen": now,
        "severity": new_severity,
        "sample_messages": samples,
        "affected_services": sorted(services),
        "affected_surfaces": sorted(surfaces),
    }
    if severity_escalated:
        payload["last_notified_at"] = now
    return payload


def validate_status_transition(current: str, new: str) -> None:
    """Raise ``ValueError`` if ``current → new`` is not in the allow-list."""
    legal = _LEGAL_TRANSITIONS.get(current, set())
    if new == current:
        # No-op transitions are tolerated — caller probably re-acked.
        return
    if new not in legal:
        raise ValueError(
            f"Illegal incident status transition: {current!r} → {new!r}"
        )


__all__ = [
    "build_incident_payload",
    "merge_observation_into_incident",
    "validate_status_transition",
]
