-- Access requests: a user asks the admin for a content role, with a reason.
-- Activity log: who changed what (roles, accounts, requests, profiles), for the admin console.

CREATE TABLE IF NOT EXISTS access_requests (
    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     uuid        NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    role        text        NOT NULL,
    reason      text        NOT NULL,
    status      text        NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'denied', 'cancelled')),
    decided_by  uuid        REFERENCES users (id) ON DELETE SET NULL,
    decided_at  timestamptz,
    note        text,                                -- the admin's reply, shown to the user
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- One open request per user and role
CREATE UNIQUE INDEX IF NOT EXISTS access_requests_one_pending
    ON access_requests (user_id, role) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS access_requests_status ON access_requests (status, created_at DESC);

CREATE TABLE IF NOT EXISTS audit_log (
    id          bigserial   PRIMARY KEY,
    actor_id    uuid        REFERENCES users (id) ON DELETE SET NULL,
    action      text        NOT NULL,                -- e.g. user.roles, user.active, request.approved
    target_id   uuid        REFERENCES users (id) ON DELETE SET NULL,
    details     jsonb       NOT NULL DEFAULT '{}',
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS audit_log_created ON audit_log (created_at DESC);
