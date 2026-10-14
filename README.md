# Batch 13: Monitoring and Auto-Scaling Applications with Kubernetes and HPA

## Project: Inventory API

A small FastAPI inventory CRUD service used to demonstrate **Kubernetes horizontal pod autoscaling**
and application monitoring. The app stays simple so the demo can focus on CPU metrics, replica counts,
and the request-rate, error-rate and latency graphs.

**Main result:** a Deployment starts at one replica and an HPA can increase it to four when average
CPU utilization exceeds 50% of the requested CPU. When load stops, it can return to one replica.

**Two separate demo paths:**
- Kubernetes + metrics-server + HPA: CPU utilization, automatic scaling and pod counts.
- Docker Compose + Prometheus + Grafana: application request rate, errors and latency.

The bundled Prometheus scrapes the Compose app at `app:8000`, not the Kubernetes pods. The Grafana
dashboard is the application-monitoring half of the demo, but it does not show Kubernetes replica
counts or drive this HPA. Moving Prometheus/Grafana into Kubernetes with per-pod discovery is future work.

## Architecture

```text
Kubernetes (minikube, namespace inventory)
  client traffic -> NodePort Service -> Inventory API Deployment (1-4 pods)
                                            |
                                each pod: SQLite on emptyDir
                                            |
  kubelet CPU metrics -> metrics-server -> metrics.k8s.io -> HPA controller
                                                             |
                                              updates Deployment replica count

Separate application-monitoring demo (Docker Compose)
  traffic -> FastAPI app <- scrape /metrics every 5s <- Prometheus <- Grafana

Supporting pipeline
  git push -> GitHub Actions -> pytest -> pip-audit -> Docker build -> Trivy -> ghcr.io
```

## Batch 13 / syllabus mapping

The selected topic is **Monitoring and Auto-Scaling Applications with Kubernetes and HPA**.

| Evidence | Project file / command | Topic link |
|---|---|---|
| Kubernetes workload and network | `k8s/deployment.yaml`, `service.yaml`, `namespace.yaml` | Kubernetes deployment (Unit III) |
| CPU request and limit | Deployment: request `100m`, limit `500m` | Resource management and HPA utilization denominator |
| Resource metrics | `minikube addons enable metrics-server`, `kubectl top pods` | Observe CPU and memory in Kubernetes |
| Automatic replica changes | `k8s/hpa.yaml`, `kubectl get hpa -w` | Core B13: CPU target 50%, min 1, max 4 |
| Load / response observation | `scripts/traffic.py`, `kubectl get pods -w` | Demonstrate load and scaling behavior |
| Application dashboard | `monitoring/`, `docker-compose.yml` | Monitoring (Unit IV): request rate, errors, p95 latency |
| CRUD backend and tests | `app/`, `tests/` | Supporting backend and testing labs |
| Container image | `Dockerfile`, `.dockerignore` | Supporting Docker lab (Unit III) |
| Automated checks and image publication | `.github/workflows/ci.yml` | Supporting CI/CD and DevSecOps (Unit IV) |

The unit links are the existing project's syllabus mapping; B13 is the main topic, not a replacement
for every lab. CI/CD, secrets and self-healing are supporting evidence rather than the main demo.

## Main demo: Kubernetes and HPA

Prerequisites: Docker running, minikube, kubectl, Python 3, and Bash (Linux, macOS or a configured WSL shell).
Run these commands from the unzipped `inventory-devops` directory. Allow several minutes for metrics
and scale-down. Rehearse on the actual laptop before the viva; no fixed scale-up time is guaranteed.

### 1. Build, enable metrics, deploy

