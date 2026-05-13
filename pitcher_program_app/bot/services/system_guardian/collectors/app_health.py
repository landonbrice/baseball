"""``app_health`` collector — in-process probes against the FastAPI app surface.

Per amendments doc §2 A1 (5s per-collector timeout, threadpool, never raises)
and §2 A2 (Phase 1 collector list includes ``app_health``).

Calls the FastAPI app **in-process** via ``httpx.AsyncClient`` +
``httpx.ASGITransport`` so we hit the real route handlers without crossing
the loopback network — this is the pattern the original spec §7 "App Health"
calls out ("Can run in-process first to avoid auth complexity").

Signals produced:

* ``app_health_endpoint_status``    — ``GET /health`` reachability + status payload.
* ``db_connectivity_via_health``    — if the ``/health`` payload exposes a Supabase
  connectivity flag, surface that as a separate observation (per spec: "if there's
  a payload with database connectivity info, propagate that as
  ``signal=db_connectivity_via_health`` rather than re-running a separate DB query").
* ``admin_health_endpoint_status``  — ``GET /admin/health`` reachability. The route
  enforces Telegram HMAC admin auth; a 401/403 from the collector means the route
  exists and the auth wall is intact, which is the healthy state for this probe.
  A 404 means the route is missing (skip — emit nothing). A 5xx is critical.
* ``recent_errors_count``           — info note: telemetry not yet wired in-process.
  The app currently relies on stdout for unstructured errors; Guardian will surface
  these via the Railway collector (PR-7+, Phase 2). Keeps the contract honest.
* ``route_latency_p95``             — info note: latency tracker not yet wired.
  Same disposition as ``recent_errors_count`` — surface the gap, don't fabricate.

The collector NEVER raises — on any catastrophic failure (import error,
loop blowup, etc.) it returns ONE ``collector_failure`` observation per the
same A1 pattern PR-3 established.
"""

from __future__ import annotations

import asyncio
import logging
import traceback
from datetime import datetime
from typing import Any

from bot.config import CHICAGO_TZ

logger = logging.getLogger(__name__)

# A1: per-collector timeout ceiling.
_COLLECTOR_TIMEOUT_S = 5.0

# Sentinel source string so observations are traceable to this exact module.
_SOURCE = "app_health.collect_app_health"


def _now_iso() -> str:
    return datetime.now(CHICAGO_TZ).isoformat()


# ---------------------------------------------------------------------------
# Pure builders — easy to unit-test without touching ASGI.
# ---------------------------------------------------------------------------


def _build_health_endpoint_observation(
    *, status_code: int | None, payload: dict | None, error: str | None
) -> dict:
    """``app_health_endpoint_status`` for ``GET /health``."""
    metadata: dict[str, Any] = {
        "category": "runtime_error" if error or (status_code or 0) >= 500 else "data_quality",
        "code": "app_health_endpoint_status",
        "endpoint": "/health",
        "status_code": status_code,
    }
    if payload is not None:
        # Keep payload small and bounded — these are top-level keys only.
        metadata["payload_keys"] = sorted(payload.keys())
        # Preserve a small subset of well-known flags so the digest can render them.
        for k in ("status", "supabase_connected", "bot_token_set", "deepseek_key_set"):
            if k in payload:
                metadata[k] = payload[k]
    if error:
        metadata["error"] = error[:300]

    if error or status_code is None:
        return {
            "observed_at": _now_iso(),
            "source": _SOURCE,
            "service": "api",
            "event_type": "app_health_endpoint_status",
            "severity_hint": "critical",
            "surface": "api_route",
            "route_or_job": "GET /health",
            "message": (
                f"GET /health failed: {(error or 'no status').splitlines()[0][:200]}"
            ),
            "metadata": {**metadata, "category": "runtime_error"},
        }

    if status_code >= 500:
        return {
            "observed_at": _now_iso(),
            "source": _SOURCE,
            "service": "api",
            "event_type": "app_health_endpoint_status",
            "severity_hint": "critical",
            "surface": "api_route",
            "route_or_job": "GET /health",
            "message": f"GET /health returned {status_code}",
            "metadata": {**metadata, "category": "runtime_error"},
        }

    if status_code != 200:
        return {
            "observed_at": _now_iso(),
            "source": _SOURCE,
            "service": "api",
            "event_type": "app_health_endpoint_status",
            "severity_hint": "warning",
            "surface": "api_route",
            "route_or_job": "GET /health",
            "message": f"GET /health returned {status_code} (expected 200)",
            "metadata": {**metadata, "category": "runtime_error"},
        }

    return {
        "observed_at": _now_iso(),
        "source": _SOURCE,
        "service": "api",
        "event_type": "app_health_endpoint_status",
        "severity_hint": "info",
        "surface": "api_route",
        "route_or_job": "GET /health",
        "message": f"GET /health: 200 ({len(payload or {})} fields)",
        "metadata": {**metadata, "category": "existing_health"},
    }


