# API Reference

Complete reference for all REST API endpoints.

Base URL (Docker Compose): `http://localhost:5050`  
Base URL (Kubernetes): `http://$(minikube service access-api-svc -n access-security --url)`

---

## Response Envelope

Every endpoint returns a consistent JSON structure:

**Success (2xx)**
```json
{
  "status": "success",
  "message": "Human-readable description",
  ...additional data fields...
}
```

**Error (4xx / 5xx)**
```json
{
  "status": "error",
  "error": "Human-readable reason"
}
```

---

## System Endpoints

### GET `/api/status`

Health check for all services. Used by the dashboard status indicator and Kubernetes probes.

**Response**
```json
{
  "status": "healthy",
  "services": {
    "api": "up",
    "database": "up",
    "ml_service": "up"
  },
  "database": {
    "total_events": 5000,
    "total_threats": 3500,
    "active_alerts": 9,
    "models_trained": true
  }
}
```

`status` is `"healthy"` when both database and ml_service are up, otherwise `"degraded"`.

---

## Data Management Endpoints

### POST `/api/data/generate`

Calls the ML service to generate synthetic API access records and insert them into `access_events`.

**Request body**
```json
{ "count": 1000 }
```

| Field | Type | Required | Constraints | Default |
|---|---|---|---|---|
| count | integer | No | 1–10 000 | 1000 |

**Response (201)**
```json
{
  "status": "success",
  "message": "Generated 1000 events",
  "generated": 1000,
  "total": 6000
}
```

**Error responses**
- `400` — count out of range
- `503` — ML service unreachable

**Example**
```bash
curl -X POST http://localhost:5050/api/data/generate \
  -H "Content-Type: application/json" \
  -d '{"count": 5000}'
```

---

### GET `/api/data/events`

Returns paginated list of access events.

**Query parameters**

| Param | Type | Default | Description |
|---|---|---|---|
| page | integer | 1 | Page number |
| limit | integer | 50 | Rows per page (max 200) |
| label | string | — | Filter by class name (e.g. `token_theft`) |

Valid label values: `normal`, `credential_stuffing`, `token_theft`, `api_abuse`, `brute_force`, `oauth_hijack`

**Response (200)**
```json
{
  "status": "success",
  "page": 1,
  "limit": 50,
  "total": 5000,
  "events": [
    {
      "id": 1,
      "created_at": "2024-01-15T10:30:00+00:00",
      "request_rate_per_min": 14.8,
      "failed_auth_count": 1,
      "token_age_hours": 6.4,
      "label": 0,
      "label_name": "normal",
      ...
    }
  ]
}
```

**Examples**
```bash
# All events, first page
curl "http://localhost:5050/api/data/events"

# Filter by class, page 2
curl "http://localhost:5050/api/data/events?label=token_theft&page=2&limit=20"
```

---

### DELETE `/api/data/events`

Deletes all access events and all dependent data (threat_detections, alerts).
Deletion respects foreign key constraints: alerts → threat_detections → access_events.

**Response (200)**
```json
{
  "status": "success",
  "message": "All data cleared",
  "deleted": 5000
}
```

**Example**
```bash
curl -X DELETE http://localhost:5050/api/data/events
```

---

## Analysis Endpoints

### POST `/api/analysis/train`

Trains Gradient Boosting, MLP, and K-Means classifiers on all records in `access_events`.
Stores accuracy, precision, recall, F1, and confusion matrices in `model_metrics`.

Delegates computation to the ML service. **Response may take 30–90 s.**

**Response (200)**
```json
{
  "status": "success",
  "message": "Models trained successfully",
  "training_samples": 4000,
  "test_samples": 1000,
  "models": {
    "gradient_boosting": {
      "accuracy": 0.9986,
      "precision": 0.9987,
      "recall": 0.9986,
      "f1": 0.9986,
      "confusion_matrix": [[285,0,0,0,0,0], [0,141,0,1,0,0], ...],
      "class_report": { "0": {"precision": 1.0, "recall": 1.0, ...}, ... }
    },
    "mlp": { ... },
    "kmeans": { ... }
  }
}
```

