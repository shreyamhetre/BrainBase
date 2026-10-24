-- Failed logins, for rate limiting: too many for one email, or from one address, in a short
-- window and further attempts are refused for a while. Old rows are pruned on each failure.

CREATE TABLE IF NOT EXISTS login_failures (
    id          bigserial   PRIMARY KEY,
    email       text        NOT NULL,
    ip          text        NOT NULL,
    at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS login_failures_email ON login_failures (email, at DESC);
CREATE INDEX IF NOT EXISTS login_failures_ip ON login_failures (ip, at DESC);
