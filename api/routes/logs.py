"""
/api/logs   — activity log management
/api/alerts — security alert management
"""

from flask import Blueprint, request

import db
from utils import error, success

logs_bp = Blueprint("logs", __name__)


@logs_bp.route("/api/logs", methods=["GET"])
def get_logs():
    level  = request.args.get("level")
    page   = max(request.args.get("page", 1, type=int), 1)
    limit  = min(request.args.get("limit", 50, type=int), 200)
    offset = (page - 1) * limit

    try:
        where, params = [], []
        if level:
            where.append("level = %s")
            params.append(level.upper())

        where_sql = ("WHERE " + " AND ".join(where)) if where else ""
        logs = db.fetchall(
            f"SELECT * FROM activity_logs {where_sql} ORDER BY created_at DESC LIMIT %s OFFSET %s",
            params + [limit, offset],
        )
        total = db.fetchone(f"SELECT COUNT(*) AS cnt FROM activity_logs {where_sql}", params)
        return success({"total": total["cnt"] if total else 0, "logs": logs})
    except Exception as exc:
        return error(f"Database error: {exc}", 500)


@logs_bp.route("/api/logs", methods=["DELETE"])
def clear_logs():
    try:
        db.execute("DELETE FROM activity_logs")
        return success({}, "Activity log cleared")
    except Exception as exc:
        return error(f"Database error: {exc}", 500)


@logs_bp.route("/api/alerts", methods=["GET"])
def get_alerts():
    try:
        alerts = db.fetchall(
            """
            SELECT * FROM alerts
            WHERE NOT acknowledged
            ORDER BY
                CASE severity
                    WHEN 'CRITICAL' THEN 1
                    WHEN 'HIGH'     THEN 2
                    WHEN 'MEDIUM'   THEN 3
                    ELSE 4
                END,
                created_at DESC
            LIMIT 100
            """
        )
        return success({"alerts": alerts, "count": len(alerts)})
    except Exception as exc:
        return error(f"Database error: {exc}", 500)


@logs_bp.route("/api/alerts/<int:alert_id>/acknowledge", methods=["PATCH"])
def acknowledge_alert(alert_id: int):
    try:
        db.execute(
            "UPDATE alerts SET acknowledged = TRUE, acknowledged_at = NOW() WHERE id = %s",
            (alert_id,),
        )
        return success({}, f"Alert {alert_id} acknowledged")
    except Exception as exc:
        return error(f"Database error: {exc}", 500)
