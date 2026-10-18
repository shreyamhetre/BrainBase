-- People mentioned in a chunk (names and @usernames from member/team shortcodes),
-- used later for "who knows this?".

ALTER TABLE chunks ADD COLUMN IF NOT EXISTS people text[] NOT NULL DEFAULT '{}';

CREATE INDEX IF NOT EXISTS chunks_people ON chunks USING gin (people);
