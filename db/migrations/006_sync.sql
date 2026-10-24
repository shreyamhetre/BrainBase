-- Connector sync: each synced document points at the channel or project it came from, so
-- changing who can read it (or removing the connector) updates or removes its chunks.
-- sync_runs records every sync for the Connectors page.

ALTER TABLE documents ADD COLUMN IF NOT EXISTS access_id uuid REFERENCES source_access (id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS documents_access ON documents (access_id);

CREATE TABLE IF NOT EXISTS sync_runs (
    id            bigserial   PRIMARY KEY,
    connector_id  uuid        NOT NULL REFERENCES connectors (id) ON DELETE CASCADE,
    trigger       text        NOT NULL,                  -- schedule, manual, event, script
    started_at    timestamptz NOT NULL DEFAULT now(),
    finished_at   timestamptz,
    status        text        NOT NULL DEFAULT 'running', -- running, ok, error
    seen          int         NOT NULL DEFAULT 0,        -- documents found in the tool
    changed       int         NOT NULL DEFAULT 0,        -- new or edited, re-embedded
    deleted       int         NOT NULL DEFAULT 0,
    chunks        int         NOT NULL DEFAULT 0,
    error         text
);

CREATE INDEX IF NOT EXISTS sync_runs_connector ON sync_runs (connector_id, started_at DESC);
