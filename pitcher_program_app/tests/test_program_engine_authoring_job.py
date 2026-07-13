"""Sprint C — async authoring job tests (mocked orchestrator/db/DM)."""

from datetime import date

import pytest

from bot.services.program_engine import authoring_job as aj


def test_build_validation_ctx_has_full_library_and_tags():
    ctx = aj.build_validation_ctx({})
    assert len(ctx["exercises_rows"]) > 100  # full canonical library, not a stub
    assert any("fpm" in tags for tags in ctx["tag_lookup"].values())
    assert any("pull" in tags for tags in ctx["tag_lookup"].values())


class _FakeProgram:
    def __init__(self):
        from bot.services.program_engine.schemas import Day

        self.pitcher_id = "landon_brice"
        self.total_weeks = 1
        self.knowledge_version = "kv_test_12345678"
        self.generation_provenance = {"fallback_used": False}
        self.engine_version = "v1"
        self.days = [
            Day(day_index=0, template_key="wk1_d1", date="2026-07-13"),
            Day(day_index=1, template_key="wk1_d2", date="2026-07-14"),
        ]


class _FakeResult:
    def __init__(self, fallback=False):
        self.program = _FakeProgram()
        self.fallback_used = fallback
        self.attempts = [{"attempt_n": 1}]
        self.knowledge_version = "kv_test_12345678"


@pytest.fixture
def wired(monkeypatch):
    sent = {"dms": [], "rows": []}

    async def fake_avp(**kwargs):
        return _FakeResult()

    async def fake_dm(chat_id, text):
        sent["dms"].append(text)

    monkeypatch.setattr(
        "bot.services.program_engine.orchestrator.author_validate_persist", fake_avp
    )
    monkeypatch.setattr(aj, "_dm", fake_dm)
    monkeypatch.setattr(
        "bot.services.research_resolver.resolve_for_program_gen",
        lambda **k: {
            "knowledge_version": "kv_test_12345678",
            "combined": "docs",
            "templates": [{"block_template_id": "return_to_mound_9wk_v1", "domain": "throwing"}],
        },
    )
    monkeypatch.setattr("bot.services.context_manager.load_profile", lambda pid: {"pitcher_id": pid})
    monkeypatch.setattr("bot.services.context_manager.load_context", lambda pid: "ctx")
    monkeypatch.setattr(
        "bot.services.db.create_program",
        lambda row: sent["rows"].append(row) or "prog-new-0001",
    )
    return sent


@pytest.mark.asyncio
async def test_job_persists_draft_and_dms_success(wired):
    pid = await aj.run_authoring_job("landon_brice", "return_to_play", chat_id=123)
    assert pid == "prog-new-0001"
    row = wired["rows"][0]
    assert row["status"] == "draft"
    assert row["engine_version"] == "v1"
    assert row["generated_schedule_json"]["scaffold_kind"] == "engine_v1_authored"
    assert len(wired["dms"]) == 1
    assert "✅" in wired["dms"][0]


@pytest.mark.asyncio
async def test_job_unknown_goal_falls_back_to_default(wired):
    pid = await aj.run_authoring_job("landon_brice", "yeet_mode", chat_id=123)
    assert pid == "prog-new-0001"  # coerced to return_to_play, still runs


@pytest.mark.asyncio
async def test_job_failure_dms_and_returns_none(monkeypatch):
    dms = []

    async def fake_dm(chat_id, text):
        dms.append(text)

    monkeypatch.setattr(aj, "_dm", fake_dm)
    monkeypatch.setattr(
        "bot.services.context_manager.load_profile",
        lambda pid: (_ for _ in ()).throw(RuntimeError("db down")),
    )
    pid = await aj.run_authoring_job("landon_brice", chat_id=123)
    assert pid is None
    assert dms and "error" in dms[0].lower()
