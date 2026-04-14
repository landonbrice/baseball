# Exercise Enrichment + Mobility Video Integration

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enrich the exercise library with new exercises + YouTube links from spreadsheet data, add med ball exercises to the explosive/plyometric pool, and build a 10-week cycling mobility video system displayed on the daily plan page.

**Architecture:** Three workstreams: (1) A Python script to backfill YouTube URLs on existing exercises and create new exercise entries (ex_121+) in both JSON and Supabase, (2) A new `mobility_videos` Supabase table + JSON data file with a 10-week rotation of follow-along YouTube videos served via API, (3) A MobilityCard component in the mini-app's DailyCard that shows today's mobility video after all other blocks.

**Tech Stack:** Python 3.11, Supabase (Postgres), React 18, FastAPI, openpyxl

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `scripts/enrich_exercises.py` | Create | Parses xlsx, fuzzy-matches, backfills YouTube URLs, creates new exercise JSON entries |
| `data/knowledge/exercise_library.json` | Modify | Add ~30 new exercises (ex_121+), update youtube_url on ~15 existing exercises |
| `data/knowledge/mobility_videos.json` | Create | 10-week rotation of mobility videos (21 unique videos, 4 per week) |
| `scripts/seed_mobility_videos.py` | Create | Seeds mobility_videos table in Supabase from JSON |
| `bot/services/mobility.py` | Create | `get_today_mobility(pitcher_id)` — returns today's mobility videos based on 10-week cycle |
| `bot/services/plan_generator.py` | Modify:~230-240 | Add `mobility` key to plan output |
| `api/routes.py` | Modify | Add `GET /api/pitcher/{id}/mobility-today` endpoint |
| `mini-app/src/components/MobilityCard.jsx` | Create | Renders today's mobility videos with YouTube thumbnails/links |
| `mini-app/src/components/DailyCard.jsx` | Modify:~64,117 | Add mobility to blockData + render MobilityCard after BLOCKS loop (NOT in BLOCKS array — mobility is video links, not exercises) |

---

### Task 1: Curate Exercise Matches and Build Enrichment Data

This task produces the enrichment script that parses the xlsx files, matches against the existing library, and outputs two artifacts: (a) YouTube URL updates for existing exercises, and (b) new exercise entries.

**Files:**
- Create: `scripts/enrich_exercises.py`

**Critical context:**
- Exercise IDs use `ex_###` format (ex_001 through ex_120 exist). New = ex_121+.
- The fuzzy matcher has known false positives. These must be handled with a curated manual map.
- Arms exercises go into `upper_body_push` or `upper_body_pull` (no separate "arms" category).
- Med ball exercises go into `plyometric_power` category.
- All new exercises need: id, name, category, muscles_primary, prescription (at minimum strength + hypertrophy), rotation_day_usage, tags, contraindications, modification_flags, youtube_url.

- [ ] **Step 1: Create the enrichment script with curated match map**

