# Project Status Report
## Batch 13 — Monitoring and Auto-Scaling Applications with Kubernetes and HPA
### Course-Based Project | DevOps | October 14, 2026

---

## 1. Project Overview

**What this project is:**
A small FastAPI inventory CRUD application used as a vehicle to demonstrate two DevOps concepts:
1. **Kubernetes Horizontal Pod Autoscaling (HPA)** — the app automatically spins up more copies of itself when CPU is high, and shrinks back when load drops.
2. **Application monitoring with Prometheus + Grafana** — a dashboard that shows request rates, error rates, and latency in real time.

**The app itself:** A REST API that lets you create, read, update, and delete inventory items (name, quantity, price). It uses SQLite as a database and exposes a `/metrics` endpoint that Prometheus scrapes.

---

## 2. What Was Done Today — Step by Step

### Phase 1: Tools Installation
Before anything could run, these tools were installed on the machine:

| Tool | Version | Purpose |
|---|---|---|
| Docker Desktop | 29.4.0 | Runs containers locally |
| kubectl | 1.34.1 | Talks to Kubernetes clusters |
| minikube | 1.39.0 | Creates a local Kubernetes cluster inside Docker |
| GitHub CLI (`gh`) | 2.102.0 | Push code to GitHub from the terminal |
| OpenSSL | 4.0.3 | Generate a random secret key |
| Python | 3.13.7 | Run the traffic simulation script |

All three new tools (minikube, gh, OpenSSL) were installed and added to the system PATH so every terminal can find them.

### Phase 2: GitHub Push
- Authenticated with GitHub account **Space-Xplorer** via `gh auth login`
- Created a new **private** repository: `https://github.com/Space-Xplorer/inventory-devops`
- Pushed all 3 commits including the B13 HPA changes
- GitHub Actions CI pipeline triggered automatically on push

**CI Pipeline result: ✅ PASSED in 2 minutes 7 seconds**
- 8/8 pytest tests passed
- pip-audit security scan passed
- Docker image built successfully
- Trivy vulnerability scan passed
- Image published to `ghcr.io/space-xplorer/inventory-devops`

**Security gates upgrade (applied after initial run):**
- `pip-audit` promoted to a **blocking gate** — `continue-on-error: true` removed. Job now fails if any dependency has a known vulnerability.
- `Trivy` promoted to a **blocking gate** — `exit-code` changed from `"0"` to `"1"`. Job now fails on CRITICAL or HIGH image vulnerabilities.
- `ignore-unfixed: true` added to Trivy — vulnerabilities with no upstream patch available do not block the build (avoids false positives).

### Phase 3: Kubernetes Deployment
Commands run in order:

```
minikube start --driver=docker --cpus=2 --memory=4096
minikube addons enable metrics-server
docker build -t inventory-api:local .
minikube image load inventory-api:local
kubectl apply -f k8s/namespace.yaml -f k8s/configmap.yaml
kubectl -n inventory create secret generic inventory-secret ...
kubectl apply -f k8s/deployment.yaml -f k8s/service.yaml -f k8s/hpa.yaml
```

**Everything deployed successfully:**
- Namespace `inventory` created
- ConfigMap `inventory-config` created
- Secret `inventory-secret` created (random 32-byte hex key)
- Deployment `inventory-api` created → 1 pod running
- Service `inventory-api` created (NodePort)
- HPA `inventory-api` created (1–4 replicas, 50% CPU target)

### Phase 4: HPA Demo — The Core of B13

**Before load:**
```
TARGETS: cpu 4%/50%    REPLICAS: 1
```
Pod sitting idle at ~4m CPU (4 millicores out of the 100m requested).

**CPU loop triggered inside the pod** (4-minute bounded loop):
```python
import time; end=time.monotonic()+240; exec("while time.monotonic()<end: pass")
```

**During load (at ~20 seconds):**
```
TARGETS: cpu 350%/50%   REPLICAS: 1  (HPA detected it)
```

