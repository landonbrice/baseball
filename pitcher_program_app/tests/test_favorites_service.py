"""Unit tests for bot.services.favorites (Plan 6 / A2).

Mocks the db helpers; verifies validation + ownership semantics.
"""
from datetime import date
from unittest.mock import patch

import pytest

from bot.services import favorites as favorites_svc


PID = "landon_brice"
SNAPSHOT = {"exercises": [{"name": "Bench", "sets": 3, "reps": 5}]}


def test_create_favorite_inserts_with_self_source():
    inserted = {
        "favorite_id": "fav-1",
        "pitcher_id": PID,
        "source_pitcher_id": PID,
        "source_entry_date": "2026-05-12",
        "block_type": "lifting",
        "block_snapshot_json": SNAPSHOT,
        "note": None,
    }
    with patch("bot.services.favorites._db.insert_favorited_block", return_value=inserted) as ins:
        out = favorites_svc.create_favorite(
            pitcher_id=PID,
            block_type="lifting",
            source_entry_date="2026-05-12",
            block_snapshot=SNAPSHOT,
        )
    assert out == inserted
    row = ins.call_args[0][0]
    assert row["pitcher_id"] == PID
    assert row["source_pitcher_id"] == PID  # self-source enforcement
    assert row["source_entry_date"] == "2026-05-12"
    assert row["block_type"] == "lifting"
    assert row["block_snapshot_json"] == SNAPSHOT
    assert "note" not in row  # omitted when None — let DB default


def test_create_favorite_with_note_includes_it():
    with patch("bot.services.favorites._db.insert_favorited_block", return_value={"favorite_id": "x"}) as ins:
        favorites_svc.create_favorite(
            pitcher_id=PID, block_type="arm_care", source_entry_date="2026-05-12",
            block_snapshot=SNAPSHOT, note="loved this one",
        )
    assert ins.call_args[0][0]["note"] == "loved this one"


def test_create_favorite_accepts_date_object():
    with patch("bot.services.favorites._db.insert_favorited_block", return_value={"favorite_id": "x"}) as ins:
        favorites_svc.create_favorite(
            pitcher_id=PID, block_type="lifting",
            source_entry_date=date(2026, 5, 12),
            block_snapshot=SNAPSHOT,
        )
    assert ins.call_args[0][0]["source_entry_date"] == "2026-05-12"


def test_create_favorite_rejects_bad_block_type():
    with pytest.raises(favorites_svc.FavoritesError):
        favorites_svc.create_favorite(
            pitcher_id=PID, block_type="mobility",  # not in ALLOWED_BLOCK_TYPES
            source_entry_date="2026-05-12", block_snapshot=SNAPSHOT,
        )


def test_create_favorite_rejects_empty_snapshot():
    with pytest.raises(favorites_svc.FavoritesError):
        favorites_svc.create_favorite(
            pitcher_id=PID, block_type="lifting",
            source_entry_date="2026-05-12", block_snapshot={},
        )


def test_create_favorite_rejects_bad_date_format():
    with pytest.raises(favorites_svc.FavoritesError):
        favorites_svc.create_favorite(
            pitcher_id=PID, block_type="lifting",
            source_entry_date="5/12/2026", block_snapshot=SNAPSHOT,
        )


def test_list_favorites_passes_type_filter_through():
    rows = [{"favorite_id": "f1"}, {"favorite_id": "f2"}]
    with patch("bot.services.favorites._db.list_favorited_blocks", return_value=rows) as lst:
        out = favorites_svc.list_favorites(PID, block_type="lifting")
    assert out == rows
    lst.assert_called_once_with(PID, "lifting")


def test_list_favorites_no_filter():
    with patch("bot.services.favorites._db.list_favorited_blocks", return_value=[]) as lst:
        favorites_svc.list_favorites(PID)
    lst.assert_called_once_with(PID, None)


def test_list_favorites_rejects_bad_type():
    with pytest.raises(favorites_svc.FavoritesError):
        favorites_svc.list_favorites(PID, block_type="cardio")


def test_delete_favorite_deletes_when_owner_matches():
    row = {"favorite_id": "fav-1", "pitcher_id": PID, "block_type": "lifting"}
    with patch("bot.services.favorites._db.get_favorited_block", return_value=row), \
         patch("bot.services.favorites._db.delete_favorited_block") as dl:
        favorites_svc.delete_favorite(PID, "fav-1")
    dl.assert_called_once_with("fav-1")


def test_delete_favorite_raises_when_missing():
    with patch("bot.services.favorites._db.get_favorited_block", return_value=None), \
         patch("bot.services.favorites._db.delete_favorited_block") as dl:
        with pytest.raises(favorites_svc.FavoriteNotFound):
            favorites_svc.delete_favorite(PID, "missing")
    dl.assert_not_called()


def test_delete_favorite_raises_when_owned_by_another_pitcher():
    row = {"favorite_id": "fav-1", "pitcher_id": "other_pitcher"}
    with patch("bot.services.favorites._db.get_favorited_block", return_value=row), \
         patch("bot.services.favorites._db.delete_favorited_block") as dl:
        with pytest.raises(favorites_svc.FavoriteNotFound):
            favorites_svc.delete_favorite(PID, "fav-1")
    dl.assert_not_called()
