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
        elif all(last_three[i] <= last_three[i + 1] for i in range(len(last_three) - 1)) and last_three[-1] >= 7:
            observations.append(
                f"Arm feel trending up ({' → '.join(str(f) for f in last_three)}). Recovery is tracking well."
            )

    if len(feels) >= 5:
        avg = sum(feels) / len(feels)
        if avg < 5.0:
            flags.append("arm_feel_low_avg")
            observations.append(
                f"Your 5-day arm feel average is {avg:.1f}/10. "
                "That's below where we'd like it. Consider backing off intensity."
            )
        elif avg >= 7.0:
            observations.append(
                f"Arm feel averaging {avg:.1f}/10 over your last {len(feels)} check-ins. Strong and consistent."
            )
        elif avg >= 5.0:
            observations.append(
                f"Arm feel averaging {avg:.1f}/10 — solid baseline. Consistency here is what builds durability."
            )

    # Stability observation — low variance is good
    if len(feels) >= 5:
        variance = sum((f - sum(feels)/len(feels))**2 for f in feels) / len(feels)
        if variance < 0.5 and sum(feels)/len(feels) >= 6.0:
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
                if post_feels[-1] <= 6:
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
        parts.append(f"  Arm feel: avg {avg_feel:.1f}/10 (range {min(feels)}-{max(feels)})")

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
        # Build structured summary from the snapshot
        structured = {
            "avg_arm_feel": snapshot.get("week", {}).get("arm_feel", {}).get("avg"),
            "avg_sleep": snapshot.get("week", {}).get("sleep", {}).get("avg"),
            "exercise_completion_rate": snapshot.get("week", {}).get("exercise_completion", {}).get("rate"),
            "exercises_skipped": snapshot.get("week", {}).get("skipped_exercises", {}),
            "throwing_sessions": len(snapshot.get("week", {}).get("throwing", [])),
            "total_throws": sum(
                t.get("throw_count", 0) for t in snapshot.get("week", {}).get("throwing", [])
            ),
            "flag_distribution": snapshot.get("week", {}).get("flag_levels", {}),
            "movement_pattern_balance": {},  # Phase 2 will populate this
        }

        _db.upsert_weekly_summary(
            pitcher_id, week_start,
            {
                "narrative": result.get("narrative", ""),
                "headline": result.get("headline", ""),
                "generated_at": datetime.now(CHICAGO_TZ).isoformat(),
            },
            structured=structured,
        )
    except Exception as e:
        logger.error(f"Failed to store weekly narrative for {pitcher_id}: {e}")

    return result