```python
# scripts/enrich_exercises.py
"""Parse uchi_exercise_library.xlsx, match against exercise library,
backfill YouTube URLs, and generate new exercise entries.

Usage:
    cd pitcher_program_app
    python -m scripts.enrich_exercises --dry-run   # preview changes
    python -m scripts.enrich_exercises              # apply to JSON + Supabase
"""

import json
import argparse
import logging
from pathlib import Path

try:
    import openpyxl
except ImportError:
    print("Install openpyxl: pip install openpyxl")
    exit(1)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
EXERCISE_LIBRARY = DATA_DIR / "knowledge" / "exercise_library.json"
XLSX_PATH = Path(__file__).resolve().parent.parent / "past_arm_programs" / "uchi_exercise_library.xlsx"

# ── Curated match map: xlsx exercise name -> existing library ID ──
# These override fuzzy matching to prevent false positives.
CURATED_MATCHES = {
    # Major Lifts - true matches
    "Front Squat": "ex_002",
    "Trap Bar Deadlift": "ex_001",
    "Barbell Hip Thrust": "ex_003",
    "Bulgarian Split Squat": "ex_004",
    "Chin Ups": "ex_019",
    # Accessories - true matches
    "Landmine Lateral Lunge": "ex_009",
    "Heel Elevated Goblet Squat": "ex_007",
    "Partner Nordic Curl": "ex_013",
    "Single Leg Dumbell RDL": "ex_006",
    "Landmine RDL": "ex_011",
    "Kneeling Landmine Press": "ex_026",
    # Med Ball - true matches
    "Rotational Scoop Throw": "ex_015",  # Med Ball Scoop Toss
}

# Exercises to SKIP (muscle target labels parsed as exercises, duplicates, etc.)
SKIP_NAMES = {
    "glute / hip flexer",  # muscle label for copenhagen plank
    "everything",          # muscle label for farmers carry
    "chest / arms",        # muscle label for plyo pushups
    "Back / shoulders",    # muscle label for weighted I/T/Ys
}

# ── New exercise definitions ──
# Each gets assigned ex_121+ in order
NEW_EXERCISES = [
    # --- Major Lifts ---
    {
        "name": "Back Squat",
        "category": "lower_body_compound",
        "subcategory": "quad_dominant",
        "muscles_primary": ["quads", "glutes", "erector spinae"],
        "muscles_secondary": ["hamstrings", "core"],
        "pitching_relevance": "Foundation lower body compound. Builds leg drive for push-off. Barbell loading allows progressive overload beyond goblet/trap bar variants.",
        "prescription": {
            "strength": {"sets": "3-4", "reps": "3-5", "intensity": "85% 1RM", "rest_min": 3},
            "hypertrophy": {"sets": "3-4", "reps": "8-12", "intensity": "65-75% 1RM", "rest_min": 2},
            "power": {"sets": "4", "reps": "2-3", "intensity": "50-60% 1RM", "rest_min": 3, "note": "Explosive concentric"},
        },
        "rotation_day_usage": {"recommended": ["day_2", "day_3"], "acceptable": ["day_4"], "avoid": ["day_0", "day_5", "day_6"]},
        "tags": ["compound", "lower_body", "strength", "force_production"],
        "contraindications": ["acute_low_back", "lumbar_disk_issues"],
        "modification_flags": {"ucl_history": "no_modification_needed", "shoulder_impingement": "use_safety_squat_bar_or_front_squat", "low_back_history": "substitute_belt_squat_or_front_squat"},
        "youtube_url": "",
        "evidence_level": "strong",
        "source_notes": "UChicago exercise library"
    },
    {
        "name": "Trap Bar Squat Jump",
        "category": "plyometric_power",
        "subcategory": "loaded_jump",
        "muscles_primary": ["quads", "glutes", "calves"],
        "muscles_secondary": ["hamstrings", "core"],
        "pitching_relevance": "Loaded explosive triple extension. Develops rate of force development directly applicable to push-off and leg drive.",
        "prescription": {
            "power": {"sets": "3-4", "reps": "3-5", "intensity": "30-40% 1RM trap bar DL", "rest_min": 3, "note": "Max jump height intent, soft landing"},
            "strength": {"sets": "3", "reps": "5", "intensity": "30% 1RM", "rest_min": 2},
        },
        "rotation_day_usage": {"recommended": ["day_2", "day_3"], "acceptable": ["day_4"], "avoid": ["day_0", "day_1", "day_5", "day_6"]},
        "tags": ["plyometric", "power", "explosive", "lower_body", "velocity_development"],
        "contraindications": ["acute_low_back", "knee_instability"],
        "modification_flags": {"ucl_history": "no_modification_needed", "low_back_history": "reduce_load_or_substitute_bodyweight_jump", "knee_history": "substitute_med_ball_slam"},
        "youtube_url": "https://youtu.be/-n2p5mQxYTw?si=YougfQuYz5Ra4tac",
        "evidence_level": "strong",
        "source_notes": "UChicago exercise library"
    },
    # --- Accessory Lifts (Lower) ---
    {
        "name": "Dumbbell Walking Lunge",
        "category": "lower_body_compound",
        "subcategory": "quad_dominant",
        "muscles_primary": ["quads", "glutes"],
        "muscles_secondary": ["hamstrings", "core"],
        "pitching_relevance": "Unilateral leg strength with dynamic stability. Mimics stride mechanics — single-leg loading with forward translation.",
        "prescription": {
            "strength": {"sets": "3", "reps": "8 each leg", "intensity": "moderate DBs", "rest_min": 2},
            "hypertrophy": {"sets": "3", "reps": "12 each leg", "intensity": "light-moderate DBs", "rest_min": 1.5},
        },
        "rotation_day_usage": {"recommended": ["day_2", "day_3", "day_4"], "acceptable": ["day_1"], "avoid": ["day_0", "day_5", "day_6"]},
        "tags": ["unilateral", "lower_body", "dynamic_stability"],
        "contraindications": ["acute_knee"],
        "modification_flags": {"ucl_history": "no_modification_needed", "knee_history": "shorter_stride_or_reverse_lunge"},
        "youtube_url": "",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library"
    },
    {
        "name": "Heel Elevated Plate Squat",
        "category": "lower_body_compound",
        "subcategory": "quad_dominant",
        "muscles_primary": ["quads", "glutes"],
        "muscles_secondary": ["core"],
        "pitching_relevance": "Quad-focused squat variation. Heel elevation shifts load anteriorly — good for pitchers with limited ankle dorsiflexion.",
        "prescription": {
            "strength": {"sets": "3", "reps": "6-8", "intensity": "moderate", "rest_min": 2},
            "hypertrophy": {"sets": "3", "reps": "10-15", "intensity": "light-moderate", "rest_min": 1.5},
        },
        "rotation_day_usage": {"recommended": ["day_2", "day_3"], "acceptable": ["day_4"], "avoid": ["day_0", "day_5", "day_6"]},
        "tags": ["quad_focused", "lower_body", "ankle_mobility_friendly"],
        "contraindications": ["acute_knee"],
        "modification_flags": {"ucl_history": "no_modification_needed", "knee_history": "reduce_depth"},
        "youtube_url": "https://youtu.be/fv1LX_brEmM?si=Carg1iLZpP5kFjJU",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library"
    },
    {
        "name": "Quad Extension Machine",
        "category": "lower_body_compound",
        "subcategory": "quad_isolation",
        "muscles_primary": ["quads"],
        "muscles_secondary": [],
        "pitching_relevance": "Isolated quad strengthening. Useful for targeted hypertrophy without spinal loading.",
        "prescription": {
            "hypertrophy": {"sets": "3", "reps": "10-15", "intensity": "moderate", "rest_min": 1.5},
            "endurance": {"sets": "3", "reps": "15-20", "intensity": "light", "rest_min": 1},
        },
        "rotation_day_usage": {"recommended": ["day_2", "day_3", "day_4"], "acceptable": ["day_1"], "avoid": ["day_0", "day_5", "day_6"]},
        "tags": ["isolation", "quad", "machine"],
        "contraindications": ["acute_knee", "patellar_tendinopathy"],
        "modification_flags": {"knee_history": "limit_ROM_or_skip"},
        "youtube_url": "",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library"
    },
    {
        "name": "Hamstring Curl Machine",
        "category": "lower_body_compound",
        "subcategory": "hamstring_isolation",
        "muscles_primary": ["hamstrings"],
        "muscles_secondary": [],
        "pitching_relevance": "Isolated hamstring strengthening. Decelerator muscle group — critical for braking/decel phase of delivery.",
        "prescription": {
            "hypertrophy": {"sets": "3", "reps": "10-12", "intensity": "moderate", "rest_min": 1.5},
            "endurance": {"sets": "3", "reps": "15-20", "intensity": "light", "rest_min": 1},
        },
        "rotation_day_usage": {"recommended": ["day_2", "day_3", "day_4"], "acceptable": ["day_1"], "avoid": ["day_0", "day_5", "day_6"]},
        "tags": ["isolation", "hamstring", "machine", "deceleration"],
        "contraindications": ["acute_hamstring_strain"],
        "modification_flags": {"ucl_history": "no_modification_needed"},
        "youtube_url": "",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library"
    },
    {
        "name": "Glute Ham Raise",
        "category": "lower_body_compound",
        "subcategory": "hip_dominant",
        "muscles_primary": ["hamstrings", "glutes"],
        "muscles_secondary": ["erector spinae"],
        "pitching_relevance": "Eccentric hamstring strength — key for deceleration phase. Superior to curl machine for functional hamstring development.",
        "prescription": {
            "strength": {"sets": "3", "reps": "6-8", "intensity": "bodyweight or light band assist", "rest_min": 2},
            "hypertrophy": {"sets": "3", "reps": "8-12", "intensity": "bodyweight", "rest_min": 1.5},
        },
        "rotation_day_usage": {"recommended": ["day_2", "day_3"], "acceptable": ["day_4"], "avoid": ["day_0", "day_5", "day_6"]},
        "tags": ["eccentric", "hamstring", "posterior_chain", "deceleration"],
        "contraindications": ["acute_hamstring_strain", "acute_low_back"],
        "modification_flags": {"low_back_history": "use_band_assist"},
        "youtube_url": "https://youtube.com/shorts/rjH934b6pVw?si=lMnmBtdS_9WhaxjJ",
        "evidence_level": "strong",
        "source_notes": "UChicago exercise library. Nordic curl alternative."
    },
    {
        "name": "Dumbbell Deadlift",
        "category": "lower_body_compound",
        "subcategory": "hip_dominant",
        "muscles_primary": ["hamstrings", "glutes", "erector spinae"],
        "muscles_secondary": ["quads", "grip"],
        "pitching_relevance": "Hip hinge pattern with lighter load option than barbell. Good regression for pitchers not ready for heavy barbell pulls.",
        "prescription": {
            "strength": {"sets": "3", "reps": "6-8", "intensity": "moderate-heavy DBs", "rest_min": 2},
            "hypertrophy": {"sets": "3", "reps": "10-12", "intensity": "moderate DBs", "rest_min": 1.5},
        },
        "rotation_day_usage": {"recommended": ["day_2", "day_3"], "acceptable": ["day_4"], "avoid": ["day_0", "day_5", "day_6"]},
        "tags": ["hip_hinge", "lower_body", "dumbbell"],
        "contraindications": ["acute_low_back"],
        "modification_flags": {"low_back_history": "elevate_DBs_or_substitute_trap_bar"},
        "youtube_url": "https://youtu.be/plb5jEO4Unw?si=rl5D8rEEn_wstJMr",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library"
    },
    {
        "name": "Swiss Ball Hamstring Curl",
        "category": "lower_body_compound",
        "subcategory": "hamstring_isolation",
        "muscles_primary": ["hamstrings"],
        "muscles_secondary": ["glutes", "core"],
        "pitching_relevance": "Hamstring curl with instability challenge. Engages core/hip stabilizers while strengthening decelerator muscles.",
        "prescription": {
            "hypertrophy": {"sets": "3", "reps": "10-12", "intensity": "bodyweight", "rest_min": 1.5},
            "endurance": {"sets": "3", "reps": "15", "intensity": "bodyweight", "rest_min": 1},
        },
        "rotation_day_usage": {"recommended": ["day_2", "day_3", "day_4"], "acceptable": ["day_1"], "avoid": ["day_0", "day_5", "day_6"]},
        "tags": ["hamstring", "stability", "bodyweight"],
        "contraindications": ["acute_hamstring_strain"],
        "modification_flags": {"ucl_history": "no_modification_needed"},
        "youtube_url": "https://youtube.com/shorts/xB1lGVzRwWk?si=HdN_lD20vlePOLuG",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library"
    },
    {
        "name": "Copenhagen Plank",
        "category": "core",
        "subcategory": "adductor_stability",
        "muscles_primary": ["adductors", "obliques"],
        "muscles_secondary": ["hip flexors", "core"],
        "pitching_relevance": "Adductor and hip flexor strengthening in frontal plane. Critical for lead leg stability during delivery and preventing groin strains.",
        "prescription": {
            "strength": {"sets": "3", "reps": "20-30 sec each side", "intensity": "bodyweight", "rest_min": 1},
            "endurance": {"sets": "3", "reps": "30-45 sec each side", "intensity": "bodyweight", "rest_min": 1},
        },
        "rotation_day_usage": {"recommended": ["day_2", "day_3", "day_4"], "acceptable": ["day_1"], "avoid": ["day_0"]},
        "tags": ["core", "adductor", "frontal_plane", "stability"],
        "contraindications": ["acute_groin_strain"],
        "modification_flags": {"ucl_history": "no_modification_needed"},
        "youtube_url": "https://youtube.com/shorts/Rwap0_j5i5A?si=r9ty_AF95aeheQms",
        "evidence_level": "strong",
        "source_notes": "UChicago exercise library. Evidence-based groin injury prevention."
    },
    # --- Accessory Lifts (Upper) ---
    {
        "name": "Barbell Bench Press",
        "category": "upper_body_push",
        "subcategory": "horizontal_press",
        "muscles_primary": ["pecs", "triceps", "anterior deltoid"],
        "muscles_secondary": ["serratus anterior"],
        "pitching_relevance": "Primary horizontal push. Builds anterior chain strength. Use cautiously in-season — heavy flat bench can increase anterior shoulder stress.",
        "prescription": {
            "strength": {"sets": "3-4", "reps": "3-5", "intensity": "85% 1RM", "rest_min": 3},
            "hypertrophy": {"sets": "3", "reps": "8-12", "intensity": "65-75% 1RM", "rest_min": 2},
        },
        "rotation_day_usage": {"recommended": ["day_3", "day_4"], "acceptable": ["day_2"], "avoid": ["day_0", "day_1", "day_5", "day_6"]},
        "tags": ["compound", "upper_body", "push", "horizontal_press"],
        "contraindications": ["acute_shoulder", "labrum_surgery_recent"],
        "modification_flags": {"shoulder_impingement": "substitute_floor_press_or_neutral_grip", "ucl_history": "no_modification_needed"},
        "youtube_url": "",
        "evidence_level": "strong",
        "source_notes": "UChicago exercise library"
    },
    {
        "name": "Incline Barbell Press",
        "category": "upper_body_push",
        "subcategory": "incline_press",
        "muscles_primary": ["pecs", "triceps", "anterior deltoid"],
        "muscles_secondary": ["serratus anterior"],
        "pitching_relevance": "Upper pec and anterior delt development. Incline angle reduces shoulder impingement risk vs. flat bench.",
        "prescription": {
            "strength": {"sets": "3", "reps": "5-6", "intensity": "80% 1RM", "rest_min": 2.5},
            "hypertrophy": {"sets": "3", "reps": "8-12", "intensity": "65-75% 1RM", "rest_min": 2},
        },
        "rotation_day_usage": {"recommended": ["day_3", "day_4"], "acceptable": ["day_2"], "avoid": ["day_0", "day_1", "day_5", "day_6"]},
        "tags": ["compound", "upper_body", "push", "incline"],
        "contraindications": ["acute_shoulder"],
        "modification_flags": {"shoulder_impingement": "reduce_incline_angle_or_use_DB"},
        "youtube_url": "",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library"
    },
    {
        "name": "Dumbbell Incline Press",
        "category": "upper_body_push",
        "subcategory": "incline_press",
        "muscles_primary": ["pecs", "triceps", "anterior deltoid"],
        "muscles_secondary": ["serratus anterior", "rotator cuff"],
        "pitching_relevance": "Dumbbell variant allows more natural shoulder path. Better for pitchers with shoulder restrictions.",
        "prescription": {
            "strength": {"sets": "3", "reps": "6-8", "intensity": "moderate-heavy DBs", "rest_min": 2},
            "hypertrophy": {"sets": "3", "reps": "10-12", "intensity": "moderate DBs", "rest_min": 1.5},
        },
        "rotation_day_usage": {"recommended": ["day_3", "day_4"], "acceptable": ["day_2"], "avoid": ["day_0", "day_1", "day_5", "day_6"]},
        "tags": ["compound", "upper_body", "push", "dumbbell"],
        "contraindications": ["acute_shoulder"],
        "modification_flags": {"shoulder_impingement": "use_neutral_grip"},
        "youtube_url": "",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library"
    },
    {
        "name": "Dumbbell Floor Press",
        "category": "upper_body_push",
        "subcategory": "horizontal_press",
        "muscles_primary": ["pecs", "triceps"],
        "muscles_secondary": ["anterior deltoid"],
        "pitching_relevance": "Shoulder-friendly pressing. Floor limits ROM to protect anterior shoulder — ideal for pitchers with impingement or in-season caution.",
        "prescription": {
            "strength": {"sets": "3", "reps": "6-8", "intensity": "moderate-heavy DBs", "rest_min": 2},
            "hypertrophy": {"sets": "3", "reps": "10-12", "intensity": "moderate DBs", "rest_min": 1.5},
        },
        "rotation_day_usage": {"recommended": ["day_2", "day_3", "day_4"], "acceptable": ["day_1"], "avoid": ["day_0", "day_5", "day_6"]},
        "tags": ["push", "upper_body", "shoulder_safe", "floor_press"],
        "contraindications": [],
        "modification_flags": {"shoulder_impingement": "preferred_pressing_variant"},
        "youtube_url": "https://youtu.be/fc7sLXRrQaU?si=TsX3lMuWR9dHPWaN",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library"
    },
    {
        "name": "Lat Pull Down",
        "category": "upper_body_pull",
        "subcategory": "vertical_pull",
        "muscles_primary": ["lats", "biceps"],
        "muscles_secondary": ["rhomboids", "rear deltoid"],
        "pitching_relevance": "Vertical pulling for lat development. Lats are primary accelerator muscle — builds decel capacity and arm speed.",
        "prescription": {
            "strength": {"sets": "3", "reps": "6-8", "intensity": "heavy", "rest_min": 2},
            "hypertrophy": {"sets": "3", "reps": "10-12", "intensity": "moderate", "rest_min": 1.5},
        },
        "rotation_day_usage": {"recommended": ["day_2", "day_3", "day_4"], "acceptable": ["day_1"], "avoid": ["day_0", "day_5", "day_6"]},
        "tags": ["pull", "upper_body", "lat", "machine"],
        "contraindications": [],
        "modification_flags": {"shoulder_impingement": "use_neutral_grip_attachment"},
        "youtube_url": "https://youtube.com/shorts/8d6d46pGdQM?si=n2vyYEvIEo7MnxBz",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library"
    },
    {
        "name": "Barbell Row",
        "category": "upper_body_pull",
        "subcategory": "horizontal_pull",
        "muscles_primary": ["lats", "rhomboids", "rear deltoid"],
        "muscles_secondary": ["biceps", "erector spinae"],
        "pitching_relevance": "Horizontal pulling builds scapular retractors and posterior chain. Counterbalances anterior-dominant throwing mechanics.",
        "prescription": {
            "strength": {"sets": "3-4", "reps": "5-6", "intensity": "heavy", "rest_min": 2.5},
            "hypertrophy": {"sets": "3", "reps": "8-12", "intensity": "moderate", "rest_min": 2},
        },
        "rotation_day_usage": {"recommended": ["day_2", "day_3", "day_4"], "acceptable": ["day_1"], "avoid": ["day_0", "day_5", "day_6"]},
        "tags": ["compound", "pull", "upper_body", "posterior_chain"],
        "contraindications": ["acute_low_back"],
        "modification_flags": {"low_back_history": "substitute_chest_supported_row"},
        "youtube_url": "https://youtube.com/shorts/DgyslsszCQ0?si=__F7SkQRGW-Ny0U1",
        "evidence_level": "strong",
        "source_notes": "UChicago exercise library"
    },
    {
        "name": "Dumbbell Row",
        "category": "upper_body_pull",
        "subcategory": "horizontal_pull",
        "muscles_primary": ["lats", "rhomboids"],
        "muscles_secondary": ["biceps", "rear deltoid"],
        "pitching_relevance": "Unilateral pulling. Addresses side-to-side imbalances common in throwers.",
        "prescription": {
            "strength": {"sets": "3", "reps": "6-8 each arm", "intensity": "moderate-heavy", "rest_min": 1.5},
            "hypertrophy": {"sets": "3", "reps": "10-12 each arm", "intensity": "moderate", "rest_min": 1.5},
        },
        "rotation_day_usage": {"recommended": ["day_2", "day_3", "day_4"], "acceptable": ["day_1"], "avoid": ["day_0", "day_5", "day_6"]},
        "tags": ["unilateral", "pull", "upper_body", "dumbbell"],
        "contraindications": [],
        "modification_flags": {"ucl_history": "no_modification_needed"},
        "youtube_url": "https://youtu.be/DMo3HJoawrU?si=RLJAKZCiDZbtLl3d",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library"
    },
    {
        "name": "Pin Press",
        "category": "upper_body_push",
        "subcategory": "horizontal_press",
        "muscles_primary": ["pecs", "triceps"],
        "muscles_secondary": ["anterior deltoid"],
        "pitching_relevance": "Partial ROM press from pins. Builds lockout strength while limiting shoulder stress from deep stretch position.",
        "prescription": {
            "strength": {"sets": "3-4", "reps": "3-5", "intensity": "85-90% bench 1RM", "rest_min": 3},
            "hypertrophy": {"sets": "3", "reps": "6-8", "intensity": "75-80%", "rest_min": 2},
        },
        "rotation_day_usage": {"recommended": ["day_3", "day_4"], "acceptable": ["day_2"], "avoid": ["day_0", "day_1", "day_5", "day_6"]},
        "tags": ["push", "upper_body", "partial_rom", "shoulder_safe"],
        "contraindications": [],
        "modification_flags": {"shoulder_impingement": "set_pins_higher_to_reduce_ROM"},
        "youtube_url": "https://youtu.be/9ntAEA4fsxc?si=enDS8xDKindoG-uz",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library"
    },
    {
        "name": "Dips",
        "category": "upper_body_push",
        "subcategory": "vertical_press",
        "muscles_primary": ["pecs", "triceps", "anterior deltoid"],
        "muscles_secondary": ["core"],
        "pitching_relevance": "Bodyweight vertical push. Builds upper body pressing endurance and tricep strength for arm extension phase.",
        "prescription": {
            "strength": {"sets": "3", "reps": "6-8", "intensity": "bodyweight or weighted", "rest_min": 2},
            "hypertrophy": {"sets": "3", "reps": "10-15", "intensity": "bodyweight", "rest_min": 1.5},
        },
        "rotation_day_usage": {"recommended": ["day_3", "day_4"], "acceptable": ["day_2"], "avoid": ["day_0", "day_1", "day_5", "day_6"]},
        "tags": ["push", "upper_body", "bodyweight", "tricep"],
        "contraindications": ["acute_shoulder", "labrum_surgery_recent"],
        "modification_flags": {"shoulder_impingement": "limit_depth_or_substitute_pushup"},
        "youtube_url": "https://youtube.com/shorts/SXBksC78v8M?si=avZE3CrBWRPrh5E0",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library"
    },
    {
        "name": "Tricep Pull Down",
        "category": "upper_body_push",
        "subcategory": "tricep_isolation",
        "muscles_primary": ["triceps"],
        "muscles_secondary": [],
        "pitching_relevance": "Tricep isolation. Supports arm extension velocity and elbow stability.",
        "prescription": {
            "hypertrophy": {"sets": "3", "reps": "10-15", "intensity": "moderate", "rest_min": 1},
            "endurance": {"sets": "3", "reps": "15-20", "intensity": "light", "rest_min": 1},
        },
        "rotation_day_usage": {"recommended": ["day_2", "day_3", "day_4"], "acceptable": ["day_1"], "avoid": ["day_0", "day_5", "day_6"]},
        "tags": ["isolation", "tricep", "upper_body", "cable"],
        "contraindications": ["acute_elbow"],
        "modification_flags": {"ucl_history": "reduce_load_avoid_full_extension"},
        "youtube_url": "https://youtube.com/shorts/6Dh8sD6aNQE?si=9Bf2FWJSXmVHFLPv",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library"
    },
    {
        "name": "Straight Arm Pull Down",
        "category": "upper_body_pull",
        "subcategory": "lat_isolation",
        "muscles_primary": ["lats"],
        "muscles_secondary": ["teres major", "rear deltoid"],
        "pitching_relevance": "Isolated lat activation. Targets the primary arm accelerator without bicep involvement.",
        "prescription": {
            "hypertrophy": {"sets": "3", "reps": "10-12", "intensity": "moderate", "rest_min": 1.5},
            "endurance": {"sets": "3", "reps": "15", "intensity": "light", "rest_min": 1},
        },
        "rotation_day_usage": {"recommended": ["day_2", "day_3", "day_4"], "acceptable": ["day_1"], "avoid": ["day_0", "day_5", "day_6"]},
        "tags": ["isolation", "lat", "pull", "cable"],
        "contraindications": [],
        "modification_flags": {"shoulder_impingement": "reduce_ROM_overhead"},
        "youtube_url": "https://youtube.com/shorts/K9Tgn6sO3J0?si=eZdcOMGn6X9pvMiF",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library"
    },
    {
        "name": "Dumbbell Lateral Raise",
        "category": "upper_body_push",
        "subcategory": "shoulder_isolation",
        "muscles_primary": ["lateral deltoid"],
        "muscles_secondary": ["supraspinatus"],
        "pitching_relevance": "Lateral delt development for shoulder stability and overall shoulder strength balance.",
        "prescription": {
            "hypertrophy": {"sets": "3", "reps": "12-15", "intensity": "light", "rest_min": 1},
            "endurance": {"sets": "3", "reps": "15-20", "intensity": "very light", "rest_min": 1},
        },
        "rotation_day_usage": {"recommended": ["day_2", "day_3", "day_4"], "acceptable": ["day_1"], "avoid": ["day_0", "day_5", "day_6"]},
        "tags": ["isolation", "shoulder", "upper_body"],
        "contraindications": ["acute_shoulder", "shoulder_impingement_active"],
        "modification_flags": {"shoulder_impingement": "keep_below_90_degrees_or_skip"},
        "youtube_url": "https://youtube.com/shorts/JIhbYYA1Q90?si=5PGEVX-_sja4TszD",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library"
    },
    {
        "name": "Skull Crushers",
        "category": "upper_body_push",
        "subcategory": "tricep_isolation",
        "muscles_primary": ["triceps"],
        "muscles_secondary": [],
        "pitching_relevance": "Tricep isolation with eccentric emphasis. Builds arm extension strength.",
        "prescription": {
            "hypertrophy": {"sets": "3", "reps": "8-12", "intensity": "moderate", "rest_min": 1.5},
            "endurance": {"sets": "3", "reps": "12-15", "intensity": "light", "rest_min": 1},
        },
        "rotation_day_usage": {"recommended": ["day_3", "day_4"], "acceptable": ["day_2"], "avoid": ["day_0", "day_1", "day_5", "day_6"]},
        "tags": ["isolation", "tricep", "upper_body"],
        "contraindications": ["acute_elbow"],
        "modification_flags": {"ucl_history": "reduce_load_or_substitute_pushdown"},
        "youtube_url": "https://youtube.com/shorts/zR9gty7LUxE?si=gP7tr-m2e_m6pEf9",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library"
    },
    {
        "name": "Overhead Tricep Extension",
        "category": "upper_body_push",
        "subcategory": "tricep_isolation",
        "muscles_primary": ["triceps"],
        "muscles_secondary": [],
        "pitching_relevance": "Overhead tricep work — long head bias. Mimics overhead arm position in throwing.",
        "prescription": {
            "hypertrophy": {"sets": "3", "reps": "10-12", "intensity": "moderate", "rest_min": 1.5},
            "endurance": {"sets": "3", "reps": "12-15", "intensity": "light", "rest_min": 1},
        },
        "rotation_day_usage": {"recommended": ["day_3", "day_4"], "acceptable": ["day_2"], "avoid": ["day_0", "day_1", "day_5", "day_6"]},
        "tags": ["isolation", "tricep", "overhead", "upper_body"],
        "contraindications": ["acute_elbow", "acute_shoulder"],
        "modification_flags": {"ucl_history": "reduce_load", "shoulder_impingement": "substitute_pushdown_variant"},
        "youtube_url": "https://youtube.com/shorts/b_r_LW4HEcM?si=92GFsPDhFW6HuRKH",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library"
    },
    {
        "name": "Chin Up Grip Pull Down",
        "category": "upper_body_pull",
        "subcategory": "vertical_pull",
        "muscles_primary": ["lats", "biceps"],
        "muscles_secondary": ["rhomboids", "lower traps"],
        "pitching_relevance": "Supinated grip lat pulldown. Greater bicep involvement — builds arm flexor strength alongside pulling.",
        "prescription": {
            "strength": {"sets": "3", "reps": "6-8", "intensity": "heavy", "rest_min": 2},
            "hypertrophy": {"sets": "3", "reps": "10-12", "intensity": "moderate", "rest_min": 1.5},
        },
        "rotation_day_usage": {"recommended": ["day_2", "day_3", "day_4"], "acceptable": ["day_1"], "avoid": ["day_0", "day_5", "day_6"]},
        "tags": ["pull", "upper_body", "lat", "bicep", "machine"],
        "contraindications": [],
        "modification_flags": {"ucl_history": "use_neutral_grip_instead"},
        "youtube_url": "https://youtu.be/ShD5kVp1tjU?si=pNa-Yv1-BZrgCQXY",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library"
    },
    {
        "name": "Dumbbell Reverse Fly",
        "category": "upper_body_pull",
        "subcategory": "rear_delt_isolation",
        "muscles_primary": ["rear deltoid", "rhomboids"],
        "muscles_secondary": ["lower traps"],
        "pitching_relevance": "Posterior shoulder strengthening. Directly supports deceleration and scapular retraction post-release.",
        "prescription": {
            "hypertrophy": {"sets": "3", "reps": "12-15", "intensity": "light", "rest_min": 1},
            "endurance": {"sets": "3", "reps": "15-20", "intensity": "very light", "rest_min": 1},
        },
        "rotation_day_usage": {"recommended": ["day_2", "day_3", "day_4"], "acceptable": ["day_1", "day_5"], "avoid": ["day_0", "day_6"]},
        "tags": ["isolation", "rear_delt", "posterior_shoulder", "deceleration"],
        "contraindications": [],
        "modification_flags": {"shoulder_impingement": "no_modification_needed"},
        "youtube_url": "https://youtube.com/shorts/4eSyt7pEK8Q?si=IjFQ-RE630PENVNd",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library"
    },
    {
        "name": "Plyo Push-Up",
        "category": "plyometric_power",
        "subcategory": "upper_body_explosive",
        "muscles_primary": ["pecs", "triceps", "anterior deltoid"],
        "muscles_secondary": ["core", "serratus anterior"],
        "pitching_relevance": "Upper body explosive power. Develops rate of force development in pushing muscles — transfers to arm acceleration.",
        "prescription": {
            "power": {"sets": "3", "reps": "5-6", "intensity": "bodyweight, max explosive intent", "rest_min": 2, "note": "Full hand clearance from ground"},
        },
        "rotation_day_usage": {"recommended": ["day_2", "day_3"], "acceptable": ["day_4"], "avoid": ["day_0", "day_1", "day_5", "day_6"]},
        "tags": ["plyometric", "power", "explosive", "upper_body", "bodyweight"],
        "contraindications": ["acute_shoulder", "acute_wrist"],
        "modification_flags": {"shoulder_impingement": "substitute_med_ball_chest_pass", "ucl_history": "no_modification_needed"},
        "youtube_url": "https://youtube.com/shorts/n-HUnTmCTys?si=edpEdIT5PpE82DZu",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library"
    },
    {
        "name": "Weighted I/T/Y Raises",
        "category": "scapular_stability",
        "subcategory": "scapular_activation",
        "muscles_primary": ["lower traps", "middle traps", "supraspinatus"],
        "muscles_secondary": ["rear deltoid", "rhomboids"],
        "pitching_relevance": "Scapular stabilizer trifecta. Builds the foundation muscles that position the scapula for safe overhead throwing.",
        "prescription": {
            "endurance": {"sets": "3", "reps": "8-10 each position", "intensity": "2.5-5 lb plates", "rest_min": 1},
            "hypertrophy": {"sets": "3", "reps": "10-12 each position", "intensity": "light", "rest_min": 1},
        },
        "rotation_day_usage": {"recommended": ["day_1", "day_2", "day_3", "day_4"], "acceptable": ["day_5"], "avoid": ["day_0"]},
        "tags": ["scapular", "stability", "shoulder_health", "warmup"],
        "contraindications": [],
        "modification_flags": {"shoulder_impingement": "reduce_weight_increase_reps"},
        "youtube_url": "https://youtube.com/shorts/_XJksTY6enk?si=iNWXqjKO2bOukGx_",
        "evidence_level": "strong",
        "source_notes": "UChicago exercise library. Cressey/Reinold protocol."
    },
    # --- Arms (integrated as upper_body_push/pull accessories) ---
    {
        "name": "Standing Dumbbell Curl",
        "category": "upper_body_pull",
        "subcategory": "bicep_isolation",
        "muscles_primary": ["biceps"],
        "muscles_secondary": ["forearms"],
        "pitching_relevance": "Bicep strengthening supports elbow flexion stability and deceleration.",
        "prescription": {
            "hypertrophy": {"sets": "3", "reps": "10-12", "intensity": "moderate", "rest_min": 1},
            "endurance": {"sets": "3", "reps": "15", "intensity": "light", "rest_min": 1},
        },
        "rotation_day_usage": {"recommended": ["day_2", "day_3", "day_4"], "acceptable": ["day_1"], "avoid": ["day_0", "day_5", "day_6"]},
        "tags": ["isolation", "bicep", "upper_body", "dumbbell"],
        "contraindications": ["acute_elbow"],
        "modification_flags": {"ucl_history": "reduce_load_avoid_full_extension"},
        "youtube_url": "https://youtube.com/shorts/MKWBV29S6c0?si=-3qXzQQyP89_QS8E",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library"
    },
    {
        "name": "EZ Bar Curl",
        "category": "upper_body_pull",
        "subcategory": "bicep_isolation",
        "muscles_primary": ["biceps"],
        "muscles_secondary": ["forearms"],
        "pitching_relevance": "EZ bar reduces wrist strain during curls. Good for pitchers with forearm tightness.",
        "prescription": {
            "hypertrophy": {"sets": "3", "reps": "8-12", "intensity": "moderate", "rest_min": 1.5},
        },
        "rotation_day_usage": {"recommended": ["day_2", "day_3", "day_4"], "acceptable": ["day_1"], "avoid": ["day_0", "day_5", "day_6"]},
        "tags": ["isolation", "bicep", "upper_body"],
        "contraindications": ["acute_elbow"],
        "modification_flags": {"ucl_history": "reduce_load"},
        "youtube_url": "https://youtube.com/shorts/pT-wvBPSMZU?si=8ED5058ZYjyuZtQ1",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library"
    },
    # --- Core (from Accessories sheet) ---
    {
        "name": "Weighted Toe Touches",
        "category": "core",
        "subcategory": "flexion",
        "muscles_primary": ["rectus abdominis"],
        "muscles_secondary": ["hip flexors"],
        "pitching_relevance": "Trunk flexion strength. Supports the trunk flexion component of the pitching delivery.",
        "prescription": {
            "hypertrophy": {"sets": "3", "reps": "15-20", "intensity": "light plate", "rest_min": 1},
            "endurance": {"sets": "3", "reps": "20-25", "intensity": "bodyweight or light", "rest_min": 1},
        },
        "rotation_day_usage": {"recommended": ["day_2", "day_3", "day_4"], "acceptable": ["day_1"], "avoid": ["day_0", "day_5", "day_6"]},
        "tags": ["core", "flexion", "weighted"],
        "contraindications": ["acute_low_back"],
        "modification_flags": {"low_back_history": "reduce_ROM_or_substitute_dead_bug"},
        "youtube_url": "https://youtu.be/HdhmIUkB-iY?si=FagMTgHh9efWU5Xr",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library"
    },
    {
        "name": "Decline Weighted Sit-Ups",
        "category": "core",
        "subcategory": "flexion",
        "muscles_primary": ["rectus abdominis"],
        "muscles_secondary": ["hip flexors", "obliques"],
        "pitching_relevance": "Loaded trunk flexion against gravity. Builds the power needed for trunk flexion at release point.",
        "prescription": {
            "strength": {"sets": "3", "reps": "10-12", "intensity": "moderate plate", "rest_min": 1.5},
            "hypertrophy": {"sets": "3", "reps": "15-20", "intensity": "light plate", "rest_min": 1},
        },
        "rotation_day_usage": {"recommended": ["day_2", "day_3", "day_4"], "acceptable": ["day_1"], "avoid": ["day_0", "day_5", "day_6"]},
        "tags": ["core", "flexion", "weighted", "decline"],
        "contraindications": ["acute_low_back"],
        "modification_flags": {"low_back_history": "substitute_dead_bug_or_plank"},
        "youtube_url": "https://youtube.com/shorts/yordNDJ2WPU?si=rn7Lot63S4qLCEIR",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library"
    },
    {
        "name": "Rope Crunch",
        "category": "core",
        "subcategory": "flexion",
        "muscles_primary": ["rectus abdominis"],
        "muscles_secondary": ["obliques"],
        "pitching_relevance": "Cable-loaded trunk flexion. Constant tension through ROM builds core strength for delivery.",
        "prescription": {
            "hypertrophy": {"sets": "3", "reps": "12-15", "intensity": "moderate", "rest_min": 1},
        },
        "rotation_day_usage": {"recommended": ["day_2", "day_3", "day_4"], "acceptable": ["day_1"], "avoid": ["day_0", "day_5", "day_6"]},
        "tags": ["core", "flexion", "cable"],
        "contraindications": ["acute_low_back"],
        "modification_flags": {"low_back_history": "reduce_weight"},
        "youtube_url": "https://youtu.be/b9FJ4hIK3pI?si=QMo3RQU42uCiaxs_",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library"
    },
    {
        "name": "Hanging Leg Raise",
        "category": "core",
        "subcategory": "flexion",
        "muscles_primary": ["rectus abdominis", "hip flexors"],
        "muscles_secondary": ["obliques", "grip"],
        "pitching_relevance": "Advanced core exercise. Builds hip flexor and abdominal strength in a hanging position — grip + core combo.",
        "prescription": {
            "strength": {"sets": "3", "reps": "8-12", "intensity": "bodyweight", "rest_min": 1.5},
            "hypertrophy": {"sets": "3", "reps": "12-15", "intensity": "bodyweight", "rest_min": 1},
        },
        "rotation_day_usage": {"recommended": ["day_2", "day_3", "day_4"], "acceptable": ["day_1"], "avoid": ["day_0", "day_5", "day_6"]},
        "tags": ["core", "flexion", "advanced", "grip"],
        "contraindications": ["acute_shoulder", "acute_low_back"],
        "modification_flags": {"shoulder_impingement": "substitute_lying_leg_raise"},
        "youtube_url": "https://youtube.com/shorts/2n4UqRIJyk4?si=C04Pt4dlu0fJqtlm",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library"
    },
    # --- Med Ball (plyometric_power) ---
    {
        "name": "Rotational Med Ball Slam",
        "category": "plyometric_power",
        "subcategory": "rotational_power",
        "muscles_primary": ["obliques", "lats", "hip rotators"],
        "muscles_secondary": ["core", "shoulders"],
        "pitching_relevance": "Rotational power development with deceleration component. Directly mimics throwing rotational sequence.",
        "prescription": {
            "power": {"sets": "3", "reps": "5-6 each side", "intensity": "6-8 lb med ball, max intent", "rest_min": 2},
        },
        "rotation_day_usage": {"recommended": ["day_2", "day_3"], "acceptable": ["day_4"], "avoid": ["day_0", "day_1", "day_5", "day_6"]},
        "tags": ["plyometric", "power", "rotational", "med_ball", "explosive"],
        "contraindications": ["acute_oblique"],
        "modification_flags": {"oblique_strain": "skip_entirely"},
        "youtube_url": "https://youtube.com/shorts/8ReGsLOc-lo?si=RSohtvSpwJOsXvxK",
        "evidence_level": "strong",
        "source_notes": "UChicago exercise library"
    },
    {
        "name": "Med Ball Slam",
        "category": "plyometric_power",
        "subcategory": "sagittal_power",
        "muscles_primary": ["lats", "core", "triceps"],
        "muscles_secondary": ["shoulders"],
        "pitching_relevance": "Sagittal plane power. Develops trunk flexion velocity and upper body power production.",
        "prescription": {
            "power": {"sets": "3", "reps": "6-8", "intensity": "8-10 lb med ball, max intent", "rest_min": 2},
        },
        "rotation_day_usage": {"recommended": ["day_2", "day_3"], "acceptable": ["day_4"], "avoid": ["day_0", "day_1", "day_5", "day_6"]},
        "tags": ["plyometric", "power", "med_ball", "explosive"],
        "contraindications": ["acute_shoulder"],
        "modification_flags": {"shoulder_impingement": "reduce_overhead_arc"},
        "youtube_url": "https://youtube.com/shorts/99DLQtHP7jE?si=cY-37LkfrMxuEi3U",
        "evidence_level": "strong",
        "source_notes": "UChicago exercise library"
    },
    {
        "name": "Kneeling Med Ball Slam",
        "category": "plyometric_power",
        "subcategory": "sagittal_power",
        "muscles_primary": ["lats", "core"],
        "muscles_secondary": ["triceps", "shoulders"],
        "pitching_relevance": "Kneeling removes lower body — isolates trunk and upper body power production.",
        "prescription": {
            "power": {"sets": "3", "reps": "6-8", "intensity": "6-8 lb med ball", "rest_min": 1.5},
        },
        "rotation_day_usage": {"recommended": ["day_2", "day_3", "day_4"], "acceptable": ["day_1"], "avoid": ["day_0", "day_5", "day_6"]},
        "tags": ["plyometric", "power", "med_ball", "kneeling"],
        "contraindications": ["acute_shoulder"],
        "modification_flags": {"shoulder_impingement": "reduce_overhead_arc"},
        "youtube_url": "https://youtube.com/shorts/JLLm3QtHkuY?si=VtOY8P3KV5_Qgl1c",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library"
    },
    {
        "name": "Split Stance Med Ball Slam",
        "category": "plyometric_power",
        "subcategory": "sagittal_power",
        "muscles_primary": ["lats", "core", "hip flexors"],
        "muscles_secondary": ["quads", "shoulders"],
        "pitching_relevance": "Staggered stance mimics delivery position. Integrates lower/upper body power in throwing-specific stance.",
        "prescription": {
            "power": {"sets": "3", "reps": "5-6 each stance", "intensity": "6-8 lb med ball", "rest_min": 2},
        },
        "rotation_day_usage": {"recommended": ["day_2", "day_3"], "acceptable": ["day_4"], "avoid": ["day_0", "day_1", "day_5", "day_6"]},
        "tags": ["plyometric", "power", "med_ball", "split_stance", "explosive"],
        "contraindications": ["acute_oblique"],
        "modification_flags": {"oblique_strain": "skip_entirely"},
        "youtube_url": "https://youtube.com/shorts/Me-KliTyDwo?si=GL9aUuSOnROCPMqq",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library"
    },
    {
        "name": "Split Stance Med Ball Throw",
        "category": "plyometric_power",
        "subcategory": "rotational_power",
        "muscles_primary": ["obliques", "hip rotators", "lats"],
        "muscles_secondary": ["core", "shoulders"],
        "pitching_relevance": "Rotational throwing from split stance. Most sport-specific med ball variation for pitchers.",
        "prescription": {
            "power": {"sets": "3", "reps": "5-6 each side", "intensity": "6 lb med ball, max intent", "rest_min": 2},
        },
        "rotation_day_usage": {"recommended": ["day_2", "day_3"], "acceptable": ["day_4"], "avoid": ["day_0", "day_1", "day_5", "day_6"]},
        "tags": ["plyometric", "power", "rotational", "med_ball", "throwing_specific"],
        "contraindications": ["acute_oblique"],
        "modification_flags": {"oblique_strain": "skip_entirely"},
        "youtube_url": "https://youtube.com/shorts/3Zfy4W1o4y0?si=n9sqNySSjOivI9Hh",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library"
    },
    {
        "name": "Walking Overhead Med Ball Throw",
        "category": "plyometric_power",
        "subcategory": "sagittal_power",
        "muscles_primary": ["lats", "core", "hip extensors"],
        "muscles_secondary": ["shoulders", "triceps"],
        "pitching_relevance": "Full-body power chain with walking momentum. Builds stride-into-throw kinetic chain.",
        "prescription": {
            "power": {"sets": "3", "reps": "5-6", "intensity": "8-10 lb med ball", "rest_min": 2},
        },
        "rotation_day_usage": {"recommended": ["day_2", "day_3"], "acceptable": ["day_4"], "avoid": ["day_0", "day_1", "day_5", "day_6"]},
        "tags": ["plyometric", "power", "med_ball", "full_body"],
        "contraindications": ["acute_shoulder"],
        "modification_flags": {"shoulder_impingement": "substitute_slam_variant"},
        "youtube_url": "https://youtu.be/UyXV4wpqerM?si=is6L2UL2PiEfEOKT",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library"
    },
    {
        "name": "Rotational Med Ball Chest Pass",
        "category": "plyometric_power",
        "subcategory": "rotational_power",
        "muscles_primary": ["pecs", "obliques", "hip rotators"],
        "muscles_secondary": ["triceps", "core"],
        "pitching_relevance": "Rotational chest pass develops horizontal push power through rotation. Complements overhead throwing variations.",
        "prescription": {
            "power": {"sets": "3", "reps": "5-6 each side", "intensity": "6-8 lb med ball", "rest_min": 2},
        },
        "rotation_day_usage": {"recommended": ["day_2", "day_3"], "acceptable": ["day_4"], "avoid": ["day_0", "day_1", "day_5", "day_6"]},
        "tags": ["plyometric", "power", "rotational", "med_ball", "chest_pass"],
        "contraindications": ["acute_oblique"],
        "modification_flags": {"oblique_strain": "skip_entirely"},
        "youtube_url": "https://youtube.com/shorts/UqY5p9XnvOU?si=LU2CSO21OvT6O424",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library"
    },
    {
        "name": "Half Kneeling Rotational Med Ball Throw",
        "category": "plyometric_power",
        "subcategory": "rotational_power",
        "muscles_primary": ["obliques", "hip rotators"],
        "muscles_secondary": ["core", "shoulders"],
        "pitching_relevance": "Kneeling isolates rotational power from the trunk without lower body momentum. Pure core/hip rotation training.",
        "prescription": {
            "power": {"sets": "3", "reps": "5-6 each side", "intensity": "4-6 lb med ball", "rest_min": 1.5},
        },
        "rotation_day_usage": {"recommended": ["day_2", "day_3", "day_4"], "acceptable": ["day_1"], "avoid": ["day_0", "day_5", "day_6"]},
        "tags": ["plyometric", "power", "rotational", "med_ball", "kneeling"],
        "contraindications": ["acute_oblique"],
        "modification_flags": {"oblique_strain": "skip_entirely"},
        "youtube_url": "https://youtu.be/c9C4uUF39hE?si=D4H9bAnvEImlayht",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library"
    },
    {
        "name": "Med Ball Slam + Rotational Throw Combo",
        "category": "plyometric_power",
        "subcategory": "combo_power",
        "muscles_primary": ["core", "obliques", "lats"],
        "muscles_secondary": ["shoulders", "hip rotators"],
        "pitching_relevance": "Combo drill builds multi-plane power and work capacity. Mimics the varied demands of repeated delivery efforts.",
        "prescription": {
            "power": {"sets": "3", "reps": "4-5 combos", "intensity": "6-8 lb med ball", "rest_min": 2},
        },
        "rotation_day_usage": {"recommended": ["day_2", "day_3"], "acceptable": ["day_4"], "avoid": ["day_0", "day_1", "day_5", "day_6"]},
        "tags": ["plyometric", "power", "combo", "med_ball"],
        "contraindications": ["acute_oblique", "acute_shoulder"],
        "modification_flags": {"oblique_strain": "skip_entirely"},
        "youtube_url": "https://youtube.com/shorts/xipSepmzHHg?si=6Es2tBZgpAWEIiXs",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library"
    },
    {
        "name": "Back Facing Rotational Med Ball Throw",
        "category": "plyometric_power",
        "subcategory": "rotational_power",
        "muscles_primary": ["obliques", "hip rotators", "lats"],
        "muscles_secondary": ["core", "glutes"],
        "pitching_relevance": "Extreme rotational ROM. Starts facing away from target — builds full rotational range of force production.",
        "prescription": {
            "power": {"sets": "3", "reps": "4-5 each side", "intensity": "4-6 lb med ball, max intent", "rest_min": 2},
        },
        "rotation_day_usage": {"recommended": ["day_2", "day_3"], "acceptable": ["day_4"], "avoid": ["day_0", "day_1", "day_5", "day_6"]},
        "tags": ["plyometric", "power", "rotational", "med_ball", "advanced"],
        "contraindications": ["acute_oblique"],
        "modification_flags": {"oblique_strain": "skip_entirely"},
        "youtube_url": "https://youtube.com/shorts/7fbeRfHsyuQ?si=ePwVGUDDFM7HYPik",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library"
    },
    {
        "name": "Rear Leg Elevated Med Ball Slam",
        "category": "plyometric_power",
        "subcategory": "sagittal_power",
        "muscles_primary": ["core", "lats", "hip flexors"],
        "muscles_secondary": ["quads", "shoulders"],
        "pitching_relevance": "Single-leg stability + slam power. Builds power in a position that challenges stride-leg balance.",
        "prescription": {
            "power": {"sets": "3", "reps": "5-6 each leg", "intensity": "6-8 lb med ball", "rest_min": 2},
        },
        "rotation_day_usage": {"recommended": ["day_2", "day_3"], "acceptable": ["day_4"], "avoid": ["day_0", "day_1", "day_5", "day_6"]},
        "tags": ["plyometric", "power", "med_ball", "single_leg", "balance"],
        "contraindications": ["acute_knee", "acute_ankle"],
        "modification_flags": {"knee_history": "substitute_bilateral_slam"},
        "youtube_url": "https://youtu.be/_5tSIbEr7Y8?si=u_Ov8WrEM0utfq_I",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library"
    },
]

# YouTube URL backfills for existing exercises (curated matches with new videos)
YOUTUBE_BACKFILLS = {
    "ex_003": "https://youtu.be/5S8SApGU_Lk?si=5ySdDtnje3end4bq",     # Barbell Hip Thrust
    "ex_004": "https://youtu.be/AGvR91bbHy8?si=a_K0I6mhT27xMPfo",     # RFESS / Bulgarian Split Squat
    "ex_006": "https://youtube.com/shorts/s32cCgmRV3I?si=ZuyElKkBdvrpalRX",  # Single-Leg RDL
    "ex_007": "https://youtu.be/3dLIa1YljLs?si=tuLL9R6qbQkmhgLG",     # Goblet Squat (Heel Elevated)
    "ex_009": "https://youtu.be/VTtLrBvHoJ8?si=oOQ22Fo0vW2guNaw",     # Landmine Lateral Lunge
    "ex_011": "https://youtube.com/shorts/6e0tp0_s5Zs?si=658yEaZvFhQMBH5d",  # Landmine RDL
    "ex_015": "https://youtube.com/shorts/02c2YLgF8iE?si=VhWstlBfsecir5sF",  # Med Ball Scoop Toss
    "ex_026": "https://youtube.com/shorts/wUFMBUX5L0M?si=M_ItZjoen_kOQlgm",  # Half-Kneeling Landmine Press
}


def load_library():
    with open(EXERCISE_LIBRARY) as f:
        return json.load(f)


def save_library(lib):
    with open(EXERCISE_LIBRARY, "w") as f:
        json.dump(lib, f, indent=2)
    logger.info("Saved exercise_library.json")


def get_next_id(exercises):
    """Return next available ex_### ID."""
    max_num = 0
    for ex in exercises:
        try:
            num = int(ex["id"].replace("ex_", ""))
            max_num = max(max_num, num)
        except ValueError:
            continue
    return max_num + 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--supabase", action="store_true", help="Also sync to Supabase")
    args = parser.parse_args()

    lib = load_library()
    exercises = lib["exercises"]

    # --- Phase 1: Backfill YouTube URLs ---
    backfill_count = 0
    for ex in exercises:
        if ex["id"] in YOUTUBE_BACKFILLS and not ex.get("youtube_url"):
            url = YOUTUBE_BACKFILLS[ex["id"]]
            if args.dry_run:
                logger.info("[DRY RUN] Backfill %s (%s) <- %s", ex["id"], ex["name"], url)
            else:
                ex["youtube_url"] = url
            backfill_count += 1

    logger.info("YouTube backfills: %d exercises", backfill_count)

    # --- Phase 2: Add new exercises ---
    next_num = get_next_id(exercises)
    new_count = 0
    for new_ex in NEW_EXERCISES:
        ex_id = f"ex_{next_num:03d}"
        entry = {"id": ex_id, "slug": ex_id, "aliases": [], **new_ex}
        if args.dry_run:
            logger.info("[DRY RUN] New %s: %s (%s)", ex_id, new_ex["name"], new_ex["category"])
        else:
            exercises.append(entry)
        next_num += 1
        new_count += 1

    logger.info("New exercises: %d (ex_%03d through ex_%03d)", new_count, next_num - new_count, next_num - 1)

    if not args.dry_run:
        save_library(lib)

    # --- Phase 3: Sync to Supabase ---
    if args.supabase and not args.dry_run:
        try:
            from supabase import create_client
            import os
            url = os.environ.get("SUPABASE_URL")
            key = os.environ.get("SUPABASE_SERVICE_KEY")
            if not url or not key:
                logger.error("Set SUPABASE_URL and SUPABASE_SERVICE_KEY to sync")
                return
            sb = create_client(url, key)

            # Upsert all exercises (backfills + new)
            for ex in exercises:
                row = {
                    "id": ex["id"],
                    "name": ex["name"],
                    "slug": ex.get("slug", ex["id"]),
                    "aliases": ex.get("aliases", []),
                    "category": ex.get("category", ""),
                    "subcategory": ex.get("subcategory", ""),
                    "muscles_primary": ex.get("muscles_primary", []),
                    "muscles_secondary": ex.get("muscles_secondary", []),
                    "pitching_relevance": ex.get("pitching_relevance", ""),
                    "prescription": ex.get("prescription", {}),
                    "rotation_day_usage": ex.get("rotation_day_usage", {}),
                    "tags": ex.get("tags", []),
                    "contraindications": ex.get("contraindications", []),
                    "modification_flags": ex.get("modification_flags", {}),
                    "youtube_url": ex.get("youtube_url", ""),
                    "evidence_level": ex.get("evidence_level", "moderate"),
                    "source_notes": ex.get("source_notes", ""),
                }
                sb.table("exercises").upsert(row, on_conflict="id").execute()

            logger.info("Supabase sync complete")
        except Exception as e:
            logger.error("Supabase sync failed: %s", e)

    logger.info("Done. Total exercises: %d", len(exercises) if not args.dry_run else len(exercises) + new_count)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run dry-run to verify**

Run: `cd pitcher_program_app && python -m scripts.enrich_exercises --dry-run`
Expected: Lists 8 YouTube backfills and ~35 new exercises with IDs ex_121 through ex_155+

- [ ] **Step 3: Run for real (JSON only first)**

Run: `cd pitcher_program_app && python -m scripts.enrich_exercises`
Expected: `exercise_library.json` updated. Verify with `python3 -c "import json; lib=json.load(open('data/knowledge/exercise_library.json')); print(len(lib['exercises']))"`
Should show ~155.

- [ ] **Step 4: Sync to Supabase**

Run: `cd pitcher_program_app && python -m scripts.enrich_exercises --supabase`
Expected: All exercises upserted. Verify:
```sql
SELECT COUNT(*) FROM exercises;  -- should be ~155
SELECT id, name, youtube_url FROM exercises WHERE youtube_url != '' ORDER BY id;
```

- [ ] **Step 5: Commit**

```bash
git add scripts/enrich_exercises.py data/knowledge/exercise_library.json
git commit -m "Enrich exercise library: 8 YouTube backfills + ~35 new exercises (lifts, arms, med ball, core)"
```

---

### Task 2: Ensure Exercise Pool Includes Med Ball / Plyometric Exercises in Every Lift

User requirement: "Each lift should have some sort of explosive aspect to it unless specifically safeguarded against." The exercise pool currently selects compounds + accessories + core. We need to add an explicit **Power/Explosive** block that pulls from `plyometric_power` category.

**Files:**
- Modify: `bot/services/exercise_pool.py:41-55`

- [ ] **Step 1: Read the full exercise_pool.py to understand current selection logic**

Read: `bot/services/exercise_pool.py` (full file)

- [ ] **Step 2: Add plyometric_power to the selection logic**

In `exercise_pool.py`, the `FOCUS_CATEGORIES` dict controls which categories are eligible per day focus. Currently `plyometric_power` is in `lower` and `full` but NOT in `upper`. Additionally, the `SESSION_STRUCTURE` only has `(compounds, accessories, core)` — no explicit explosive slot.

Modify `SESSION_STRUCTURE` to add an explosive count as the 4th tuple element:

```python
# Session structure: (compounds, accessories, core, explosive) counts
SESSION_STRUCTURE = {
    "full":     (2, 3, 2, 1),
    "lower":    (2, 3, 2, 1),
    "upper":    (2, 3, 2, 1),
    "light":    (1, 2, 1, 0),  # no explosive on light days
    "recovery": (0, 0, 0, 0),
}
```

Add `plyometric_power` to the `upper` focus:
```python
FOCUS_CATEGORIES = {
    "lower": {"lower_body_compound", "plyometric_power"},
    "upper": {"upper_body_pull", "upper_body_push", "plyometric_power"},
    "full": {"lower_body_compound", "upper_body_pull", "upper_body_push", "plyometric_power"},
    "recovery": set(),
}
```

In the `build_exercise_pool()` function, after the existing compound/accessory/core selection, add explosive selection:

```python
# Select explosive/plyometric exercises
explosive_count = structure[3] if len(structure) > 3 else 0
if explosive_count > 0:
    plyo_candidates = [
        e for e in eligible
        if e.get("category") == "plyometric_power"
        and e["id"] not in {ex["exercise_id"] for block in blocks for ex in block.get("exercises", [])}
    ]
    plyo_selected = _pick_exercises(plyo_candidates, explosive_count, recent_exercise_ids, day_key)
    if plyo_selected:
        blocks.insert(0, {
            "block_name": "Explosive",
            "exercises": [_format_exercise(e, training_intent) for e in plyo_selected],
        })
