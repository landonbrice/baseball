"""Integration tests for POST /api/programs/{program_id}/recompute (Plan 6 / A5).

Verifies:
- 404 when program doesn't exist or belongs to another pitcher
- server-reads scheduled_throws from pitcher_training_model
- maps `type` → `kind` for the anchoring shim
- no-op when schedule unchanged (no write, no override event)
- writes schedule + override event when days shift
- the override event payload includes days_shifted count
- response shape on both paths
"""
from datetime import date, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("DISABLE_AUTH", "true")
    from api import routes as routes_mod
    monkeypatch.setattr(routes_mod, "DISABLE_AUTH", True)
    from api.main import app
    return TestClient(app)


PID = "landon_brice"
PROG_ID = "prog-uuid-1"


def _anchor_program(start_date="2026-05-01", current_day_index=0):
    """Anchor-relative program where day 0 is T-3 from next bullpen."""
    sd = date.fromisoformat(start_date)
    days = []
    pattern = [
        ("T-3_from_next_bullpen", "high_effort_plyo"),
        ("T-2_from_next_bullpen", "moderate_plyo"),
        ("T-1_from_next_bullpen", "rest"),
        ("bullpen_day", "bullpen"),
    ]
    for i in range(14):
        ak, tk = pattern[i % len(pattern)]
        days.append({
            "day_index": i,
            "template_key": tk,
            "date": (sd + timedelta(days=i)).isoformat(),
            "anchor_kind": ak,
        })
    return {
        "program_id": PROG_ID,
        "pitcher_id": PID,
        "current_day_index": current_day_index,
        "generated_schedule_json": {
            "scaffold_kind": "anchor_relative",
            "days": days,
        },
    }


def _calendar_program():
    """Calendar-relative — recompute is always a no-op."""
    days = [
        {"day_index": i, "template_key": f"day_{i%7}", "date": f"2026-05-{(i%30)+1:02d}"}
        for i in range(14)
    ]
    return {
        "program_id": PROG_ID,
        "pitcher_id": PID,
        "current_day_index": 0,
        "generated_schedule_json": {
            "scaffold_kind": "calendar_relative_repeating_7day",
            "days": days,
        },
    }


def test_recompute_404_when_program_missing(client):
    from bot.services import db as _db
    with patch.object(_db, "get_program", return_value=None):
        resp = client.post(f"/api/programs/{PROG_ID}/recompute",
                           headers={"X-Test-Pitcher-Id": PID})
    assert resp.status_code == 404
    assert resp.json()["detail"] == "program not found"


def test_recompute_404_when_wrong_pitcher(client):
    """Cross-pitcher access returns 404 (existence stays opaque)."""
    from bot.services import db as _db
    program = _anchor_program()
    program["pitcher_id"] = "someone_else"
    with patch.object(_db, "get_program", return_value=program):
        resp = client.post(f"/api/programs/{PROG_ID}/recompute",
                           headers={"X-Test-Pitcher-Id": PID})
    assert resp.status_code == 404


def test_recompute_noop_for_calendar_relative(client):
    """Calendar-relative templates — recompute returns updated=False, no writes."""
    from bot.services import db as _db
    program = _calendar_program()
    with patch.object(_db, "get_program", return_value=program), \
         patch.object(_db, "get_pitcher_scheduled_throws",
                      return_value=[{"date": "2026-05-15", "type": "bullpen"}]), \
         patch.object(_db, "update_program_schedule") as upd, \
         patch.object(_db, "insert_override_event") as ovr:
        resp = client.post(f"/api/programs/{PROG_ID}/recompute",
                           headers={"X-Test-Pitcher-Id": PID})
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"updated": False, "days_shifted": 0, "schedule": None}
    upd.assert_not_called()
    ovr.assert_not_called()


def test_recompute_noop_when_no_future_throws(client):
    """Anchor-relative program but no scheduled throws — days don't move."""
    from bot.services import db as _db
    program = _anchor_program()
    with patch.object(_db, "get_program", return_value=program), \
         patch.object(_db, "get_pitcher_scheduled_throws", return_value=[]), \
         patch.object(_db, "update_program_schedule") as upd, \
         patch.object(_db, "insert_override_event") as ovr:
        resp = client.post(f"/api/programs/{PROG_ID}/recompute",
                           headers={"X-Test-Pitcher-Id": PID})
    assert resp.status_code == 200
    assert resp.json()["updated"] is False
    upd.assert_not_called()
    ovr.assert_not_called()


