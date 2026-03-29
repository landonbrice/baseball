"""Progression tracking. Analyzes arm feel trends, sleep patterns, and recovery curves."""

import json
import logging
from datetime import datetime, timedelta
from bot.config import CHICAGO_TZ
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

    # Consistency observation
    checkin_count = len(training_entries)
    if checkin_count >= 7:
        observations.append(
            f"{checkin_count} check-ins logged. The data is compounding — "
            "every day builds a clearer picture of your patterns."
        )
    elif checkin_count >= 3:
        observations.append(
            f"{checkin_count} check-ins so far. A few more days and weekly trend analysis unlocks."
        )
    elif checkin_count >= 1:
        observations.append(
            "First check-ins logged. Keep going — insights start appearing after 3-5 days of data."
        )

    # Weekly summary on Sundays
    weekly_summary = None
    if datetime.now(CHICAGO_TZ).weekday() == 6:  # Sunday
        weekly_summary = _generate_weekly_summary(pitcher_id, training_entries)

    return {
        "observations": observations,
        "flags": flags,
        "weekly_summary": weekly_summary,
    }


def _analyze_arm_feel_trend(entries: list) -> tuple[list[str], list[str]]:
    """Analyze arm feel trends — both positive and negative."""
    observations = []
    flags = []

    recent = entries[-7:]
    feels = [e["pre_training"]["arm_feel"] for e in recent]

    if len(feels) >= 3:
        last_three = feels[-3:]
        # Declining trend
        if all(last_three[i] > last_three[i + 1] for i in range(len(last_three) - 1)):
            flags.append("arm_feel_declining")
            observations.append(
                f"Arm feel has declined 3 days straight ({' → '.join(str(f) for f in last_three)}). "
                "Worth monitoring — talk to your trainer if it continues."
            )
        # Improving trend
        elif all(last_three[i] <= last_three[i + 1] for i in range(len(last_three) - 1)) and last_three[-1] >= 4:
            observations.append(
                f"Arm feel trending up ({' → '.join(str(f) for f in last_three)}). Recovery is tracking well."
            )

    if len(feels) >= 5:
        avg = sum(feels) / len(feels)
        if avg < 3.0:
            flags.append("arm_feel_low_avg")
            observations.append(
                f"Your 5-day arm feel average is {avg:.1f}/5. "
                "That's below where we'd like it. Consider backing off intensity."
            )
        elif avg >= 4.0:
            observations.append(
                f"Arm feel averaging {avg:.1f}/5 over your last {len(feels)} check-ins. Strong and consistent."
            )
        elif avg >= 3.0:
            observations.append(
                f"Arm feel averaging {avg:.1f}/5 — solid baseline. Consistency here is what builds durability."
            )

    # Stability observation — low variance is good
    if len(feels) >= 5:
        variance = sum((f - sum(feels)/len(feels))**2 for f in feels) / len(feels)
        if variance < 0.5 and sum(feels)/len(feels) >= 3.5:
            observations.append(
                "Arm feel has been very stable recently. That consistency matters more than any single day."
            )

    return observations, flags


