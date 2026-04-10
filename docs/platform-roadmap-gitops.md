# QuantCloud Platform Roadmap (Corrected + Executable)

This roadmap is adjusted to the current repo/cluster state and is ordered to minimize deployment risk.

## Current State Snapshot

- ArgoCD app `quant-cloud` is `Synced/Healthy`.
- App workloads are running in `quant-cloud`.
- `k8s/` previously had an ingress filename typo (`ingres.yaml`).
- `k8s/` previously lacked `argocd.yaml` even though runbooks referenced it.

## Corrected Execution Plan

### 1) Prove ArgoCD auto-sync with a safe Git change (executed)

Goal:
- Prove reconciliation happens from Git push alone.

Execution:
- Add a harmless metadata label to `k8s/phase1.yaml`.
- Commit + push.
- Verify with:
  - `kubectl get applications -n argocd`
  - `kubectl -n quant-cloud get pods`

Pass criteria:
- ArgoCD remains `Synced/Healthy`.
- Updated workload is reconciled without `kubectl apply`.

### 2) Make `k8s/` strictly GitOps manifests (executed)

Changes applied:
- Normalize ingress filename to `k8s/ingress.yaml`.
- Remove typo file `k8s/ingres.yaml`.
- Add `k8s/argocd.yaml` so the expected app spec lives in the declared source path.

Rule:
- Keep only live manifests in `k8s/`.
- Keep notes/runbooks under `docs/`.

### 3) Scope GitOps ownership (decided for now)

Decision for this phase:
- App stack in ArgoCD: API, worker, service, ingress, app config.
- Postgres/RabbitMQ stay manually managed short-term until app releases are stable.

Rationale:
- Reduces blast radius while tightening deployment workflow.

### 4) Ingress baseline for API access (executed + verify)

Manifest:
- `k8s/ingress.yaml` routes `quant.local` to service `quant-api:80`.

Required host mapping (client machine):
- Add `YOUR_VPS_IP quant.local` to `/etc/hosts`.

Validation:
- `kubectl -n quant-cloud get ingress`
- `curl http://quant.local/health`

### 5) Versioned image tags (gated rollout)

This is now automated in CI: images are built and the deployment manifest is updated to immutable tags automatically.

Implemented:
- `.github/workflows/build-images.yml` builds and pushes API/worker images to GHCR on `master` and manual dispatch.
- Published tags include `sha-<commit>`, `latest`, and `phase1`.
- Images are named `ghcr.io/<owner>/quant-cloud-api` and `ghcr.io/<owner>/quant-cloud-worker` so `GITHUB_TOKEN` can publish (same repo). Pushing to a different package path (for example an old `option-pricing-cluster/...` name) returns **403** on upload because that package is not writable by this workflow.
- After both images are pushed, the workflow updates `k8s/phase1.yaml` to:
  - `ghcr.io/<owner>/quant-cloud-api:sha-<commit>`
  - `ghcr.io/<owner>/quant-cloud-worker:sha-<commit>`
  then commits and pushes the manifest change back to `master`.

Automated release sequence:
1. Push app code (or manually dispatch the workflow).
2. CI builds/pushes API and worker images.
3. CI commits immutable image tags into `k8s/phase1.yaml`.
4. ArgoCD detects the manifest commit and syncs.
5. Verify rollout from the checklist below.

Why this gate exists:
- The manifest is only bumped after image push succeeds, so ArgoCD never points at tags that do not exist yet.

## Standard Verification Checklist

Run after each deployment push:

```bash
kubectl get applications -n argocd
kubectl -n quant-cloud get pods -o wide
kubectl -n quant-cloud get svc
kubectl -n quant-cloud get ingress
kubectl -n quant-cloud logs deploy/quant-api --tail=50
kubectl -n quant-cloud logs deploy/quant-worker --tail=50
```

External check:

```bash
curl http://quant.local/health
```

### 6) Argo CD UI via Ingress (optional, after app ingress)

Manifest:

- `k8s/argocd-ingress.yaml` routes **`argocd.local`** to `argocd-server` **:80** (HTTP to the pod). Traefik must not use HTTPS to the pod unless you configure backend TLS trust; the default self-signed cert on 443 commonly yields **500** errors.

Cluster:

- One-time `argocd-cmd-params-cm` (`server.insecure`) and `argocd-cm` (`url`) patches — see `docs/ops-notes.md` section 6.

Client:

- Add `YOUR_VPS_IP argocd.local` to `/etc/hosts`.
- Open `http://argocd.local`.

## Next After Step 5

1. Add rollback guidance (revert the auto-bump commit to redeploy previous SHA tags).
2. Optionally split build and deploy-manifest update into separate workflows/environments.
3. Harden Argo CD exposure (TLS on the public hostname, SSO) once the ingress path is stable.
