"""Supabase CRUD against the three PR-1 tables.

This is the single boundary between the rest of the Guardian package and the
``system_observations`` / ``system_incidents`` / ``guardian_reviews`` tables.

Style follows ``bot/services/db.py``:

* Synchronous Supabase service-role client.
* Reuses ``bot.services.db.get_client()`` rather than holding its own
  connection.
* Defensive against query failures — every public function logs and either
  swallows or returns a sentinel rather than raising into the caller.

Only PR-2 functions are here. Notification dispatch (``notify.py``), admin
routes, and shakedown logic land in PR-5.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from bot.config import CHICAGO_TZ
from bot.services import db as _db
from bot.services.system_guardian.classify import (
    SEVERITY_RANK,
    classify_severity,
)
from bot.services.system_guardian.cluster import generate_signature
from bot.services.system_guardian.incidents import (
    build_incident_payload,
    merge_observation_into_incident,
    validate_status_transition,
)
from bot.services.system_guardian.normalize import normalize_observation

logger = logging.getLogger(__name__)


# Columns the storage layer is allowed to write into ``system_observations``.
# Mirrors migration 019 column list. We strip everything else from the
# normalized dict before insert so accidentally-added fields don't cause
# PostgREST 400s.
_OBSERVATION_COLUMNS = {
    "observed_at",
    "source",
    "service",
    "event_type",
    "severity_hint",
    "surface",
    "route_or_job",
    "message",
    "error_class",
    "stack_hash",
    "signature",
    "metadata",
}


def _now_iso() -> str:
    return datetime.now(CHICAGO_TZ).isoformat()


def _strip_to_columns(obs: dict) -> dict:
    return {k: v for k, v in obs.items() if k in _OBSERVATION_COLUMNS}


# ---------------------------------------------------------------------------
# Observations
# ---------------------------------------------------------------------------

def insert_observation(raw: dict) -> dict | None:
    """Normalize + write-time-redact + insert one observation.

    Returns the row dict on success, ``None`` on failure. Per A4, when the
    write-time redactor catches a secret pattern, this function ALSO inserts
    a paired ``category=security_posture severity=critical`` observation
    tagged with source/route/job (no secret content).

    Failure handling: a Supabase error here is logged but does not raise —
    Guardian must never crash its host (the Telegram bot process). Callers
    that need the row id must handle ``None``.
    """
    obs = normalize_observation(raw)
    redaction_hits: list[str] = obs.pop("_redaction_hits", []) or []
    write_payload = _strip_to_columns(obs)

    inserted_row = None
    try:
        client = _db.get_client()
        resp = client.table("system_observations").insert(write_payload).execute()
        if resp.data:
            inserted_row = resp.data[0]
    except Exception as e:
        logger.error("guardian: insert_observation failed: %s", e, exc_info=True)
        return None

    # Paired security_posture observation when redaction fired (A4).
    if redaction_hits:
        try:
            _emit_security_posture_observation(
                source=raw.get("source"),
                route_or_job=raw.get("route_or_job"),
                kinds=redaction_hits,
            )
        except Exception as e:
            logger.error(
                "guardian: paired security_posture emit failed: %s", e, exc_info=True
            )

    return inserted_row


def _emit_security_posture_observation(
    *, source: str | None, route_or_job: str | None, kinds: list[str]
) -> None:
    """Emit the paired observation when write-time redactor caught a secret.

    The payload contains NO secret content — only the kind labels and the
    source/route/job context, per A4.
    """
    kind_summary = ",".join(sorted(set(kinds)))
    payload = {
        "observed_at": _now_iso(),
        "source": "guardian",
        "service": source or "unknown",
        "event_type": "security_posture",
        "severity_hint": "critical",
        "surface": "guardian_redactor",
        "route_or_job": route_or_job,
        "message": f"Write-time redactor caught secret pattern: {kind_summary}",
        "error_class": None,
        "stack_hash": None,
        "metadata": {
            "kinds": sorted(set(kinds)),
            "category": "security_posture",
            "code": "exposed_secret",
        },
    }
    payload["signature"] = generate_signature(
        {
            "category": "security_posture",
            "code": "exposed_secret",
            "route_or_job": route_or_job,
        }
    )
    write_payload = _strip_to_columns(payload)
    try:
        client = _db.get_client()
        client.table("system_observations").insert(write_payload).execute()
    except Exception as e:
        logger.error(
            "guardian: paired security_posture insert failed: %s", e, exc_info=True
        )

    # Also upsert the matching incident so the security posture surfaces in
    # /admin/guardian/incidents immediately.
    try:
        upsert_incident(
            {
                **payload,
                "severity": "critical",
                "category": "security_posture",
            }
        )
    except Exception as e:
        logger.error(
            "guardian: paired security_posture incident upsert failed: %s",
            e,
            exc_info=True,
        )


# ---------------------------------------------------------------------------
# Incidents
# ---------------------------------------------------------------------------

def upsert_incident(observation: dict) -> dict | None:
    """Upsert an incident row keyed on ``signature``.

    On insert: full payload from :func:`build_incident_payload`.
    On conflict: partial UPDATE from :func:`merge_observation_into_incident`.

    The classify layer is consulted when ``observation`` lacks an explicit
    ``severity`` — uses ``(category, code)`` to derive one. Returns the row
    dict on success, ``None`` on failure.
    """
    if not observation.get("signature"):
        observation["signature"] = generate_signature(observation)

    if not observation.get("severity"):
        observation["severity"] = classify_severity(
            observation.get("category"), observation.get("code")
        )

    try:
        client = _db.get_client()
        existing_resp = (
            client.table("system_incidents")
            .select("*")
            .eq("signature", observation["signature"])
            .execute()
        )
    except Exception as e:
        logger.error("guardian: upsert_incident lookup failed: %s", e, exc_info=True)
        return None

    existing_rows = (existing_resp.data or []) if existing_resp else []
    if not existing_rows:
        payload = build_incident_payload(observation)
        # First occurrence is a notification candidate — last_notified_at
        # stays NULL so PR-5's notifier knows to fire.
        try:
            insert_resp = (
                client.table("system_incidents").insert(payload).execute()
            )
            return (insert_resp.data or [None])[0]
        except Exception as e:
            logger.error(
                "guardian: upsert_incident insert failed: %s", e, exc_info=True
            )
            return None

    existing = existing_rows[0]
    update_payload = merge_observation_into_incident(existing, observation)
    try:
        update_resp = (
            client.table("system_incidents")
            .update(update_payload)
            .eq("id", existing["id"])
            .execute()
        )
        return (update_resp.data or [None])[0]
    except Exception as e:
        logger.error("guardian: upsert_incident update failed: %s", e, exc_info=True)
        return None


def list_open_incidents(limit: int = 50) -> list[dict]:
    """Return open + acknowledged incidents, newest last_seen first."""
    try:
        client = _db.get_client()
        resp = (
            client.table("system_incidents")
            .select("*")
            .in_("status", ["open", "ack"])
            .order("last_seen", desc=True)
            .limit(limit)
            .execute()
        )
        return resp.data or []
    except Exception as e:
        logger.error("guardian: list_open_incidents failed: %s", e, exc_info=True)
        return []


def get_incident(incident_id: str) -> dict | None:
    """Return a single incident row by id, or ``None`` if missing."""
    try:
        client = _db.get_client()
        resp = (
            client.table("system_incidents")
            .select("*")
            .eq("id", incident_id)
            .execute()
        )
        return (resp.data or [None])[0]
    except Exception as e:
        logger.error("guardian: get_incident failed: %s", e, exc_info=True)
        return None


def update_incident_status(
    incident_id: str,
    status: str,
    *,
    note: str | None = None,
    actor: str | None = None,
) -> dict | None:
    """Transition an incident's status and write a guardian_reviews audit row.

    Validates the transition via :func:`validate_status_transition`. Advances
    ``last_notified_at`` because a status change is itself a notification
    surface (per A6).
    """
    incident = get_incident(incident_id)
    if not incident:
        return None
    current = incident.get("status") or "open"
    validate_status_transition(current, status)

    now = _now_iso()
    update_payload: dict[str, Any] = {
        "status": status,
        "last_notified_at": now,
    }
    try:
        client = _db.get_client()
        client.table("system_incidents").update(update_payload).eq(
            "id", incident_id
        ).execute()
    except Exception as e:
        logger.error(
            "guardian: update_incident_status update failed: %s", e, exc_info=True
        )
        return None

    review_payload = {
        "incident_id": incident_id,
        "review_type": f"status_change:{current}->{status}",
        "model": actor or "system",
        "input_fingerprint": None,
        "summary": note or f"Status transitioned {current} -> {status}",
        "debug_packet": {},
        "vision_flags": [],
    }
    try:
        client = _db.get_client()
        client.table("guardian_reviews").insert(review_payload).execute()
    except Exception as e:
        logger.error(
            "guardian: guardian_reviews insert failed: %s", e, exc_info=True
        )

    return get_incident(incident_id)


# ---------------------------------------------------------------------------
# Pruning (D15) — called from the 3am scheduler hook in __init__.run_observation_prune
# ---------------------------------------------------------------------------

def call_prune_old_observations() -> int:
    """Invoke ``public.prune_old_observations()`` and return the row count.

    Wraps the supabase ``rpc`` call so the scheduler hook stays readable.
    On error returns ``-1`` so the caller can detect failure without
    needing to catch.
    """
    try:
        client = _db.get_client()
        resp = client.rpc("prune_old_observations", {}).execute()
    except Exception as e:
        logger.error("guardian: prune RPC failed: %s", e, exc_info=True)
        return -1
    data = getattr(resp, "data", None)
    # PostgREST can return the int as the body, or a list with one row.
    if isinstance(data, int):
        return data
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, int):
            return first
        if isinstance(first, dict):
            for v in first.values():
                if isinstance(v, int):
                    return v
    if isinstance(data, dict):
        for v in data.values():
            if isinstance(v, int):
                return v
    return 0


__all__ = [
    "insert_observation",
    "upsert_incident",
    "list_open_incidents",
    "get_incident",
    "update_incident_status",
    "call_prune_old_observations",
]
