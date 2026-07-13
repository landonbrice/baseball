# Drive Policy Comparison — Phase 4.3 Harness Output

_Generated 2026-06-01 by `pitcher_program_app/scripts/compare_drive_policies.py`. Source fixtures: `pitcher_program_app/tests/fixtures/drive_policy_fixtures.json`._

## What this is

Per locked decision **L7**, Program Engine v1 ships THREE candidate "drive" policies + this harness, but does NOT pick one. The harness exercises each policy against four readiness scenarios on a 12-week velocity program and records the metrics that the v2 decision will weigh.

**Policies under test:**
- `silent_absorb` — never re-paces; today's hit stays today's hit.
- `immediate_repace` — every reduction emits a governor signal; remaining weeks adapt.
- `banked_deviation` — small variance absorbs; structural deviation (cumulative or single-day >50%) triggers re-pacing.

**Scenarios:**
- `all_green` — perfect 10 days; no signals expected from any policy.
- `mid_cycle_yellow` — days 3-5 YELLOW with low tissue, then recovery.
- `late_phase_red` — days 7-9 RED with arm_feel=3 + active mod.
- `repeated_low_tissue` — every day YELLOW with tissue=3.5 (chronic drift).

**Metrics emitted:**
- `progress_fraction_10d` — delivered throwing G / intended throwing G across the 10-day window. 1.00 = no compromise.
- `weeks_disturbed` — list of program weeks the governor adjusted.
- `gate_outcomes` — max intent reached per phase (after re-pacing). Tells you if the velocity gate cleared.

## Comparison table

| Scenario | Policy | progress_fraction_10d | weeks_disturbed | total_delivered_g_10d |
|---|---|---|---|---|
| `all_green` | `silent_absorb` | 1.000 | — | 7150 |
| `all_green` | `immediate_repace` | 1.000 | — | 7150 |
| `all_green` | `banked_deviation` | 1.000 | — | 7150 |
| `mid_cycle_yellow` | `silent_absorb` | 0.930 | — | 6649 |
| `mid_cycle_yellow` | `immediate_repace` | 0.930 | — | 6649 |
| `mid_cycle_yellow` | `banked_deviation` | 0.930 | — | 6649 |
| `late_phase_red` | `silent_absorb` | 0.830 | — | 5934 |
| `late_phase_red` | `immediate_repace` | 0.830 | — | 5934 |
| `late_phase_red` | `banked_deviation` | 0.830 | — | 5934 |
| `repeated_low_tissue` | `silent_absorb` | 0.650 | — | 4647 |
| `repeated_low_tissue` | `immediate_repace` | 0.650 | — | 4647 |
| `repeated_low_tissue` | `banked_deviation` | 0.650 | — | 4647 |

## Per-scenario gate outcomes

### `all_green`

| Policy | Phase | max_intent |
|---|---|---|
| `silent_absorb` | Base Building | max_intent=50 |
| `silent_absorb` | Distance Extension | max_intent=65 |
| `silent_absorb` | Compression+Pulldowns | max_intent=77 |
| `silent_absorb` | Max Intent+Mound | max_intent=87 |
| `immediate_repace` | Base Building | max_intent=50 |
| `immediate_repace` | Distance Extension | max_intent=65 |
| `immediate_repace` | Compression+Pulldowns | max_intent=77 |
| `immediate_repace` | Max Intent+Mound | max_intent=87 |
| `banked_deviation` | Base Building | max_intent=50 |
| `banked_deviation` | Distance Extension | max_intent=65 |
| `banked_deviation` | Compression+Pulldowns | max_intent=77 |
| `banked_deviation` | Max Intent+Mound | max_intent=87 |

### `mid_cycle_yellow`

| Policy | Phase | max_intent |
|---|---|---|
| `silent_absorb` | Base Building | max_intent=50 |
| `silent_absorb` | Distance Extension | max_intent=65 |
| `silent_absorb` | Compression+Pulldowns | max_intent=77 |
| `silent_absorb` | Max Intent+Mound | max_intent=87 |
| `immediate_repace` | Base Building | max_intent=50 |
| `immediate_repace` | Distance Extension | max_intent=65 |
| `immediate_repace` | Compression+Pulldowns | max_intent=77 |
| `immediate_repace` | Max Intent+Mound | max_intent=87 |
| `banked_deviation` | Base Building | max_intent=50 |
| `banked_deviation` | Distance Extension | max_intent=65 |
| `banked_deviation` | Compression+Pulldowns | max_intent=77 |
| `banked_deviation` | Max Intent+Mound | max_intent=87 |

### `late_phase_red`

| Policy | Phase | max_intent |
|---|---|---|
| `silent_absorb` | Base Building | max_intent=50 |
| `silent_absorb` | Distance Extension | max_intent=65 |
| `silent_absorb` | Compression+Pulldowns | max_intent=77 |
| `silent_absorb` | Max Intent+Mound | max_intent=87 |
| `immediate_repace` | Base Building | max_intent=50 |
| `immediate_repace` | Distance Extension | max_intent=65 |
| `immediate_repace` | Compression+Pulldowns | max_intent=77 |
| `immediate_repace` | Max Intent+Mound | max_intent=87 |
| `banked_deviation` | Base Building | max_intent=50 |
| `banked_deviation` | Distance Extension | max_intent=65 |
| `banked_deviation` | Compression+Pulldowns | max_intent=77 |
| `banked_deviation` | Max Intent+Mound | max_intent=87 |

### `repeated_low_tissue`

| Policy | Phase | max_intent |
|---|---|---|
| `silent_absorb` | Base Building | max_intent=50 |
| `silent_absorb` | Distance Extension | max_intent=65 |
| `silent_absorb` | Compression+Pulldowns | max_intent=77 |
| `silent_absorb` | Max Intent+Mound | max_intent=87 |
| `immediate_repace` | Base Building | max_intent=50 |
| `immediate_repace` | Distance Extension | max_intent=65 |
| `immediate_repace` | Compression+Pulldowns | max_intent=77 |
| `immediate_repace` | Max Intent+Mound | max_intent=87 |
| `banked_deviation` | Base Building | max_intent=50 |
| `banked_deviation` | Distance Extension | max_intent=65 |
| `banked_deviation` | Compression+Pulldowns | max_intent=77 |
| `banked_deviation` | Max Intent+Mound | max_intent=87 |

## What this report DOES NOT do

- Does not pick a policy. That decision is **explicitly deferred to v2** per L7.
- Does not run on real pitcher check-in data — the readiness sequences are hand-crafted fixtures.
- Does not account for lifting-side re-pacing. The throwing half is the primary driver in the velocity goal; lifting-side adjustments are a v2 concern.
- Does not project forward beyond the 10-day window. Long-tail effects of `silent_absorb` (compounding deviation) require a longer-horizon harness — call that v2 work too.
