# QuantCloud Phase 1

QuantCloud is a self-hosted, Kubernetes-based platform for running asynchronous quant workloads through a simple API.

## Recruiter Snapshot

This project demonstrates end-to-end platform ownership: backend service design, distributed job processing, cloud-native deployment, and production-style operational runbooks.

- Built a working async compute platform for quant-style workloads using API + queue + worker architecture.
- Implemented GitOps-based deployment and reconciliation workflows with Kubernetes and Argo CD.
- Documented setup, incident recovery, and rollout procedures to improve reliability and reproducibility.

## Tooling Summary

![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)
![Celery](https://img.shields.io/badge/Celery-37814A?style=flat-square&logo=celery&logoColor=white)
![RabbitMQ](https://img.shields.io/badge/RabbitMQ-FF6600?style=flat-square&logo=rabbitmq&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white)
![Kubernetes](https://img.shields.io/badge/Kubernetes-326CE5?style=flat-square&logo=kubernetes&logoColor=white)
![ArgoCD](https://img.shields.io/badge/ArgoCD-EF7B4D?style=flat-square&logo=argo&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-2088FF?style=flat-square&logo=githubactions&logoColor=white)
![GitHub Container Registry](https://img.shields.io/badge/GHCR-181717?style=flat-square&logo=github&logoColor=white)
![K3s](https://img.shields.io/badge/K3s-FFC61C?style=flat-square&logo=k3s&logoColor=black)

This Phase 1 repository establishes the core cloud pattern:
- submit work through a FastAPI service,
- queue jobs with RabbitMQ,
- execute jobs with Celery workers,
- deploy via GitOps with Argo CD.

## Purpose

The purpose of this project is to build a reliable foundation for distributed quant compute on a small private cluster (VPS + home/lab nodes), with clean deployment workflows and room to scale.

In practical terms, this phase proves:
- API-to-worker asynchronous job flow,
- repeatable Kubernetes deployment,
- image build and rollout workflow,
- operational recovery/runbook coverage.

## Scope (Phase 1)

### Included
- FastAPI control plane (`app/api/main.py`) with:
  - `GET /health`
  - `POST /jobs`
  - `GET /jobs/{task_id}`
- Celery worker (`app/worker/`) processing queued jobs.
- Kubernetes app manifests in `k8s/`:
  - API deployment and service,
  - worker deployment,
  - ingress for `quant.local`,
  - Argo CD application spec.
- GitOps deployment model:
  - Argo CD sync from GitHub repo,
  - CI-driven image publish/tag flow (see docs notes).
- Ops documentation under `docs/` for setup, recovery, and roadmap.

### Not Included Yet
- Full production quant model suite (current worker task is a baseline demo task).
- Advanced authn/authz beyond API key header.
- Dedicated observability stack (metrics, tracing, alerting) as a hardened default.
- Automated burst-node orchestration policy.
- Multi-environment promotion model (dev/stage/prod).

## High-Level Architecture

1. Client submits a job to the API.
2. API enqueues the task to RabbitMQ.
3. Celery worker consumes and executes the task.
4. Client polls task status/result from the API.
5. Kubernetes runs all services; Argo CD keeps manifests reconciled from Git.

## Repository Layout

```text
quant-cloud-phase1/
  app/
    api/            # FastAPI service
    worker/         # Celery app + tasks
  k8s/              # Kubernetes and Argo CD manifests
  docs/             # Setup guides, runbooks, and roadmap
  Dockerfile.api
  Dockerfile.worker
  requirements.txt
```

## Deployment Model

- **Runtime platform:** K3s cluster
- **App namespace:** `quant-cloud`
- **Ingress host:** `quant.local`
- **GitOps controller:** Argo CD (`k8s/argocd.yaml`)
- **Container images:** GHCR

Argo CD tracks the manifests in `k8s/` and applies drift correction with automated sync.

## Local Build (Images)

```bash
docker build -t quant-cloud-api:phase1 -f Dockerfile.api .
docker build -t quant-cloud-worker:phase1 -f Dockerfile.worker .
```

## API Usage (Example)

Health:

```bash
curl http://127.0.0.1:8000/health
```

Submit:

```bash
curl -X POST http://127.0.0.1:8000/jobs \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"job_type":"demo","sleep_seconds":5}'
```

Status:

```bash
curl -H "X-API-Key: $API_KEY" \
  http://127.0.0.1:8000/jobs/<TASK_ID>
```

## Operations Docs

- Setup guide: `docs/Setup Phase 1 Quant Cloud.md`
- Ops notes and Argo CD recovery: `docs/ops-notes.md`
- Reproducible runbook: `docs/ops-runbook-reproducible.md`
- Roadmap and rollout sequencing: `docs/platform-roadmap-gitops.md`

## Security Notes

- Store credentials in Kubernetes Secrets (`quant-cloud-secrets`); never commit secrets.
- Set `API_KEY` via environment/secret in deployment manifests.
- Use private networking and controlled ingress exposure for cluster services.

## Near-Term Next Steps

- Replace demo worker task with real pricing/model workloads.
- Add structured result persistence and retrieval strategy.
- Introduce observability baseline (metrics + logs + alerting).
- Harden API access and add environment promotion workflow.
