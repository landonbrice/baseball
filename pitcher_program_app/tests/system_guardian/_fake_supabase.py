"""Shared fake Supabase client for system_guardian tests.

Implements the subset of the supabase-py builder pattern we actually use:
``client.table(name).select(...).eq/in_/gte/order/limit(...).execute()``,
``insert(...)``, ``update(...)``, ``rpc(...)``.

Backing store is a plain in-memory list per table — tests can pre-seed data
or assert against captured writes.

Not a general-purpose mock — only the call shapes the Guardian store +
admin router actually issue are supported.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any


class _Resp:
    def __init__(self, data, count=None):
        self.data = data
        self.count = count


class _Query:
    def __init__(self, parent: "FakeSupabase", table_name: str):
        self.parent = parent
        self.table_name = table_name
        self._select_cols: str | None = None
        self._filters: list[tuple[str, str, Any]] = []  # (op, col, val)
        self._order_col: str | None = None
        self._order_desc: bool = False
        self._limit: int | None = None
        self._count_mode: str | None = None
        self._update_payload: dict | None = None
        self._insert_payload: dict | None = None
        self._is_update = False
        self._is_insert = False

    # -------- read --------
    def select(self, *cols, count=None):
        self._select_cols = ",".join(cols) if cols else "*"
        self._count_mode = count
        return self

    def eq(self, col, val):
        self._filters.append(("eq", col, val))
        return self

    def in_(self, col, values):
        self._filters.append(("in_", col, list(values)))
        return self

    def gte(self, col, val):
        self._filters.append(("gte", col, val))
        return self

    def order(self, col, desc=False):
        self._order_col = col
        self._order_desc = desc
        return self

    def limit(self, n):
        self._limit = n
        return self

    def single(self):
        # Not really used here, but returns self so chains don't break.
        return self

    # -------- write --------
    def insert(self, payload):
        self._insert_payload = dict(payload)
        self._is_insert = True
        return self

    def update(self, payload):
        self._update_payload = dict(payload)
        self._is_update = True
        return self

    def delete(self):
        # No-op for tests.
        return self

    # -------- run --------
    def execute(self):
        rows = self.parent.tables.setdefault(self.table_name, [])

        if self._is_insert:
            row = dict(self._insert_payload or {})
            row.setdefault("id", str(uuid.uuid4()))
            row.setdefault("created_at", datetime.utcnow().isoformat())
            rows.append(row)
            self.parent.writes.append(("insert", self.table_name, row))
            return _Resp([row])

        if self._is_update:
            patch = self._update_payload or {}
            matched = self._filter_rows(rows)
            updated = []
            for r in matched:
                r.update(patch)
                updated.append(r)
            self.parent.writes.append(("update", self.table_name, patch))
            return _Resp(updated)

        # SELECT
        out = list(self._filter_rows(rows))
        if self._order_col:
            out.sort(
                key=lambda r: r.get(self._order_col) or "",
                reverse=self._order_desc,
            )
        if self._limit is not None:
            out = out[: self._limit]

        count = len(self._filter_rows(rows)) if self._count_mode == "exact" else None
        return _Resp(out, count=count)

    # -------- helper --------
    def _filter_rows(self, rows):
        out = rows
        for op, col, val in self._filters:
            if op == "eq":
                out = [r for r in out if r.get(col) == val]
            elif op == "in_":
                out = [r for r in out if r.get(col) in val]
            elif op == "gte":
                out = [r for r in out if (r.get(col) or "") >= val]
        return out


class _Rpc:
    def __init__(self, parent: "FakeSupabase", fn_name: str):
        self.parent = parent
        self.fn_name = fn_name

    def execute(self):
        self.parent.rpc_calls.append(self.fn_name)
        return _Resp(self.parent.rpc_returns.get(self.fn_name, 0))


class FakeSupabase:
    def __init__(self, *, rpc_returns: dict | None = None):
        self.tables: dict[str, list[dict]] = {}
        self.writes: list[tuple[str, str, Any]] = []
        self.rpc_calls: list[str] = []
        self.rpc_returns = rpc_returns or {}

    def table(self, name: str) -> _Query:
        return _Query(self, name)

    def rpc(self, name: str, params: dict) -> _Rpc:
        return _Rpc(self, name)
