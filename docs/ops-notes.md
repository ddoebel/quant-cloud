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

---

## 6) Argo CD web UI: port-forward or Ingress

### Option A — Port-forward (no Ingress)

From any machine with `kubectl` configured for the cluster:

```bash
kubectl port-forward svc/argocd-server -n argocd 8080:443
```

Open **`https://localhost:8080`** (accept the browser certificate warning for the self-signed cert).

Initial login:

- **Username:** `admin`
- **Password:**

```bash
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d
echo
```

If that secret is gone, use the password you set when you rotated credentials.

### Option B — Ingress via Traefik (GitOps)

The repo includes `k8s/argocd-ingress.yaml`. It routes **`argocd.local`** to **`argocd-server` port 80 (HTTP)**. The default Argo CD install serves **TLS on 443**; pointing Traefik at 443 with HTTPS upstream often hits **self-signed cert** issues and you see **500 Internal Server Error**, **502**, or blank pages. **Do not** use port 443 behind Traefik unless you add TLS trust (ServersTransport `insecureSkipVerify`, or trusted certs).

**One-time cluster setup (required for Ingress)**

Run these on the cluster **once** (they merge into existing ConfigMaps; safe for typical installs):

```bash
# Serve UI/API over HTTP on port 80 so Traefik can proxy without verifying pod TLS
kubectl patch configmap argocd-cmd-params-cm -n argocd --type merge \
  -p '{"data":{"server.insecure":"true"}}'

# Tell Argo CD its public URL (must match what you type in the browser)
kubectl patch configmap argocd-cm -n argocd --type merge \
  -p '{"data":{"url":"http://argocd.local"}}'

kubectl rollout restart deployment argocd-server -n argocd
kubectl -n argocd rollout status deployment argocd-server --timeout=120s
```

If you use a **different hostname**, change `url` accordingly.

**What this does**

- **Traefik** receives HTTP on the ingress entrypoint (for example port 80).
- It forwards **HTTP** to **`argocd-server:80`**, which matches `server.insecure` mode.

**Client setup**

1. Point the hostname at your VPS (same idea as `quant.local`):

   ```text
   YOUR_VPS_IP argocd.local
   ```

   Add that line to `/etc/hosts` on the machine where you run the browser.

2. After the `quant-cloud` Application syncs, verify:

   ```bash
   kubectl -n argocd get ingress
   ```

3. Open **`http://argocd.local`** in the browser and log in with `admin` and the password from the secret above.

**If you still see 500 or a blank page**

```bash
kubectl -n argocd logs deploy/argocd-server --tail=80
kubectl -n kube-system logs -l app.kubernetes.io/name=traefik --tail=50
```

Confirm the Ingress backend is **port 80** and that `argocd-cm` **`url`** matches how you open the UI.

**If you see 504 Gateway Timeout**

That almost always means Traefik reached the Service but the **pod did not answer plain HTTP** in time: `server.insecure` is missing or **`argocd-server` was not restarted** after patching ConfigMaps. The default server still expects TLS on the container port; sending HTTP stalls until the proxy times out.

Verify and fix:

```bash
# Must print "true"
kubectl -n argocd get configmap argocd-cmd-params-cm -o jsonpath="{.data['server.insecure']}{'\n'}"

kubectl rollout restart deployment argocd-server -n argocd
kubectl -n argocd rollout status deployment argocd-server --timeout=120s
```

Sanity-check from inside the cluster (should return HTML quickly, not hang):

```bash
kubectl run argocd-curl --rm -i --restart=Never --image=curlimages/curl:8.5.0 -- \
  curl -sS -m 10 -o /dev/null -w "%{http_code}\n" http://argocd-server.argocd.svc.cluster.local/
```

Expect **`200`** or **`302`**. If it **times out**, insecure mode is not active or the Deployment did not pick up the ConfigMap.

Then re-test **`http://argocd.local`**.

**Optional: TLS only at Traefik**

For HTTPS in the browser (`https://argocd.local`), terminate TLS on Traefik (cert on the Ingress) and keep the **HTTP** backend to `argocd-server:80` with `server.insecure` — then set `url` to `https://argocd.local`. See upstream Argo CD ingress documentation.

