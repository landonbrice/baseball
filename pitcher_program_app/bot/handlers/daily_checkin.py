"""Daily check-in flow using ConversationHandler.

Phase 3: Coaching-quality conversation. Same data gathered, but the bot
responds to what you say before asking the next question. Smart defaults
skip steps when data is already known.

Flow (full): arm report → acknowledgment + lift pref → throw intent → schedule → plan
Flow (day-after): arm report → acknowledgment → confirm recovery day → plan
Flow (schedule known): arm report → acknowledgment + lift pref → throw intent → plan
"""

import logging
import json
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from bot.services.checkin_service import process_checkin
from bot.services.context_manager import (
    load_profile,
    load_log,
    save_log,
    append_context,
    get_pitcher_id_by_telegram,
    increment_days_since_outing,
    update_active_flags,
    get_recent_entries,
)
from bot.utils import build_rating_keyboard, build_completion_keyboard

logger = logging.getLogger(__name__)

# Conversation states
ARM_REPORT, LIFT_PREF, THROW_INTENT, SCHEDULE, RELIEVER_THREW, RECOVERY_CONFIRM, LOW_ARM_CLARIFY = range(7)


# ---------------------------------------------------------------------------
# Helpers — smart defaults and context awareness
# ---------------------------------------------------------------------------

def _get_yesterday_entry(pitcher_id):
    """Return yesterday's log entry if it exists."""
    try:
        recent = get_recent_entries(pitcher_id, n=3)
        if not recent:
            return None
        yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        for e in reversed(recent):
            if e.get("date") == yesterday_str:
                return e
        return None
    except Exception:
        return None


def _get_soreness_areas(yesterday_entry):
    """Extract specific soreness areas from yesterday's entry."""
    if not yesterday_entry:
        return []
    notes = (yesterday_entry.get("pre_training") or {}).get("soreness_notes", "")
    if not notes:
        return []
    areas = []
    area_keywords = {
        "forearm": "forearm", "elbow": "elbow", "medial": "medial elbow",
        "shoulder": "shoulder", "bicep": "bicep", "lat": "lat",
        "ucl": "UCL area", "scap": "scapula", "back": "back",
    }
    notes_lower = notes.lower()
    for keyword, label in area_keywords.items():
        if keyword in notes_lower:
            areas.append(label)
    return areas


def _is_recovery_day(days_since, role):
    """Return True if this is a recovery day (day 0-1 post-outing)."""
    return days_since <= 1


def _schedule_already_known(flags):
    """Return True if next outing is already set and recent."""
    next_days = flags.get("next_outing_days")
    return next_days is not None and next_days > 0


def _build_arm_acknowledgment(arm_feel, arm_report, days_since, concern_areas=None):
    """Build a coaching response to the arm feel report before asking the next question."""
    if arm_feel is None:
        arm_feel = 4  # fallback

    # Day-after-outing gets special treatment
    if days_since <= 1:
        if arm_feel >= 4:
            return "Good recovery. We'll keep it light today — recovery flush and blood flow."
        elif arm_feel == 3:
            return "Day-after at a 3 — that's normal. Recovery focus, nothing heavy."
        else:
            return "That's lower than we'd like day-after. Let's prioritize recovery and keep an eye on it."

    # Severe concern — immediate coaching response
    if arm_feel <= 2:
        if concern_areas:
            areas = ", ".join(concern_areas[:2])
            return f"Noted the {areas} concern. We'll go easy today — I'm flagging this."
        return "Noted — we'll keep things light and protective today."

    # Mild concern with specific areas
    if arm_feel == 3:
        if concern_areas:
            areas = ", ".join(concern_areas[:2])
            return f"Got it — some {areas} stuff going on. I'll factor that into your plan."
        return "Got it — I'll factor that in. We'll be smart about it."

    # Feeling good
    if arm_feel >= 4:
        if arm_report and any(w in arm_report.lower() for w in ["great", "perfect", "amazing", "100"]):
            return "Good to hear."
        return "Arm's feeling solid."

    return "Got it."