def build_season_summary(pitcher_id: str) -> dict:
    """Build a full-season summary for the Season tab.

    Returns stats, timeline, rotation signature, outing recovery curves,
    sleep-vs-arm-feel correlation, and weekly narratives.
    """
    from bot.services import db as _db
    from datetime import date as _date

    profile = load_profile(pitcher_id)
    pitcher_name = profile.get("name", pitcher_id)
    rotation_length = profile.get("rotation_length", 7)

    # Fetch all entries (full season), sort chronologically
    entries = _db.get_daily_entries(pitcher_id, limit=365)
    entries.sort(key=lambda e: e.get("date", ""))

    # --- Training entries with arm_feel ---
    training_entries = []
    for e in entries:
        pre = e.get("pre_training")
        af = None
        if isinstance(pre, dict):
            af = pre.get("arm_feel")
        if af is None:
            af = e.get("arm_feel")
        if af is not None:
            training_entries.append(e)

    def _get_arm_feel(entry):
        pre = entry.get("pre_training")
        if isinstance(pre, dict) and pre.get("arm_feel") is not None:
            return pre["arm_feel"]
        return entry.get("arm_feel")

    def _get_sleep(entry):
        pre = entry.get("pre_training")
        if isinstance(pre, dict):
            return pre.get("sleep_hours")
        return None

    def _get_flag(entry):
        pre = entry.get("pre_training")
        if isinstance(pre, dict):
            return pre.get("flag_level", "green")
        return "green"

    # --- Summary stats ---
    feels = [_get_arm_feel(e) for e in training_entries]
    sleeps = [_get_sleep(e) for e in training_entries if _get_sleep(e) is not None]
    outing_entries = [e for e in entries if e.get("outing")]

    avg_arm_feel = round(sum(feels) / len(feels), 1) if feels else None
    avg_sleep = round(sum(sleeps) / len(sleeps), 1) if sleeps else None
    total_starts = len(outing_entries)

    # Current streak
    check_dates = set()
    for e in entries:
        d = e.get("date")
        if d and _get_arm_feel(e) is not None:
            check_dates.add(d)
    current_streak = 0
    day = _date.today()
    while day.isoformat() in check_dates:
        current_streak += 1
        day = day - timedelta(days=1)

    # --- Season label ---
    if training_entries:
        first_month = int(training_entries[0].get("date", "2026-01-01")[5:7])
    else:
        first_month = datetime.now(CHICAGO_TZ).month
    year = datetime.now(CHICAGO_TZ).year
    season_label = f"{'Fall' if 8 <= first_month <= 11 else 'Spring'} {year}"

    # --- Timeline ---
    timeline = []
    for e in training_entries:
        timeline.append({
            "date": e.get("date"),
            "arm_feel": _get_arm_feel(e),
            "is_outing": e.get("outing") is not None,
            "flag_level": _get_flag(e),
            "sleep_hours": _get_sleep(e),
            "rotation_day": e.get("rotation_day") or e.get("days_since_outing"),
        })

    # --- Rotation signature ---
    rotation_signature = None
    rot_buckets = {}  # rotation_day -> list of arm_feel values
    for e in training_entries:
        rd = e.get("rotation_day") or e.get("days_since_outing")
        if rd is not None:
            rd = int(rd)
            if rd not in rot_buckets:
                rot_buckets[rd] = []
            rot_buckets[rd].append(_get_arm_feel(e))

    if sum(len(v) for v in rot_buckets.values()) >= 5:
        bars = []
        for day_num in range(rotation_length):
            vals = rot_buckets.get(day_num, [])
            if vals:
                bars.append({
                    "day": day_num,
                    "avg_feel": round(sum(vals) / len(vals), 1),
                    "count": len(vals),
                })
            else:
                bars.append({"day": day_num, "avg_feel": None, "count": 0})

        valid_bars = [b for b in bars if b["avg_feel"] is not None]
        best_day = max(valid_bars, key=lambda b: b["avg_feel"])["day"] if valid_bars else None
        low_days = [b["day"] for b in valid_bars if b["avg_feel"] is not None and b["avg_feel"] < 7.0]

        insight = ""
        ask_prompt = ""
        if low_days:
            low_str = ", ".join(str(d) for d in low_days)
            if len(low_days) == 1:
                insight = f"Day {low_str} is your lowest. Watch forearm going into Day {low_days[0]}."
                ask_prompt = f"Why is my arm feel lower on Day {low_str} of my rotation?"
            else:
                insight = f"Days {low_str} are your lowest. Watch forearm going into Day {low_days[0]}."
                ask_prompt = f"Why is my arm feel lower on Days {low_str} of my rotation?"

        rotation_signature = {
            "bars": bars,
            "best_day": best_day,
            "low_days": low_days,
            "insight": insight,
            "ask_prompt": ask_prompt,
        }

    # --- Outing history with recovery curves ---
    outings = []
    for i, e in enumerate(entries):
        outing = e.get("outing")
        if not outing:
            continue

        post_arm_feel = outing.get("arm_feel") or outing.get("post_arm_feel")
        pitch_count = outing.get("pitch_count")

        # Collect recovery: arm_feel from the next 4 entries after the outing
        recovery = []
        for offset in range(1, 5):
            if i + offset < len(entries):
                next_e = entries[i + offset]
                next_af = _get_arm_feel(next_e)
                if next_af is not None:
                    recovery.append({"day": f"D+{offset}", "arm_feel": next_af})

        # How many days to get back to 7+
        recovery_days = None
        for r in recovery:
            if r["arm_feel"] >= 7:
                recovery_days = int(r["day"].split("+")[1])
                break

        # Generate insight
        insight = ""
        if recovery_days is not None:
            if recovery_days <= 2:
                insight = f"{recovery_days}-day recovery."
                if pitch_count and pitch_count < 75:
                    insight += f" Under 75 pitches, back to 7+ by D+{recovery_days}."
                elif post_arm_feel and post_arm_feel >= 7:
                    insight += " Post-arm feel was solid."
            else:
                insight = f"Took {recovery_days} days to get back to 7."
        elif recovery:
            insight = f"Still recovering — haven't reached 7+ in the {len(recovery)} days tracked."

        outings.append({
            "date": e.get("date"),
            "pitch_count": pitch_count,
            "post_arm_feel": post_arm_feel,
            "recovery": recovery,
            "recovery_days": recovery_days,
            "insight": insight,
            "ask_prompt": f"Why did my recovery take {recovery_days or 'so many'} days after the {e.get('date', '')} start?",
        })

    outings.reverse()  # most recent first

    # --- Enrich outings with schedule data + upcoming games ---
    upcoming_games = []
    try:
        outing_dates = [o["date"] for o in outings if o.get("date")]
        schedule_map = _db.get_schedule_by_dates(outing_dates)
        for o in outings:
            game = schedule_map.get(o.get("date"))
            if game:
                o["opponent"] = game.get("opponent")
                o["home_away"] = game.get("home_away")

        # Upcoming games not yet logged as outings
        today_str = _date.today().isoformat()
        outing_date_set = set(outing_dates)
        raw_upcoming = _db.get_upcoming_games(today_str, days=30)
        for g in raw_upcoming:
            if g["game_date"] not in outing_date_set:
                upcoming_games.append({
                    "game_date": g["game_date"],
                    "opponent": g.get("opponent"),
                    "home_away": g.get("home_away"),
                    "start_time": g.get("start_time"),
                })
    except Exception as e:
        logger.warning("Schedule enrichment failed: %s", e)

    # --- WHOOP overlay on timeline ---
    has_whoop = False
    try:
        from bot.services.whoop import is_linked
        if is_linked(pitcher_id):
            whoop_rows = _db.get_whoop_daily_range(pitcher_id, days=365)
            if whoop_rows:
                has_whoop = True
                whoop_by_date = {r["date"]: r for r in whoop_rows}
                for t in timeline:
                    w = whoop_by_date.get(t["date"])
                    t["recovery_score"] = w.get("recovery_score") if w else None
    except Exception as e:
        logger.warning("WHOOP overlay skipped for %s: %s", pitcher_id, e)

    # --- WHOOP weekly card data ---
    whoop_week = None
    if has_whoop:
        try:
            today_str = _date.today().isoformat()
            week_ago = (_date.today() - timedelta(days=7)).isoformat()
            two_weeks_ago = (_date.today() - timedelta(days=14)).isoformat()

            this_week = [r for r in whoop_rows if r.get("date") and r["date"] >= week_ago]
            this_week.sort(key=lambda r: r["date"])
            prior_week = [r for r in whoop_rows if r.get("date") and two_weeks_ago <= r["date"] < week_ago]

            today_whoop = whoop_by_date.get(today_str, {})

            recoveries = [r["recovery_score"] for r in this_week if r.get("recovery_score") is not None]
            hrvs = [r["hrv_rmssd"] for r in this_week if r.get("hrv_rmssd") is not None]
            sleep_hrs = [r["sleep_hours"] for r in this_week if r.get("sleep_hours") is not None]

            # HRV trend: this week avg vs prior week avg
            prior_hrvs = [r["hrv_rmssd"] for r in prior_week if r.get("hrv_rmssd") is not None]
            hrv_trend_pct = None
            if hrvs and prior_hrvs:
                this_avg = sum(hrvs) / len(hrvs)
                prior_avg = sum(prior_hrvs) / len(prior_hrvs)
                if prior_avg > 0:
                    hrv_trend_pct = round((this_avg - prior_avg) / prior_avg * 100)

            # HRV sparkline
            day_letters = {0: "M", 1: "T", 2: "W", 3: "T", 4: "F", 5: "S", 6: "S"}
            hrv_sparkline = []
            hrv_sparkline_labels = []
            for r in this_week:
                if r.get("hrv_rmssd") is not None:
                    hrv_sparkline.append(round(r["hrv_rmssd"], 1))
                    d = _date.fromisoformat(r["date"])
                    hrv_sparkline_labels.append(day_letters.get(d.weekday(), "?"))

            # Insight
            parts = []
            if hrv_trend_pct is not None:
                direction = "up" if hrv_trend_pct > 0 else "down"
                parts.append(f"HRV {direction} {abs(hrv_trend_pct)}% week-over-week.")
            if today_whoop.get("yesterday_strain") is not None:
                strain = today_whoop["yesterday_strain"]
                level = "light" if strain < 8 else "moderate" if strain < 14 else "high"
                parts.append(f"Strain {level}.")
            if recoveries:
                avg_rec = sum(recoveries) / len(recoveries)
                if avg_rec >= 67:
                    parts.append("Body handling load well going into your next start.")
                elif avg_rec >= 34:
                    parts.append("Recovery moderate — watch for accumulation.")

            ask_parts = []
            if hrv_trend_pct is not None and hrv_trend_pct > 0:
                ask_parts.append("Why is HRV trending up?")
            elif hrv_trend_pct is not None and hrv_trend_pct < -5:
                ask_parts.append("Why is my HRV declining?")
            else:
                ask_parts.append("How is my body handling the current training load?")

            whoop_week = {
                "today": {
                    "recovery_score": today_whoop.get("recovery_score"),
                    "hrv_rmssd": round(today_whoop["hrv_rmssd"], 1) if today_whoop.get("hrv_rmssd") else None,
                    "sleep_performance": today_whoop.get("sleep_performance"),
                    "sleep_hours": today_whoop.get("sleep_hours"),
                    "yesterday_strain": today_whoop.get("yesterday_strain"),
                },
                "avg_recovery": round(sum(recoveries) / len(recoveries)) if recoveries else None,
                "avg_sleep_hours": round(sum(sleep_hrs) / len(sleep_hrs), 1) if sleep_hrs else None,
                "hrv_trend_pct": hrv_trend_pct,
                "hrv_sparkline": hrv_sparkline,
                "hrv_sparkline_labels": hrv_sparkline_labels,
                "insight": " ".join(parts) if parts else None,
                "ask_prompt": ask_parts[0] if ask_parts else None,
            }
        except Exception as e:
            logger.warning("WHOOP weekly card skipped for %s: %s", pitcher_id, e)

    # --- Timeline insight (arm feel + recovery correlation) ---
    timeline_insight = None
    if has_whoop and outings:
        low_rec_low_arm = 0
        low_rec_total = 0
        for t in timeline:
            rec = t.get("recovery_score")
            if rec is not None and rec < 67:
                low_rec_total += 1
                if t["arm_feel"] <= 6:
                    low_rec_low_arm += 1
        if low_rec_total >= 2:
            timeline_insight = (
                f"Sub-67% recovery days produced arm feel 6 or below "
                f"in {low_rec_low_arm} of {low_rec_total} instances this season."
            )
        elif low_rec_total == 0 and len(timeline) >= 5:
            timeline_insight = "Recovery has stayed above 67% all season — arm feel is tracking consistently."

    # --- Fingerprint insight (pitch count vs recovery) ---
    fingerprint_insight = None
    if len(outings) >= 2:
        high_pc = [o for o in outings if o.get("pitch_count") and o["pitch_count"] >= 75]
        low_pc = [o for o in outings if o.get("pitch_count") and o["pitch_count"] < 75]
        high_days = [o["recovery_days"] for o in high_pc if o.get("recovery_days")]
        low_days = [o["recovery_days"] for o in low_pc if o.get("recovery_days")]
        if high_days and low_days:
            h_avg = sum(high_days) / len(high_days)
            l_avg = sum(low_days) / len(low_days)
            if h_avg > l_avg:
                fingerprint_insight = (
                    f"After 75+ pitches you average {h_avg:.0f} days to return to baseline. "
                    f"Sub-75 pitch outings recover {h_avg - l_avg:.0f} day{'s' if h_avg - l_avg > 1 else ''} faster."
                )
        elif high_days:
            h_avg = sum(high_days) / len(high_days)
            fingerprint_insight = f"After 75+ pitches you average {h_avg:.0f} days to return to baseline."

    # --- Sleep vs arm feel correlation ---
    sleep_correlation = None
    points = []
    under_7_count = 0
    under_7_low_feel_count = 0

    # Pair night N sleep with morning N+1 arm feel
    for i in range(len(training_entries) - 1):
        sleep_val = _get_sleep(training_entries[i])
        next_af = _get_arm_feel(training_entries[i + 1])
        if sleep_val is not None and next_af is not None:
            points.append({"sleep": sleep_val, "arm_feel": next_af})
            if sleep_val < 7:
                under_7_count += 1
                if next_af < 7:
                    under_7_low_feel_count += 1

    if len(points) >= 3:
        if under_7_count > 0:
            insight = (
                f"Nights under 7h correlated with lower arm feel the following morning "
                f"in {under_7_low_feel_count} of {under_7_count} instances this season."
            )
        else:
            insight = "You've consistently slept 7+ hours. Keep it up — that's your recovery edge."
        sleep_correlation = {
            "points": points,
            "under_7_count": under_7_count,
            "under_7_low_feel_count": under_7_low_feel_count,
            "insight": insight,
            "ask_prompt": "How does my sleep affect my arm feel? Show me the pattern.",
        }

    # --- Weekly narratives ---
    raw_narratives = _db.get_weekly_summaries(pitcher_id, limit=20)
    weekly_narratives = []
    for n in raw_narratives:
        weekly_narratives.append({
            "week_start": n.get("week_start"),
            "headline": n.get("headline", ""),
            "narrative": n.get("narrative", ""),
        })

    return {
        "pitcher_name": pitcher_name,
        "season_label": season_label,
        "total_checkins": len(training_entries),
        "has_whoop": has_whoop,
        "stats": {
            "avg_arm_feel": avg_arm_feel,
            "avg_sleep": avg_sleep,
            "total_starts": total_starts,
            "current_streak": current_streak,
        },
        "timeline": timeline,
        "timeline_insight": timeline_insight,
        "rotation_signature": rotation_signature,
        "outings": outings,
        "upcoming_games": upcoming_games,
        "fingerprint_insight": fingerprint_insight,
        "sleep_correlation": sleep_correlation,
        "whoop_week": whoop_week,
    }


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
