"""System Guardian collectors.

Each module here exposes one ``collect_*()`` coroutine that returns a list of
normalized observation dicts. Collectors NEVER raise — per amendments doc A1,
on any internal exception they MUST return a list containing a single
``collector_failure`` observation. The wiring layer (PR-5 admin route, PR-6
tick loop) is what calls :func:`bot.services.system_guardian.store.insert_observation`
on each returned dict.

PR-3: ``existing_health`` — wraps the legacy 9am digest.
PR-4 (this file): ``app_health`` (in-process /health + /admin/health) +
``supabase_app`` (queries app telemetry tables).
PR-7+: ``railway`` + ``supabase_mgmt`` (Phase 2, feature-flagged).
"""

from __future__ import annotations

from bot.services.system_guardian.collectors.app_health import collect_app_health
from bot.services.system_guardian.collectors.existing_health import (
    PLAN_ENRICHMENT_SIGNATURE,
    collect_existing_health,
)
from bot.services.system_guardian.collectors.supabase_app import collect_supabase_app

__all__ = [
    "collect_app_health",
    "collect_existing_health",
    "collect_supabase_app",
    "PLAN_ENRICHMENT_SIGNATURE",
]
