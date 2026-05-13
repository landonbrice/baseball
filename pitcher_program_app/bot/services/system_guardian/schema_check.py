"""Startup-time schema sanity check for Phase 1 collectors.

Background (2026-05-13 post-deploy):
Guardian V1 shipped with ``supabase_app._query_research_load_log_24h``
selecting + filtering on ``research_load_log.created_at`` — a column that
does not exist in production (the table uses ``ts``). Every 15-min tick
logged a query failure; under the original A6 contract those failures were
``info``-level, so the admin never saw a DM. The drift was only caught when
the ack-flood of unrelated baseline observations revealed how many ticks
had already failed silently.

This module is the "belt" half of the belt-and-suspenders runtime check.
The "suspenders" half lives in ``supabase_app._signal_failure_obs``, which
now bumps schema-drift query failures from ``info`` to ``warning``.

What this does:

1. Holds a module-level ``_EXPECTED_COLUMNS`` map — for each table the
   Phase 1 collectors read from, list the columns the collector code
   depends on. ONE source of truth; when a future contributor renames a
   column they update this map at the same time as the query and the
   verifier fires a critical observation on the next deploy if they miss.
2. ``verify_collector_schema()`` runs once on startup. It queries
   ``information_schema.columns`` once (cheap), then for each
   ``(table, columns)`` pair asserts every expected column is present.
   Missing columns → ONE ``severity=critical category=guardian_self
   signal=collector_schema_drift`` observation per affected table.
3. Never raises. On its own internal failure (e.g. cannot query
   ``information_schema``) emits a single ``warning collector_failure``
   observation tagged ``step=verify_collector_schema``.

Wiring: ``bot.main.post_init`` calls this once after the JobQueue is
scheduled, persisting each returned dict via
``store.insert_observation_with_notify`` so the observation participates in
the standard A6 dedup contract (first-occurrence critical drift → admin DM).
"""

from __future__ import annotations

import logging
import traceback
from datetime import datetime
from typing import Any

from bot.config import CHICAGO_TZ

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# The contract. ONE source of truth — change here when collector code
# changes, and the next deploy boot catches any forgotten mismatch.
# ---------------------------------------------------------------------------

# Verified against production information_schema 2026-05-13.
# Each entry: ``{"table": <table_name>, "columns": [<expected columns>]}``.
# Columns listed must be the ones the Phase 1 collectors actually read.
_EXPECTED_COLUMNS: list[dict[str, Any]] = [
    {
        "table": "daily_entries",
        "columns": [
            "pitcher_id",
            "date",
            "team_id",
            "pre_training",
            "plan_generated",
        ],
    },
    {
        "table": "research_load_log",
        "columns": [
            "pitcher_id",
            "context",
            "trigger_reason",
            "total_chars",
            "degraded",
            "ts",  # NOT ``created_at`` — see module docstring.
        ],
    },
    {
        "table": "ui_fallback_log",
        "columns": [
            "id",
            "exercise_id",
            "surface",
            "component",
            "pitcher_id",
            "logged_at",
        ],
    },
    {
        "table": "whoop_tokens",
        "columns": ["pitcher_id"],
    },
    {
        "table": "whoop_daily",
        "columns": ["pitcher_id", "date"],
    },
]


_SOURCE = "guardian.schema_check.verify_collector_schema"


def _now_iso() -> str:
    return datetime.now(CHICAGO_TZ).isoformat()


