#!/usr/bin/env bash
set -euo pipefail
NS=payment-service
HERE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "Deploying payment service to namespace: $NS"

command -v kubectl >/dev/null || { echo "kubectl not found"; exit 1; }
command -v minikube >/dev/null || echo "minikube not found; if you run outside minikube skip minikube-specific steps"

kubectl apply -f "$HERE_DIR/namespace.yaml"
# Create config and secrets
kubectl apply -n $NS -f "$HERE_DIR/payment-configmap.yaml"
kubectl apply -n $NS -f "$HERE_DIR/payment-secret.yaml"
# Create postgres PVC and statefulset + service
kubectl apply -n $NS -f "$HERE_DIR/payment-postgres-pvc.yaml"
kubectl apply -n $NS -f "$HERE_DIR/payment-postgres-service.yaml"
kubectl apply -n $NS -f "$HERE_DIR/payment-postgres-statefulset.yaml"

echo "Waiting for Postgres to be ready..."
kubectl rollout status statefulset/payment-postgres -n $NS --timeout=120s || {
  echo "Postgres statefulset not ready within timeout"; kubectl get pods -n $NS; exit 1;
}

# Create CSV configmap and run DB init job
kubectl apply -n $NS -f "$HERE_DIR/payment-db-csv-configmap.yaml"
kubectl apply -n $NS -f "$HERE_DIR/db-init-job.yaml"

echo "Waiting for DB init job to complete..."
# Wait for job completion
kubectl wait --for=condition=complete job/payment-db-init -n $NS --timeout=120s || {
  echo "DB init job failed or timed out"; kubectl describe job payment-db-init -n $NS; kubectl logs job/payment-db-init -n $NS || true; exit 1;
}

# Deploy payment service
kubectl apply -n $NS -f "$HERE_DIR/payment-deployment.yaml"
kubectl apply -n $NS -f "$HERE_DIR/payment-service.yaml"
kubectl apply -n $NS -f "$HERE_DIR/payment-nodeport.yaml"

echo "Waiting for payment pods to be ready..."
kubectl rollout status deployment/payment-service -n $NS --timeout=120s || { echo "Payment deployment not ready"; kubectl get pods -n $NS; exit 1; }

echo "Deployment complete. Services:"
kubectl get svc -n $NS -o wide

if command -v minikube >/dev/null; then
  echo "Minikube service URL (NodePort):"
  minikube service payment-service-nodeport --url -n $NS || true
fi

echo "You can test the health endpoint with: kubectl port-forward svc/payment-service 8082:8082 -n $NS &\n  curl http://localhost:8082/health"
