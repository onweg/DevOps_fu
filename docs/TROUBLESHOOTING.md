# Troubleshooting Guide

Diagnostic steps and solutions for the most common problems.

---

## Quick Diagnostic Checklist

Run these in order before anything else:

```bash
# 1. Are all containers running?
docker compose ps

# 2. Any recent errors?
docker compose logs --tail=20

# 3. Is the API responding?
curl http://localhost:5050/api/status
```

---

## Startup Problems

### Problem: `Error response from daemon: port is already allocated`

**Cause:** Port 5050 or 8080 is in use by another application.

**Fix:**
```bash
# Find what's using port 5050
lsof -i :5050        # macOS/Linux
netstat -ano | findstr :5050  # Windows

# Kill the process (macOS/Linux)
kill -9 <PID>

# Or change the port in docker-compose.yml:
ports:
  - "5051:5000"   # use 5051 on host instead
```

> **macOS note:** Port 5000 is permanently occupied by AirPlay Receiver. The project already uses 5050 to avoid this conflict. If 5050 is also busy, change to any free port above 1024.

---

### Problem: `connection refused` immediately after `docker compose up`

**Cause:** Services take 30–90 seconds to start. The postgres healthcheck must pass before ml-service starts, and ml-service must pass its healthcheck before the API starts.

**Fix:** Wait 60 seconds and retry:
```bash
# Watch containers reach healthy state
docker compose ps

# Or watch logs
docker compose logs -f api
```

---

### Problem: `ml-service` container restarts repeatedly

**Cause:** Cannot connect to PostgreSQL, or numpy/scikit-learn import error.

**Diagnosis:**
```bash
docker compose logs ml-service
```

If you see `psycopg2.OperationalError: could not connect to server`:
- PostgreSQL is still initialising — wait and retry
- Check `POSTGRES_PASSWORD` in `.env` matches the value used when the volume was created

If you see `ModuleNotFoundError`:
- Image was built incorrectly — run `docker compose build --no-cache ml-service`

---

### Problem: `api` container exits with code 1

**Diagnosis:**
```bash
docker compose logs api
```

Common causes:
- Missing `.env` file → copy `.env.example` to `.env`
- `ml-service` not yet healthy → wait for healthcheck chain to complete
- Python import error → check build logs with `docker compose up --build`

---

### Problem: api container stays in "Created" state

**Cause:** Docker Compose started the API before ml-service became healthy, then the API exited and wasn't restarted automatically in "Created" state.

**Fix:**
```bash
docker compose up -d api
```

---

## ML Workflow Problems

### Problem: Dashboard shows 0 threats after Analyze

**Cause (most likely):** Data not generated or models not trained.

**Fix:** Run the full sequence in order:
```bash
curl -X POST http://localhost:5050/api/data/generate \
  -H "Content-Type: application/json" -d '{"count": 5000}'

curl -X POST http://localhost:5050/api/analysis/train

curl -X POST http://localhost:5050/api/analysis/analyze
```

Then click **Refresh Dashboard**.

---

### Problem: `POST /api/analysis/train` returns 503

**Cause:** ML service is not reachable from the API container.

**Diagnosis:**
```bash
# Check ml-service health from inside the API container
docker compose exec api curl http://ml-service:5001/health

# Check ml-service logs
docker compose logs ml-service --tail=30
```

---

### Problem: Training times out

**Cause:** GradientBoosting with 150 estimators and MLP with early stopping on 5000+ records can take 60–120 seconds on slow CPUs.

**Fix:** Increase the timeout in `.env`:
```env
ML_TIMEOUT_SEC=180
```
Then restart: `docker compose up -d`

---

### Problem: `POST /api/analysis/analyze` returns 400 with "train the models first"

**Cause:** `.pkl` files are missing from the `ml_models` volume. This happens after `docker compose down -v` (volumes deleted).

**Fix:** Run `POST /api/analysis/train` first.

---

### Problem: K-Means gives wrong predictions after retraining

