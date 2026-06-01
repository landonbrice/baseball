// @vitest-environment node
// msw/node patches Node's fetch; running this file in the node environment
// (rather than the suite-default jsdom) keeps that interception reliable.
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest';
import { handlers } from '../handlers';
import * as fx from '../fixtures';

const server = setupServer(...handlers);
const BASE = 'http://localhost:8000';

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('mock backend handlers', () => {
  it('serves the pitcher profile fixture (fictional data)', async () => {
    const res = await fetch(`${BASE}/api/pitcher/${fx.MOCK_PITCHER_ID}/profile`);
    const data = await res.json();
    expect(data.name).toBe('Sample Pitcher');
    expect(data.active_flags.current_flag_level).toBe('yellow');
    expect(data.team_id).toBe('uchicago_baseball');
  });

  it('serves active programs in the {throwing, lifting} shape Home reads', async () => {
    const res = await fetch(`${BASE}/api/programs/active`);
    const data = await res.json();
    expect(data.throwing).toBeTruthy();
    expect(data.lifting).toBeTruthy();
    expect(data.throwing.domain).toBe('throwing');
  });

  it('serves a log whose latest entry is a full "today" plan', async () => {
    const res = await fetch(`${BASE}/api/pitcher/x/log`);
    const data = await res.json();
    expect(Array.isArray(data.entries)).toBe(true);
    const today = data.entries[data.entries.length - 1];
    expect(today.lifting.exercises.length).toBeGreaterThan(0);
    expect(today.arm_care.exercises.length).toBeGreaterThan(0);
  });

  it('catch-all returns {} for an un-fixtured GET (screens never crash)', async () => {
    const res = await fetch(`${BASE}/api/pitcher/x/some-future-endpoint`);
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({});
  });

  it('catch-all returns {ok:true} for an un-fixtured POST', async () => {
    const res = await fetch(`${BASE}/api/pitcher/x/some-write`, { method: 'POST' });
    expect((await res.json()).ok).toBe(true);
  });

  it('matches paths despite cache-bust query suffixes', async () => {
    const res = await fetch(`${BASE}/api/programs/active?_r=5`);
    expect((await res.json()).lifting).toBeTruthy();
  });

  it('exercises and slugs resolve to distinct fixtures (no path overlap)', async () => {
    const ex = await (await fetch(`${BASE}/api/exercises`)).json();
    const slugs = await (await fetch(`${BASE}/api/exercises/slugs`)).json();
    expect(Array.isArray(ex.exercises)).toBe(true);
    expect(slugs.ex_001).toBe('trap-bar-deadlift');
  });
});
