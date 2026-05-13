"""System Guardian collectors.

Each module here exposes one ``collect_*()`` coroutine that returns a list of
normalized observation dicts. Collectors NEVER raise — per amendments doc A1,
on any internal exception they MUST return a list containing a single
``collector_failure`` observation. The wiring layer (PR-3 onwards) is what
calls :func:`bot.services.system_guardian.store.insert_observation` on each
returned dict.

PR-3 (this file): ``existing_health`` — wraps the legacy 9am digest.
PR-4: ``app_health`` (in-process /health) + ``supabase_app`` (telemetry tables).
PR-7+: ``railway`` + ``supabase_mgmt`` (Phase 2, feature-flagged).
"""

from __future__ import annotations

__all__: list[str] = []
