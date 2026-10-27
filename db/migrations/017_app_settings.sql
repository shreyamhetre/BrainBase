-- Settings managed in the app (RAG settings, background job status). One row per key.

CREATE TABLE IF NOT EXISTS app_settings (
    key         text        PRIMARY KEY,
    value       jsonb       NOT NULL,
    updated_by  uuid        REFERENCES users (id) ON DELETE SET NULL,
    updated_at  timestamptz NOT NULL DEFAULT now()
);