def _build_adaptive_greeting(first_name, pitcher_id, flags, days_since, role):
    """Build a context-aware opening message referencing yesterday's data."""
    base = f"Morning {first_name}."

    yesterday = _get_yesterday_entry(pitcher_id)

    # Reference specific soreness from yesterday
    if yesterday:
        areas = _get_soreness_areas(yesterday)
        if areas:
            return base + f" Yesterday you mentioned some {areas[0]} stuff — how's that feeling today?"

        yesterday_arm = (yesterday.get("pre_training") or {}).get("arm_feel")
        if yesterday_arm is not None:
            if yesterday_arm <= 2:
                return base + f" Yesterday you reported your arm at {yesterday_arm}/5 — how's it feeling today?"
            elif yesterday_arm == 3:
                return base + " Arm was at a 3 yesterday. Any better today?"

        if yesterday.get("skip_notes"):
            return base + " You mentioned skipping some stuff yesterday. How's the arm?"

    # Day-after-outing
    if days_since == 1:
        return base + " Day after — how's the arm recovering?"

    # Pre-outing
    next_outing = flags.get("next_outing_days")
    if next_outing and next_outing <= 1:
        return base + " You've got an outing coming up. How's the arm feeling?"

    # Check for active injury flags in profile
    try:
        profile = load_profile(pitcher_id)
        injuries = profile.get("injury_history", [])
        active_injuries = [i for i in injuries if i.get("flag_level") in ("yellow", "red")]
        if active_injuries:
            area = active_injuries[0].get("area", "").replace("_", " ")
            if area:
                return base + f" How's the {area} feeling today?"
    except Exception:
        pass

    return base + " How's the arm feeling?"


# ---------------------------------------------------------------------------
# Conversation handlers
# ---------------------------------------------------------------------------

async def start_checkin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Begin the daily check-in flow. Adapts opening based on yesterday's data."""
    pitcher_id = get_pitcher_id_by_telegram(update.effective_user.id, update.effective_user.username)
    if not pitcher_id:
        await update.message.reply_text(
            "I don't have a profile for you yet. Ask your coach to set you up."
        )
        return ConversationHandler.END

    context.user_data["pitcher_id"] = pitcher_id
    context.user_data["conversation_history"] = []

    # Read current rotation state (increment deferred until successful check-in)
    profile = load_profile(pitcher_id)
    phase = (profile.get("active_flags") or {}).get("phase", "")
    flags = profile.get("active_flags", {})
    days_since = flags.get("days_since_outing", 0)
    role = profile.get("role", "starter")
    first_name = profile.get("name", "").split()[0] if profile.get("name") else "there"

    # Store context for smart defaults later
    context.user_data["days_since"] = days_since
    context.user_data["role"] = role
    context.user_data["flags"] = flags
    context.user_data["schedule_known"] = _schedule_already_known(flags)

    # Record check-in start
    append_context(pitcher_id, "checkin_start", f"Check-in started (day {days_since})")

    # 8+ days without outing for starters
    if role == "starter" and days_since > 8:
        await update.message.reply_text(
            f"It's been {days_since} days since your last logged outing. "
            "Did you pitch recently? If so, use /outing to log it."
        )

    # Reliever "Did you throw?" branch
    if role == "reliever":
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Yes", callback_data="reliever_threw_yes"),
                InlineKeyboardButton("No", callback_data="reliever_threw_no"),
            ]
        ])
        await update.message.reply_text(
            "Did you throw in a game yesterday?",
            reply_markup=keyboard,
        )
        return RELIEVER_THREW

    # Context-aware opening
    greeting = _build_adaptive_greeting(first_name, pitcher_id, flags, days_since, role)
    await update.message.reply_text(greeting)
    return ARM_REPORT


