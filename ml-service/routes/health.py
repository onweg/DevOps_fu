from flask import Blueprint, jsonify
import db

health_bp = Blueprint("health", __name__)


@health_bp.route("/health", methods=["GET"])
def health():
    try:
        db.fetchone("SELECT 1")
        return jsonify({"status": "healthy", "db": "up"}), 200
    except Exception as exc:
        return jsonify({"status": "unhealthy", "db": str(exc)}), 503
