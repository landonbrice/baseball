"""Enrich the exercise library: backfill YouTube URLs on existing exercises
and add ~35 new exercises sourced from uchi_exercise_library.xlsx.

Usage:
    python -m scripts.enrich_exercises             # dry-run (prints changes)
    python -m scripts.enrich_exercises --apply     # writes exercise_library.json
    python -m scripts.enrich_exercises --supabase  # upserts to Supabase (requires env vars)
    python -m scripts.enrich_exercises --apply --supabase  # both
"""

import argparse
import json
import os
import sys

LIBRARY_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "knowledge", "exercise_library.json")

# ── YouTube URL backfills for existing exercises ──────────────────────────────
# Sourced from uchi_exercise_library.xlsx hyperlinks.
# Key = exercise id, value = url to apply if field is currently empty.
YOUTUBE_BACKFILLS = {
    "ex_003": "https://youtu.be/5S8SApGU_Lk?si=5ySdDtnje3end4bq",    # Barbell Hip Thrust
    "ex_004": "https://youtu.be/AGvR91bbHy8?si=a_K0I6mhT27xMPfo",    # Rear-Foot-Elevated Split Squat (Bulgarian)
    "ex_008": "https://youtu.be/qfpaNBDhidg?si=Oi50XxX_B_NNSTc_",    # DB Reverse Lunge
    "ex_009": "https://youtu.be/VTtLrBvHoJ8?si=oOQ22Fo0vW2guNaw",    # Landmine Lateral Lunge
    "ex_011": "https://youtube.com/shorts/6e0tp0_s5Zs?si=658yEaZvFhQMBH5d",  # Landmine RDL
    "ex_013": "https://youtube.com/shorts/ehxvDjvCwHw?si=MDY1NoYRLEhpdVKN",  # Nordic Hamstring Curl (partner)
    "ex_020": "https://youtube.com/shorts/DgyslsszCQ0?si=__F7SkQRGW-Ny0U1",  # Chest-Supported Row (Barbell Row match)
}