```bash
minikube start --driver=docker --cpus=2 --memory=4096
minikube addons enable metrics-server

docker build -t inventory-api:local .
minikube image load inventory-api:local

kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
# The app does not enforce API_KEY; this optional Secret is a configuration example.
# Never commit a real Secret manifest or real values.
kubectl -n inventory create secret generic inventory-secret \
  --from-literal=API_KEY="$(openssl rand -hex 32)" \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f k8s/deployment.yaml -f k8s/service.yaml -f k8s/hpa.yaml
kubectl -n inventory rollout status deployment/inventory-api --timeout=180s
kubectl -n kube-system rollout status deployment/metrics-server --timeout=180s
kubectl -n inventory get hpa
kubectl -n inventory top pods
```

Initial HPA targets can show `<unknown>/50%` until samples are available. A ready metrics-server pod
does not itself prove the API has samples: `kubectl top pods` must succeed before starting the load demo.
If it does not, wait briefly and retry, then use the troubleshooting commands below.

### 2. Get the service URL (Terminal A)

```bash
minikube service inventory-api -n inventory --url
```

Copy the printed `http://...` URL. **Keep this terminal open** if minikube creates a tunnel, especially
with the Docker driver on macOS, Windows or WSL. Do not put this command in command substitution on
those systems: it may keep running to maintain the tunnel.

### 3. Watch the HPA and pods

Terminal B:
```bash
kubectl -n inventory get hpa -w
```

Terminal C:
```bash
kubectl -n inventory get pods -w
```

In another terminal, `kubectl -n inventory top pods` gives CPU usage snapshots. Point to HPA's
`TARGETS` (current utilization / 50% target) and `REPLICAS`. New pods should become Running/Ready;
Pending pods mean the cluster has not scheduled them yet, not that capacity is already serving traffic.

### 4. Send traffic to Kubernetes (Terminal D)

Set the URL to exactly the one printed in Terminal A, without a trailing slash:
```bash
API_URL='http://REPLACE_WITH_MINIKUBE_SERVICE_URL'
curl "$API_URL/health"
python3 scripts/traffic.py "$API_URL" 240
```

This script is intentionally throttled by a 0.2-second sleep and mainly does I/O. **One worker may
not produce enough CPU to scale.** For the scale-up rehearsal, use eight workers for four minutes:
```bash
for i in {1..8}; do
  python3 scripts/traffic.py "$API_URL" 240 > "/tmp/inventory-traffic-$i.log" 2>&1 &
done
wait
```

Load ends automatically. Check the log files for connection errors if the graphs or CPU do not move.
Each worker deliberately requests a missing item to produce 404s. At multiple replicas, per-pod SQLite
also means an item created through one connection may be absent on the next pod, so CRUD consistency
is not the scaling evidence. Use HPA CPU/replica readings and pod readiness as the evidence.

### 5. Deterministic CPU stimulus if HTTP traffic stays below target

This bounded diagnostic runs a CPU loop **inside one existing API pod**, using the Python already in
the image. It demonstrates CPU-triggered HPA behavior, not throughput-driven scaling or a production
benchmark. Use only in this local demo, and say what is running during the viva.

In Terminal D after the HTTP test, while the watchers remain open:
```bash
POD=$(kubectl -n inventory get pod -l app=inventory-api \
  -o jsonpath='{.items[0].metadata.name}')
kubectl -n inventory exec "$POD" -- python -c \
  'import time; end=time.monotonic()+240; exec("while time.monotonic()<end: pass")'
```

The loop stops after four minutes. The existing `500m` CPU limit bounds that container's usage.
With a `100m` request, `50m` average CPU is already 50% utilization. A busy pod can therefore raise
the average across the Deployment enough for the HPA to request more pods. Actual sampling, startup,
CPU availability and HPA tolerance affect what you see; verify the current readings rather than claiming
an exact timing. Do not manually scale the Deployment while the HPA is active.

### 6. Show scale-down and capture evidence

After all load has ended:
```bash
kubectl -n inventory get hpa
kubectl -n inventory top pods
kubectl -n inventory get pods
kubectl -n inventory describe hpa inventory-api
```

