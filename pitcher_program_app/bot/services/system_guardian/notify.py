"""Telegram admin notifier — PR-5.

Single-channel V1 dispatcher for System Guardian. Reads
``ADMIN_TELEGRAM_CHAT_ID`` + ``TELEGRAM_BOT_TOKEN`` from :mod:`bot.config`,
and DMs the admin chat for the events A6 says are notification-worthy.

Per A6 (Amendments §2 - the dedup contract):

1. **Shakedown window suppresses DMs.** While
   :func:`store.is_shakedown_active` returns True, all incident DMs are
   suppressed. A single end-of-window summary fires when shakedown ends.
2. **First occurrence notifies.** When ``incident.last_notified_at is None``,
   the notifier DMs and advances ``last_notified_at``.
3. **Severity escalation notifies.** When the observation caused the
   incident's stored severity to rise to a higher band, the notifier DMs
   and advances ``last_notified_at`` + ``severity``. Detection works by
   comparing the pre-upsert ``_prev_severity`` (set by
   :func:`store.insert_observation_with_notify`) against the post-upsert
   ``incident.severity`` - a strict band increase fires.
4. **Status transitions notify.** Status changes are admin-API driven; the
   ``/incidents/{id}/status`` route calls :func:`notify_status_change`.
5. **Count increment alone does NOT notify.** Same-band repeats of an
   already-notified incident stay silent.

D12: no Telegram inline keyboard in V1 - ack happens via the admin API.
D5: athlete context is OK in the runtime DM (admin-only, never persisted to
git). D6 (dual-pass redaction) is enforced by ``insert_observation``'s
write-time pass plus :func:`redact_observation_for_emit` on every emit; the
notifier applies the read-time pass before forming the message body so any
pattern that slipped through write-time still gets stripped at the wire.

The notifier never raises - Guardian must never crash its host. All Telegram
errors are logged and dropped.
"""

from __future__ import annotations

import logging
from typing import Any

from bot.services.system_guardian import store as _store
from bot.services.system_guardian.classify import SEVERITY_RANK
from bot.services.system_guardian.normalize import redact_observation_for_emit

logger = logging.getLogger(__name__)


# Single-line severity icons. ASCII so Telegram renders consistently.
_SEVERITY_ICON = {
    "critical": "[CRIT]",
    "warning": "[WARN]",
    "info": "[INFO]",
}


# ---------------------------------------------------------------------------
# Telegram dispatch - thin so tests monkeypatch this single function.
# ---------------------------------------------------------------------------


async def _send_admin_dm(text: str) -> bool:
    """Send a DM to ``ADMIN_TELEGRAM_CHAT_ID``. Returns ``True`` on success.

    Mirrors the direct ``Bot(token=...).send_message`` pattern used by
    ``checkin_service._send_emergency_alert_if_present``. Instantiating a
    fresh ``Bot`` is cheap (no network until ``send_message``).
    """
    try:
        from bot.config import ADMIN_TELEGRAM_CHAT_ID, TELEGRAM_BOT_TOKEN

        if not TELEGRAM_BOT_TOKEN or not ADMIN_TELEGRAM_CHAT_ID:
            logger.warning(
                "guardian.notify: TELEGRAM_BOT_TOKEN / ADMIN_TELEGRAM_CHAT_ID "
                "not configured - skipping DM"
            )
            return False

        from telegram import Bot

        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        await bot.send_message(chat_id=ADMIN_TELEGRAM_CHAT_ID, text=text)
        return True
    except Exception as e:
        logger.error("guardian.notify: send_admin_dm failed: %s", e, exc_info=True)
        return False


# ---------------------------------------------------------------------------
# Message formatters - pure functions, asserted against in tests.
# ---------------------------------------------------------------------------


