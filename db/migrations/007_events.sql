-- Near-real-time updates. Slack: an app-level token (xapp-…) for Socket Mode.
-- GitLab: the secret GitLab sends with each webhook call. Both Fernet-encrypted.

ALTER TABLE connectors ADD COLUMN IF NOT EXISTS events_secret_encrypted text;
ALTER TABLE connectors ADD COLUMN IF NOT EXISTS events_status text NOT NULL DEFAULT 'off';  -- off, listening, error
ALTER TABLE connectors ADD COLUMN IF NOT EXISTS events_error text;
ALTER TABLE connectors ADD COLUMN IF NOT EXISTS last_event_at timestamptz;
