import { http, HttpResponse } from 'msw';
import * as fx from './fixtures';

// `*` globs the origin, so handlers match whatever VITE_API_URL points at
// (localhost:8000, Railway, etc.). Query strings (?_r=, ?bust=) don't affect
// pathname matching, so cache-bust suffixes pass through fine.
const json = (data) => () => HttpResponse.json(data);

export const handlers = [
  // --- auth (only hit on the Telegram/token path; dev fallback skips it) ---
  http.get('*/api/auth/resolve', () =>
    HttpResponse.json({ pitcher_id: fx.MOCK_PITCHER_ID })),

  // --- pitcher-scoped reads ---
  http.get('*/api/pitcher/:id/profile', json(fx.profile)),
  http.get('*/api/pitcher/:id/log', json(fx.log)),
  http.get('*/api/pitcher/:id/progression', json(fx.progression)),
  http.get('*/api/pitcher/:id/trend', json(fx.trend)),
  http.get('*/api/pitcher/:id/week-summary', json(fx.weekSummary)),
  http.get('*/api/pitcher/:id/weekly-narrative', json(fx.weeklyNarrative)),
  http.get('*/api/pitcher/:id/whoop-today', json(fx.whoopToday)),
  http.get('*/api/pitcher/:id/upcoming', json(fx.upcoming)),
  http.get('*/api/pitcher/:id/morning-status', json(fx.morningStatus)),
  http.get('*/api/pitcher/:id/scheduled-throws', json({ scheduled_throws: [] })),

  // --- library / team (slugs before exercises is harmless; paths don't overlap) ---
  http.get('*/api/exercises/slugs', json(fx.exerciseSlugs)),
  http.get('*/api/exercises', json(fx.exercises)),
  http.get('*/api/staff/pulse', json(fx.staffPulse)),

  // --- programs ---
  http.get('*/api/programs/active', json(fx.programsActive)),
  http.get('*/api/programs/drafts', json(fx.programsDrafts)),
  http.get('*/api/programs/history', json(fx.programsHistory)),
  http.get('*/api/programs/holds-today', json(fx.holdsToday)),
  http.get('*/api/programs/templates', json(fx.programsTemplates)),

  // --- favorites ---
  http.get('*/api/favorites', json(fx.favorites)),

  // --- common writes: optimistic success so flows don't dead-end ---
  http.post('*/api/pitcher/:id/checkin', () =>
    HttpResponse.json({ ok: true, plan_generated: true, ...fx.morningStatus })),
  http.post('*/api/pitcher/:id/chat', () =>
    HttpResponse.json({
      reply: 'Mock coach: looks good — keep the arm-care volume up today.',
      messages: [],
    })),

  // --- catch-all (MUST stay last): never let an un-fixtured /api call throw ---
  http.all('*/api/*', ({ request }) =>
    request.method === 'GET'
      ? HttpResponse.json({})
      : HttpResponse.json({ ok: true })),
];