```

This inserts the explosive block at position 0 (first block in the lift), which is standard programming order (power before strength).

- [ ] **Step 3: Verify the pool builder still works**

Run: `cd pitcher_program_app && python3 -c "
from bot.services.exercise_pool import build_exercise_pool
pool = build_exercise_pool(2, 'upper', 'strength', {'injury_history': []}, set(), {'flag_level': 'green', 'protocol_adjustments': {}})
for block in pool:
    print(f'{block[\"block_name\"]}: {len(block[\"exercises\"])} exercises')
    for ex in block['exercises']:
        print(f'  - {ex[\"name\"]} ({ex[\"exercise_id\"]})')
"`
Expected: Should show an "Explosive" block with 1 plyometric exercise, followed by compounds, accessories, and core.

- [ ] **Step 4: Commit**

```bash
git add bot/services/exercise_pool.py
git commit -m "Add explosive/plyometric block to every lift session (med ball, plyo pushups, jumps)"
```

---

### Task 3: Create Mobility Video Data + Supabase Table

**Files:**
- Create: `data/knowledge/mobility_videos.json`
- Create: `scripts/seed_mobility_videos.py`

- [ ] **Step 1: Create the mobility_videos.json data file**

```json
{
  "$schema": "mobility_videos",
  "$description": "10-week rotating mobility video program. 4 videos per week: 3 P/R (postural restoration) + 1 targeted. Cycles back to week 1 after week 10.",
  "videos": [
    {"id": "mob_001", "youtube_url": "https://www.youtube.com/watch?v=injmxSkTXaY", "type": "P/R", "title": "P/R Routine A"},
    {"id": "mob_002", "youtube_url": "https://www.youtube.com/watch?v=PQwpLfBiB5U", "type": "P/R", "title": "P/R Routine B"},
    {"id": "mob_003", "youtube_url": "https://www.youtube.com/watch?v=V-bBSjBZbIs", "type": "P/R", "title": "P/R Routine C"},
    {"id": "mob_004", "youtube_url": "https://youtu.be/KfElAgr72Vo?si=VDTz-SAlrjvn_lo8", "type": "Hip", "title": "Hip Mobility A"},
    {"id": "mob_005", "youtube_url": "https://www.youtube.com/watch?v=Kp8r-OACCKE", "type": "P/R", "title": "P/R Routine D"},
    {"id": "mob_006", "youtube_url": "https://www.youtube.com/watch?v=7vokuI8D8QU", "type": "P/R", "title": "P/R Routine E"},
    {"id": "mob_007", "youtube_url": "https://www.youtube.com/watch?v=wbHWRAHGZxc", "type": "P/R", "title": "P/R Routine F"},
    {"id": "mob_008", "youtube_url": "https://youtu.be/lPKRiU9u_Hc?si=Ji7IduozPWLWfZ9U", "type": "Full", "title": "Full Body Mobility A"},
    {"id": "mob_009", "youtube_url": "https://www.youtube.com/watch?v=IU3A-pwsynQ", "type": "P/R", "title": "P/R Routine G"},
    {"id": "mob_010", "youtube_url": "https://youtu.be/JLdgw-FWGr4?si=t16CNDcj0gYAWESE", "type": "Back", "title": "Back Mobility"},
    {"id": "mob_011", "youtube_url": "https://www.youtube.com/watch?v=iBEtEPGb_Lg", "type": "P/R", "title": "P/R Routine H"},
    {"id": "mob_012", "youtube_url": "https://www.youtube.com/watch?v=RRiPvafe6dM", "type": "P/R", "title": "P/R Routine I"},
    {"id": "mob_013", "youtube_url": "https://youtu.be/Wa_FD6EsBSg?si=8sIcRE_7-pFFx6to", "type": "Lower", "title": "Lower Body Mobility A"},
    {"id": "mob_014", "youtube_url": "https://www.youtube.com/watch?v=v_gG-swvg7g", "type": "P/R", "title": "P/R Routine J"},
    {"id": "mob_015", "youtube_url": "https://www.youtube.com/watch?v=axqwhAgDEec", "type": "P/R", "title": "P/R Routine K"},
    {"id": "mob_016", "youtube_url": "https://youtu.be/TNU6umd0sNA?si=R5dxckwpfx2uLFW0", "type": "Shoulder", "title": "Shoulder Mobility"},
    {"id": "mob_017", "youtube_url": "https://youtu.be/jj2AAH6jbHk?si=idyFwR2OhzbzW5dY", "type": "Hip", "title": "Hip Mobility B"},
    {"id": "mob_018", "youtube_url": "https://youtu.be/9iHko2F81cE?si=aQoWbdr5WbkboRnL", "type": "Shoulder/Spine", "title": "Shoulder & Spine Mobility A"},
    {"id": "mob_019", "youtube_url": "https://youtu.be/DCdKTMlatYw?si=lAQfFYq6jYL6-MZc", "type": "Lower", "title": "Lower Body Mobility B"},
    {"id": "mob_020", "youtube_url": "https://youtu.be/P_QR28TIjEQ?si=aYqHOcv5rQCeIBQA", "type": "Full", "title": "Full Body Mobility B"},
    {"id": "mob_021", "youtube_url": "https://youtu.be/Btn6J6NFFSU?si=FYCpu6HnqVZy64qy", "type": "Shoulder/Spine", "title": "Shoulder & Spine Mobility B"}
  ],
  "weekly_rotation": [
    {"week": 1, "slots": ["mob_001", "mob_002", "mob_003", "mob_004"]},
    {"week": 2, "slots": ["mob_005", "mob_006", "mob_007", "mob_008"]},
    {"week": 3, "slots": ["mob_009", "mob_001", "mob_002", "mob_010"]},
    {"week": 4, "slots": ["mob_007", "mob_011", "mob_012", "mob_013"]},
    {"week": 5, "slots": ["mob_014", "mob_015", "mob_015", "mob_016"]},
    {"week": 6, "slots": ["mob_001", "mob_002", "mob_005", "mob_017"]},
    {"week": 7, "slots": ["mob_001", "mob_002", "mob_005", "mob_018"]},
    {"week": 8, "slots": ["mob_007", "mob_002", "mob_003", "mob_019"]},
    {"week": 9, "slots": ["mob_009", "mob_001", "mob_002", "mob_020"]},
    {"week": 10, "slots": ["mob_007", "mob_001", "mob_006", "mob_021"]}
  ]
}
```

