"""Tests for ``bot.services.system_guardian.schema_check`` (2026-05-13).

Covers the startup schema-sanity check that catches collector vs DB column
drift BEFORE the next 15-min tick produces a noisy first-occurrence DM
flood. See ``schema_check.py`` module docstring for the live-deploy
background.

* All expected columns present → returns empty list.
* One column missing on one table → returns one drift observation with
  ``signal=collector_schema_drift severity=critical`` and the missing
  column listed in ``metadata.missing_columns``.
* The information_schema query itself raises → returns one
  ``collector_failure warning`` observation, does NOT re-raise.
* The expected-column contract is locked: every table the supabase_app
  collector reads is covered, and the research_load_log row uses ``ts``
  not ``created_at`` (the live Bug C trigger).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from bot.services.system_guardian import schema_check
from bot.services.system_guardian.schema_check import (
    _EXPECTED_COLUMNS,
    verify_collector_schema,
)


# ---------------------------------------------------------------------------
# Fake Supabase client — just enough surface for the schema check.
# ---------------------------------------------------------------------------


class _Resp:
    def __init__(self, data):
        self.data = data


class _Rpc:
    def __init__(self, rows):
        self.rows = rows

    def execute(self):
        if isinstance(self.rows, Exception):
            raise self.rows
        return _Resp(self.rows)


class _SelectQuery:
    """Mimic the per-table fallback SELECT chain when the RPC isn't present."""

    def __init__(self, table_name, present_columns: dict[str, set[str]]):
        self.table_name = table_name
        self.present_columns = present_columns
        self._cols: list[str] = []

    def select(self, cols_str, *_args, **_kwargs):
        self._cols = [c.strip() for c in cols_str.split(",")]
        return self

    def limit(self, _n):
        return self

    def execute(self):
        missing = [c for c in self._cols if c not in self.present_columns.get(self.table_name, set())]
        if missing:
            raise RuntimeError(
                f"column {self.table_name}.{missing[0]} does not exist"
            )
        return _Resp([])


class _FakeClient:
    """Configurable: choose to either expose the RPC (preferred) or not."""

    def __init__(
        self,
        *,
        rpc_rows=None,
        present_columns: dict[str, set[str]] | None = None,
        rpc_raises_always: bool = False,
    ):
        self.rpc_rows = rpc_rows
        self.present_columns = present_columns or {}
        self.rpc_raises_always = rpc_raises_always
        self.rpc_calls: list[tuple] = []

    def rpc(self, name, params):
        self.rpc_calls.append((name, params))
        if self.rpc_raises_always:
            return _Rpc(RuntimeError("RPC not deployed"))
        return _Rpc(self.rpc_rows)

    def table(self, name):
        return _SelectQuery(name, self.present_columns)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_all_columns_present_returns_empty_list_via_rpc():
    """RPC path: every expected column present → no observations."""
    rpc_rows = []
    for entry in _EXPECTED_COLUMNS:
        for col in entry["columns"]:
            rpc_rows.append({"table_name": entry["table"], "column_name": col})

    fake = _FakeClient(rpc_rows=rpc_rows)
    with patch("bot.services.db.get_client", return_value=fake):
        out = await verify_collector_schema()

    assert out == []
    assert fake.rpc_calls, "RPC path should have been attempted first"


@pytest.mark.asyncio
async def test_all_columns_present_returns_empty_list_via_fallback():
    """Per-table fallback path: same outcome, no observations."""
    present = {
        entry["table"]: set(entry["columns"])
        for entry in _EXPECTED_COLUMNS
    }
    fake = _FakeClient(rpc_raises_always=True, present_columns=present)
    with patch("bot.services.db.get_client", return_value=fake):
        out = await verify_collector_schema()

    assert out == []


# ---------------------------------------------------------------------------
# Drift detection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_one_column_missing_returns_one_critical_drift_observation():
    """The Bug C scenario: research_load_log.ts is missing → one critical
    drift observation per affected table."""
    rpc_rows = []
    for entry in _EXPECTED_COLUMNS:
        for col in entry["columns"]:
            # Simulate Bug C: research_load_log has every column EXCEPT ts.
            if entry["table"] == "research_load_log" and col == "ts":
                continue
            rpc_rows.append({"table_name": entry["table"], "column_name": col})

    fake = _FakeClient(rpc_rows=rpc_rows)
    with patch("bot.services.db.get_client", return_value=fake):
        out = await verify_collector_schema()

    assert len(out) == 1
    drift = out[0]
    assert drift["event_type"] == "collector_schema_drift"
    assert drift["severity_hint"] == "critical"
    md = drift["metadata"]
    assert md["category"] == "guardian_self"
    assert md["code"] == "collector_schema_drift"
    assert md["signal"] == "collector_schema_drift"
    assert md["table"] == "research_load_log"
    assert "ts" in md["missing_columns"]


@pytest.mark.asyncio
async def test_multiple_tables_with_drift_returns_one_obs_per_table():
    """If two collectors regressed simultaneously, each table gets its own
    drift observation so the admin can fix them independently."""
    rpc_rows = []
    for entry in _EXPECTED_COLUMNS:
        for col in entry["columns"]:
            # Drop ONE column from each of two tables.
            if entry["table"] == "research_load_log" and col == "ts":
                continue
            if entry["table"] == "ui_fallback_log" and col == "logged_at":
                continue
            rpc_rows.append({"table_name": entry["table"], "column_name": col})

    fake = _FakeClient(rpc_rows=rpc_rows)
    with patch("bot.services.db.get_client", return_value=fake):
        out = await verify_collector_schema()

    assert len(out) == 2
    by_table = {o["metadata"]["table"]: o for o in out}
    assert "research_load_log" in by_table
    assert "ui_fallback_log" in by_table
    assert "ts" in by_table["research_load_log"]["metadata"]["missing_columns"]
    assert "logged_at" in by_table["ui_fallback_log"]["metadata"]["missing_columns"]


