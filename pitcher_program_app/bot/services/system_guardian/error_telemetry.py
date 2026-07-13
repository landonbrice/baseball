"""In-process error telemetry (Sprint D — closes the `recent_errors_count`
"not yet wired" gap Guardian has flagged since PR-19).

A logging.Handler on the root logger keeps a bounded ring of recent
ERROR-and-above records so the `app_health` collector can report real
counts + sample messages. Motivation: the 2026-07-13 check-in failure was
only diagnosable by inference — the traceback lived in Railway stdout,
invisible to Guardian. With this wired, the next in-process exception
becomes an observation within one 15-minute tick.

Zero-dependency, process-local, never raises. Redaction happens downstream
at `insert_observation` (A4 write-time pass) — samples are still truncated
here as a first defense.
"""
from __future__ import annotations

import logging
import threading
import time
from collections import deque

_MAX_RECORDS = 200
_SAMPLE_CHARS = 300

_lock = threading.Lock()
_ring: deque = deque(maxlen=_MAX_RECORDS)
_installed = False


class _RingErrorHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            if record.levelno < logging.ERROR:
                return
            # Guardian's own plumbing must not feed back into itself.
            if record.name.startswith("bot.services.system_guardian"):
                return
            msg = record.getMessage()[:_SAMPLE_CHARS]
            with _lock:
                _ring.append((time.time(), record.name, msg))
        except Exception:
            pass  # a telemetry handler must never break logging


def install_error_telemetry() -> None:
    """Attach the ring handler to the root logger. Idempotent."""
    global _installed
    if _installed:
        return
    handler = _RingErrorHandler(level=logging.ERROR)
    logging.getLogger().addHandler(handler)
    _installed = True


def recent_errors(minutes: int = 60) -> list[dict]:
    """Errors recorded in the last `minutes`, oldest first."""
    cutoff = time.time() - minutes * 60
    with _lock:
        return [
            {"age_s": int(time.time() - ts), "logger": name, "message": msg}
            for ts, name, msg in _ring
            if ts >= cutoff
        ]


def is_installed() -> bool:
    return _installed
