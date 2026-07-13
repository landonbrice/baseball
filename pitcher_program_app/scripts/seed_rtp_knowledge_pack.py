"""Seed the return-to-play knowledge pack into block_library (Sprint A).

Upserts `return_to_mound_9wk_v1` — the RTP template the Program Engine authors
against — following the 029/033 idiom (idempotent, keyed on block_template_id).
The rationale layer lives in
data/knowledge/research/return_to_play_progression_model.md; the golden source
data is data/knowledge/golden_programs/ (recovered 2026-07-12).

Requires SUPABASE_URL + SUPABASE_SERVICE_KEY (blocked in sandboxes whose
network policy denies *.supabase.co — run from Railway/local if so).

Usage: python -m scripts.seed_rtp_knowledge_pack [--dry-run]
Exit codes: 0 seeded/verified · 1 connection failure · 2 verification failure
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

ROW = {
    "block_template_id": "return_to_mound_9wk_v1",
    "name": "Return to Play — 9-Week Mound Reintroduction",
    "description": (
        "Stage-2 return-to-play macrocycle from the recovered golden program. "
        "Presumes a completed ramp. 3→4 throwing days/week, weekly throws "
        "178→254, flat-ground intent to 100% by wk3 while mound volume gates "
        "on its own ladder. Goal is a durable pain-free arm — velocity is a "
        "by-product, never a target, until RTP completes."
    ),
    "block_type": "throwing",
    "duration_days": 63,
    "source": "golden_return_to_mound_8wk.csv (9 weeks; recovered from Drive 2026-07-12)",
    "domain": "throwing",
    "goal_tags": ["return_to_play", "return_to_mound", "post_injury_ramp", "healthy_arm"],
    "duration_range_weeks": "[8,10]",
    "compatible_phases": ["off_season", "preseason", "in_season", "in_season_active"],
    "content": {
        "engine_version": "v1",
        "weeks": 9,
        "throws_per_week_progression": [178, 203, 241, 223, 237, 247, 247, 249, 254],
        "phases": [
            {
                "name": "Reintroduction",
                "weeks": [1, 2],
                "distances": ["45ft", "60ft", "75ft", "90ft", "105ft", "120ft"],
                "total_throws_range": [178, 203],
                "effort_pct": 85,
                "intent_notes": "3 days/wk. Compression 'on a line' at 80% then 85-90%. No mound.",
                "drills": ["compression_on_a_line_80pct", "qb_drop_back", "lateral_bound"],
            },
            {
                "name": "Intent Restoration",
                "weeks": [3, 4, 5],
                "distances": ["full_progression_to_120ft"],
                "total_throws_range": [223, 241],
                "effort_pct": 100,
                "intent_notes": (
                    "4 days/wk. Flat-ground pulldowns reach 100%. Mound begins at 50ft "
                    "('on the bump, move plate in — groove fastball'). Wk4 is the deload dip."
                ),
                "drills": ["pulldowns_flat_ground", "bump_at_50ft_groove_fastball"],
            },
            {
                "name": "Mound Build",
                "weeks": [6, 7, 8, 9],
                "distances": ["full_progression", "mound_work"],
                "total_throws_range": [247, 254],
                "effort_pct": 100,
                "intent_notes": "Bullpen ladder climbs 15→50 throws; pitch mix after FB command.",
                "drills": ["bullpen_progression", "pitch_mix_after_fb_command"],
            },
        ],
        "phase_gates": {
            "stage_entry": {
                "criteria": [
                    "completed ramp macrocycle (see ramp golden) or equivalent throwing base",
                    "120ft long toss sustained pain-free",
                    "no active YELLOW/RED triage flag",
                    "acwr_rolling in [0.8, 1.3] for 7 consecutive days",
                ]
            },
            "mound_introduction": {
                "min_week": 3,
                "default_week": 3,
                "criteria": [
                    "flat-ground intent at 100% pain-free",
                    "no active FPM modification (FPM.md gate cleared)",
                    "start at 50ft, groove fastball only",
                ],
            },
            "pitch_mix": {"min_week": 6, "criteria": ["fastball command established in pen"]},
        },
        "mound_volume_ladder_throws": [15, 20, 25, 30, 40, 45, 50],
        "acwr_governor": {
            "band_lower": 0.8,
            "band_upper": 1.3,
            "hard_cap": 1.5,
            "acute_window_days": 7,
            "chronic_window_days": 28,
            "rtp_conservatism": "shrink_week_on_breach_never_absorb",
            "regression_rule": "two RED days in rolling 7d OR symptom recurrence → regress one full week (propose-and-confirm)",
        },
        "invariant_warmup_ladder": [
            {"distance_ft": 45, "intent_pct": 50, "note": "high/pec load 10@30ft, snap-snap rocker x5, self-toss x5"},
            {"distance_ft": 60, "intent_pct": 60, "note": "figure-8 rocker / half-kneel / in-the-hole / step-back quarters"},
            {"distance_ft": 75, "intent_pct": 70, "note": "QB drop-back 50%, lateral bound 50%"},
        ],
        "lifting_integration": {
            "mode_default": "unified",
            "rule": "one intensity tier below throwing stage; no strength_power until RTP completes",
            "sessions_per_week": 2,
            "pull_push_ratio_min": 2.0,
            "fpm_min_days_per_week": 4,
        },
    },
    "tunable_parameters_schema": {
        "stage": {
            "type": "enum",
            "default": "mound_reintroduction",
            "choices": ["ramp", "mound_reintroduction", "full_chain"],
            "description": "Where the pitcher enters the two-stage RTP arc.",
        },
        "stage2_weeks": {"type": "int", "default": 9, "min": 8, "max": 10,
                         "description": "Length of the mound-reintroduction stage."},
        "throwing_days_per_week": {"type": "int", "default": 4, "min": 3, "max": 4,
                                   "description": "Wk1-2 default 3; wk3+ default 4."},
        "mound_ladder_start_rung": {"type": "int", "default": 15, "min": 10, "max": 25,
                                    "description": "First bullpen throw count."},
        "conservatism": {
            "type": "enum",
            "default": "standard",
            "choices": ["standard", "post_surgical"],
            "description": "post_surgical halves weekly increases and doubles gate dwell times.",
        },
    },
    "modification_rules_json": {
        "flag_deltas": {
            "GREEN": {"throwing": "run_prescribed", "lifting": "run_prescribed", "counter": "advance"},
            "YELLOW": {
                "throwing": "drop_one_intent_tier_and_freeze_mound_ladder",
                "lifting": "drop_one_accessory_keep_compounds",
                "counter": "advance",
            },
            "RED": {
                "throwing": "recovery_only_capped_at_prescribed",
                "mound_ladder": "step_back_one_rung",
                "lifting": "light_session",
                "counter": "pause_with_hold_event",
            },
            "CRITICAL_RED": {"throwing": "shutdown", "lifting": "mobility_only", "counter": "pause_with_hold_event"},
        },
        "regression_rule": {
            "trigger": "two_red_days_in_rolling_7d_or_symptom_recurrence",
            "action": "regress_one_week_propose_and_confirm",
        },
        "fpm_gate": {
            "when_active": "pause_throwing_progression_switch_to_FPM_isometrics",
            "cleared_by": "thinker_test_pain_free + 30_reps_x2_consecutive_pain_free_days",
            "reference_doc": "FPM",
        },
        "forearm_tightness": "stop_sign_red_handling_no_progression",
    },
    "research_doc_ids": [
        "return_to_play_progression_model",
        "fpm_strain_protocol",
        "ucl_flexor_pronator_protection",
        "advanced_workload_performance",
        "final_research_base",
    ],
    "implied_phase": "off_season",
}


def main() -> int:
    dry = "--dry-run" in sys.argv
    if dry:
        import json

        print(json.dumps(ROW, indent=2)[:2000] + "\n… (dry run — nothing written)")
        return 0
    try:
        from bot.services.db import get_client

        client = get_client()
        client.table("block_library").upsert(ROW, on_conflict="block_template_id").execute()
    except Exception as e:  # connection / auth / policy failures
        print(f"seed failed: {e}", file=sys.stderr)
        return 1
    got = (
        client.table("block_library")
        .select("block_template_id, goal_tags, research_doc_ids")
        .eq("block_template_id", ROW["block_template_id"])
        .execute()
    )
    rows = got.data or []
    if not rows or "return_to_play" not in (rows[0].get("goal_tags") or []):
        print("verification failed: row missing or goal_tags not written", file=sys.stderr)
        return 2
    print(f"seeded + verified: {rows[0]['block_template_id']} goal_tags={rows[0]['goal_tags']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