def _build_db_connectivity_observation(payload: dict | None) -> dict | None:
    """Propagate Supabase connectivity from the ``/health`` payload, when present.

    If the payload doesn't carry a ``supabase_connected`` field, return ``None`` —
    we don't fabricate it.
    """
    if not isinstance(payload, dict) or "supabase_connected" not in payload:
        return None

    connected = bool(payload.get("supabase_connected"))
    pitcher_count = payload.get("pitcher_count")

    if connected:
        return {
            "observed_at": _now_iso(),
            "source": _SOURCE,
            "service": "api",
            "event_type": "db_connectivity_via_health",
            "severity_hint": "info",
            "surface": "api_route",
            "route_or_job": "GET /health",
            "message": (
                f"db_connectivity_via_health: supabase_connected=true"
                + (f", pitcher_count={pitcher_count}" if pitcher_count is not None else "")
            ),
            "metadata": {
                "category": "existing_health",
                "code": "db_connectivity_via_health",
                "supabase_connected": True,
                "pitcher_count": pitcher_count,
            },
        }

    return {
        "observed_at": _now_iso(),
        "source": _SOURCE,
        "service": "api",
        "event_type": "db_connectivity_via_health",
        "severity_hint": "critical",
        "surface": "api_route",
        "route_or_job": "GET /health",
        "message": "db_connectivity_via_health: supabase_connected=false",
        "metadata": {
            "category": "database_error",
            "code": "db_connectivity_via_health",
            "supabase_connected": False,
            "pitcher_count": pitcher_count,
        },
    }


