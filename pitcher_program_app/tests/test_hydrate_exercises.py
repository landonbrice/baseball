"""D16, D17: hydrate_exercises stamps `name` onto exercise dicts using snapshot cache."""
from bot.services import exercise_pool


def test_hydrate_stamps_name(monkeypatch):
    fake_rows = [
        {"id": "ex_001", "slug": "goblet_squat", "name": "Goblet Squat"},
        {"id": "ex_002", "slug": "bench_press", "name": "Bench Press"},
    ]
    monkeypatch.setattr("bot.services.exercise_pool.get_exercises", lambda: fake_rows)
    exercise_pool._refresh_snapshot()

    items = [
        {"exercise_id": "ex_001", "prescribed": "3x8"},
        {"exercise_id": "ex_002", "prescribed": "3x5"},
    ]
    out = exercise_pool.hydrate_exercises(items)
    assert out[0]["name"] == "Goblet Squat"
    assert out[1]["name"] == "Bench Press"
    # Other fields untouched
    assert out[0]["prescribed"] == "3x8"


def test_hydrate_lazy_miss_falls_through_to_supabase(monkeypatch):
    snapshot_rows = [{"id": "ex_001", "slug": "a", "name": "A"}]
    monkeypatch.setattr("bot.services.exercise_pool.get_exercises", lambda: snapshot_rows)
    exercise_pool._refresh_snapshot()

    def fake_get_exercise(ex_id):
        if ex_id == "ex_new":
            return {"id": "ex_new", "slug": "new", "name": "Newly Added"}
        return None

    monkeypatch.setattr("bot.services.exercise_pool.get_exercise", fake_get_exercise)
    items = [{"exercise_id": "ex_new", "prescribed": "2x10"}]
    out = exercise_pool.hydrate_exercises(items)
    assert out[0]["name"] == "Newly Added"
    # Subsequent call should hit snapshot (no new Supabase call)
    call_count = {"n": 0}
    monkeypatch.setattr("bot.services.exercise_pool.get_exercise", lambda _: (call_count.update({"n": call_count["n"] + 1}), None)[1])
    exercise_pool.hydrate_exercises([{"exercise_id": "ex_new"}])
    assert call_count["n"] == 0  # served from snapshot after first-miss hydration


def test_hydrate_missing_exercise_leaves_name_absent(monkeypatch):
    monkeypatch.setattr("bot.services.exercise_pool.get_exercises", lambda: [])
    exercise_pool._refresh_snapshot()
    monkeypatch.setattr("bot.services.exercise_pool.get_exercise", lambda _: None)

    items = [{"exercise_id": "truly_missing"}]
    out = exercise_pool.hydrate_exercises(items)
    assert "name" not in out[0] or out[0].get("name") is None


def test_hydrate_keeps_last_good_on_refresh_failure(monkeypatch):
    """Snapshot is not cleared when a refresh raises — last-good data is preserved (D5)."""
    seed_rows = [{"id": "ex_001", "slug": "goblet_squat", "name": "Goblet Squat"}]
    monkeypatch.setattr("bot.services.exercise_pool.get_exercises", lambda: seed_rows)
    exercise_pool._refresh_snapshot()
    assert "ex_001" in exercise_pool._EXERCISE_SNAPSHOT

    def boom():
        raise RuntimeError("transient Supabase outage")

    monkeypatch.setattr("bot.services.exercise_pool.get_exercises", boom)
    exercise_pool._refresh_snapshot()  # should not raise and should keep the old snapshot
    assert "ex_001" in exercise_pool._EXERCISE_SNAPSHOT
    assert exercise_pool._EXERCISE_SNAPSHOT["ex_001"]["name"] == "Goblet Squat"


def test_hydrate_handles_supabase_error_on_lazy_miss(monkeypatch):
    """A Supabase error during lazy-miss does not crash hydrate_exercises (fix A)."""
    monkeypatch.setattr("bot.services.exercise_pool.get_exercises", lambda: [])
    exercise_pool._refresh_snapshot()  # empty snapshot

    def boom(_ex_id):
        raise RuntimeError("network timeout")

    monkeypatch.setattr("bot.services.exercise_pool.get_exercise", boom)

    items = [{"exercise_id": "ex_fail", "prescribed": "3x8"}]
    out = exercise_pool.hydrate_exercises(items)  # must not raise
    assert out[0].get("exercise_id") == "ex_fail"
    assert "name" not in out[0]  # graceful degradation — item unchanged, no name added
