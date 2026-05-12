"""Signature generation + clustering per spec §13.

A signature is a deterministic ≤64-char string that collapses repeated
occurrences of the same logical event into a single incident row.
``system_incidents.signature`` has a unique constraint, so the same signature
must always come from the same logical event regardless of timestamp,
pitcher_id specifics, request IDs, or other volatile parts.

Strategy:

1. Build a tuple ``(category, code, normalized_subject)`` where
   ``normalized_subject`` is the route/job/error_class with volatile
   substrings stripped (UUIDs, request IDs, large integer IDs, ISO
   timestamps, etc).
2. Hash the tuple with SHA-1 and base32-encode the first 12 bytes — gives a
   ~20-char body. Prefix with a short category tag for readability.
3. Total length stays ≤64 chars even with the prefix.
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from typing import Any, Iterable

# ---------------------------------------------------------------------------
# Volatile-substring stripping
# ---------------------------------------------------------------------------

# These get replaced with ``*`` before hashing so that
# "pitcher pitcher_kamat_001 missing whoop pull" and
# "pitcher pitcher_richert_001 missing whoop pull" hash to the same signature.
_VOLATILE_PATTERNS: list[re.Pattern[str]] = [
    # UUIDs
    re.compile(
        r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
    ),
    # ISO 8601 timestamps (with or without timezone).
    re.compile(r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?\b"),
    # ISO date-only (e.g. 2026-04-30).
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    # pitcher_id-like tokens (snake_case ending in _\d+ or with _001 suffix).
    re.compile(r"\bpitcher_[a-z]+_\d+\b"),
    # Bare large integers (request IDs, row counts > 4 digits).
    re.compile(r"\b\d{4,}\b"),
    # ``request_id=<value>``-shaped fragments.
    re.compile(r"(request_id|req_id|trace_id)\s*[:=]\s*\S+", re.IGNORECASE),
]


def _strip_volatile(text: str | None) -> str:
    if not text:
        return ""
    out = text
    for pattern in _VOLATILE_PATTERNS:
        out = pattern.sub("*", out)
    # Collapse runs of whitespace and lowercase for stable hashing.
    out = re.sub(r"\s+", " ", out).strip().lower()
    return out


def _category_prefix(category: str | None) -> str:
    if not category:
        return "obs"
    # Strip non-alphanum, lowercase, cap at 12 chars so the total signature
    # body fits comfortably under 64.
    cleaned = re.sub(r"[^a-z0-9]+", "_", (category or "").lower()).strip("_")
    return cleaned[:12] or "obs"


def generate_signature(observation: dict) -> str:
    """Return a deterministic signature ≤64 chars.

    Keys consulted, in priority order:

    * ``category`` (also drives the human-readable prefix)
    * ``code`` — a short stable string the caller can supply (e.g.
      ``llm_enrichment_below_60pct``). Falls back to ``event_type``.
    * ``route_or_job`` and ``error_class`` — used as the normalized subject.
      If both are missing, the message is normalized as a fallback.

    Callers SHOULD supply a ``code`` for stability across message changes,
    but the function works without one.
    """
    category = (observation.get("category") or observation.get("severity_hint") or "").strip()
    code = (observation.get("code") or observation.get("event_type") or "").strip().lower()
    route = (observation.get("route_or_job") or "").strip().lower()
    err = (observation.get("error_class") or "").strip().lower()
    msg = observation.get("message") or ""

    subject = " ".join([route, err]).strip()
    if not subject:
        subject = _strip_volatile(msg)
    else:
        subject = _strip_volatile(subject)

    # Build the tuple and hash.
    payload = "|".join([category.lower(), code, subject])
    digest = hashlib.sha1(payload.encode("utf-8")).digest()
    # base32 of 12 bytes → 20 chars (with no padding for that exact length).
    import base64
    body = base64.b32encode(digest[:12]).decode("ascii").lower().rstrip("=")

    prefix = _category_prefix(category)
    sig = f"{prefix}_{body}"
    if len(sig) > 64:
        sig = sig[:64]
    return sig


def cluster_observations(
    observations: Iterable[dict],
) -> dict[str, list[dict]]:
    """Group observations by signature.

    Used by the digest formatter (PR-3+) to render "this signature fired N
    times" rather than dumping every raw row. Signature is read from each
    observation; if missing, it's generated on the fly.
    """
    grouped: dict[str, list[dict]] = defaultdict(list)
    for obs in observations:
        sig = obs.get("signature") or generate_signature(obs)
        grouped[sig].append(obs)
    return dict(grouped)


__all__ = ["generate_signature", "cluster_observations"]