- [ ] **Step 2: Create Supabase migration for mobility_videos table**

Apply via Supabase MCP:

```sql
CREATE TABLE IF NOT EXISTS mobility_videos (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  youtube_url TEXT NOT NULL,
  type TEXT NOT NULL,  -- 'P/R', 'Hip', 'Full', 'Back', 'Lower', 'Shoulder', 'Shoulder/Spine'
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS mobility_weekly_rotation (
  week INT NOT NULL,
  slot INT NOT NULL,      -- 1-4 within the week
  video_id TEXT NOT NULL REFERENCES mobility_videos(id),
  PRIMARY KEY (week, slot)
);

-- Enable RLS but allow service role full access
ALTER TABLE mobility_videos ENABLE ROW LEVEL SECURITY;
ALTER TABLE mobility_weekly_rotation ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access" ON mobility_videos FOR ALL USING (true);
CREATE POLICY "Service role full access" ON mobility_weekly_rotation FOR ALL USING (true);
```

- [ ] **Step 3: Create seed script**

```python
# scripts/seed_mobility_videos.py
"""Seed mobility_videos and mobility_weekly_rotation tables from JSON.

Usage:
    cd pitcher_program_app
    python -m scripts.seed_mobility_videos
"""

import json
import os
import sys
from pathlib import Path

try:
    from supabase import create_client
except ImportError:
    print("Install supabase-py: pip install supabase")
    sys.exit(1)

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "knowledge" / "mobility_videos.json"


def main():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        print("Set SUPABASE_URL and SUPABASE_SERVICE_KEY")
        sys.exit(1)

    sb = create_client(url, key)

    with open(DATA_FILE) as f:
        data = json.load(f)

    # Seed videos
    for v in data["videos"]:
        sb.table("mobility_videos").upsert({
            "id": v["id"],
            "title": v["title"],
            "youtube_url": v["youtube_url"],
            "type": v["type"],
        }, on_conflict="id").execute()

    print(f"Seeded {len(data['videos'])} mobility videos")

    # Seed weekly rotation
    for week_data in data["weekly_rotation"]:
        week = week_data["week"]
        for slot_idx, video_id in enumerate(week_data["slots"], start=1):
            sb.table("mobility_weekly_rotation").upsert({
                "week": week,
                "slot": slot_idx,
                "video_id": video_id,
            }, on_conflict="week,slot").execute()

    print(f"Seeded {len(data['weekly_rotation'])} weeks of rotation")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the seed script**

Run: `cd pitcher_program_app && python -m scripts.seed_mobility_videos`
Expected: "Seeded 21 mobility videos" and "Seeded 10 weeks of rotation"

Verify:
```sql
SELECT COUNT(*) FROM mobility_videos;  -- 21
SELECT week, slot, video_id FROM mobility_weekly_rotation ORDER BY week, slot;
```

- [ ] **Step 5: Commit**

```bash
git add data/knowledge/mobility_videos.json scripts/seed_mobility_videos.py
git commit -m "Add mobility video data: 21 videos in 10-week rotation, Supabase seed script"
```

---

### Task 4: Mobility Service (Backend Logic)

**Files:**
- Create: `bot/services/mobility.py`

- [ ] **Step 1: Create mobility.py service**

```python
# bot/services/mobility.py
"""Mobility video rotation service.

Returns today's mobility videos based on a 10-week cycling program.
Each week has 4 videos (3 P/R + 1 targeted). The program cycles
endlessly — week 11 = week 1, etc.
"""