async def reliever_threw_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle reliever 'Did you throw?' response."""
    query = update.callback_query
    await query.answer()

    threw = query.data == "reliever_threw_yes"

    if threw:
        await query.edit_message_text(
            "Got it — use /outing to log your appearance, "
            "then come back and /checkin for today's plan."
        )
        return ConversationHandler.END

    await query.edit_message_text("No game appearance yesterday. Let's do your check-in.")
    await query.message.reply_text("How's the arm feeling?")
    return ARM_REPORT


async def arm_report_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle arm feel report. Acknowledges before asking the next question.

    Smart defaults:
    - Day 0-1 post-outing: auto-set recovery, skip to schedule/plan
    - Arm feel 1-2: auto-set rest day, skip throw intent
    """
    text = update.message.text.strip()
    days_since = context.user_data.get("days_since", 99)
    flags = context.user_data.get("flags", {})

    # Parse arm feel
    arm_feel = None
    arm_report = ""
    concern_areas = []
    try:
        num = int(text)
        if 1 <= num <= 5:
            arm_feel = num
        else:
            arm_report = text
    except ValueError:
        arm_report = text

    # Quick-classify free text for acknowledgment (full LLM classification happens at plan gen)
    if arm_feel is None and arm_report:
        arm_feel, concern_areas = _quick_classify(arm_report)

    context.user_data["arm_feel"] = arm_feel
    context.user_data["arm_report"] = arm_report
    context.user_data["concern_areas"] = concern_areas

    # Build coaching acknowledgment
    ack = _build_arm_acknowledgment(arm_feel, arm_report, days_since, concern_areas)

    # --- REFINEMENT 1: Recovery day — recommend + give choice ---
    if _is_recovery_day(days_since, context.user_data.get("role", "starter")):
        feel_comment = ""
        if arm_feel is not None:
            if arm_feel >= 4:
                feel_comment = f"arm's at a {arm_feel} — solid recovery"
            elif arm_feel == 3:
                feel_comment = f"arm's at a {arm_feel} — pretty typical day-after"
            else:
                feel_comment = f"arm's at a {arm_feel} — let's be careful"
        else:
            feel_comment = "day after"

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Recovery day", callback_data="recovery_yes"),
                InlineKeyboardButton("Something different", callback_data="recovery_no"),
            ]
        ])
        await update.message.reply_text(
            f"Day after, {feel_comment}. I'd keep it to recovery flush and blood flow. "
            "Want me to build that, or are you thinking something different?",
            reply_markup=keyboard,
        )
        return RECOVERY_CONFIRM

    # --- REFINEMENT 2: Arm feel 1-2 — probe before assuming protective ---
    if arm_feel is not None and arm_feel <= 2:
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Expected soreness", callback_data="lowarm_expected"),
                InlineKeyboardButton("Something feels off", callback_data="lowarm_concerned"),
            ]
        ])
        concern_note = ""
        if concern_areas:
            concern_note = f" ({', '.join(concern_areas[:2])})"
        await update.message.reply_text(
            f"{ack}{concern_note} That's on the lower end — is this soreness you'd "
            "expect given where you are in rotation, or does something feel different?",
            reply_markup=keyboard,
        )
        return LOW_ARM_CLARIFY

    # --- NORMAL FLOW: Acknowledge + ask lift preference ---
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Upper", callback_data="lift_upper"),
            InlineKeyboardButton("Lower", callback_data="lift_lower"),
            InlineKeyboardButton("Full body", callback_data="lift_full"),
        ],
        [
            InlineKeyboardButton("Rest day", callback_data="lift_rest"),
            InlineKeyboardButton("Your call", callback_data="lift_auto"),
        ],
    ])
    await update.message.reply_text(
        ack + " What are you thinking for a lift?",
        reply_markup=keyboard,
    )
    return LIFT_PREF


