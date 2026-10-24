-- MCP tools as the server describes them: the input form (JSON schema) and whether the tool
-- only reads. Read-only tools are listed but never enabled: reads come from the permission-
-- filtered index, never from a tool connection that sees more than the user may.

ALTER TABLE mcp_tools ADD COLUMN IF NOT EXISTS input_schema jsonb NOT NULL DEFAULT '{}';
ALTER TABLE mcp_tools ADD COLUMN IF NOT EXISTS read_only boolean NOT NULL DEFAULT false;
ALTER TABLE mcp_servers ADD COLUMN IF NOT EXISTS last_checked_at timestamptz;