**Error responses**
- `400` — `access_events` table is empty (generate data first)
- `503` — ML service unreachable

**Example**
```bash
curl -X POST http://localhost:5050/api/analysis/train
```

---

### POST `/api/analysis/analyze`

Classifies all `access_events` rows that do not yet have an entry in `threat_detections`.
Uses three trained models and majority vote. Creates `alerts` for high-confidence non-normal detections.

**Response (200)**
```json
{
  "status": "success",
  "message": "Analysis complete. 287 alerts generated.",
  "analyzed": 5000,
  "skipped_already_classified": 0,
  "detections": {
    "normal": 1500,
    "credential_stuffing": 700,
    "token_theft": 700,
    "api_abuse": 700,
    "brute_force": 700,
    "oauth_hijack": 700
  },
  "alerts_generated": 287
}
```

**Error responses**
- `400` — models not trained (.pkl files missing)
- `503` — ML service unreachable

**Example**
```bash
curl -X POST http://localhost:5050/api/analysis/analyze
```

---

### GET `/api/analysis/threats`

Returns classified threat detections.

**Query parameters**

| Param | Type | Default | Description |
|---|---|---|---|
| threat_type | string | — | Filter by label name |
| min_confidence | float | 0.0 | Minimum confidence score (0.0–1.0) |
| limit | integer | 100 | Max rows (capped at 500) |

**Response (200)**
```json
{
  "status": "success",
  "total": 3500,
  "threats": [
    {
      "id": 1,
      "detected_at": "2024-01-15T10:31:00+00:00",
      "event_id": 42,
      "gb_label": 2, "gb_label_name": "token_theft",
      "mlp_label": 2, "mlp_label_name": "token_theft",
      "km_label": 2, "km_label_name": "token_theft",
      "final_label": 2, "final_label_name": "token_theft",
      "confidence": 0.9741,
      "model_agreement": true
    }
  ]
}
```

**Examples**
```bash
# All threats
curl "http://localhost:5050/api/analysis/threats"

# High-confidence token theft only
curl "http://localhost:5050/api/analysis/threats?threat_type=token_theft&min_confidence=0.9"
```

---

### GET `/api/analysis/metrics`

Returns the most recent training metrics for each of the three models.

**Response (200)**
```json
{
  "status": "success",
  "models": {
    "gradient_boosting": {
      "id": 1,
      "trained_at": "2024-01-15T10:31:00+00:00",
      "model_name": "gradient_boosting",
      "training_samples": 4000,
      "test_samples": 1000,
      "accuracy": 0.9986,
      "precision_macro": 0.9987,
      "recall_macro": 0.9986,
      "f1_macro": 0.9986,
      "confusion_matrix": [[...]],
      "class_report": {...}
    },
    "mlp": { ... },
    "kmeans": { ... }
  }
}
```

**Error responses**
- `404` — No models have been trained yet

---

### GET `/api/analysis/summary`

Returns threat counts grouped by class. Used by the dashboard charts.

**Response (200)**
```json
{
  "status": "success",
  "threat_distribution": [
    { "threat_type": "normal",              "count": 1500 },
    { "threat_type": "credential_stuffing", "count": 700  },
    { "threat_type": "token_theft",         "count": 700  },
    { "threat_type": "api_abuse",           "count": 700  },
    { "threat_type": "brute_force",         "count": 700  },
    { "threat_type": "oauth_hijack",        "count": 700  }
  ]
}
```

---

## Trusted Services Endpoints

### GET `/api/services`

Returns all trusted third-party services in the whitelist.

**Response (200)**
```json
{
  "status": "success",
  "services": [
    {
      "id": 1,
      "added_at": "2024-01-15T10:00:00+00:00",
      "name": "Google OAuth",
      "base_url": "https://accounts.google.com",
      "description": "Google OAuth 2.0 identity provider",
      "is_active": true
    }
  ]
}
```

---

