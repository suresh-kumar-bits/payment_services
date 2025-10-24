# Payment Service - Deployment Documentation

## Project Overview
**Service Name**: Payment Service  
**Port**: 8082  
**Database**: PostgreSQL 15  
**Framework**: Flask (Python)  
**Container**: Docker  
**Orchestration**: Docker Compose / Kubernetes  

---

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Project Structure](#project-structure)
3. [Local Development Deployment](#local-development-deployment)
4. [Docker Deployment](#docker-deployment)
5. [API Endpoints](#api-endpoints)
6. [Database Schema](#database-schema)
7. [Inter-Service Communication](#inter-service-communication)
8. [Monitoring & Health Checks](#monitoring--health-checks)
9. [Kubernetes Deployment](#kubernetes-deployment)
10. [Troubleshooting](#troubleshooting)
11. [Testing Guide](#testing-guide)
12. [Environment Variables](#environment-variables)

---

## Prerequisites

### Required Software
- **Docker**: Version 20.10 or higher
- **Docker Compose**: Version 2.0 or higher
- **Python**: Version 3.11 or higher (for local development)
- **PostgreSQL Client**: For database operations
- **Git**: For version control
- **Make**: For automation (optional but recommended)

### Installation Commands

#### Windows (using PowerShell as Administrator):
```powershell
# Install Chocolatey (if not installed)
Set-ExecutionPolicy Bypass -Scope Process -Force
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))

# Install required tools
choco install docker-desktop
choco install make
choco install python
choco install git
```

#### macOS:
```bash
# Install Homebrew (if not installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install required tools
brew install --cask docker
brew install make
brew install python@3.11
brew install postgresql
brew install git
```

#### Linux (Ubuntu/Debian):
```bash
# Update package list
sudo apt update

# Install required tools
sudo apt install docker.io docker-compose
sudo apt install make
sudo apt install python3.11 python3-pip
sudo apt install postgresql-client
sudo apt install git
```

---

## Project Structure

```
payment-service/
├── app.py                    # Main Flask application
├── database_setup.py         # Database initialization script
├── requirements.txt          # Python dependencies
├── Dockerfile               # Container definition
├── docker-compose.yml       # Service orchestration
├── .env                     # Environment variables
├── Makefile                 # Automation commands
├── wait-for-postgres.sh     # Database wait script
├── rhfd_payments.csv        # Seed data
├── k8s/                     # Kubernetes manifests (optional)
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── configmap.yaml
│   └── secret.yaml
├── tests/                   # Test files
│   └── test_api.py
├── logs/                    # Application logs
└── backups/                 # Database backups
```

---

## Local Development Deployment

### Step 1: Clone Repository
```bash
# Clone your repository
git clone <your-repository-url>
cd payment_service
```

### Step 2: Set Up Environment
```bash
# Copy environment template
cp .env.example .env

# Edit .env file with your configurations
nano .env  # or use any text editor
```

### Step 3: Install Dependencies (for local development)
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
.\venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 4: Run Locally (without Docker)
```bash
# Start PostgreSQL locally
# Make sure PostgreSQL is running on port 5433

# Run database setup
python database_setup.py

# Start the Flask application
python app.py
```

---

## Docker Deployment

### Method 1: Using Make Commands (Recommended)

```bash
# Initial setup
make setup

# Build Docker images
make build

# Start all services
make up

# Verify deployment
make health

# View logs
make logs
```

### Method 2: Using Docker Compose Directly

```bash
# Create Docker network
docker network create ride-hailing-network

# Build images
docker-compose build

# Start services in detached mode
docker-compose up -d

# Verify services are running
docker-compose ps

# Check service health
curl http://localhost:8082/health

# View logs
docker-compose logs -f
```

### Method 3: Step-by-Step Manual Deployment

```bash
# 1. Create network for inter-service communication
docker network create ride-hailing-network

# 2. Start PostgreSQL database
docker run -d \
  --name payment-postgres \
  --network ride-hailing-network \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=Superb#915 \
  -e POSTGRES_DB=postgres \
  -p 5433:5433 \
  postgres:15-alpine

# 3. Wait for database to be ready (30 seconds)
sleep 30

# 4. Build Payment Service image
docker build -t payment-service:latest .

# 5. Run Payment Service
docker run -d \
  --name payment-service-api \
  --network ride-hailing-network \
  -e DB_HOST=payment-postgres \
  -e DB_PORT=5433 \
  -e DB_NAME=postgres \
  -e DB_USER=postgres \
  -e DB_PASS=Superb#915 \
  -p 8082:8082 \
  payment-service:latest

# 6. Initialize database
docker exec payment-service-api python database_setup.py

# 7. Verify deployment
curl http://localhost:8082/health
```

---

## API Endpoints

### Base URL
```
http://localhost:8082
```

### Available Endpoints

#### 1. Health Check
```bash
GET /health

curl http://localhost:8082/health
```

#### 2. List Payments
```bash
GET /v1/payments
Parameters: trip_id, status, method, limit, offset

curl "http://localhost:8082/v1/payments?status=SUCCESS&limit=10"
```

#### 3. Get Payment by ID
```bash
GET /v1/payments/{payment_id}

curl http://localhost:8082/v1/payments/1
```

#### 4. Process Payment (Idempotent)
```bash
POST /v1/payments/charge
Body: {
  "idempotency_key": "unique-key-123",
  "trip_id": 1,
  "method": "CARD",
  "rider_id": 101,
  "driver_id": 201
}

curl -X POST http://localhost:8082/v1/payments/charge \
  -H "Content-Type: application/json" \
  -d '{
    "idempotency_key": "test-payment-001",
    "trip_id": 1,
    "method": "CARD",
    "rider_id": 101,
    "driver_id": 201
  }'
```

#### 5. Process Refund
```bash
POST /v1/payments/{payment_id}/refund
Body: {
  "idempotency_key": "refund-key-123",
  "amount": 50.00
}

curl -X POST http://localhost:8082/v1/payments/1/refund \
  -H "Content-Type: application/json" \
  -d '{
    "idempotency_key": "refund-001",
    "amount": 50.00
  }'
```

#### 6. Generate Receipt
```bash
GET /v1/payments/{payment_id}/receipt

curl http://localhost:8082/v1/payments/1/receipt
```

#### 7. Get Metrics
```bash
GET /metrics

curl http://localhost:8082/metrics
```

---

## Database Schema

### Connect to Database
```bash
# Using Docker
docker exec -it payment-postgres psql -U postgres -d postgres

# Using Make
make db-shell
```

### Tables Structure

```sql
-- View all tables
\dt

-- Payments table structure
\d payments

-- Sample queries
SELECT COUNT(*) FROM payments;
SELECT * FROM payments WHERE status = 'SUCCESS' LIMIT 5;
SELECT method, COUNT(*) FROM payments GROUP BY method;
```

---

## Inter-Service Communication

### Configure Service URLs
Edit `.env` file:
```bash
TRIP_SERVICE_URL=http://trip-service:8081
DRIVER_SERVICE_URL=http://driver-service:8080
RIDER_SERVICE_URL=http://rider-service:8079
NOTIFICATION_SERVICE_URL=http://notification-service:8084
```

### Testing Inter-Service Communication
```bash
# Ensure all services are on the same network
docker network inspect ride-hailing-network

# Test connectivity from Payment Service
docker exec payment-service-api ping trip-service
```

---

## Monitoring & Health Checks

### Health Check Endpoints
```bash
# Service health
curl http://localhost:8082/health

# Database health (included in service health)
# Metrics
curl http://localhost:8082/metrics
```

### View Logs
```bash
# All logs
docker-compose logs

# Payment service logs only
docker-compose logs payment_api

# Follow logs in real-time
docker-compose logs -f payment_api
```

### Monitoring with Prometheus (Optional)
```yaml
# Add to docker-compose.yml
prometheus:
  image: prom/prometheus:latest
  volumes:
    - ./prometheus.yml:/etc/prometheus/prometheus.yml
  ports:
    - "9090:9090"
```

---

## Kubernetes Deployment

### Prerequisites
```bash
# Install Minikube
brew install minikube  # macOS
choco install minikube  # Windows

# Start Minikube
minikube start

# Verify cluster
kubectl cluster-info
```

### Deploy to Kubernetes
```bash
# Create namespace
kubectl create namespace ride-hailing

# Apply configurations
kubectl apply -f k8s/ -n ride-hailing

# Verify deployment
kubectl get pods -n ride-hailing
kubectl get services -n ride-hailing

# Port forward to access service
kubectl port-forward -n ride-hailing service/payment-service 8082:8082
```

---

## Troubleshooting

### Common Issues and Solutions

#### 1. Database Connection Failed
```bash
# Check if database is running
docker ps | grep postgres

# Check database logs
docker logs payment-postgres

# Test connection manually
docker exec payment-postgres pg_isready -U postgres

# Solution: Restart database
docker-compose restart payment_db
```

#### 2. Port Already in Use
```bash
# Find process using port 8082
lsof -i :8082  # macOS/Linux
netstat -ano | findstr :8082  # Windows

# Kill the process or change port in .env
```

#### 3. Import Error in Python
```bash
# Ensure all dependencies are installed
pip install -r requirements.txt

# If using Docker, rebuild image
docker-compose build --no-cache payment_api
```

#### 4. Idempotency Key Error
```bash
# Clear idempotency keys table
docker exec payment-postgres psql -U postgres -d postgres \
  -c "DELETE FROM idempotency_keys WHERE expires_at < NOW();"
```

#### 5. Service Not Responding
```bash
# Check container status
docker-compose ps

# Restart services
docker-compose restart

# Check for errors in logs
docker-compose logs payment_api | grep ERROR
```

---

## Testing Guide

### Run Automated Tests
```bash
# Using Make
make test-api

# Manual testing with curl
./test_payment_api.sh
```

### Sample Test Script
Create `test_payment_api.sh`:
```bash
#!/bin/bash

echo "Testing Payment Service API..."

# Health check
echo "1. Health Check:"
curl -s http://localhost:8082/health | python -m json.tool

# Get payments
echo -e "\n2. Get Payments:"
curl -s http://localhost:8082/v1/payments?limit=5 | python -m json.tool

# Process payment
echo -e "\n3. Process Payment:"
curl -s -X POST http://localhost:8082/v1/payments/charge \
  -H "Content-Type: application/json" \
  -d '{
    "idempotency_key": "test-'$(date +%s)'",
    "trip_id": 1,
    "method": "CARD"
  }' | python -m json.tool
```

---

## Environment Variables

### Complete List
| Variable | Default | Description |
|----------|---------|-------------|
| DB_HOST | localhost | Database host |
| DB_PORT | 5433 | Database port |
| DB_NAME | postgres | Database name |
| DB_USER | postgres | Database user |
| DB_PASS | Superb#915 | Database password |
| SERVICE_PORT | 8082 | API port |
| TRIP_SERVICE_URL | http://localhost:8081 | Trip service URL |
| LOG_LEVEL | INFO | Logging level |
| RATE_LIMIT_ENABLED | true | Enable rate limiting |

---

## Backup and Recovery

### Create Backup
```bash
make db-backup
# or
docker exec payment-postgres pg_dump -U postgres postgres > backup.sql
```

### Restore from Backup
```bash
make db-restore
# or
cat backup.sql | docker exec -i payment-postgres psql -U postgres postgres
```

---

## Production Considerations

1. **Security**:
   - Change default passwords
   - Use secrets management
   - Enable TLS/SSL
   - Implement proper authentication

2. **Performance**:
   - Add caching (Redis)
   - Optimize database queries
   - Implement connection pooling
   - Use production WSGI server (Gunicorn)

3. **Monitoring**:
   - Set up Prometheus/Grafana
   - Configure alerting
   - Implement distributed tracing
   - Centralized logging (ELK stack)

4. **Scaling**:
   - Horizontal scaling with Kubernetes
   - Database replication
   - Load balancing
   - Circuit breakers for external services

---

## Contact & Support

For issues or questions about the Payment Service deployment:
- Check logs: `docker-compose logs payment_api`
- Review this documentation
- Contact the development team

---

**Document Version**: 1.0.0  
**Last Updated**: October 2024  
**Service Version**: 1.0.0