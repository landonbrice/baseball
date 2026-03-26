"""Telegram initData HMAC-SHA256 validation and pitcher resolution."""

import hashlib
import hmac
import json
from urllib.parse import unquote

from bot.config import TELEGRAM_BOT_TOKEN


def validate_init_data(init_data: str):
    """Validate Telegram WebApp initData using HMAC-SHA256.

    Returns parsed user data if valid, None otherwise.
    """
    if not init_data or not TELEGRAM_BOT_TOKEN:
        return None

    # Parse initData as url-encoded key=value pairs
    raw_pairs = {}
    for part in init_data.split("&"):
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        raw_pairs[k] = v

    received_hash = raw_pairs.pop("hash", None)
    if not received_hash:
        return None

    # Build check string: sorted key=value pairs joined by newline
    check_string = "\n".join(f"{k}={unquote(v)}" for k, v in sorted(raw_pairs.items()))

    # HMAC: secret_key = HMAC-SHA256("WebAppData", bot_token)
    secret = hmac.new(b"WebAppData", TELEGRAM_BOT_TOKEN.encode(), hashlib.sha256).digest()
    computed = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed, received_hash):
        return None

    # Extract user info
    user_raw = raw_pairs.get("user")
    if user_raw:
        return json.loads(unquote(user_raw))
    return None


def resolve_pitcher(telegram_id: int, username: str = None):
    """Resolve telegram_id to pitcher_id."""
    from bot.services.context_manager import get_pitcher_id_by_telegram
    return get_pitcher_id_by_telegram(telegram_id, username)
