# QuantCloud ArgoCD Recovery Notes

This is a quick runbook for the ArgoCD `Unknown/Progressing` issues we fixed.

## 1) Apply the correct Application spec

Use the app manifest from this repo:

```bash
kubectl apply -f /home/david/coding/QuantCloud/quant-cloud-phase1/k8s/argocd.yaml
```

Expected key fields in `quant-cloud-phase1/k8s/argocd.yaml`:

- `spec.source.repoURL: https://github.com/ddoebel/quant-cloud`
- `spec.source.targetRevision: master`
- `spec.source.path: k8s`
- `spec.syncPolicy.syncOptions: [CreateNamespace=true]`

## 2) Force ArgoCD app refresh

```bash
kubectl annotate application quant-cloud -n argocd argocd.argoproj.io/refresh=hard --overwrite
kubectl get applications -n argocd
kubectl describe application quant-cloud -n argocd
```

## 3) If app gets stuck in `Unknown` or `Progressing`

Pin controller and CoreDNS to the stable control node (`qc-vps`):

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

Then refresh app:

```bash
kubectl annotate application quant-cloud -n argocd argocd.argoproj.io/refresh=hard --overwrite
kubectl get applications -n argocd
```

## 4) Fast diagnostics

```bash
kubectl get pods -n argocd -o wide
kubectl logs -n argocd statefulset/argocd-application-controller --tail=80
kubectl get pods -n kube-system -l k8s-app=kube-dns -o wide
kubectl get pods -n quant-cloud -o wide
```

## 5) Expected healthy end state

```bash
kubectl get applications -n argocd
```

Expected:

- `quant-cloud   Synced   Healthy`

