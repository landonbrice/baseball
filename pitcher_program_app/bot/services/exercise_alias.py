"""Exercise canonical-name → id resolver (Program Engine Task 0.1).

The `exercises` table already carries an `aliases` jsonb column on every row.
This module is a thin name-normalizing index OVER that column — it is NOT a
separate source of truth.

The guardrail plane (Task 2.3, content invariants #7) calls `resolve_alias` on
every exercise reference in an authored program. Unknown names raise
`UnknownExerciseAlias` so the validate→repair→reject loop fails hard with the
offending name surfaced.

Why a Supabase read instead of a hand-curated JSON: when this module was being
spec'd the assumption was that aliases didn't exist yet; recon Front 3 said the
golden content "doesn't reconcile" with the exercises table. A live check on
2026-06-01 found `exercises.aliases` populated for all 159 rows with high
coverage of the golden content (e.g. ex_004 RFESS already aliases Bulgarian
split squat; ex_020 Chest-Supported Row already aliases seal row). Maintaining
a duplicate JSON would create a sync problem; the Supabase column is the
canonical store, and Phase 0.1 reduces to (a) this resolver, (b) an audit
script that surfaces gaps, (c) adding missing aliases via Supabase update.
"""

from __future__ import annotations

import logging
import re
from typing import Iterable

from bot.services.db import get_exercises

logger = logging.getLogger(__name__)


class UnknownExerciseAlias(Exception):
    """No `exercises` row matches the given name (canonical or alias).

    Phase 2.3 (guardrail #7 — exercise IDs resolve) treats this as a fatal
    violation that cannot be repaired in the validate loop; the orchestrator
    re-prompts the LLM with the offending name.
    """

    def __init__(self, name: str):
        super().__init__(f"unresolved exercise alias: {name!r}")
        self.name = name


_NORM_PUNCT_RE = re.compile(r"[^\w\s]")
_NORM_SPACE_RE = re.compile(r"\s+")


def _normalize(name: str) -> str:
    """Case-fold + strip punctuation + collapse whitespace.

    Used as the lookup key for both canonical names and aliases. The normalization
    is intentionally lossy (drops parentheticals, hyphens, ampersands) so
    `'Chest-Supported Row'` and `'chest supported row'` collide.
    """
    if not isinstance(name, str):
        raise UnknownExerciseAlias(repr(name))
    s = name.strip()
    if not s:
        raise UnknownExerciseAlias(name)
    s = _NORM_PUNCT_RE.sub(" ", s).lower()
    s = _NORM_SPACE_RE.sub(" ", s).strip()
    return s


_ALIAS_INDEX: dict[str, str] = {}
_INDEX_BUILT_FROM: int = 0  # row count last index was built from; 0 = not built
_BUILD_ATTEMPTED_AND_FAILED: bool = False  # latch so we don't log on every retry


def _build_index_from_rows(rows: list[dict]) -> None:
    """Lower-level: build the index from an explicit row list (no I/O)."""
    global _ALIAS_INDEX, _INDEX_BUILT_FROM
    index: dict[str, str] = {}
    for row in rows:
        ex_id = row.get("id")
        if not ex_id:
            continue
        name = row.get("name")
        if name:
            try:
                index[_normalize(name)] = ex_id
            except UnknownExerciseAlias:
                pass
        for alias in row.get("aliases") or []:
            if not isinstance(alias, str):
                continue
            try:
                index[_normalize(alias)] = ex_id
            except UnknownExerciseAlias:
                pass
    _ALIAS_INDEX = index
    _INDEX_BUILT_FROM = len(rows)


def load_from_snapshot(path: str) -> None:
    """Seed the index from a JSON snapshot file instead of Supabase.

    Used by the audit script when running in an environment without
    SUPABASE_URL / SUPABASE_SERVICE_KEY (e.g. cleanroom checkouts). The
    snapshot shape is `{"rows": [{"id":..., "name":..., "aliases":[...]}, ...]}`.
    """
    import json
    with open(path) as f:
        data = json.load(f)
    rows = data.get("rows") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise ValueError(f"snapshot {path}: expected dict with 'rows' or top-level list")
    _build_index_from_rows(rows)
    global _BUILD_ATTEMPTED_AND_FAILED
    _BUILD_ATTEMPTED_AND_FAILED = False
    logger.info("alias index loaded from snapshot %s: %d rows", path, len(rows))


def _build_index() -> None:
    """Walk live `exercises` rows and build the normalized name → id map.

    Indexes both the canonical `name` and every entry in `aliases`. Aliases
    win on collision (later overrides earlier) because aliases are the
    explicit operator-curated mapping. Practical collisions are rare; if one
    matters the audit script catches it.
    """
    global _BUILD_ATTEMPTED_AND_FAILED
    try:
        rows = get_exercises()
    except Exception as exc:
        if not _BUILD_ATTEMPTED_AND_FAILED:
            logger.warning("alias index build failed, keeping last-good: %s", exc)
            _BUILD_ATTEMPTED_AND_FAILED = True
        return
    _BUILD_ATTEMPTED_AND_FAILED = False
    _build_index_from_rows(rows)
    logger.info("alias index built from %d exercises (%d normalized keys)", len(rows), len(_ALIAS_INDEX))


def resolve_alias(name: str) -> str:
    """Return canonical exercise id for `name`.

    Lazy-builds the index on first call. Raises `UnknownExerciseAlias` on miss.
    Callers in the guardrail plane use the exception's `.name` attribute to
    surface the offending string in the re-prompt to the LLM.
    """
    if not _ALIAS_INDEX:
        _build_index()
    key = _normalize(name)
    hit = _ALIAS_INDEX.get(key)
    if hit is None:
        raise UnknownExerciseAlias(name)
    return hit


def try_resolve_alias(name: str) -> str | None:
    """Non-raising variant. Returns None on miss. Audit script uses this."""
    try:
        return resolve_alias(name)
    except UnknownExerciseAlias:
        return None


def refresh_index() -> None:
    """Force rebuild on next resolve. Call after Supabase alias edits."""
    global _ALIAS_INDEX, _INDEX_BUILT_FROM
    _ALIAS_INDEX = {}
    _INDEX_BUILT_FROM = 0


def audit_names(names: Iterable[str]) -> dict[str, list[str]]:
    """Bulk classify a sequence of names into resolved vs unresolved.

    Returns {'resolved': [name, ...], 'unresolved': [name, ...]}.
    Used by `scripts/audit_golden_alias_coverage.py`.
    """
    if not _ALIAS_INDEX:
        _build_index()
    resolved: list[str] = []
    unresolved: list[str] = []
    seen: set[str] = set()
    for raw in names:
        if not isinstance(raw, str):
            continue
        s = raw.strip()
        if not s:
            continue
        try:
            key = _normalize(s)
        except UnknownExerciseAlias:
            continue
        if key in seen:
            continue
        seen.add(key)
        if key in _ALIAS_INDEX:
            resolved.append(s)
        else:
            unresolved.append(s)
    return {"resolved": resolved, "unresolved": unresolved}
