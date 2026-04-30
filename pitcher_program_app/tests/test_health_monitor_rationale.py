from bot.services.health_monitor import format_emergency_alert


def test_alert_uses_rationale_detail_when_present():
    alert = {
        "pitcher_name": "Preston",
        "rationale_detail": {
            "status_line": "Red — acute concern",
            "signal_line": "Arm feel dropped from 7 to 3 overnight.",
            "response_line": "Recovery-only day. Trainer consult recommended.",
        },
        "flag_level": "red",
    }
    out = format_emergency_alert(alert)
    assert "Preston" in out
    assert "Red — acute concern" in out
    assert "Arm feel dropped from 7 to 3" in out
    assert "Trainer consult" in out


def test_alert_falls_back_when_rationale_absent():
    """Legacy system-health alert (DeepSeek failures) still works."""
    alert = {
        "pattern": "llm_timeout",
        "count": 3,
        "window_min": 30,
        "pitchers": ["x", "y"],
        "reasons": ["timeout from API"],
    }
    out = format_emergency_alert(alert)
    assert "llm_timeout" in out
    assert "3" in out


def test_alert_renders_pitcher_name_with_rationale():
    """Verify pitcher_name appears in the rich alert title."""
    alert = {
        "pitcher_name": "Wade",
        "rationale_detail": {
            "status_line": "Red — flexor irritation",
            "signal_line": "Forearm tightness reported.",
            "response_line": "Day off. Monitor 24h.",
        },
    }
    out = format_emergency_alert(alert)
    assert "Wade" in out
    assert "RED FLAG" in out
