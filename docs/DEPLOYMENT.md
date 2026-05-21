# Deployment Guide

Production-oriented deployment documentation for both Docker Compose and Kubernetes.

---

## Environment Matrix

| Setting | Docker Compose (dev) | Kubernetes (prod-style) |
|---|---|---|
| Config source | `.env` file | ConfigMap + Secret |
| Network | access-net bridge | Pod shared localhost |
| Storage | Named volumes | PersistentVolumeClaims |
| API access | `localhost:5050` | NodePort `<minikube-ip>:30000` |
| pgAdmin | `localhost:8080` | NodePort `<minikube-ip>:30080` |
| ML service | Internal only | Internal only (same pod) |
| Image build | Local via Compose | Local via `minikube docker-env` |
| DB init | Volume mount | ConfigMap volume |

> **macOS note:** Port 5000 is occupied by AirPlay Receiver. The API is exposed on port **5050** in all Docker Compose configurations.

---

## Docker Compose Deployment

### Architecture

```
Host machine
├── Port 5050 ──────────────────► api container
├── Port 8080 ──────────────────► pgadmin container
│
└── Docker network: access-net
    ├── api          (Flask :5000, exposed as :5050)
    ├── ml-service   (Flask :5001, internal only)
    ├── postgres     (PostgreSQL :5432, internal only)
    └── pgadmin      (HTTP :80, exposed as :8080)

Volumes:
├── postgres_data  → /var/lib/postgresql/data
├── pgadmin_data   → /var/lib/pgadmin
└── ml_models      → /app/models
```

### Service startup order

Enforced by Docker Compose `depends_on` with `condition: service_healthy`:

```
1. postgres    — starts first; healthcheck: pg_isready every 5s, up to 10 retries (50s)
2. ml-service  — starts after postgres healthy; healthcheck: GET /health every 10s, 5 retries
3. api         — starts after postgres AND ml-service healthy
4. pgadmin     — starts after postgres healthy (independent of api/ml-service)
```

### Configuration reference

All configuration comes from `.env` (never hardcoded):

```env
POSTGRES_DB=access_security         # Database name
POSTGRES_USER=secuser               # PostgreSQL username
POSTGRES_PASSWORD=<secret>          # PostgreSQL password — CHANGE THIS

PGADMIN_DEFAULT_EMAIL=admin@...     # pgAdmin login email
PGADMIN_DEFAULT_PASSWORD=<secret>   # pgAdmin login password — CHANGE THIS

FLASK_ENV=development               # 'development' or 'production'
ML_TIMEOUT_SEC=120                  # Seconds API waits for ML service responses
```

### Build and deploy

```bash
# First-time setup
cp .env.example .env
# Edit .env with your passwords

# Build images and start
docker compose up --build -d

# Verify
docker compose ps
curl http://localhost:5050/api/status
```

### Updating after code changes

```bash
# Rebuild only the changed service (faster than full rebuild)
docker compose build api
docker compose up -d --no-deps api

# Or rebuild everything
docker compose up --build -d
```

### Volume management

```bash
# List volumes
docker volume ls | grep devops_fu

# Backup PostgreSQL data
docker compose exec postgres pg_dump -U secuser access_security > backup.sql

# Restore from backup
docker compose exec -T postgres psql -U secuser access_security < backup.sql
```

---

## Kubernetes Deployment

### Architecture

```
Kubernetes Cluster (Minikube)
└── Namespace: access-security
    │
    ├── ConfigMap: access-config         (non-sensitive env vars)
    ├── ConfigMap: postgres-init-sql     (init.sql content)
    ├── Secret: access-secret            (base64 credentials)
    │
    ├── PVC: postgres-pvc    (1 Gi)
    ├── PVC: ml-models-pvc   (256 Mi)
    ├── PVC: pgadmin-pvc     (256 Mi)
    │
    ├── Deployment: access-security (1 pod, 4 containers)
    │   │   All 4 containers share localhost (single pod network)
    │   ├── container: postgres    (postgres:16-alpine)
    │   ├── container: ml-service  (access-ml-service:latest)
    │   ├── container: api         (access-api:latest)
    │   └── container: pgadmin     (dpage/pgadmin4:8)
    │
    ├── Service: access-api-svc    (NodePort :30000 → api :5000)
    └── Service: access-pgadmin-svc(NodePort :30080 → pgAdmin :80)
```

### Updating K8s credentials

The Secret in `k8s/config.yaml` contains base64-encoded defaults. To use your own:

```bash
# Encode your value
echo -n 'my_secure_password' | base64

# Edit k8s/config.yaml and replace the value under data:
#   POSTGRES_PASSWORD: <base64-output>
```

### Full deployment sequence

```bash
# 1. Start cluster
minikube start --memory=4096 --cpus=2

# 2. Point to Minikube Docker daemon
eval $(minikube docker-env)

# 3. Build images inside Minikube (no registry needed)
docker build -t access-api:latest       ./api
docker build -t access-ml-service:latest ./ml-service

# 4. Apply all manifests
kubectl apply -f k8s/config.yaml

# 5. Monitor pod startup
kubectl get pods -n access-security -w
# Wait for: READY 4/4   STATUS Running

# 6. Get service URLs
minikube service access-api-svc     -n access-security --url
minikube service access-pgadmin-svc -n access-security --url
```

### Verifying deployment health

```bash
# Pod status
kubectl get pods -n access-security

# All resources in namespace
kubectl get all -n access-security

# Check readiness probes passed
kubectl get pod -n access-security \
  -o jsonpath='{.items[0].status.containerStatuses[*].ready}'
```

### Exec into containers

```bash
POD=$(kubectl get pod -n access-security -o jsonpath='{.items[0].metadata.name}')

# API container shell
kubectl exec -n access-security $POD -c api -- sh

# psql session
kubectl exec -n access-security $POD -c postgres -- \
  psql -U secuser -d access_security -c "SELECT COUNT(*) FROM access_events"

# Check model files
kubectl exec -n access-security $POD -c ml-service -- ls /app/models
```

### Updating after image changes

```bash
eval $(minikube docker-env)
docker build -t access-api:latest ./api
kubectl rollout restart deployment/access-security -n access-security
kubectl rollout status deployment/access-security -n access-security
```

### Teardown

```bash
# Remove all resources (volumes deleted — data lost)
kubectl delete -f k8s/config.yaml
kubectl delete namespace access-security

# Stop Minikube
minikube stop

# Full reset
minikube delete
```

---

## Image Size Reference

| Image | Approximate Size |
|---|---|
| `access-api:latest` | ~180 MB |
| `access-ml-service:latest` | ~520 MB (scikit-learn + numpy) |
| `postgres:16-alpine` | ~240 MB |
| `dpage/pgadmin4:8` | ~560 MB |

Total pull: ~1.5 GB on first deploy.
