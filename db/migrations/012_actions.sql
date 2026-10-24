-- Actions GitMore proposes from a chat message. Nothing is written to a tool until the person
-- confirms; the row then records what ran, its result, and who asked (the audit trail).

CREATE TABLE IF NOT EXISTS actions (
    id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       uuid        NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    tool_id       uuid        REFERENCES mcp_tools (id) ON DELETE SET NULL,
    server_name   text        NOT NULL,
    tool_name     text        NOT NULL,
    message       text        NOT NULL,                  -- what the person asked
    summary       text        NOT NULL,                  -- one line, e.g. Create issue "..." in engineering
    arguments     jsonb       NOT NULL,                  -- as proposed, then as confirmed (after edits)
    status        text        NOT NULL DEFAULT 'proposed'
                  CHECK (status IN ('proposed', 'done', 'failed', 'cancelled')),
    result_text   text,
    result_url    text,
    created_at    timestamptz NOT NULL DEFAULT now(),
    decided_at    timestamptz
);

CREATE INDEX IF NOT EXISTS actions_user ON actions (user_id, created_at DESC);
