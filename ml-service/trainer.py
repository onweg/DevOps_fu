"""
Train three classifiers on access_events data and persist models to disk.

Algorithms:
  - GradientBoosting (бустинг)           — primary supervised classifier
  - MLP Neural Network (многослойный перцептрон) — deep pattern recognition
  - K-Means (кластеризация)              — clustering-based classifier (unsupervised)

K-Means is used as a classifier by labelling each cluster with the majority
ground-truth class from training data, then assigning new samples to the
nearest centroid.
"""

import logging
import os

import joblib
import numpy as np
from sklearn.cluster import KMeans
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler

from db import fetchall
from features import FEATURE_COLUMNS

logger = logging.getLogger(__name__)

_N_CLASSES = 6


def train(model_dir: str) -> dict:
    """
    Load all labelled events, train/evaluate three models, save artefacts.

    Returns dict with training_samples, test_samples, and per-model metrics.
    """
    cols = ", ".join(FEATURE_COLUMNS)
    rows = fetchall(f"SELECT {cols}, label FROM access_events ORDER BY id")

    if not rows:
        raise ValueError("access_events table is empty — generate data first")

    X = np.array([[row[c] for c in FEATURE_COLUMNS] for row in rows], dtype=np.float64)
    y = np.array([row["label"] for row in rows], dtype=np.int32)

    logger.info("Loaded %d samples from access_events", len(rows))

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s  = scaler.transform(X_test)

    os.makedirs(model_dir, exist_ok=True)
    joblib.dump(scaler, os.path.join(model_dir, "scaler.pkl"))
    logger.info("Saved scaler.pkl")

    results = {}

    # ── 1. Gradient Boosting ─────────────────────────────────────────────────
    logger.info("Training GradientBoosting …")
    gb = GradientBoostingClassifier(
        n_estimators=150,
        learning_rate=0.1,
        max_depth=5,
        random_state=42,
    )
    gb.fit(X_train_s, y_train)
    results["gradient_boosting"] = _evaluate(gb, X_test_s, y_test, "gradient_boosting")
    joblib.dump(gb, os.path.join(model_dir, "gradient_boosting.pkl"))

    # ── 2. MLP Neural Network ─────────────────────────────────────────────────
    logger.info("Training MLP …")
    mlp = MLPClassifier(
        hidden_layer_sizes=(128, 64, 32),
        activation="relu",
        max_iter=300,
        random_state=42,
        early_stopping=True,
        validation_fraction=0.1,
    )
    mlp.fit(X_train_s, y_train)
    results["mlp"] = _evaluate(mlp, X_test_s, y_test, "mlp")
    joblib.dump(mlp, os.path.join(model_dir, "mlp.pkl"))

    # ── 3. K-Means clustering classifier ─────────────────────────────────────
    logger.info("Training K-Means …")
    kmeans = KMeans(n_clusters=_N_CLASSES, random_state=42, n_init=20)
    kmeans.fit(X_train_s)

    # Label each cluster by the majority ground-truth class in that cluster
    cluster_to_label = {}
    train_cluster_ids = kmeans.predict(X_train_s)
    for cid in range(_N_CLASSES):
        mask = train_cluster_ids == cid
        if mask.sum() > 0:
            cluster_to_label[cid] = int(np.bincount(y_train[mask]).argmax())
        else:
            cluster_to_label[cid] = 0

    joblib.dump(kmeans, os.path.join(model_dir, "kmeans.pkl"))
    joblib.dump(cluster_to_label, os.path.join(model_dir, "kmeans_labels.pkl"))

    # Evaluate K-Means as a classifier
    test_clusters = kmeans.predict(X_test_s)
    y_pred_km = np.array([cluster_to_label[c] for c in test_clusters])
    results["kmeans"] = _evaluate_array(y_pred_km, y_test, "kmeans")

    return {
        "training_samples": int(len(X_train)),
        "test_samples":     int(len(X_test)),
        "models":           results,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _evaluate(clf, X_test_s, y_test, name: str) -> dict:
    y_pred = clf.predict(X_test_s)
    return _evaluate_array(y_pred, y_test, name)


def _evaluate_array(y_pred, y_test, name: str) -> dict:
    acc    = float(accuracy_score(y_test, y_pred))
    cm     = confusion_matrix(y_test, y_pred).tolist()
    report = classification_report(y_test, y_pred, output_dict=True, zero_division=0)
    macro  = report.get("macro avg", {})

    logger.info("%-20s accuracy=%.4f", name, acc)
    return {
        "accuracy":         round(acc, 4),
        "precision":        round(macro.get("precision", 0), 4),
        "recall":           round(macro.get("recall", 0), 4),
        "f1":               round(macro.get("f1-score", 0), 4),
        "confusion_matrix": cm,
        "class_report":     report,
    }
