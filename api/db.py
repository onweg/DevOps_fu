"""PostgreSQL connection helpers for the API service."""

import logging

import psycopg2
import psycopg2.extras
from flask import current_app, g

logger = logging.getLogger(__name__)


def get_db():
    if "db" not in g:
        g.db = psycopg2.connect(
            current_app.config["DATABASE_URL"],
            cursor_factory=psycopg2.extras.RealDictCursor,
        )
    return g.db


def close_db(exc=None):
    db = g.pop("db", None)
    if db is not None and not db.closed:
        db.close()


def init_app(app):
    app.teardown_appcontext(close_db)


def execute(sql: str, params=None):
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(sql, params)
    conn.commit()


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