def _quick_classify(arm_report):
    """Fast rule-based classification for acknowledgment. Full LLM runs later."""
    report_lower = arm_report.lower()
    areas = []

    # Extract concern areas
    area_keywords = {
        "forearm": "forearm", "elbow": "elbow", "medial": "medial elbow",
        "shoulder": "shoulder", "bicep": "bicep", "ucl": "UCL area",
        "lat": "lat", "scap": "scapula",
    }
    for keyword, label in area_keywords.items():
        if keyword in report_lower:
            areas.append(label)

    if any(w in report_lower for w in ["great", "perfect", "amazing", "100", "feel good", "feels good", "no issues"]):
        return 5, []
    if any(w in report_lower for w in ["sharp", "shooting", "numb", "tingling", "swelling", "can't"]):
        return 1, areas or ["immediate_concern"]
    if any(w in report_lower for w in ["terrible", "really bad", "awful"]):
        return 2, areas or ["significant_concern"]
    if any(w in report_lower for w in ["tight", "sore", "stiff", "tender"]):
        return 3, areas or ["mild_concern"]
    if any(w in report_lower for w in ["good", "fine", "solid", "normal", "decent", "ok", "okay", "alright"]):
        return 4, []

    return None, areas  # Unknown — will be LLM-classified later


async def recovery_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle recovery day choice: build recovery plan or let pitcher choose differently."""
    query = update.callback_query
    await query.answer()

    choice = query.data
    flags = context.user_data.get("flags", {})

    if choice == "recovery_yes":
        # Pitcher accepts recovery day recommendation
        context.user_data["lift_preference"] = "rest"
        context.user_data["throw_intent"] = "none"
        await query.edit_message_text("Recovery day it is.")

        if _schedule_already_known(flags):
            await query.message.reply_text("Building your recovery plan...")
            return await _generate_plan_and_respond(query.message, context)
        else:
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("Tomorrow", callback_data="schedule_1"),
                    InlineKeyboardButton("2 days", callback_data="schedule_2"),
                    InlineKeyboardButton("3+ days", callback_data="schedule_3"),
                    InlineKeyboardButton("Not sure", callback_data="schedule_0"),
                ],
            ])
            await query.message.reply_text("When do you pitch next?", reply_markup=keyboard)
            return SCHEDULE
    else:
        # Pitcher wants something different — ask lift preference
        await query.edit_message_text("Got it — your call.")
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Upper", callback_data="lift_upper"),
                InlineKeyboardButton("Lower", callback_data="lift_lower"),
                InlineKeyboardButton("Full body", callback_data="lift_full"),
            ],
            [
                InlineKeyboardButton("Light lift", callback_data="lift_auto"),
                InlineKeyboardButton("Rest day", callback_data="lift_rest"),
            ],
        ])
        await query.message.reply_text(
            "What are you thinking for a lift?",
            reply_markup=keyboard,
        )
        return LIFT_PREF


async def low_arm_clarify_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle arm feel 1-2 clarification: expected soreness vs something different."""
    query = update.callback_query
    await query.answer()

    choice = query.data
    flags = context.user_data.get("flags", {})

    if choice == "lowarm_expected":
        # Expected soreness — modified green, still protective but not shutdown
        await query.edit_message_text("Expected soreness — got it.")
        context.user_data["arm_clarification"] = "expected_soreness"

        # Offer lift preference (protective but not forced rest)
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Light upper", callback_data="lift_upper"),
                InlineKeyboardButton("Light lower", callback_data="lift_lower"),
            ],
            [
                InlineKeyboardButton("Rest day", callback_data="lift_rest"),
                InlineKeyboardButton("Your call", callback_data="lift_auto"),
            ],
        ])
        await query.message.reply_text(
            "We'll keep intensity down. Want to do a light lift or take a rest day?",
            reply_markup=keyboard,
        )
        return LIFT_PREF
    else:
        # Something feels off — protective mode, skip to plan
        await query.edit_message_text("Something feels off — flagging this.")
        context.user_data["arm_clarification"] = "concerned"
        context.user_data["lift_preference"] = "rest"
        context.user_data["throw_intent"] = "none"

        if _schedule_already_known(flags):
            await query.message.reply_text("Building a protective plan...")
            return await _generate_plan_and_respond(query.message, context)
        else:
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("Tomorrow", callback_data="schedule_1"),
                    InlineKeyboardButton("2 days", callback_data="schedule_2"),
                    InlineKeyboardButton("3+ days", callback_data="schedule_3"),
                    InlineKeyboardButton("Not sure", callback_data="schedule_0"),
                ],
            ])
            await query.message.reply_text(
                "We'll go protective today. When do you pitch next?",
                reply_markup=keyboard,
            )
            return SCHEDULE


