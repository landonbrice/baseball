/**
 * parseBrief — tolerant morning_brief parser.
 *
 * Historically morning_brief could be any of:
 *   • a plain string ("Focus on recovery today.")
 *   • a JSON-stringified dict with coaching_note + other keys
 *   • null / undefined
 *   • malformed garbage
 *
 * parseBrief always returns an object so readers can destructure safely.
 * Per D8, the envelope is free-form — readers pick off keys they recognize.
 *
 * @param {unknown} raw
 * @returns {{ coaching_note?: string, [key: string]: unknown }}
 */
export function parseBrief(raw) {
  if (raw == null || raw === '') return {};
  if (typeof raw === 'object') return raw;
  if (typeof raw !== 'string') return {};

  try {
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      return parsed;
    }
    return {};
  } catch (_err) {
    // Legacy plain-string brief — wrap it as coaching_note
    return { coaching_note: raw };
  }
}
