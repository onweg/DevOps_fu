from flask import Blueprint, request, jsonify
import generator

generate_bp = Blueprint("generate", __name__)


@generate_bp.route("/generate", methods=["POST"])
def do_generate():
    body  = request.get_json(silent=True) or {}
    count = int(body.get("count", 1000))
    count = max(1, min(count, 10_000))
    try:
        result = generator.generate(count)
        return jsonify({"status": "success", **result}), 200
    except Exception as exc:
        return jsonify({"status": "error", "error": str(exc)}), 500
