"""
/api/data/* — access event generation and management.

POST   /api/data/generate          Generate synthetic access events
GET    /api/data/events             List events (paginated, filterable)
DELETE /api/data/events             Clear all events and related records
"""

import logging

from flask import Blueprint, request

import db
import ml_client
from utils import error, log_activity, success

data_bp = Blueprint("data", __name__)
logger  = logging.getLogger(__name__)


@data_bp.route("/api/data/generate", methods=["POST"])
def generate_data():
    body  = request.get_json(silent=True) or {}
    count = int(body.get("count", 1000))
    count = max(1, min(count, 10_000))

    try:
        result = ml_client.generate(count)
    except RuntimeError as exc:
        return error(str(exc), 503)

    log_activity(
        "INFO", "DATA_GENERATED",
        f"Generated {result.get('generated', 0)} synthetic access events",
        {"count": result.get("generated"), "total": result.get("total")},
    )
    return success(result, f"Generated {result.get('generated', 0)} access events")


@data_bp.route("/api/data/events", methods=["GET"])
def get_events():
    page       = max(request.args.get("page", 1, type=int), 1)
    limit      = min(request.args.get("limit", 50, type=int), 200)
    label_name = request.args.get("label")
    offset     = (page - 1) * limit

    try:
        where, params = [], []
        if label_name:
            where.append("label_name = %s")
            params.append(label_name)

        where_sql = ("WHERE " + " AND ".join(where)) if where else ""
        events = db.fetchall(
            f"SELECT * FROM access_events {where_sql} ORDER BY created_at DESC LIMIT %s OFFSET %s",
            params + [limit, offset],
        )
        total = db.fetchone(f"SELECT COUNT(*) AS cnt FROM access_events {where_sql}", params)
        return success({"total": total["cnt"] if total else 0, "page": page, "events": events})
    except Exception as exc:
        return error(f"Database error: {exc}", 500)


@data_bp.route("/api/data/events", methods=["DELETE"])
def delete_events():
    try:
        db.execute("DELETE FROM alerts")
        db.execute("DELETE FROM threat_detections")
        db.execute("DELETE FROM access_events")
        log_activity("WARNING", "DATA_CLEARED", "All access events and detections deleted")
        return success({}, "All data cleared")
    except Exception as exc:
        return error(f"Database error: {exc}", 500)
