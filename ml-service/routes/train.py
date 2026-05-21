import os
from flask import Blueprint, current_app, jsonify
import trainer

train_bp = Blueprint("train", __name__)


@train_bp.route("/train", methods=["POST"])
def do_train():
    model_dir = current_app.config["MODEL_DIR"]
    try:
        result = trainer.train(model_dir)
        return jsonify({"status": "success", **result}), 200
    except ValueError as exc:
        return jsonify({"status": "error", "error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"status": "error", "error": str(exc)}), 500
