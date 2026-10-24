-- Settings managed in the app instead of code: roles, connectors with encrypted tokens,
-- which roles can read each channel or project, and MCP servers with their tools.

CREATE TABLE IF NOT EXISTS roles (
    name        text        PRIMARY KEY CHECK (name ~ '^[a-z][a-z0-9-]{1,30}$'),
    description text        NOT NULL DEFAULT '',
    created_at  timestamptz NOT NULL DEFAULT now()
);

INSERT INTO roles (name, description) VALUES
    ('engineer', 'Engineering channels, issues and runbooks'),
    ('hr',       'People team documents, such as salary bands'),
    ('manager',  'Leadership plans and manager channels'),
    ('security', 'Security incidents and confidential security issues'),
    ('sales',    'Sales channels, deals and playbooks')
ON CONFLICT (name) DO NOTHING;

-- One row per connected tool. The token is Fernet-encrypted with SECRETS_KEY from .env
-- and never sent to the browser.
CREATE TABLE IF NOT EXISTS connectors (
    id                     uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    kind                   text        NOT NULL CHECK (kind IN ('slack', 'gitlab')),
    name                   text        NOT NULL,
    config                 jsonb       NOT NULL DEFAULT '{}',    -- non-secret: GitLab URL and group, Slack team name
    token_encrypted        text        NOT NULL,
    enabled                boolean     NOT NULL DEFAULT true,
    sync_interval_minutes  int         NOT NULL DEFAULT 60 CHECK (sync_interval_minutes BETWEEN 5 AND 1440),
    status                 text        NOT NULL DEFAULT 'connected',  -- connected, error
    last_error             text,
    last_checked_at        timestamptz,
    last_sync_at           timestamptz,
    created_by             uuid        REFERENCES users (id) ON DELETE SET NULL,
    created_at             timestamptz NOT NULL DEFAULT now()
);

-- Channels and projects a connector found, and which roles may read them.
-- New ones start with no roles: only admins can read them until they are mapped.
CREATE TABLE IF NOT EXISTS source_access (
    id             uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    connector_id   uuid        NOT NULL REFERENCES connectors (id) ON DELETE CASCADE,
    container_id   text        NOT NULL,                 -- Slack channel id or GitLab project id
    container_name text        NOT NULL,                 -- #hr-private, engineering
    container_kind text        NOT NULL,                 -- public_channel, private_channel, project
    allowed_roles  text[]      NOT NULL DEFAULT '{}',    -- 'all' means everyone
    discovered_at  timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now(),
    UNIQUE (connector_id, container_id)
);

CREATE TABLE IF NOT EXISTS mcp_servers (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    kind            text        NOT NULL CHECK (kind IN ('gitlab', 'slack', 'custom')),
    name            text        NOT NULL,
    url             text        NOT NULL,
    auth_encrypted  text,                                -- OAuth or API token, Fernet-encrypted
    enabled         boolean     NOT NULL DEFAULT true,
    status          text        NOT NULL DEFAULT 'not_connected',
    last_error      text,
    created_by      uuid        REFERENCES users (id) ON DELETE SET NULL,
    created_at      timestamptz NOT NULL DEFAULT now()
);

-- Tools a server offers. Off until an admin turns them on and picks who may use them.
CREATE TABLE IF NOT EXISTS mcp_tools (
    id             uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    server_id      uuid        NOT NULL REFERENCES mcp_servers (id) ON DELETE CASCADE,
    name           text        NOT NULL,
    description    text        NOT NULL DEFAULT '',
    enabled        boolean     NOT NULL DEFAULT false,
    allowed_roles  text[]      NOT NULL DEFAULT '{}',
    UNIQUE (server_id, name)
);
