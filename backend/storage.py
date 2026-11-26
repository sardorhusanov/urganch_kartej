"""SQLite locally and PostgreSQL for the Vercel deployment."""
from contextlib import contextmanager
import os
import sqlite3


class PostgresConnection:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, sql, params=()):
        # Serialize read-modify-write operations just like SQLite's BEGIN IMMEDIATE.
        if sql == "BEGIN IMMEDIATE":
            return self.connection.execute("SELECT pg_advisory_xact_lock(72734519)")
        return self.connection.execute(sql.replace("?", "%s"), params)


@contextmanager
def open_database(directory):
    url = os.getenv("DATABASE_URL")
    if url:
        import psycopg
        with psycopg.connect(url, connect_timeout=12) as conn:
            yield PostgresConnection(conn)
    else:
        if os.getenv("VERCEL"):
            raise RuntimeError("Configure DATABASE_URL for durable storage.")
        conn = sqlite3.connect(directory / "kartej.sqlite3")
        try:
            with conn:
                yield conn
        finally:
            conn.close()
