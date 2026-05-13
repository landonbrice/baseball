"""Favorited blocks service (Plan 6 / A2).

Thin domain layer over `favorited_blocks`. The table holds an immutable per-block
snapshot — once written, a row is never updated. Re-use renders the snapshot
as-is; there is no "current value" follow-through.

Source ref is the Plan 1 corrected shape: `(source_pitcher_id, source_entry_date)`
rather than a `daily_entries.id` FK (daily_entries has a composite PK).

For v1, `source_pitcher_id` is required to equal the authenticated `pitcher_id`
— pitchers can only favorite their own blocks. Cross-pitcher copy is deferred.
"""
from __future__ import annotations

from datetime import date as _date

from bot.services import db as _db

ALLOWED_BLOCK_TYPES = {"lifting", "arm_care", "throwing", "warmup"}


class FavoritesError(ValueError):
    """Validation error in the favorites service. Routes translate to HTTP 400."""


class FavoriteNotFound(LookupError):
    """Favorite row not found or not owned by the caller. Routes translate to 404."""


def _coerce_entry_date(value) -> str:
    """Accept `YYYY-MM-DD` string or `date`; return ISO string."""
    if isinstance(value, _date):
        return value.isoformat()
    if isinstance(value, str) and len(value) == 10 and value[4] == "-" and value[7] == "-":
        return value
    raise FavoritesError("source_entry_date must be a YYYY-MM-DD string")


def create_favorite(
    pitcher_id: str,
    block_type: str,
    source_entry_date,
    block_snapshot: dict,
    *,
    note: str | None = None,
) -> dict:
    """Insert a favorited block. Returns the inserted row including `favorite_id`.

    `source_pitcher_id` is set to `pitcher_id` (v1 self-source enforcement).
    """
    if block_type not in ALLOWED_BLOCK_TYPES:
        raise FavoritesError(
            f"block_type must be one of {sorted(ALLOWED_BLOCK_TYPES)}, got {block_type!r}"
        )
    if not isinstance(block_snapshot, dict) or not block_snapshot:
        raise FavoritesError("block_snapshot must be a non-empty object")
    entry_date = _coerce_entry_date(source_entry_date)

    row = {
        "pitcher_id": pitcher_id,
        "source_pitcher_id": pitcher_id,
        "source_entry_date": entry_date,
        "block_type": block_type,
        "block_snapshot_json": block_snapshot,
    }
    if note is not None:
        row["note"] = note

    return _db.insert_favorited_block(row)


def list_favorites(pitcher_id: str, block_type: str | None = None) -> list[dict]:
    """Return this pitcher's favorites, newest first. Optional block_type filter."""
    if block_type is not None and block_type not in ALLOWED_BLOCK_TYPES:
        raise FavoritesError(
            f"block_type must be one of {sorted(ALLOWED_BLOCK_TYPES)}, got {block_type!r}"
        )
    return _db.list_favorited_blocks(pitcher_id, block_type)


def delete_favorite(pitcher_id: str, favorite_id: str) -> None:
    """Delete a favorite owned by `pitcher_id`.

    Raises FavoriteNotFound if the row doesn't exist or is owned by someone else
    (404 keeps existence opaque — same pattern as builder-session endpoints).
    """
    row = _db.get_favorited_block(favorite_id)
    if not row or row.get("pitcher_id") != pitcher_id:
        raise FavoriteNotFound("favorite not found")
    _db.delete_favorited_block(favorite_id)
