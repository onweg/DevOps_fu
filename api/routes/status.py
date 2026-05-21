import logging

import requests
from flask import Blueprint, current_app

import db
from utils import error, success

status_bp = Blueprint("status", __name__)
logger    = logging.getLogger(__name__)


@status_bp.route("/api/status", methods=["GET"])
def get_status():
    db_status, ml_status = "up", "up"
    db_info = {}

    try:
        row = db.fetchone(
            """
            SELECT
                (SELECT COUNT(*) FROM access_events)    AS total_events,
                (SELECT COUNT(*) FROM threat_detections) AS total_threats,
                (SELECT COUNT(*) FROM alerts WHERE NOT acknowledged) AS active_alerts,
                (SELECT COUNT(*) FROM model_metrics) > 0 AS models_trained
            """
        )
        db_info = dict(row) if row else {}
    except Exception as exc:
        db_status = str(exc)
        logger.warning("DB status check failed: %s", exc)

    try:
        ml_url = current_app.config["ML_SERVICE_URL"].rstrip("/") + "/health"
        requests.get(ml_url, timeout=3).raise_for_status()
    except Exception as exc:
        ml_status = str(exc)

    overall = "healthy" if db_status == "up" and ml_status == "up" else "degraded"
    return success(
        {
            "services": {"api": "up", "database": db_status, "ml_service": ml_status},
            "database":  db_info,
        },
        overall,
    )
