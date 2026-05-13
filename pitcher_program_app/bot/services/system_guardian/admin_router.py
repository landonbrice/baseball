"""Admin API routes for System Guardian (PR-5).

Mounted under ``/admin/guardian`` in :mod:`api.main`. ALL routes require the
``X-Guardian-Admin-Token`` header to match the ``GUARDIAN_ADMIN_TOKEN`` env
var. If that env var is unset, every route returns 503 — a misconfigured
deploy must fail visibly rather than silently open the surface (per the
PR-5 brief hard constraints).

Routes:

* ``GET    /admin/guardian``                                — overview JSON
* ``GET    /admin/guardian/incidents``                      — list, filtered
* ``GET    /admin/guardian/incidents/{id}``                 — single + recent obs
* ``GET    /admin/guardian/incidents/{id}/debug-packet``    — §12 packet JSON
* ``POST   /admin/guardian/incidents/{id}/status``          — ack/resolved/etc.
* ``POST   /admin/guardian/shakedown/ack``                  — close window now
* ``POST   /admin/guardian/shakedown/rearm``                — re-arm 24h window
* ``POST   /admin/guardian/collect-now``                    — fire all collectors

Per A7: ``debug-packet`` returns JSON only - no file artifacts.
Per D12: ``shakedown/ack`` is the API-only ack surface in V1 (no Telegram
inline keyboard).
Per A1: ``collect-now`` runs the three Phase 1 collectors with per-collector
``asyncio.wait_for(timeout=5.0)`` and isolates failures so one collector's
exception does not block the others.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Header, Request
from pydantic import BaseModel, Field

from bot.config import CHICAGO_TZ
from bot.services.system_guardian import (
    debug_packet as _debug_packet,
    notify as _notify,
    store as _store,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/guardian")


# Source strings emitted by each Phase 1 collector. Mirror the ``_SOURCE``
# constants in the collector modules so the overview's last_run map keeps
# working even if a collector module reorganizes.
COLLECTOR_SOURCES = {
    "existing_health": "existing_health.collect_existing_health",
    "app_health": "app_health.collect_app_health",
    "supabase_app": "supabase_app.collect_supabase_app",
}

# Per A1: per-collector timeout for the manual collect-now path.
_COLLECT_NOW_TIMEOUT_S = 5.0

# /admin/guardian/incidents `limit` is bounded so an accidental ?limit=1e9
# can't OOM the API process.
_MAX_INCIDENTS_LIMIT = 200


# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------


async def require_guardian_admin(
    x_guardian_admin_token: str | None = Header(default=None),
) -> None:
    """FastAPI dependency: enforce the shared-secret header.

    Behavior matrix:

    * ``GUARDIAN_ADMIN_TOKEN`` env var unset → 503 (clear misconfiguration).
    * Header missing or empty → 401.
    * Header does not match env var → 401.
    * Otherwise → no-op.

    503 (not 404, not 500) on missing env so a misconfigured deploy doesn't
    silently open the routes. See PR-5 brief hard constraints.
    """
    expected = os.getenv("GUARDIAN_ADMIN_TOKEN", "").strip()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail=(
                "Guardian admin auth not configured. "
                "Set GUARDIAN_ADMIN_TOKEN in the API environment."
            ),
        )
    if not x_guardian_admin_token or x_guardian_admin_token != expected:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing X-Guardian-Admin-Token header.",
        )


# ---------------------------------------------------------------------------
# Pydantic bodies
# ---------------------------------------------------------------------------


class _StatusUpdateBody(BaseModel):
    status: str = Field(..., description="Target status. One of: ack, resolved, open, muted.")
    note: str | None = Field(default=None, description="Optional audit note.")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("", dependencies=[Depends(require_guardian_admin)])
async def overview() -> dict:
    """Guardian overview JSON.

    Returns shakedown state + incident/observation counts + the last_run map
    for the three Phase 1 collectors.
    """
    started_at = _store.get_shakedown_started_at()
    if started_at is not None:
        expires_at = started_at + timedelta(hours=_store.SHAKEDOWN_WINDOW_HOURS)
    else:
        expires_at = None

    # Observation count in the last 24h.
    since = datetime.now(CHICAGO_TZ) - timedelta(hours=24)
    obs_24h = await asyncio.to_thread(_store.count_observations_since, since)

    open_total = await asyncio.to_thread(_store.count_open_incidents)
    critical_open = await asyncio.to_thread(
        _store.count_open_incidents, "critical"
    )

    last_run_by_collector = await asyncio.to_thread(
        _store.latest_observation_by_source, list(COLLECTOR_SOURCES.values())
    )
    # Re-key by short name (existing_health / app_health / supabase_app).
    last_run = {
        short: last_run_by_collector.get(src)
        for short, src in COLLECTOR_SOURCES.items()
    }

    return {
        "shakedown": {
            "active": _store.is_shakedown_active(),
            "started_at": started_at.isoformat() if started_at else None,
            "expires_at": expires_at.isoformat() if expires_at else None,
        },
        "incidents": {
            "open": open_total,
            "critical_open": critical_open,
        },
        "observations": {
            "last_24h": obs_24h,
        },
        "collectors": {
            "last_run": last_run,
        },
    }


@router.get("/incidents", dependencies=[Depends(require_guardian_admin)])
async def list_incidents_route(
    status: str = "open",
    limit: int = 50,
    category: str | None = None,
) -> dict:
    """List incidents, filtered by status (comma-separated) + optional category.

    Default ``status=open`` returns open + ack (per spec §8). Pass
    ``status=open,resolved`` to widen the window.
    """
    if limit < 1:
        raise HTTPException(status_code=400, detail="limit must be >= 1")
    limit = min(limit, _MAX_INCIDENTS_LIMIT)

    requested = [s.strip().lower() for s in status.split(",") if s.strip()]
    if not requested:
        requested = ["open", "ack"]
    # ``open`` is shorthand for "open + ack" per the brief.
    expanded: list[str] = []
    for s in requested:
        if s == "open":
            expanded.extend(["open", "ack"])
        else:
            expanded.append(s)
    # De-dup while preserving order.
    seen = set()
    statuses = [s for s in expanded if not (s in seen or seen.add(s))]

    rows = await asyncio.to_thread(
        _store.list_incidents, status=statuses, category=category, limit=limit
    )

    # Reduce each row to the most useful fields for the list view.
    summary_fields = (
        "id",
        "signature",
        "category",
        "severity",
        "status",
        "count",
        "first_seen",
        "last_seen",
        "last_notified_at",
        "title",
    )
    summaries = [{k: row.get(k) for k in summary_fields} for row in rows]
    return {"incidents": summaries, "count": len(summaries)}


@router.get("/incidents/{incident_id}", dependencies=[Depends(require_guardian_admin)])
async def get_incident_route(incident_id: str) -> dict:
    """Return the full incident row + last 5 linked observations."""
    incident = await asyncio.to_thread(_store.get_incident, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    signature = incident.get("signature")
    if signature:
        recent_obs = await asyncio.to_thread(
            _store.list_recent_observations_for_signature, signature, limit=5
        )
    else:
        recent_obs = []
    return {"incident": incident, "recent_observations": recent_obs}


@router.get(
    "/incidents/{incident_id}/debug-packet",
    dependencies=[Depends(require_guardian_admin)],
)
async def get_debug_packet_route(incident_id: str) -> dict:
    """Return the §12 JSON debug packet for an incident. No file artifacts (A7)."""
    incident = await asyncio.to_thread(_store.get_incident, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    # build_debug_packet shells out to git log; run it on a worker thread.
    packet = await asyncio.to_thread(_debug_packet.build_debug_packet, incident)
    return packet


@router.post(
    "/incidents/{incident_id}/status",
    dependencies=[Depends(require_guardian_admin)],
)
async def post_incident_status_route(
    incident_id: str, body: _StatusUpdateBody
) -> dict:
    """Transition an incident's status.

    Validates the transition via :func:`incidents.validate_status_transition`
    (raises ValueError on illegal). After persistence, fires a Telegram DM
    via :func:`notify.notify_status_change` (per A6 rule 4).
    """
    incident = await asyncio.to_thread(_store.get_incident, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    prev_status = incident.get("status") or "open"
    new_status = (body.status or "").strip().lower()
    if not new_status:
        raise HTTPException(status_code=400, detail="status field is required")

    try:
        updated = await asyncio.to_thread(
            _store.update_incident_status,
            incident_id,
            new_status,
            note=body.note,
            actor="admin_api",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if updated is None:
        raise HTTPException(status_code=500, detail="Status update failed")

    # Fire the status-change DM (rule 4). Failure must not break the route.
    try:
        await _notify.notify_status_change(
            updated, prev_status, new_status, note=body.note
        )
    except Exception as e:
        logger.error(
            "guardian.admin_router: notify_status_change failed: %s",
            e,
            exc_info=True,
        )

    return {"incident": updated}


@router.post(
    "/shakedown/ack",
    dependencies=[Depends(require_guardian_admin)],
)
async def post_shakedown_ack_route() -> dict:
    """Admin acknowledges the shakedown baseline (D12).

    Idempotent: if shakedown is already inactive, returns 200 with
    ``{"status": "already_inactive"}`` and skips the summary DM.
    """
    if not _store.is_shakedown_active():
        return {"status": "already_inactive"}
    try:
        await _notify.send_shakedown_summary()
    except Exception as e:
        logger.error(
            "guardian.admin_router: send_shakedown_summary failed: %s",
            e,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail="Shakedown summary failed to dispatch"
        )
    return {"status": "acked"}


@router.post(
    "/shakedown/rearm",
    dependencies=[Depends(require_guardian_admin)],
)
async def post_shakedown_rearm_route() -> dict:
    """Manually re-arm a 24h shakedown window (e.g. after a major deploy)."""
    started_at = datetime.now(CHICAGO_TZ)
    await asyncio.to_thread(_store.set_shakedown_active, True, started_at)
    return {
        "status": "armed",
        "started_at": started_at.isoformat(),
        "expires_at": (
            started_at + timedelta(hours=_store.SHAKEDOWN_WINDOW_HOURS)
        ).isoformat(),
    }


@router.post(
    "/collect-now",
    dependencies=[Depends(require_guardian_admin)],
)
async def post_collect_now_route() -> dict:
    """Fire the three Phase 1 collectors in parallel and persist observations.

    Per A1: each collector runs under its own ``asyncio.wait_for`` so one
    timeout doesn't block the others. Per-collector exceptions are isolated
    and surfaced in the response as ``{"<name>": -1}``.
    """
    from bot.services.system_guardian.collectors import (
        collect_app_health,
        collect_existing_health,
        collect_supabase_app,
    )

    collectors: dict[str, Any] = {
        "existing_health": collect_existing_health,
        "app_health": collect_app_health,
        "supabase_app": collect_supabase_app,
    }

    async def _run_one(name: str, fn: Any) -> tuple[str, list[dict] | None]:
        try:
            obs_list = await asyncio.wait_for(fn(), timeout=_COLLECT_NOW_TIMEOUT_S)
            if not isinstance(obs_list, list):
                obs_list = []
            return name, obs_list
        except asyncio.TimeoutError:
            logger.error(
                "guardian.admin_router: collector %s timed out after %ss",
                name,
                _COLLECT_NOW_TIMEOUT_S,
            )
            return name, None
        except Exception as e:
            logger.error(
                "guardian.admin_router: collector %s raised: %s",
                name,
                e,
                exc_info=True,
            )
            return name, None

    results = await asyncio.gather(
        *[_run_one(name, fn) for name, fn in collectors.items()],
        return_exceptions=False,
    )

    counts: dict[str, int] = {}
    total = 0
    for name, obs_list in results:
        if obs_list is None:
            counts[name] = -1
            continue
        counts[name] = len(obs_list)
        total += len(obs_list)
        # Persist each observation via the async notify wrapper so the
        # collector run participates in the standard notification path.
        for obs in obs_list:
            try:
                await _store.insert_observation_with_notify(obs)
            except Exception as e:
                logger.error(
                    "guardian.admin_router: insert_observation_with_notify "
                    "failed during collect-now (%s): %s",
                    name,
                    e,
                    exc_info=True,
                )

    counts["total_observations"] = total
    return counts


__all__ = ["router", "require_guardian_admin", "COLLECTOR_SOURCES"]