import json
import logging
from datetime import date
from pathlib import Path

from bot.config import CHICAGO_TZ

logger = logging.getLogger(__name__)

DATA_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "knowledge" / "mobility_videos.json"

_MOBILITY_CACHE = None


def _load_mobility_data() -> dict:
    global _MOBILITY_CACHE
    if _MOBILITY_CACHE is None:
        with open(DATA_FILE) as f:
            _MOBILITY_CACHE = json.load(f)
        logger.info("Mobility videos loaded: %d videos, %d weeks",
                     len(_MOBILITY_CACHE["videos"]),
                     len(_MOBILITY_CACHE["weekly_rotation"]))
    return _MOBILITY_CACHE


def get_today_mobility(anchor_date: date | None = None) -> dict:
    """Return today's mobility video(s).

    The 10-week program cycles based on ISO week number:
        current_week = (iso_week % 10) + 1  (1-indexed, cycles 1-10)

    Returns:
        {
            "week": 3,
            "videos": [
                {"id": "mob_009", "title": "P/R Routine G", "youtube_url": "...", "type": "P/R"},
                ...
            ]
        }
    """
    data = _load_mobility_data()
    today = anchor_date or date.today()
    iso_week = today.isocalendar()[1]
    cycle_week = (iso_week % 10) + 1  # 1-10

    # Find the week's rotation
    week_data = None
    for w in data["weekly_rotation"]:
        if w["week"] == cycle_week:
            week_data = w
            break

    if not week_data:
        logger.warning("No mobility rotation found for cycle week %d", cycle_week)
        return {"week": cycle_week, "videos": []}

    # Resolve video IDs to full video objects
    video_map = {v["id"]: v for v in data["videos"]}
    videos = []
    for vid_id in week_data["slots"]:
        video = video_map.get(vid_id)
        if video:
            videos.append({
                "id": video["id"],
                "title": video["title"],
                "youtube_url": video["youtube_url"],
                "type": video["type"],
            })

    return {"week": cycle_week, "videos": videos}
