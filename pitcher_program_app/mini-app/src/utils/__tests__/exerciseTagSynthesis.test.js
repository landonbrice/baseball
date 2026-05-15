/**
 * Active-only collapse — synthesize buckets when LLM returns a flat
 * exercise list. Spot-checks against the conventions in
 * `data/knowledge/exercise_library.json` (verified 2026-05-15).
 */
import { describe, it, expect } from 'vitest';
import {
  synthesizeCategory,
  groupExercisesByCategory,
} from '../exerciseTagSynthesis';

// ---------------------------------------------------------------------------
// Lifting context
// ---------------------------------------------------------------------------

describe('synthesizeCategory · lifting', () => {
  it('places a tagged compound into Compounds', () => {
    // "Bench Press" style — `compound` tag, upper_body_push category
    const ex = { name: 'Bench Press', tags: ['compound', 'upper_body', 'push'], category: 'upper_body_push' };
    expect(synthesizeCategory(ex, { context: 'lifting' })).toBe('Compounds');
  });

  it('places an explosive plyometric into Explosive even when tagged power+lower_body', () => {
    // Mirrors "Trap Bar Squat Jumps" in the library — tag list crosses
    // compound-y intent with power intent; spec says Explosive wins.
    const ex = {
      name: 'Trap Bar Squat Jumps',
      tags: ['power', 'plyometric', 'lower_body', 'velocity_development', 'explosive'],
      category: 'lower_body_power',
    };
    expect(synthesizeCategory(ex, { context: 'lifting' })).toBe('Explosive');
  });

  it('places a Pallof Press into Core', () => {
    const ex = { name: 'Pallof Press', tags: ['core', 'anti_rotation', 'stability'], category: 'core' };
    expect(synthesizeCategory(ex, { context: 'lifting' })).toBe('Core');
  });

  it('places an accessory lift into Accessories', () => {
    const ex = {
      name: 'Tricep Pushdown',
      tags: ['accessory', 'upper_body', 'tricep', 'cable', 'elbow'],
      category: 'upper_body_accessory',
    };
    expect(synthesizeCategory(ex, { context: 'lifting' })).toBe('Accessories');
  });

  it('uses category prefix when tags are missing', () => {
    const ex = { name: 'Mystery Lift', category: 'core_stability' };
    expect(synthesizeCategory(ex, { context: 'lifting' })).toBe('Core');
  });

  it('falls back to Accessories when nothing else matches', () => {
    const ex = { name: 'Unlabeled Movement' };
    expect(synthesizeCategory(ex, { context: 'lifting' })).toBe('Accessories');
  });

  it('falls back to exerciseMap when the plan row is sparse', () => {
    const ex = { exercise_id: 'ex_42' };
    const exerciseMap = {
      ex_42: { name: 'Trap Bar Deadlift', tags: ['compound', 'lower_body'], category: 'lower_body_compound' },
    };
    expect(synthesizeCategory(ex, { context: 'lifting', exerciseMap })).toBe('Compounds');
  });
});

// ---------------------------------------------------------------------------
// Arm care context
// ---------------------------------------------------------------------------

describe('synthesizeCategory · arm_care', () => {
  it('places a J-Band Routine into J-Bands by name (case-insensitive)', () => {
    // The library entry "J-Band Routine" carries arm_care/warmup tags but
    // not the literal `jband` token — the name check has to catch it.
    const ex = { name: 'J-Band Routine', tags: ['warmup', 'throwing', 'arm_care'] };
    expect(synthesizeCategory(ex, { context: 'arm_care' })).toBe('J-Bands');
  });

  it('places a J-Band Forward Fly into J-Bands by tag', () => {
    const ex = { name: 'J-Band Forward Fly', tags: ['jband', 'throwing_warmup', 'arm_care'] };
    expect(synthesizeCategory(ex, { context: 'arm_care' })).toBe('J-Bands');
  });

  it('places a Wrist Weight Drill into Wrist Weights even without explicit arm_care tag', () => {
    // The seed library tags "Wrist Weight Drills" with `forearm`/`activation`
    // but no `arm_care` — the bucket has to come from the name, not the tag.
    const ex = { name: 'Wrist Weight Drills', tags: ['warmup', 'throwing', 'forearm', 'activation'] };
    expect(synthesizeCategory(ex, { context: 'arm_care' })).toBe('Wrist Weights');
  });

  it('places a Plyo Reverse Throws into Plyo recovery', () => {
    const ex = {
      name: 'Plyo Reverse Throws',
      tags: ['plyo', 'throwing', 'deceleration', 'posterior_shoulder'],
      category: 'plyo_throwing',
    };
    expect(synthesizeCategory(ex, { context: 'arm_care' })).toBe('Plyo recovery');
  });

  it('places a Band External Rotation into Cuff/Scap', () => {
    const ex = {
      name: 'Band External Rotation at 90°',
      tags: ['isolation', 'arm_care', 'rotator_cuff', 'external_rotation'],
      category: 'scapular_stability',
    };
    expect(synthesizeCategory(ex, { context: 'arm_care' })).toBe('Cuff/Scap');
  });

  it('places a Prone Y-T-W-A Raises into Cuff/Scap by category prefix', () => {
    const ex = {
      name: 'Prone Y-T-W-A Raises',
      tags: ['isolation', 'arm_care', 'scapular', 'lower_trap'],
      category: 'scapular_stability',
    };
    expect(synthesizeCategory(ex, { context: 'arm_care' })).toBe('Cuff/Scap');
  });

  it('drops everything else into Arm Care', () => {
    const ex = { name: 'Towel Drill', tags: ['arm_care'] };
    expect(synthesizeCategory(ex, { context: 'arm_care' })).toBe('Arm Care');
  });
});

