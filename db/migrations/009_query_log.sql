-- One row per question: who asked, what it cost and how long it took. GitMore's own permanent
-- record, independent of Langfuse (which keeps the detailed step-by-step traces).

CREATE TABLE IF NOT EXISTS query_log (
    id                 bigserial   PRIMARY KEY,
    user_id            uuid        REFERENCES users (id) ON DELETE SET NULL,
    question           text        NOT NULL,
    answer             text        NOT NULL,
    found              boolean     NOT NULL,             -- false when it said it couldn't find the answer
    sources            jsonb       NOT NULL DEFAULT '[]', -- [{source, title, link, cited}]
    model              text        NOT NULL,
    prompt_tokens      int         NOT NULL DEFAULT 0,
    completion_tokens  int         NOT NULL DEFAULT 0,
    cost_usd           numeric(12, 6) NOT NULL DEFAULT 0,
    seconds            real        NOT NULL,
    trace_id           text,                             -- Langfuse trace, when Langfuse was reachable
    trace_url          text,
    created_at         timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS query_log_created ON query_log (created_at DESC);
CREATE INDEX IF NOT EXISTS query_log_user ON query_log (user_id, created_at DESC);