```

- [ ] **Step 2: Verify it works**

Run: `cd pitcher_program_app && python3 -c "
from bot.services.mobility import get_today_mobility
result = get_today_mobility()
print(f'Week {result[\"week\"]}:')
for v in result['videos']:
    print(f'  [{v[\"type\"]}] {v[\"title\"]} - {v[\"youtube_url\"]}')
"`
Expected: Shows 4 mobility videos for the current week.

- [ ] **Step 3: Commit**

```bash
git add bot/services/mobility.py
git commit -m "Add mobility service: 10-week cycling video rotation"
```

---

### Task 5: API Endpoint for Mobility

**Files:**
- Modify: `api/routes.py`

- [ ] **Step 1: Add mobility endpoint to routes.py**

Add after the existing trend/progression endpoints:

```python
# --- Mobility ---

@router.get("/pitcher/{pitcher_id}/mobility-today")
async def get_mobility_today(pitcher_id: str, request: Request):
    """Return today's mobility videos from the 10-week rotation."""
    from bot.services.mobility import get_today_mobility
    return get_today_mobility()
```

Note: This endpoint doesn't need pitcher-specific logic yet (all pitchers get the same rotation). The pitcher_id is in the path for consistency and future personalization.

- [ ] **Step 2: Verify endpoint works**