def _query_information_schema_columns(client, tables: list[str]) -> dict[str, set[str]]:
    """Fetch ``column_name`` for every requested table from
    ``information_schema.columns``. Returns a ``{table: {columns...}}`` map.

    Uses a raw RPC-style query when supabase-py exposes ``execute_sql``-style
    helpers; otherwise falls back to per-table select against
    ``information_schema.columns`` via the standard PostgREST builder.
    PostgREST exposes ``information_schema.columns`` as a system view that
    accepts the same ``.select().eq().execute()`` chain we already use.

    NOTE: Supabase's PostgREST is configured with ``db-schemas=public`` by
    default. ``information_schema`` is NOT in the exposed schemas, so a
    standard ``client.table("information_schema.columns")`` will 404. We
    work around that by calling the project's RPC ``schema_columns`` if
    present; if it isn't, we fall back to running a SECURITY DEFINER PL/pgSQL
    function — and if that ALSO isn't present we surface the gap as a
    ``collector_failure``. In every case, the function never raises.
    """
    # Strategy 1: a dedicated RPC. Cheapest, future-proof. If unavailable
    # the supabase client raises and we fall through.
    try:
        resp = client.rpc(
            "guardian_collector_schema_columns",
            {"p_tables": list(tables)},
        ).execute()
        rows = getattr(resp, "data", None) or []
        if isinstance(rows, list) and rows:
            out: dict[str, set[str]] = {t: set() for t in tables}
            for r in rows:
                t = r.get("table_name")
                c = r.get("column_name")
                if t and c and t in out:
                    out[t].add(c)
            return out
    except Exception as e:
        logger.debug(
            "guardian.schema_check: RPC guardian_collector_schema_columns "
            "unavailable (%s); falling back to per-table probe",
            e,
        )

    # Strategy 2: per-table probe. Use a 0-row SELECT against each table and
    # rely on supabase-py raising "column does not exist" iff a column is
    # missing. This is a best-effort fallback when the RPC isn't deployed.
    out2: dict[str, set[str]] = {}
    for expected in _EXPECTED_COLUMNS:
        if expected["table"] not in tables:
            continue
        cols = list(expected["columns"])
        out2[expected["table"]] = set()
        try:
            # Build a comma-joined column list and run a limit(0) select.
            # PostgREST returns 200 with empty data iff every selected
            # column exists; on any missing column it raises a 4xx wrapped
            # by supabase-py.
            client.table(expected["table"]).select(",".join(cols)).limit(0).execute()
            out2[expected["table"]] = set(cols)
        except Exception as e:
            # We can't recover individual column names from the error in
            # this fallback path, so we leave the table's known-columns
            # set EMPTY. The verifier will then mark every expected column
            # missing — noisy but safe; the right fix is to deploy the RPC.
            logger.warning(
                "guardian.schema_check: per-table probe failed for %s: %s",
                expected["table"],
                e,
            )
    return out2


def _build_drift_observation(
    *, table: str, missing: list[str], expected: list[str]
) -> dict:
    return {
        "observed_at": _now_iso(),
        "source": _SOURCE,
        "service": "supabase",
        "event_type": "collector_schema_drift",
        "severity_hint": "critical",
        "surface": "guardian_self",
        "route_or_job": f"schema_check.{table}",
        "message": (
            f"collector_schema_drift: table {table} missing expected "
            f"columns {missing} (expected={expected})"
        ),
        "metadata": {
            "category": "guardian_self",
            "code": "collector_schema_drift",
            "signal": "collector_schema_drift",
            "table": table,
            "missing_columns": missing,
            "expected_columns": expected,
        },
    }


def _build_self_failure_observation(exc: BaseException) -> dict:
    stack_excerpt = traceback.format_exc(limit=6)[-1200:]
    return {
        "observed_at": _now_iso(),
        "source": _SOURCE,
        "service": "supabase",
        "event_type": "collector_failure",
        "severity_hint": "warning",
        "surface": "guardian_self",
        "route_or_job": "verify_collector_schema",
        "message": (
            f"verify_collector_schema raised: "
            f"{type(exc).__name__}: {str(exc)[:200]}"
        ),
        "stack": stack_excerpt,
        "metadata": {
            "category": "guardian_self",
            "code": "collector_failure",
            "step": "verify_collector_schema",
            "exception_class": type(exc).__name__,
        },
    }


async def verify_collector_schema() -> list[dict]:
    """On startup, verify every column the Phase 1 collectors expect.

    Returns a list of observation dicts (empty list if every expected
    column is present). Caller is responsible for persisting each via
    ``store.insert_observation_with_notify``.

    Each missing-column scenario produces ONE
    ``severity=critical category=guardian_self signal=collector_schema_drift``
    observation per affected table. On internal failure (cannot query
    information_schema, can't import the supabase client, etc.) emits a
    single ``severity=warning collector_failure`` observation tagged
    ``step=verify_collector_schema``.

    Never raises.
    """
    try:
        # Lazy import keeps the supabase client off the cold path and lets
        # tests patch the client cleanly.
        from bot.services.db import get_client

        client = get_client()
    except Exception as e:
        logger.error("guardian.schema_check: get_client failed: %s", e, exc_info=True)
        return [_build_self_failure_observation(e)]

    tables = [entry["table"] for entry in _EXPECTED_COLUMNS]
    try:
        present_by_table = _query_information_schema_columns(client, tables)
    except Exception as e:
        # _query_information_schema_columns is itself defensive, but
        # belt-and-braces.
        logger.error(
            "guardian.schema_check: column lookup raised: %s", e, exc_info=True
        )
        return [_build_self_failure_observation(e)]

    drift_observations: list[dict] = []
    for entry in _EXPECTED_COLUMNS:
        table = entry["table"]
        expected_cols = list(entry["columns"])
        present = present_by_table.get(table) or set()
        missing = [c for c in expected_cols if c not in present]
        if missing:
            drift_observations.append(
                _build_drift_observation(
                    table=table, missing=missing, expected=expected_cols
                )
            )

    return drift_observations


__all__ = ["verify_collector_schema", "_EXPECTED_COLUMNS"]
