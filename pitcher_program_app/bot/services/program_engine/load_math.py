"""Program Engine v1 — load math + ACWR governor (Task 2.1).

Calibrated against `tests/fixtures/golden_acwr_curve.json`. The golden curve's
verified daily anchor — `(45ft × 40 throws × 50% intent) → G ≈ 2145` — pins
the single tunable constant K_THROWING. The weekly G curve serves as a
secondary regression target (programs that should look like the human-authored
golden must produce a similar curve under this load function).

Public surface:
- `daily_throwing_load(t)`         single ThrowingFiveTuple exposure → G
- `daily_lifting_load(blocks)`     sum across LiftingBlock list → load units
- `weekly_load_from_days(days, week_index, mode)`  per-week aggregate
- `compute_acwr(loads, at_day, window_acute, window_chronic)`  → ratio | None
- `check_acwr_invariant(program)`  → list[GuardrailViolation]

Tunable constants live at module top (no magic numbers inside functions).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional, Sequence

from bot.services.program_engine.schemas import (
    Day,
    LiftingBlock,
    LiftingExercise,
    PitcherProgram,
    ThrowingFiveTuple,
)

# ─────────────────────────────────────────────────────────────────────────────
# Calibration constants
# ─────────────────────────────────────────────────────────────────────────────

# K_THROWING calibrates per-exposure G to the verified anchor:
#     G = K_THROWING × throw_count × distance_ft × (intensity_pct / 100)
# Anchor: (45ft, 40 throws, 50% intent) → G ≈ 2145.
#   K = 2145 / (40 × 45 × 0.5) = 2145 / 900 ≈ 2.3833
K_THROWING: float = 2.3833

# Lifting intensity heuristics — convert prescription strings to a 0–1 factor.
# Order matters: more-specific patterns first.
# Defaults reflect Driveline lifting + PITCHING-PROGRAM-FINAL.pdf RIR tables.
_INTENSITY_PATTERNS: list[tuple[re.Pattern, float]] = [
    (re.compile(r"(\d+)\s*-\s*(\d+)\s*%\s*1\s*rm", re.IGNORECASE), -1.0),   # range placeholder; handled specially
    (re.compile(r"(\d+)\s*%\s*1\s*rm", re.IGNORECASE), -2.0),                # single-pct placeholder
    (re.compile(r"(\d+)\s*rir", re.IGNORECASE), -3.0),                       # RIR placeholder
    (re.compile(r"\bbw\b", re.IGNORECASE), 0.50),                            # bodyweight
    (re.compile(r"\bnear\s+maximal\b", re.IGNORECASE), 0.92),
    (re.compile(r"\bmoderate\b", re.IGNORECASE), 0.65),
    (re.compile(r"\bheavy\b", re.IGNORECASE), 0.80),
    (re.compile(r"\blight\b", re.IGNORECASE), 0.50),
]
# RIR table: 0 RIR ≈ 100% 1RM, 1 ≈ 95%, 2 ≈ 90%, 3 ≈ 85%, 4 ≈ 80%, 5 ≈ 75%
_RIR_TO_INTENSITY = {0: 1.00, 1: 0.95, 2: 0.90, 3: 0.85, 4: 0.80, 5: 0.75}

# When intensity is unset/unparseable, default to a moderate accumulation load.
_DEFAULT_LIFTING_INTENSITY = 0.65

# ACWR bands — Phase 2.2 invariants consume these defaults; the velocity
# knowledge pack's `content.acwr_governor` overrides them per-program.
ACWR_BAND_DEFAULT = (0.8, 1.3)
ACWR_HARD_CAP_DEFAULT = 1.5
ACUTE_WINDOW_DAYS = 7
CHRONIC_WINDOW_DAYS = 28

# ─────────────────────────────────────────────────────────────────────────────
# Violation type — shared with structural/content invariants
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class GuardrailViolation:
    """A single guardrail miss. Phase 2.4's orchestrator partitions these into
    repairable/fatal and surfaces them to the LLM in re-prompts."""

    kind: str                                       # e.g. "acwr_hard_cap_exceeded"
    where: dict                                     # e.g. {"week": 7, "day_index": 22}
    actual: object                                  # observed value
    expected: object                                # expected value or band
    severity: str = "error"                         # "error" | "warning"
    repair_hint: Optional[str] = None               # cheap remedy, if any

    def __str__(self) -> str:
        return f"[{self.severity}] {self.kind} at {self.where}: actual={self.actual!r} expected={self.expected!r}"


# ─────────────────────────────────────────────────────────────────────────────
# Load formulas — pure functions, no I/O
# ─────────────────────────────────────────────────────────────────────────────


def daily_throwing_load(t: ThrowingFiveTuple) -> float:
    """G load units for one throwing exposure.

    Calibrated against `tests/fixtures/golden_acwr_curve.json` —
    `(45ft × 40 throws × 50% intent) → G ≈ 2145 ± 5%`.

    Multiple exposures in a single day (e.g. 45/60/75ft warmup ladder + a velo
    set) sum: `sum(daily_throwing_load(t) for t in exposures)`.
    """
    if t.throw_count <= 0 or t.distance_ft <= 0 or t.intensity_pct <= 0:
        return 0.0
    return K_THROWING * t.throw_count * t.distance_ft * (t.intensity_pct / 100.0)


def _parse_intensity_factor(prescription: Optional[str]) -> float:
    """Map a freeform lifting intensity string to a 0–1 factor.

    Recognized:
      - "50-75% 1RM"   → midpoint 0.625
      - "85% 1RM"      → 0.85
      - "2RIR" / "2 RIR" → table lookup
      - "BW", "Heavy", "Light", "Moderate", "Near Maximal"
      - empty / None / unparseable → _DEFAULT_LIFTING_INTENSITY
    """
    if not prescription:
        return _DEFAULT_LIFTING_INTENSITY
    s = prescription.strip()
    for pat, value in _INTENSITY_PATTERNS:
        m = pat.search(s)
        if not m:
            continue
        if value == -1.0:  # range
            lo, hi = int(m.group(1)), int(m.group(2))
            return ((lo + hi) / 2.0) / 100.0
        if value == -2.0:  # single percent
            return int(m.group(1)) / 100.0
        if value == -3.0:  # RIR
            rir = int(m.group(1))
            return _RIR_TO_INTENSITY.get(rir, 0.85)
        return value
    return _DEFAULT_LIFTING_INTENSITY


def _parse_reps_count(reps_str: str) -> int:
    """Best-effort rep count for load math.

    Strategy:
    - "8" → 8
    - "8-10" → ceil((8+10)/2) = 9
    - "3x8" / "3X8" → 8 (strip leading "Nx" — that's sets, not reps)
    - "3x4-6" → ceil((4+6)/2) = 5 (after stripping leading "3x", range avg)
    - "3 each leg" → 3 (single number; each-leg is caller's concern)
    - "AMRAP" / "" / None → 1 (conservative fallback)

    Uses `(a + b + 1) // 2` for averaging to dodge Python's banker's rounding
    (`round(4.5) == 4`) so a 4-6 rep range deterministically returns 5.
    """
    if not reps_str:
        return 1
    s = reps_str
    # Strip "Nx" / "NX" prefix when present (sets × reps notation)
    m = re.match(r"^\s*\d+\s*[xX]\s*(.+)$", s)
    if m:
        s = m.group(1)
    nums = [int(n) for n in re.findall(r"\d+", s)]
    if not nums:
        return 1
    if len(nums) == 1:
        return nums[0]
    # Range like "8-10" — ceiling-average so 4-6 → 5 and 8-10 → 9
    a, b = nums[0], nums[-1]
    return max(1, (a + b + 1) // 2)


def daily_lifting_load(blocks: Sequence[LiftingBlock]) -> float:
    """Σ(sets × reps × intensity_factor) across all exercises in all blocks."""
    total = 0.0
    for block in blocks:
        for ex in block.exercises:
            sets = ex.sets
            reps = _parse_reps_count(ex.reps)
            factor = _parse_intensity_factor(ex.intensity)
            total += sets * reps * factor
    return total


def daily_total_load(day: Day) -> float:
    """Combined throwing + lifting load for a day."""
    throwing = daily_throwing_load(day.throwing_5tuple) if day.throwing_5tuple else 0.0
    lifting = daily_lifting_load(day.lifting_blocks)
    return throwing + lifting


def weekly_load_from_days(days: Sequence[Day], week_one_based: int) -> float:
    """Sum daily_total_load across days that fall in `week_one_based`.

    Week boundaries: day_index 0–6 → week 1; 7–13 → week 2; etc. This matches
    the calendar-relative scaffold the existing Plan 4 program uses.
    """
    if week_one_based < 1:
        return 0.0
    lo = (week_one_based - 1) * 7
    hi = lo + 7
    return sum(daily_total_load(d) for d in days if lo <= d.day_index < hi)


def daily_loads_series(days: Sequence[Day]) -> list[float]:
    """Per-day total-load series in day_index order. Missing days fill with 0.

    Returns a list of length `max(day_index)+1`. Holes from a non-dense
    `day_index` sequence are zero so the rolling windows in `compute_acwr`
    align with the calendar.
    """
    if not days:
        return []
    sorted_days = sorted(days, key=lambda d: d.day_index)
    max_idx = sorted_days[-1].day_index
    series = [0.0] * (max_idx + 1)
    for d in sorted_days:
        series[d.day_index] = daily_total_load(d)
    return series


# ─────────────────────────────────────────────────────────────────────────────
# ACWR
# ─────────────────────────────────────────────────────────────────────────────


def compute_acwr(
    daily_loads: Sequence[float],
    at_day_index: int,
    *,
    window_acute: int = ACUTE_WINDOW_DAYS,
    window_chronic: int = CHRONIC_WINDOW_DAYS,
) -> Optional[float]:
    """Acute:chronic workload ratio at day `at_day_index`.

    Standard sports-science convention (Gabbett 2016, Hulin et al.):
    - acute   = MEAN of daily_loads over trailing window_acute days
    - chronic = MEAN of daily_loads over trailing window_chronic days
    - returns acute / chronic, or None when chronic == 0 or out of range.

    The 0.8–1.3 sweet-spot band only makes sense when both terms are means
    (or both are sums of equal-length windows). Steady state → ratio ≈ 1.0.

    Both windows are trailing and inclusive of `at_day_index`.
    """
    if at_day_index < 0 or at_day_index >= len(daily_loads):
        return None
    a_lo = max(0, at_day_index - window_acute + 1)
    c_lo = max(0, at_day_index - window_chronic + 1)
    acute_window = daily_loads[a_lo : at_day_index + 1]
    chronic_window = daily_loads[c_lo : at_day_index + 1]
    if not acute_window or not chronic_window:
        return None
    acute_mean = sum(acute_window) / len(acute_window)
    chronic_mean = sum(chronic_window) / len(chronic_window)
    if chronic_mean == 0:
        return None
    return acute_mean / chronic_mean


# ─────────────────────────────────────────────────────────────────────────────
# Invariant check — Guardrail #1 (ACWR band)
# ─────────────────────────────────────────────────────────────────────────────


def check_acwr_invariant(
    program: PitcherProgram,
    *,
    band: tuple[float, float] = ACWR_BAND_DEFAULT,
    hard_cap: float = ACWR_HARD_CAP_DEFAULT,
) -> list[GuardrailViolation]:
    """Walk the program day-by-day. Return violations where:
      - ACWR exceeds hard_cap (FATAL — no repair, only reject+reprompt)
      - ACWR exits band (REPAIRABLE — Phase 2.4 may clip intensity)

    The first chronic-window worth of days are skipped (ACWR undefined).
    """
    series = daily_loads_series(program.days)
    violations: list[GuardrailViolation] = []
    band_lo, band_hi = band
    for d in program.days:
        if d.day_index < CHRONIC_WINDOW_DAYS - 1:
            # Not enough chronic history yet — undefined, not a violation
            continue
        acwr = compute_acwr(series, d.day_index)
        if acwr is None:
            continue
        if acwr > hard_cap:
            violations.append(
                GuardrailViolation(
                    kind="acwr_hard_cap_exceeded",
                    where={"day_index": d.day_index, "date": d.date},
                    actual=round(acwr, 3),
                    expected=f"≤ {hard_cap}",
                    severity="error",
                    repair_hint=None,
                )
            )
        elif acwr > band_hi:
            violations.append(
                GuardrailViolation(
                    kind="acwr_above_band",
                    where={"day_index": d.day_index, "date": d.date},
                    actual=round(acwr, 3),
                    expected=f"[{band_lo}, {band_hi}]",
                    severity="warning",
                    repair_hint="clip_intensity_pct_to_lower_band",
                )
            )
        elif acwr < band_lo:
            violations.append(
                GuardrailViolation(
                    kind="acwr_below_band",
                    where={"day_index": d.day_index, "date": d.date},
                    actual=round(acwr, 3),
                    expected=f"[{band_lo}, {band_hi}]",
                    severity="warning",
                    repair_hint="add_supplementary_throwing_volume",
                )
            )
    return violations
