"""Tests for the 3am observation-prune scheduler hook (D15)."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from bot.services.system_guardian import run_observation_prune


# ---------------------------------------------------------------------------
# Helpers — stub Supabase client + capture inserts
# ---------------------------------------------------------------------------

class _Resp:
    def __init__(self, data):
        self.data = data


class _RpcCall:
    def __init__(self, parent, fn_name):
        self.parent = parent
        self.fn_name = fn_name

    def execute(self):
        self.parent.rpc_calls.append(self.fn_name)
        return _Resp(self.parent.rpc_return)


class _TableQuery:
    def __init__(self, parent, name):
        self.parent = parent
        self.name = name

    def insert(self, payload):
        self.parent.inserts.append((self.name, payload))
        return self

    def select(self, *a, **kw):
        return self

    def eq(self, *a, **kw):
        return self

    def update(self, payload):
        return self

    def execute(self):
        return _Resp([])


class _FakeClient:
    def __init__(self, rpc_return=5, raise_on_rpc=False):
        self.rpc_return = rpc_return
        self.raise_on_rpc = raise_on_rpc
        self.rpc_calls: list[str] = []
        self.inserts: list[tuple[str, dict]] = []

    def rpc(self, name, params):
        if self.raise_on_rpc:
            raise RuntimeError("simulated RPC failure")
        return _RpcCall(self, name)

    def table(self, name):
        return _TableQuery(self, name)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_prune_job_calls_sql_function_and_emits_self_observation():
    fake = _FakeClient(rpc_return=42)

    with patch(
        "bot.services.system_guardian.store._db.get_client", return_value=fake
    ):
        pruned = await run_observation_prune()

    # (a) calls the SQL function
    assert "prune_old_observations" in fake.rpc_calls
    # Returned value flows back to caller
    assert pruned == 42
    # (b) emits the self-observation
    assert any(
        table == "system_observations"
        and payload.get("event_type") == "prune_observations_daily"
        and payload.get("severity_hint") == "info"
        and "42" in payload.get("message", "")
        for table, payload in fake.inserts
    ), f"prune_observations_daily self-obs not emitted; inserts={fake.inserts}"


@pytest.mark.asyncio
async def test_prune_job_self_obs_signature_is_stable():
    """Signature must be the deterministic guardian_self prune signature."""
    fake = _FakeClient(rpc_return=0)
    with patch(
        "bot.services.system_guardian.store._db.get_client", return_value=fake
    ):
        await run_observation_prune()

    self_obs_inserts = [
        payload
        for table, payload in fake.inserts
        if table == "system_observations"
        and payload.get("event_type") == "prune_observations_daily"
    ]
    assert self_obs_inserts
    assert all(payload.get("signature") for payload in self_obs_inserts)


@pytest.mark.asyncio
async def test_prune_job_handles_zero_pruned():
    fake = _FakeClient(rpc_return=0)
    with patch(
        "bot.services.system_guardian.store._db.get_client", return_value=fake
    ):
        pruned = await run_observation_prune()
    assert pruned == 0


# ---------------------------------------------------------------------------
# Failure paths
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_prune_job_does_not_raise_on_rpc_error():
    """(c) Emits collector_failure + does not raise on exception."""
    fake = _FakeClient(raise_on_rpc=True)

    with patch(
        "bot.services.system_guardian.store._db.get_client", return_value=fake
    ):
        # Must not raise
        pruned = await run_observation_prune()

    assert pruned == -1
    assert any(
        payload.get("event_type") == "collector_failure"
        and payload.get("severity_hint") == "warning"
        for table, payload in fake.inserts
        if table == "system_observations"
    ), f"collector_failure self-obs not emitted; inserts={fake.inserts}"


@pytest.mark.asyncio
async def test_prune_job_emits_collector_failure_on_timeout(monkeypatch):
    """If the underlying call hangs past _PRUNE_TIMEOUT_S, we emit a
    collector_failure observation rather than re-raise."""
    import bot.services.system_guardian as sg

    monkeypatch.setattr(sg, "_PRUNE_TIMEOUT_S", 0.05)

    def _slow():
        import time

        time.sleep(0.5)
        return 1

    fake = _FakeClient(rpc_return=0)
    with (
        patch(
            "bot.services.system_guardian.store.call_prune_old_observations",
            _slow,
        ),
        patch(
            "bot.services.system_guardian.store._db.get_client",
            return_value=fake,
        ),
    ):
        pruned = await run_observation_prune()

    assert pruned == -1
    timeout_obs = [
        payload
        for table, payload in fake.inserts
        if table == "system_observations"
        and payload.get("event_type") == "collector_failure"
    ]
    assert timeout_obs, f"timeout collector_failure not emitted; inserts={fake.inserts}"
    assert "timed out" in timeout_obs[0]["message"].lower()


# ---------------------------------------------------------------------------
# RPC return-shape parser
# ---------------------------------------------------------------------------

def test_call_prune_unpacks_int_in_list_of_dicts():
    """Supabase commonly returns the int wrapped in [{'prune_old_observations': N}]."""
    from bot.services.system_guardian import store

    fake = _FakeClient(rpc_return=[{"prune_old_observations": 17}])
    with patch(
        "bot.services.system_guardian.store._db.get_client", return_value=fake
    ):
        assert store.call_prune_old_observations() == 17


def test_call_prune_handles_bare_int():
    from bot.services.system_guardian import store

    fake = _FakeClient(rpc_return=9)
    with patch(
        "bot.services.system_guardian.store._db.get_client", return_value=fake
    ):
        assert store.call_prune_old_observations() == 9


def test_call_prune_returns_minus_one_on_exception():
    from bot.services.system_guardian import store

    fake = _FakeClient(raise_on_rpc=True)
    with patch(
        "bot.services.system_guardian.store._db.get_client", return_value=fake
    ):
        assert store.call_prune_old_observations() == -1


# ---------------------------------------------------------------------------
# Scheduler wiring smoke check — make sure bot/main.py exports the hook.
# ---------------------------------------------------------------------------

def test_bot_main_schedules_guardian_prune_at_3am():
    """``_schedule_jobs`` must register a daily 3am Chicago job named
    ``guardian_prune_observations``. We grep the source rather than execute
    the Telegram scheduler, because actually running ``_schedule_jobs`` would
    require a live Application + JobQueue.
    """
    from pathlib import Path

    main_path = Path(__file__).resolve().parents[2] / "bot" / "main.py"
    src = main_path.read_text(encoding="utf-8")
    assert "guardian_prune_observations" in src
    assert "hour=3" in src
    assert "run_observation_prune" in src
