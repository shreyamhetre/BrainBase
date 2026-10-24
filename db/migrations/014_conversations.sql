-- Saved chats. Each person sees only their own; follow-up questions use the last few messages,
-- always read from here (never trusted from the browser).

CREATE TABLE IF NOT EXISTS conversations (
    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     uuid        NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    title       text        NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS conversations_user ON conversations (user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS messages (
    id               bigserial   PRIMARY KEY,
    conversation_id  uuid        NOT NULL REFERENCES conversations (id) ON DELETE CASCADE,
    role             text        NOT NULL CHECK (role IN ('user', 'assistant')),
    content          text        NOT NULL,      -- the question, or the answer / action summary / clarifying question
    kind             text,                      -- assistant only: answer, action, clarify
    payload          jsonb       NOT NULL DEFAULT '{}',  -- sources, action id, timing, tokens
    created_at       timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS messages_conversation ON messages (conversation_id, id);