**At ~50 seconds:**
```
TARGETS: cpu 483%/50%   REPLICAS: 4  ← SCALED UP ✅
```

**HPA scaling event recorded:**
```
Normal  SuccessfulRescale  New size: 4; reason: cpu resource utilization above target
```

**HPA conditions at peak:**
- `ScalingActive: True` — valid CPU metrics found
- `ScalingLimited: True` — hit maxReplicas: 4 (working as designed)
- `AbleToScale: True` — ready for new scale

**After load ended (~5 minutes later):**
```
TARGETS: cpu 4%/50%    REPLICAS: 1  ← SCALED BACK DOWN ✅
```

**Full cycle completed: 1 → 4 → 1 replicas**

### Phase 5: Monitoring Stack (Docker Compose)

```
docker compose up -d --build
python scripts/traffic.py http://localhost:8000 120
```

**2,346 requests sent** to the app over 2 minutes.

**Results at http://localhost:3000 (Grafana dashboard "Inventory API"):**

| Panel | What it showed |
|---|---|
| Request rate (req/s) | Peaked at ~20 req/s during the traffic run |
| Requests by endpoint | `/items`, `/health`, `/metrics`, `/docs` all visible |
| Error rate (4xx) | ~3 req/s of deliberate 404s (traffic script requests missing items) |
| p95 latency | ~95ms — 95% of requests completed in under 95ms |

**All 3 services healthy:**
- App: `http://localhost:8000` — status OK
- Prometheus: `http://localhost:9090` — target `inventory-api` **UP**, scraping every 5s
- Grafana: `http://localhost:3000` — dashboard loaded with populated graphs

---

## 3. Final State of Everything

| System | Status | Detail |
|---|---|---|
| GitHub repo | ✅ Live | `github.com/Space-Xplorer/inventory-devops` (private) |
| CI pipeline | ✅ Passed | 8/8 tests, Docker build, Trivy scan — 2m 7s |
| minikube cluster | ✅ Running | Kubernetes v1.37.0, 2 CPUs, 4GB RAM |
| metrics-server | ✅ Running | Provides CPU data to HPA |
| Deployment | ✅ Running | 1 pod (after scale-down), image `inventory-api:local` |
| Service | ✅ Running | NodePort, tunnel at `http://127.0.0.1:50102` |
| HPA | ✅ Demonstrated | Scaled 1→4→1, event recorded |
| Docker Compose app | ✅ Running | Port 8000 |
| Prometheus | ✅ Running | Port 9090, target UP |
| Grafana | ✅ Running | Port 3000, dashboard populated |

---

## 4. Key Numbers for the Viva