async def lift_pref_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle lift preference selection."""
    query = update.callback_query
    await query.answer()

    pref = query.data.replace("lift_", "")
    context.user_data["lift_preference"] = pref

    pref_labels = {
        "upper": "Upper body", "lower": "Lower body", "full": "Full body",
        "rest": "Rest day", "auto": "I'll pick",
    }
    await query.edit_message_text(f"Lift: {pref_labels.get(pref, pref)}.")

    # --- SMART DEFAULT: Skip throw intent if rest day ---
    if pref == "rest":
        context.user_data["throw_intent"] = "none"
        flags = context.user_data.get("flags", {})
        if _schedule_already_known(flags):
            await query.message.reply_text("Rest day — building your plan.")
            return await _generate_plan_and_respond(query.message, context)
        else:
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("Tomorrow", callback_data="schedule_1"),
                    InlineKeyboardButton("2 days", callback_data="schedule_2"),
                    InlineKeyboardButton("3+ days", callback_data="schedule_3"),
                    InlineKeyboardButton("Not sure", callback_data="schedule_0"),
                ],
            ])
            await query.message.reply_text("When do you pitch next?", reply_markup=keyboard)
            return SCHEDULE

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Flat ground", callback_data="throw_flat_ground"),
            InlineKeyboardButton("Bullpen", callback_data="throw_bullpen"),
        ],
        [
            InlineKeyboardButton("Long toss", callback_data="throw_long_toss"),
            InlineKeyboardButton("Light catch", callback_data="throw_light_catch"),
            InlineKeyboardButton("No", callback_data="throw_none"),
        ],
    ])
    await query.message.reply_text("Throwing today?", reply_markup=keyboard)
    return THROW_INTENT


async def throw_intent_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle throwing intent selection."""
    query = update.callback_query
    await query.answer()

    intent = query.data.replace("throw_", "")
    context.user_data["throw_intent"] = intent

    label = intent.replace("_", " ").title()
    if intent == "none":
        label = "No throwing"
    await query.edit_message_text(f"Throwing: {label}.")

    # --- SMART DEFAULT: Skip schedule if already known ---
    flags = context.user_data.get("flags", {})
    if _schedule_already_known(flags):
        next_days = flags.get("next_outing_days")
        context.user_data["next_pitch_days"] = next_days
        await query.message.reply_text("Building your plan...")
        return await _generate_plan_and_respond(query.message, context)

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Tomorrow", callback_data="schedule_1"),
            InlineKeyboardButton("2 days", callback_data="schedule_2"),
            InlineKeyboardButton("3+ days", callback_data="schedule_3"),
            InlineKeyboardButton("Not sure", callback_data="schedule_0"),
        ],
    ])
    await query.message.reply_text("When do you pitch next?", reply_markup=keyboard)
    return SCHEDULE


