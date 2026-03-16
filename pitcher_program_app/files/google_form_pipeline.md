# Google Form → Codebase Pipeline

## Overview
Google Form captures pitcher intake data → Google Sheets stores responses → 
Script reads sheet and generates pitcher files → Bot picks up new pitcher on next startup/refresh.

## Option A: Manual Script (MVP — recommended)
1. Create Google Form with fields below
2. Form responses auto-populate a Google Sheet
3. Run `scripts/intake_to_profile.py` manually when new pitchers sign up
4. Script reads the Google Sheet (via gspread or CSV export) and generates files

This is the right choice for MVP because:
- You're onboarding pitchers in batches (not real-time sign-ups)
- No webhook infrastructure needed
- You can review form responses before generating profiles
- Dead simple to debug

## Option B: Automated Webhook (Post-MVP)
- Google Form → Google Apps Script → webhook to bot server
- Bot auto-generates profile and sends welcome message
- More complex, only needed if you're scaling beyond your team

## Google Form Fields

### Required Fields
- Full name (text)
- Telegram username (text) — CRITICAL for linking
- Throws (dropdown: Right / Left)
- Role (dropdown: Starter / Reliever / Both)
- Rotation length if starter (dropdown: 5-day / 6-day / 7-day)
- Year (dropdown: Freshman / Sophomore / Junior / Senior)

### Injury History (checkboxes — select all that apply)
- No significant injury history
- UCL / medial elbow tightness or injury
- Shoulder impingement
- Lat strain
- Low back issues
- Tommy John surgery (with year field)
- Other (free text)

### For each checked injury:
- Brief description (free text)
- Current status (dropdown: Fully resolved / Ongoing management / Recently cleared)

### Training Background
- Lifting experience (dropdown: Beginner / Intermediate / Advanced)
- Current lifting frequency (dropdown: 1x / 2x / 3x / 4x+ per week)

### Optional but Valuable
- Height (inches)
- Weight (lbs)
- Average fastball velocity (mph)
- Known mobility limitations (free text)
- Mechanical focus areas (free text)
- Goals - primary (free text)
- Goals - secondary (free text)
- Preferred notification time (dropdown: 7am / 8am / 9am / 10am)

## Script: intake_to_profile.py