# ── New exercises ex_121 → ex_155 ─────────────────────────────────────────────
# Curated from uchi_exercise_library.xlsx sheets: Major Lifts, Accessory Lifts,
# Arms, Med Ball. ~35 entries with full schema.
NEW_EXERCISES = [
    # ── Major Lifts – Lower ───────────────────────────────────────────────────
    {
        "id": "ex_121",
        "name": "Back Squat",
        "slug": "ex_back_squat",
        "aliases": ["barbell back squat", "barbell squat"],
        "category": "lower_body_compound",
        "subcategory": "quad_dominant",
        "muscles_primary": ["quads", "glutes"],
        "muscles_secondary": ["hamstrings", "erector spinae", "core"],
        "pitching_relevance": "Foundational lower-body strength. Bilateral quad and glute loading builds the base for rotational power and stride force.",
        "prescription": {
            "strength": {"sets": "3-4", "reps": "4-6", "intensity": "80-85% 1RM", "rest_min": 3},
            "hypertrophy": {"sets": "3-4", "reps": "8-10", "intensity": "65-75% 1RM", "rest_min": 2},
            "power": {"sets": "4", "reps": "2-3", "intensity": "70% 1RM", "rest_min": 3, "note": "Compensatory acceleration — max intent on concentric"}
        },
        "rotation_day_usage": {
            "recommended": ["day_1", "day_4"],
            "acceptable": ["day_2"],
            "avoid": ["day_0", "day_5", "day_6"]
        },
        "tags": ["compound", "lower_body", "strength", "quad_dominant", "bilateral"],
        "contraindications": ["acute_knee_pain", "lumbar_disk_issues"],
        "modification_flags": {
            "ucl_history": "no_modification_needed",
            "shoulder_impingement": "monitor_bar_position_use_safety_bar",
            "low_back_history": "substitute_trap_bar_deadlift",
            "poor_hip_mobility": "use_box_squat_or_goblet_squat"
        },
        "youtube_url": "",
        "evidence_level": "strong",
        "source_notes": "UChicago exercise library (Major Lifts). Cressey prefers front squat for baseball but back squat acceptable for general strength."
    },
    {
        "id": "ex_122",
        "name": "Barbell Deadlift",
        "slug": "ex_barbell_deadlift",
        "aliases": ["conventional deadlift", "straight bar deadlift"],
        "category": "lower_body_compound",
        "subcategory": "hip_dominant",
        "muscles_primary": ["hamstrings", "glutes", "erector spinae"],
        "muscles_secondary": ["quads", "traps", "grip"],
        "pitching_relevance": "Posterior chain strength foundational to high-velocity pitching. Conventional bar increases spinal shear vs trap bar — use trap bar in-season.",
        "prescription": {
            "strength": {"sets": "3", "reps": "3-5", "intensity": "85% 1RM", "rest_min": 3},
            "hypertrophy": {"sets": "3", "reps": "6-8", "intensity": "70-75% 1RM", "rest_min": 2}
        },
        "rotation_day_usage": {
            "recommended": ["day_1", "day_4"],
            "acceptable": ["day_2"],
            "avoid": ["day_0", "day_5", "day_6"]
        },
        "tags": ["compound", "lower_body", "hip_dominant", "strength"],
        "contraindications": ["acute_low_back", "lumbar_disk_issues"],
        "modification_flags": {
            "ucl_history": "no_modification_needed",
            "shoulder_impingement": "no_modification_needed",
            "low_back_history": "substitute_trap_bar_deadlift",
            "poor_hip_mobility": "substitute_trap_bar_deadlift"
        },
        "youtube_url": "",
        "evidence_level": "strong",
        "source_notes": "UChicago exercise library (Major Lifts). Prefer trap bar variant in-season."
    },
    {
        "id": "ex_123",
        "name": "Trap Bar Squat",
        "slug": "ex_trap_bar_squat",
        "aliases": ["hex bar squat", "trap bar elevated squat"],
        "category": "lower_body_compound",
        "subcategory": "quad_dominant",
        "muscles_primary": ["quads", "glutes"],
        "muscles_secondary": ["hamstrings", "core"],
        "pitching_relevance": "More upright torso than conventional squat — loads quads and glutes with reduced spinal shear. Good in-season compound option.",
        "prescription": {
            "strength": {"sets": "3", "reps": "4-6", "intensity": "80% 1RM", "rest_min": 3},
            "hypertrophy": {"sets": "3", "reps": "8-10", "intensity": "65-75% 1RM", "rest_min": 2}
        },
        "rotation_day_usage": {
            "recommended": ["day_1", "day_4"],
            "acceptable": ["day_2"],
            "avoid": ["day_0", "day_5", "day_6"]
        },
        "tags": ["compound", "lower_body", "quad_dominant", "trap_bar"],
        "contraindications": [],
        "modification_flags": {
            "ucl_history": "no_modification_needed",
            "shoulder_impingement": "no_modification_needed",
            "low_back_history": "preferred_over_barbell_squat",
            "poor_hip_mobility": "elevate_handles"
        },
        "youtube_url": "",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library (Major Lifts)."
    },
    {
        "id": "ex_124",
        "name": "Trap Bar Squat Jumps",
        "slug": "ex_trap_bar_squat_jumps",
        "aliases": ["trap bar jump squat", "hex bar jump"],
        "category": "lower_body_power",
        "subcategory": "plyometric",
        "muscles_primary": ["quads", "glutes", "calves"],
        "muscles_secondary": ["hamstrings", "core"],
        "pitching_relevance": "Develops rate of force development — directly transfers to explosive drive off the mound. Lower spinal load than barbell jump squats.",
        "prescription": {
            "power": {"sets": "4", "reps": "3-5", "intensity": "20-40% 1RM trap bar DL", "rest_min": 3, "note": "Max intent on takeoff — land softly and reset between reps"}
        },
        "rotation_day_usage": {
            "recommended": ["day_2"],
            "acceptable": ["day_1"],
            "avoid": ["day_0", "day_5", "day_6"]
        },
        "tags": ["power", "plyometric", "lower_body", "velocity_development", "explosive"],
        "contraindications": ["knee_ligament_instability", "acute_ankle_sprain"],
        "modification_flags": {
            "ucl_history": "no_modification_needed",
            "shoulder_impingement": "no_modification_needed",
            "low_back_history": "reduce_load_or_substitute_broad_jump",
            "knee_history": "substitute_broad_jump"
        },
        "youtube_url": "https://youtu.be/-n2p5mQxYTw?si=YougfQuYz5Ra4tac",
        "evidence_level": "strong",
        "source_notes": "UChicago exercise library (Major Lifts). Driveline — ballistic lower body work for velocity development."
    },
    {
        "id": "ex_125",
        "name": "Barbell Reverse Lunge",
        "slug": "ex_barbell_reverse_lunge",
        "aliases": ["barbell step back lunge", "back lunge barbell"],
        "category": "lower_body_compound",
        "subcategory": "single_leg",
        "muscles_primary": ["quads", "glutes"],
        "muscles_secondary": ["hamstrings", "hip_stabilizers"],
        "pitching_relevance": "Unilateral hip stability and single-leg strength. Reverse lunge reduces anterior knee shear vs. forward lunge — better for pitchers with knee history.",
        "prescription": {
            "strength": {"sets": "3", "reps": "5-6/side", "intensity": "RPE 7-8", "rest_min": 2},
            "hypertrophy": {"sets": "3", "reps": "8-10/side", "intensity": "2-3 RIR", "rest_min": 1.5}
        },
        "rotation_day_usage": {
            "recommended": ["day_2", "day_4"],
            "acceptable": ["day_1"],
            "avoid": ["day_0", "day_5", "day_6"]
        },
        "tags": ["compound", "lower_body", "single_leg", "unilateral"],
        "contraindications": [],
        "modification_flags": {
            "ucl_history": "no_modification_needed",
            "shoulder_impingement": "no_modification_needed",
            "low_back_history": "use_goblet_hold_instead_of_barbell",
            "knee_history": "preferred_over_forward_lunge"
        },
        "youtube_url": "https://youtu.be/qfpaNBDhidg?si=Oi50XxX_B_NNSTc_",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library (Major Lifts)."
    },
    # ── Major Lifts – Upper ───────────────────────────────────────────────────
    {
        "id": "ex_126",
        "name": "Barbell Bench Press",
        "slug": "ex_barbell_bench_press",
        "aliases": ["bench press", "flat bench barbell"],
        "category": "upper_body_push",
        "subcategory": "horizontal_push",
        "muscles_primary": ["pectorals", "anterior deltoid", "triceps"],
        "muscles_secondary": ["serratus anterior", "core"],
        "pitching_relevance": "General upper-body pressing strength. Use sparingly in-season — prefer neutral-grip DB variants to reduce shoulder impingement risk. Off-season strength base builder.",
        "prescription": {
            "strength": {"sets": "3-4", "reps": "4-6", "intensity": "80-85% 1RM", "rest_min": 3},
            "hypertrophy": {"sets": "3-4", "reps": "8-10", "intensity": "65-75% 1RM", "rest_min": 2}
        },
        "rotation_day_usage": {
            "recommended": ["day_1", "day_3"],
            "acceptable": ["day_2"],
            "avoid": ["day_0", "day_5", "day_6"]
        },
        "tags": ["compound", "upper_body", "push", "horizontal", "bilateral"],
        "contraindications": ["shoulder_impingement_acute", "ac_joint_issues"],
        "modification_flags": {
            "ucl_history": "no_modification_needed",
            "shoulder_impingement": "substitute_neutral_grip_db_press",
            "labrum_history": "substitute_neutral_grip_db_press",
            "low_back_history": "no_modification_needed"
        },
        "youtube_url": "",
        "evidence_level": "strong",
        "source_notes": "UChicago exercise library (Major Lifts). Cressey: limit in-season; prefer DB/neutral-grip variants for shoulder health."
    },
    {
        "id": "ex_127",
        "name": "Incline Barbell Press",
        "slug": "ex_incline_barbell_press",
        "aliases": ["incline bench press", "incline barbell bench"],
        "category": "upper_body_push",
        "subcategory": "incline_push",
        "muscles_primary": ["upper pectorals", "anterior deltoid", "triceps"],
        "muscles_secondary": ["serratus anterior"],
        "pitching_relevance": "Upper chest and anterior delt strength. Lower shoulder stress at incline angle vs. flat. Useful off-season pressing variant.",
        "prescription": {
            "hypertrophy": {"sets": "3", "reps": "8-10", "intensity": "65-75% 1RM", "rest_min": 2},
            "strength": {"sets": "3", "reps": "5-6", "intensity": "75-80% 1RM", "rest_min": 2.5}
        },
        "rotation_day_usage": {
            "recommended": ["day_1", "day_3"],
            "acceptable": ["day_2"],
            "avoid": ["day_0", "day_5", "day_6"]
        },
        "tags": ["compound", "upper_body", "push", "incline"],
        "contraindications": ["shoulder_impingement_acute"],
        "modification_flags": {
            "ucl_history": "no_modification_needed",
            "shoulder_impingement": "substitute_incline_db_press_neutral_grip",
            "labrum_history": "substitute_incline_db_press_neutral_grip",
            "low_back_history": "no_modification_needed"
        },
        "youtube_url": "",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library (Major Lifts)."
    },
    {
        "id": "ex_128",
        "name": "Pull-Up",
        "slug": "ex_pull_up",
        "aliases": ["pull ups", "pullup", "bodyweight pull up"],
        "category": "upper_body_pull",
        "subcategory": "vertical_pull",
        "muscles_primary": ["latissimus dorsi", "biceps"],
        "muscles_secondary": ["lower traps", "rhomboids", "core"],
        "pitching_relevance": "Lat strength directly loads arm deceleration and scapular stability. Bodyweight pull-ups build relative strength without excessive load on shoulder structures.",
        "prescription": {
            "strength": {"sets": "3-4", "reps": "5-8", "intensity": "bodyweight or +10-20lb", "rest_min": 2},
            "hypertrophy": {"sets": "3", "reps": "8-12", "intensity": "bodyweight or band-assisted", "rest_min": 1.5},
            "endurance": {"sets": "2-3", "reps": "max", "intensity": "bodyweight", "rest_min": 1.5}
        },
        "rotation_day_usage": {
            "recommended": ["day_1", "day_3"],
            "acceptable": ["day_2", "day_4"],
            "avoid": ["day_0", "day_6"]
        },
        "tags": ["compound", "upper_body", "pull", "vertical", "lat", "bodyweight"],
        "contraindications": ["acute_shoulder_impingement", "labrum_acute_flare"],
        "modification_flags": {
            "ucl_history": "monitor_medial_elbow_stress",
            "shoulder_impingement": "reduce_range_or_substitute_lat_pulldown",
            "labrum_history": "use_band_assisted_or_lat_pulldown",
            "low_back_history": "no_modification_needed"
        },
        "youtube_url": "",
        "evidence_level": "strong",
        "source_notes": "UChicago exercise library (Major Lifts). Cressey staple for baseball lat development."
    },
    {
        "id": "ex_129",
        "name": "Lat Pulldown",
        "slug": "ex_lat_pulldown",
        "aliases": ["lat pull down", "cable lat pulldown", "wide grip pulldown"],
        "category": "upper_body_pull",
        "subcategory": "vertical_pull",
        "muscles_primary": ["latissimus dorsi", "biceps"],
        "muscles_secondary": ["lower traps", "rhomboids"],
        "pitching_relevance": "Lat loading with load control — good substitute for pull-ups when managing fatigue or shoulder flags. Adjustable load makes it useful across all rotation days.",
        "prescription": {
            "hypertrophy": {"sets": "3", "reps": "10-12", "intensity": "moderate load 2-3 RIR", "rest_min": 1.5},
            "endurance": {"sets": "2-3", "reps": "12-15", "intensity": "light-moderate", "rest_min": 1}
        },
        "rotation_day_usage": {
            "recommended": ["day_1", "day_3"],
            "acceptable": ["day_2", "day_4"],
            "avoid": ["day_0", "day_6"]
        },
        "tags": ["upper_body", "pull", "vertical", "lat", "cable"],
        "contraindications": [],
        "modification_flags": {
            "ucl_history": "no_modification_needed",
            "shoulder_impingement": "use_neutral_grip_attachment",
            "labrum_history": "use_neutral_grip_or_supinated_grip",
            "low_back_history": "no_modification_needed"
        },
        "youtube_url": "https://youtube.com/shorts/8d6d46pGdQM?si=n2vyYEvIEo7MnxBz",
        "evidence_level": "strong",
        "source_notes": "UChicago exercise library (Major Lifts, Accessory Lifts)."
    },
    {
        "id": "ex_130",
        "name": "Barbell Row",
        "slug": "ex_barbell_row",
        "aliases": ["bent over row barbell", "bent-over barbell row", "overhand barbell row"],
        "category": "upper_body_pull",
        "subcategory": "horizontal_pull",
        "muscles_primary": ["latissimus dorsi", "rhomboids", "lower traps"],
        "muscles_secondary": ["biceps", "erector spinae", "rear deltoid"],
        "pitching_relevance": "Horizontal pulling for scapular retractor strength — counterbalances pressing volume and supports arm deceleration.",
        "prescription": {
            "strength": {"sets": "3-4", "reps": "5-6", "intensity": "75-80% 1RM", "rest_min": 2.5},
            "hypertrophy": {"sets": "3", "reps": "8-10", "intensity": "65-70% 1RM", "rest_min": 2}
        },
        "rotation_day_usage": {
            "recommended": ["day_1", "day_3"],
            "acceptable": ["day_2"],
            "avoid": ["day_0", "day_5", "day_6"]
        },
        "tags": ["compound", "upper_body", "pull", "horizontal", "row"],
        "contraindications": ["acute_low_back"],
        "modification_flags": {
            "ucl_history": "no_modification_needed",
            "shoulder_impingement": "no_modification_needed",
            "low_back_history": "substitute_chest_supported_row",
            "labrum_history": "no_modification_needed"
        },
        "youtube_url": "https://youtube.com/shorts/DgyslsszCQ0?si=__F7SkQRGW-Ny0U1",
        "evidence_level": "strong",
        "source_notes": "UChicago exercise library (Major Lifts)."
    },
    {
        "id": "ex_131",
        "name": "Dumbbell Row",
        "slug": "ex_dumbbell_row",
        "aliases": ["DB row", "single arm dumbbell row", "one arm dumbbell row"],
        "category": "upper_body_pull",
        "subcategory": "horizontal_pull",
        "muscles_primary": ["latissimus dorsi", "rhomboids"],
        "muscles_secondary": ["biceps", "rear deltoid", "lower traps"],
        "pitching_relevance": "Unilateral horizontal pulling — addresses side-to-side lat imbalances common in pitchers. Chest-supported variation available for low back protection.",
        "prescription": {
            "hypertrophy": {"sets": "3", "reps": "10-12/side", "intensity": "2-3 RIR", "rest_min": 1.5},
            "strength": {"sets": "3", "reps": "6-8/side", "intensity": "RPE 7-8", "rest_min": 2}
        },
        "rotation_day_usage": {
            "recommended": ["day_1", "day_3"],
            "acceptable": ["day_2", "day_4"],
            "avoid": ["day_0", "day_6"]
        },
        "tags": ["upper_body", "pull", "horizontal", "unilateral", "dumbbell"],
        "contraindications": [],
        "modification_flags": {
            "ucl_history": "no_modification_needed",
            "shoulder_impingement": "no_modification_needed",
            "low_back_history": "use_chest_supported_or_incline_bench_support",
            "labrum_history": "no_modification_needed"
        },
        "youtube_url": "https://youtu.be/DMo3HJoawrU?si=RLJAKZCiDZbtLl3d",
        "evidence_level": "strong",
        "source_notes": "UChicago exercise library (Major Lifts)."
    },
    {
        "id": "ex_132",
        "name": "Pin Press",
        "slug": "ex_pin_press",
        "aliases": ["barbell pin press", "floor pin press"],
        "category": "upper_body_push",
        "subcategory": "horizontal_push",
        "muscles_primary": ["triceps", "pectorals"],
        "muscles_secondary": ["anterior deltoid"],
        "pitching_relevance": "Trains pressing from a dead stop — eliminates stretch-shortening cycle and overloads the sticking point. Useful for pitchers with UCL/elbow history to control ROM.",
        "prescription": {
            "strength": {"sets": "3-4", "reps": "3-5", "intensity": "80-85% 1RM", "rest_min": 3}
        },
        "rotation_day_usage": {
            "recommended": ["day_1", "day_3"],
            "acceptable": ["day_2"],
            "avoid": ["day_0", "day_5", "day_6"]
        },
        "tags": ["upper_body", "push", "tricep", "strength"],
        "contraindications": ["shoulder_impingement_acute"],
        "modification_flags": {
            "ucl_history": "set_pin_height_above_90_degree_elbow_flexion",
            "shoulder_impingement": "substitute_neutral_grip_db_floor_press",
            "low_back_history": "no_modification_needed"
        },
        "youtube_url": "https://youtu.be/9ntAEA4fsxc?si=enDS8xDKindoG-uz",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library (Major Lifts)."
    },
    # ── Accessory Lifts – Lower ───────────────────────────────────────────────
    {
        "id": "ex_133",
        "name": "Glute Ham Raise",
        "slug": "ex_glute_ham_raise",
        "aliases": ["GHR", "glute-ham raise"],
        "category": "lower_body_accessory",
        "subcategory": "hip_dominant",
        "muscles_primary": ["hamstrings", "glutes"],
        "muscles_secondary": ["calves", "erector spinae"],
        "pitching_relevance": "Eccentric hamstring strength — high injury prevention value. Hamstring strain is a top soft-tissue injury for pitchers. GHR develops active eccentric control through full ROM.",
        "prescription": {
            "strength": {"sets": "3", "reps": "4-6", "intensity": "bodyweight or +10-20lb", "rest_min": 2},
            "hypertrophy": {"sets": "3", "reps": "6-8", "intensity": "bodyweight", "rest_min": 1.5},
            "endurance": {"sets": "2-3", "reps": "8-12", "intensity": "bodyweight", "rest_min": 1}
        },
        "rotation_day_usage": {
            "recommended": ["day_1", "day_4"],
            "acceptable": ["day_2", "day_3"],
            "avoid": ["day_0", "day_5", "day_6"]
        },
        "tags": ["accessory", "lower_body", "hamstring", "eccentric", "injury_prevention"],
        "contraindications": ["acute_hamstring_strain"],
        "modification_flags": {
            "ucl_history": "no_modification_needed",
            "shoulder_impingement": "no_modification_needed",
            "low_back_history": "no_modification_needed",
            "hamstring_history": "reduce_depth_or_use_nordic_progression"
        },
        "youtube_url": "https://youtube.com/shorts/rjH934b6pVw?si=lMnmBtdS_9WhaxjJ",
        "evidence_level": "strong",
        "source_notes": "UChicago exercise library (Accessory Lifts). Hamstring injury prevention evidence from Driveline and Cressey."
    },
    {
        "id": "ex_134",
        "name": "Copenhagen Plank",
        "slug": "ex_copenhagen_plank",
        "aliases": ["copenhagen side plank", "adductor side plank"],
        "category": "core_stability",
        "subcategory": "lateral",
        "muscles_primary": ["adductors", "hip abductors", "lateral core"],
        "muscles_secondary": ["glutes", "obliques"],
        "pitching_relevance": "Adductor and groin strength — critical for pitchers who drive hard off the mound. Reduces groin/oblique strain risk in rotational athletes.",
        "prescription": {
            "endurance": {"sets": "3", "reps": "20-30s/side", "intensity": "bodyweight", "rest_min": 1},
            "strength": {"sets": "3", "reps": "8-10/side", "intensity": "slow tempo 3s hold at top", "rest_min": 1.5}
        },
        "rotation_day_usage": {
            "recommended": ["day_1", "day_3"],
            "acceptable": ["day_2", "day_4"],
            "avoid": ["day_0", "day_6"]
        },
        "tags": ["core", "lateral", "adductor", "injury_prevention", "stability"],
        "contraindications": ["active_groin_strain", "active_oblique_strain"],
        "modification_flags": {
            "ucl_history": "no_modification_needed",
            "oblique_strain": "avoid_until_cleared",
            "low_back_history": "no_modification_needed"
        },
        "youtube_url": "https://youtube.com/shorts/Rwap0_j5i5A?si=r9ty_AF95aeheQms",
        "evidence_level": "strong",
        "source_notes": "UChicago exercise library (Accessory Lifts). High evidence for groin injury prevention in kicking/throwing athletes."
    },
    {
        "id": "ex_135",
        "name": "Swiss Ball Hamstring Curl",
        "slug": "ex_swiss_ball_hamstring_curl",
        "aliases": ["stability ball hamstring curl", "physio ball leg curl"],
        "category": "lower_body_accessory",
        "subcategory": "hip_dominant",
        "muscles_primary": ["hamstrings"],
        "muscles_secondary": ["glutes", "core"],
        "pitching_relevance": "Eccentric hamstring loading with hip extension component — bridges gap between isolated curl and GHR. No equipment barrier; useful when GHR machine unavailable.",
        "prescription": {
            "endurance": {"sets": "3", "reps": "10-15", "intensity": "bodyweight", "rest_min": 1},
            "hypertrophy": {"sets": "3", "reps": "8-12", "intensity": "slow eccentric 3s", "rest_min": 1.5}
        },
        "rotation_day_usage": {
            "recommended": ["day_2", "day_4"],
            "acceptable": ["day_1", "day_3"],
            "avoid": ["day_0", "day_6"]
        },
        "tags": ["accessory", "lower_body", "hamstring", "eccentric", "stability"],
        "contraindications": ["acute_hamstring_strain"],
        "modification_flags": {
            "ucl_history": "no_modification_needed",
            "shoulder_impingement": "no_modification_needed",
            "low_back_history": "no_modification_needed",
            "hamstring_history": "reduce_range_or_do_isometric_holds"
        },
        "youtube_url": "https://youtube.com/shorts/xB1lGVzRwWk?si=HdN_lD20vlePOLuG",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library (Accessory Lifts)."
    },
    {
        "id": "ex_136",
        "name": "Heel Elevated Goblet Squat",
        "slug": "ex_heel_elevated_goblet_squat",
        "aliases": ["heel raised goblet squat", "goblet squat heel raise"],
        "category": "lower_body_compound",
        "subcategory": "quad_dominant",
        "muscles_primary": ["quads", "glutes"],
        "muscles_secondary": ["core", "hip flexors"],
        "pitching_relevance": "Heel elevation increases quad loading and reduces ankle dorsiflexion demand — good for pitchers with limited ankle mobility. Anterior chain strength for front-foot landing.",
        "prescription": {
            "hypertrophy": {"sets": "3", "reps": "10-12", "intensity": "moderate KB/DB", "rest_min": 1.5},
            "endurance": {"sets": "2-3", "reps": "12-15", "intensity": "light-moderate", "rest_min": 1}
        },
        "rotation_day_usage": {
            "recommended": ["day_2", "day_4"],
            "acceptable": ["day_1", "day_3"],
            "avoid": ["day_0", "day_6"]
        },
        "tags": ["lower_body", "quad_dominant", "accessory", "goblet"],
        "contraindications": [],
        "modification_flags": {
            "ucl_history": "no_modification_needed",
            "shoulder_impingement": "no_modification_needed",
            "low_back_history": "preferred_over_barbell_squat",
            "knee_history": "monitor_knee_tracking"
        },
        "youtube_url": "https://youtu.be/3dLIa1YljLs?si=tuLL9R6qbQkmhgLG",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library (Accessory Lifts)."
    },
    {
        "id": "ex_137",
        "name": "Dumbbell Walking Lunge",
        "slug": "ex_dumbbell_walking_lunge",
        "aliases": ["walking lunges", "DB walking lunge", "dumbbell lunges"],
        "category": "lower_body_compound",
        "subcategory": "single_leg",
        "muscles_primary": ["quads", "glutes"],
        "muscles_secondary": ["hamstrings", "hip_stabilizers", "adductors"],
        "pitching_relevance": "Dynamic single-leg loading with hip and knee stability demand. Builds stride-leg eccentric strength and drive-leg push-off power.",
        "prescription": {
            "hypertrophy": {"sets": "3", "reps": "10-12/side", "intensity": "moderate DBs 2-3 RIR", "rest_min": 1.5},
            "endurance": {"sets": "2-3", "reps": "12-15/side", "intensity": "light DBs", "rest_min": 1}
        },
        "rotation_day_usage": {
            "recommended": ["day_2", "day_4"],
            "acceptable": ["day_1"],
            "avoid": ["day_0", "day_5", "day_6"]
        },
        "tags": ["lower_body", "single_leg", "dynamic", "accessory"],
        "contraindications": ["knee_ligament_instability_acute"],
        "modification_flags": {
            "ucl_history": "no_modification_needed",
            "shoulder_impingement": "no_modification_needed",
            "low_back_history": "no_modification_needed",
            "knee_history": "substitute_reverse_lunge"
        },
        "youtube_url": "",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library (Accessory Lifts)."
    },
    # ── Accessory Lifts – Upper ───────────────────────────────────────────────
    {
        "id": "ex_138",
        "name": "Tricep Pushdown",
        "slug": "ex_tricep_pushdown",
        "aliases": ["cable tricep pulldown", "tricep pull down", "rope pushdown", "straight bar pushdown"],
        "category": "upper_body_accessory",
        "subcategory": "elbow_extension",
        "muscles_primary": ["triceps"],
        "muscles_secondary": ["anconeus"],
        "pitching_relevance": "Tricep hypertrophy and elbow extension strength — important for arm deceleration and elbow stability. Low joint stress compared to free-weight skull crushers.",
        "prescription": {
            "hypertrophy": {"sets": "3", "reps": "12-15", "intensity": "moderate load 2-3 RIR", "rest_min": 1},
            "endurance": {"sets": "2-3", "reps": "15-20", "intensity": "light pump work", "rest_min": 1}
        },
        "rotation_day_usage": {
            "recommended": ["day_1", "day_3"],
            "acceptable": ["day_2"],
            "avoid": ["day_0", "day_5", "day_6"]
        },
        "tags": ["accessory", "upper_body", "tricep", "cable", "elbow"],
        "contraindications": [],
        "modification_flags": {
            "ucl_history": "avoid_if_medial_elbow_pain_present",
            "shoulder_impingement": "no_modification_needed",
            "low_back_history": "no_modification_needed"
        },
        "youtube_url": "https://youtube.com/shorts/6Dh8sD6aNQE?si=9Bf2FWJSXmVHFLPv",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library (Accessory Lifts). Rope pushdown URL from xlsx."
    },
    {
        "id": "ex_139",
        "name": "Straight Arm Pulldown",
        "slug": "ex_straight_arm_pulldown",
        "aliases": ["cable straight arm pulldown", "straight arm lat pulldown"],
        "category": "upper_body_pull",
        "subcategory": "lat_isolation",
        "muscles_primary": ["latissimus dorsi"],
        "muscles_secondary": ["teres major", "posterior deltoid"],
        "pitching_relevance": "Lat isolation with minimal bicep involvement — reinforces arm deceleration musculature. Elbow stays extended, reducing UCL stress.",
        "prescription": {
            "hypertrophy": {"sets": "3", "reps": "12-15", "intensity": "moderate load", "rest_min": 1},
            "endurance": {"sets": "2-3", "reps": "15-20", "intensity": "light", "rest_min": 1}
        },
        "rotation_day_usage": {
            "recommended": ["day_1", "day_3"],
            "acceptable": ["day_2", "day_4"],
            "avoid": ["day_0", "day_6"]
        },
        "tags": ["accessory", "upper_body", "pull", "lat", "cable"],
        "contraindications": [],
        "modification_flags": {
            "ucl_history": "preferred_low_elbow_stress_lat_exercise",
            "shoulder_impingement": "no_modification_needed",
            "low_back_history": "no_modification_needed"
        },
        "youtube_url": "https://youtube.com/shorts/K9Tgn6sO3J0?si=eZdcOMGn6X9pvMiF",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library (Accessory Lifts)."
    },
    {
        "id": "ex_140",
        "name": "Dumbbell Lateral Raise",
        "slug": "ex_dumbbell_lateral_raise",
        "aliases": ["lateral raise", "DB lateral raise", "side raise"],
        "category": "upper_body_accessory",
        "subcategory": "shoulder_isolation",
        "muscles_primary": ["medial deltoid"],
        "muscles_secondary": ["upper traps", "supraspinatus"],
        "pitching_relevance": "Medial deltoid development for shoulder cap stability. Keep loads light and range controlled for pitchers — avoid above shoulder height with impingement history.",
        "prescription": {
            "hypertrophy": {"sets": "3", "reps": "12-15", "intensity": "light-moderate DBs", "rest_min": 1},
            "endurance": {"sets": "2-3", "reps": "15-20", "intensity": "very light", "rest_min": 1}
        },
        "rotation_day_usage": {
            "recommended": ["day_1", "day_3"],
            "acceptable": ["day_2"],
            "avoid": ["day_0", "day_5", "day_6"]
        },
        "tags": ["accessory", "upper_body", "shoulder", "deltoid", "isolation"],
        "contraindications": ["supraspinatus_tear_active"],
        "modification_flags": {
            "ucl_history": "no_modification_needed",
            "shoulder_impingement": "limit_to_90_degrees_or_substitute_cable_variation",
            "labrum_history": "use_cable_lateral_raise_for_more_control"
        },
        "youtube_url": "https://youtube.com/shorts/JIhbYYA1Q90?si=5PGEVX-_sja4TszD",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library (Accessory Lifts)."
    },
    {
        "id": "ex_141",
        "name": "Dumbbell Reverse Fly",
        "slug": "ex_dumbbell_reverse_fly",
        "aliases": ["DB reverse fly", "rear delt fly", "bent over reverse fly"],
        "category": "upper_body_accessory",
        "subcategory": "rear_delt",
        "muscles_primary": ["posterior deltoid", "rhomboids"],
        "muscles_secondary": ["lower traps", "infraspinatus"],
        "pitching_relevance": "Rear deltoid and scapular retractor strength — directly counteracts the heavy anterior shoulder use in throwing. Reduces impingement risk when done consistently.",
        "prescription": {
            "hypertrophy": {"sets": "3", "reps": "12-15", "intensity": "light DBs", "rest_min": 1},
            "endurance": {"sets": "3", "reps": "15-20", "intensity": "very light", "rest_min": 1}
        },
        "rotation_day_usage": {
            "recommended": ["day_1", "day_3"],
            "acceptable": ["day_2", "day_4"],
            "avoid": ["day_0", "day_6"]
        },
        "tags": ["accessory", "upper_body", "rear_delt", "scapular", "shoulder_health"],
        "contraindications": [],
        "modification_flags": {
            "ucl_history": "no_modification_needed",
            "shoulder_impingement": "good_exercise_for_posterior_shoulder_health",
            "labrum_history": "monitor_shoulder_position"
        },
        "youtube_url": "https://youtube.com/shorts/4eSyt7pEK8Q?si=IjFQ-RE630PENVNd",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library (Accessory Lifts)."
    },
    {
        "id": "ex_142",
        "name": "Skull Crusher",
        "slug": "ex_skull_crusher",
        "aliases": ["skull crushers", "EZ bar skull crusher", "lying tricep extension", "lying DB skull crusher"],
        "category": "upper_body_accessory",
        "subcategory": "elbow_extension",
        "muscles_primary": ["triceps"],
        "muscles_secondary": [],
        "pitching_relevance": "Tricep mass and elbow extension strength. Monitor medial elbow stress for pitchers with UCL history — may substitute cable pushdown.",
        "prescription": {
            "hypertrophy": {"sets": "3", "reps": "10-12", "intensity": "moderate load 2-3 RIR", "rest_min": 1.5}
        },
        "rotation_day_usage": {
            "recommended": ["day_1", "day_3"],
            "acceptable": ["day_2"],
            "avoid": ["day_0", "day_5", "day_6"]
        },
        "tags": ["accessory", "upper_body", "tricep", "isolation"],
        "contraindications": ["medial_elbow_pain_active"],
        "modification_flags": {
            "ucl_history": "substitute_cable_pushdown_or_reduce_load",
            "shoulder_impingement": "no_modification_needed",
            "low_back_history": "no_modification_needed"
        },
        "youtube_url": "https://youtube.com/shorts/zR9gty7LUxE?si=gP7tr-m2e_m6pEf9",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library (Accessory Lifts)."
    },
    {
        "id": "ex_143",
        "name": "Hanging Leg Raise",
        "slug": "ex_hanging_leg_raise",
        "aliases": ["hanging leg raises", "hanging knee raise"],
        "category": "core_stability",
        "subcategory": "anterior",
        "muscles_primary": ["hip flexors", "lower abs"],
        "muscles_secondary": ["upper abs", "grip", "lat"],
        "pitching_relevance": "Hip flexor and anterior core strength — critical for leg lift mechanics and maintaining posture through delivery. Lat loading during hang also beneficial.",
        "prescription": {
            "hypertrophy": {"sets": "3", "reps": "10-15", "intensity": "bodyweight", "rest_min": 1},
            "endurance": {"sets": "2-3", "reps": "15-20", "intensity": "bodyweight", "rest_min": 1}
        },
        "rotation_day_usage": {
            "recommended": ["day_1", "day_3"],
            "acceptable": ["day_2", "day_4"],
            "avoid": ["day_0", "day_6"]
        },
        "tags": ["core", "anterior", "hip_flexor", "bodyweight"],
        "contraindications": ["active_hip_flexor_strain"],
        "modification_flags": {
            "ucl_history": "monitor_grip_pressure_on_medial_elbow",
            "shoulder_impingement": "substitute_decline_situp_or_ab_wheel",
            "labrum_history": "substitute_decline_situp_or_cable_crunch",
            "low_back_history": "start_with_knee_raise_variant"
        },
        "youtube_url": "https://youtube.com/shorts/2n4UqRIJyk4?si=C04Pt4dlu0fJqtlm",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library (Accessory Lifts)."
    },
    {
        "id": "ex_144",
        "name": "Kneeling Landmine Press",
        "slug": "ex_kneeling_landmine_press",
        "aliases": ["landmine press", "half kneeling landmine press"],
        "category": "upper_body_push",
        "subcategory": "overhead_push",
        "muscles_primary": ["anterior deltoid", "upper pectorals", "triceps"],
        "muscles_secondary": ["serratus anterior", "core", "glutes"],
        "pitching_relevance": "Shoulder-friendly overhead press variant — neutral-to-internal grip path reduces impingement risk. Half-kneeling position demands hip-to-core stability that transfers to pitching delivery.",
        "prescription": {
            "hypertrophy": {"sets": "3", "reps": "10-12/side", "intensity": "moderate load", "rest_min": 1.5},
            "strength": {"sets": "3", "reps": "6-8/side", "intensity": "RPE 7", "rest_min": 2}
        },
        "rotation_day_usage": {
            "recommended": ["day_1", "day_3"],
            "acceptable": ["day_2"],
            "avoid": ["day_0", "day_5", "day_6"]
        },
        "tags": ["upper_body", "push", "overhead", "unilateral", "shoulder_friendly"],
        "contraindications": [],
        "modification_flags": {
            "ucl_history": "no_modification_needed",
            "shoulder_impingement": "preferred_overhead_press_option",
            "labrum_history": "monitor_end_range_overhead_position",
            "low_back_history": "kneeling_position_reduces_lumbar_extension"
        },
        "youtube_url": "https://youtube.com/shorts/wUFMBUX5L0M?si=M_ItZjoen_kOQlgm",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library (Accessory Lifts). Cressey recommends landmine press for overhead-compromised pitchers."
    },
    {
        "id": "ex_145",
        "name": "Plyometric Push-Up",
        "slug": "ex_plyometric_pushup",
        "aliases": ["plyo pushups", "explosive push up", "clap push up"],
        "category": "upper_body_power",
        "subcategory": "horizontal_push",
        "muscles_primary": ["pectorals", "triceps", "anterior deltoid"],
        "muscles_secondary": ["serratus anterior", "core"],
        "pitching_relevance": "Upper-body rate of force development — elastic push-off speed transfers to arm acceleration. Low load makes it safe for in-season power maintenance.",
        "prescription": {
            "power": {"sets": "3-4", "reps": "5-8", "intensity": "bodyweight max intent", "rest_min": 2, "note": "Full takeoff — hands leave ground each rep"}
        },
        "rotation_day_usage": {
            "recommended": ["day_2"],
            "acceptable": ["day_1"],
            "avoid": ["day_0", "day_5", "day_6"]
        },
        "tags": ["power", "plyometric", "upper_body", "push", "explosive", "velocity_development"],
        "contraindications": ["acute_wrist_pain", "shoulder_instability_active"],
        "modification_flags": {
            "ucl_history": "monitor_wrist_extension_stress",
            "shoulder_impingement": "substitute_medicine_ball_chest_pass",
            "labrum_history": "substitute_medicine_ball_chest_pass"
        },
        "youtube_url": "https://youtube.com/shorts/n-HUnTmCTys?si=edpEdIT5PpE82DZu",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library (Accessory Lifts)."
    },
    {
        "id": "ex_146",
        "name": "Weighted I-T-Y",
        "slug": "ex_weighted_ity",
        "aliases": ["weighted I/T/Ys", "dumbbell ITY", "DB I-T-Y", "prone ITY"],
        "category": "upper_body_accessory",
        "subcategory": "scapular",
        "muscles_primary": ["lower traps", "middle traps", "rhomboids"],
        "muscles_secondary": ["posterior deltoid", "serratus anterior"],
        "pitching_relevance": "Scapular upward rotation and lower trap strength — directly supports arm health and reduces impingement risk. Essential for pitchers with scap/shoulder issues.",
        "prescription": {
            "endurance": {"sets": "3", "reps": "10-12 each position", "intensity": "very light DBs 2-5lb", "rest_min": 1}
        },
        "rotation_day_usage": {
            "recommended": ["day_1", "day_3"],
            "acceptable": ["day_2", "day_4"],
            "avoid": ["day_0", "day_6"]
        },
        "tags": ["accessory", "scapular", "shoulder_health", "lower_trap", "arm_care"],
        "contraindications": [],
        "modification_flags": {
            "ucl_history": "no_modification_needed",
            "shoulder_impingement": "excellent_exercise_keep_loads_very_light",
            "labrum_history": "use_very_light_loads_monitor_pain"
        },
        "youtube_url": "https://youtube.com/shorts/_XJksTY6enk?si=iNWXqJKO2bOukGx_",
        "evidence_level": "strong",
        "source_notes": "UChicago exercise library (Accessory Lifts). Cressey and Driveline standard scapular health protocol."
    },
    # ── Arms (isolation) ──────────────────────────────────────────────────────
    {
        "id": "ex_147",
        "name": "EZ Bar Curl",
        "slug": "ex_ez_bar_curl",
        "aliases": ["EZ bar bicep curl", "cambered bar curl"],
        "category": "upper_body_accessory",
        "subcategory": "elbow_flexion",
        "muscles_primary": ["biceps brachii"],
        "muscles_secondary": ["brachialis", "brachioradialis"],
        "pitching_relevance": "Bicep hypertrophy for elbow flexion strength and forearm stability. EZ bar reduces wrist/elbow stress vs. straight bar — preferred for pitchers with elbow history.",
        "prescription": {
            "hypertrophy": {"sets": "3", "reps": "10-12", "intensity": "moderate 2-3 RIR", "rest_min": 1}
        },
        "rotation_day_usage": {
            "recommended": ["day_1", "day_3"],
            "acceptable": ["day_2"],
            "avoid": ["day_0", "day_5", "day_6"]
        },
        "tags": ["accessory", "bicep", "elbow", "isolation"],
        "contraindications": ["medial_elbow_pain_active"],
        "modification_flags": {
            "ucl_history": "use_supinated_grip_minimize_pronation_force",
            "shoulder_impingement": "no_modification_needed",
            "flexor_pronator_strain": "reduce_load_avoid_if_acute"
        },
        "youtube_url": "https://youtube.com/shorts/pT-wvBPSMZU?si=8ED5058ZYjyuZtQ1",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library (Arms)."
    },
    {
        "id": "ex_148",
        "name": "Overhead Tricep Extension",
        "slug": "ex_overhead_tricep_extension",
        "aliases": ["seated overhead DB tricep extension", "seated overhead DB tri ext", "overhead cable tricep ext"],
        "category": "upper_body_accessory",
        "subcategory": "elbow_extension",
        "muscles_primary": ["triceps long head"],
        "muscles_secondary": ["triceps lateral head"],
        "pitching_relevance": "Long head of tricep is stressed in overhead position — important for arm deceleration. Overhead loading stretches the long head for full eccentric development.",
        "prescription": {
            "hypertrophy": {"sets": "3", "reps": "10-12", "intensity": "moderate 2-3 RIR", "rest_min": 1}
        },
        "rotation_day_usage": {
            "recommended": ["day_1", "day_3"],
            "acceptable": ["day_2"],
            "avoid": ["day_0", "day_5", "day_6"]
        },
        "tags": ["accessory", "tricep", "overhead", "long_head", "isolation"],
        "contraindications": ["shoulder_impingement_acute", "medial_elbow_pain_active"],
        "modification_flags": {
            "ucl_history": "reduce_load_monitor_medial_elbow",
            "shoulder_impingement": "substitute_tricep_pushdown",
            "labrum_history": "substitute_tricep_pushdown_if_overhead_painful"
        },
        "youtube_url": "https://youtube.com/shorts/b_r_LW4HEcM?si=92GFsPDhFW6HuRKH",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library (Arms)."
    },
    {
        "id": "ex_149",
        "name": "Reverse Curl",
        "slug": "ex_reverse_curl",
        "aliases": ["pronated grip EZ bar reverse curl", "overhand EZ bar curl", "reverse barbell curl"],
        "category": "upper_body_accessory",
        "subcategory": "elbow_flexion",
        "muscles_primary": ["brachioradialis", "brachialis"],
        "muscles_secondary": ["biceps", "wrist extensors"],
        "pitching_relevance": "Brachioradialis and wrist extensor strength — supports forearm resilience and reduces medial elbow stress. Relevant for pitchers with UCL or flexor-pronator history.",
        "prescription": {
            "hypertrophy": {"sets": "3", "reps": "12-15", "intensity": "light-moderate load", "rest_min": 1}
        },
        "rotation_day_usage": {
            "recommended": ["day_1", "day_3"],
            "acceptable": ["day_2", "day_4"],
            "avoid": ["day_0", "day_6"]
        },
        "tags": ["accessory", "forearm", "elbow", "wrist_extensor", "arm_care"],
        "contraindications": [],
        "modification_flags": {
            "ucl_history": "excellent_supportive_exercise",
            "flexor_pronator_strain": "reduce_load_if_acute",
            "shoulder_impingement": "no_modification_needed"
        },
        "youtube_url": "https://youtube.com/shorts/MOEMvgYzNZQ?si=97JQe9yjN8JWvQbJ",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library (Arms)."
    },
    {
        "id": "ex_150",
        "name": "Cable Lateral Raise",
        "slug": "ex_cable_lateral_raise",
        "aliases": ["cable side raise", "single arm cable lateral raise"],
        "category": "upper_body_accessory",
        "subcategory": "shoulder_isolation",
        "muscles_primary": ["medial deltoid"],
        "muscles_secondary": ["supraspinatus", "upper traps"],
        "pitching_relevance": "Medial delt isolation with constant cable tension — better resistance curve than DB for shoulder stability work. Good accessory for pitchers needing shoulder balance.",
        "prescription": {
            "hypertrophy": {"sets": "3", "reps": "12-15", "intensity": "light load", "rest_min": 1},
            "endurance": {"sets": "2-3", "reps": "15-20", "intensity": "very light", "rest_min": 1}
        },
        "rotation_day_usage": {
            "recommended": ["day_1", "day_3"],
            "acceptable": ["day_2", "day_4"],
            "avoid": ["day_0", "day_6"]
        },
        "tags": ["accessory", "shoulder", "deltoid", "cable", "isolation"],
        "contraindications": ["supraspinatus_tear_active"],
        "modification_flags": {
            "ucl_history": "no_modification_needed",
            "shoulder_impingement": "limit_to_90_degrees_or_below",
            "labrum_history": "keep_loads_very_light"
        },
        "youtube_url": "https://youtube.com/shorts/0N6-ichlpxg?si=Rx1hH4lwtM6DrnTm",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library (Arms)."
    },
    # ── Med Ball ──────────────────────────────────────────────────────────────
    {
        "id": "ex_151",
        "name": "Med Ball Rotational Slam",
        "slug": "ex_med_ball_rotational_slam",
        "aliases": ["rotational slam", "rotational med ball slam", "rotational overhead slam"],
        "category": "med_ball",
        "subcategory": "rotational_power",
        "muscles_primary": ["obliques", "glutes", "lats"],
        "muscles_secondary": ["shoulders", "hip flexors", "thoracic extensors"],
        "pitching_relevance": "Directly trains rotational power in the pitching plane — hip-to-shoulder separation and deceleration loading. One of the most transfer-specific exercises for velocity.",
        "prescription": {
            "power": {"sets": "4", "reps": "5-8", "intensity": "6-10lb med ball max intent", "rest_min": 2}
        },
        "rotation_day_usage": {
            "recommended": ["day_2"],
            "acceptable": ["day_1"],
            "avoid": ["day_0", "day_5", "day_6"]
        },
        "tags": ["med_ball", "power", "rotational", "velocity_development", "explosive"],
        "contraindications": ["active_oblique_strain"],
        "modification_flags": {
            "ucl_history": "no_modification_needed",
            "oblique_strain": "avoid_until_cleared",
            "shoulder_impingement": "monitor_overhead_position",
            "low_back_history": "reduce_slam_height_or_substitute_chest_pass"
        },
        "youtube_url": "https://youtube.com/shorts/8ReGsLOc-lo?si=RSohtvSpwJOsXvxK",
        "evidence_level": "strong",
        "source_notes": "UChicago exercise library (Med Ball). Driveline med ball protocols."
    },
    {
        "id": "ex_152",
        "name": "Med Ball Slam",
        "slug": "ex_med_ball_slam",
        "aliases": ["slam", "overhead slam", "med ball overhead slam"],
        "category": "med_ball",
        "subcategory": "vertical_power",
        "muscles_primary": ["lats", "abs", "glutes"],
        "muscles_secondary": ["shoulders", "triceps"],
        "pitching_relevance": "Total body power in vertical plane — lat and core co-contraction with trunk flexion. Trains the deceleration musculature. Good warm-up explosive option.",
        "prescription": {
            "power": {"sets": "3-4", "reps": "6-8", "intensity": "8-14lb med ball", "rest_min": 1.5}
        },
        "rotation_day_usage": {
            "recommended": ["day_2"],
            "acceptable": ["day_1", "day_3"],
            "avoid": ["day_0", "day_6"]
        },
        "tags": ["med_ball", "power", "vertical", "explosive", "total_body"],
        "contraindications": ["active_oblique_strain", "shoulder_impingement_acute"],
        "modification_flags": {
            "ucl_history": "no_modification_needed",
            "oblique_strain": "avoid_or_reduce_to_chest_height_only",
            "shoulder_impingement": "substitute_rotational_chest_pass"
        },
        "youtube_url": "https://youtube.com/shorts/99DLQtHP7jE?si=cY-37LkfrMxuEi3U",
        "evidence_level": "strong",
        "source_notes": "UChicago exercise library (Med Ball)."
    },
    {
        "id": "ex_153",
        "name": "Med Ball Split Stance Throw",
        "slug": "ex_med_ball_split_stance_throw",
        "aliases": ["split stance throw", "split stance med ball throw", "med ball split stance"],
        "category": "med_ball",
        "subcategory": "rotational_power",
        "muscles_primary": ["obliques", "glutes", "hip rotators"],
        "muscles_secondary": ["lats", "anterior core", "shoulders"],
        "pitching_relevance": "Rotational power from a split stance mimics the pitching position — trains hip-to-shoulder kinetic chain in a mechanically relevant position.",
        "prescription": {
            "power": {"sets": "4", "reps": "5-6/side", "intensity": "6-10lb max intent", "rest_min": 2}
        },
        "rotation_day_usage": {
            "recommended": ["day_2"],
            "acceptable": ["day_1"],
            "avoid": ["day_0", "day_5", "day_6"]
        },
        "tags": ["med_ball", "power", "rotational", "velocity_development", "split_stance"],
        "contraindications": ["active_oblique_strain"],
        "modification_flags": {
            "ucl_history": "no_modification_needed",
            "oblique_strain": "avoid_until_cleared",
            "shoulder_impingement": "monitor_follow_through_position"
        },
        "youtube_url": "https://youtube.com/shorts/3Zfy4W1o4y0?si=n9sqNySSjOivI9Hh",
        "evidence_level": "strong",
        "source_notes": "UChicago exercise library (Med Ball). Driveline split stance series."
    },
    {
        "id": "ex_154",
        "name": "Med Ball Half Kneeling Rotational Throw",
        "slug": "ex_med_ball_half_kneeling_rotational_throw",
        "aliases": ["half kneeling rotational throw", "half kneeling med ball throw"],
        "category": "med_ball",
        "subcategory": "rotational_power",
        "muscles_primary": ["obliques", "hip flexors", "glutes"],
        "muscles_secondary": ["lats", "anterior core"],
        "pitching_relevance": "Rotational power with a fixed lower body — isolates trunk rotation and hip-shoulder separation. Good for isolating rotational deficits.",
        "prescription": {
            "power": {"sets": "3-4", "reps": "6-8/side", "intensity": "6-8lb", "rest_min": 1.5}
        },
        "rotation_day_usage": {
            "recommended": ["day_2"],
            "acceptable": ["day_1", "day_3"],
            "avoid": ["day_0", "day_5", "day_6"]
        },
        "tags": ["med_ball", "power", "rotational", "kneeling", "velocity_development"],
        "contraindications": ["active_oblique_strain"],
        "modification_flags": {
            "ucl_history": "no_modification_needed",
            "oblique_strain": "avoid_until_cleared",
            "shoulder_impingement": "monitor_follow_through"
        },
        "youtube_url": "https://youtu.be/c9C4uUF39hE?si=D4H9bAnvEImlayht",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library (Med Ball)."
    },
    {
        "id": "ex_155",
        "name": "Med Ball Back Facing Rotational Throw",
        "slug": "ex_med_ball_back_facing_rotational_throw",
        "aliases": ["back facing rotational throw", "reverse rotational throw", "backward rotational slam"],
        "category": "med_ball",
        "subcategory": "rotational_power",
        "muscles_primary": ["obliques", "glutes", "hip extensors"],
        "muscles_secondary": ["lats", "hamstrings"],
        "pitching_relevance": "Reactive hip extension and rotation starting from a counter-rotation position — trains the elastic energy storage and release of the pitching motion.",
        "prescription": {
            "power": {"sets": "4", "reps": "5-6/side", "intensity": "8-12lb max intent", "rest_min": 2}
        },
        "rotation_day_usage": {
            "recommended": ["day_2"],
            "acceptable": ["day_1"],
            "avoid": ["day_0", "day_5", "day_6"]
        },
        "tags": ["med_ball", "power", "rotational", "velocity_development", "reactive"],
        "contraindications": ["active_oblique_strain"],
        "modification_flags": {
            "ucl_history": "no_modification_needed",
            "oblique_strain": "avoid_until_cleared",
            "shoulder_impingement": "monitor_arm_follow_through"
        },
        "youtube_url": "https://youtube.com/shorts/7fbeRfHsyuQ?si=ePwVGUDDFM7HYPik",
        "evidence_level": "moderate",
        "source_notes": "UChicago exercise library (Med Ball)."
    },
]


