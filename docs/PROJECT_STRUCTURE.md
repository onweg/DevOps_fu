# Project Structure

Annotated file tree explaining the purpose and responsibility of every file in the project.

---

## Top-level layout

```
DevOps_fu/
├── api/                  Flask REST API + web dashboard
├── ml-service/           Scikit-learn ML pipeline (isolated service)
├── postgres/             Database initialisation SQL
├── k8s/                  Kubernetes manifests
├── docs/                 Extended documentation
├── docker-compose.yml    Multi-container local deployment
├── .env                  Local secrets (gitignored)
├── .env.example          Template for .env
├── .gitignore
└── task.txt              Original assignment description
```

---

## `api/` — Flask REST API Service

The API is the **only externally exposed service**. It owns all HTTP routing, request validation, database reads/writes for business logic, and the web dashboard. It communicates with the ML service over HTTP via `ml_client.py`.

```
api/
├── app.py              Application factory.
│                       create_app() registers blueprints and DB teardown.
│                       Gunicorn calls it as "app:create_app()".
│
├── config.py           All config from environment variables.
│                       DATABASE_URL, ML_SERVICE_URL, ML_TIMEOUT_SEC, DEBUG.
│
├── db.py               PostgreSQL connection and query helpers.
│                       One connection per request (Flask `g` object).
│                       get_db() / close_db() / execute() / fetchall() / fetchone()
│
├── ml_client.py        HTTP client for the ML service.
│                       All inter-service calls go through here.
│                       Converts all request exceptions → RuntimeError.
│
├── utils.py            Shared utilities:
│                       success() / error() — consistent JSON response envelope
│                       log_activity() — shared activity log writer
│
├── requirements.txt    flask, psycopg2-binary, requests, gunicorn
│
├── Dockerfile          python:3.11-slim, gunicorn, 2 workers, port 5000
│
├── .dockerignore       __pycache__, *.pyc, .env, .DS_Store
│
├── routes/             One blueprint per functional area
│   ├── __init__.py
│   ├── status.py       GET /api/status (DB + ML service health + record counts)
│   ├── dashboard.py    GET / (HTML dashboard with server-side stats pre-load)
│   ├── data.py         POST /api/data/generate
│   │                   GET  /api/data/events   (paginated, filterable)
│   │                   DELETE /api/data/events (cascade: alerts + detections)
│   ├── analysis.py     POST /api/analysis/train
│   │                   POST /api/analysis/analyze
│   │                   GET  /api/analysis/threats
│   │                   GET  /api/analysis/metrics
│   │                   GET  /api/analysis/summary
│   ├── services.py     GET/POST /api/services
│   │                   DELETE /api/services/<id>
│   └── logs.py         GET/DELETE /api/logs
│                       GET /api/alerts
│                       PATCH /api/alerts/<id>/acknowledge
│
└── templates/
    └── dashboard.html  Single-page dashboard. Jinja2 for server-side stats,
                        vanilla JS fetch() for all chart/table data.
                        Chart.js 4.4.0 loaded from CDN (no build step).
                        Dark theme with sidebar layout (cyan/purple accent).
```

---

## `ml-service/` — ML Processing Service

The ML service is **internal only** (not exposed on any host port). It owns all scikit-learn computation: data synthesis, model training, and inference. The API service calls it via HTTP.

This isolation means:
- Heavy ML dependencies (scikit-learn, numpy, joblib) stay out of the API image
- ML computation can be scaled or replaced independently
- API remains fast even during long training runs (they run in a separate container)

```
ml-service/
├── app.py              Application factory.
│                       Registers all 4 route blueprints + DB teardown.
│
├── config.py           DATABASE_URL, MODEL_DIR, DEBUG.
│                       MODEL_DIR defaults to ./models/ (maps to Docker volume).
│
├── db.py               Module-level _conn with get_db(), fetchall(), fetchone().
│                       Psycopg2 connection shared within a single process.
│
├── features.py         *** SINGLE SOURCE OF TRUTH ***
│                       FEATURE_COLUMNS — ordered list of 22 feature names.
│                       LABEL_NAMES     — int → string label mapping (6 classes).
│                       LABEL_IDS       — string → int reverse mapping.
│                       All other modules import from here; never duplicate.
│
├── generator.py        Synthetic API access event data generator.
│                       One function per class:
│                         _normal(), _credential_stuffing(), _token_theft(),
│                         _api_abuse(), _brute_force(), _oauth_hijack()
│                       bulk_insert() via psycopg2.extras.execute_values().
│
├── trainer.py          Loads events from DB, trains GB+MLP+KMeans, saves .pkl files.
│                       K-Means cluster labeling by majority ground-truth class.
│                       Returns metrics dict (accuracy, CM, classification report).
│
├── predictor.py        Loads .pkl files, classifies unanalysed events, bulk-inserts
│                       into threat_detections.
│                       Majority vote: GB wins ties.
│                       Confidence = mean of GB and MLP predict_proba.
│
├── requirements.txt    flask, psycopg2-binary, scikit-learn, numpy, joblib, gunicorn
│
├── Dockerfile          python:3.11-slim, gunicorn, 2 workers,
│                       timeout 300s (GradientBoosting training), port 5001
│
├── .dockerignore       __pycache__, *.pyc, .env, models/*.pkl
│
├── models/             Trained model artifacts (populated after first /train call)
│   ├── scaler.pkl              StandardScaler fitted on training data
│   ├── gradient_boosting.pkl   Trained GradientBoostingClassifier
│   ├── mlp.pkl                 Trained MLPClassifier
│   ├── kmeans.pkl              Trained KMeans (6 clusters)
│   └── kmeans_cluster_map.pkl  dict: cluster_id → label_id
│
└── routes/
    ├── __init__.py
    ├── generate.py     POST /generate   — validates count, calls generator.generate()
    ├── train.py        POST /train      — calls trainer.train(model_dir)
    ├── predict.py      POST /predict    — calls predictor.predict(model_dir)
    └── health.py       GET  /health     — checks DB with SELECT 1
```

