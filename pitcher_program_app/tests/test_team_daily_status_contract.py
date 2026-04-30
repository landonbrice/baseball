from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class _Response:
    def __init__(self, data):
        self.data = data


class _NotFilter:
    def __init__(self, query):
        self.query = query

    def is_(self, field, value):
        self.query.filters.append(("not_is", field, value))
        return self.query


class _Query:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.filters = []
        self.not_ = _NotFilter(self)

    def select(self, *args, **kwargs):
        return self

    def eq(self, field, value):
        self.filters.append(("eq", field, value))
        return self

    def gte(self, field, value):
        self.filters.append(("gte", field, value))
        return self

    def lte(self, field, value):
        self.filters.append(("lte", field, value))
        return self

    def in_(self, field, values):
        self.filters.append(("in", field, values))
        return self

    def order(self, *args, **kwargs):
        return self

    def execute(self):
        self.client.queries.append((self.table_name, list(self.filters)))
        rows = list(self.client.rows.get(self.table_name, []))
        for op, field, value in self.filters:
            if op == "eq":
                rows = [r for r in rows if r.get(field) == value]
            elif op == "gte":
                rows = [r for r in rows if r.get(field) is not None and r.get(field) >= value]
            elif op == "lte":
                rows = [r for r in rows if r.get(field) is not None and r.get(field) <= value]
            elif op == "in":
                rows = [r for r in rows if r.get(field) in value]
            elif op == "not_is" and value == "null":
                rows = [r for r in rows if r.get(field) is not None]
        return _Response(rows)


class _Client:
    def __init__(self, rows):
        self.rows = rows
        self.queries = []

    def table(self, table_name):
        return _Query(self, table_name)


def _rows(today="2026-04-30"):
    return {
        "pitchers": [
            {"pitcher_id": "p1", "name": "Alpha Arm", "role": "Starter (7-day)", "team_id": "team_a"},
            {"pitcher_id": "p2", "name": "Beta Bullpen", "role": "Reliever", "team_id": "team_a"},
            {"pitcher_id": "p3", "name": "Other Team", "role": "Starter", "team_id": "team_b"},
        ],
        "daily_entries": [
            {
                "pitcher_id": "p1",
                "team_id": "team_a",
                "date": today,
                "pre_training": {"arm_feel": 8},
                "plan_generated": None,
                "completed_exercises": {},
            },
            {
                "pitcher_id": "p3",
                "team_id": "team_b",
                "date": today,
                "pre_training": {"arm_feel": 4},
                "plan_generated": {"exercise_blocks": []},
                "completed_exercises": {},
            },
        ],
        "pitcher_training_model": [
            {"pitcher_id": "p1", "current_flag_level": "green", "days_since_outing": 2},
            {"pitcher_id": "p2", "current_flag_level": "yellow", "days_since_outing": 1},
            {"pitcher_id": "p3", "current_flag_level": "red", "days_since_outing": 5},
        ],
        "injury_history": [],
        "team_games": [],
    }


def test_staff_pulse_and_coach_overview_contract_agree_for_team_date():
    from bot.services.team_daily_status import (
        get_team_daily_status,
        to_coach_compliance,
        to_coach_roster,
        to_staff_pulse,
    )

    client = _Client(_rows())
    status = get_team_daily_status("team_a", "2026-04-30", client=client)
    staff = to_staff_pulse(status)
    coach_roster = to_coach_roster(status)
    coach_compliance = to_coach_compliance(status)

    assert status["summary"]["checked_in"] == 1
    assert status["summary"]["plans_pending"] == 1
    assert staff["checked_in_count"] == coach_compliance["checked_in_today"] == 1
    assert staff["total_pitchers"] == coach_compliance["total"] == 2
    assert sum(1 for r in coach_roster if r["today_status"] == "checked_in") == 1
    assert sum(1 for r in coach_roster if r["checkin_status"] == "checked_in") == 1
    assert coach_roster[0]["plan_status"] == "pending"
    assert coach_roster[0]["last_7_days"][-1]["checkin_status"] == "checked_in"
    assert staff["pitchers"][0]["checkin_status"] == "checked_in"

    p1 = next(p for p in status["pitchers"] if p["pitcher_id"] == "p1")
    assert p1["checkin_status"] == "checked_in"
    assert p1["plan_status"] == "pending"