| Number | What it means |
|---|---|
| `100m` | CPU **requested** per pod (0.1 of a CPU core) |
| `500m` | CPU **limit** per pod (max 0.5 of a CPU core) |
| `50%` | HPA target — scale up when average CPU > 50% of request |
| `1` | Minimum replicas (always at least 1 pod) |
| `4` | Maximum replicas (HPA won't go beyond this) |
| `483%` | Peak CPU utilization recorded during the demo |
| `15s` | HPA controller default sync interval |
| `5 min` | Default scale-down stabilization window (prevents thrashing) |
| `2346` | HTTP requests sent during the Grafana traffic test |
| `~20 req/s` | Peak request rate seen in Grafana |
| `~95ms` | p95 latency — 95% of requests under 95 milliseconds |
| `8/8` | Tests passing in the pytest suite |
| `2m 7s` | Total CI pipeline time on GitHub Actions |

---

## 5. What Each File Does

```
app/
  main.py        — FastAPI app: routes, /health, /metrics endpoints
  models.py      — SQLAlchemy database model for an Item
  schemas.py     — Pydantic schemas: what the API accepts and returns
  database.py    — SQLite database connection setup

k8s/
  namespace.yaml   — Creates the "inventory" namespace to isolate resources
  configmap.yaml   — Non-secret config (DB path, app name) passed to pods
  secret.yaml      — API_KEY value (randomly generated, not committed)
  deployment.yaml  — Tells Kubernetes: run this container, with these resources
  service.yaml     — Exposes the pods so traffic can reach them
  hpa.yaml         — THE CENTERPIECE: autoscale 1-4 replicas at 50% CPU

monitoring/
  prometheus.yml              — Tells Prometheus where to scrape (/metrics every 5s)
  grafana/dashboards/         — Pre-built dashboard JSON (loads automatically)
  grafana/provisioning/       — Tells Grafana where the dashboard and data source are

tests/
  test_api.py    — 8 tests covering all CRUD endpoints + health

.github/workflows/ci.yml — CI: test → audit → build → scan → publish

docker-compose.yml — Runs app + Prometheus + Grafana together locally
Dockerfile         — How to build the container image
scripts/traffic.py — Sends HTTP requests to simulate user load
```

---

## 6. The Two Demo Paths (Important for Viva)

These are **separate** — they do not share data or communicate with each other.

### Path A: Kubernetes + HPA (the main B13 demo)
```
Your laptop → minikube tunnel → NodePort Service → Pod(s)
                                                      ↑
                                              kubelet reports CPU
                                                      ↓
                                           metrics-server collects it
                                                      ↓
                                          HPA reads it every 15s
                                                      ↓
                                     HPA tells Deployment: change replicas
```

### Path B: Docker Compose + Prometheus + Grafana (monitoring demo)
```
Your laptop → Docker app:8000 → FastAPI
                    ↑
        Prometheus scrapes /metrics every 5s
                    ↓
        Grafana queries Prometheus
                    ↓
        Dashboard shows graphs
```

Prometheus here watches the **Compose app on port 8000**, NOT the Kubernetes pods. The Grafana dashboard shows HTTP behavior (requests, errors, latency), not Kubernetes replica counts.

---

## 7. Syllabus Coverage

| B13 Requirement | How it's met | File |
|---|---|---|
| Kubernetes deployment | Deployment with 1 pod, namespace, configmap, secret | `k8s/deployment.yaml` |
| Resource management | CPU request 100m, limit 500m | `k8s/deployment.yaml` |
| Resource metrics | metrics-server addon, `kubectl top pods` | minikube addon |
| Horizontal Pod Autoscaling | autoscaling/v2, 1-4 replicas, 50% CPU | `k8s/hpa.yaml` |
| Load simulation | traffic.py, CPU loop diagnostic | `scripts/traffic.py` |
| Application monitoring | Prometheus + Grafana dashboard | `monitoring/` |
| CI/CD pipeline | GitHub Actions: test, build, scan (blocking), publish | `.github/workflows/ci.yml` |
| Container image | Multi-stage Dockerfile, ghcr.io publish | `Dockerfile` |
| Automated tests | 8 pytest tests, 100% pass | `tests/test_api.py` |
| Security scanning | pip-audit (blocking) + Trivy CRITICAL/HIGH blocking, ignore-unfixed | `.github/workflows/ci.yml` |

---

## 8. Known Limitations (Be Honest in the Viva)

- **SQLite is not shared across pods** — each pod has its own database on `emptyDir`. An item created through pod A may not appear when pod B handles the next request. This is fine for demonstrating scaling, but not a production-ready setup. Fix: replace SQLite with a shared PostgreSQL database.
- **HTTP traffic alone didn't trigger scaling** — the traffic script's 0.2s sleep between requests kept CPU too low. The CPU loop diagnostic was used instead. This is documented in the README and is an honest representation.
- **minikube is not production Kubernetes** — it's a single-node local cluster for learning. Production clusters run on cloud providers (EKS, GKE, AKS).
- **Grafana admin/admin password** — local demo only, never acceptable in production.
- **No real authentication** — the API_KEY secret is an example of how secrets work, but the app doesn't actually enforce it.

---

*Report generated: October 14, 2026 | Session run on Windows 11, Docker Desktop 29.4.0, minikube v1.39.0*