def _resolve_signal_label(observation: dict, incident: dict) -> str:
    """Pick the human-readable signal label for the DM headline.

    Preference order:

    1. ``observation.metadata.signal`` — set explicitly by Phase 1 collectors.
    2. ``observation.metadata.code`` — set by classify / collectors as the
       stable identifier for the incident class.
    3. ``observation.event_type`` — the original observation kind, fine as a
       fallback but never the FIRST choice because for failure observations
       it's tokens like ``runtime_error`` which mean nothing to the recipient.
    4. ``incident.category`` — last resort.

    The 2026-05-13 bug was that ``_format_incident_line`` used
    ``incident.category`` directly, which defaults to ``runtime_error``
    when an observation arrives without an explicit category. The headline
    on every DM read ``[INFO] runtime_error - ...`` which the human reader
    couldn't tell apart from a real exception. Using the actual signal name
    (e.g. ``research_load_anomaly``) is what the shakedown summary already
    does and what the recipient needs.
    """
    md = observation.get("metadata")
    if isinstance(md, dict):
        sig = md.get("signal") or md.get("code")
        if sig:
            return str(sig)
    et = observation.get("event_type")
    if et:
        return str(et)
    cat = incident.get("category")
    return str(cat) if cat else "incident"


def _format_incident_line(observation: dict, incident: dict) -> str:
    """Single-line DM body for a new/escalated incident.

    Layout (one line, compact for Telegram preview):
    ``[SEV] service:signal - title (count=N) sig=<hash12>``

    The ``service:signal`` prefix mirrors the format of the shakedown
    summary lines (``* signal: detail``) so the recipient sees consistent
    naming across both DM types. Pre-fix the format was ``[SEV] category -
    title`` where ``category`` defaulted to the literal string
    ``runtime_error`` for any observation without an explicit category —
    which read like a bug, not a signal label. See `_resolve_signal_label`.
    """
    safe_obs = redact_observation_for_emit(observation)
    safe_inc = redact_observation_for_emit(incident)

    severity = safe_inc.get("severity") or safe_obs.get("severity_hint") or "info"
    icon = _SEVERITY_ICON.get(severity, "[????]")
    signal = _resolve_signal_label(safe_obs, safe_inc)
    service = (safe_obs.get("service") or safe_inc.get("service") or "").strip()
    label = f"{service}:{signal}" if service else signal
    title = (safe_inc.get("title") or safe_obs.get("message") or "incident").strip()
    if len(title) > 140:
        title = title[:137] + "..."
    count = safe_inc.get("count") or 1
    signature = safe_inc.get("signature") or ""
    sig_tag = signature[:12] if signature else ""
    parts = [f"{icon} {label} - {title} (count={count})"]
    if sig_tag:
        parts.append(f"sig={sig_tag}")
    return " ".join(parts)


def _format_status_change_line(
    incident: dict, prev_status: str, new_status: str, *, note: str | None = None
) -> str:
    """Single-line DM body for a status transition (admin-driven)."""
    safe_inc = redact_observation_for_emit(incident)
    severity = safe_inc.get("severity") or "info"
    icon = _SEVERITY_ICON.get(severity, "[????]")
    title = (safe_inc.get("title") or "incident").strip()
    if len(title) > 100:
        title = title[:97] + "..."
    sig = (safe_inc.get("signature") or "")[:12]
    line = f"{icon} status {prev_status}->{new_status}: {title}"
    if sig:
        line += f" sig={sig}"
    if note:
        n = str(note).strip()
        if len(n) > 80:
            n = n[:77] + "..."
        line += f' note="{n}"'
    return line