# ---------------------------------------------------------------------------
# Self-failure path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_client_raises_returns_one_collector_failure():
    """If we can't even instantiate the client, emit ONE collector_failure
    and don't re-raise."""

    def boom():
        raise RuntimeError("SUPABASE_URL missing")

    with patch("bot.services.db.get_client", side_effect=boom):
        out = await verify_collector_schema()

    assert len(out) == 1
    f = out[0]
    assert f["event_type"] == "collector_failure"
    assert f["severity_hint"] == "warning"
    assert f["metadata"]["step"] == "verify_collector_schema"
    assert "RuntimeError" in f["message"]


@pytest.mark.asyncio
async def test_information_schema_query_raises_returns_self_failure_obs(monkeypatch):
    """If the column-lookup function itself raises (both RPC and fallback
    fail), surface a single collector_failure warning."""
    fake = _FakeClient(rpc_rows=[])

    def boom(_client, _tables):
        raise RuntimeError("information_schema unreachable")

    monkeypatch.setattr(
        schema_check, "_query_information_schema_columns", boom
    )
    with patch("bot.services.db.get_client", return_value=fake):
        out = await verify_collector_schema()

    assert len(out) == 1
    f = out[0]
    assert f["event_type"] == "collector_failure"
    assert f["severity_hint"] == "warning"
    assert f["metadata"]["step"] == "verify_collector_schema"


@pytest.mark.asyncio
async def test_verify_never_raises_even_on_unexpected_internal_error(monkeypatch):
    """Defense-in-depth: even if a NEW failure mode shows up, the function
    returns a list (possibly empty) rather than raising — Guardian must
    never crash the bot startup."""
    # Patch the column lookup to return an obviously-broken value the rest of
    # the code must tolerate.
    monkeypatch.setattr(
        schema_check, "_query_information_schema_columns", lambda c, t: {}
    )
    fake = _FakeClient(rpc_rows=[])
    with patch("bot.services.db.get_client", return_value=fake):
        out = await verify_collector_schema()

    # Empty column map for every table → every table reports drift.
    assert isinstance(out, list)
    # One drift per table in the contract.
    assert len(out) == len(_EXPECTED_COLUMNS)


# ---------------------------------------------------------------------------
# Contract sanity — the most load-bearing assertions in this file.
# ---------------------------------------------------------------------------


def test_research_load_log_expected_columns_use_ts_not_created_at():
    """Lock the Bug C fix: schema_check's expected-column contract must
    say ``ts`` for research_load_log, never ``created_at``. If a future
    contributor regresses, this test fires before the collector does."""
    rll = next(e for e in _EXPECTED_COLUMNS if e["table"] == "research_load_log")
    assert "ts" in rll["columns"]
    assert "created_at" not in rll["columns"]


def test_expected_columns_covers_every_supabase_app_collector_table():
    """Every table the supabase_app collector reads must be in the
    expected-columns contract — otherwise the runtime check has a blind
    spot equivalent to Bug C."""
    covered = {entry["table"] for entry in _EXPECTED_COLUMNS}
    must_cover = {
        "daily_entries",
        "research_load_log",
        "ui_fallback_log",
        "whoop_tokens",
        "whoop_daily",
    }
    missing = must_cover - covered
    assert missing == set(), (
        f"verify_collector_schema is missing coverage for tables: {missing}. "
        "Add them to _EXPECTED_COLUMNS in schema_check.py."
    )


def test_public_api_surface_exposes_verify_and_startup_runner():
    """Imports work as documented in the module docstring."""
    from bot.services.system_guardian import (
        run_startup_schema_check,
        verify_collector_schema as exported,
    )

    assert exported is verify_collector_schema
    assert callable(run_startup_schema_check)


# ---------------------------------------------------------------------------
# Startup runner wiring
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_startup_schema_check_persists_each_drift_observation():
    """``run_startup_schema_check`` must hand each drift obs to
    ``insert_observation_with_notify`` so the standard A6 path fires the
    critical first-occurrence DM."""
    from bot.services import system_guardian as _sg

    fake_observations = [
        {
            "observed_at": "2026-05-13T17:00:00-05:00",
            "event_type": "collector_schema_drift",
            "severity_hint": "critical",
            "metadata": {
                "category": "guardian_self",
                "code": "collector_schema_drift",
                "table": "research_load_log",
                "missing_columns": ["ts"],
            },
        },
    ]

    persisted: list[dict] = []

    async def _fake_insert(payload):
        persisted.append(payload)
        return payload

    with (
        patch.object(_sg, "verify_collector_schema", return_value=fake_observations),
        patch.object(_sg.store, "insert_observation_with_notify", _fake_insert),
    ):
        count = await _sg.run_startup_schema_check()

    assert count == 1
    assert persisted[0]["event_type"] == "collector_schema_drift"


@pytest.mark.asyncio
async def test_run_startup_schema_check_returns_zero_on_clean_run():
    from bot.services import system_guardian as _sg

    async def _no_op_insert(payload):
        return payload

    with (
        patch.object(_sg, "verify_collector_schema", return_value=[]),
        patch.object(_sg.store, "insert_observation_with_notify", _no_op_insert),
    ):
        count = await _sg.run_startup_schema_check()
    assert count == 0