Leave the watchers running. Scale-down normally waits for the default five-minute stabilization
window plus sampling/controller delays. It is not instant. Capture screenshots of:
1. One ready pod and HPA target 50% before load.
2. Higher CPU utilization, increased HPA replica count and additional ready pods during load.
3. Return toward one replica after load stops and stabilization has elapsed.

For a repeat demo, wait for scale-down before starting the next load test. Reapplying the Deployment
manifest's `replicas: 1` can temporarily reset the replica count, so don't reapply it during the evidence run.

## Monitoring half: Prometheus and Grafana (separate Compose app)

Keep the monitoring files unchanged and use their own local app. This is separate from the Kubernetes
HPA path above, and has its own SQLite database.

```bash
docker compose up -d --build
python3 scripts/traffic.py http://localhost:8000 120
```

- API docs: http://localhost:8000/docs
- Prometheus: http://localhost:9090. Status > Targets should show `inventory-api` UP.
- Grafana: http://localhost:3000, login `admin` / `admin`, dashboard **Inventory API**.
- Explain request rate, requests by endpoint, deliberate 404s, and p95 request latency.
- Let traffic run for at least a minute so rate windows have samples; p95 uses a five-minute range.

Take a dashboard screenshot after the panels populate. Grafana/Prometheus measure application HTTP
behavior here. HPA uses CPU from metrics-server, not these HTTP graphs.

Stop the Compose stack with `docker compose down`; add `-v` only if you also want to delete its data volume.

## HPA troubleshooting

```bash
kubectl -n inventory describe hpa inventory-api
kubectl -n inventory top pods
kubectl get apiservice v1beta1.metrics.k8s.io
kubectl -n kube-system logs deployment/metrics-server --tail=80
kubectl -n inventory get events --sort-by=.lastTimestamp
```

- `<unknown>` / `FailedGetResourceMetric`: confirm metrics-server, a working metrics API and CPU requests.
- CPU stays below 50%: use concurrent traffic or the explicitly labeled CPU-loop diagnostic.
- `ScalingLimited` at four replicas: expected when the recommendation exceeds `maxReplicas: 4`.
- Pods Pending: inspect events and cluster resource capacity. HPA cannot create extra physical CPU.
- `ImagePullBackOff`: confirm the local image was loaded into this minikube profile.
- Service unreachable: check pod readiness, the exact service URL, and the open tunnel terminal.

## Local app and tests (optional supporting demo)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
uvicorn app.main:app --reload
```

Try it against the single local app:
```bash
curl -X POST localhost:8000/items -H 'Content-Type: application/json' \
  -d '{"name":"Laptop","quantity":5,"price":799.5}'
