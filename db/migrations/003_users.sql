-- People who can log in. roles holds content roles (engineer, hr, manager, security, sales);
-- everyone can also read chunks marked 'all'. is_admin grants the admin console and is
-- separate from content roles.

CREATE TABLE IF NOT EXISTS users (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    email           text        NOT NULL UNIQUE,
    name            text        NOT NULL,
    password_hash   text        NOT NULL,
    roles           text[]      NOT NULL DEFAULT '{}',
    is_admin        boolean     NOT NULL DEFAULT false,
    team            text,
    title           text,
    slack_handle    text,           -- links a user to their synthetic Slack messages
    gitlab_username text,           -- links a user to their synthetic issues and wiki pages
    is_active       boolean     NOT NULL DEFAULT true,
    created_at      timestamptz NOT NULL DEFAULT now(),
    last_login_at   timestamptz
);

-- Emails are compared case-insensitively
CREATE UNIQUE INDEX IF NOT EXISTS users_email_lower ON users (lower(email));
