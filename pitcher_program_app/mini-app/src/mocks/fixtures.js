/**
 * Fictional fixture data for backend-less dev mode (VITE_USE_MOCKS=true).
 *
 * NONE of this is real athlete data — "Sample Pitcher" is invented, and every
 * value here exists only to make the UI render realistically without a backend.
 * Shapes are driven by what the mini-app actually reads (see pages/Home.jsx,
 * pages/Programs.jsx, components/DailyCard.jsx, etc.).
 */

export const MOCK_PITCHER_ID = 'mock_pitcher';

const todayStr = () =>
  new Date().toLocaleDateString('en-CA', { timeZone: 'America/Chicago' });

const daysAgo = (n) => {
  const d = new Date(Date.now() - n * 86400000);
  return d.toLocaleDateString('en-CA', { timeZone: 'America/Chicago' });
};

// ---- profile -------------------------------------------------------------
export const profile = {
  pitcher_id: MOCK_PITCHER_ID,
  name: 'Sample Pitcher',
  role: 'starter',
  rotation_length: 7,
  team_id: 'uchicago_baseball',
  active_flags: {
    current_flag_level: 'yellow',
    current_arm_feel: 6,
    days_since_outing: 3,
    next_outing_days: 4,
    last_outing_date: daysAgo(3),
  },
  pitching_profile: {
    pitch_arsenal: ['4-Seam', 'Slider', 'Changeup', 'Curveball'],
  },
  current_training: {
    current_maxes: { trap_bar_dl: 405, front_squat: 275, db_bench: 90, pullup: 45 },
    lifting_experience: 'intermediate',
    current_split: 'upper_lower_2x',
  },
  injury_history: [
    { area: 'elbow', severity: 'mild', status: 'monitoring' },
  ],
};

// ---- a fully-formed "today" plan so DailyCard renders a real day ---------
const liftingExercises = [
  { exercise_id: 'ex_001', name: 'Trap Bar Deadlift', sets: 3, reps: '5', block: 'compound' },
  { exercise_id: 'ex_014', name: 'DB Bench Press', sets: 3, reps: '8', block: 'compound' },
  { exercise_id: 'ex_042', name: 'Single-Leg RDL', sets: 3, reps: '8/side', block: 'accessory' },
  { exercise_id: 'ex_077', name: 'Half-Kneeling Cable Row', sets: 3, reps: '10', block: 'accessory' },
  { exercise_id: 'ex_101', name: 'Pallof Press', sets: 3, reps: '12/side', block: 'core' },
  { exercise_id: 'ex_133', name: 'Med Ball Rotational Throw', sets: 4, reps: '5/side', block: 'explosive' },
];

const armCareExercises = [
  { exercise_id: 'ac_001', name: 'Band External Rotation', sets: 2, reps: '15' },
  { exercise_id: 'ac_004', name: 'Prone Y-T-W', sets: 2, reps: '10' },
  { exercise_id: 'ac_009', name: 'Wrist Flexor Eccentrics', sets: 2, reps: '12' },
];

const todayEntry = {
  date: todayStr(),
  pre_training: { arm_feel: 6, overall_energy: 7, sleep_hours: 7.5 },
  plan_generated: {
    day_focus: 'Lower + Arm Care',
    training_intent: 'maintenance',
    estimated_duration_min: 55,
    source: 'llm_enriched',
    source_reason: 'mock',
    morning_brief: JSON.stringify({
      arm_verdict: 'cleared',
      coaching_note:
        "Arm feel is a 6 — slightly below your green line, so we're trimming one accessory and keeping intent moderate. Prioritize the arm-care block today.",
    }),
  },
  lifting: { exercises: liftingExercises, estimated_duration_min: 55 },
  arm_care: { exercises: armCareExercises },
  completed_exercises: { ex_001: true, ex_014: true, ac_001: true },
  plan_narrative: 'Lower-body maintenance with a full arm-care block.',
};

const priorEntry = (n, flag, arm) => ({
  date: daysAgo(n),
  pre_training: { arm_feel: arm, overall_energy: 6, sleep_hours: 7 },
  plan_generated: { day_focus: 'Recovery', estimated_duration_min: 30 },
  plan_narrative: 'Recovery day.',
  flag_level: flag,
});

// ---- log -----------------------------------------------------------------
export const log = {
  entries: [
    priorEntry(5, 'green', 8),
    priorEntry(4, 'green', 7),
    priorEntry(3, 'yellow', 6),
    priorEntry(2, 'yellow', 6),
    priorEntry(1, 'green', 7),
    todayEntry,
  ],
};

// ---- progression ---------------------------------------------------------
export const progression = {
  observations: [
    'Arm feel has held in the 6-8 band for two weeks — stable.',
    'Sleep averaging 7.3h; recovery on track for your next start.',
  ],
};

