-- Migration 009: Program Builder v1 — core tables
-- Adds:
--   programs                     — personalized, activatable program instances (per-pitcher, per-domain)
--   favorited_blocks             — immutable per-block snapshots (D8)
--   program_builder_sessions     — Socratic interview telemetry + 24h resume (D17)
--   program_hold_events          — every triage-paused day (B-mode counter pause; D7)
--   program_schedule_revisions   — every recompute (anchor changes etc.)
--   program_generation_failures  — validation failures during generate_program
--   coach_visible_override_events — player overrides surfaced to coaches

CREATE TABLE IF NOT EXISTS programs (
  program_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pitcher_id              TEXT NOT NULL REFERENCES pitchers(pitcher_id) ON DELETE CASCADE,
  parent_template_id      UUID NOT NULL,
  domain                  TEXT NOT NULL CHECK (domain IN ('throwing','lifting')),
  tuned_spec_json         JSONB NOT NULL DEFAULT '{}'::jsonb,
  generated_schedule_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  start_date              DATE NOT NULL,
  nominal_end_date        DATE NOT NULL,
  current_day_index       INT  NOT NULL DEFAULT 0,
  held_days_count         INT  NOT NULL DEFAULT 0,
  status                  TEXT NOT NULL CHECK (status IN ('draft','active','archived','error')),
  created_by              TEXT NOT NULL,
  created_by_role         TEXT NOT NULL CHECK (created_by_role IN ('pitcher','coach')),
  approval_required       BOOLEAN NOT NULL DEFAULT false,
  created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  activated_at            TIMESTAMPTZ,
  archived_at             TIMESTAMPTZ,
  archive_reason          TEXT
);

-- Enforces "one active per (pitcher, domain)" — partial unique index
CREATE UNIQUE INDEX IF NOT EXISTS idx_programs_one_active_per_domain
  ON programs (pitcher_id, domain)
  WHERE status = 'active';

CREATE INDEX IF NOT EXISTS idx_programs_pitcher_status
  ON programs (pitcher_id, status);

CREATE INDEX IF NOT EXISTS idx_programs_status_created
  ON programs (status, created_at DESC);

CREATE TABLE IF NOT EXISTS favorited_blocks (
  favorite_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pitcher_id            TEXT NOT NULL REFERENCES pitchers(pitcher_id) ON DELETE CASCADE,
  source_daily_entry_id UUID NOT NULL,
  block_type            TEXT NOT NULL CHECK (block_type IN ('lifting','arm_care','throwing','warmup')),
  block_snapshot_json   JSONB NOT NULL,
  note                  TEXT,
  favorited_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_favorited_blocks_pitcher_type
  ON favorited_blocks (pitcher_id, block_type, favorited_at DESC);

CREATE TABLE IF NOT EXISTS program_builder_sessions (
  session_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pitcher_id              TEXT NOT NULL REFERENCES pitchers(pitcher_id) ON DELETE CASCADE,
  initiator_id            TEXT NOT NULL,
  initiator_role          TEXT NOT NULL CHECK (initiator_role IN ('pitcher','coach')),
  interview_mode          TEXT NOT NULL CHECK (interview_mode IN ('personalize','team_personalize','authoring')),
  constraint_envelope_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  candidate_template_ids  TEXT[] NOT NULL DEFAULT '{}',
  turns_jsonb             JSONB NOT NULL DEFAULT '[]'::jsonb,
  chosen_template_id      UUID,
  tuned_spec_json         JSONB,
  status                  TEXT NOT NULL CHECK (status IN ('in_progress','completed','abandoned')),
  started_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_activity_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  generated_program_id    UUID REFERENCES programs(program_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_builder_sessions_pitcher_status
  ON program_builder_sessions (pitcher_id, status, last_activity_at DESC);

-- For "completed drafts visible to coach" query (locked answer to draft-visibility question):
CREATE INDEX IF NOT EXISTS idx_builder_sessions_completed_drafts
  ON program_builder_sessions (pitcher_id, generated_program_id)
  WHERE status = 'completed' AND generated_program_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS program_hold_events (
  hold_event_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  program_id     UUID NOT NULL REFERENCES programs(program_id) ON DELETE CASCADE,
  hold_date      DATE NOT NULL,
  triage_result  JSONB NOT NULL,
  reason_code    TEXT NOT NULL,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (program_id, hold_date)
);

CREATE INDEX IF NOT EXISTS idx_hold_events_program
  ON program_hold_events (program_id, hold_date DESC);

CREATE TABLE IF NOT EXISTS program_schedule_revisions (
  revision_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  program_id      UUID NOT NULL REFERENCES programs(program_id) ON DELETE CASCADE,
  revised_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  trigger_type    TEXT NOT NULL,
  old_schedule    JSONB NOT NULL,
  new_schedule    JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_schedule_revisions_program
  ON program_schedule_revisions (program_id, revised_at DESC);

CREATE TABLE IF NOT EXISTS program_generation_failures (
  failure_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id              UUID REFERENCES program_builder_sessions(session_id) ON DELETE SET NULL,
  attempt_number          INT NOT NULL,
  validation_failure_kind TEXT NOT NULL,
  llm_response            JSONB,
  created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_generation_failures_kind_created
  ON program_generation_failures (validation_failure_kind, created_at DESC);

CREATE TABLE IF NOT EXISTS coach_visible_override_events (
  event_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pitcher_id   TEXT NOT NULL REFERENCES pitchers(pitcher_id) ON DELETE CASCADE,
  program_id   UUID REFERENCES programs(program_id) ON DELETE SET NULL,
  event_kind   TEXT NOT NULL,
  event_date   DATE NOT NULL,
  details      JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_override_events_pitcher_date
  ON coach_visible_override_events (pitcher_id, event_date DESC);
