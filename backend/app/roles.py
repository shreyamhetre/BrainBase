"""Content roles, stored in the roles table so admins can add them in the app.

'all' is not a role: it marks content everyone can read.
"""

import psycopg


def content_roles(conn: psycopg.Connection) -> list[str]:
    return [row[0] for row in conn.execute("SELECT name FROM roles ORDER BY name")]
