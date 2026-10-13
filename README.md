# Inventory API - DevOps Mini Project

A small FastAPI CRUD service (inventory items) delivered through a full DevOps pipeline:
Git workflow, automated tests, Docker, CI/CD on GitHub Actions, security scans, Kubernetes on minikube,
and Prometheus + Grafana monitoring.

The application is deliberately simple. The graded part is the pipeline around it.

## Architecture

```
 Developer --git push--> GitHub
                           |
                           v
                 GitHub Actions (.github/workflows/ci.yml)
        test (pytest) -> pip-audit (report-only) -> docker build
              -> Trivy scan (report-only) -> push image to ghcr.io

 Local / demo stack (docker compose)            Kubernetes (minikube, namespace "inventory")
 +---------+   /metrics   +------------+        +--------------------------------------+
 |  app    | <----------- | Prometheus |        | Service (NodePort) -> Deployment       |
 | FastAPI |   scrape 5s  +-----+------+        |   pod: api (probes on /health)         |
 | SQLite  |                    |               |   ConfigMap (settings), Secret (keys)  |
 +---------+                    v               +--------------------------------------+
                           +---------+
                           | Grafana |  dashboard "Inventory API"
                           +---------+
```

## What each piece does

| Path | Purpose | Syllabus unit |
|---|---|---|
| `app/main.py` | CRUD endpoints `/items`, `/health`, `/metrics` | CRUD backend lab |
| `tests/` | pytest suite: CRUD, 404s, validation, health, metrics | Unit IV testing |
| `requirements.txt` | pinned versions, tested on a clean virtualenv | reproducible builds |
| `Dockerfile`, `.dockerignore` | slim image, non-root user, HEALTHCHECK | Unit III Docker |
| `docker-compose.yml` | app + Prometheus + Grafana | containerized app, Unit IV monitoring |
| `monitoring/` | Prometheus scrape config, provisioned Grafana dashboard | monitoring dashboard lab |
| `.github/workflows/ci.yml` | test, scan, build, push | Unit IV CI/CD, GitHub Actions, DevSecOps |
| `k8s/` | namespace, ConfigMap, Secret example, Deployment, Service, HPA (stretch) | Unit III Kubernetes |
| `scripts/traffic.py` | load generator so the dashboard moves | demo |

## Run locally (no Docker)

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
uvicorn app.main:app --reload       # http://localhost:8000/docs
```

Try it:
```bash
curl -X POST localhost:8000/items -H 'Content-Type: application/json' \
  -d '{"name":"Laptop","quantity":5,"price":799.5}'
curl localhost:8000/items
curl localhost:8000/metrics | head
```

## Run with Docker + monitoring

```bash
docker compose up --build
```
- API docs: http://localhost:8000/docs
- Prometheus: http://localhost:9090 (Status > Targets should show `inventory-api` UP)
- Grafana: http://localhost:3000 (login admin / admin), dashboard "Inventory API"
- Make the graphs move: `python3 scripts/traffic.py http://localhost:8000 120`

Stop: `docker compose down` (add `-v` to also delete the data volume).

## Run on Kubernetes (minikube)

Prerequisites: Docker, minikube, kubectl.

```bash
minikube start --driver=docker
docker build -t inventory-api:local .
minikube image load inventory-api:local        # the deployment uses this local image

kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl -n inventory create secret generic inventory-secret --from-literal=API_KEY="$(openssl rand -hex 32)"
kubectl apply -f k8s/deployment.yaml -f k8s/service.yaml
kubectl -n inventory rollout status deploy/inventory-api

minikube service inventory-api -n inventory --url      # open this URL + /docs
```

Never commit a real Secret manifest or values. `k8s/secret.example.yaml` only has a placeholder, and
`k8s/secret.yaml` is in `.gitignore`.

To use the image built by CI instead: in `k8s/deployment.yaml` change `image:` to
`ghcr.io/<your-github-user>/<repo>:latest` (lower case), and make the package public in GitHub (Packages settings).

## CI/CD pipeline

On every push or PR to `main`: `test` (pytest, then pip-audit) and then `build-push` (docker build, Trivy scan,
and on pushes only, push to `ghcr.io/<owner>/<repo>` tagged with the commit SHA and `latest`).
pip-audit and Trivy are **report-only** during setup (`continue-on-error` / `exit-code: 0`). Once there is a
baseline, make them blocking by removing `continue-on-error` and setting Trivy `exit-code: "1"` at an agreed
severity. Authentication to ghcr.io uses the built-in `GITHUB_TOKEN`, so no secrets need to be created.

## Demo script (about 5 minutes)

1. **Pipeline.** Make a small change on a branch, open a PR, show Actions running tests. Merge, show the image in
   the repo's Packages tab. Optional: break one test on purpose, show the red run, fix it, show green.
2. **Monitoring.** `docker compose up -d`, open Grafana, run `python3 scripts/traffic.py http://localhost:8000 120`,
   point at request rate, per-endpoint rate, 4xx errors (the 404 probe) and p95 latency.
3. **Kubernetes, self-healing.** `kubectl -n inventory get pods`, then
   `kubectl -n inventory delete pod -l app=inventory-api`, then `kubectl -n inventory get pods -w`: a new pod appears.
4. **Rollout and rollback.** Change an env value in `k8s/configmap.yaml` or the image tag, then
   `kubectl -n inventory rollout restart deploy/inventory-api`, `kubectl -n inventory rollout status deploy/inventory-api`,
   and `kubectl -n inventory rollout undo deploy/inventory-api`.
5. **Manual scaling.** `kubectl -n inventory scale deploy/inventory-api --replicas=3`, `kubectl -n inventory get pods`,
   then scale back to 1.

HPA (`k8s/hpa.yaml`) is a stretch item: it needs `minikube addons enable metrics-server` and real CPU load to fire.
Do not rely on it in the demo.

## Viva prep: questions you should be able to answer

- **Why Docker over a VM?** Shares the host kernel, starts in seconds, image is about a hundred MB, reproducible.
- **Why multi-stage or slim base?** `python:3.12-slim` keeps the image small. The container runs as a non-root user.
- **What does the HEALTHCHECK / readiness / liveness probe do?** All call `/health`. Readiness gates traffic to the pod,
  liveness restarts a stuck pod.
- **ConfigMap vs Secret?** ConfigMap for plain settings, Secret for sensitive values. Neither is committed with real
  values. Secrets are only base64 encoded by default, not encrypted.
- **Why replicas: 1?** SQLite lives in a per-pod volume, so more replicas would each hold different data. A real
  deployment would use a shared database such as PostgreSQL. This is a known limitation and future work.
- **Why pin requirements?** Same versions everywhere, so CI builds are reproducible.
- **What do pip-audit and Trivy do?** pip-audit checks Python dependencies for known vulnerabilities, Trivy scans the
  built image. Both are report-only for now (DevSecOps).
- **What does Prometheus scrape and how?** `/metrics` every 5 s (pull model). Metrics come from
  `prometheus-fastapi-instrumentator`: `http_requests_total`, `http_request_duration_seconds`.
- **What is CI vs CD here?** CI = test and build on every push. CD here = image pushed to a registry and deployed to
  minikube with kubectl.

## Future work (outside the critical path)

Terraform (infrastructure as code), ArgoCD (GitOps), Jenkins as an alternative CI, PostgreSQL with multiple replicas,
Prometheus alert rules, Splunk or New Relic for logging.

## Known limitations

- SQLite data is lost when a Kubernetes pod is replaced (emptyDir).
- No authentication on the API (kept simple on purpose).
- Grafana runs with the default admin/admin login for local demo only.
