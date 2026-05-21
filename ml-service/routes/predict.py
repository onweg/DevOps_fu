from flask import Blueprint, current_app, jsonify
import predictor

predict_bp = Blueprint("predict", __name__)


@predict_bp.route("/predict", methods=["POST"])
def do_predict():
    model_dir = current_app.config["MODEL_DIR"]
    try:
        result = predictor.predict(model_dir)
        return jsonify({"status": "success", **result}), 200
    except FileNotFoundError as exc:
        return jsonify({"status": "error", "error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"status": "error", "error": str(exc)}), 500
