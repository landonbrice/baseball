"""Sprint D — in-process error telemetry (closes recent_errors_count gap)."""

import logging

from bot.services.system_guardian import error_telemetry as et


def _reset():
    et._ring.clear()
    et._installed = False
    # Remove any previously-attached ring handlers so installs stay clean
    root = logging.getLogger()
    for h in list(root.handlers):
        if isinstance(h, et._RingErrorHandler):
            root.removeHandler(h)


def test_install_captures_error_records():
    _reset()
    et.install_error_telemetry()
    logging.getLogger("bot.services.checkin_service").error("boom: %s", "AttributeError str.get")
    errs = et.recent_errors(minutes=5)
    assert len(errs) == 1
    assert "AttributeError" in errs[0]["message"]
    assert errs[0]["logger"] == "bot.services.checkin_service"


def test_below_error_level_ignored():
    _reset()
    et.install_error_telemetry()
    logging.getLogger("bot.services.foo").warning("just a warning")
    logging.getLogger("bot.services.foo").info("info")
    assert et.recent_errors(minutes=5) == []


def test_guardian_own_errors_excluded():
    _reset()
    et.install_error_telemetry()
    logging.getLogger("bot.services.system_guardian.notify").error("guardian internal")
    assert et.recent_errors(minutes=5) == []


def test_install_idempotent():
    _reset()
    et.install_error_telemetry()
    et.install_error_telemetry()
    logging.getLogger("bot.x").error("once")
    assert len(et.recent_errors(minutes=5)) == 1  # not double-captured
