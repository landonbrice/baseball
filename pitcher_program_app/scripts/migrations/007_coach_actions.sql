-- pitcher_program_app/scripts/migrations/007_coach_actions.sql
create table if not exists coach_actions (
  id bigserial primary key,
  coach_id uuid references coaches(coach_id),
  pitcher_id text references pitchers(pitcher_id),
  action_type text not null,
  message_text text,
  telegram_message_id bigint,
  metadata jsonb,
  created_at timestamptz default now()
);

create index if not exists coach_actions_pitcher_type_time_idx
  on coach_actions(pitcher_id, action_type, created_at desc);