// ---- trend / week-summary / narrative ------------------------------------
export const trend = {
  sparkline: [8, 7, 6, 6, 7, 6],
  outing_day_indices: [0, 5],
  current_streak: 6,
  weeks: [
    { week_start: daysAgo(14), avg_arm_feel: 7.2 },
    { week_start: daysAgo(7), avg_arm_feel: 6.6 },
  ],
};

export const weekSummary = {
  week: [
    { date: daysAgo(5), flag_level: 'green' },
    { date: daysAgo(4), flag_level: 'green' },
    { date: daysAgo(3), flag_level: 'yellow' },
    { date: daysAgo(2), flag_level: 'yellow' },
    { date: daysAgo(1), flag_level: 'green' },
    { date: todayStr(), flag_level: 'yellow' },
  ],
};

export const weeklyNarrative = {
  headline: 'Holding steady into your next start',
  week_start: daysAgo(7),
  narrative:
    'A solid week. Arm feel dipped midweek but recovered — exactly the pattern we want three days out. Keep the arm-care volume up.',
};

// ---- whoop ---------------------------------------------------------------
export const whoopToday = {
  linked: true,
  data: { recovery_score: 64, hrv_ms: 78, resting_hr: 52, sleep_performance: 81, strain: 11.2 },
  averages: { hrv_7day: 74, recovery_7day: 61 },
};

// ---- staff pulse ---------------------------------------------------------
export const staffPulse = {
  total_pitchers: 6,
  checked_in: 4,
  green: 3,
  yellow: 2,
  red: 1,
  pitchers: [
    { name: 'Sample Pitcher', checkin_status: 'checked_in', flag_level: 'yellow' },
    { name: 'Teammate A', checkin_status: 'checked_in', flag_level: 'green' },
    { name: 'Teammate B', checkin_status: 'checked_in', flag_level: 'green' },
    { name: 'Teammate C', checkin_status: 'checked_in', flag_level: 'green' },
    { name: 'Teammate D', checkin_status: 'pending', flag_level: 'red' },
    { name: 'Teammate E', checkin_status: 'pending', flag_level: 'yellow' },
  ],
};

// ---- exercises -----------------------------------------------------------
export const exercises = {
  exercises: [
    ...liftingExercises.map((e) => ({
      id: e.exercise_id,
      name: e.name,
      category: e.block,
      youtube_url: '',
      prescription: `${e.sets} x ${e.reps}`,
    })),
    ...armCareExercises.map((e) => ({
      id: e.exercise_id,
      name: e.name,
      category: 'arm_care',
      youtube_url: '',
      prescription: `${e.sets} x ${e.reps}`,
    })),
  ],
};

export const exerciseSlugs = {
  ex_001: 'trap-bar-deadlift',
  ex_014: 'db-bench-press',
};

// ---- upcoming ------------------------------------------------------------
export const upcoming = {
  upcoming: [
    { date: daysAgo(-1), day_focus: 'Upper + Plyos', throwing: 'Catch play', duration_min: 50 },
    { date: daysAgo(-2), day_focus: 'Recovery', throwing: 'Light catch', duration_min: 25 },
    { date: daysAgo(-3), day_focus: 'Bullpen prep', throwing: 'Long toss', duration_min: 60 },
    { date: daysAgo(-4), day_focus: 'Start', throwing: 'Game', duration_min: 0 },
  ],
};

// ---- programs ------------------------------------------------------------
const throwingProgram = {
  id: 'prog_throw_mock',
  domain: 'throwing',
  template_id: 'velocity_12wk_v1',
  name: 'Velocity Development (12wk)',
  status: 'active',
  current_day_index: 22,
  total_days: 84,
  goal: 'Build velocity into the season',
  duration_weeks: 12,
  created_at: daysAgo(22),
};

const liftingProgram = {
  id: 'prog_lift_mock',
  domain: 'lifting',
  template_id: 'in_season_lifting_starter_v1',
  name: 'In-Season Lifting',
  status: 'active',
  current_day_index: 18,
  total_days: 56,
  goal: 'Maintain strength in-season',
  duration_weeks: 8,
  created_at: daysAgo(18),
};

export const programsActive = { throwing: throwingProgram, lifting: liftingProgram };
export const programsDrafts = [];
export const programsHistory = [
  { ...liftingProgram, id: 'prog_hist_mock', status: 'archived', name: 'Off-Season Hypertrophy', archived_at: daysAgo(30) },
];
export const holdsToday = { throwing: false, lifting: true };
export const programsTemplates = {
  templates: [
    { template_id: 'velocity_12wk_v1', domain: 'throwing', name: 'Velocity Development', duration_range: '[8,12]', goal_tags: ['velocity'], research_doc_ids: [] },
    { template_id: 'in_season_lifting_starter_v1', domain: 'lifting', name: 'In-Season Lifting', duration_range: '[8,8]', goal_tags: ['maintenance'], research_doc_ids: [] },
  ],
};

export const favorites = [];
export const morningStatus = { checked_in: true, plan_status: 'generated', flag_level: 'yellow' };
