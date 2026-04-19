// Run with: node --test tests/test_quick_classify.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { quickClassify } from '../mini-app/src/lib/quickClassify.js';

test('positive phrases map to high end of 1-10 scale', () => {
  assert.ok(quickClassify('arm feels great today').feel >= 9);
  assert.ok(quickClassify('perfect, no issues').feel >= 9);
  assert.ok(quickClassify('arm feels good, no soreness').feel >= 9);
});

test('neutral phrases map to middle of 1-10 scale', () => {
  const r = quickClassify('arm feels fine');
  assert.ok(r.feel >= 6 && r.feel <= 8, `got ${r.feel}`);
});

test('mild-negative phrases (tight/sore) map to 4-5', () => {
  const r = quickClassify('arm feels a bit tight');
  assert.ok(r.feel >= 4 && r.feel <= 6, `got ${r.feel}`);
});

test('severe-negative phrases map to 1-3', () => {
  assert.ok(quickClassify('sharp pain when throwing').feel <= 3);
  assert.ok(quickClassify('shooting pain in elbow').feel <= 3);
});

test('unmatched text returns null feel (delegates to LLM)', () => {
  assert.equal(quickClassify('idk').feel, null);
});

test('"feels good" wins over substring "sore" in "no soreness"', () => {
  // Regression guard: order of keyword checks must not fire "sore" match
  // when the user is explicitly saying "no soreness"
  const r = quickClassify('arm feels good, no soreness');
  assert.ok(r.feel >= 9, `feels-good should win; got ${r.feel}`);
});

test('present-participle "feeling good" maps to top bucket (D4a regression)', () => {
  // Observed 2026-04-19 Railway logs: "arm is feeling good" → arm_feel=4 → RED flag
  // because legacy classifier only matched "good" (bucket 4, pre-migration).
  // After fix, both "feels good" and "feeling good" must land in the 10 bucket.
  assert.ok(quickClassify('arm is feeling good').feel >= 9);
  assert.ok(quickClassify("I'm feeling great today").feel >= 9);
  assert.ok(quickClassify('feeling amazing, no issues').feel >= 9);
});
