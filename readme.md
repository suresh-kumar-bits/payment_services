# Payment Service - Ride-Hailing Platform

A microservice for handling payment transactions, refunds, and fare calculations for a ride-hailing platform. Built with Flask, PostgreSQL, Docker, and Kubernetes.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
  - [Option 1: Local Development](#option-1-local-development)
  - [Option 2: Docker Compose](#option-2-docker-compose)
  - [Option 3: Kubernetes (Minikube)](#option-3-kubernetes-minikube)
- [API Endpoints](#api-endpoints)
- [Assignment Tasks Completion](#assignment-tasks-completion)
- [Screenshots for Submission](#screenshots-for-submission)
- [Troubleshooting](#troubleshooting)
- [Quick Reference](#quick-reference)

---

## 🎯 Overview

**Service Role:** Payment processing microservice for ride-hailing platform  
**Technology:** Python 3.x, Flask, PostgreSQL  
**Port:** 8082  
**Database:** PostgreSQL (350 seed records)

**Key Features:**
- ✅ **Idempotency:** Prevents duplicate charges using SHA-256 hashing
- ✅ **Fare Calculator:** Base fare + distance × rate × surge multiplier
- ✅ **Refunds:** Full and partial refund support
- ✅ **Inter-Service Communication:** Validates trips via Trip Service
- ✅ **Async Notifications:** Non-blocking notification to Notification Service
- ✅ **Monitoring:** Prometheus metrics endpoint
- ✅ **Structured Logging:** JSON logs with correlation IDs

---

## 📁 Project Structure

```
payment_service/
├── app.py                          # Flask application entry point
├── config.py                       # Configuration management
├── database_setup.py               # Schema creation + CSV seeding
├── requirements.txt                # Python dependencies
├── docker-compose.yml              # Docker Compose configuration
├── Dockerfile                      # Container image definition
├── .env                            # Environment variables (local)
├── rhfd_payments.csv               # Seed data (350 records)
│
├── api/
│   ├── middleware/
│   │   ├── error_handler.py       # Global error handling
│   │   └── rate_limiter.py        # In-memory rate limiting
│   └── routes/
│       ├── health.py               # Health check endpoints
│       ├── metrics.py              # Prometheus metrics
│       └── payments.py             # Payment & refund endpoints
│
├── services/
│   ├── payment_service.py          # Core business logic
│   ├── idempotency_service.py      # Idempotency management
│   └── external_services.py        # Inter-service communication
│
├── database/
│   └── connection.py               # PostgreSQL connection pool
│
├── utils/
│   ├── logger.py                   # JSON structured logging
│   └── helpers.py                  # Validation utilities
│
└── k8s/                            # Kubernetes manifests
    ├── namespace.yaml
    ├── payment-deployment.yaml
    ├── payment-service.yaml
    ├── payment-nodeport.yaml
    ├── payment-configmap.yaml
    ├── payment-secret.yaml
    ├── payment-postgres-statefulset.yaml
    ├── payment-postgres-service.yaml
    ├── payment-db-csv-configmap.yaml
    ├── db-init-job.yaml
    ├── ingress.yaml
    ├── deploy.sh
    └── test-k8s.sh
```

---

## 🛠️ Prerequisites

### For All Deployments:
- **Python 3.9+** - [Download](https://www.python.org/downloads/)
- **Git** - [Download](https://git-scm.com/downloads)

### For Docker:
- **Docker Desktop** - [Download](https://www.docker.com/products/docker-desktop/)

### For Kubernetes:
- **Minikube** - [Download](https://minikube.sigs.k8s.io/docs/start/)
- **kubectl** - [Download](https://kubernetes.io/docs/tasks/tools/)
- **Git Bash** (Windows only) - [Download](https://git-scm.com/download/win)

---

## 🚀 Quick Start

### Option 1: Local Development

**Step 1: Clone and Setup**
```bash
cd payment_service
python -m venv .venv
.venv\Scripts\activate          # Windows
# OR
source .venv/bin/activate       # Mac/Linux

pip install -r requirements.txt
```

**Step 2: Configure Environment**
```bash
# Copy .env.example to .env (if exists) or use existing .env
# Update DB credentials if needed
```

**Step 3: Start PostgreSQL**
```bash
# Ensure PostgreSQL is running on port 5433
# Or use Docker:
docker run -d --name payment-postgres \
  -e POSTGRES_PASSWORD=Superb#915 \
  -p 5433:5432 postgres:15-alpine
```

**Step 4: Initialize Database**
```bash
python database_setup.py
```

**Step 5: Run Service**
```bash
python app.py
```

**Step 6: Test**
```bash
# Browser or curl:
curl http://localhost:8082/health
```

---

### Option 2: Docker Compose

**Step 1: Build and Start**
```bash
cd payment_service
docker-compose build
docker-compose up -d
```

**Step 2: Verify**
```bash
docker ps
# Should show: payment-postgres, payment-service-api
```

**Step 3: Check Logs**
```bash
docker logs payment-service-api
```

**Step 4: Test**
```bash
curl http://localhost:8082/health
```

**Step 5: Stop**
```bash
docker-compose down
# Keep data: docker-compose down (volumes persist)
# Remove data: docker-compose down -v
```

---

### Option 3: Kubernetes (Minikube)

**Step 1: Start Minikube**
```bash
minikube start --cpus=2 --memory=3072 --driver=docker
```

**Step 2: Verify Minikube**
```bash
minikube status
kubectl version --client
```

**Step 3: Build Docker Image**
```bash
cd payment_service
docker build -t payment_service:latest .
```

**Step 4: Load Image into Minikube**
```bash
minikube image load payment_service:latest
```

**Step 5: Verify Image**
```bash
# For Windows OS run below command
minikube image ls | findstr payment
# Should show: docker.io/library/payment_service:latest
```

**Step 6: Deploy Using Script**
```bash
cd k8s

# Windows: Use Git Bash
chmod +x deploy.sh
./deploy.sh
```

**Step 7: Manual Deployment (Alternative)**
```bash
cd k8s

# Create namespace and configs
kubectl apply -f namespace.yaml
kubectl apply -f payment-configmap.yaml
kubectl apply -f payment-secret.yaml

# Deploy PostgreSQL
kubectl apply -f payment-postgres-statefulset.yaml
kubectl apply -f payment-postgres-service.yaml

# Wait for Postgres
kubectl wait --for=condition=ready pod -l app=payment-postgres \
  -n payment-service --timeout=120s

# Initialize database
kubectl apply -f payment-db-csv-configmap.yaml
kubectl apply -f db-init-job.yaml

# Wait for job
kubectl wait --for=condition=complete job/payment-db-init \
  -n payment-service --timeout=120s

# Deploy payment service
kubectl apply -f payment-deployment.yaml
kubectl apply -f payment-service.yaml
kubectl apply -f payment-nodeport.yaml

# Wait for deployment
kubectl wait --for=condition=available deployment/payment-service \
  -n payment-service --timeout=120s
```

**Step 8: Verify Deployment**
```bash
kubectl get pods -n payment-service
# Expected: All pods Running or Completed

kubectl get svc -n payment-service
# Expected: payment-service, payment-service-nodeport, payment-postgres

kubectl get pvc -n payment-service
# Expected: PVC in Bound status
```

**Step 9: Get Service URL**
```bash
minikube service payment-service-nodeport --url -n payment-service
# Output: http://127.0.0.1:xxxxx
# KEEP THIS TERMINAL OPEN!
```

**Step 10: Test Service**
```bash
# Use URL from Step 9
curl http://127.0.0.1:xxxxx/health

# Expected response:
# {
#   "service": "payment-service",
#   "version": "1.0.0",
#   "status": "UP",
#   "database_status": "UP"
# }
```

---

## 📡 API Endpoints

### **1. Health Check**
```bash
GET /health
```
**Response:**
```json
{
  "service": "payment-service",
  "version": "1.0.0",
  "status": "UP",
  "database_status": "UP",
  "timestamp": "2025-11-06T12:00:00.000000"
}
```

### **2. Create Payment**
```bash
POST /payments
Content-Type: application/json

{
  "idempotency_key": "test-payment-001",
  "trip_id": 101,
  "method": "CARD",
  "amount": 150.00
}
```

**Response (Success):**
```json
{
  "payment_id": 351,
  "trip_id": 101,
  "amount": 150.0,
  "method": "CARD",
  "status": "SUCCESS",
  "reference": "PAY-20251106-abc12345",
  "created_at": "2025-11-06T12:00:00.000000"
}
```

### **3. Create Refund**
```bash
POST /payments/{payment_id}/refunds
Content-Type: application/json

{
  "idempotency_key": "refund-001",
  "amount": 50.00,
  "metadata": {
    "reason": "Customer request"
  }
}
```

### **4. Prometheus Metrics**
```bash
GET /metrics
```

---

## ✅ Assignment Tasks Completion

### **Task 1: Services (≥4)**
✅ **Payment Service** (this repository)
- Endpoints: `/payments`, `/payments/{id}/refunds`, `/health`, `/metrics`
- Inter-service calls: Trip Service, Notification Service
- Database: PostgreSQL (independent)
- Idempotency: SHA-256 key hashing

**Integration with other services:**
- Calls **Trip Service** to validate trip completion before payment
- Calls **Notification Service** asynchronously after payment/refund
- Can call **Rider/Driver Service** for user information

---

### **Task 2: Database Design**

**Schema Overview:**
```sql
-- Core tables
payments (payment_id PK, trip_id, amount, method, status, reference)
idempotency_keys (key_hash PK, request_path, response_status, response_data)
payment_refunds (refund_id PK, payment_id FK, refund_amount, status)
payment_receipts (receipt_id PK, payment_id FK, receipt_number, receipt_data)

-- Indexes for performance
idx_payments_trip_id
idx_payments_status
idx_idempotency_expires
```

**Data Ownership:** Payment Service owns all payment and refund data  
**Seed Data:** 350 payment records from `rhfd_payments.csv`  
**Integrity:** Foreign keys within service boundary

---

### **Task 3: Inter-Service Communication**

**Workflow: Trip Completion → Payment**
1. **Trip Service** marks trip as COMPLETED
2. **Trip Service** → **Payment Service**: `POST /payments`
3. **Payment Service** validates trip via `GET /trips/{trip_id}`
4. **Payment Service** calculates fare: `base_fare + (distance × rate × surge)`
5. **Payment Service** processes payment (gateway simulation)
6. **Payment Service** → **Notification Service**: Send receipt (async)
7. Return payment confirmation to Trip Service

**Implementation:**
- File: `services/external_services.py`
- Methods: `validate_trip_completion()`, `send_payment_notification()`
- Timeout: 5 seconds per call
- Retry: Trip Service should retry on 409 (idempotency in-progress)

---

### **Task 4: Containerization with Docker**

**Files:**
- ✅ `Dockerfile` - Multi-stage build for Python app
- ✅ `docker-compose.yml` - PostgreSQL + Payment Service
- ✅ Health checks configured
- ✅ Volume persistence for database

**Commands:**
```bash
docker-compose build
docker-compose up -d
docker ps
curl http://localhost:8082/health
```

**Screenshot locations:**
- `docker ps` output
- Service health endpoint response
- Sample API call in Postman

---

### **Task 5: Deployment on Minikube**

**Kubernetes Resources Created:**
- ✅ **Namespace:** `payment-service`
- ✅ **Deployment:** `payment-deployment.yaml` (1 replica, probes, resources)
- ✅ **Services:** ClusterIP (internal) + NodePort (external:30082)
- ✅ **ConfigMap:** `payment-configmap.yaml` (business rules, URLs)
- ✅ **Secret:** `payment-secret.yaml` (DB credentials)
- ✅ **StatefulSet:** PostgreSQL with PVC (1Gi)
- ✅ **Job:** Database initialization with CSV seeding
- ✅ **Scripts:** `deploy.sh` (deployment), `test-k8s.sh` (testing)

**Probes Configured:**
- Liveness: `/health` (30s delay, 10s period)
- Readiness: `/health` (10s delay, 5s period)

**Resource Limits:**
- Requests: 100m CPU, 128Mi RAM
- Limits: 500m CPU, 512Mi RAM

---

### **Task 6: Monitoring**

**Metrics Implemented:**
- ✅ `payment_total{status="SUCCESS|FAILED|PENDING"}`
- ✅ `payment_method_total{method="CARD|UPI|WALLET|CASH"}`
- ✅ `payment_average_amount`
- ✅ `payment_total_revenue`

**Endpoints:**
- `/metrics` - JSON format
- `/metrics/prometheus` - Prometheus format

**Logging:**
- Format: JSON structured logs
- Fields: timestamp, level, message, correlation_id
- File: `utils/logger.py`

**Prometheus Annotations:**
```yaml
prometheus.io/scrape: "true"
prometheus.io/port: "8082"
prometheus.io/path: "/metrics"
```

---

### **Task 7: Documentation**

✅ **This README.md** covers:
- Architecture overview
- Setup instructions (Local, Docker, Kubernetes)
- API endpoint documentation
- Assignment task mapping
- Screenshot checklist
- Troubleshooting guide

---

## 📸 Screenshots for Submission

### **Docker Screenshots:**
```bash
# 1. Docker containers running
docker ps

# 2. Service health check
curl http://localhost:8082/health

# 3. Database connection
docker exec -it payment-postgres psql -U postgres -c "\dt"

# 4. Payment creation (use Postman)
POST http://localhost:8082/payments
```

---

### **Kubernetes Screenshots:**

**1. All pods running:**
```bash
kubectl get pods -n payment-service -o wide
```
Expected: `payment-postgres-0`, `payment-db-init-xxxxx` (Completed), `payment-service-xxxxx` (Running)

**2. All services:**
```bash
kubectl get svc -n payment-service
```
Expected: ClusterIP + NodePort services

**3. Persistent Volume Claims:**
```bash
kubectl get pvc -n payment-service
```
Expected: `postgres-data-payment-postgres-0` in Bound status

**4. Deployment details:**
```bash
kubectl describe deployment payment-service -n payment-service
```

**5. Pod logs:**
```bash
kubectl logs -n payment-service deployment/payment-service --tail=100
```

**6. Service URL (with curl test):**
```bash
minikube service payment-service-nodeport --url -n payment-service
curl <URL>/health
```

**7. Payment creation in Postman:**
- Method: POST
- URL: `http://127.0.0.1:xxxxx/payments`
- Body: (see API Endpoints section)
- Screenshot: Request + Response

**8. Metrics endpoint:**
```bash
curl <URL>/metrics
```

---

## 🐛 Troubleshooting

### **Issue 1: Minikube won't start**
**Error:** "Exiting due to RSRC_OVER_ALLOC_MEM"

**Solution:**
```bash
minikube delete
minikube start --cpus=2 --memory=3072 --driver=docker
```

---

### **Issue 2: Image not found in Minikube**
**Error:** "ErrImagePull" or "ImagePullBackOff"

**Solution:**
```bash
# Rebuild and reload
docker build -t payment_service:latest .
minikube image load payment_service:latest

# Verify
minikube image ls | grep payment

# Restart deployment
kubectl rollout restart deployment/payment-service -n payment-service
```

---

### **Issue 3: Pods stuck in Pending**
**Check:**
```bash
kubectl describe pod <pod-name> -n payment-service
```

**Common causes:**
- Insufficient resources → Reduce replicas to 1
- PVC not bound → Check storage class
- Image not available → See Issue 2

---

### **Issue 4: Database connection refused**
**Check:**
```bash
kubectl logs payment-postgres-0 -n payment-service
kubectl get svc payment-postgres -n payment-service
```

**Solution:**
- Wait for Postgres to be ready (30-60 seconds)
- Check Secret has correct credentials
- Verify Service is pointing to correct pod

---

### **Issue 5: NodePort not accessible**
**Error:** "Connection refused" when testing

**Solution:**
```bash
# Option 1: Keep minikube service terminal open
minikube service payment-service-nodeport --url -n payment-service
# Keep this window open, use URL in another terminal

# Option 2: Use port-forward
kubectl port-forward svc/payment-service 8082:8082 -n payment-service
# Access: http://localhost:8082
```

---

### **Issue 6: Job fails to complete**
**Check:**
```bash
kubectl logs job/payment-db-init -n payment-service
kubectl describe job payment-db-init -n payment-service
```

**Common causes:**
- CSV ConfigMap not created → Check CSV is embedded
- Database not ready → Increase wait time
- Schema error → Check `database_setup.py` logs

---

### **Issue 7: API returns 404**
**Check root endpoint first:**
```bash
curl http://127.0.0.1:xxxxx/
# Should list available endpoints
```

**Verify route registration:**
```bash
kubectl logs -n payment-service deployment/payment-service | grep "registered"
```

---

## 📚 Quick Reference

### **Environment Variables (Key Ones)**
```bash
DB_HOST=payment-postgres      # In K8s
DB_PORT=5432                  # Internal port
DB_NAME=postgres
SERVICE_PORT=8082
BASE_FARE=5.0
RATE_PER_KM=2.5
IDEMPOTENCY_KEY_TTL=86400     # 24 hours
```

### **Useful kubectl Commands**
```bash
# Get all resources
kubectl get all -n payment-service

# Check pod logs (follow)
kubectl logs -f deployment/payment-service -n payment-service

# Execute command in pod
kubectl exec -it <pod-name> -n payment-service -- /bin/bash

# Port forward service
kubectl port-forward svc/payment-service 8082:8082 -n payment-service

# Scale deployment
kubectl scale deployment/payment-service --replicas=2 -n payment-service

# Delete everything
kubectl delete namespace payment-service

# Restart deployment
kubectl rollout restart deployment/payment-service -n payment-service
```

### **Testing Payment Creation**
```bash
# Get service URL
URL=$(minikube service payment-service-nodeport --url -n payment-service)

# Create payment
curl -X POST "$URL/payments" \
  -H "Content-Type: application/json" \
  -d '{
    "idempotency_key": "test-001",
    "trip_id": 101,
    "method": "CARD",
    "amount": 150.00
  }'
```

### **Database Access (from pod)**
```bash
kubectl exec -it payment-postgres-0 -n payment-service -- \
  psql -U postgres -c "SELECT COUNT(*) FROM payments;"
```

### **Clean Up**
```bash
# Stop Minikube
minikube stop

# Delete cluster (frees disk)
minikube delete

# Docker cleanup
docker-compose down -v
docker system prune -a
```

---

## 📞 Support

**For assignment-related queries:**
- Review this README thoroughly
- Check troubleshooting section
- Verify all prerequisites are installed
- Test locally with Docker first, then move to Kubernetes

**Key Files for Debugging:**
- `app.py` - Application entry point
- `config.py` - Configuration values
- `database_setup.py` - Database initialization
- `k8s/deploy.sh` - Deployment script
- `api/routes/payments.py` - Payment logic

---
