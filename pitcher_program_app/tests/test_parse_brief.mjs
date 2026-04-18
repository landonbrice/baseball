// Run with: node --test tests/test_parse_brief.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parseBrief } from '../shared/parseBrief.js';

test('null/undefined/empty → empty object', () => {
  assert.deepEqual(parseBrief(null), {});
  assert.deepEqual(parseBrief(undefined), {});
  assert.deepEqual(parseBrief(''), {});
});

test('plain string → { coaching_note: <string> }', () => {
  const res = parseBrief('Focus on recovery today.');
  assert.equal(res.coaching_note, 'Focus on recovery today.');
});

test('JSON stringified dict → parsed object with coaching_note passthrough', () => {
  const raw = JSON.stringify({ coaching_note: 'rest', arm_verdict: { status: 'green', value: '8/10' } });
  const res = parseBrief(raw);
  assert.equal(res.coaching_note, 'rest');
  assert.equal(res.arm_verdict.status, 'green');
});

test('garbage string that is not JSON → coaching_note falls back to raw', () => {
  const raw = '{not valid json';
  const res = parseBrief(raw);
  assert.equal(res.coaching_note, '{not valid json');
});

test('JSON of a non-object (array, number) → empty object', () => {
  assert.deepEqual(parseBrief('[1,2,3]'), {});
  assert.deepEqual(parseBrief('42'), {});
});

test('already-parsed object passed in → returned as-is', () => {
  const obj = { coaching_note: 'done' };
  assert.deepEqual(parseBrief(obj), obj);
});
