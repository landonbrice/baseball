"""Program Engine v1 feature flag.

Module-level constant. Default OFF so the legacy rotation-repeat path in
`program_generator.generate_program` stays active in prod. Flipping
requires a code change (no env var, no DB toggle — explicit by design).

Tests can monkeypatch via:
    monkeypatch.setattr("bot.services.program_engine.feature_flag.PROGRAM_ENGINE_V1", True)
"""
PROGRAM_ENGINE_V1: bool = False
