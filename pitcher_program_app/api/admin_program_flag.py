"""Plan 8 / A2 — per-pitcher kill-switch for the program-aware fork.

Mounted at ``/admin/program-flag/*``. Shares the ``GUARDIAN_ADMIN_TOKEN``
shared-secret with ``/admin/guardian/*`` (same operator audience, same threat
model). When the program-aware path misbehaves for a specific pitcher, flip
them off in <5s without a redeploy.

Auth contract mirrors :mod:`bot.services.system_guardian.admin_router`:

* env var unset → 503 (clear misconfiguration)
* header missing/wrong → 401
* otherwise → no-op

Audit: every successful flip emits a ``program_aware_flag_changed``
``system_observations`` row (sync no-notify path — visible in the next 9am
digest, never DMs). Audit failure is swallowed; the flag write itself wins.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime

from fastapi import APIRouter, Header, HTTPException

from bot.config import CHICAGO_TZ

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/program-flag", tags=["admin"])

ADMIN_TOKEN_ENV = "GUARDIAN_ADMIN_TOKEN"

FLAG_KEY = "program_aware_plan_gen"


def _require_admin_token(token: str | None) -> None:
    """Same shared-secret contract as ``/admin/guardian/*``.

    503 (not 404, not 500) on unset env so a misconfigured deploy surfaces
    visibly. 401 on header missing/wrong.
    """
    expected = (os.environ.get(ADMIN_TOKEN_ENV) or "").strip()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail=(
                "Admin auth not configured. "
                f"Set {ADMIN_TOKEN_ENV} in the API environment."
            ),
        )
    if not token or token != expected:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing X-Guardian-Admin-Token header.",
        )


def _emit_flag_change_audit(pitcher_id: str, new_value: bool) -> None:
    """Best-effort sync no-notify observation so the flip lands in the 9am digest.

    Wrapped in a broad try/except — Guardian audit failure must not break the
    flag write itself (the operator NEEDS the kill switch to be reliable).
    """
    try:
        from bot.services.system_guardian import store as _gstore

        value_label = "on" if new_value else "off"
        _gstore.insert_observation(
            {
                "observed_at": datetime.now(CHICAGO_TZ).isoformat(),
                "source": "guardian",
                "service": "admin_program_flag",
                "event_type": "program_aware_flag_changed",
                "severity_hint": "info",
                "surface": "guardian_self",
                "route_or_job": "POST /admin/program-flag",
                "message": (
                    f"Admin flipped {FLAG_KEY}={value_label} for {pitcher_id}"
                ),
                "signature": "program_aware_flag_changed",
                "metadata": {
                    "category": "guardian_self",
                    "code": "program_aware_flag_changed",
                    "pitcher_id": pitcher_id,
                    "new_value": new_value,
                },
            }
        )
    except Exception:  # pragma: no cover — audit best-effort
        logger.warning(
            "program_aware_flag_changed audit emit failed for %s",
            pitcher_id,
            exc_info=True,
        )


@router.post("/{pitcher_id}/{value}")
async def set_pitcher_program_aware_flag(
    pitcher_id: str,
    value: str,
    x_guardian_admin_token: str | None = Header(default=None),
):
    """Set ``pitcher_training_model.feature_flags.program_aware_plan_gen``.

    ``value`` must be ``"on"`` or ``"off"``. Audited via a Guardian
    ``system_observations`` sentinel so the change surfaces in the next 9am
    digest. Returns 404 if the pitcher has no ``pitcher_training_model`` row
    yet (caller must bootstrap the row first — no auto-create).
    """
    _require_admin_token(x_guardian_admin_token)
    if value not in ("on", "off"):
        raise HTTPException(
            status_code=422,
            detail="value must be 'on' or 'off'",
        )

    from bot.services import db

    new_value = value == "on"
    try:
        db.set_feature_flag(pitcher_id, FLAG_KEY, new_value)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=(
                f"no pitcher_training_model row for {pitcher_id} — "
                "bootstrap the row before flipping flags"
            ),
        )

    _emit_flag_change_audit(pitcher_id, new_value)

    return {
        "pitcher_id": pitcher_id,
        FLAG_KEY: new_value,
    }


@router.get("/{pitcher_id}")
async def get_pitcher_program_aware_flag(
    pitcher_id: str,
    x_guardian_admin_token: str | None = Header(default=None),
):
    """Read the current ``program_aware_plan_gen`` value for a pitcher."""
    _require_admin_token(x_guardian_admin_token)
    from bot.services import db

    return {
        "pitcher_id": pitcher_id,
        FLAG_KEY: db.get_feature_flag(pitcher_id, FLAG_KEY),
    }
