# Payment Service — Kubernetes Deployment (Minikube)

This material contains Kubernetes manifests, deployment and test scripts, and instructions to run the Payment Service on a local Minikube cluster.

## Prerequisites

- Minikube (recommended) — https://minikube.sigs.k8s.io/docs/start/
- kubectl — compatible with your Minikube
- Bash (Git Bash / WSL on Windows) to run the provided `deploy.sh` and `test-k8s.sh` scripts
- Docker (for building images) or pre-built images pushed to a registry

## Files created

- `k8s/namespace.yaml` — Namespace for payment resources
- `k8s/payment-configmap.yaml` — Non-sensitive config
- `k8s/payment-secret.yaml` — Secrets (use stringData; Kubernetes stores base64 in `.data`)
- `k8s/payment-db-csv-configmap.yaml` — CSV used by DB init job
- `k8s/payment-postgres-pvc.yaml` — PVC for Postgres
- `k8s/payment-postgres-statefulset.yaml` — Postgres StatefulSet
- `k8s/payment-postgres-service.yaml` — Postgres ClusterIP service
- `k8s/payment-deployment.yaml` — Payment Deployment (2 replicas, probes, resources)
- `k8s/payment-service.yaml` — ClusterIP service
- `k8s/payment-nodeport.yaml` — NodePort service (nodePort: 30082)
- `k8s/db-init-job.yaml` — Job to run `database_setup.py` once to seed DB
- `k8s/ingress.yaml` — Optional Ingress for host `payment.local`
- `k8s/deploy.sh` — Deploy script (applies manifests in order, waits, runs DB job)
- `k8s/test-k8s.sh` — Simple tests: pods, health endpoint, sample create

## Quick deploy (recommended)

1. Start Minikube (example):

```bash
minikube start --cpus=4 --memory=8192
```

2. Build/load your `payment_service:latest` image into Minikube or push to a registry and update image names in `k8s/payment-deployment.yaml` and `k8s/db-init-job.yaml`.

- To load local image into minikube:

```bash
# from repo root
minikube image build -t payment_service:latest -f Dockerfile .
# or docker build then `minikube image load payment_service:latest`
```

3. Run the deploy script (in Git Bash / WSL):

```bash
cd k8s
./deploy.sh
```

4. Run tests:

```bash
./test-k8s.sh
```

## Notes & troubleshooting

- If using Windows PowerShell, run the scripts in Git Bash or WSL; they are bash scripts.
- If your image is in a registry, replace `payment_service:latest` with the full image path and ensure `imagePullSecrets` are configured.
- To view the NodePort externally (Minikube):

```bash
minikube service payment-service-nodeport --url -n payment-service
```

- For Ingress: enable an ingress controller in minikube (`minikube addons enable ingress`) and add `127.0.0.1 payment.local` to your hosts file.

## Security & best-practices included

- Secrets are stored in a Kubernetes Secret (use sealed-secrets / Vault in prod)
- Resource requests and limits are set on the deployment
- Liveness/readiness probes are configured
- Postgres runs in a StatefulSet for stable identity and PVC usage
- Prometheus scrape annotations added on deployment

## Next steps / suggestions

- Add NetworkPolicy restricting traffic to only allowed services
- Use a dedicated ServiceAccount for the payment pods and limit RBAC
- Use sealed-secrets or HashiCorp Vault for production secrets
- Add Horizontal Pod Autoscaler (HPA) based on CPU or custom metrics

## Screenshots for assignment

- `kubectl get pods -n payment-service` (capture pods ready)
- `kubectl get pvc -n payment-service` (show PVC bound)
- `kubectl logs -n payment-service deployment/payment-service` (health)
- `minikube service payment-service-nodeport --url -n payment-service` (service URL)

Include those screenshots in your assignment submission.
