"""PostgreSQL connection helpers for the ML service."""

import logging
import os

import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)

_conn = None


def get_db():
    global _conn
    if _conn is None or _conn.closed:
        _conn = psycopg2.connect(
            os.environ["DATABASE_URL"],
            cursor_factory=psycopg2.extras.RealDictCursor,
        )
        logger.info("DB connection established")
    return _conn


def fetchall(sql: str, params=None):
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]


def fetchone(sql: str, params=None):
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
        return dict(row) if row else None
