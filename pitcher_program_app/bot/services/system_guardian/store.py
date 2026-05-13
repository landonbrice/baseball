"""Supabase CRUD against the three PR-1 tables.

This is the single boundary between the rest of the Guardian package and the
``system_observations`` / ``system_incidents`` / ``guardian_reviews`` tables.

Style follows ``bot/services/db.py``:

* Synchronous Supabase service-role client.
* Reuses ``bot.services.db.get_client()`` rather than holding its own
  connection.
* Defensive against query failures — every public function logs and either
  swallows or returns a sentinel rather than raising into the caller.

PR-2 shipped: insert/upsert/list/get + prune.
PR-5 adds (this file): shakedown sentinel-row helpers (A6) + notification
dispatch wiring via :func:`insert_observation_with_notify` + admin-route
support helpers (counts, observation queries, latest-by-source map).

The shakedown sentinel row lives in ``system_observations`` itself rather than
in a new table so this PR does not require another migration. It is keyed on
the deterministic signature ``guardian_shakedown_state`` and carries the
``{"active": bool, "started_at": iso8601}`` payload in ``metadata.details``.
``is_shakedown_active`` reads the most-recent sentinel; older sentinel rows are
ignored (and eventually pruned by the 3am job).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
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


# Shakedown (A6): a deterministic signature value used to find the sentinel
# row. NOT generated via cluster.generate_signature so the value is stable
# across cluster-rule changes and can be queried by literal equality.
SHAKEDOWN_SENTINEL_SIGNATURE = "guardian_shakedown_state"
# 24 hours per A6.
SHAKEDOWN_WINDOW_HOURS = 24


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

    Per A6: on the FIRST EVER observation insert (i.e. no shakedown sentinel
    row exists yet), this function auto-arms a 24h shakedown window by
    writing the sentinel row. Subsequent restarts do NOT auto-arm — only an
    absent sentinel triggers arming. Sentinel inserts themselves do NOT
    re-arm (to avoid an infinite loop and to keep manual ack idempotent).

    Failure handling: a Supabase error here is logged but does not raise —
    Guardian must never crash its host (the Telegram bot process). Callers
    that need the row id must handle ``None``.
    """
    obs = normalize_observation(raw)
    redaction_hits: list[str] = obs.pop("_redaction_hits", []) or []
    write_payload = _strip_to_columns(obs)

    is_sentinel = write_payload.get("signature") == SHAKEDOWN_SENTINEL_SIGNATURE

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

    # A6 auto-arm: if this is a regular observation AND the shakedown sentinel
    # has NEVER been written, write it now. A brand-new deploy gets a fresh
    # 24h shakedown window. Defensive try/except — auto-arm failure must not
    # take down the regular insert path.
    if not is_sentinel:
        try:
            if not _sentinel_row_exists():
                set_shakedown_active(True, started_at=datetime.now(CHICAGO_TZ))
        except Exception as e:
            logger.error(
                "guardian: shakedown auto-arm failed: %s", e, exc_info=True
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


# ---------------------------------------------------------------------------
# PR-5: notification-state advance + async insert+notify wrapper
# ---------------------------------------------------------------------------


def advance_last_notified_at(
    incident_id: str, *, severity: str | None = None
) -> dict | None:
    """Stamp ``last_notified_at`` and (optionally) ``severity`` on an incident.

    Per A6 the notifier dispatches when an incident is first seen, when its
    status changes, or when severity escalates — and in each of those cases
    this helper persists the timestamp so the next dedup decision sees the
    advance. We deliberately do NOT update ``count`` or ``last_seen`` here —
    those move inside :func:`upsert_incident` on the observation-insert path.

    ``severity`` is stored alongside ``last_notified_at`` so the dedup rule can
    notice escalations across notifier invocations even when the stored
    ``severity`` column has been updated since the last DM (e.g. via an
    out-of-band review). Stored in metadata-free form: as the actual
    ``severity`` column, since that's what callers read elsewhere.
    """
    now = _now_iso()
    update_payload: dict[str, Any] = {"last_notified_at": now}
    if severity:
        update_payload["severity"] = severity
    try:
        client = _db.get_client()
        resp = (
            client.table("system_incidents")
            .update(update_payload)
            .eq("id", incident_id)
            .execute()
        )
        return (resp.data or [None])[0]
    except Exception as e:
        logger.error(
            "guardian: advance_last_notified_at failed: %s", e, exc_info=True
        )
        return None


def _lookup_incident_by_signature(signature: str) -> dict | None:
    """Internal: fetch the current incident row for a signature, or None."""
    try:
        client = _db.get_client()
        resp = (
            client.table("system_incidents")
            .select("severity, last_notified_at, status")
            .eq("signature", signature)
            .limit(1)
            .execute()
        )
        rows = resp.data or []
        return rows[0] if rows else None
    except Exception as e:
        logger.error(
            "guardian: lookup_incident_by_signature failed: %s", e, exc_info=True
        )
        return None


async def insert_observation_with_notify(raw: dict) -> dict | None:
    """Async wrapper: insert + upsert incident + maybe notify admin.

    Sync ``insert_observation`` stays the write-only path (e.g. the prune
    job's self-observation). Callers in async contexts that want the A6
    notification path use THIS function instead. Returns the inserted
    observation row (same shape as :func:`insert_observation`) or ``None`` on
    failure.

    Notification dedup is determined by comparing the incident's severity
    BEFORE the upsert against the observation severity, so a same-signature
    repeat that just escalated from warning→critical is correctly detected as
    "newly notify-worthy" instead of being silenced by the post-merge value.
    The pre-upsert snapshot is captured via :func:`_lookup_incident_by_signature`
    and passed to :func:`notify.maybe_notify_admin` via the ``raw`` dict's
    transient ``_prev_severity`` / ``_prev_last_notified_at`` /
    ``_prev_status`` keys; the notifier strips those before formatting.

    The notifier dispatch is loaded lazily so importing ``store`` from
    contexts without an event loop (or without Telegram credentials) doesn't
    pull ``python-telegram-bot`` along with it.
    """
    import asyncio

    # Compute the signature once so the pre-upsert lookup hits the same key
    # the upsert will end up using. ``normalize_observation`` would generate
    # the same signature, but we use cluster.generate_signature directly so
    # this step doesn't double-redact / double-normalize the message.
    signature = raw.get("signature") or generate_signature(raw)
    prev = _lookup_incident_by_signature(signature) or {}
    prev_severity = prev.get("severity")
    prev_last_notified_at = prev.get("last_notified_at")
    prev_status = prev.get("status")

    row = await asyncio.to_thread(insert_observation, raw)
    # Storage failure is logged inside insert_observation; we still try to
    # upsert the incident from the raw payload so the row hits system_incidents.
    incident = None
    try:
        incident = await asyncio.to_thread(upsert_incident, raw)
    except Exception as e:
        logger.error(
            "guardian: incident upsert failed in notify wrapper: %s", e, exc_info=True
        )
        incident = None

    if incident is None:
        # Without an incident there is nothing for the notifier to deduplicate
        # against; skip the dispatch step entirely.
        return row

    # Stash the pre-upsert context on a copy of the raw dict so notify can
    # read it without us mutating the caller's input.
    enriched = dict(raw)
    enriched["_prev_severity"] = prev_severity
    enriched["_prev_last_notified_at"] = prev_last_notified_at
    enriched["_prev_status"] = prev_status

    try:
        from bot.services.system_guardian import notify as _notify

        await _notify.maybe_notify_admin(enriched, incident)
    except Exception as e:
        logger.error(
            "guardian: maybe_notify_admin failed: %s", e, exc_info=True
        )

    return row


# ---------------------------------------------------------------------------
# PR-5: shakedown sentinel-row helpers (A6)
# ---------------------------------------------------------------------------


def _sentinel_row_exists() -> bool:
    """``True`` if ANY shakedown sentinel row has ever been written."""
    try:
        client = _db.get_client()
        resp = (
            client.table("system_observations")
            .select("id")
            .eq("signature", SHAKEDOWN_SENTINEL_SIGNATURE)
            .limit(1)
            .execute()
        )
        return bool(resp.data)
    except Exception as e:
        logger.error("guardian: sentinel_row_exists check failed: %s", e, exc_info=True)
        # Be conservative: pretend it exists. Pretending it doesn't would
        # cause an auto-arm storm during a Supabase outage.
        return True


def _latest_sentinel_row() -> dict | None:
    """Return the most recent shakedown sentinel row, or ``None``."""
    try:
        client = _db.get_client()
        resp = (
            client.table("system_observations")
            .select("*")
            .eq("signature", SHAKEDOWN_SENTINEL_SIGNATURE)
            .order("observed_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = resp.data or []
        return rows[0] if rows else None
    except Exception as e:
        logger.error("guardian: latest_sentinel_row lookup failed: %s", e, exc_info=True)
        return None


def _parse_sentinel_details(row: dict | None) -> dict:
    """Extract the ``{active, started_at}`` from a sentinel row.

    Tolerates legacy shapes where details landed at the metadata root rather
    than under ``details``.
    """
    if not row:
        return {}
    metadata = row.get("metadata") or {}
    if not isinstance(metadata, dict):
        return {}
    details = metadata.get("details")
    if isinstance(details, dict):
        return details
    # Fallback: legacy / direct shape.
    return {
        k: metadata.get(k)
        for k in ("active", "started_at")
        if k in metadata
    }


def get_shakedown_started_at() -> datetime | None:
    """Return the ISO-parsed start time of the active shakedown, or ``None``.

    Returns ``None`` when the sentinel says ``active=false`` OR when there is
    no sentinel at all OR when the start_at is unparseable.
    """
    row = _latest_sentinel_row()
    details = _parse_sentinel_details(row)
    if not details or not details.get("active"):
        return None
    raw = details.get("started_at")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except (TypeError, ValueError):
        logger.warning("guardian: unparseable shakedown started_at=%r", raw)
        return None


def is_shakedown_active() -> bool:
    """Return ``True`` iff a shakedown window is currently open.

    Auto-expiry guard: if the sentinel says ``active=true`` but ``started_at``
    is older than ``SHAKEDOWN_WINDOW_HOURS``, we report ``False`` here.

    Per the docstring contract in the PR-5 brief, this function MUST NOT have
    side effects — the auto-expire write happens via
    :func:`check_and_expire_shakedown`.
    """
    started_at = get_shakedown_started_at()
    if started_at is None:
        return False
    elapsed = datetime.now(CHICAGO_TZ) - started_at
    return elapsed < timedelta(hours=SHAKEDOWN_WINDOW_HOURS)


def set_shakedown_active(active: bool, started_at: datetime | None = None) -> None:
    """Write a new shakedown sentinel row.

    Each call appends a new sentinel observation rather than mutating an
    existing row, so the audit trail of arm/disarm transitions is preserved
    in ``system_observations``. ``is_shakedown_active`` and
    ``get_shakedown_started_at`` always read the most recent sentinel.

    When ``active=True`` and ``started_at`` is None, defaults to now (Chicago).
    """
    if active and started_at is None:
        started_at = datetime.now(CHICAGO_TZ)
    iso = started_at.isoformat() if started_at else None

    sentinel = {
        "observed_at": _now_iso(),
        "source": "guardian",
        "service": "shakedown",
        "event_type": "shakedown_state",
        "severity_hint": "info",
        "surface": "guardian_self",
        "route_or_job": "shakedown_window",
        "message": (
            f"shakedown_state active={active}"
            + (f" started_at={iso}" if iso else "")
        ),
        "signature": SHAKEDOWN_SENTINEL_SIGNATURE,
        "metadata": {
            "category": "guardian_self",
            "code": "shakedown_state",
            "details": {
                "active": bool(active),
                "started_at": iso,
            },
        },
    }
    payload = _strip_to_columns(sentinel)
    try:
        client = _db.get_client()
        client.table("system_observations").insert(payload).execute()
    except Exception as e:
        logger.error(
            "guardian: set_shakedown_active insert failed: %s", e, exc_info=True
        )


def list_shakedown_signatures() -> list[dict]:
    """Distinct incident signatures seen since the active shakedown started.

    Returns a list of ``{signature, count, severity, title, last_seen, category}``
    dicts ordered by severity (critical > warning > info) then count descending.
    Used by :func:`bot.services.system_guardian.notify.send_shakedown_summary`
    to compose the end-of-window DM.

    If no shakedown is active, returns an empty list.
    """
    started_at = get_shakedown_started_at()
    if started_at is None:
        return []

    try:
        client = _db.get_client()
        resp = (
            client.table("system_incidents")
            .select("signature, title, severity, count, last_seen, category")
            .gte("last_seen", started_at.isoformat())
            .execute()
        )
    except Exception as e:
        logger.error(
            "guardian: list_shakedown_signatures query failed: %s", e, exc_info=True
        )
        return []

    rows = resp.data or []
    # Sort by severity desc (critical first), then count desc, then signature.
    def _sort_key(r: dict) -> tuple[int, int, str]:
        return (
            -SEVERITY_RANK.get(r.get("severity") or "info", 0),
            -(int(r.get("count") or 0)),
            r.get("signature") or "",
        )

    return sorted(rows, key=_sort_key)


def check_and_expire_shakedown() -> bool:
    """Auto-expire the shakedown window when older than 24h.

    Returns ``True`` when this call transitioned the state from active to
    inactive — caller (the scheduler hook in
    :mod:`bot.services.system_guardian.__init__`) uses the return value to
    decide whether to fire the end-of-window summary DM.
    """
    started_at = get_shakedown_started_at()
    if started_at is None:
        return False  # Already inactive.
    elapsed = datetime.now(CHICAGO_TZ) - started_at
    if elapsed < timedelta(hours=SHAKEDOWN_WINDOW_HOURS):
        return False  # Still active.

    set_shakedown_active(False)
    return True


# ---------------------------------------------------------------------------
# PR-5: admin-route support — counts + observation queries by source
# ---------------------------------------------------------------------------


def count_open_incidents(severity: str | None = None) -> int:
    """Return the count of open incidents, optionally filtered by severity.

    "Open" includes both ``open`` and ``ack`` per spec §8 (an ack'd incident
    is still an active concern; a resolved/muted one is not). When
    ``severity`` is set, only counts incidents at that exact severity.
    """
    try:
        client = _db.get_client()
        query = (
            client.table("system_incidents")
            .select("id", count="exact")
            .in_("status", ["open", "ack"])
        )
        if severity:
            query = query.eq("severity", severity)
        resp = query.execute()
    except Exception as e:
        logger.error("guardian: count_open_incidents failed: %s", e, exc_info=True)
        return 0
    # PostgREST returns count via the `count` attribute on the response.
    return int(getattr(resp, "count", 0) or 0)


def count_observations_since(since: datetime) -> int:
    """Return the count of observations with ``observed_at >= since``."""
    try:
        client = _db.get_client()
        resp = (
            client.table("system_observations")
            .select("id", count="exact")
            .gte("observed_at", since.isoformat())
            .execute()
        )
    except Exception as e:
        logger.error(
            "guardian: count_observations_since failed: %s", e, exc_info=True
        )
        return 0
    return int(getattr(resp, "count", 0) or 0)


def latest_observation_by_source(sources: list[str]) -> dict[str, str | None]:
    """For each source string, return the ISO ``observed_at`` of the most
    recent observation produced by that source (or ``None`` if none).

    Used by the ``/admin/guardian`` overview to render the
    ``collectors.last_run`` map.
    """
    out: dict[str, str | None] = {s: None for s in sources}
    if not sources:
        return out
    try:
        client = _db.get_client()
        for s in sources:
            resp = (
                client.table("system_observations")
                .select("observed_at")
                .eq("source", s)
                .order("observed_at", desc=True)
                .limit(1)
                .execute()
            )
            rows = resp.data or []
            if rows:
                out[s] = rows[0].get("observed_at")
    except Exception as e:
        logger.error(
            "guardian: latest_observation_by_source failed: %s", e, exc_info=True
        )
    return out


def list_incidents(
    *,
    status: list[str] | None = None,
    category: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Generalized incident lister used by the admin routes.

    ``status`` is a list of acceptable statuses (default: ``["open", "ack"]``).
    """
    statuses = status or ["open", "ack"]
    try:
        client = _db.get_client()
        query = (
            client.table("system_incidents")
            .select("*")
            .in_("status", statuses)
            .order("last_seen", desc=True)
            .limit(limit)
        )
        if category:
            query = query.eq("category", category)
        resp = query.execute()
        return resp.data or []
    except Exception as e:
        logger.error("guardian: list_incidents failed: %s", e, exc_info=True)
        return []


def list_recent_observations_for_signature(
    signature: str, *, limit: int = 5
) -> list[dict]:
    """Return the most recent observations carrying ``signature``."""
    try:
        client = _db.get_client()
        resp = (
            client.table("system_observations")
            .select("*")
            .eq("signature", signature)
            .order("observed_at", desc=True)
            .limit(limit)
            .execute()
        )
        return resp.data or []
    except Exception as e:
        logger.error(
            "guardian: list_recent_observations_for_signature failed: %s",
            e,
            exc_info=True,
        )
        return []


__all__ = [
    "SHAKEDOWN_SENTINEL_SIGNATURE",
    "SHAKEDOWN_WINDOW_HOURS",
    "insert_observation",
    "insert_observation_with_notify",
    "upsert_incident",
    "list_open_incidents",
    "list_incidents",
    "list_recent_observations_for_signature",
    "get_incident",
    "update_incident_status",
    "advance_last_notified_at",
    "call_prune_old_observations",
    # Shakedown
    "is_shakedown_active",
    "set_shakedown_active",
    "get_shakedown_started_at",
    "list_shakedown_signatures",
    "check_and_expire_shakedown",
    # Admin support
    "count_open_incidents",
    "count_observations_since",
    "latest_observation_by_source",
]
