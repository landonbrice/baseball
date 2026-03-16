"""Generate 21 days of synthetic daily_log data for test_pitcher_001.

Creates realistic variance: arm feel 2-5, sleep 5.5-9h, 3 outings at 65/82/95 pitches.
At least one yellow flag day (arm feel 2, sleep ~5.5h).
"""

import json
import os
import random
from datetime import datetime, timedelta

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
LOG_PATH = os.path.join(DATA_DIR, "pitchers", "test_pitcher_001", "daily_log.json")

random.seed(42)

START_DATE = datetime(2026, 2, 22)
OUTING_DAYS = {0: 65, 7: 82, 14: 95}  # day_offset: pitch_count
YELLOW_FLAG_DAY = 9  # day after 2nd outing recovery


def generate_entries():
    entries = []
    rotation_day = 3  # start mid-rotation
    days_since_outing = 3

    for day_offset in range(21):
        date = START_DATE + timedelta(days=day_offset)
        date_str = date.strftime("%Y-%m-%d")

        is_outing = day_offset in OUTING_DAYS
        is_yellow = day_offset == YELLOW_FLAG_DAY

        # Arm feel: post-outing dips, yellow flag day = 2, otherwise 3-5
        if is_outing:
            arm_feel = 4
        elif is_yellow:
            arm_feel = 2
        elif days_since_outing == 1:
            arm_feel = 3
        elif days_since_outing == 2:
            arm_feel = random.choice([3, 4])
        else:
            arm_feel = random.choice([3, 4, 4, 5, 5])

        # Sleep: yellow flag day = 5.5, otherwise 6-9
        if is_yellow:
            sleep_hours = 5.5
        else:
            sleep_hours = round(random.uniform(6.0, 9.0), 1)

        energy = random.choice([2, 3, 3, 4, 4]) if is_yellow else random.choice([3, 3, 4, 4, 5])

        flag_level = "yellow" if arm_feel <= 2 or sleep_hours < 6 else "green"

        entry = {
            "date": date_str,
            "rotation_day": rotation_day % 7,
            "days_since_outing": days_since_outing,
            "pre_training": {
                "arm_feel": arm_feel,
                "overall_energy": energy,
                "sleep_hours": sleep_hours,
                "flag_level": flag_level,
            },
        }

        # Add outing data
        if is_outing:
            pitch_count = OUTING_DAYS[day_offset]
            entry["outing"] = {
                "pitch_count": pitch_count,
                "post_arm_feel": random.choice([3, 4]),
                "notes": f"{'Good outing' if pitch_count < 90 else 'Deep into game, felt fatigue late'}",
            }
            days_since_outing = 0
        else:
            days_since_outing += 1

        # Add plan_generated to ~60% of entries
        if random.random() < 0.6:
            template_day = f"day_{rotation_day % 7}"
            entry["plan_generated"] = {
                "template_used": "starter_7day_v1",
                "template_day": template_day,
                "exercises_prescribed": [
                    {"exercise_id": "ex_001", "prescribed": "3x5 @ 275"},
                    {"exercise_id": "ex_rdl", "prescribed": "3x8 @ 185"},
                ],
            }

        # Add bot_observations to ~40% of entries
        if random.random() < 0.4:
            obs = []
            if arm_feel <= 3:
                obs.append("Arm feel below baseline — monitoring")
            if sleep_hours < 7:
                obs.append(f"Sleep at {sleep_hours}h, below target")
            if not obs:
                obs.append("Training on track, no concerns")
            entry["bot_observations"] = {
                "progression_notes": obs[0],
                "concern_flags": ["arm_feel_low"] if arm_feel <= 2 else [],
                "pattern_notes": obs[-1],
            }

        entries.append(entry)
        rotation_day += 1

    return entries


def main():
    entries = generate_entries()
    log = {"pitcher_id": "test_pitcher_001", "entries": entries}

    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "w") as f:
        json.dump(log, f, indent=2)

    # Summary stats
    feels = [e["pre_training"]["arm_feel"] for e in entries]
    sleeps = [e["pre_training"]["sleep_hours"] for e in entries]
    outings = [e for e in entries if "outing" in e]
    yellows = [e for e in entries if e["pre_training"]["flag_level"] == "yellow"]

    print(f"Generated {len(entries)} entries → {LOG_PATH}")
    print(f"  Arm feel range: {min(feels)}-{max(feels)} (avg {sum(feels)/len(feels):.1f})")
    print(f"  Sleep range: {min(sleeps)}-{max(sleeps)}h")
    print(f"  Outings: {len(outings)} ({', '.join(str(e['outing']['pitch_count']) for e in outings)} pitches)")
    print(f"  Yellow flag days: {len(yellows)}")


if __name__ == "__main__":
    main()
