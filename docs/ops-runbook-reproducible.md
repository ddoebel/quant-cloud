# QuantCloud Reproducible Runbook (ArgoCD + K3s + Ingress)

This merges your existing `ops-notes.md` with the external summary, but only keeps steps that are truly reproducible and necessary.

Goal end state:

```text
GitHub -> ArgoCD -> Kubernetes -> Synced + Healthy
```

---

## 0) What Is Always Required vs Conditional

Always required:
- ArgoCD `Application` points to a real repo branch and real path.
- ArgoCD installs cleanly (CRDs + controller + repo-server + server).
- Cluster DNS works from pods.

Conditional (only if symptoms appear):
- Draining `qc-laptop`.
- Pinning CoreDNS / ArgoCD components to `qc-vps`.
- Editing CoreDNS Corefile.

Do not treat conditional fixes as mandatory baseline steps.

---

## 1) Preflight Checks (Required)

```bash
# cluster reachable
kubectl get nodes -o wide

# repo branch/path sanity (from any machine with git)
git ls-remote --heads https://github.com/ddoebel/quant-cloud
```

For this project, ArgoCD source must be:
- `targetRevision: master`
- `path: k8s`

---

## 2) Install ArgoCD Cleanly (Required)

```bash
kubectl delete namespace argocd --ignore-not-found
kubectl create namespace argocd

kubectl apply --server-side -n argocd \
  -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

kubectl -n argocd get pods
```

Required components:
- `argocd-application-controller-0`
- `argocd-repo-server-*`
- `argocd-server-*`

Why server-side apply: avoids CRD annotation-size failures during install.

---

## 3) Apply QuantCloud Application (Required)

Use:

```bash
kubectl apply -f /home/david/coding/QuantCloud/quant-cloud-phase1/k8s/argocd.yaml
kubectl annotate application quant-cloud -n argocd argocd.argoproj.io/refresh=hard --overwrite
kubectl get applications -n argocd
```

Expected key fields in `quant-cloud-phase1/k8s/argocd.yaml`:
- `repoURL: https://github.com/ddoebel/quant-cloud`
- `targetRevision: master`
- `path: k8s`
- `syncOptions: [CreateNamespace=true]`

---

## 4) DNS Validation Gate (Required Before Deep Argo Debugging)

Use FQDN to avoid resolver ambiguity:

```bash
kubectl run dns-test --image=busybox:1.36 --restart=Never --command -- \
  nslookup kubernetes.default.svc.cluster.local
kubectl logs dns-test
kubectl delete pod dns-test --wait=true
```

Pass condition:
- Resolves to Kubernetes service IP (typically `10.43.0.1` on k3s defaults).

If this fails, fix DNS/network first; ArgoCD cannot become healthy without it.

---

## 5) If App Is `Unknown` or Stuck `Progressing` (Conditional Fixes)

### 5.1 Check where critical components run

```bash
kubectl get pods -n argocd -o wide
kubectl get pods -n kube-system -l k8s-app=kube-dns -o wide
kubectl logs -n argocd statefulset/argocd-application-controller --tail=120
```

If logs show redis/dns timeouts (for example lookup or i/o timeout), pin critical components to the stable control node (`qc-vps`).

### 5.2 Pin controller and CoreDNS to control node

```bash
kubectl -n argocd patch statefulset argocd-application-controller \
  --type merge \
  -p '{"spec":{"template":{"spec":{"nodeSelector":{"quantcloud/node-role":"control"}}}}}'
kubectl -n argocd rollout restart statefulset argocd-application-controller
kubectl -n argocd rollout status statefulset argocd-application-controller --timeout=120s

kubectl -n kube-system patch deployment coredns \
  --type merge \
  -p '{"spec":{"template":{"spec":{"nodeSelector":{"quantcloud/node-role":"control"}}}}}'
kubectl -n kube-system rollout restart deployment coredns
kubectl -n kube-system rollout status deployment coredns --timeout=120s
```

### 5.3 Optional: drain unstable worker node

Only if mixed-network node causes recurring connectivity instability:

```bash
kubectl cordon qc-laptop
kubectl drain qc-laptop --ignore-daemonsets --delete-emptydir-data
```

Note: this can disrupt workloads scheduled with `worker-main` selectors.

---

## 6) CoreDNS Corefile Guidance (Conditional)

Do not edit CoreDNS unless DNS test fails.

Preferred baseline is k3s default-style Corefile (includes):
- `kubernetes cluster.local ...`
- `forward . /etc/resolv.conf`

Custom upstreams like `8.8.8.8 1.1.1.1` are environment-specific, not universally required.

---

## 7) Repo Content Rules for Argo Source Path

Argo source path (`k8s/`) should contain valid Kubernetes manifests only.

Avoid putting unrelated helper/config files in that path.

`argocd.yaml` in the same path is optional:
- acceptable if you intentionally want Argo to manage its own `Application` CR.
- otherwise keep app bootstrap manifest outside the managed path.

---

## 8) Ingress Baseline

For ingress to be usable:

```bash
kubectl get ingress -n quant-cloud
kubectl get svc -n kube-system traefik
```

Your ingress host (`quant.local`) must resolve to a node IP externally (via local DNS or `/etc/hosts`).

TLS/production hardening is a separate step (cert-manager, trusted DNS, certificates).

---

## 9) Final Verification

```bash
kubectl get applications -n argocd
kubectl describe application quant-cloud -n argocd
kubectl get pods -n quant-cloud -o wide
```

Expected:
- `quant-cloud   Synced   Healthy`

---

## 10) What Actually Mattered In Your Incident

These were the impactful fixes in your case:
1. Correct Argo source to `targetRevision: master` and `path: k8s`.
2. Ensure Argo controller could reliably reach Redis/DNS.
3. Run CoreDNS and critical Argo components on stable node (`qc-vps`) when mixed-network routing was flaky.
4. Use hard refresh after fixes.

Everything else is supportive diagnostics or conditional remediation.

