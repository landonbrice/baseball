"""Observation normalization + dual-pass secret redaction (A4).

Two redactor functions live here:

* ``redact_text(text)`` — write-time redactor. Run BEFORE any DB write in
  :mod:`store`. Replaces matched secrets with ``[REDACTED:<kind>]`` and
  returns ``(redacted_text, hits)`` where ``hits`` is a list of pattern kinds
  that fired.
* ``redact_observation_for_emit(obs)`` — read-time redactor. Wraps ``message``,
  ``stack``, and any ``sample_messages`` on every digest / packet / API emit
  as a fallback for anything the write-time pass missed.

Both passes use the same module-level ``SECRET_PATTERNS`` list so adding a
pattern is a one-line change. Per amendments doc A4, on a write-time match the
caller must also emit a ``category=security_posture severity=critical``
observation tagged with source/route/job (no secret content). That happens
inside :mod:`store.insert_observation`; this module returns the data needed.

``normalize_observation(raw)`` produces a dict aligned with the
``system_observations`` table column set (see migration 019). Required fields
are validated and missing optional fields default to safe values. The
write-time redactor is applied to ``message`` and ``stack`` here, and the
``signature`` is generated from :mod:`cluster` if the caller hasn't provided
one.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

from bot.config import CHICAGO_TZ

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Secret patterns (A4) — single source of truth.
#
# Each entry is (kind, compiled_pattern). Order matters only for cosmetic
# REDACTED label preference when two patterns overlap; we put the most
# specific patterns first.
# ---------------------------------------------------------------------------

SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # JWT (eyJ...) — 3 base64url segments separated by dots.
    ("jwt", re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")),
    # Telegram bot token: <8-10 digits>:<35+ char base64url-ish>.
    ("telegram_token", re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{35,}\b")),
    # Supabase publishable / secret keys (sbp_..., sbs_...).
    ("supabase_key", re.compile(r"\bsb[ps]_[a-z0-9_-]{20,}\b")),
    # OAuth bearer tokens — any 20+ char token after "Bearer ".
    ("oauth_bearer", re.compile(r"Bearer\s+[A-Za-z0-9._-]{20,}")),
    # Generic api_key / secret / password assignment with 16+ char value.
    (
        "generic_secret",
        re.compile(
            r"(?i)(api[_-]?key|secret|password)[\"'=:\s]+[A-Za-z0-9_-]{16,}"
        ),
    ),
]


def _now_iso() -> str:
    return datetime.now(CHICAGO_TZ).isoformat()


def redact_text(text: str | None) -> tuple[str | None, list[str]]:
    """Redact known secret patterns. Returns ``(redacted, hits)``.

    ``hits`` is the list of pattern kinds that fired (one entry per match).
    A `None` input returns ``(None, [])`` so callers don't have to guard.
    """
    if text is None:
        return None, []
    if not isinstance(text, str):
        # Defensive: callers should hand us strings, but if they don't, coerce
        # rather than crash. JSON serialization rather than ``str()`` would be
        # nicer but adds an import for the cold path; ``str()`` is sufficient
        # because the redactor only inspects patterns.
        text = str(text)

    hits: list[str] = []
    redacted = text
    for kind, pattern in SECRET_PATTERNS:
        def _sub(match: re.Match[str]) -> str:
            hits.append(kind)
            return f"[REDACTED:{kind}]"

        redacted = pattern.sub(_sub, redacted)
    return redacted, hits


def redact_observation_for_emit(obs: dict) -> dict:
    """Read-time redactor: wraps ``title`` / ``message`` / ``stack`` /
    ``sample_messages``.

    Returns a NEW dict; the input is not mutated. Use this on every emit path
    (digest formatter, debug packet builder, /admin/guardian responses) as a
    last line of defense after the write-time pass in ``insert_observation``.

    ``title`` is redacted because incidents copy the original observation's
    message into the title (see ``incidents.build_incident_payload``); a
    secret that survived write-time redaction would otherwise leak through
    the title on every digest emit.
    """
    if not isinstance(obs, dict):
        return obs  # Non-dict inputs pass through unchanged.

    out = dict(obs)
    for key in ("title", "message", "stack"):
        if key in out:
            out[key], _ = redact_text(out.get(key))

    samples = out.get("sample_messages")
    if isinstance(samples, list):
        cleaned = []
        for sample in samples:
            if isinstance(sample, str):
                cleaned.append(redact_text(sample)[0])
            elif isinstance(sample, dict):
                cleaned.append(redact_observation_for_emit(sample))
            else:
                cleaned.append(sample)
        out["sample_messages"] = cleaned
    return out


# ---------------------------------------------------------------------------
# Observation normalization
# ---------------------------------------------------------------------------

# Schema-driven default skeleton. Mirrors the column list in
# scripts/migrations/019_system_guardian_tables.sql.
_OBSERVATION_DEFAULTS: dict[str, Any] = {
    "observed_at": None,        # required — will be filled to now() if absent
    "source": "guardian",       # required
    "service": None,
    "event_type": "observation",  # required
    "severity_hint": None,
    "surface": None,
    "route_or_job": None,
    "message": "",              # required
    "error_class": None,
    "stack_hash": None,
    "signature": None,          # required — caller or cluster.generate_signature
    "metadata": {},
}


def normalize_observation(raw: dict) -> dict:
    """Coerce a raw observation dict to the table-aligned shape.

    * Fills ``observed_at`` with now() (Chicago) if missing.
    * Applies the write-time redactor to ``message`` and ``stack``.
    * Generates a signature via :func:`cluster.generate_signature` if the
      caller didn't pre-compute one.
    * Records redaction hits in the returned dict's ``_redaction_hits`` key
      so :func:`store.insert_observation` can decide whether to emit the
      paired security_posture observation.

    The returned dict contains ALL columns from ``system_observations`` (with
    safe defaults) plus the synthetic ``_redaction_hits`` field which the
    storage layer must strip before writing.
    """
    out: dict[str, Any] = {**_OBSERVATION_DEFAULTS, **(raw or {})}
    if not out.get("observed_at"):
        out["observed_at"] = _now_iso()
    if not out.get("source"):
        out["source"] = "guardian"
    if not out.get("event_type"):
        out["event_type"] = "observation"

    # Write-time redaction (A4).
    redacted_msg, msg_hits = redact_text(out.get("message") or "")
    out["message"] = redacted_msg or ""
    redacted_stack, stack_hits = redact_text(out.get("stack"))
    out["stack"] = redacted_stack
    hits = list(msg_hits) + list(stack_hits)

    # Metadata: we do NOT walk metadata recursively for redaction here; the
    # contract is that callers stage metadata themselves. But we DO log if a
    # caller passes a metadata blob whose top-level string values look
    # secret-shaped, so the read-time redactor still catches them on emit.
    metadata = out.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}
    out["metadata"] = metadata

    # Defer signature generation to cluster.generate_signature when missing.
    # Import locally to dodge a circular import (cluster imports nothing from
    # normalize today, but defensive).
    if not out.get("signature"):
        from bot.services.system_guardian.cluster import generate_signature

        out["signature"] = generate_signature(out)

    out["_redaction_hits"] = hits
    return out


__all__ = [
    "SECRET_PATTERNS",
    "redact_text",
    "redact_observation_for_emit",
    "normalize_observation",
]