def _build_admin_health_observation(
    *, status_code: int | None, error: str | None
) -> dict | None:
    """``admin_health_endpoint_status`` for ``GET /admin/health``.

    Behavior:
    * 401 / 403  → info: route exists, admin auth wall in place (healthy).
    * 404        → return None (skip; route doesn't exist).
    * 2xx        → info: route exists and (in this probe context) returned a body.
    * 5xx        → critical.
    * Other 4xx  → warning.
    * Exception  → warning (route may not be reachable through ASGI for some reason).
    """
    metadata: dict[str, Any] = {
        "category": "existing_health",
        "code": "admin_health_endpoint_status",
        "endpoint": "/admin/health",
        "status_code": status_code,
    }
    if error:
        metadata["error"] = error[:300]

    if error:
        return {
            "observed_at": _now_iso(),
            "source": _SOURCE,
            "service": "api",
            "event_type": "admin_health_endpoint_status",
            "severity_hint": "warning",
            "surface": "api_route",
            "route_or_job": "GET /admin/health",
            "message": f"GET /admin/health raised: {error.splitlines()[0][:200]}",
            "metadata": {**metadata, "category": "runtime_error"},
        }

    if status_code is None:
        return None

    if status_code == 404:
        # Route doesn't exist — skip per spec ("if it doesn't exist, skip").
        return None

    if status_code in (401, 403):
        return {
            "observed_at": _now_iso(),
            "source": _SOURCE,
            "service": "api",
            "event_type": "admin_health_endpoint_status",
            "severity_hint": "info",
            "surface": "api_route",
            "route_or_job": "GET /admin/health",
            "message": f"GET /admin/health: {status_code} (admin auth wall intact)",
            "metadata": {**metadata, "auth_wall_intact": True},
        }

    if status_code >= 500:
        return {
            "observed_at": _now_iso(),
            "source": _SOURCE,
            "service": "api",
            "event_type": "admin_health_endpoint_status",
            "severity_hint": "critical",
            "surface": "api_route",
            "route_or_job": "GET /admin/health",
            "message": f"GET /admin/health returned {status_code}",
            "metadata": {**metadata, "category": "runtime_error"},
        }

    if 200 <= status_code < 300:
        return {
            "observed_at": _now_iso(),
            "source": _SOURCE,
            "service": "api",
            "event_type": "admin_health_endpoint_status",
            "severity_hint": "info",
            "surface": "api_route",
            "route_or_job": "GET /admin/health",
            "message": f"GET /admin/health: {status_code}",
            "metadata": metadata,
        }

    return {
        "observed_at": _now_iso(),
        "source": _SOURCE,
        "service": "api",
        "event_type": "admin_health_endpoint_status",
        "severity_hint": "warning",
        "surface": "api_route",
        "route_or_job": "GET /admin/health",
        "message": f"GET /admin/health returned {status_code}",
        "metadata": {**metadata, "category": "runtime_error"},
    }


def _build_not_wired_observation(signal: str, route_or_job: str, reason: str) -> dict:
    """Honest 'this telemetry is not yet wired in-process' info observation.

    Used for ``recent_errors_count`` and ``route_latency_p95`` — the spec
    explicitly says "produce ONE info observation noting that error telemetry
    is not yet wired and stop. Don't fabricate it."
    """
    return {
        "observed_at": _now_iso(),
        "source": _SOURCE,
        "service": "api",
        "event_type": f"{signal}_not_wired",
        "severity_hint": "info",
        "surface": "api_route",
        "route_or_job": route_or_job,
        "message": f"{signal}: telemetry not yet wired in-process ({reason})",
        "metadata": {
            "category": "guardian_self",
            "code": f"{signal}_not_wired",
            "signal": signal,
            "reason": reason,
        },
    }


def _build_collector_failure_observation(exc: BaseException, *, step: str) -> dict:
    """Single ``collector_failure`` observation for the catch-all branch (A1)."""
    stack_excerpt = traceback.format_exc(limit=8)[-1500:]
    return {
        "observed_at": _now_iso(),
        "source": _SOURCE,
        "service": "api",
        "event_type": "collector_failure",
        "severity_hint": "warning",
        "surface": "guardian_self",
        "route_or_job": "collect_app_health",
        "message": (
            f"collector_failure in app_health.{step}: "
            f"{type(exc).__name__}: {str(exc)[:200]}"
        ),
        "stack": stack_excerpt,
        "metadata": {
            "category": "guardian_self",
            "code": "collector_failure",
            "step": step,
            "exception_class": type(exc).__name__,
        },
    }


# ---------------------------------------------------------------------------
# In-process probe — uses ASGITransport so we never hit loopback.
# ---------------------------------------------------------------------------


async def _probe_route(path: str) -> tuple[int | None, dict | None, str | None]:
    """Probe an in-process FastAPI route. Returns (status_code, payload, error).

    On exception, returns (None, None, error_message). On non-JSON 200 bodies,
    returns (status_code, None, None). The ASGITransport pattern means there is
    no real network hop — the route handler runs directly in this event loop.
    """
    try:
        import httpx
        from api.main import app as api_app
    except Exception as e:  # pragma: no cover — env-level import error
        return (None, None, f"import_error: {type(e).__name__}: {e}")

    transport = httpx.ASGITransport(app=api_app)
    try:
        async with httpx.AsyncClient(
            transport=transport, base_url="http://guardian.internal"
        ) as client:
            resp = await client.get(path)
    except Exception as e:
        return (None, None, f"{type(e).__name__}: {e}")

    payload: dict | None = None
    try:
        body = resp.json()
        if isinstance(body, dict):
            payload = body
    except Exception:
        payload = None

    return (resp.status_code, payload, None)