def _format_shakedown_summary(
    signatures: list[dict], *, started_at_iso: str | None
) -> str:
    """Multi-line end-of-window summary.

    Groups distinct incident signatures by severity, lists up to 8 per band
    so the message stays under Telegram's 4096-char ceiling.
    """
    header = "System Guardian - shakedown summary"
    if started_at_iso:
        header += f" (window started {started_at_iso})"

    if not signatures:
        return header + "\nNo incidents observed during shakedown."

    by_severity: dict[str, list[dict]] = {"critical": [], "warning": [], "info": []}
    for row in signatures:
        sev = row.get("severity") or "info"
        if sev not in by_severity:
            by_severity[sev] = []
        by_severity[sev].append(row)

    lines = [header]
    for sev in ("critical", "warning", "info"):
        bucket = by_severity.get(sev) or []
        if not bucket:
            continue
        lines.append("")
        lines.append(f"{_SEVERITY_ICON.get(sev, '[????]')} {sev} ({len(bucket)}):")
        for row in bucket[:8]:
            safe = redact_observation_for_emit(row)
            title = (safe.get("title") or "incident").strip()
            if len(title) > 100:
                title = title[:97] + "..."
            count = safe.get("count") or 1
            sig = (safe.get("signature") or "")[:12]
            lines.append(f"  * {title} (count={count}) sig={sig}")
        if len(bucket) > 8:
            lines.append(f"  ... +{len(bucket) - 8} more")

    lines.append("")
    lines.append("Ack: POST /admin/guardian/shakedown/ack to dismiss this window.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def maybe_notify_admin(observation: dict, incident: dict) -> bool:
    """Decide whether to send a Telegram DM for an observation/incident pair.

    Returns ``True`` if a DM was actually sent. Dedup per A6:

    * Rule 1: shakedown active -> no DM.
    * Rule 2: ``incident.last_notified_at is None`` (first occurrence) -> DM.
    * Rule 3: severity band escalated since the previous occurrence -> DM.
      Detected by comparing ``observation["_prev_severity"]`` (set by
      :func:`store.insert_observation_with_notify`) against the post-upsert
      ``incident.severity``.
    * Rule 4: status transition. NOT handled here; the admin status route
      calls :func:`notify_status_change` after the persisted update.
    * Rule 5: same-band count increment -> no DM (default fall-through).
    """
    if observation is None or incident is None:
        return False

    incident_id = incident.get("id")
    if not incident_id:
        # Without an id we cannot persist last_notified_at; skip.
        return False

    # Rule 1: shakedown window suppresses DMs.
    try:
        if _store.is_shakedown_active():
            return False
    except Exception as e:
        # On shakedown lookup failure, dispatch anyway (better to over-notify
        # than to suppress a real alert).
        logger.error(
            "guardian.notify: shakedown check failed, dispatching anyway: %s",
            e,
            exc_info=True,
        )

    # Rule 2: first occurrence.
    last_notified_at = incident.get("last_notified_at")
    if last_notified_at is None:
        sent = await _send_admin_dm(_format_incident_line(observation, incident))
        if sent:
            _store.advance_last_notified_at(
                incident_id, severity=incident.get("severity")
            )
        return sent

    # Rule 3: severity band escalated.
    prev_severity = observation.get("_prev_severity") or "info"
    if prev_severity not in SEVERITY_RANK:
        prev_severity = "info"

    incident_severity = incident.get("severity") or "info"
    if incident_severity not in SEVERITY_RANK:
        incident_severity = "info"

    if SEVERITY_RANK[incident_severity] > SEVERITY_RANK[prev_severity]:
        sent = await _send_admin_dm(_format_incident_line(observation, incident))
        if sent:
            _store.advance_last_notified_at(
                incident_id, severity=incident_severity
            )
        return sent

    # Rule 5: no DM on count-only increment.
    return False


async def notify_status_change(
    incident: dict, prev_status: str, new_status: str, *, note: str | None = None
) -> bool:
    """DM the admin when an incident's status transitions.

    Per A6 rule 4. Called from ``/admin/guardian/incidents/{id}/status``
    after the update is persisted. The status update path already advances
    ``last_notified_at`` via :func:`store.update_incident_status`, so this
    function only handles dispatch.
    """
    if not incident or prev_status == new_status:
        return False
    text = _format_status_change_line(incident, prev_status, new_status, note=note)
    return await _send_admin_dm(text)


def _acknowledge_shakedown_baseline() -> int:
    """Stamp every currently-open incident as "already notified".

    The 2026-05-13 ack-flood fix. During shakedown, observations + incidents
    persist but ``maybe_notify_admin`` returns False, so
    ``advance_last_notified_at`` never gets called on first-occurrence
    incidents. As soon as shakedown ends, every baseline incident still has
    ``last_notified_at IS NULL`` and the next observation re-triggers A6
    rule 2 (first-occurrence DM) for every signature seen during shakedown.

    This helper closes that gap: BEFORE we flip shakedown off, stamp
    ``last_notified_at = now()`` + ``last_notified_severity`` on every open
    incident so the dedup logic treats them as already-notified baseline.
    The actual end-of-window DM is the summary, not per-incident DMs.

    Returns the number of incidents stamped. Never raises.
    """
    stamped = 0
    try:
        open_incidents = _store.list_open_incidents(limit=500)
    except Exception as e:
        logger.error(
            "guardian.notify: list_open_incidents failed during baseline-ack: %s",
            e,
            exc_info=True,
        )
        return 0

    for inc in open_incidents:
        inc_id = inc.get("id")
        if not inc_id:
            continue
        try:
            _store.advance_last_notified_at(
                inc_id, severity=inc.get("severity") or "info"
            )
            stamped += 1
        except Exception as e:
            logger.error(
                "guardian.notify: advance_last_notified_at failed for %s during "
                "baseline-ack: %s",
                inc_id,
                e,
                exc_info=True,
            )
    return stamped


async def send_shakedown_summary() -> None:
    """End-of-window summary DM. Idempotent.

    Triggered by either the manual ack endpoint or the scheduler auto-expire
    hook. Writes a ``shakedown_summary_sent`` self-observation regardless of
    DM success (audit trail), and flips :func:`store.set_shakedown_active`
    to ``False`` if it wasn't already.

    **Ack-flood fix (2026-05-13)**: BEFORE flipping shakedown off, call
    :func:`_acknowledge_shakedown_baseline` to stamp every currently-open
    incident as already-notified. Without that step, all baseline incidents
    accumulated during the 24h window have ``last_notified_at IS NULL``,
    and the very next observation on each signature re-triggers A6 rule 2
    (first-occurrence DM) — producing one Telegram DM per signature seen
    during shakedown. Both the manual ack path and the auto-expire path
    flow through this function so both are covered.

    Order: (1) snapshot the baseline signatures for the summary DM,
    (2) DM the summary, (3) self-observation, (4) baseline-ack the
    incidents, (5) flip shakedown off. The DM-first ordering preserves the
    pre-flip view; the baseline-ack-before-flip ordering ensures that even
    if a tick fires concurrently, it sees ``shakedown_active=True`` until
    the baseline is fully stamped.

    Idempotence: if shakedown is already inactive (no active sentinel), we
    DM with an empty-signature summary noting the close and skip both the
    baseline-ack AND flipping state. Calling twice in a row therefore
    results in two DMs but no double-state-flip; if even the DM is undesired
    on a second call, callers should check
    :func:`store.is_shakedown_active` themselves.
    """
    started_at = _store.get_shakedown_started_at()
    started_at_iso = started_at.isoformat() if started_at is not None else None
    signatures = _store.list_shakedown_signatures() if started_at is not None else []

    text = _format_shakedown_summary(signatures, started_at_iso=started_at_iso)
    sent = await _send_admin_dm(text)

    # Self-observation: shakedown_summary_sent.
    try:
        from datetime import datetime as _dt

        from bot.config import CHICAGO_TZ

        _store.insert_observation(
            {
                "observed_at": _dt.now(CHICAGO_TZ).isoformat(),
                "source": "guardian",
                "service": "shakedown",
                "event_type": "shakedown_summary_sent",
                "severity_hint": "info",
                "surface": "guardian_self",
                "route_or_job": "shakedown_window",
                "message": (
                    f"shakedown_summary_sent: {len(signatures)} signatures "
                    f"(dm_dispatched={sent})"
                ),
                "metadata": {
                    "category": "guardian_self",
                    "code": "shakedown_summary_sent",
                    "signature_count": len(signatures),
                    "dm_dispatched": sent,
                    "started_at": started_at_iso,
                },
            }
        )
    except Exception as e:
        logger.error(
            "guardian.notify: self-observation insert failed: %s", e, exc_info=True
        )

    # Baseline-ack every open incident BEFORE flipping shakedown off.
    # See _acknowledge_shakedown_baseline docstring for the 2026-05-13
    # ack-flood reasoning.
    baseline_stamped = 0
    if started_at is not None:
        try:
            baseline_stamped = _acknowledge_shakedown_baseline()
            logger.info(
                "guardian.notify: shakedown baseline-ack stamped %d open incident(s)",
                baseline_stamped,
            )
        except Exception as e:
            logger.error(
                "guardian.notify: shakedown baseline-ack failed: %s",
                e,
                exc_info=True,
            )

    # Flip the flag off when there was an active window.
    try:
        if started_at is not None:
            _store.set_shakedown_active(False)
    except Exception as e:
        logger.error(
            "guardian.notify: set_shakedown_active(False) failed: %s",
            e,
            exc_info=True,
        )


__all__ = [
    "maybe_notify_admin",
    "notify_status_change",
    "send_shakedown_summary",
    "_acknowledge_shakedown_baseline",
]
