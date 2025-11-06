#!/usr/bin/env bash
set -euo pipefail
NS=payment-service
HERE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Namespace: $NS"
kubectl get pods -n $NS
kubectl get svc -n $NS

# Prefer minikube service URL for testing
if command -v minikube >/dev/null; then
  URL=$(minikube service payment-service-nodeport --url -n $NS || true)
  if [ -n "$URL" ]; then
    echo "Using minikube service URL: $URL"
    echo "Health:"
    curl -sS --fail "$URL/health" || (kubectl get pods -n $NS; exit 1)
  fi
fi

# Fallback: port-forward and test
echo "Port-forwarding service to localhost:8082 (background)..."
kubectl port-forward svc/payment-service 8082:8082 -n $NS >/dev/null 2>&1 &
PF_PID=$!
sleep 2
trap 'kill $PF_PID || true' EXIT

echo "Health check (via port-forward):"
if ! curl -sS --fail http://localhost:8082/health; then
  echo "Health endpoint failed"; kubectl logs -n $NS -l app=payment-service --tail=100; exit 1
fi

echo "Create payment sample (if API exists):"
# Example /v1/payments/charge. Adjust payload to your API expectations.
if curl -sS --fail -X POST -H "Content-Type: application/json" \
  -d '{"trip_id":1, "amount":10.5, "method":"CASH"}' http://localhost:8082/v1/payments/charge; then
  echo "Sample create payment returned success (check logs for details)"
else
  echo "Sample create may have failed or endpoint differs. Check logs."
fi

# Show recent logs
kubectl logs -n $NS -l app=payment-service --tail=200