Run: `cd pitcher_program_app && python3 -c "
import uvicorn
# Just verify import works
from api.routes import router
print('Routes loaded successfully')
"`

- [ ] **Step 3: Commit**

```bash
git add api/routes.py
git commit -m "Add GET /api/pitcher/{id}/mobility-today endpoint"
```

---

### Task 6: Add Mobility to Plan Generation Output

The plan generator should include a `mobility` key in its output so the daily entry has mobility data for the mini-app to display. The plan generator has **three** output paths (LLM success, LLM parse failure fallback, LLM timeout/error fallback) — all three need the key. Follow the same pattern as `warmup` which was just added in commit `9e899dc`.

**Files:**
- Modify: `bot/services/plan_generator.py`

- [ ] **Step 1: Read plan_generator.py fully to find the three output dicts**

Read: `bot/services/plan_generator.py` (full file)

Find the three places where the plan result dict is built — search for `"warmup": warmup_block` which appears in all three. The `mobility` key goes right next to it in each.

- [ ] **Step 2: Add mobility to the plan output**

Near the top of `generate_plan()`, after `warmup_block = _build_warmup_block(...)`, add:

```python
from bot.services.mobility import get_today_mobility

# Add mobility videos to plan
mobility_data = get_today_mobility()
```

Then add `"mobility": mobility_data,` next to each `"warmup": warmup_block,` line in all three output dicts.