curl localhost:8000/items
curl localhost:8000/metrics | head
```

## CI/CD and GitHub (supporting evidence)

The ZIP preserves the original Git history. The B13 edits are included in a local commit so the helper
pushes the updated README and HPA. To create a new private repository, with GitHub CLI installed:
```bash
./PUSH_TO_GITHUB.sh
```

If a repository named `inventory-devops` already exists, do not run the create helper against it.
Use the correct existing remote and push the updated commit yourself, or pass a new repo name:
`./PUSH_TO_GITHUB.sh inventory-devops-b13`. Check the local Git author email matches your GitHub email.

On push/PR to `main`, Actions runs pytest, pip-audit, Docker build and Trivy. Pushes publish to
`ghcr.io/<owner>/<repo>` with SHA and latest tags using `GITHUB_TOKEN`. Security scans remain report-only
while establishing a baseline. The supplied minikube Deployment deliberately uses the locally loaded
image, not the registry image. For a registry image, update `image:` and configure registry access;
a public package can be pulled without private-package credentials.

## Viva prep

- **What is HPA?** A controller that changes a workload's replica count based on observed metrics.
  Here `autoscaling/v2` targets the `inventory-api` Deployment, with 1-4 replicas and 50% CPU utilization.
- **How does it decide?** The basic rule is
  `desiredReplicas = ceil(currentReplicas * currentAverageUtilization / targetUtilization)`.
  For example, 2 pods averaging 100% against a 50% target suggest 4 pods. Tolerance, missing samples,
  readiness, stabilization and min/max bounds can modify the actual decision.
- **Why do CPU requests matter?** Utilization is usage divided by requested CPU, not by the CPU limit
  or the whole machine. Our request is `100m` (0.1 CPU); `50m` usage is 50%. Missing CPU requests can
  make CPU-utilization metrics undefined and prevent scaling for that metric.
- **Request vs limit?** A request is used for scheduling and utilization calculations. A limit caps usage;
  the API container has a `500m` CPU limit and may be throttled above it.
- **What is metrics-server?** It exposes Kubernetes resource metrics through `metrics.k8s.io`, used by
  `kubectl top` and this HPA. It is not Prometheus and not the Grafana dashboard's data source.
- **How fast does HPA react?** The default controller sync interval is 15 seconds, but metrics availability,
  startup and stabilization also matter. Do not promise a scale-up exactly 15 seconds after starting load.
- **Why doesn't it immediately scale down?** The default downscale stabilization window is five minutes,
  which reduces rapid replica changes when load fluctuates.
- **What does maxReplicas protect?** It limits this workload to four replicas. HPA scales pods, not nodes;
  it cannot guarantee the cluster has enough resources to schedule them.
- **Why use a CPU loop?** The unchanged HTTP script may not create sustained CPU demand. The bounded loop
  verifies CPU-driven scaling directly and is clearly a diagnostic, not a claim about real user throughput.
- **Why is SQLite a limitation?** Every Kubernetes replica has its own `emptyDir` and database. Reads and
  writes can differ between replicas, and replacing a pod loses its data. Fine for demonstrating scaling
  mechanics, not for a correct multi-replica inventory service. A shared PostgreSQL database is future work.
- **Prometheus vs Grafana?** Prometheus scrapes and stores metrics; Grafana queries it and shows graphs.
  Here `/metrics` exposes request counters and duration histograms. Compose scrapes its own app every 5 s.
- **What does p95 latency mean?** An estimated duration under which 95% of observed requests fall, calculated
  from histogram buckets. It is not CPU utilization and is not the HPA input in this project.
- **Readiness vs liveness?** Readiness controls whether a pod receives Service traffic. Liveness restarts
  a stuck container. Both use `/health` here.
- **ConfigMap vs Secret?** Plain settings vs sensitive values. Never commit real secrets. Base64 encoding
  alone is not encryption; API_KEY is only a mounted example and does not authenticate this app.
- **What is CI/CD here?** CI tests and builds; the pipeline publishes an image. Deployment to minikube is
  manual with kubectl, so it is not an automatic production deployment pipeline.

## Cleanup

After capturing screenshots, stop watchers and any service tunnel with Ctrl-C, then:
```bash
kubectl delete namespace inventory
docker compose down
minikube stop
```

Deleting the namespace deletes its demo databases. Metrics-server stays enabled in the minikube profile.

## Known limitations and verification boundary

- Kubernetes replicas do not share SQLite state; pod replacement loses its database (`emptyDir`).
- API authentication is intentionally absent. Grafana's admin/admin login is for local demo only.
- The existing app, tests, Dockerfile, CI, Compose, traffic script and Grafana files are unchanged.
- The B13 revision was checked with the Python test suite and static YAML/JSON checks. Docker,
  minikube/HPA and the live Grafana rendering were not run in the preparation environment. The first
  actual laptop rehearsal is the integration test. Do not describe screenshots or scale-up as already verified.

## Future work

Shared PostgreSQL for consistent inventory data; Prometheus/Grafana in Kubernetes with per-pod discovery;
replica/CPU dashboard panels and alerts; production auth; cluster autoscaling; Terraform or ArgoCD.

## Technical references

- HPA mechanics, resource requests, metrics API and stabilization:
  https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/
- Minikube service access and Docker-driver tunnels:
  https://minikube.sigs.k8s.io/docs/handbook/accessing/