// ---------------------------------------------------------------------------
// Grouping
// ---------------------------------------------------------------------------

describe('groupExercisesByCategory', () => {
  it('returns null when only one bucket is populated (lifting)', () => {
    // All explicitly compounds → can render flat, no synthesis benefit
    const exercises = [
      { name: 'Bench Press', tags: ['compound'], category: 'upper_body_push' },
      { name: 'Squat', tags: ['compound'], category: 'lower_body_compound' },
    ];
    expect(groupExercisesByCategory(exercises, 'lifting')).toBeNull();
  });

  it('returns null when input is empty', () => {
    expect(groupExercisesByCategory([], 'lifting')).toBeNull();
  });

  it('returns null when input is not an array', () => {
    expect(groupExercisesByCategory(undefined, 'lifting')).toBeNull();
  });

  it('groups lifting in declared order (Compounds → Accessories → Core → Explosive)', () => {
    const exercises = [
      { name: 'Tricep Pushdown', tags: ['accessory'], category: 'upper_body_accessory' },
      { name: 'Trap Bar Squat Jumps', tags: ['power', 'plyometric'], category: 'lower_body_power' },
      { name: 'Bench Press', tags: ['compound'], category: 'upper_body_push' },
      { name: 'Pallof Press', tags: ['core'], category: 'core' },
    ];
    const grouped = groupExercisesByCategory(exercises, 'lifting');
    expect(grouped.map(g => g.name)).toEqual(['Compounds', 'Accessories', 'Core', 'Explosive']);
  });

  it('preserves original order within a bucket', () => {
    const exercises = [
      { name: 'Bench Press', tags: ['compound'], category: 'upper_body_push' },
      { name: 'Pallof Press', tags: ['core'], category: 'core' },
      { name: 'Squat', tags: ['compound'], category: 'lower_body_compound' },
      { name: 'Deadlift', tags: ['compound'], category: 'lower_body_compound' },
    ];
    const grouped = groupExercisesByCategory(exercises, 'lifting');
    const compounds = grouped.find(g => g.name === 'Compounds');
    expect(compounds.exercises.map(e => e.name)).toEqual(['Bench Press', 'Squat', 'Deadlift']);
  });

  it('skips empty buckets (only renders populated ones)', () => {
    const exercises = [
      { name: 'Bench Press', tags: ['compound'], category: 'upper_body_push' },
      { name: 'Trap Bar Squat Jumps', tags: ['power', 'plyometric'], category: 'lower_body_power' },
    ];
    const grouped = groupExercisesByCategory(exercises, 'lifting');
    expect(grouped.map(g => g.name)).toEqual(['Compounds', 'Explosive']);
  });

  it('groups arm_care in declared order', () => {
    const exercises = [
      { name: 'Band External Rotation at 90°', tags: ['rotator_cuff', 'arm_care'], category: 'scapular_stability' },
      { name: 'J-Band Forward Fly', tags: ['jband', 'arm_care'] },
      { name: 'Wrist Weight Drills', tags: ['forearm', 'activation'] },
      { name: 'Plyo Reverse Throws', tags: ['plyo', 'throwing'], category: 'plyo_throwing' },
    ];
    const grouped = groupExercisesByCategory(exercises, 'arm_care');
    expect(grouped.map(g => g.name)).toEqual(['J-Bands', 'Wrist Weights', 'Plyo recovery', 'Cuff/Scap']);
  });

  it('returns null when arm_care has only Cuff/Scap items', () => {
    const exercises = [
      { name: 'Band External Rotation at 90°', tags: ['rotator_cuff', 'arm_care'], category: 'scapular_stability' },
      { name: 'Prone Y-T-W-A Raises', tags: ['scapular', 'arm_care'], category: 'scapular_stability' },
    ];
    expect(groupExercisesByCategory(exercises, 'arm_care')).toBeNull();
  });
});
