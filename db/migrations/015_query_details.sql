-- The query inspector: what happened inside each message, for the admin.
-- route: chat, answer, action, choose, clarify. search_question: what was actually searched
-- (a follow-up rewritten to stand alone). details: the chunks found with every score, and later
-- the evidence gate's decisions.

ALTER TABLE query_log ADD COLUMN IF NOT EXISTS route text;
ALTER TABLE query_log ADD COLUMN IF NOT EXISTS search_question text;
ALTER TABLE query_log ADD COLUMN IF NOT EXISTS details jsonb NOT NULL DEFAULT '{}';
