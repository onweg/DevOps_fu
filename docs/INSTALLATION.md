# Installation Guide

Complete step-by-step installation for all supported environments.

---

## Prerequisites

### Required software

| Software | Minimum Version | Check |
|---|---|---|
| Docker Desktop (Mac/Windows) or Docker Engine (Linux) | 24.0 | `docker --version` |
| Docker Compose v2 | 2.20 | `docker compose version` |
| Git | any | `git --version` |

### For Kubernetes deployment (additional)

| Software | Minimum Version | Check |
|---|---|---|
| Minikube | 1.32 | `minikube version` |
| kubectl | 1.28 | `kubectl version --client` |

### For local ML testing only (no Docker)

| Software | Minimum Version | Check |
|---|---|---|
| Python | 3.11 | `python3 --version` |
| pip | 23+ | `pip3 --version` |

### Hardware

- **RAM:** 4 GB minimum available (8 GB recommended for Kubernetes)
- **Disk:** ~2 GB for Docker images + data volumes
- **CPU:** Any modern 64-bit processor

---

## Part 1: Clone the Repository

```bash
git clone <repository-url>
cd DevOps_fu
```

---

## Part 2: Environment Configuration

Copy the environment template and configure values:

```bash
cp .env.example .env
```

Open `.env` in a text editor and set your values:

```env
# PostgreSQL credentials
POSTGRES_DB=access_security
POSTGRES_USER=secuser
POSTGRES_PASSWORD=your_secure_password_here   # CHANGE THIS

# pgAdmin web interface credentials
PGADMIN_DEFAULT_EMAIL=admin@admin.com
PGADMIN_DEFAULT_PASSWORD=your_pgadmin_password  # CHANGE THIS

# Flask mode: 'development' enables debug logs
FLASK_ENV=development

# ML service timeout in seconds
# GradientBoosting + MLP training on 5000 records takes ~30-60 s
ML_TIMEOUT_SEC=120
```

> **Security note:** Never commit `.env` to version control. It is already in `.gitignore`.

---

## Part 3: Docker Compose Installation (Recommended)

This is the primary deployment method. All services start with one command.

### Step 1: Build and start all containers

```bash
docker compose up --build -d
```

This command:
1. Builds the `api` image from `./api/Dockerfile`
2. Builds the `ml-service` image from `./ml-service/Dockerfile`
3. Pulls `postgres:16-alpine` and `dpage/pgadmin4:8` from Docker Hub
4. Creates the `access-net` bridge network
5. Creates three named volumes: `postgres_data`, `pgadmin_data`, `ml_models`
6. Starts all 4 containers with health checks and dependency ordering

Expected build time: **3-6 minutes** (first build, depends on internet speed)

> **macOS users:** Port 5000 is occupied by AirPlay Receiver. The API is exposed on port **5050**.

### Step 2: Verify all containers are healthy

```bash
docker compose ps
```

Expected output (all services should show `healthy` or `running`):
```
NAME                   STATUS          PORTS
devops_fu-api-1        Up (healthy)    0.0.0.0:5050->5000/tcp
devops_fu-ml-service-1 Up (healthy)
devops_fu-postgres-1   Up (healthy)    5432/tcp
devops_fu-pgadmin-1    Up              0.0.0.0:8080->80/tcp
```

If a service is still starting, wait 30–60 seconds and run `docker compose ps` again.

### Step 3: Access the system

| Interface | URL | Credentials |
|---|---|---|
| Dashboard | http://localhost:5050 | No login required |
| pgAdmin | http://localhost:8080 | admin@admin.com / (value from .env) |
| API status | http://localhost:5050/api/status | No login required |

### Step 4: Run the full ML workflow

```bash
# Generate 5000 synthetic API access records
curl -s -X POST http://localhost:5050/api/data/generate \
  -H "Content-Type: application/json" \
  -d '{"count": 5000}' | python3 -m json.tool

# Train all three models (takes 30-90 s)
curl -s -X POST http://localhost:5050/api/analysis/train | python3 -m json.tool

# Classify all events and generate alerts
curl -s -X POST http://localhost:5050/api/analysis/analyze | python3 -m json.tool
```

Refresh the dashboard at http://localhost:5050 — charts should now be populated.

---

## Part 4: Kubernetes (Minikube) Installation

### Step 1: Install Minikube

**macOS:**
```bash
brew install minikube kubectl
```

**Linux:**
```bash
curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
sudo install minikube-linux-amd64 /usr/local/bin/minikube
```

**Windows (PowerShell as Administrator):**
```powershell
winget install Kubernetes.minikube
winget install Kubernetes.kubectl
```

### Step 2: Start the cluster

```bash
minikube start --memory=4096 --cpus=2
```

### Step 3: Build images inside Minikube's Docker daemon

```bash
# Point Docker CLI to Minikube's daemon
eval $(minikube docker-env)

# Build both service images
docker build -t access-api:latest        ./api
docker build -t access-ml-service:latest ./ml-service
```

> **Windows (PowerShell):** Replace `eval $(minikube docker-env)` with  
> `& minikube -p minikube docker-env --shell powershell | Invoke-Expression`

### Step 4: Deploy

```bash
kubectl apply -f k8s/config.yaml
```

### Step 5: Wait for the pod to become ready

```bash
kubectl get pods -n access-security -w
```

Wait until STATUS is `Running` and READY is `4/4`. This takes approximately **60–120 seconds** on first run.

```
NAME                               READY   STATUS    RESTARTS   AGE
access-security-7d8b9c5f6-xk2pq   4/4     Running   0          90s
```

Press `Ctrl+C` to stop watching.

### Step 6: Get service URLs

```bash
minikube service access-api-svc     -n access-security --url
minikube service access-pgadmin-svc -n access-security --url
```

### Step 7: Run the ML workflow

```bash
export API_URL=$(minikube service access-api-svc -n access-security --url)

curl -X POST $API_URL/api/data/generate \
  -H "Content-Type: application/json" -d '{"count": 5000}'
curl -X POST $API_URL/api/analysis/train
curl -X POST $API_URL/api/analysis/analyze
```

---

## Stopping and Resetting

### Docker Compose

```bash
# Stop containers (preserve data volumes)
docker compose down

# Stop and delete ALL data (full reset)
docker compose down -v

# Restart after changes to source code
docker compose up --build -d
```

### Kubernetes

```bash
# Delete all resources (data lost — PVCs deleted)
kubectl delete -f k8s/config.yaml
kubectl delete namespace access-security

# Stop Minikube
minikube stop

# Full Minikube reset
minikube delete
```