---

## `postgres/init.sql`

Executed automatically by the postgres:16 Docker image on **first startup** (when the data directory is empty).

Contents:
- 6 `CREATE TABLE IF NOT EXISTS` statements with all columns, types, and foreign keys
- Performance indexes on frequently queried columns
- 5 seed rows in `trusted_services` (Google OAuth, GitHub OAuth, Stripe, SendGrid, Twilio)
- 1 seed row in `activity_logs`

`IF NOT EXISTS` guards make the script idempotent — safe to run manually on an existing DB.

### Database schema summary

| Table | Purpose |
|---|---|
| `access_events` | Raw API access records with 22 feature columns + label |
| `threat_detections` | ML predictions: gb/mlp/km/final labels + confidence |
| `model_metrics` | Training results per model (accuracy, F1, confusion matrix) |
| `trusted_services` | Third-party service whitelist (name, base_url) |
| `activity_logs` | Audit trail of all system actions (level, action, message) |
| `alerts` | Active security alerts with severity and acknowledgement state |

---

## `k8s/config.yaml`

Single file containing all Kubernetes manifests separated by `---`:

| Manifest | Kind | Purpose |
|---|---|---|
| 1 | Namespace | `access-security` — isolates all resources |
| 2 | ConfigMap `access-config` | Non-sensitive env vars (DB name, Flask env) |
| 3 | ConfigMap `postgres-init-sql` | init.sql embedded; mounted as init volume |
| 4 | Secret `access-secret` | base64 credentials (passwords) |
| 5 | PVC `postgres-pvc` | 1 Gi for PostgreSQL data |
| 6 | PVC `ml-models-pvc` | 256 Mi for trained .pkl files |
| 7 | PVC `pgadmin-pvc` | 256 Mi for pgAdmin settings |
| 8 | Deployment `access-security` | 1 pod, 4 containers |
| 9 | Service `access-api-svc` | NodePort :30000 → API :5000 |
| 10 | Service `access-pgadmin-svc` | NodePort :30080 → pgAdmin :80 |

---

## `docker-compose.yml`

Defines all 4 services with:
- Build context / image references
- Environment variable injection from `.env`
- Volume mounts
- Network membership (`access-net`)
- Healthchecks with `depends_on` conditions
- Restart policies (`unless-stopped`)
- Port mapping: API `5050:5000` (5000 reserved by macOS AirPlay)

---

## Key Architectural Decisions

### Why two Flask services instead of one?

GradientBoosting training with 150 estimators is CPU-intensive and can block for 30–90 seconds. Keeping ML in a separate service means:
- The API remains responsive during training
- ML dependencies (scikit-learn, numpy) don't bloat the API image (~340 MB saved)
- The ML service can be independently scaled, replaced, or upgraded

### Why psycopg2 + raw SQL instead of an ORM?

For a university DevOps project with a fixed schema, raw SQL is appropriate because:
- Queries are explicit and easy to audit
- No ORM migration complexity
- DB schema matches the SQL exactly (init.sql is the schema definition)
- psycopg2 RealDictCursor returns rows as dicts, eliminating manual mapping

### Why three different algorithm families?

GradientBoosting, MLP, and K-Means represent three fundamentally different approaches to classification:
- **GB** — ensemble of decision trees (boosting); excellent on tabular data with mixed features
- **MLP** — neural network; learns non-linear interactions automatically
- **K-Means** — unsupervised clustering adapted as classifier; validates that attack classes are geometrically separable in feature space

This ensemble reduces the risk of any single model's blind spots affecting the final prediction.

### Why vanilla JS instead of React/Vue?

The dashboard is a single page with ~6 API calls. The full JS footprint is under 500 lines in one file. Adding a framework build pipeline would add 10× complexity for no benefit at this scale.

### Why single-pod Kubernetes?

Containers in a Kubernetes pod share a network namespace (localhost). This:
- Eliminates inter-pod Service DNS complexity
- Mirrors the Docker Compose networking model (services call each other by name internally)
- Is explicitly acknowledged as a known limitation for a production deployment
