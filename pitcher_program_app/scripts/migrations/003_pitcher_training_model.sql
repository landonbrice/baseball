-- Migration: Create pitcher_training_model table
-- Replaces active_flags with consolidated pitcher state + exercise intelligence
-- Applied: 2026-04-01

CREATE TABLE IF NOT EXISTS pitcher_training_model (
  pitcher_id TEXT PRIMARY KEY REFERENCES pitchers(pitcher_id),

  -- Absorbed from active_flags --
  current_arm_feel        INTEGER,
  current_flag_level      TEXT,
  days_since_outing       INTEGER DEFAULT 0,
  last_outing_date        DATE,
  last_outing_pitches     INTEGER,
  phase                   TEXT,
  active_modifications    TEXT[] DEFAULT '{}',
  next_outing_days        INTEGER,
  grip_drop_reported      BOOLEAN DEFAULT FALSE,

  -- Exercise intelligence (new) --
  working_weights         JSONB DEFAULT '{}',
  exercise_preferences    JSONB DEFAULT '{}',
  equipment_constraints   TEXT[] DEFAULT '{}',
  recent_swap_history     JSONB DEFAULT '[]',

  -- Weekly arc (new) --
  current_week_state      JSONB DEFAULT '{}',

  updated_at              TIMESTAMPTZ DEFAULT now()
);

-- Auto-update updated_at on row changes
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_pitcher_training_model_updated_at
  BEFORE UPDATE ON pitcher_training_model
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Enable RLS
ALTER TABLE pitcher_training_model ENABLE ROW LEVEL SECURITY;

-- Service role bypass
CREATE POLICY "Service role full access" ON pitcher_training_model
  FOR ALL USING (true) WITH CHECK (true);
