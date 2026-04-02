"""Game appearance detector — auto-updates pitcher model after games.

Checks the schedule table for games today/yesterday, then updates
pitcher_training_model for relievers who may have appeared. Since we
can't scrape box scores automatically (no reliable public API), this
module:
1. Detects game days from the schedule table
2. Sends a Telegram prompt to relievers asking if they appeared
3. For pitchers who report via /outing, the outing_service already
   updates the model — this is the gap-filler for unreported appearances.

Future: integrate with UChicago athletics box score page when available.
"""

import logging
from datetime import datetime, timedelta
from bot.config import CHICAGO_TZ
from bot.services.db import get_client, get_training_model, upsert_training_model

logger = logging.getLogger(__name__)


def get_games_on_date(date_str: str) -> list:
    """Return schedule rows for a given date."""
    resp = (get_client().table("schedule")
            .select("*")
            .eq("game_date", date_str)
            .execute())
    return resp.data or []


def get_unreported_relievers(date_str: str) -> list:
    """Find relievers who haven't logged an outing on a game day.

    Returns list of dicts: { pitcher_id, name, telegram_id, chat_id }
    """
    from bot.services.db import list_pitchers, get_daily_entry

    pitchers = list_pitchers()
    unreported = []

    for p in pitchers:
        role = p.get("role", "")
        if "reliever" not in role:
            continue

        pitcher_id = p.get("pitcher_id")
        telegram_id = p.get("telegram_id")
        if not telegram_id:
            continue

        # Check if they already logged an outing today
        entry = get_daily_entry(pitcher_id, date_str)
        if entry and entry.get("outing"):
            continue  # Already reported

        # Check if they already have a throwing entry in weekly state
        model = get_training_model(pitcher_id)
        week_state = model.get("current_week_state") or {}
        days = week_state.get("days") or []
        already_tracked = False
        for d in days:
            if d.get("date") == date_str and d.get("threw") and d.get("throw_type") == "game":
                already_tracked = True
                break
        if already_tracked:
            continue

        unreported.append({
            "pitcher_id": pitcher_id,
            "name": p.get("name", pitcher_id),
            "telegram_id": telegram_id,
        })

    return unreported


async def prompt_relievers_after_game(bot, date_str: str = None):
    """Send a check-in message to relievers after a game day.

    Called as a scheduled job ~30 minutes after game end.
    """
    if not date_str:
        date_str = datetime.now(CHICAGO_TZ).strftime("%Y-%m-%d")

    games = get_games_on_date(date_str)
    if not games:
        logger.info(f"No games on {date_str}, skipping reliever prompt")
        return

    game = games[0]
    opponent = game.get("opponent", "")

    unreported = get_unreported_relievers(date_str)
    if not unreported:
        logger.info(f"All relievers reported or no relievers to check on {date_str}")
        return

    for p in unreported:
        try:
            msg = (
                f"Game vs {opponent} today — did you get in? "
                f"If you threw, use /outing to log your pitch count and arm feel."
            )
            await bot.send_message(chat_id=p["telegram_id"], text=msg)
            logger.info(f"Prompted {p['name']} about game appearance on {date_str}")
        except Exception as e:
            logger.warning(f"Failed to prompt {p['name']}: {e}")


def update_pitcher_game_appearance(
    pitcher_id: str,
    date_str: str,
    innings_pitched: float = None,
    pitch_count: int = None,
):
    """Manually record a game appearance in the pitcher training model.

    Called when we detect or are told a pitcher appeared in a game.
    The outing_service handles the full flow — this is for when we
    learn about it through the scraper/schedule rather than /outing.
    """
    model = get_training_model(pitcher_id)

    # Estimate pitch count from innings if not provided
    if pitch_count is None and innings_pitched is not None:
        pitch_count = int(innings_pitched * 15)  # ~15 pitches per IP

    # Update model fields
    model["last_outing_date"] = date_str
    if pitch_count:
        model["last_outing_pitches"] = pitch_count
    model["days_since_outing"] = 0

    # Update weekly state
    week_state = dict(model.get("current_week_state") or {})
    days = list(week_state.get("days") or [])

    today_entry = None
    for d in days:
        if d.get("date") == date_str:
            today_entry = d
            break

    if not today_entry:
        today_entry = {
            "date": date_str,
            "threw": True,
            "throw_type": "game",
            "throw_intensity": 100,
            "lifted": False,
            "lift_focus": None,
            "exercises_completed": [],
            "exercises_skipped": [],
            "exercises_swapped": [],
        }
        days.append(today_entry)
    else:
        today_entry["threw"] = True
        today_entry["throw_type"] = "game"
        today_entry["throw_intensity"] = 100

    # Update throwing load
    load = week_state.get("throwing_load") or {}
    load["sessions"] = load.get("sessions", 0) + 1
    load["max_intensity"] = 100
    if pitch_count:
        load["total_throws"] = load.get("total_throws", 0) + pitch_count
    week_state["throwing_load"] = load
    week_state["days"] = days

    # Recompute next-day suggestion
    from bot.services.weekly_model import compute_next_day_suggestion
    from bot.services.context_manager import load_profile
    profile = load_profile(pitcher_id)
    suggestion = compute_next_day_suggestion(profile, {**model, "current_week_state": week_state})
    week_state["next_day_suggestion"] = suggestion

    model["current_week_state"] = week_state
    upsert_training_model(pitcher_id, model)
    logger.info(f"Recorded game appearance for {pitcher_id} on {date_str}: {pitch_count} pitches")