```python
"""
Reads Google Form responses (from CSV export or gspread)
and generates pitcher profile JSON, context MD, and empty log JSON.

Usage:
  python scripts/intake_to_profile.py --csv responses.csv
  OR
  python scripts/intake_to_profile.py --sheet "Pitcher Intake Responses"
"""

import json
import csv
import os
from datetime import datetime

def generate_pitcher_id(name: str) -> str:
    """Generate a URL-safe pitcher ID from name."""
    return name.lower().replace(" ", "_").replace(".", "")

def form_row_to_profile(row: dict) -> dict:
    """Convert a single form response row to a pitcher profile dict."""
    pitcher_id = generate_pitcher_id(row["Full name"])
    
    # Parse injury history from checkbox responses
    injuries = []
    if "UCL" in row.get("Injury History", ""):
        injuries.append({
            "area": "medial_elbow",
            "description": row.get("UCL Description", ""),
            "status": row.get("UCL Status", "resolved"),
            "ongoing_considerations": "Elevated FPM work frequency"
        })
    # ... similar parsing for other injury types
    
    profile = {
        "pitcher_id": pitcher_id,
        "name": row["Full name"],
        "telegram_username": row["Telegram username"].strip("@"),
        "role": row["Role"].lower(),
        "rotation_length": int(row.get("Rotation length", "7").split("-")[0]),
        "throws": row["Throws"].lower()[0],  # "r" or "l"
        "physical_profile": {
            "height_in": int(row.get("Height", 0)) or None,
            "weight_lbs": int(row.get("Weight", 0)) or None,
            "known_mobility_limitations": row.get("Mobility limitations", "").split(","),
        },
        "injury_history": injuries,
        "current_training": {
            "lifting_experience": row.get("Lifting experience", "intermediate").lower(),
            "lifting_frequency": row.get("Lifting frequency", "3x"),
        },
        "pitching_profile": {
            "avg_velocity_fb": int(row.get("Fastball velocity", 0)) or None,
            "mechanical_focus_areas": row.get("Mechanical focus areas", "").split(","),
        },
        "goals": {
            "primary": row.get("Primary goal", ""),
            "secondary": row.get("Secondary goal", ""),
        },
        "preferences": {
            "notification_time": row.get("Notification time", "08:00"),
            "wants_youtube_links": True,
        },
        "active_flags": {
            "current_arm_feel": 4,
            "current_flag_level": "green",
            "last_outing_date": None,
            "last_outing_pitches": None,
            "days_since_outing": None,
            "active_modifications": []
        },
        "created_at": datetime.now().isoformat()
    }
    
    # Auto-set modifications based on injury history
    for injury in injuries:
        if injury["area"] == "medial_elbow":
            profile["active_flags"]["active_modifications"].append("elevated_fpm_volume")
        elif injury["area"] == "shoulder":
            profile["active_flags"]["active_modifications"].append("reduced_pressing")
    
    return profile

def generate_context_md(profile: dict) -> str:
    """Generate the initial context.md file for a pitcher."""
    injuries_text = "None reported"
    if profile["injury_history"]:
        injuries_text = "\n".join([
            f"- {i['area']}: {i['description']} (Status: {i['status']})"
            for i in profile["injury_history"]
        ])
    
    return f"""# Pitcher context: {profile['name']}
## Last updated: {datetime.now().strftime('%Y-%m-%d')}

### Profile summary
- Role: {profile['role']}, {profile['rotation_length']}-day rotation
- Throws: {'Right' if profile['throws'] == 'r' else 'Left'}
- Experience: {profile['current_training']['lifting_experience']}
- Velocity: {profile['pitching_profile']['avg_velocity_fb'] or 'Not reported'} mph

### Injury history
{injuries_text}

### Goals
- Primary: {profile['goals']['primary'] or 'Not specified'}
- Secondary: {profile['goals']['secondary'] or 'Not specified'}

### Active modifications
{chr(10).join(['- ' + m for m in profile['active_flags']['active_modifications']]) or '- None'}

### Longitudinal patterns
(Will populate as data accumulates)

### Interaction memory
(Will populate as pitcher interacts with bot)
"""

def process_intake(csv_path: str, output_dir: str = "data/pitchers"):
    """Process all form responses and generate pitcher files."""
    os.makedirs(output_dir, exist_ok=True)
    
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            profile = form_row_to_profile(row)
            pitcher_id = profile["pitcher_id"]
            
            # Write profile JSON
            with open(f"{output_dir}/{pitcher_id}.json", 'w') as pf:
                json.dump(profile, pf, indent=2)
            
            # Write context MD
            with open(f"{output_dir}/{pitcher_id}_context.md", 'w') as cf:
                cf.write(generate_context_md(profile))
            
            # Write empty log
            with open(f"{output_dir}/{pitcher_id}_log.json", 'w') as lf:
                json.dump({"pitcher_id": pitcher_id, "entries": []}, lf, indent=2)
            
            print(f"Created profile for {profile['name']} ({pitcher_id})")

    # Generate telegram_username → pitcher_id mapping
    # Bot uses this to identify who's messaging
    mapping = {}
    for f in os.listdir(output_dir):
        if f.endswith('.json') and not f.endswith('_log.json'):
            with open(f"{output_dir}/{f}") as pf:
                p = json.load(pf)
                if "telegram_username" in p:
                    mapping[p["telegram_username"]] = p["pitcher_id"]
    
    with open(f"{output_dir}/_telegram_mapping.json", 'w') as mf:
        json.dump(mapping, mf, indent=2)
    print(f"Telegram mapping saved ({len(mapping)} pitchers)")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True, help="Path to CSV export of Google Form responses")
    args = parser.parse_args()
    process_intake(args.csv)
```

## Telegram Username Mapping

The critical link between Google Form and bot is the Telegram username.

When a pitcher messages the bot for the first time:
1. Bot gets their Telegram user ID and username from the message
2. Looks up username in `_telegram_mapping.json`
3. If found → loads their profile, sends welcome confirmation
4. If not found → "I don't have you in the system yet. Ask [Lando] to get you set up."

Store both telegram_username AND telegram_user_id in the profile after first contact,
since user_id is more reliable (usernames can change).

## File Output Structure
```
data/pitchers/
  _telegram_mapping.json      ← username → pitcher_id lookup
  lando_b.json                ← profile
  lando_b_context.md          ← growing context
  lando_b_log.json            ← daily log entries
  pitcher_two.json
  pitcher_two_context.md
  pitcher_two_log.json
  ...
```
