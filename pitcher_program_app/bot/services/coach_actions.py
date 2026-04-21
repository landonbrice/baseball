"""Telegram DM actions triggered by coaches."""
import logging
import os

from bot.services import db as _db

logger = logging.getLogger(__name__)

# Lazy-bind Bot at module scope so tests can patch `bot.services.coach_actions.Bot`.
# The telegram package is already imported elsewhere at bot startup
# (bot/main.py), so this import adds no real cost on the bot path.
try:
    from telegram import Bot  # type: ignore
except ImportError:  # pragma: no cover - defensive
    Bot = None  # type: ignore


async def send_nudge(pitcher_id: str, coach_name: str) -> int:
    """Send a Telegram nudge DM. Returns telegram_message_id.

    Raises:
        ValueError: pitcher not found or has no telegram_id.
    """
    try:
        pitcher = _db.get_pitcher(pitcher_id)
    except KeyError:
        raise ValueError(f"Pitcher not found: {pitcher_id}")

    chat_id = pitcher.get("telegram_id")
    if not chat_id:
        raise ValueError(f"No telegram_id for pitcher: {pitcher_id}")

    first_name = (pitcher.get("name") or "").split()[0]
    text = (
        f"Hey {first_name}, {coach_name} wants a quick check-in "
        f"— hit /checkin when you get a sec."
    )

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    bot = Bot(token=token)
    msg = await bot.send_message(chat_id=chat_id, text=text)
    return msg.message_id
