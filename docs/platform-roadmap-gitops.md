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

Do not switch running manifests to new tags until the images exist in GHCR.

Implemented:
- `.github/workflows/build-images.yml` builds and pushes API/worker images to GHCR on `master` and manual dispatch.
- Published tags include `sha-<commit>` and `latest`.

Required release sequence:
1. Build/push commit-tagged images via CI (for example `sha-<commit>`).
2. Update `k8s/phase1.yaml` image tags to those immutable tags.
3. Push Git.
4. Verify Argo sync and rollout.

Why this gate exists:
- Changing tags before push would break deployment with image pull errors.

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

- `k8s/argocd-ingress.yaml` routes **`argocd.local`** to `argocd-server` **:443** with Traefik using **HTTPS** to the pods.

Client:

- Add `YOUR_VPS_IP argocd.local` to `/etc/hosts`.
- Open `http://argocd.local` (Traefik terminates HTTP on the edge; upstream to Argo CD remains HTTPS on 443).

Credentials and troubleshooting (TLS between Traefik and self-signed Argo cert, optional `url` in `argocd-cm`) are documented in `docs/ops-notes.md` section 6.

## Next After Step 5

1. Switch manifests to immutable image tags only after CI publishes them.
2. Optionally automate manifest tag bump in a second workflow once the build pipeline is stable.
3. Harden Argo CD exposure (TLS on the public hostname, SSO) once the ingress path is stable.