async def schedule_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle schedule selection, then generate plan."""
    query = update.callback_query
    await query.answer()

    next_days = int(query.data.replace("schedule_", ""))
    context.user_data["next_pitch_days"] = next_days if next_days > 0 else None

    if next_days > 0:
        await query.edit_message_text(f"Next pitch: {next_days} day{'s' if next_days > 1 else ''}.")
    else:
        await query.edit_message_text("Next pitch: not sure.")

    await query.message.reply_text("Building your plan...")
    return await _generate_plan_and_respond(query.message, context)


async def _generate_plan_and_respond(message, context) -> int:
    """Shared plan generation + response delivery. Called from multiple exit points."""
    pitcher_id = context.user_data["pitcher_id"]
    arm_report = context.user_data.get("arm_report", "")
    arm_feel = context.user_data.get("arm_feel")
    lift_preference = context.user_data.get("lift_preference", "auto")
    throw_intent = context.user_data.get("throw_intent", "none")
    next_pitch_days = context.user_data.get("next_pitch_days")
    arm_clarification = context.user_data.get("arm_clarification", "")

    # Full LLM classification if quick-classify didn't resolve
    if arm_feel is None and arm_report:
        arm_feel, concern_areas = await _classify_arm_report(arm_report)
        context.user_data["arm_feel"] = arm_feel
    elif arm_feel is None:
        arm_feel = 4

    # Update schedule/rotation if specified
    if next_pitch_days and next_pitch_days > 0:
        profile = load_profile(pitcher_id)
        rotation = profile.get("rotation_length", 7)
        new_day = max(0, rotation - next_pitch_days)
        update_active_flags(pitcher_id, {
            "days_since_outing": new_day,
            "next_outing_days": next_pitch_days,
        })

    # Default sleep to profile baseline
    profile = load_profile(pitcher_id)
    sleep_hours = (profile.get("biometric_integration") or {}).get("avg_sleep_hours") or 7.0

    # Let the pitcher know we're working on it
    status_msg = await message.reply_text("Generating your plan...")

    try:
        result = await process_checkin(
            pitcher_id, arm_feel, sleep_hours,
            arm_report=arm_report,
            lift_preference=lift_preference,
            throw_intent=throw_intent,
            next_pitch_days=next_pitch_days,
            arm_clarification=arm_clarification,
        )

        # Increment rotation day only after successful check-in
        profile = load_profile(pitcher_id)
        phase = (profile.get("active_flags") or {}).get("phase", "")
        if not phase.startswith("return_to_throwing"):
            increment_days_since_outing(pitcher_id)

        # Remove the "generating" message
        try:
            await status_msg.delete()
        except Exception:
            pass

        # Handle plan generation failure (check-in data saved, but no plan)
        if not result.get("plan_narrative") and not result.get("morning_brief"):
            flag = result["flag_level"].upper()
            await message.reply_text(
                f"{flag} flag. Your check-in data has been saved.\n\n"
                "Plan generation had a hiccup — your exercises are based on your template today. "
                "You can try /checkin again for a personalized plan, or open the mini app."
            )
            return ConversationHandler.END

        # Send triage + brief
        flag = result["flag_level"].upper()
        brief = result.get("morning_brief") or result.get("triage_reasoning", "")
        await message.reply_text(f"{flag} flag. {brief}")

        for alert in result["alerts"]:
            await message.reply_text(f"⚠️ {alert}")

        # Dashboard link
        from bot.config import MINI_APP_URL
        if MINI_APP_URL:
            from telegram import WebAppInfo
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("Open full plan", web_app=WebAppInfo(url=MINI_APP_URL))]
            ])
            await message.reply_text(
                "Your plan is ready. Tap below for the full breakdown.",
                reply_markup=keyboard,
            )
        else:
            reply_markup = build_completion_keyboard()
            await message.reply_text(result["plan_narrative"], reply_markup=reply_markup)

        if result["weekly_summary"]:
            await message.reply_text(result["weekly_summary"])

    except Exception as e:
        logger.error(f"Error in check-in flow: {e}", exc_info=True)
        try:
            await status_msg.delete()
        except Exception:
            pass
        await message.reply_text(
            "There was an issue generating your plan. Your check-in data may not have been saved.\n\n"
            "Try /checkin again, or open the mini app for your last plan."
        )

    return ConversationHandler.END


async def _classify_arm_report(arm_report):
    """Classify free-text arm report into arm_feel (1-5) and concern areas via LLM."""
    # Try quick classification first
    arm_feel, areas = _quick_classify(arm_report)
    if arm_feel is not None:
        return arm_feel, areas

    # LLM classification for nuanced reports
    try:
        from bot.services.llm import call_llm
        response = await call_llm(
            "You classify pitcher arm reports. Return ONLY valid JSON, no other text.",
            f'Classify this arm report on a 1-5 scale (1=severe pain, 5=feels great). '
            f'Return: {{"arm_feel": <1-5>, "areas": ["area1"], "trend": "better|same|worse|unknown"}}\n\n'
            f'Report: "{arm_report}"',
            max_tokens=80,
        )
        data = json.loads(response.strip())
        return int(data.get("arm_feel", 4)), data.get("areas", [])
    except Exception as e:
        logger.warning(f"Arm report classification failed, defaulting to 4: {e}")
        return 4, areas


async def plan_completion_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle plan completion button presses (outside ConversationHandler)."""
    query = update.callback_query
    await query.answer()

    pitcher_id = context.user_data.get("pitcher_id")
    action = query.data

    if action == "plan_dashboard":
        from bot.config import MINI_APP_URL
        if MINI_APP_URL:
            from telegram import WebAppInfo
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("Open Dashboard", web_app=WebAppInfo(url=MINI_APP_URL))]
            ])
            await query.message.reply_text("Tap to open:", reply_markup=keyboard)
        else:
            await query.message.reply_text("Dashboard not configured yet.")
        await query.edit_message_reply_markup(reply_markup=None)
        return

    if pitcher_id:
        _update_log_completion(pitcher_id, action)

    await query.edit_message_reply_markup(reply_markup=None)

    if action == "plan_done":
        await query.message.reply_text("Logged as completed. Nice work.")
    elif action == "plan_skipped":
        context.user_data["awaiting_skip_details"] = True
        await query.message.reply_text(
            "Logged as partially completed. What did you skip or modify?\n\n"
            "Just a quick note — e.g., 'skipped plyocare, cut lifting short'"
        )


