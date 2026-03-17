"""Telegram initData HMAC-SHA256 validation and pitcher resolution."""

import hashlib
import hmac
import json
import sys
from urllib.parse import unquote

from bot.config import TELEGRAM_BOT_TOKEN


def validate_init_data(init_data: str) -> dict | None:
    """Validate Telegram WebApp initData using HMAC-SHA256.

    Returns parsed user data if valid, None otherwise.
    """
    print(f"[AUTH] validate_init_data called, initData length={len(init_data) if init_data else 0}", flush=True)
    print(f"[AUTH] TELEGRAM_BOT_TOKEN set: {bool(TELEGRAM_BOT_TOKEN)}", flush=True)

    if not init_data or not TELEGRAM_BOT_TOKEN:
        print(f"[AUTH] Early return: init_data={bool(init_data)}, token={bool(TELEGRAM_BOT_TOKEN)}", flush=True)
        return None

    # Parse initData as url-encoded key=value pairs
    raw_pairs = {}
    for part in init_data.split("&"):
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        raw_pairs[k] = v

    print(f"[AUTH] Parsed keys: {list(raw_pairs.keys())}", flush=True)

    received_hash = raw_pairs.pop("hash", None)
    if not received_hash:
        print("[AUTH] No hash in initData", flush=True)
        return None

    # Build check string: sorted key=value pairs joined by newline
    check_string = "\n".join(f"{k}={unquote(v)}" for k, v in sorted(raw_pairs.items()))
    print(f"[AUTH] Check string keys: {sorted(raw_pairs.keys())}", flush=True)

    # HMAC: secret_key = HMAC-SHA256("WebAppData", bot_token)
    secret = hmac.new(b"WebAppData", TELEGRAM_BOT_TOKEN.encode(), hashlib.sha256).digest()
    computed = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()

    hmac_match = hmac.compare_digest(computed, received_hash)
    print(f"[AUTH] HMAC match: {hmac_match}", flush=True)
    if not hmac_match:
        print(f"[AUTH] HMAC mismatch: computed={computed[:16]}... received={received_hash[:16]}...", flush=True)
        return None

    # Extract user info
    user_raw = raw_pairs.get("user")
    if user_raw:
        user = json.loads(unquote(user_raw))
        print(f"[AUTH] Extracted user: id={user.get('id')}, username={user.get('username')}", flush=True)
        return user

    print("[AUTH] No user field in initData", flush=True)
    return None


def resolve_pitcher(telegram_id: int, username: str = None) -> str | None:
    """Resolve telegram_id to pitcher_id."""
    print(f"[AUTH] resolve_pitcher called: telegram_id={telegram_id}, username={username}", flush=True)
    from bot.services.context_manager import get_pitcher_id_by_telegram
    try:
        result = get_pitcher_id_by_telegram(telegram_id, username)
        print(f"[AUTH] resolve_pitcher result: {result}", flush=True)
        return result
    except Exception as e:
        print(f"[AUTH] resolve_pitcher EXCEPTION: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
        return None
