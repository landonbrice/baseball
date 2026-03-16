"""Telegram initData HMAC-SHA256 validation and pitcher resolution."""

import hashlib
import hmac
import json
from urllib.parse import parse_qs, unquote

from bot.config import TELEGRAM_BOT_TOKEN


def validate_init_data(init_data: str) -> dict | None:
    """Validate Telegram WebApp initData using HMAC-SHA256.

    Returns parsed user data if valid, None otherwise.
    """
    if not init_data or not TELEGRAM_BOT_TOKEN:
        return None

    parsed = parse_qs(init_data)
    received_hash = parsed.pop("hash", [None])[0]
    if not received_hash:
        return None

    # Build check string: sorted key=value pairs joined by newline
    pairs = []
    for key in sorted(parsed.keys()):
        val = unquote(parsed[key][0])
        pairs.append(f"{key}={val}")
    check_string = "\n".join(pairs)

    # HMAC: secret_key = HMAC-SHA256(bot_token, "WebAppData")
    secret = hmac.new(TELEGRAM_BOT_TOKEN.encode(), b"WebAppData", hashlib.sha256).digest()
    computed = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed, received_hash):
        return None

    # Extract user info
    user_raw = parsed.get("user", [None])[0]
    if user_raw:
        return json.loads(unquote(user_raw))
    return None


def resolve_pitcher(telegram_id: int) -> str | None:
    """Resolve telegram_id to pitcher_id."""
    from bot.services.context_manager import get_pitcher_id_by_telegram
    return get_pitcher_id_by_telegram(telegram_id)