async def skip_details_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle free-text response about what was skipped."""
    if not context.user_data.get("awaiting_skip_details"):
        return
    context.user_data["awaiting_skip_details"] = False

    pitcher_id = context.user_data.get("pitcher_id")
    details = update.message.text.strip()

    if pitcher_id and details:
        log = load_log(pitcher_id)
        today = datetime.now().strftime("%Y-%m-%d")
        for entry in reversed(log.get("entries", [])):
            if entry.get("date") == today:
                entry["skip_notes"] = details
                break
        save_log(pitcher_id, log)
        append_context(pitcher_id, "feedback", f"Skipped: {details[:100]}")

    await update.message.reply_text("Got it — noted for your log.")


def _update_log_completion(pitcher_id, action):
    """Update the most recent log entry with completion status."""
    log = load_log(pitcher_id)
    today = datetime.now().strftime("%Y-%m-%d")
    for entry in reversed(log.get("entries", [])):
        if entry.get("date") == today:
            entry["actual_logged"] = "all_done" if action == "plan_done" else "skipped_some"
            break
    save_log(pitcher_id, log)


async def cancel_checkin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the check-in flow."""
    await update.message.reply_text("Check-in cancelled.")
    return ConversationHandler.END


def get_checkin_handler() -> ConversationHandler:
    """Build and return the ConversationHandler for daily check-in."""
    return ConversationHandler(
        entry_points=[CommandHandler("checkin", start_checkin)],
        states={
            RELIEVER_THREW: [CallbackQueryHandler(
                reliever_threw_callback, pattern=r"^reliever_threw_(yes|no)$"
            )],
            ARM_REPORT: [MessageHandler(filters.TEXT & ~filters.COMMAND, arm_report_handler)],
            RECOVERY_CONFIRM: [CallbackQueryHandler(
                recovery_confirm_callback, pattern=r"^recovery_(yes|no)$"
            )],
            LOW_ARM_CLARIFY: [CallbackQueryHandler(
                low_arm_clarify_callback, pattern=r"^lowarm_(expected|concerned)$"
            )],
            LIFT_PREF: [CallbackQueryHandler(lift_pref_callback, pattern=r"^lift_")],
            THROW_INTENT: [CallbackQueryHandler(throw_intent_callback, pattern=r"^throw_")],
            SCHEDULE: [CallbackQueryHandler(schedule_callback, pattern=r"^schedule_")],
        },
        fallbacks=[CommandHandler("cancel", cancel_checkin)],
    )
