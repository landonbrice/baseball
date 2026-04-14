"""Shared bot utilities — keyboards, constants."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def build_rating_keyboard(callback_prefix: str, emoji_low: str = "💀",
                          emoji_high: str = "💪") -> InlineKeyboardMarkup:
    """Build a 1-10 rating inline keyboard."""
    keyboard = [
        [
            InlineKeyboardButton(f"1 {emoji_low}", callback_data=f"{callback_prefix}_1"),
            InlineKeyboardButton("2", callback_data=f"{callback_prefix}_2"),
            InlineKeyboardButton("3", callback_data=f"{callback_prefix}_3"),
            InlineKeyboardButton("4", callback_data=f"{callback_prefix}_4"),
            InlineKeyboardButton("5", callback_data=f"{callback_prefix}_5"),
        ],
        [
            InlineKeyboardButton("6", callback_data=f"{callback_prefix}_6"),
            InlineKeyboardButton("7", callback_data=f"{callback_prefix}_7"),
            InlineKeyboardButton("8", callback_data=f"{callback_prefix}_8"),
            InlineKeyboardButton("9", callback_data=f"{callback_prefix}_9"),
            InlineKeyboardButton(f"10 {emoji_high}", callback_data=f"{callback_prefix}_10"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def build_completion_keyboard() -> InlineKeyboardMarkup:
    """Build the post-plan completion keyboard."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ All done", callback_data="plan_done"),
            InlineKeyboardButton("⏭ Skipped some", callback_data="plan_skipped"),
        ],
        [
            InlineKeyboardButton("📊 View dashboard", callback_data="plan_dashboard"),
        ],
    ])
