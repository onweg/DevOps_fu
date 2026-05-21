"""JSON response helpers and activity logging."""

import logging

from flask import jsonify

import db

logger = logging.getLogger(__name__)


def success(data: dict = None, message: str = "OK") -> tuple:
    body = {"status": "success", "message": message}
    if data:
        body.update(data)
    return jsonify(body), 200


def error(message: str, code: int = 400) -> tuple:
    return jsonify({"status": "error", "error": message}), code


def log_activity(level: str, action: str, message: str, details: dict = None):
    import json
    try:
        db.execute(
            "INSERT INTO activity_logs (level, action, message, details) VALUES (%s, %s, %s, %s::jsonb)",
            (level, action, message, json.dumps(details or {})),
        )
    except Exception as exc:
        logger.warning("Failed to write activity log: %s", exc)
