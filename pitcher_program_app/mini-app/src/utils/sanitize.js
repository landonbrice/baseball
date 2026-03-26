/**
 * Sanitize Supabase JSONB data at the API boundary.
 *
 * Root cause: Supabase JSONB columns can return {} where code expects []
 * (and vice versa), or null where code expects {}. When React tries to
 * render an object as a child, it throws Error #310.
 *
 * Use these helpers when accessing JSONB fields from API responses.
 */

/** Ensure value is an array. Returns [] for null, undefined, or objects. */
export function asArray(val) {
  return Array.isArray(val) ? val : [];
}

/** Ensure value is a plain object. Returns {} for null, undefined, or arrays. */
export function asObject(val) {
  return (val && typeof val === 'object' && !Array.isArray(val)) ? val : {};
}

/** Ensure value is a string. Returns fallback for null, undefined, or objects. */
export function asString(val, fallback = '') {
  return typeof val === 'string' ? val : fallback;
}

/** Ensure value is a number. Returns fallback for null, undefined, or non-numbers. */
export function asNumber(val, fallback = null) {
  return typeof val === 'number' && !isNaN(val) ? val : fallback;
}
