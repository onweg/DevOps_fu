# ML Pipeline Documentation

Technical deep-dive into the machine learning pipeline: data generation, model training, and ensemble prediction.

---

## Overview

The ML pipeline follows a standard supervised learning workflow with three algorithms trained in parallel and combined via majority-vote ensemble inference.

```
Synthetic Generator → PostgreSQL → Trainer → .pkl files → Predictor → threat_detections
```

All ML code lives in `ml-service/`. The pipeline is exposed as a Flask microservice so it runs in an isolated container.

---

## Feature Engineering

### Feature set: 22 dimensions

All features represent **observable API access metrics** collected per session or request window. Features are grouped into four semantic categories:

#### Group 1: Authentication & Credentials (3 features)

| Feature | Type | Range | Threat Signal |
|---|---|---|---|
| `request_rate_per_min` | float | 1–1000 | Brute Force / Credential Stuffing: > 300 |
| `failed_auth_count` | int | 0–300 | Brute Force: 150–300; Credential Stuffing: 50–150 |
| `token_age_hours` | float | 0–720 | Token Theft: fresh token from unknown IP |

#### Group 2: Service Context (5 features)

| Feature | Type | Range | Threat Signal |
|---|---|---|---|
| `is_known_service` | 0/1 | — | API Abuse: always known (internal); Token Theft: may be unknown |
| `service_id` | int | 1–100 | Uniform across classes; context for aggregation |
| `oauth_scope_count` | int | 1–20 | OAuth Hijack: 10–20 (over-scoped token) |
| `api_key_age_days` | float | 0–365 | Normal: 30–365; Credential Stuffing: fresh/stolen keys |
| `ssl_valid` | 0/1 | — | Normal: 1; Rogue proxies may relay with broken SSL |

#### Group 3: Session Behaviour (7 features)

| Feature | Type | Range | Threat Signal |
|---|---|---|---|
| `session_duration_sec` | float | 10–7200 | Normal: moderate; API Abuse: long (bulk exfil) |
| `unique_endpoints_count` | int | 1–50 | API Abuse: 30–50; Brute Force: always 1 |
| `concurrent_sessions` | int | 1–15 | Token Theft / OAuth Hijack: 3–15 (shared token) |
| `off_hours_access` | 0/1 | — | Normal: rare; attacks: 0.5–0.8 probability |
| `permission_escalation_count` | int | 0–10 | OAuth Hijack: 3–10 (scope creep) |
| `token_refresh_count` | int | 0–30 | OAuth Hijack: 15–30; Normal: 0–2 |
| `redirect_count` | int | 0–15 | OAuth Hijack: 6–15 (flow manipulation) |

#### Group 4: Network & Traffic (7 features)

| Feature | Type | Range | Threat Signal |
|---|---|---|---|
| `is_known_ip` | 0/1 | — | Token Theft: always 0; Normal: always 1 |
| `ip_change_count` | int | 0–10 | Token Theft: 3–10; Normal: 0 |
| `geolocation_anomaly` | 0/1 | — | Token Theft: always 1; Normal: always 0 |
| `response_error_rate` | float | 0–1 | Brute Force: 0.90–0.99; Credential Stuffing: 0.75–0.95 |
| `data_volume_mb` | float | 0.01–1000 | API Abuse: 200–1000; Normal: 0.1–5 |
| `request_size_avg_bytes` | float | 100–5000 | API Abuse: large payloads; Normal: small |
| `anomaly_score_prev` | float | 0–1 | Rolling anomaly score from previous window |

---

## Data Generation

**File:** `ml-service/generator.py`

### Class distribution

```python
_WEIGHTS = [0.30, 0.14, 0.14, 0.14, 0.14, 0.14]
#           normal  cred  token  api  brute  oauth
```

30% normal traffic reflects a realistic API environment. Attack classes are equal (14% each) for training balance.

### How each class is generated

Each class has its own generator function that samples features from numpy distributions calibrated to reflect how that attack actually manifests.

**Credential Stuffing** (`_credential_stuffing`):
```python
"request_rate_per_min":  _clip(rng.normal(500, 80), 300, 900),  # ★ high rate
"failed_auth_count":     int(rng.normal(100, 20)),               # ★ many failures
"response_error_rate":   _clip(rng.normal(0.85, 0.05), 0.75, 0.95),
"unique_endpoints_count": int(rng.integers(1, 3)),               # focused on /login
"is_known_ip":           int(rng.choice([0, 1], p=[0.6, 0.4])),
```

**Token Theft** (`_token_theft`):
```python
"is_known_ip":          0,              # ★ always unknown IP
"geolocation_anomaly":  1,              # ★ impossible travel
"ip_change_count":      int(rng.integers(3, 11)),
"data_volume_mb":       _clip(rng.normal(150, 50), 50, 300),
"concurrent_sessions":  int(rng.integers(3, 11)),  # token shared
```

**OAuth Hijack** (`_oauth_hijack`):
```python
"redirect_count":             int(rng.normal(8, 2)),    # ★ flow manipulation
"token_refresh_count":        int(rng.normal(20, 4)),   # ★ excessive refresh
"oauth_scope_count":          int(rng.integers(10, 21)),# ★ over-privileged
"permission_escalation_count":int(rng.integers(3, 11)),
```

---

## Model Training

**File:** `ml-service/trainer.py`

### Pipeline steps

