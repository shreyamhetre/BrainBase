-- The Knowledge library: documents people add (PDF, Word, or a link to a file in GitLab).
-- They are stored like every other document (documents + chunks, with allowed roles), plus who
-- added them; uploaded files keep their original bytes so citations can open the real file.

ALTER TABLE roles ADD COLUMN IF NOT EXISTS can_add_documents boolean NOT NULL DEFAULT false;

ALTER TABLE documents ADD COLUMN IF NOT EXISTS added_by uuid REFERENCES users (id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS documents_added_by ON documents (added_by) WHERE added_by IS NOT NULL;

CREATE TABLE IF NOT EXISTS document_files (
    document_id   bigint      PRIMARY KEY REFERENCES documents (id) ON DELETE CASCADE,
    file_name     text        NOT NULL,
    content_type  text        NOT NULL,
    size_bytes    int         NOT NULL,
    data          bytea       NOT NULL
);
