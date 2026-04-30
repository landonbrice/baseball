-- Keep coach-scoped daily-entry reads in sync with player check-in writes.

UPDATE daily_entries AS de
SET team_id = p.team_id
FROM pitchers AS p
WHERE de.pitcher_id = p.pitcher_id
  AND (de.team_id IS NULL OR de.team_id = '');

CREATE OR REPLACE FUNCTION set_daily_entry_team_id_from_pitcher()
RETURNS trigger AS $$
BEGIN
    IF NEW.team_id IS NULL OR NEW.team_id = '' THEN
        SELECT team_id
        INTO NEW.team_id
        FROM pitchers
        WHERE pitcher_id = NEW.pitcher_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS daily_entries_set_team_id ON daily_entries;
CREATE TRIGGER daily_entries_set_team_id
BEFORE INSERT OR UPDATE OF pitcher_id, team_id ON daily_entries
FOR EACH ROW
EXECUTE FUNCTION set_daily_entry_team_id_from_pitcher();