def test_team_daily_status_uses_chicago_today_by_default():
    from bot.config import CHICAGO_TZ
    from bot.services.team_daily_status import get_team_daily_status

    client = _Client(_rows(today="2026-04-30"))
    chicago_late = datetime(2026, 4, 30, 23, 30, tzinfo=CHICAGO_TZ)

    with patch("bot.services.team_daily_status.datetime") as mock_datetime:
        mock_datetime.now.return_value = chicago_late
        status = get_team_daily_status("team_a", client=client)

    assert status["date"] == "2026-04-30"
    assert status["summary"]["checked_in"] == 1


def test_team_daily_status_scopes_daily_entries_by_team_id():
    from bot.services.team_daily_status import get_team_daily_status

    client = _Client(_rows())
    status = get_team_daily_status("team_a", "2026-04-30", client=client)

    assert {p["pitcher_id"] for p in status["pitchers"]} == {"p1", "p2"}
    assert all(p["team_id"] == "team_a" for p in status["pitchers"])

    daily_entry_queries = [filters for table, filters in client.queries if table == "daily_entries"]
    assert daily_entry_queries
    assert all(("eq", "team_id", "team_a") in filters for filters in daily_entry_queries)


@pytest.mark.asyncio
async def test_staff_pulse_and_coach_overview_routes_use_same_daily_status_shape():
    from api.coach_routes import team_overview
    from api.routes import staff_pulse
    from bot.config import CHICAGO_TZ
    from bot.services.team_daily_status import get_team_daily_status

    status = get_team_daily_status("team_a", "2026-04-30", client=_Client(_rows()))

    team_chain = MagicMock()
    team_chain.select.return_value = team_chain
    team_chain.eq.return_value = team_chain
    team_chain.single.return_value = team_chain
    team_chain.execute.return_value = SimpleNamespace(data={"name": "Team A", "training_phase": "in-season"})
    db_client = MagicMock()
    db_client.table.return_value = team_chain

    request = SimpleNamespace(
        state=SimpleNamespace(team_id="team_a", coach_id="c1", coach_name="Coach", coach_role="coach")
    )

    with patch("api.routes.get_team_daily_status", return_value=status) as staff_service, \
            patch("api.coach_routes.get_team_daily_status", return_value=status) as coach_service, \
            patch("api.coach_routes.datetime") as coach_datetime, \
            patch("api.coach_routes.require_coach_auth", new=AsyncMock()), \
            patch("api.coach_routes.get_team_games", return_value=[]), \
            patch("api.coach_routes._db.get_active_team_blocks", return_value=[]), \
            patch("api.coach_routes._db.get_pending_suggestions", return_value=[]), \
            patch("api.coach_routes._db.get_client", return_value=db_client):
        coach_datetime.now.return_value = datetime(2026, 4, 30, 12, 0, tzinfo=CHICAGO_TZ)
        staff = await staff_pulse(team_id="team_a")
        coach = await team_overview(request)

    assert staff_service.call_args.args[0] == "team_a"
    assert coach_service.call_args.args == ("team_a", "2026-04-30")
    assert staff["checked_in_count"] == coach["compliance"]["checked_in_today"] == 1
    assert staff["total_pitchers"] == coach["compliance"]["total"] == 2
    assert [p["checked_in"] for p in staff["pitchers"]] == [
        r["today_status"] == "checked_in" for r in coach["roster"]
    ]


@pytest.mark.asyncio
async def test_staff_pulse_defaults_to_uchicago_for_legacy_clients():
    from api.routes import staff_pulse

    with patch("api.routes.get_team_daily_status", return_value={"pitchers": []}) as service:
        staff = await staff_pulse()

    assert service.call_args.args[0] == "uchicago_baseball"
    assert staff == {"checked_in_count": 0, "total_pitchers": 0, "pitchers": []}
