"""
/api/analysis/* — ML training, prediction, and result retrieval.

POST /api/analysis/train      Train all three ML models
POST /api/analysis/analyze    Classify unanalyzed events, generate alerts
GET  /api/analysis/threats    List threat detections (filtered/paginated)
GET  /api/analysis/metrics    Latest training metrics for all models
GET  /api/analysis/summary    Aggregated threat counts for dashboard charts
"""

import json
import logging

from flask import Blueprint, request

import db
import ml_client
from utils import error, log_activity, success

analysis_bp = Blueprint("analysis", __name__)
logger      = logging.getLogger(__name__)

SEVERITY = {
    "credential_stuffing": "HIGH",
    "token_theft":         "CRITICAL",
    "api_abuse":           "MEDIUM",
    "brute_force":         "HIGH",
    "oauth_hijack":        "CRITICAL",
}

ALERT_THRESHOLD = 0.70


@analysis_bp.route("/api/analysis/train", methods=["POST"])
def train_models():
    try:
        result = ml_client.train()
    except RuntimeError as exc:
        return error(str(exc), 503)

    try:
        for model_name, metrics in result.get("models", {}).items():
            db.execute(
                """
                INSERT INTO model_metrics
                    (model_name, training_samples, test_samples,
                     accuracy, precision_macro, recall_macro, f1_macro,
                     confusion_matrix, class_report)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)
                """,
                (
                    model_name,
                    result.get("training_samples", 0),
                    result.get("test_samples", 0),
                    metrics.get("accuracy", 0),
                    metrics.get("precision", 0),
                    metrics.get("recall", 0),
                    metrics.get("f1", 0),
                    json.dumps(metrics.get("confusion_matrix", [])),
                    json.dumps(metrics.get("class_report", {})),
                ),
            )

        best = max(
            (m.get("accuracy", 0) for m in result.get("models", {}).values()),
            default=0,
        )
        log_activity(
            "INFO", "MODELS_TRAINED",
            f"All 3 models trained. Best accuracy: {best:.1%}",
            {"training_samples": result.get("training_samples")},
        )
    except Exception as exc:
        return error(f"Failed to store metrics: {exc}", 500)

    return success(result, "Models trained successfully")


@analysis_bp.route("/api/analysis/analyze", methods=["POST"])
def analyze_threats():
    try:
        result = ml_client.predict()
    except RuntimeError as exc:
        return error(str(exc), 503)

    alerts_count = _generate_alerts()
    result["alerts_generated"] = alerts_count

    total_threats = sum(
        v for k, v in result.get("detections", {}).items() if k != "normal"
    )
    log_activity(
        "ALERT" if total_threats > 0 else "INFO",
        "ANALYSIS_COMPLETE",
        f"Analyzed {result.get('analyzed', 0)} events. {total_threats} threats detected.",
        {"analyzed": result.get("analyzed"), "detections": result.get("detections")},
    )
    return success(result, f"Analysis complete. {alerts_count} alerts generated.")


@analysis_bp.route("/api/analysis/threats", methods=["GET"])
def get_threats():
    threat_type    = request.args.get("threat_type")
    min_confidence = request.args.get("min_confidence", 0.0, type=float)
    limit          = min(request.args.get("limit", 100, type=int), 500)

    try:
        where  = ["confidence >= %s"]
        params = [min_confidence]

        if threat_type:
            where.append("final_label_name = %s")
            params.append(threat_type)

        where_sql = " AND ".join(where)
        threats = db.fetchall(
            f"SELECT * FROM threat_detections WHERE {where_sql} ORDER BY detected_at DESC LIMIT %s",
            params + [limit],
        )
        total = db.fetchone(
            f"SELECT COUNT(*) AS cnt FROM threat_detections WHERE {where_sql}", params
        )
        return success({"total": total["cnt"] if total else 0, "threats": threats})
    except Exception as exc:
        return error(f"Database error: {exc}", 500)


@analysis_bp.route("/api/analysis/metrics", methods=["GET"])
def get_metrics():
    try:
        rows = db.fetchall(
            """
            SELECT DISTINCT ON (model_name) *
            FROM model_metrics
            ORDER BY model_name, trained_at DESC
            """
        )
        if not rows:
            return error("No trained models found. Call POST /api/analysis/train first.", 404)
        return success({"models": {r["model_name"]: r for r in rows}})
    except Exception as exc:
        return error(f"Database error: {exc}", 500)


@analysis_bp.route("/api/analysis/summary", methods=["GET"])
def get_summary():
    try:
        rows = db.fetchall(
            """
            SELECT final_label_name AS threat_type, COUNT(*) AS count
            FROM threat_detections
            GROUP BY final_label_name
            ORDER BY count DESC
            """
        )
        return success({"threat_distribution": rows})
    except Exception as exc:
        return error(f"Database error: {exc}", 500)


def _generate_alerts():
    count = 0
    try:
        new_detections = db.fetchall(
            """
            SELECT td.*
            FROM   threat_detections td
            WHERE  td.final_label_name != 'normal'
              AND  td.confidence >= %s
              AND  NOT EXISTS (SELECT 1 FROM alerts a WHERE a.detection_id = td.id)
            """,
            (ALERT_THRESHOLD,),
        )

        for det in new_detections:
            threat_type = det.get("final_label_name", "unknown")
            severity    = SEVERITY.get(threat_type, "MEDIUM")
            db.execute(
                """
                INSERT INTO alerts
                    (threat_type, severity, event_id, detection_id, message, confidence)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    threat_type,
                    severity,
                    det.get("event_id"),
                    det.get("id"),
                    f"{threat_type.replace('_', ' ').title()} detected "
                    f"— confidence {det.get('confidence', 0):.0%}",
                    det.get("confidence", 0),
                ),
            )
            count += 1
    except Exception as exc:
        logger.warning("Alert generation failed: %s", exc)
    return count
