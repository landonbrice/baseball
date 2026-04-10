-- 006_coach_dashboard_foundation.sql
-- Coach Dashboard v0: 7 new tables + additive columns + backfill
-- Idempotent: uses IF NOT EXISTS and ON CONFLICT DO NOTHING

-- 1. teams
CREATE TABLE IF NOT EXISTS teams (
    team_id         text PRIMARY KEY,
    name            text NOT NULL,
    level           text,
    training_phase  text DEFAULT 'offseason',
    timezone        text DEFAULT 'America/Chicago',
    settings        jsonb DEFAULT '{}',
    created_at      timestamptz DEFAULT now(),
    updated_at      timestamptz DEFAULT now()
);

INSERT INTO teams (team_id, name, level, training_phase, timezone)
VALUES ('uchicago_baseball', 'UChicago Baseball', 'd3_college', 'in_season', 'America/Chicago')
ON CONFLICT (team_id) DO NOTHING;

-- 2. coaches
CREATE TABLE IF NOT EXISTS coaches (
    coach_id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id          text NOT NULL REFERENCES teams(team_id),
    email            text UNIQUE NOT NULL,
    name             text NOT NULL,
    role             text,
    supabase_user_id uuid UNIQUE,
    created_at       timestamptz DEFAULT now()
);

-- 3. team_games (replaces schedule table)
CREATE TABLE IF NOT EXISTS team_games (
    game_id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id              text NOT NULL REFERENCES teams(team_id),
    game_date            date NOT NULL,
    game_time            time,
    opponent             text,
    home_away            text,
    is_doubleheader_g2   boolean DEFAULT false,
    starting_pitcher_id  text REFERENCES pitchers(pitcher_id),
    status               text DEFAULT 'scheduled',
    source               text DEFAULT 'manual',
    notes                text,
    created_at           timestamptz DEFAULT now(),
    updated_at           timestamptz DEFAULT now(),
    UNIQUE (team_id, game_date, is_doubleheader_g2)
);

-- 4. block_library
CREATE TABLE IF NOT EXISTS block_library (
    block_template_id   text PRIMARY KEY,
    name                text NOT NULL,
    description         text,
    block_type          text NOT NULL,
    duration_days       integer NOT NULL,
    content             jsonb NOT NULL,
    source              text,
    created_at          timestamptz DEFAULT now()
);

-- 5. team_assigned_blocks
CREATE TABLE IF NOT EXISTS team_assigned_blocks (
    block_id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id               text NOT NULL REFERENCES teams(team_id),
    block_type            text NOT NULL,
    block_template_id     text NOT NULL,
    start_date            date NOT NULL,
    duration_days         integer NOT NULL,
    assigned_by_coach_id  uuid REFERENCES coaches(coach_id),
    notes                 text,
    status                text DEFAULT 'active',
    created_at            timestamptz DEFAULT now()
);

-- 6. coach_suggestions
CREATE TABLE IF NOT EXISTS coach_suggestions (
    suggestion_id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id               text NOT NULL REFERENCES teams(team_id),
    pitcher_id            text NOT NULL REFERENCES pitchers(pitcher_id),
    category              text NOT NULL,
    title                 text NOT NULL,
    reasoning             text NOT NULL,
    proposed_action       jsonb,
    status                text DEFAULT 'pending',
    expires_at            timestamptz,
    created_at            timestamptz DEFAULT now(),
    resolved_at           timestamptz,
    resolved_by_coach_id  uuid REFERENCES coaches(coach_id)
);

-- 7. training_phase_blocks
CREATE TABLE IF NOT EXISTS training_phase_blocks (
    phase_block_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id          text NOT NULL REFERENCES teams(team_id),
    phase_name       text NOT NULL,
    start_date       date NOT NULL,
    end_date         date NOT NULL,
    emphasis         text,
    notes            text,
    created_at       timestamptz DEFAULT now(),
    CHECK (end_date >= start_date)
);

-- Seed current UChicago offseason phases
INSERT INTO training_phase_blocks (team_id, phase_name, start_date, end_date, emphasis)
VALUES
    ('uchicago_baseball', 'Fall GPP', '2025-10-01', '2025-10-28', 'hypertrophy'),
    ('uchicago_baseball', 'Strength Block', '2025-10-29', '2025-12-15', 'strength'),
    ('uchicago_baseball', 'Power Block', '2026-01-05', '2026-02-07', 'power'),
    ('uchicago_baseball', 'Preseason Ramp', '2026-02-08', '2026-02-28', 'maintenance'),
    ('uchicago_baseball', 'In-Season', '2026-03-01', '2026-05-31', 'maintenance')
ON CONFLICT DO NOTHING;

-- 8. Add team_id to existing tables
ALTER TABLE pitchers ADD COLUMN IF NOT EXISTS team_id text DEFAULT 'uchicago_baseball' REFERENCES teams(team_id);
UPDATE pitchers SET team_id = 'uchicago_baseball' WHERE team_id IS NULL;

ALTER TABLE daily_entries ADD COLUMN IF NOT EXISTS team_id text;
UPDATE daily_entries SET team_id = 'uchicago_baseball' WHERE team_id IS NULL;

ALTER TABLE daily_entries ADD COLUMN IF NOT EXISTS active_team_block_id uuid;

ALTER TABLE saved_plans ADD COLUMN IF NOT EXISTS team_id text;
UPDATE saved_plans SET team_id = 'uchicago_baseball' WHERE team_id IS NULL;

ALTER TABLE weekly_summaries ADD COLUMN IF NOT EXISTS team_id text;
UPDATE weekly_summaries SET team_id = 'uchicago_baseball' WHERE team_id IS NULL;

ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS team_id text;
UPDATE chat_messages SET team_id = 'uchicago_baseball' WHERE team_id IS NULL;