### POST `/api/services`

Adds a third-party service to the trusted whitelist.

**Request body**
```json
{
  "name": "Stripe",
  "base_url": "https://api.stripe.com",
  "description": "Payment processing API (optional)"
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| name | string | Yes | Service display name |
| base_url | string | Yes | Base URL; stored as-is |
| description | string | No | Optional human-readable note |

**Response (200)**
```json
{
  "status": "success",
  "message": "Service added to whitelist",
  "service": { "id": 6, "name": "Stripe", "base_url": "https://api.stripe.com", ... }
}
```

**Error responses**
- `400` — name or base_url missing
- `409` — service name already in whitelist

**Example**
```bash
curl -X POST http://localhost:5050/api/services \
  -H "Content-Type: application/json" \
  -d '{"name": "Twilio", "base_url": "https://api.twilio.com", "description": "SMS gateway"}'
```

---

### DELETE `/api/services/<id>`

Removes a trusted service by its database ID.

**Response (200)**
```json
{
  "status": "success",
  "message": "Service removed from whitelist",
  "id": 6
}
```

**Error responses**
- `404` — Service ID not found

---

## Logs & Alerts Endpoints

### GET `/api/logs`

Returns paginated activity log entries.

**Query parameters**

| Param | Type | Default | Description |
|---|---|---|---|
| level | string | — | Filter: `INFO`, `WARNING`, `ALERT`, `ERROR` |
| page | integer | 1 | Page number |
| limit | integer | 50 | Max rows (capped at 200) |

**Response (200)**
```json
{
  "status": "success",
  "page": 1,
  "limit": 50,
  "total": 120,
  "logs": [
    {
      "id": 42,
      "created_at": "2024-01-15T10:35:00+00:00",
      "level": "ALERT",
      "action": "ANALYSIS_COMPLETE",
      "message": "Analyzed 5000 events. 3500 threats found.",
      "details": { "analyzed": 5000, "detections": { ... } }
    }
  ]
}
```

**Example**
```bash
curl "http://localhost:5050/api/logs?level=ALERT&limit=20"
```

---

### DELETE `/api/logs`

Clears all activity log entries.

**Response (200)**
```json
{ "status": "success", "message": "Activity log cleared", "deleted": 42 }
```

---

### GET `/api/alerts`

Returns active (unacknowledged) alerts, sorted by severity: CRITICAL → HIGH → MEDIUM.

**Response (200)**
```json
{
  "status": "success",
  "total": 9,
  "alerts": [
    {
      "id": 1,
      "created_at": "2024-01-15T10:35:00+00:00",
      "threat_type": "token_theft",
      "severity": "CRITICAL",
      "event_id": 42,
      "detection_id": 3,
      "message": "Token_theft detected — confidence 97%",
      "confidence": 0.974,
      "acknowledged": false,
      "acknowledged_at": null
    }
  ]
}
```

### Severity mapping

| Threat Type | Severity |
|---|---|
| token_theft | CRITICAL |
| oauth_hijack | CRITICAL |
| credential_stuffing | HIGH |
| brute_force | HIGH |
| api_abuse | MEDIUM |

---

### PATCH `/api/alerts/<id>/acknowledge`

Marks an alert as acknowledged.

**Response (200)**
```json
{ "status": "success", "message": "Alert acknowledged", "id": 1 }
```

**Error responses**
- `404` — Alert ID not found

**Example**
```bash
curl -X PATCH http://localhost:5050/api/alerts/1/acknowledge
```

---

## ML Service Internal Endpoints

These endpoints are called by the API service via `ml_client.py`. Not intended for direct use.

| Method | Endpoint | Description |
|---|---|---|
| GET | `http://ml-service:5001/health` | Liveness probe; returns `{"status": "ok", "models_ready": bool}` |
| POST | `http://ml-service:5001/generate` | Generate records; body `{"count": N}` |
| POST | `http://ml-service:5001/train` | Train models |
| POST | `http://ml-service:5001/predict` | Classify unclassified events |
