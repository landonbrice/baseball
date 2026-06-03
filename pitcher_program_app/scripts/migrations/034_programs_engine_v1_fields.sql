-- Program Engine v1 — additive fields on the `programs` table (Task 3.4).
-- Three new columns capture the engine's authoring provenance + the knowledge
-- pack hash so we can detect "stale program after knowledge update" downstream.
--
-- Idempotent — uses IF NOT EXISTS so re-running is a no-op.
ALTER TABLE programs ADD COLUMN IF NOT EXISTS knowledge_version text NULL;
ALTER TABLE programs ADD COLUMN IF NOT EXISTS generation_provenance jsonb NULL DEFAULT '{}'::jsonb;
ALTER TABLE programs ADD COLUMN IF NOT EXISTS engine_version text NULL DEFAULT 'v1';

-- Helpful for "which programs were authored by which knowledge pack" queries
-- once the engine has been live for a while.
CREATE INDEX IF NOT EXISTS programs_knowledge_version_idx
    ON programs (knowledge_version)
    WHERE knowledge_version IS NOT NULL;
