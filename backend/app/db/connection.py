"""Database connections with pgvector support."""

import psycopg
from pgvector.psycopg import register_vector

from app.config import DATABASE_URL


def connect() -> psycopg.Connection:
    conn = psycopg.connect(DATABASE_URL)
    register_vector(conn)
    return conn