def main():
    parser = argparse.ArgumentParser(description="Enrich exercise library with YouTube URLs and new exercises.")
    parser.add_argument("--apply", action="store_true", help="Write changes to exercise_library.json")
    parser.add_argument("--supabase", action="store_true", help="Upsert changes to Supabase (requires env vars)")
    parser.add_argument("--dry-run", action="store_true", help="Alias for default: print changes without writing")
    args = parser.parse_args()

    write = args.apply
    push_supabase = args.supabase

    with open(LIBRARY_PATH) as f:
        library = json.load(f)

    exercises = library["exercises"]
    ex_by_id = {ex["id"]: ex for ex in exercises}

    # ── 1. YouTube backfills ──────────────────────────────────────────────────
    backfilled = []
    for ex_id, url in YOUTUBE_BACKFILLS.items():
        if ex_id not in ex_by_id:
            print(f"  WARNING: {ex_id} not found in library — skipping backfill")
            continue
        ex = ex_by_id[ex_id]
        if not ex.get("youtube_url"):
            if write:
                ex["youtube_url"] = url
            backfilled.append((ex_id, ex["name"], url))
            print(f"  BACKFILL {'(applied)' if write else '(dry run)'}: {ex_id} {ex['name']} <- {url}")
        else:
            print(f"  SKIP (already has URL): {ex_id} {ex['name']}")

    # ── 2. New exercises ──────────────────────────────────────────────────────
    added = []
    existing_ids = set(ex_by_id.keys())
    for new_ex in NEW_EXERCISES:
        ex_id = new_ex["id"]
        if ex_id in existing_ids:
            print(f"  SKIP (already exists): {ex_id} {new_ex['name']}")
            continue
        if write:
            exercises.append(new_ex)
        added.append(ex_id)
        print(f"  ADD {'(applied)' if write else '(dry run)'}: {ex_id} {new_ex['name']}")

    # ── 3. Write file ─────────────────────────────────────────────────────────
    if write:
        with open(LIBRARY_PATH, "w") as f:
            json.dump(library, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"\nWrote exercise_library.json: {len(exercises)} total exercises")
        print(f"  Backfilled: {len(backfilled)} YouTube URLs")
        print(f"  Added: {len(added)} new exercises")
    else:
        print(f"\nDry run complete. Pass --apply to write changes.")
        print(f"  Would backfill: {len(backfilled)} YouTube URLs")
        print(f"  Would add: {len(added)} new exercises")

    # ── 4. Supabase upsert ────────────────────────────────────────────────────
    if push_supabase:
        try:
            import os as _os
            from supabase import create_client
            url = _os.environ["SUPABASE_URL"]
            key = _os.environ["SUPABASE_SERVICE_KEY"]
            client = create_client(url, key)

            # Upsert backfilled exercises
            for ex_id, name, yt_url in backfilled:
                ex = ex_by_id[ex_id]
                client.table("exercises").upsert({"id": ex_id, "youtube_url": yt_url}).execute()
                print(f"  Supabase upsert backfill: {ex_id}")

            # Upsert new exercises
            for new_ex in NEW_EXERCISES:
                if new_ex["id"] in added:
                    client.table("exercises").upsert(new_ex).execute()
                    print(f"  Supabase upsert new: {new_ex['id']} {new_ex['name']}")

        except ImportError:
            print("ERROR: supabase-py not installed. Run: pip install supabase")
            sys.exit(1)
        except KeyError as e:
            print(f"ERROR: Missing env var {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
