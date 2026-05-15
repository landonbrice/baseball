/**
 * Active-only collapse UI — synthesize sub-phase buckets when the LLM plan
 * arrives as a flat exercise list with no block_name structure.
 *
 * Two contexts:
 *   - "lifting"  → Compounds / Accessories / Core / Explosive
 *   - "arm_care" → J-Bands / Wrist Weights / Plyo recovery / Cuff/Scap / Arm Care (fallback)
 *
 * Matching order: tags[] first, then `category` prefix, then exercise name
 * (arm_care only). Inputs are pure — pass exerciseMap so we can fall back
 * to library-defined tags/category when the plan row is sparse.
 */

const LIFTING_BUCKETS = ['Compounds', 'Accessories', 'Core', 'Explosive'];
const ARM_CARE_BUCKETS = ['J-Bands', 'Wrist Weights', 'Plyo recovery', 'Cuff/Scap', 'Arm Care'];

function _resolveTagsAndCategory(exercise, exerciseMap = {}) {
  const inlineTags = Array.isArray(exercise?.tags) ? exercise.tags : null;
  const inlineCat = typeof exercise?.category === 'string' ? exercise.category : null;
  if (inlineTags && inlineCat) {
    return { tags: inlineTags.map(t => String(t).toLowerCase()), category: inlineCat.toLowerCase() };
  }
  const exId = exercise?.exercise_id;
  const lib = exId ? exerciseMap?.[exId] : null;
  const tags = inlineTags
    || (Array.isArray(lib?.tags) ? lib.tags : []);
  const category = inlineCat || lib?.category || '';
  return {
    tags: tags.map(t => String(t).toLowerCase()),
    category: String(category).toLowerCase(),
  };
}

function _name(exercise, exerciseMap = {}) {
  const n = exercise?.name || (exerciseMap?.[exercise?.exercise_id]?.name) || '';
  return String(n).toLowerCase();
}

/**
 * Map a single exercise to a bucket name for the given context.
 *
 * @param {object} exercise — plan row (may have inline tags/category/name)
 * @param {object} options
 * @param {'lifting'|'arm_care'} options.context
 * @param {object} [options.exerciseMap] — id → library record for fallback
 * @returns {string} bucket label (always one of the LIFTING_BUCKETS / ARM_CARE_BUCKETS arrays)
 */
export function synthesizeCategory(exercise, { context, exerciseMap = {} } = {}) {
  const { tags, category } = _resolveTagsAndCategory(exercise, exerciseMap);
  const name = _name(exercise, exerciseMap);

  if (context === 'lifting') {
    const hasTag = (t) => tags.includes(t);
    const catIncludes = (s) => category.includes(s);

    // Explosive takes priority over compound when an exercise is tagged both
    // (e.g. "Trap Bar Squat Jumps" carries both `power` and `lower_body` —
    // the explosive bucket is the more specific intent).
    if (hasTag('power') || hasTag('explosive') || hasTag('plyometric') || catIncludes('plyometric')) {
      return 'Explosive';
    }
    if (hasTag('core') || catIncludes('core')) {
      return 'Core';
    }
    if (hasTag('compound') || catIncludes('compound')) {
      return 'Compounds';
    }
    return 'Accessories';
  }

  if (context === 'arm_care') {
    // Name-based wins for J-Bands / Wrist Weights / Plyo — these are
    // tooling buckets, not anatomy buckets. The tag conventions in the
    // exercise library (`jband`, `wrist_weight`, `plyo`) line up.
    if (
      name.includes('j-band') || name.includes('jband') ||
      tags.includes('jband')
    ) {
      return 'J-Bands';
    }
    if (
      name.includes('wrist weight') ||
      tags.includes('wrist_weight')
    ) {
      return 'Wrist Weights';
    }
    if (
      name.includes('plyo') ||
      tags.includes('plyo') ||
      (tags.includes('plyometric') && tags.includes('recovery'))
    ) {
      return 'Plyo recovery';
    }
    if (
      tags.includes('scapular') || tags.includes('rotator') || tags.includes('cuff') ||
      tags.includes('rotator_cuff') ||
      category.includes('scapular')
    ) {
      return 'Cuff/Scap';
    }
    return 'Arm Care';
  }

  // Unknown context — drop into a catch-all so callers can decide what to do.
  return 'Other';
}

/**
 * Group a flat exercise list into ordered buckets. Preserves original order
 * within each bucket. Drops empty buckets. Returns null when synthesis would
 * produce only a single bucket (caller renders flat in that case).
 *
 * @param {Array} exercises
 * @param {'lifting'|'arm_care'} context
 * @param {object} [options]
 * @param {object} [options.exerciseMap]
 * @returns {Array<{name: string, exercises: Array}>|null}
 */
export function groupExercisesByCategory(exercises, context, { exerciseMap = {} } = {}) {
  if (!Array.isArray(exercises) || exercises.length === 0) return null;

  const order = context === 'lifting' ? LIFTING_BUCKETS : context === 'arm_care' ? ARM_CARE_BUCKETS : [];
  const buckets = new Map();
  for (const ex of exercises) {
    const label = synthesizeCategory(ex, { context, exerciseMap });
    if (!buckets.has(label)) buckets.set(label, []);
    buckets.get(label).push(ex);
  }

  // Emit in spec order; empty buckets are skipped. Any unforeseen labels
  // (shouldn't happen given the bucket enums above) appear after the
  // declared order in insertion order.
  const declared = order.filter(label => buckets.has(label));
  const extras = [...buckets.keys()].filter(label => !order.includes(label));
  const allLabels = [...declared, ...extras];

  if (allLabels.length <= 1) return null;

  return allLabels.map(label => ({ name: label, exercises: buckets.get(label) }));
}
