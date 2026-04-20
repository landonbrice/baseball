/**
 * Classify free-text arm-feel reports to a numeric 1-10 scale.
 * Returns { feel: number | null, ack: string }.
 *
 * Keyword ordering matters — checked top-to-bottom; first match wins.
 * "no soreness" regression: positive phrases are checked FIRST so
 * "feels good" wins before the "sore" substring check can fire.
 *
 * Scale values map to triage bands (see bot/services/triage.py):
 *   <=2 critical shutdown, <=4 RED, <=6 YELLOW, >=7 GREEN.
 *
 * Mapping:
 *   great/perfect/amazing → 9   (high green — leave 10 for superlatives)
 *   good/fine/solid       → 7   (low green)
 *   tight/sore/stiff      → 5   (yellow mid)
 *   terrible/really bad   → 3   (red)
 *   sharp/shooting/numb   → 1   (critical — neurological)
 *   bare numeric 1-10     → clamp + sub-band ack (see below)
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
    return { feel: 9, ack: 'Good to hear.' };
  }
  if (['sharp', 'shooting', 'numb', 'tingling'].some(w => lower.includes(w))) {
    return { feel: 1, ack: 'That sounds concerning \u2014 I\'ll factor that in.' };
  }
  if (['terrible', 'really bad', 'awful'].some(w => lower.includes(w))) {
    return { feel: 3, ack: 'Noted \u2014 we\'ll keep things light today.' };
  }
  if (['tight', 'sore', 'stiff', 'tender'].some(w => lower.includes(w))) {
    return { feel: 5, ack: 'Got it \u2014 I\'ll factor that into your plan.' };
  }
  // Lukewarm bucket — "good" / "fine" without the explicit positive verb pairing.
  if (['good', 'fine', 'solid', 'normal', 'decent'].some(w => lower.includes(w))) {
    return { feel: 7, ack: 'Arm\'s feeling solid.' };
  }
  // Bare numeric input (e.g. "8", "a 3") — clamp to 1-10 with sub-band ack.
  // Sub-bands mirror triage.py thresholds so the ack agrees with the eventual flag.
  const num = parseInt(text);
  if (num >= 1 && num <= 10) {
    if (num <= 4) return { feel: num, ack: 'Noted \u2014 we\'ll keep things light today.' };
    if (num <= 6) return { feel: num, ack: 'Got it \u2014 I\'ll factor that in.' };
    return { feel: num, ack: 'Arm\'s feeling solid.' };
  }
  return { feel: null, ack: 'Got it.' };
}
