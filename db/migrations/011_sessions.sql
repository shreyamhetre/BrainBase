-- Server-side login sessions. Each JWT carries its session id (jti); every request checks the
-- session is still open, so logging out (or a password change) makes old tokens useless at once
-- instead of leaving them valid until they expire.

CREATE TABLE IF NOT EXISTS sessions (
    id           uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      uuid        NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    created_at   timestamptz NOT NULL DEFAULT now(),
    expires_at   timestamptz NOT NULL,
    revoked_at   timestamptz,
    user_agent   text
);

CREATE INDEX IF NOT EXISTS sessions_user ON sessions (user_id) WHERE revoked_at IS NULL;
