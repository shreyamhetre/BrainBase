-- Real-time updates (Slack Socket Mode, GitLab webhooks) were dropped in favour of scheduled
-- sync plus Sync now (decision 2026-10-24), so their columns go too.

ALTER TABLE connectors DROP COLUMN IF EXISTS events_secret_encrypted;
ALTER TABLE connectors DROP COLUMN IF EXISTS events_status;
ALTER TABLE connectors DROP COLUMN IF EXISTS events_error;
ALTER TABLE connectors DROP COLUMN IF EXISTS last_event_at;
