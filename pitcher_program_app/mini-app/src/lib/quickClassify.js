/**
 * Classify free-text arm-feel reports to a numeric 1-10 scale.
 * Returns { feel: number | null, ack: string }.
 *
 * Keyword ordering matters — checked top-to-bottom; first match wins.
 * "no soreness" regression: positive phrases are checked FIRST so
 * "feels good" wins before the "sore" substring check can fire.
 *
 * Migrated from 1-5 to 1-10 on 2026-04-19 (D4). Mapping:
 *   old 5 (great/perfect) → new 10
 *   old 4 (good/fine)     → new 8
 *   old 3 (tight/sore)    → new 5
 *   old 2 (terrible)      → new 2
 *   old 1 (sharp/numb)    → new 1
 */
export function quickClassify(text) {
  const lower = (text || '').toLowerCase();
  // Top bucket — explicitly positive. Include both "feels X" and "feeling X"
  // forms (D4a): observed production regression 2026-04-19 where
  // "arm is feeling good" missed the top bucket and landed in "good"-alone.
  const POSITIVE = [
    'great', 'perfect', 'amazing', 'no issues',
    'feels good', 'feeling good',
    'feels great', 'feeling great',
    'feels amazing', 'feeling amazing',
    'feels perfect', 'feeling perfect',
  ];
  if (POSITIVE.some(w => lower.includes(w))) {
    return { feel: 10, ack: 'Good to hear.' };
  }
  if (['sharp', 'shooting', 'numb', 'tingling'].some(w => lower.includes(w))) {
    return { feel: 1, ack: 'That sounds concerning — I\'ll factor that in.' };
  }
  if (['terrible', 'really bad', 'awful'].some(w => lower.includes(w))) {
    return { feel: 2, ack: 'Got it.' };
  }
  if (['tight', 'sore', 'stiff', 'tender'].some(w => lower.includes(w))) {
    return { feel: 5, ack: 'Got it — I\'ll factor that into your plan.' };
  }
  // Lukewarm bucket — "good" / "fine" without the explicit positive verb pairing.
  if (['good', 'fine', 'solid', 'normal', 'decent'].some(w => lower.includes(w))) {
    return { feel: 8, ack: 'Arm\'s feeling solid.' };
  }
  return { feel: null, ack: 'Got it.' };
}