def _analyze_sleep_pattern(entries: list) -> tuple[list[str], list[str]]:
    """Analyze sleep patterns — both positive and negative."""
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

    last_five = sleep_hours[-5:] if len(sleep_hours) >= 5 else sleep_hours
    avg = sum(last_five) / len(last_five)

    if avg < 6.5:
        flags.append("sleep_low_avg")
        observations.append(
            f"Sleep averaging {avg:.1f}h recently. "
            "Below 6.5h consistently impacts recovery and arm health."
        )
    elif avg >= 8.0:
        observations.append(
            f"Sleep averaging {avg:.1f}h — excellent. This is your biggest recovery advantage."
        )
    elif avg >= 7.0:
        observations.append(
            f"Sleep averaging {avg:.1f}h — good range for recovery."
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


# ---------------------------------------------------------------------------
# Weekly Coaching Narrative (LLM-generated)
# ---------------------------------------------------------------------------

def build_week_snapshot(pitcher_id: str) -> dict:
    """Build a structured data snapshot of the pitcher's week for narrative generation."""
    profile = load_profile(pitcher_id)
    log = load_log(pitcher_id)
    entries = log.get("entries", [])

    # Filter to last 7 days
    today = datetime.now(CHICAGO_TZ).date()
    week_ago = today - timedelta(days=7)
    week_entries = [
        e for e in entries
        if e.get("date") and e["date"] >= week_ago.isoformat()
    ]

    # Previous week for comparison
    two_weeks_ago = today - timedelta(days=14)
    prev_week_entries = [
        e for e in entries
        if e.get("date") and two_weeks_ago.isoformat() <= e["date"] < week_ago.isoformat()
    ]

    # Training entries (have pre_training data)
    training = [e for e in week_entries if e.get("pre_training") and (e["pre_training"] or {}).get("arm_feel") is not None]
    prev_training = [e for e in prev_week_entries if e.get("pre_training") and (e["pre_training"] or {}).get("arm_feel") is not None]

    # Arm feel
    feels = [e["pre_training"]["arm_feel"] for e in training]
    prev_feels = [e["pre_training"]["arm_feel"] for e in prev_training]

    arm_feel = {}
    if feels:
        arm_feel = {
            "avg": round(sum(feels) / len(feels), 1),
            "high": max(feels),
            "low": min(feels),
            "values": feels,
            "trend": "improving" if len(feels) >= 3 and feels[-1] > feels[0] else
                     "declining" if len(feels) >= 3 and feels[-1] < feels[0] else "stable",
        }

    # Sleep
    sleeps = [e["pre_training"]["sleep_hours"] for e in training if (e["pre_training"] or {}).get("sleep_hours") is not None]
    prev_sleeps = [e["pre_training"]["sleep_hours"] for e in prev_training if (e["pre_training"] or {}).get("sleep_hours") is not None]
    sleep_data = {}
    if sleeps:
        sleep_data = {
            "avg": round(sum(sleeps) / len(sleeps), 1),
            "nights_under_6": sum(1 for s in sleeps if s < 6),
        }

    # Throwing
    throwing_days = []
    for e in week_entries:
        t = e.get("throwing") or {}
        if t and t.get("type") and t["type"] not in ("none", "no_throw"):
            vol = (t.get("volume_summary") or {}).get("total_throws_estimate")
            throwing_days.append({
                "date": e["date"],
                "type": t["type"],
                "throws": vol,
                "post_feel": t.get("post_throw_feel"),
            })

    # Exercise completion
    total_exercises = 0
    completed_count = 0
    skipped = []
    for e in week_entries:
        ce = e.get("completed_exercises") or {}
        if isinstance(ce, dict):
            for ex_id, done in ce.items():
                total_exercises += 1
                if done:
                    completed_count += 1
                else:
                    skipped.append(ex_id)

    # Count skipped exercise frequency
    skip_counts = {}
    for ex_id in skipped:
        skip_counts[ex_id] = skip_counts.get(ex_id, 0) + 1
    skipped_summary = [f"{ex_id} ({count}x)" for ex_id, count in sorted(skip_counts.items(), key=lambda x: -x[1])[:5]]

    # Modifications applied this week
    mods = set()
    for e in week_entries:
        pg = e.get("plan_generated") or {}
        for m in (pg.get("modifications_applied") or []):
            mods.add(m)

    # Flag levels
    flag_counts = {"green": 0, "yellow": 0, "red": 0}
    for e in training:
        fl = (e["pre_training"] or {}).get("flag_level", "green")
        flag_counts[fl] = flag_counts.get(fl, 0) + 1

    # Previous week comparison
    comparison = {}
    if prev_feels and feels:
        comparison["arm_feel_avg_change"] = round(sum(feels)/len(feels) - sum(prev_feels)/len(prev_feels), 1)
    if prev_sleeps and sleeps:
        comparison["sleep_avg_change"] = round(sum(sleeps)/len(sleeps) - sum(prev_sleeps)/len(prev_sleeps), 1)

    # Pitcher context
    injuries = profile.get("injury_history", [])
    injury_summary = [
        {"area": i.get("area", ""), "ongoing": i.get("ongoing_considerations", i.get("resolution", ""))}
        for i in injuries if i.get("area")
    ]
    flags = profile.get("active_flags", {})
    goals = profile.get("goals", {})

    # WHOOP weekly averages (if pitcher is linked)
    whoop_week = None
    try:
        from bot.services.db import get_whoop_daily_range
        rows = get_whoop_daily_range(pitcher_id, days=7)
        if rows:
            recoveries = [r["recovery_score"] for r in rows if r.get("recovery_score") is not None]
            hrvs = [r["hrv_rmssd"] for r in rows if r.get("hrv_rmssd") is not None]
            sleep_perfs = [r["sleep_performance"] for r in rows if r.get("sleep_performance") is not None]
            if recoveries or hrvs:
                hrv_trend = "stable"
                if len(hrvs) >= 4:
                    first_half = sum(hrvs[:len(hrvs)//2]) / (len(hrvs)//2)
                    second_half = sum(hrvs[len(hrvs)//2:]) / (len(hrvs) - len(hrvs)//2)
                    if second_half > first_half * 1.05:
                        hrv_trend = "improving"
                    elif second_half < first_half * 0.95:
                        hrv_trend = "declining"
                whoop_week = {
                    "avg_recovery": round(sum(recoveries) / len(recoveries), 1) if recoveries else None,
                    "avg_hrv": round(sum(hrvs) / len(hrvs), 1) if hrvs else None,
                    "hrv_trend": hrv_trend,
                    "avg_sleep_performance": round(sum(sleep_perfs) / len(sleep_perfs), 1) if sleep_perfs else None,
                    "days_with_data": len(rows),
                }
    except Exception as e:
        logger.warning("WHOOP weekly data skipped for %s: %s", pitcher_id, e)

    snapshot = {
        "pitcher": {
            "name": profile.get("name", pitcher_id),
            "role": profile.get("role", "starter"),
            "rotation_length": profile.get("rotation_length", 7),
            "injury_history": injury_summary,
            "active_modifications": flags.get("active_modifications", []),
            "goals": goals,
        },
        "week": {
            "dates": f"{week_ago.isoformat()} to {today.isoformat()}",
            "checkins": len(training),
            "arm_feel": arm_feel,
            "sleep": sleep_data,
            "throwing": throwing_days,
            "exercise_completion": {
                "total": total_exercises,
                "completed": completed_count,
                "rate": round(completed_count / total_exercises, 2) if total_exercises else 0,
            },
            "skipped_exercises": skipped_summary,
            "modifications_applied": list(mods),
            "flag_levels": flag_counts,
            "previous_week_comparison": comparison,
        },
    }
    if whoop_week:
        snapshot["week"]["whoop"] = whoop_week
    return snapshot


async def generate_weekly_narrative(pitcher_id: str) -> dict | None:
    """Generate an LLM coaching narrative from the week's data.

    Returns dict with 'narrative' and 'headline' keys, or None if not enough data.
    Stores result in weekly_summaries table.
    """
    from bot.services.llm import call_llm, load_prompt
    from bot.services.context_manager import load_profile
    from bot.services import db as _db

    snapshot = build_week_snapshot(pitcher_id)
    if snapshot["week"]["checkins"] < 1:
        return None

    try:
        prompt_template = load_prompt("weekly_narrative.md")
    except FileNotFoundError:
        logger.warning("weekly_narrative.md prompt not found, skipping narrative generation")
        return None

    system_prompt = (
        "You are a pitching coach reviewing your pitcher's week. "
        "You know their injury history, training patterns, and goals. "
        "Write like a coach who's been watching them — direct, specific, encouraging but honest."
    )

    user_prompt = prompt_template.replace("{week_data}", json.dumps(snapshot, indent=2))

    try:
        raw = await call_llm(system_prompt, user_prompt, max_tokens=500)
    except Exception as e:
        logger.error(f"Weekly narrative LLM call failed for {pitcher_id}: {e}")
        return None

    # Parse JSON response
    result = _parse_narrative(raw)
    if not result:
        return None

    # Store in weekly_summaries
    today = datetime.now(CHICAGO_TZ).date()
    week_start = (today - timedelta(days=today.weekday())).isoformat()  # Monday of this week
    try:
        _db.upsert_weekly_summary(pitcher_id, week_start, {
            "narrative": result["narrative"],
            "headline": result.get("headline", ""),
            "generated_at": datetime.now(CHICAGO_TZ).isoformat(),
        })
    except Exception as e:
        logger.error(f"Failed to store weekly narrative for {pitcher_id}: {e}")

    return result


def _parse_narrative(raw: str) -> dict | None:
    """Parse narrative JSON from LLM response."""
    import re
    text = raw.strip()

    # Strip markdown fences
    fence = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and "narrative" in parsed:
            return parsed
    except json.JSONDecodeError:
        pass

    # If not JSON, treat the whole response as the narrative
    if len(text) > 20:
        return {"narrative": text, "headline": ""}

    logger.warning(f"Could not parse weekly narrative: {raw[:200]}")
    return None
