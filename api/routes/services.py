"""
/api/services/* — trusted third-party service whitelist management.

GET    /api/services           List all trusted services
POST   /api/services           Add a trusted service
DELETE /api/services/<id>      Remove a trusted service
"""

from flask import Blueprint, request

import db
from utils import error, log_activity, success

services_bp = Blueprint("services", __name__)


@services_bp.route("/api/services", methods=["GET"])
def list_services():
    try:
        rows = db.fetchall(
            "SELECT * FROM trusted_services WHERE is_active = TRUE ORDER BY added_at DESC"
        )
        return success({"services": rows})
    except Exception as exc:
        return error(f"Database error: {exc}", 500)


@services_bp.route("/api/services", methods=["POST"])
def add_service():
    body = request.get_json(silent=True) or {}
    name = body.get("service_name", "").strip()
    sid  = body.get("service_id")
    url  = body.get("service_url", "").strip()
    desc = body.get("description", "")

    if not name or sid is None:
        return error("service_name and service_id are required", 400)

    try:
        db.execute(
            "INSERT INTO trusted_services (service_name, service_id, service_url, description) VALUES (%s, %s, %s, %s)",
            (name, int(sid), url, desc),
        )
        log_activity("INFO", "SERVICE_ADDED", f"Trusted service added: {name}")
        return success({}, f"Service '{name}' added to whitelist")
    except Exception as exc:
        return error(f"Database error: {exc}", 500)


@services_bp.route("/api/services/<int:service_id>", methods=["DELETE"])
def delete_service(service_id: int):
    try:
        db.execute("UPDATE trusted_services SET is_active = FALSE WHERE id = %s", (service_id,))
        log_activity("WARNING", "SERVICE_REMOVED", f"Service id={service_id} deactivated")
        return success({}, "Service deactivated")
    except Exception as exc:
        return error(f"Database error: {exc}", 500)