```python
# 1. Load all rows from access_events
rows = fetchall("SELECT request_rate_per_min, ..., label FROM access_events")

# 2. Build feature matrix and label vector
X = np.array([[row[c] for c in FEATURE_COLUMNS] for row in rows], dtype=np.float64)
y = np.array([row["label"] for row in rows], dtype=np.int32)

# 3. Stratified 80/20 split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2,
                                                      random_state=42, stratify=y)

# 4. Fit StandardScaler on TRAINING data only
scaler = StandardScaler()
X_train_s = scaler.fit_transform(X_train)
X_test_s  = scaler.transform(X_test)   # ← transform only, no fit

# 5. Train Gradient Boosting and MLP
gb.fit(X_train_s, y_train)
mlp.fit(X_train_s, y_train)

# 6. Train K-Means and label clusters by majority class
kmeans.fit(X_train_s)
cluster_labels = kmeans.labels_
for cid in range(6):
    mask = cluster_labels == cid
    cluster_to_label[cid] = int(np.bincount(y_train[mask]).argmax())

# 7. Save all artifacts to models/
joblib.dump(scaler, "models/scaler.pkl")
```

### Model hyperparameters and rationale

| Model | Key Parameters | Rationale |
|---|---|---|
| `GradientBoostingClassifier` | `n_estimators=150, learning_rate=0.1, max_depth=5` | Sequential boosting corrects residual errors. 150 trees with shallow depth prevent overfitting while capturing non-linear interactions between authentication and network features. Primary tiebreaker. |
| `MLPClassifier` | `hidden_layer_sizes=(128,64,32), activation='relu', early_stopping=True` | Three-layer neural network learns complex feature interactions (e.g., combination of ip_change + geolocation_anomaly + data_volume). Early stopping prevents overfitting. |
| `KMeans` | `n_clusters=6, n_init=20` | Unsupervised clustering serves as a classifier by labeling each cluster with the majority ground-truth class from training data. `n_init=20` ensures stable centroid initialization. |

### Why StandardScaler is critical

MLP is sensitive to feature scale: `data_volume_mb` can reach 1000 MB while `ssl_valid` is binary (0/1). Without scaling, the neural network's gradient descent would be dominated by high-magnitude features. StandardScaler normalises all features to zero mean and unit variance before training. Critically, the scaler is fitted only on training data to prevent data leakage.

### K-Means as a classifier

K-Means is an unsupervised algorithm, but we use it as a classifier by mapping each cluster to the attack class most commonly found in that cluster during training:

```python
for cid in range(n_clusters):
    mask = (kmeans.labels_ == cid)
    cluster_to_label[cid] = int(np.bincount(y_train[mask]).argmax())
```

At inference time: `km_label = cluster_to_label[kmeans.predict(X_scaled)[i]]`

This label map is persisted in `models/kmeans_cluster_map.pkl`.

### Output artifacts

```
ml-service/models/
├── scaler.pkl              # StandardScaler fitted on training data
├── gradient_boosting.pkl   # Trained GradientBoostingClassifier
├── mlp.pkl                 # Trained MLPClassifier
├── kmeans.pkl              # Trained KMeans (6 clusters)
└── kmeans_cluster_map.pkl  # dict: cluster_id → label_id
```

---

## Ensemble Prediction

**File:** `ml-service/predictor.py`

### Inference pipeline

```python
# 1. Load artifacts
scaler  = joblib.load("models/scaler.pkl")
gb      = joblib.load("models/gradient_boosting.pkl")
mlp     = joblib.load("models/mlp.pkl")
kmeans  = joblib.load("models/kmeans.pkl")
km_map  = joblib.load("models/kmeans_cluster_map.pkl")

# 2. Fetch unclassified events
rows = fetchall("""
    SELECT ae.id, request_rate_per_min, ...
    FROM   access_events ae
    LEFT JOIN threat_detections td ON td.event_id = ae.id
    WHERE  td.id IS NULL
""")

# 3. Scale features
X_s = scaler.transform(X)

# 4. Predict with all three models
gb_preds  = gb.predict(X_s)
gb_probas = gb.predict_proba(X_s)
mlp_preds = mlp.predict(X_s)
mlp_probas= mlp.predict_proba(X_s)
km_raw    = kmeans.predict(X_s)
km_preds  = [km_map[c] for c in km_raw]

# 5. Majority vote (GB wins ties)
for i in range(len(rows)):
    votes  = [gb_preds[i], mlp_preds[i], km_preds[i]]
    counts = {}
    for v in votes: counts[v] = counts.get(v, 0) + 1
    final  = max(counts, key=lambda k: (counts[k], k == gb_preds[i]))

# 6. Confidence = mean of GB and MLP predict_proba for winning class
confidence = (gb_probas[i][final] + mlp_probas[i][final]) / 2

# 7. Bulk insert into threat_detections
```

### Alert generation

After prediction, the API creates `alerts` rows for:
- Non-normal detections (`final_label != 0`)
- Confidence ≥ 0.70 (configurable via `ALERT_THRESHOLD`)
- Not already alerted (deduplication via `NOT EXISTS` subquery)

Severity is assigned per threat type:
```python
SEVERITY = {
    "token_theft":         "CRITICAL",
    "oauth_hijack":        "CRITICAL",
    "credential_stuffing": "HIGH",
    "brute_force":         "HIGH",
    "api_abuse":           "MEDIUM",
}
```

---

## Feature Source of Truth

**File:** `ml-service/features.py`

`FEATURE_COLUMNS` is the single authoritative list of the 22 feature names **in exact order**. This order must match across:
- `generator.py` — dict keys
- `trainer.py` — numpy array column order
- `predictor.py` — numpy array column order
- `postgres/init.sql` — table column order

**Never change the order of `FEATURE_COLUMNS` after the first model has been trained.** Doing so invalidates all saved `.pkl` files and requires retraining.

---

## Reproducibility

Training is reproducible with `random_state=42` on all models and the train/test split. Running `POST /api/analysis/train` twice on the same dataset produces **identical** `.pkl` files.

The data generator uses an **unseeded** `numpy.random.default_rng()` — each call generates different data. This is intentional: we want different synthetic batches across demo runs.
