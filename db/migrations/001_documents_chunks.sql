-- Documents (one row per source page / message / ticket) and their chunks.

CREATE TABLE IF NOT EXISTS documents (
    id            bigserial PRIMARY KEY,
    source        text        NOT NULL,                  -- handbook, docs, issue, slack, notion, jira
    external_id   text        NOT NULL,                  -- file path, message id, ticket key
    title         text        NOT NULL,
    url           text,
    section       text,                                  -- top-level area, e.g. total-rewards
    doc_type      text,                                  -- page, design_doc, ...
    status        text,                                  -- design doc status: proposed, implemented, ...
    owners        text[]      NOT NULL DEFAULT '{}',     -- authors / DRIs, for "who knows this?"
    allowed_roles text[]      NOT NULL DEFAULT '{all}',  -- who may see it
    updated_at    timestamptz,                           -- last change in the source
    content_hash  text        NOT NULL,                  -- skip unchanged docs on re-sync
    metadata      jsonb       NOT NULL DEFAULT '{}',
    synced_at     timestamptz NOT NULL DEFAULT now(),
    UNIQUE (source, external_id)
);

CREATE TABLE IF NOT EXISTS chunks (
    id            bigserial PRIMARY KEY,
    document_id   bigint      NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    chunk_index   int         NOT NULL,                  -- order within the document
    heading_path  text,                                  -- "Total Rewards > Benefits > PTO"
    anchor        text,                                  -- #heading for citation links
    content       text        NOT NULL,
    token_count   int         NOT NULL,
    embedding     vector(1024),                          -- BGE-M3 dense vector
    search_tsv    tsvector GENERATED ALWAYS AS (
                      to_tsvector('english', coalesce(heading_path, '') || ' ' || content)
                  ) STORED,

    -- Copied from documents so search can filter in one query, without a join
    source        text        NOT NULL,
    section       text,
    status        text,
    allowed_roles text[]      NOT NULL,
    updated_at    timestamptz,

    UNIQUE (document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS chunks_search_tsv     ON chunks USING gin (search_tsv);
CREATE INDEX IF NOT EXISTS chunks_allowed_roles  ON chunks USING gin (allowed_roles);
CREATE INDEX IF NOT EXISTS chunks_source_section ON chunks (source, section);
