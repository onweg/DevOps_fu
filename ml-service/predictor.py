"""
Load trained classifiers and classify every unclassified access_events row.

Ensemble: majority vote across GradientBoosting, MLP, and K-Means.
GradientBoosting wins ties (highest accuracy on this dataset).
Confidence = mean predict_proba of GB and MLP for the winning class
(K-Means does not produce probabilities natively).
"""

import logging
import os

import joblib
import numpy as np
import psycopg2.extras

from db import fetchall, get_db
from features import FEATURE_COLUMNS, LABEL_NAMES

logger = logging.getLogger(__name__)


def _load_models(model_dir: str):
    scaler_path = os.path.join(model_dir, "scaler.pkl")
    if not os.path.exists(scaler_path):
        raise FileNotFoundError("scaler.pkl not found — train the models first")

    scaler         = joblib.load(scaler_path)
    gb             = joblib.load(os.path.join(model_dir, "gradient_boosting.pkl"))
    mlp            = joblib.load(os.path.join(model_dir, "mlp.pkl"))
    kmeans         = joblib.load(os.path.join(model_dir, "kmeans.pkl"))
    kmeans_labels  = joblib.load(os.path.join(model_dir, "kmeans_labels.pkl"))

    logger.info("Models loaded: gradient_boosting, mlp, kmeans")
    return scaler, gb, mlp, kmeans, kmeans_labels


def predict(model_dir: str) -> dict:
    scaler, gb, mlp, kmeans, kmeans_labels = _load_models(model_dir)

    cols = ", ".join(FEATURE_COLUMNS)
    rows = fetchall(
        f"""
        SELECT ae.id, {cols}
        FROM   access_events ae
        LEFT JOIN threat_detections td ON td.event_id = ae.id
        WHERE  td.id IS NULL
        ORDER  BY ae.id
        """
    )

    if not rows:
        already = fetchall("SELECT COUNT(*) AS n FROM threat_detections")[0]["n"]
        logger.info("No unclassified events (already classified: %d)", already)
        return {"analyzed": 0, "skipped_already_classified": int(already), "detections": {}}

    event_ids = [r["id"] for r in rows]
    X   = np.array([[r[c] for c in FEATURE_COLUMNS] for r in rows], dtype=np.float64)
    X_s = scaler.transform(X)

    # Predictions and probabilities
    gb_preds   = gb.predict(X_s)
    mlp_preds  = mlp.predict(X_s)
    gb_probas  = gb.predict_proba(X_s)   # (n, 6)
    mlp_probas = mlp.predict_proba(X_s)  # (n, 6)

    km_clusters = kmeans.predict(X_s)
    km_preds    = np.array([kmeans_labels.get(c, 0) for c in km_clusters])

    # Majority vote; GB wins ties
    gb_classes  = list(gb.classes_)
    mlp_classes = list(mlp.classes_)

    records = []
    detection_counts: dict = {}

    for i, event_id in enumerate(event_ids):
        gb_l  = int(gb_preds[i])
        mlp_l = int(mlp_preds[i])
        km_l  = int(km_preds[i])

        votes  = [gb_l, mlp_l, km_l]
        counts: dict = {}
        for v in votes:
            counts[v] = counts.get(v, 0) + 1
        final_l = max(counts, key=lambda k: (counts[k], k == gb_l))

        # Confidence from GB and MLP probas only
        conf = _confidence(i, final_l, gb_probas, gb_classes, mlp_probas, mlp_classes)
        agreement = (gb_l == mlp_l == km_l)

        records.append((
            event_id,
            gb_l,    LABEL_NAMES[gb_l],
            mlp_l,   LABEL_NAMES[mlp_l],
            km_l,    LABEL_NAMES[km_l],
            final_l, LABEL_NAMES[final_l],
            conf,
            agreement,
        ))
        detection_counts[LABEL_NAMES[final_l]] = \
            detection_counts.get(LABEL_NAMES[final_l], 0) + 1

    conn = get_db()
    with conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            """
            INSERT INTO threat_detections
                (event_id,
                 gb_label, gb_label_name,
                 mlp_label, mlp_label_name,
                 km_label, km_label_name,
                 final_label, final_label_name,
                 confidence, model_agreement)
            VALUES %s
            """,
            records,
            page_size=500,
        )
    conn.commit()

    logger.info("Inserted %d threat_detections rows", len(records))
    return {
        "analyzed":                   len(records),
        "skipped_already_classified": 0,
        "detections":                 detection_counts,
    }


def _confidence(i, label, gb_probas, gb_classes, mlp_probas, mlp_classes) -> float:
    total, n = 0.0, 0
    for probas, classes in [(gb_probas, gb_classes), (mlp_probas, mlp_classes)]:
        if label in classes:
            idx = classes.index(label)
            total += probas[i][idx]
            n += 1
    return round(total / n, 4) if n else 0.0
