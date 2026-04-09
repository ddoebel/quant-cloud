Below is a **Phase 1 build guide** you can execute now.

I’m assuming:

- all 3 current nodes run **Ubuntu/Debian-like Linux**
    
- you want **3 nodes now** and the design should remain compatible with a **future 4th node**
    
- you’re okay using **GHCR** for container images
    
- you want **K3s + Tailscale + Helm + Postgres + RabbitMQ + FastAPI + Celery worker**
    

K3s supports a lightweight server/agent model, Tailscale can be installed on Linux with its install script or distro packages, Helm is the standard package manager for Kubernetes, Kubernetes Secrets are the right place for passwords/API keys, and Celery supports RabbitMQ as a broker. ([K3s](https://docs.k3s.io/quick-start?utm_source=chatgpt.com "Quick-Start Guide"))

---

# Phase 1 target state

You will end with:

- **VPS** = K3s server/control plane + lightweight workloads
    
- **Laptop** = worker
    
- **Pentium** = worker, but tainted for burst jobs only
    
- **Tailscale** mesh between all nodes
    
- **Postgres** in Kubernetes
    
- **RabbitMQ** in Kubernetes
    
- **FastAPI API** deployed in Kubernetes
    
- **Celery worker** deployed in Kubernetes
    

Labels and taints are built-in Kubernetes mechanisms for placement control, which is why I use them here for node roles and the Pentium burst node. ([Kubernetes](https://kubernetes.io/docs/concepts/overview/working-with-objects/labels/?utm_source=chatgpt.com "Labels and Selectors"))

---

# 0. Pick names first

Use these names consistently:

- VPS hostname: `qc-vps`
    
- Laptop hostname: `qc-laptop`
    
- Pentium hostname: `qc-burst`
    

Use these environment placeholders in the commands below:

```bash
export TAILNET_NAME="your-tailnet"
export VPS_HOSTNAME="qc-vps"
export LAPTOP_HOSTNAME="qc-laptop"
export BURST_HOSTNAME="qc-burst"

export K3S_VERSION=""   # leave empty unless you want to pin
export CLUSTER_NAME="quant-cloud"

export PG_PASSWORD="CHANGE_ME_STRONG_POSTGRES_PASSWORD"
export RABBITMQ_PASSWORD="CHANGE_ME_STRONG_RABBITMQ_PASSWORD"
export API_KEY="CHANGE_ME_STRONG_API_KEY"

export GH_USER="YOUR_GITHUB_USERNAME"
export GH_REPO="option-pricing-cluster"
export GHCR_IMAGE_PREFIX="ghcr.io/$GH_USER/$GH_REPO"
```

---

# 1. Prepare all 3 nodes

Run this on **each node**.

```bash
sudo hostnamectl set-hostname qc-REPLACE-ME
sudo apt update
sudo apt install -y curl wget git vim ca-certificates gnupg lsb-release jq apt-transport-https
```

Replace `qc-REPLACE-ME` with:

- `qc-vps`
    
- `qc-laptop`
    
- `qc-burst`
    

Optional but useful:

```bash
echo "127.0.0.1 $(hostname)" | sudo tee -a /etc/hosts
```

---

# 2. Install Tailscale on all 3 nodes

Tailscale’s Linux docs support installing with their script. ([Tailscale](https://tailscale.com/docs/install/linux?utm_source=chatgpt.com "Install Tailscale on Linux"))

Run on **each node**:

```bash
curl -fsSL https://tailscale.com/install.sh | sh
```

Then bring each node into your tailnet.

On the **VPS**:

```bash
sudo tailscale up --ssh --hostname qc-vps
```

On the **laptop**:

```bash
sudo tailscale up --ssh --hostname qc-laptop
```

On the **Pentium**:

```bash
sudo tailscale up --ssh --hostname qc-burst
```

Now verify on each node:

```bash
tailscale ip -4
tailscale status
```

From the VPS, test reachability:

```bash
ping -c 3 qc-laptop
ping -c 3 qc-burst
```

If name resolution does not work, use the Tailscale IPs from `tailscale ip -4`.

Keep reverse SSH as your fallback path, but for K3s node-to-node traffic use the Tailscale private addresses.

---

# 3. Install K3s server on the VPS

K3s’ quick-start shows using the install script for the server, and agent nodes join with `K3S_URL` and `K3S_TOKEN`. ([K3s](https://docs.k3s.io/quick-start?utm_source=chatgpt.com "Quick-Start Guide"))

First get the VPS Tailscale IP:

```bash
tailscale ip -4
```

Assume it returns something like `100.64.0.10`.

Install K3s server on the VPS:

```bash
curl -sfL https://get.k3s.io | sh -s - \
  --write-kubeconfig-mode 644 \
  --node-name qc-vps \
  --tls-san 100.64.0.10
```

Check it:

```bash
sudo kubectl get nodes -o wide
sudo kubectl get pods -A
```

Get the join token:

```bash
sudo cat /var/lib/rancher/k3s/server/node-token
```

Save that token somewhere safe.

Copy kubeconfig for your normal user:

```bash
mkdir -p ~/.kube
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown $USER:$USER ~/.kube/config
sed -i 's/127.0.0.1/100.64.0.10/' ~/.kube/config
```

Test:

```bash
kubectl get nodes
```

---

# 4. Install K3s agents on the laptop and Pentium

On **laptop** and **Pentium**, use the K3s agent install method with `K3S_URL` and `K3S_TOKEN`. ([K3s](https://docs.k3s.io/quick-start?utm_source=chatgpt.com "Quick-Start Guide"))

Replace:

- `100.64.0.10` with the VPS Tailscale IP
    
- `TOKEN_HERE` with the token from step 3
    

On the **laptop**:

```bash
curl -sfL https://get.k3s.io | K3S_URL=https://100.64.0.10:6443 K3S_TOKEN=TOKEN_HERE sh -s - --node-name qc-laptop
```

On the **Pentium**:

```bash
curl -sfL https://get.k3s.io | K3S_URL=https://100.64.0.10:6443 K3S_TOKEN=TOKEN_HERE sh -s - --node-name qc-burst
```

Back on the VPS:

```bash
kubectl get nodes -o wide
```

You should see all 3 nodes in `Ready`.

---

# 5. Label and taint the nodes

Kubernetes supports labels for organizing/selecting objects and taints/tolerations for scheduling control. ([Kubernetes](https://kubernetes.io/docs/concepts/overview/working-with-objects/labels/?utm_source=chatgpt.com "Labels and Selectors"))

Run on the VPS:

```bash
kubectl label node qc-vps quantcloud/node-role=control --overwrite
kubectl label node qc-laptop quantcloud/node-role=worker-main --overwrite
kubectl label node qc-burst quantcloud/node-role=worker-burst --overwrite
```

Taint the burst node so only tolerated workloads land there:

```bash
kubectl taint node qc-burst quantcloud/burst=true:NoSchedule
```

Verify:

```bash
kubectl get nodes --show-labels
kubectl describe node qc-burst | grep -A5 Taints
```

---

# 6. Install Helm on the VPS

Helm’s official docs provide the install script. ([Helm](https://helm.sh/docs/intro/install?utm_source=chatgpt.com "Installing Helm"))

```bash
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
helm version
```

Add the Bitnami repo and refresh:

```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update
```

---

# 7. Create namespaces

```bash
kubectl create namespace quant-cloud
kubectl create namespace observability
```

For Phase 1, you’ll only use `quant-cloud`.

---

# 8. Create Kubernetes secrets

Kubernetes Secrets are intended for passwords, tokens, and keys. ([Kubernetes](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_create/kubectl_create_secret_generic/?utm_source=chatgpt.com "kubectl create secret generic"))

```bash
kubectl -n quant-cloud create secret generic quant-cloud-secrets \
  --from-literal=POSTGRES_PASSWORD="$PG_PASSWORD" \
  --from-literal=RABBITMQ_PASSWORD="$RABBITMQ_PASSWORD" \
  --from-literal=API_KEY="$API_KEY"
```

Verify names only:

```bash
kubectl -n quant-cloud get secret
```

---

# 9. Install PostgreSQL with Helm

The Bitnami PostgreSQL chart is a standard Helm-based deployment path. ([Artifact Hub](https://artifacthub.io/packages/helm/bitnami/postgresql?utm_source=chatgpt.com "Bitnami Secure Images Helm chart for PostgreSQL"))

Create a values file on the VPS.

```bash
cat > pg-values.yaml <<'EOF'
auth:
  username: quant
  password: CHANGE_ME_STRONG_POSTGRES_PASSWORD
  database: quantcloud

primary:
  nodeSelector:
    quantcloud/node-role: worker-main

  persistence:
    enabled: true
    size: 20Gi

  resources:
    requests:
      cpu: "250m"
      memory: "512Mi"
    limits:
      cpu: "1"
      memory: "1Gi"
EOF
```

Inject your real password:

```bash
sed -i "s/CHANGE_ME_STRONG_POSTGRES_PASSWORD/$PG_PASSWORD/" pg-values.yaml
```

Install:

```bash
helm install postgres bitnami/postgresql \
  -n quant-cloud \
  -f pg-values.yaml
```

Watch it come up:

```bash
kubectl -n quant-cloud get pods -w
```

Check service:

```bash
kubectl -n quant-cloud get svc postgres-postgresql
```

Quick connectivity test from inside cluster (DNS-independent):

```bash
kubectl -n quant-cloud exec "$(kubectl -n quant-cloud get pod -l app.kubernetes.io/name=postgresql -o jsonpath='{.items[0].metadata.name}')" -- \
  env PGPASSWORD="$PG_PASSWORD" psql -U quant -d quantcloud -c '\dt'
```

---

# 10. Install RabbitMQ with Helm

The Bitnami RabbitMQ chart is a standard Helm deployment path; RabbitMQ is a supported Celery broker. ([Artifact Hub](https://artifacthub.io/packages/helm/bitnami/rabbitmq?utm_source=chatgpt.com "rabbitmq 16.0.14 · bitnami/bitnami"))

Create values:

```bash
cat > rabbitmq-values.yaml <<'EOF'
auth:
  username: quant
  password: CHANGE_ME_STRONG_RABBITMQ_PASSWORD

replicaCount: 1

persistence:
  enabled: true
  size: 8Gi

resources:
  requests:
    cpu: "250m"
    memory: "256Mi"
  limits:
    cpu: "1"
    memory: "1Gi"

nodeSelector:
  quantcloud/node-role: worker-main
EOF
```

Inject your real password:

```bash
sed -i "s/CHANGE_ME_STRONG_RABBITMQ_PASSWORD/$RABBITMQ_PASSWORD/" rabbitmq-values.yaml
```

Install:

```bash
helm install rabbitmq bitnami/rabbitmq \
  -n quant-cloud \
  -f rabbitmq-values.yaml
```

Check:

```bash
kubectl -n quant-cloud get pods
kubectl -n quant-cloud get svc rabbitmq
```

Test AMQP port exists:

```bash
kubectl -n quant-cloud get svc rabbitmq -o wide
```

---

# 11. Create your Phase 1 app repo layout

Do this on your laptop or dev machine.

```bash
mkdir -p ~/quant-cloud-phase1
cd ~/quant-cloud-phase1

mkdir -p app/api app/worker k8s
touch app/api/main.py app/worker/celery_app.py app/worker/tasks.py
touch Dockerfile.api Dockerfile.worker requirements.txt
```

Create `requirements.txt`:

```bash
cat > requirements.txt <<'EOF'
fastapi==0.135.3
uvicorn[standard]==0.38.0
celery==5.6.0
psycopg[binary]==3.2.12
SQLAlchemy==2.0.44
pydantic==2.12.0
EOF
```

FastAPI’s docs explicitly recommend container images for Kubernetes-style deployment. ([FastAPI](https://fastapi.tiangolo.com/deployment/docker/?utm_source=chatgpt.com "FastAPI in Containers - Docker"))

Create `app/worker/celery_app.py`:

```bash
cat > app/worker/celery_app.py <<'EOF'
from celery import Celery
import os

RABBITMQ_USER = os.getenv("RABBITMQ_USER", "quant")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "changeme")
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq.quant-cloud.svc.cluster.local")
RABBITMQ_PORT = os.getenv("RABBITMQ_PORT", "5672")

broker_url = f"amqp://{RABBITMQ_USER}:{RABBITMQ_PASSWORD}@{RABBITMQ_HOST}:{RABBITMQ_PORT}//"

celery_app = Celery("quantcloud", broker=broker_url, backend=None)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)
EOF
```

Create `app/worker/tasks.py`:

```bash
cat > app/worker/tasks.py <<'EOF'
from .celery_app import celery_app
import time

@celery_app.task(bind=True, autoretry_for=(Exception,), retry_kwargs={"max_retries": 3})
def run_pricing_job(self, payload: dict):
    seconds = int(payload.get("sleep_seconds", 10))
    time.sleep(seconds)
    return {
        "status": "ok",
        "job_type": payload.get("job_type", "demo"),
        "sleep_seconds": seconds,
    }
EOF
```

Create `app/api/main.py`:

```bash
cat > app/api/main.py <<'EOF'
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from celery.result import AsyncResult
import os

from app.worker.celery_app import celery_app
from app.worker.tasks import run_pricing_job

app = FastAPI(title="Quant Cloud API")

API_KEY = os.getenv("API_KEY", "changeme")

class JobRequest(BaseModel):
    job_type: str
    sleep_seconds: int = 10

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/jobs")
def submit_job(job: JobRequest, x_api_key: str = Header(default="")):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="invalid api key")

    task = run_pricing_job.delay(job.model_dump())
    return {"task_id": task.id, "status": "queued"}

@app.get("/jobs/{task_id}")
def get_job(task_id: str, x_api_key: str = Header(default="")):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="invalid api key")

    result = AsyncResult(task_id, app=celery_app)
    response = {"task_id": task.id, "state": result.state}

    if result.ready():
        try:
            response["result"] = result.result
        except Exception as exc:
            response["error"] = str(exc)

    return response
EOF
```

Create `Dockerfile.api`:

```bash
cat > Dockerfile.api <<'EOF'
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
ENV PYTHONPATH=/app
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
EOF
```

Create `Dockerfile.worker`:

```bash
cat > Dockerfile.worker <<'EOF'
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
ENV PYTHONPATH=/app
CMD ["celery", "-A", "app.worker.celery_app:celery_app", "worker", "--loglevel=INFO"]
EOF
```

---

# 12. Build and push images to GHCR

Log into GHCR first. Use a GitHub token with package write permission.

```bash
echo YOUR_GITHUB_TOKEN | docker login ghcr.io -u "$GH_USER" --password-stdin
```

Build and push the API image:

```bash
docker build -t $GHCR_IMAGE_PREFIX/api:phase1 -f Dockerfile.api .
docker push $GHCR_IMAGE_PREFIX/api:phase1
```

Build and push the worker image:

```bash
docker build -t $GHCR_IMAGE_PREFIX/worker:phase1 -f Dockerfile.worker .
docker push $GHCR_IMAGE_PREFIX/worker:phase1
```

If your GHCR repo is private, create an image pull secret. Kubernetes supports registry secrets for this. ([Kubernetes](https://kubernetes.io/docs/tasks/configure-pod-container/pull-image-private-registry/?utm_source=chatgpt.com "Pull an Image from a Private Registry"))

```bash
kubectl -n quant-cloud create secret docker-registry ghcr-creds \
  --docker-server=ghcr.io \
  --docker-username="$GH_USER" \
  --docker-password="YOUR_GITHUB_TOKEN"
```

---

# 13. Deploy the API and worker

Create a manifest:

```bash
cat > k8s/phase1.yaml <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: quant-api
  namespace: quant-cloud
spec:
  replicas: 1
  selector:
    matchLabels:
      app: quant-api
  template:
    metadata:
      labels:
        app: quant-api
    spec:
      imagePullSecrets:
      - name: ghcr-creds
      nodeSelector:
        quantcloud/node-role: control
      containers:
      - name: api
        image: $GHCR_IMAGE_PREFIX/api:phase1
        ports:
        - containerPort: 8000
        env:
        - name: API_KEY
          valueFrom:
            secretKeyRef:
              name: quant-cloud-secrets
              key: API_KEY
        - name: RABBITMQ_USER
          value: quant
        - name: RABBITMQ_PASSWORD
          valueFrom:
            secretKeyRef:
              name: quant-cloud-secrets
              key: RABBITMQ_PASSWORD
        - name: RABBITMQ_HOST
          value: rabbitmq.quant-cloud.svc.cluster.local
        resources:
          requests:
            cpu: "100m"
            memory: "128Mi"
          limits:
            cpu: "500m"
            memory: "512Mi"
---
apiVersion: v1
kind: Service
metadata:
  name: quant-api
  namespace: quant-cloud
spec:
  selector:
    app: quant-api
  ports:
  - port: 80
    targetPort: 8000
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: quant-worker
  namespace: quant-cloud
spec:
  replicas: 1
  selector:
    matchLabels:
      app: quant-worker
  template:
    metadata:
      labels:
        app: quant-worker
    spec:
      imagePullSecrets:
      - name: ghcr-creds
      nodeSelector:
        quantcloud/node-role: worker-main
      containers:
      - name: worker
        image: $GHCR_IMAGE_PREFIX/worker:phase1
        env:
        - name: RABBITMQ_USER
          value: quant
        - name: RABBITMQ_PASSWORD
          valueFrom:
            secretKeyRef:
              name: quant-cloud-secrets
              key: RABBITMQ_PASSWORD
        - name: RABBITMQ_HOST
          value: rabbitmq.quant-cloud.svc.cluster.local
        resources:
          requests:
            cpu: "250m"
            memory: "256Mi"
          limits:
            cpu: "2"
            memory: "1Gi"
EOF
```

Apply it:

```bash
kubectl apply -f k8s/phase1.yaml
```

Check:

```bash
kubectl -n quant-cloud get deploy,po,svc
kubectl -n quant-cloud logs deploy/quant-worker
kubectl -n quant-cloud logs deploy/quant-api
```

Deployments are the standard Kubernetes controller for long-running stateless application workloads. ([Kubernetes](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/?utm_source=chatgpt.com "Deployments"))

---

# 14. Expose the API temporarily for testing

For Phase 1, use port-forward first.

```bash
kubectl -n quant-cloud port-forward svc/quant-api 8000:80
```

In a second terminal:

```bash
curl http://127.0.0.1:8000/health
```

Submit a job:

```bash
curl -X POST http://127.0.0.1:8000/jobs \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"job_type":"demo-monte-carlo","sleep_seconds":15}'
```

It returns a `task_id`. Poll it:

```bash
curl -H "X-API-Key: $API_KEY" \
  http://127.0.0.1:8000/jobs/YOUR_TASK_ID
```

Watch worker logs:

```bash
kubectl -n quant-cloud logs deploy/quant-worker -f
```

---

# 15. Add a second worker on the laptop

Scale up worker count:

```bash
kubectl -n quant-cloud scale deployment quant-worker --replicas=2
kubectl -n quant-cloud get pods -o wide
```

This is enough for Phase 1 queue-based async compute.

---

# 16. Prepare the Pentium for later burst use, but do not schedule normal pods there

You already tainted the Pentium. That means regular pods without a matching toleration will avoid it. ([Kubernetes](https://kubernetes.io/docs/concepts/scheduling-eviction/taint-and-toleration/?utm_source=chatgpt.com "Taints and Tolerations"))

If you want to test a burst-only worker later, add a second worker deployment with toleration.

Create:

```bash
cat > k8s/burst-worker.yaml <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: quant-worker-burst
  namespace: quant-cloud
spec:
  replicas: 0
  selector:
    matchLabels:
      app: quant-worker-burst
  template:
    metadata:
      labels:
        app: quant-worker-burst
    spec:
      imagePullSecrets:
      - name: ghcr-creds
      nodeSelector:
        quantcloud/node-role: worker-burst
      tolerations:
      - key: "quantcloud/burst"
        operator: "Equal"
        value: "true"
        effect: "NoSchedule"
      containers:
      - name: worker
        image: $GHCR_IMAGE_PREFIX/worker:phase1
        env:
        - name: RABBITMQ_USER
          value: quant
        - name: RABBITMQ_PASSWORD
          valueFrom:
            secretKeyRef:
              name: quant-cloud-secrets
              key: RABBITMQ_PASSWORD
        - name: RABBITMQ_HOST
          value: rabbitmq.quant-cloud.svc.cluster.local
EOF
```

Apply it:

```bash
kubectl apply -f k8s/burst-worker.yaml
```

When you want to test the Pentium manually:

```bash
kubectl -n quant-cloud scale deployment quant-worker-burst --replicas=1
kubectl -n quant-cloud get pods -o wide
```

And stop it again:

```bash
kubectl -n quant-cloud scale deployment quant-worker-burst --replicas=0
```

---

# 17. Save the cluster state you just created

```bash
mkdir -p ~/cluster-backup
kubectl get all -A -o yaml > ~/cluster-backup/all-resources.yaml
kubectl get secret -A > ~/cluster-backup/secret-list.txt
helm list -A > ~/cluster-backup/helm-releases.txt
kubectl get nodes -o wide > ~/cluster-backup/nodes.txt
```

Do not dump secret values into git.

---

# 18. Sanity checks

Run these on the VPS:

```bash
kubectl get nodes -o wide
kubectl -n quant-cloud get all
kubectl -n quant-cloud top pods
kubectl -n quant-cloud top nodes
```

If `top` fails, install metrics-server later; that is normal in an early cluster.

---

# What you should have working at the end

You’re done with Phase 1 when all of these work:

```bash
kubectl get nodes
kubectl -n quant-cloud get pods
kubectl -n quant-cloud get svc
curl http://127.0.0.1:8000/health
curl -X POST http://127.0.0.1:8000/jobs \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"job_type":"demo","sleep_seconds":5}'
```

At that point you have:

- a real 3-node K3s cluster
    
- private node-to-node networking
    
- queue-based async execution
    
- API + worker split
    
- PostgreSQL and RabbitMQ inside Kubernetes
    
- a tainted burst node ready for later automation
    

---

# Important implementation note

For your **actual option pricer**, I would not bolt all model code into the API container. Keep the API thin and put pricing logic into the worker image. That keeps your eventual move to Kubernetes Jobs much cleaner.

If you want, the next step I’d take is to give you the **exact Phase 1 repo contents** as ready-to-copy files so you can paste them in without editing.