async def _run_probes() -> list[dict]:
    """Run all in-process probes + emit the not-yet-wired notes."""
    observations: list[dict] = []

    # /health — required.
    try:
        status, payload, error = await _probe_route("/health")
        observations.append(
            _build_health_endpoint_observation(
                status_code=status, payload=payload, error=error
            )
        )
        db_obs = _build_db_connectivity_observation(payload)
        if db_obs is not None:
            observations.append(db_obs)
    except Exception as e:
        logger.error("app_health: /health probe builder failed: %s", e, exc_info=True)
        observations.append(_build_collector_failure_observation(e, step="health"))

    # /admin/health — optional, may 404.
    try:
        status, _payload, error = await _probe_route("/admin/health")
        admin_obs = _build_admin_health_observation(status_code=status, error=error)
        if admin_obs is not None:
            observations.append(admin_obs)
    except Exception as e:
        logger.error("app_health: /admin/health probe builder failed: %s", e, exc_info=True)
        observations.append(_build_collector_failure_observation(e, step="admin_health"))

    # recent_errors_count — telemetry not yet wired.
    try:
        observations.append(
            _build_not_wired_observation(
                "recent_errors_count",
                "in_process_error_counter",
                "app currently relies on stdout for unstructured errors",
            )
        )
    except Exception as e:  # pragma: no cover — pure dict construction
        observations.append(
            _build_collector_failure_observation(e, step="recent_errors_count")
        )

    # route_latency_p95 — telemetry not yet wired.
    try:
        observations.append(
            _build_not_wired_observation(
                "route_latency_p95",
                "in_process_latency_tracker",
                "no in-process latency tracker installed",
            )
        )
    except Exception as e:  # pragma: no cover — pure dict construction
        observations.append(
            _build_collector_failure_observation(e, step="route_latency_p95")
        )

    return observations


# ---------------------------------------------------------------------------
# Public coroutine
# ---------------------------------------------------------------------------


async def collect_app_health() -> list[dict]:
    """Async collector entrypoint per A1.

    Bounded by a 5s ``asyncio.wait_for`` ceiling. On any unrecoverable error
    (timeout, top-level exception), returns ONE ``collector_failure``
    observation. Never raises.

    The wiring layer (PR-5 admin route, PR-6 tick loop) is responsible for
    calling :func:`bot.services.system_guardian.store.insert_observation` on
    each returned dict — collectors don't touch storage directly.
    """
    try:
        return await asyncio.wait_for(_run_probes(), timeout=_COLLECTOR_TIMEOUT_S)
    except asyncio.TimeoutError:
        logger.error(
            "app_health: collector exceeded %ss timeout", _COLLECTOR_TIMEOUT_S
        )
        return [
            {
                "observed_at": _now_iso(),
                "source": _SOURCE,
                "service": "api",
                "event_type": "collector_failure",
                "severity_hint": "warning",
                "surface": "guardian_self",
                "route_or_job": "collect_app_health",
                "message": (
                    f"collect_app_health timed out after {_COLLECTOR_TIMEOUT_S}s"
                ),
                "metadata": {
                    "category": "guardian_self",
                    "code": "collector_failure",
                    "step": "wait_for",
                    "timeout_s": _COLLECTOR_TIMEOUT_S,
                },
            }
        ]
    except Exception as e:
        logger.error("app_health: collector raised: %s", e, exc_info=True)
        return [_build_collector_failure_observation(e, step="run_probes")]


__all__ = ["collect_app_health"]
