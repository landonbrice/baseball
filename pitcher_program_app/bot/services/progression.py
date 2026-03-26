"""Progression tracking. Analyzes arm feel trends, sleep patterns, and recovery curves."""

import logging
from datetime import datetime
from bot.services.context_manager import load_log, load_profile

logger = logging.getLogger(__name__)


def analyze_progression(pitcher_id: str) -> dict:
    """Analyze recent log entries for patterns and flags.

    Returns:
        dict with keys: observations (list[str]), flags (list[str]), weekly_summary (str|None)
    """
    log = load_log(pitcher_id)
    entries = log.get("entries", [])

    observations = []
    flags = []

    if not entries:
        return {"observations": observations, "flags": flags, "weekly_summary": None}

    # Get entries with pre_training data
    training_entries = [
        e for e in entries
        if e.get("pre_training") and e["pre_training"].get("arm_feel") is not None
    ]

    if training_entries:
        arm_obs, arm_flags = _analyze_arm_feel_trend(training_entries)
        observations.extend(arm_obs)
        flags.extend(arm_flags)

        sleep_obs, sleep_flags = _analyze_sleep_pattern(training_entries)
        observations.extend(sleep_obs)
        flags.extend(sleep_flags)

    # Recovery curve analysis needs outing data
    recovery_obs, recovery_flags = _analyze_recovery_curve(entries)
    observations.extend(recovery_obs)
    flags.extend(recovery_flags)

    # Weekly summary on Sundays
    weekly_summary = None
    if datetime.now().weekday() == 6:  # Sunday
        weekly_summary = _generate_weekly_summary(pitcher_id, training_entries)

    return {
        "observations": observations,
        "flags": flags,
        "weekly_summary": weekly_summary,
    }


def _analyze_arm_feel_trend(entries: list) -> tuple[list[str], list[str]]:
    """Check for declining arm feel trends.

    Flags:
    - 3+ day strict decline
    - Average < 3.0 over last 5 days
    """
    observations = []
    flags = []

    recent = entries[-5:]
    feels = [e["pre_training"]["arm_feel"] for e in recent]

    if len(feels) >= 3:
        # Check for strict 3+ day decline
        last_three = feels[-3:]
        if all(last_three[i] > last_three[i + 1] for i in range(len(last_three) - 1)):
            flags.append("arm_feel_declining")
            observations.append(
                f"Arm feel has declined 3 days straight ({' → '.join(str(f) for f in last_three)}). "
                "Worth monitoring — talk to your trainer if it continues."
            )

    if len(feels) >= 5:
        avg = sum(feels) / len(feels)
        if avg < 3.0:
            flags.append("arm_feel_low_avg")
            observations.append(
                f"Your 5-day arm feel average is {avg:.1f}/5. "
                "That's below where we'd like it. Consider backing off intensity."
            )

    return observations, flags


def _analyze_sleep_pattern(entries: list) -> tuple[list[str], list[str]]:
    """Check for poor sleep patterns.

    Flags:
    - Average < 6.5h over last 5 days
    - 3+ nights under 6h in last 7 entries
    """
    observations = []
    flags = []

    recent = entries[-7:]
    sleep_hours = [
        e["pre_training"]["sleep_hours"]
        for e in recent
        if e["pre_training"].get("sleep_hours") is not None
    ]

    if not sleep_hours:
        return observations, flags

    # Average check (last 5)
    last_five = sleep_hours[-5:] if len(sleep_hours) >= 5 else sleep_hours
    avg = sum(last_five) / len(last_five)
    if avg < 6.5:
        flags.append("sleep_low_avg")
        observations.append(
            f"Your recent sleep average is {avg:.1f}h. "
            "Below 6.5h consistently impacts recovery and arm health."
        )

    # Frequency check
    under_six = sum(1 for h in sleep_hours if h < 6)
    if under_six >= 3:
        flags.append("sleep_frequently_low")
        observations.append(
            f"You've had {under_six} nights under 6h recently. "
            "Prioritize sleep — it's the single biggest recovery factor."
        )

    return observations, flags


def _analyze_recovery_curve(entries: list) -> tuple[list[str], list[str]]:
    """Check if arm feel recovers after outings.

    Looks for post-outing entries where arm feel isn't recovering
    within expected timeframe (should trend up by day 2-3 post-outing).
    """
    observations = []
    flags = []

    # Find outing entries
    outing_indices = []
    for i, e in enumerate(entries):
        if e.get("outing"):
            outing_indices.append(i)

    if not outing_indices:
        return observations, flags

    # Check recovery after most recent outing
    last_outing_idx = outing_indices[-1]
    post_outing = entries[last_outing_idx + 1:]

    if len(post_outing) >= 3:
        post_feels = [
            e["pre_training"]["arm_feel"]
            for e in post_outing[:3]
            if e.get("pre_training") and e["pre_training"].get("arm_feel") is not None
        ]
        if len(post_feels) >= 2:
            # Arm feel should be trending up or stable by day 2-3
            if all(post_feels[i] >= post_feels[i + 1] for i in range(len(post_feels) - 1)):
                if post_feels[-1] <= 3:
                    flags.append("slow_recovery")
                    observations.append(
                        "Arm feel isn't recovering as expected post-outing. "
                        "Consider adjusting recovery protocol or flagging for your trainer."
                    )

    return observations, flags


def _generate_weekly_summary(pitcher_id: str, entries: list):
    """Generate a weekly summary (Sunday only)."""
    if not entries:
        return None

    # Use last 7 entries (or fewer)
    week = entries[-7:]

    feels = [e["pre_training"]["arm_feel"] for e in week]
    sleeps = [
        e["pre_training"]["sleep_hours"]
        for e in week
        if e["pre_training"].get("sleep_hours") is not None
    ]

    parts = ["📊 Weekly Summary:"]
    parts.append(f"  Check-ins this week: {len(week)}")

    if feels:
        avg_feel = sum(feels) / len(feels)
        parts.append(f"  Arm feel: avg {avg_feel:.1f}/5 (range {min(feels)}-{max(feels)})")

    if sleeps:
        avg_sleep = sum(sleeps) / len(sleeps)
        parts.append(f"  Sleep: avg {avg_sleep:.1f}h")

    # Count outings from full log
    log = load_log(pitcher_id)
    all_entries = log.get("entries", [])
    outing_count = sum(1 for e in all_entries[-7:] if e.get("outing"))
    parts.append(f"  Outings: {outing_count}")

    # Load profile for context
    try:
        profile = load_profile(pitcher_id)
        flags = profile.get("active_flags", {})
        flag_level = flags.get("current_flag_level", "unknown")
        parts.append(f"  Current flag: {flag_level.upper()}")
    except Exception:
        pass

    return "\n".join(parts)
