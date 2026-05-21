from flask import Blueprint, render_template

import db

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/", methods=["GET"])
def index():
    stats = db.fetchone(
        """
        SELECT
            (SELECT COUNT(*) FROM access_events)              AS total_events,
            (SELECT COUNT(*) FROM threat_detections)          AS total_detections,
            (SELECT COUNT(*) FROM alerts WHERE NOT acknowledged) AS active_alerts,
            (SELECT COUNT(*) FROM trusted_services WHERE is_active) AS trusted_services
        """
    ) or {}
    return render_template("dashboard.html", stats=stats)