def test_recompute_shifts_days_and_writes_everything(client):
    """Adding a future bullpen 5 days out shifts the T-3/T-2/T-1 ladder around it."""
    from bot.services import db as _db
    program = _anchor_program(start_date="2026-05-01")
    # Schedule a bullpen on day-6 (was day-3 in original pattern). T-N days slide.
    throws = [{"date": "2026-05-07", "type": "bullpen"}]
    with patch.object(_db, "get_program", return_value=program), \
         patch.object(_db, "get_pitcher_scheduled_throws", return_value=throws), \
         patch.object(_db, "update_program_schedule") as upd, \
         patch.object(_db, "insert_override_event") as ovr:
        resp = client.post(f"/api/programs/{PROG_ID}/recompute",
                           headers={"X-Test-Pitcher-Id": PID})
    assert resp.status_code == 200
    body = resp.json()
    assert body["updated"] is True
    assert body["days_shifted"] > 0
    assert body["schedule"] is not None
    assert "days" in body["schedule"]
    # Writes happen exactly once each
    upd.assert_called_once()
    upd_args = upd.call_args
    assert upd_args.args[0] == PROG_ID
    assert upd_args.kwargs.get("trigger_type") == "anchor_recompute"
    ovr.assert_called_once()
    ovr_kwargs = ovr.call_args.kwargs
    assert ovr_kwargs["pitcher_id"] == PID
    assert ovr_kwargs["program_id"] == PROG_ID
    assert ovr_kwargs["event_kind"] == "schedule_recompute"
    assert ovr_kwargs["details"]["trigger"] == "scheduled_throw_change"
    assert ovr_kwargs["details"]["days_shifted"] == body["days_shifted"]


def test_recompute_maps_type_to_kind_for_anchoring(client):
    """weekly_model stores `type`; program_anchoring reads `kind`. Route must shim."""
    from bot.services import db as _db
    from bot.services import program_anchoring as anchoring
    program = _anchor_program()
    throws_raw = [{"date": "2026-05-07", "type": "bullpen"}]
    with patch.object(_db, "get_program", return_value=program), \
         patch.object(_db, "get_pitcher_scheduled_throws", return_value=throws_raw), \
         patch.object(anchoring, "recompute_program_schedule",
                      wraps=anchoring.recompute_program_schedule) as wrapped, \
         patch.object(_db, "update_program_schedule"), \
         patch.object(_db, "insert_override_event"):
        client.post(f"/api/programs/{PROG_ID}/recompute",
                    headers={"X-Test-Pitcher-Id": PID})
    # Verify the shimmed `kind`-keyed throws were passed through
    call_throws = wrapped.call_args.args[1]
    assert call_throws == [{"date": "2026-05-07", "kind": "bullpen"}]


def test_recompute_drops_malformed_throws(client):
    """Throws missing date or type are filtered out before reaching the anchoring fn."""
    from bot.services import db as _db
    from bot.services import program_anchoring as anchoring
    program = _anchor_program()
    throws_raw = [
        {"date": "2026-05-07", "type": "bullpen"},  # valid
        {"date": None, "type": "bullpen"},          # bad date
        {"date": "2026-05-08"},                     # missing type
        {"type": "outing"},                          # missing date
    ]
    with patch.object(_db, "get_program", return_value=program), \
         patch.object(_db, "get_pitcher_scheduled_throws", return_value=throws_raw), \
         patch.object(anchoring, "recompute_program_schedule",
                      wraps=anchoring.recompute_program_schedule) as wrapped, \
         patch.object(_db, "update_program_schedule"), \
         patch.object(_db, "insert_override_event"):
        client.post(f"/api/programs/{PROG_ID}/recompute",
                    headers={"X-Test-Pitcher-Id": PID})
    call_throws = wrapped.call_args.args[1]
    assert call_throws == [{"date": "2026-05-07", "kind": "bullpen"}]


def test_recompute_requires_auth(client, monkeypatch):
    from api import routes as routes_mod
    monkeypatch.setattr(routes_mod, "DISABLE_AUTH", False)
    resp = client.post(f"/api/programs/{PROG_ID}/recompute")
    assert resp.status_code == 401
