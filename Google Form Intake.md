# Google Form: UChicago Pitcher Onboarding
## Purpose: Capture enough to generate a smart Day 1 program. Bot learns the rest through interaction.

---

## How to build this

Create a Google Form with the sections below. Use "Go to section based on answer" 
for the injury history branching. Keep it under 5 minutes to complete — pitchers 
won't finish a long form.

Title: "UChicago Pitching — Get Your Program"
Description: "Fill this out once. Takes 3-4 minutes. This builds your personalized 
daily training plan — arm care, lifting, throwing, recovery, all of it."

---

## Section 1: The basics (4 questions)

**1. Full name** (short text, required)

**2. Telegram username** (short text, required)
Helper text: "Your @username on Telegram — this is how the bot finds you"

**3. Year** (dropdown, required)
- Freshman
- Sophomore  
- Junior
- Senior
- 5th year

**4. Throws** (dropdown, required)
- Right
- Left

---

## Section 2: Your pitching role (4 questions)

**5. What's your role?** (dropdown, required)
- Starting pitcher
- Relief pitcher
- Both (starter and reliever)

**6. If you start: how many days between starts?** (dropdown)
- 5 days
- 6 days
- 7 days
- Varies / not sure
(Show only if answer to #5 is "Starting pitcher" or "Both")

**7. How many pitches do you typically throw in an outing?** (short text, number)
Helper text: "Best guess is fine. For starters: per start. For relievers: per appearance."

**8. What pitches do you throw?** (checkboxes)
- 4-seam fastball
- 2-seam / sinker
- Slider
- Curveball
- Changeup
- Cutter
- Other: ___

---

## Section 3: Your body — injuries and limitations (this is the most important section)

**9. Do you have any current or past arm/shoulder injuries?** (dropdown, required)
- Yes
- No
→ If No, skip to Section 4

**10. Select everything that applies** (checkboxes)
- UCL / medial elbow tightness or pain
- Tommy John surgery
- Shoulder impingement or pain
- Labrum tear or surgery
- Lat strain
- Low back issues
- Biceps tendon issue
- Forearm tightness (recurring)
- Other: ___

**11. For your most significant injury: what happened and where are you now?** (long text)
Helper text: "Brief description — what it was, when, how it was treated, and how 
it feels now. Example: 'UCL area tightness spring 2024, dry needling + pronator 
work, fully resolved but I monitor forearm tightness.'"

**12. Any areas you're currently managing or keeping an eye on?** (long text, optional)
Helper text: "Anything that's not injured but you're aware of. Example: 'Shoulder 
gets tight after long outings' or 'forearm fatigue by the 5th inning.'"

---

## Section 4: How strong are you right now? (5 questions)

Helper text for section: "These help the bot prescribe actual weights, not just 
percentages. Best estimates are fine — we're not testing you."

**13. Lifting experience** (dropdown, required)
- Beginner (less than 1 year consistent lifting)
- Intermediate (1-3 years)
- Advanced (3+ years, comfortable with all compound movements)

**14. Trap bar or hex bar deadlift — best working set** (short text, optional)
Helper text: "Weight x reps. Example: '315 x 5' or '275 x 3'. Leave blank if unsure."

**15. Front squat or goblet squat — best working set** (short text, optional)
Helper text: "Example: '225 x 5' or 'goblet 70 x 10'"

**16. DB bench press — best working set** (short text, optional)
Helper text: "Example: '80s x 8'"

**17. Pull-up / chin-up** (short text, optional)
Helper text: "Example: 'BW + 45 x 5' or '8 bodyweight reps' or 'can't do pull-ups yet'"

---

## Section 5: Your schedule and availability (3 questions)

**18. How many days per week can you realistically get in the gym?** (dropdown, required)
- 2 days
- 3 days
- 4 days
- 5+ days

**19. When do you usually lift?** (dropdown)
- Before practice
- After practice
- Mornings before class
- Evenings
- Varies

**20. Any time constraints?** (short text, optional)
Helper text: "Example: 'Can only lift 45 min on Tuesdays' or 'No gym access on Sundays'"

---

## Section 6: Goals and preferences (3 questions)

**21. What's the #1 thing you want from this system?** (long text, required)
Helper text: "Be honest. Examples: 'Stay healthy all season' / 'Add velocity' / 
'Actually have a plan instead of winging it' / 'Understand my arm better'"

**22. How do you want information delivered?** (dropdown)
- Just tell me what to do — keep it brief
- Explain the reasoning behind everything  
- Somewhere in between

**23. Best time for your daily check-in notification** (dropdown)
- 7:00 AM
- 8:00 AM
- 9:00 AM
- 10:00 AM
- I'll check in on my own (no notification)

---

## Section 7: Optional — helps the bot be smarter from Day 1

**24. Average sleep per night** (dropdown, optional)
- Less than 6 hours
- 6-7 hours
- 7-8 hours
- 8+ hours

**25. Any mechanical focus areas you're working on?** (long text, optional)
Helper text: "Example: 'Hip-shoulder separation' / 'Staying closed longer' / 
'Leading with my hip.' Leave blank if none."

**26. Anything else the bot should know about you?** (long text, optional)
Helper text: "Allergies, preferences, past programs you liked, things you've 
tried that didn't work, etc."

---

## TOTAL: 26 questions, ~4 minutes to complete
## Required: 10 questions. Optional: 16 questions.

---

## How the form maps to pitcher profile.json

| Form field | Profile field |
|------------|--------------|
| Full name | name |
| Telegram username | telegram_username |
| Year | year |
| Throws | throws |
| Role | role |
| Rotation length | rotation_length |
| Typical pitch count | pitching_profile.typical_pitch_count |
| Pitch arsenal | pitching_profile.pitch_arsenal |
| Injury history checkboxes | injury_history[] |
| Injury description | injury_history[].description |
| Currently monitoring | injury_history[].ongoing_considerations |
| Lifting experience | current_training.lifting_experience |
| Trap bar DL | current_training.current_maxes.trap_bar_dl |
| Front squat | current_training.current_maxes.front_squat |
| DB bench | current_training.current_maxes.db_bench |
| Pull-up | current_training.current_maxes.pullup |
| Gym days per week | current_training.lifting_frequency |
| Usual lift time | preferences.lift_timing |
| Time constraints | preferences.time_constraints |
| Primary goal | goals.primary |
| Info delivery preference | preferences.detail_level |
| Notification time | preferences.notification_time |
| Average sleep | biometric_integration.avg_sleep_hours |
| Mechanical focus | pitching_profile.mechanical_focus_areas |
| Additional notes | context.md initial entry |

### Auto-generated fields (not from form)
- pitcher_id: generated from name (lowercase, underscore)
- telegram_id: backfilled on first bot interaction
- active_flags: initialized with defaults (green, no outing logged)
- active_modifications: auto-set based on injury history 
  (UCL history → elevated_fpm_volume, shoulder → reduced_pressing, etc.)

### What the bot does with this on Day 1
1. Reads the profile
2. Identifies their role + rotation position (asks "when do you next pitch?")
3. Generates a complete daily plan based on:
   - Rotation day position
   - Their lifting maxes (real weights if provided, RPE if not)
   - Their injury modifications (elevated FPM if UCL history, etc.)
   - Their available time and gym days
   - Their goal bias (velocity → more power work, durability → more eccentric/FPM)
4. Delivers it through the in-app chat + DailyCard

The form is the seed. The bot grows from there through every interaction.