**Cause:** K-Means cluster-to-label mapping (`kmeans_cluster_map.pkl`) is inconsistent with the saved `kmeans.pkl`. This can happen if training is interrupted.

**Fix:** Retrain fully — both files are always saved together in `trainer.py`. Running `/api/analysis/train` replaces all 5 model files atomically.

---

## Database Problems

### Problem: pgAdmin shows "Unable to connect to server"

**Steps:**
1. Verify postgres container is running: `docker compose ps postgres`
2. In pgAdmin, add a new server with these settings:
   - **Host:** `postgres`
   - **Port:** `5432`
   - **Database:** `access_security`
   - **Username:** `secuser`
   - **Password:** (value from `.env`)

---

### Problem: `init.sql` changes not applied after restart

**Cause:** The `postgres_data` volume already contains an initialised database. PostgreSQL only runs `init.sql` on an **empty** data directory.

**Fix:** Remove the volume and restart:
```bash
docker compose down -v          # WARNING: deletes all data
docker compose up -d
```

---

### Problem: `psycopg2.errors.UniqueViolation` when adding a service

**Cause:** A trusted service with that name already exists in `trusted_services`.

**Response:** The API returns `409 Conflict` — this is expected behaviour. Use `DELETE /api/services/<id>` first if you want to replace it.

---

## Disk Space Problems

### Problem: Docker build fails with I/O error or "no space left on device"

**Cause:** Docker build cache can grow to 10–20 GB over time.

**Fix:**
```bash
# Check Docker disk usage
docker system df

# Remove unused images, containers, and build cache
docker system prune -af

# Also remove volumes if necessary (WARNING: data loss)
docker system prune -af --volumes
```

---

## Kubernetes Problems

### Problem: Pod stuck in `Pending` state

**Diagnosis:**
```bash
kubectl describe pod -n access-security
```

Look for `Events:` section at the bottom. Common causes:
- **Insufficient memory:** `minikube start --memory=4096`
- **Image not found:** Verify images were built inside Minikube's daemon:
  `eval $(minikube docker-env) && docker images | grep access`

---

### Problem: Pod stuck in `CrashLoopBackOff`

**Diagnosis:**
```bash
# Which container is crashing?
kubectl get pod -n access-security \
  -o jsonpath='{.items[0].status.containerStatuses[*].name}'

# Get logs for the crashing container
kubectl logs -n access-security <pod-name> -c api
kubectl logs -n access-security <pod-name> -c ml-service
kubectl logs -n access-security <pod-name> -c postgres
```

---

### Problem: Changes to `k8s/config.yaml` not applied

```bash
kubectl apply -f k8s/config.yaml
kubectl rollout restart deployment/access-security -n access-security
```

---

## Performance Problems

### Problem: Training is very slow inside containers

**Causes and fixes:**
- **Docker Desktop on Mac:** Allocate more CPU/RAM in Docker Desktop → Settings → Resources
- **GradientBoosting slow:** Reduce `n_estimators` temporarily. Default 150 is a good balance; 50 trains 3× faster with slightly lower accuracy.
- **Too many records:** Keep generate count ≤ 5000 for demos.

---

## Logs Reference

| Service | How to view |
|---|---|
| API (Docker) | `docker compose logs api` |
| ML service (Docker) | `docker compose logs ml-service` |
| PostgreSQL (Docker) | `docker compose logs postgres` |
| All services | `docker compose logs -f` |
| API (Kubernetes) | `kubectl logs -n access-security <pod> -c api` |
| Activity log (DB) | `curl http://localhost:5050/api/logs` |

---

## Full Reset Procedure

To return the entire system to a completely clean state:

```bash
# Docker Compose
docker compose down -v
docker compose up --build -d

# After containers are healthy, re-run the ML workflow
curl -X POST http://localhost:5050/api/data/generate \
  -H "Content-Type: application/json" -d '{"count": 5000}'
curl -X POST http://localhost:5050/api/analysis/train
curl -X POST http://localhost:5050/api/analysis/analyze
```