- [ ] **Step 3: Commit**

```bash
git add bot/services/plan_generator.py
git commit -m "Include mobility videos in plan generation output"
```

---

### Task 7: MobilityCard Component + DailyCard Integration

**Important context:** As of commit `9e899dc`, DailyCard.jsx BLOCKS array is now `[warmup, arm_care, lifting, throwing]`. Mobility is NOT an exercise block — it's a video card. Do NOT add it to the BLOCKS array. Instead, render `<MobilityCard>` after the BLOCKS loop and notes, before the outing section. The `blockData` object (line ~64) now includes `warmup`. Add `mobility` there too.

**Files:**
- Create: `mini-app/src/components/MobilityCard.jsx`
- Modify: `mini-app/src/components/DailyCard.jsx:~64,~117`

- [ ] **Step 1: Create MobilityCard component**

```jsx
// mini-app/src/components/MobilityCard.jsx

export default function MobilityCard({ mobility }) {
  if (!mobility || !mobility.videos || mobility.videos.length === 0) return null;

  return (
    <div style={{ background: 'var(--color-white)', borderRadius: 12, overflow: 'hidden' }}>
      <div style={{ padding: '10px 14px', borderBottom: '0.5px solid var(--color-cream-border)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 14 }}>🧘</span>
          <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--color-ink-primary)' }}>Mobility</span>
          <span style={{ fontSize: 11, color: 'var(--color-ink-muted)' }}>— Week {mobility.week}</span>
        </div>
      </div>
      <div style={{ padding: '8px 14px', display: 'flex', flexDirection: 'column', gap: 6 }}>
        {mobility.videos.map((video, i) => (
          <a
            key={video.id || i}
            href={video.youtube_url}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: '8px 10px',
              borderRadius: 8,
              background: 'var(--color-cream-bg)',
              textDecoration: 'none',
              color: 'inherit',
            }}
          >
            <span style={{
              fontSize: 18,
              width: 32,
              height: 32,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              borderRadius: 8,
              background: 'var(--color-maroon)',
              color: 'white',
              flexShrink: 0,
            }}>
              ▶
            </span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-ink-primary)' }}>
                {video.title}
              </div>
              <div style={{ fontSize: 11, color: 'var(--color-ink-muted)' }}>
                {video.type}
              </div>
            </div>
          </a>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Integrate MobilityCard into DailyCard**

In `DailyCard.jsx`, add the import at the top (after the PostThrowFeel import):

```jsx
import MobilityCard from './MobilityCard';
```

In the `blockData` object (around line 64, right after the `warmup` line), add:

```jsx
const mobilityData = entry.mobility || plan_generated?.mobility;
```

In the JSX return (around line 117), after `{notes.length > 0 && <NotesBlock notes={notes} />}` and before the `{entry.outing && (` block, add:

```jsx
<MobilityCard mobility={mobilityData} />
```

This places mobility AFTER warmup/arm care/lifting/throwing/notes but BEFORE outing — "after everything" as requested.

- [ ] **Step 3: Verify the mini-app builds**

Run: `cd pitcher_program_app/mini-app && npm run build`
Expected: Build succeeds with no errors.

- [ ] **Step 4: Commit**

```bash
git add mini-app/src/components/MobilityCard.jsx mini-app/src/components/DailyCard.jsx
git commit -m "Add MobilityCard: clickable YouTube videos for daily mobility routine"
```

---

### Task 8: Fallback — Fetch Mobility Client-Side if Not in Plan

Plans generated before this change won't have a `mobility` key. The mini-app should fetch mobility data from the API as a fallback.

**Files:**
- Modify: `mini-app/src/pages/Home.jsx` (or wherever DailyCard gets its entry prop)
- Modify: `mini-app/src/components/DailyCard.jsx`

- [ ] **Step 1: Read Home.jsx to understand how entry data flows to DailyCard**

Read: `mini-app/src/pages/Home.jsx` — find where `<DailyCard>` is rendered and how `entry` is passed.

- [ ] **Step 2: Add mobility fetch fallback in DailyCard**

Add a `useEffect` in DailyCard that fetches `/api/pitcher/{id}/mobility-today` if `mobilityData` is null:

```jsx
import { useState, useCallback, useEffect } from 'react';

// Inside DailyCard component, after mobilityData declaration:
const [fetchedMobility, setFetchedMobility] = useState(null);

useEffect(() => {
  if (!mobilityData && pitcherId) {
    const apiBase = import.meta.env.VITE_API_URL || '';
    fetch(`${apiBase}/api/pitcher/${pitcherId}/mobility-today`)
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data) setFetchedMobility(data); })
      .catch(() => {});
  }
}, [mobilityData, pitcherId]);

const activeMobility = mobilityData || fetchedMobility;
```

Then use `activeMobility` in the MobilityCard:

```jsx
<MobilityCard mobility={activeMobility} />
```

- [ ] **Step 3: Verify build**

Run: `cd pitcher_program_app/mini-app && npm run build`
Expected: Clean build.

- [ ] **Step 4: Commit**

```bash
git add mini-app/src/components/DailyCard.jsx
git commit -m "Fallback: fetch mobility videos client-side if not in plan data"
```

---

### Task 9: Update CLAUDE.md

**Files:**
- Modify: `/Users/landonprojects/baseball/CLAUDE.md`

- [ ] **Step 1: Update exercise count and add mobility section**

In the "Phase 8" section or a new "Phase 9" entry, document:
- Exercise library expanded from 120 to ~155 exercises
- New categories effectively used: med ball/plyometric exercises added, arm isolation integrated as upper body accessories
- Explosive block added to every non-recovery lift session
- Mobility video system: 21 videos in 10-week rotation, `mobility_videos` + `mobility_weekly_rotation` Supabase tables
- MobilityCard component on daily plan page
- `GET /api/pitcher/{id}/mobility-today` endpoint

Update the Supabase schema table to include `mobility_videos` and `mobility_weekly_rotation`.

Update exercise count references (120 → ~155).

- [ ] **Step 2: Commit**

```bash
git add /Users/landonprojects/baseball/CLAUDE.md
git commit -m "Update CLAUDE.md: exercise enrichment + mobility video system"
```
