# Payment Service — Integration Guide

This document describes how other microservices can integrate with the **Payment Service**. It covers setup, environment configuration, Docker usage, API specifications, idempotency behavior, database schema highlights, and testing.

---

## Table of Contents

1. [Overview](#overview)
2. [Run & Connect (Docker / Local)](#run--connect-docker--local)
3. [Environment Variables](#environment-variables)
4. [API Endpoints](#api-endpoints)
   - [Create Payment](#1-create-payment-post-payments)
   - [Refund Payment](#2-refund-payment-post-paymentspayment_idrefunds)
   - [Health Check](#3-health-check-get-health)
5. [Idempotency Behavior](#idempotency-behavior)
6. [Database Schema Summary](#database-schema-summary)
7. [Postman Collection](#postman-collection)
8. [Testing & Verification](#testing--verification)
9. [Error Codes](#error-codes)
10. [Integration Tips for Other Services](#integration-tips-for-other-services)
11. [Troubleshooting](#troubleshooting)
12. [Ownership](#ownership)
13. [Quick Reference](#quick-reference)

---

## Overview

- **Service Role:** Handles all payment and refund transactions for completed trips
- **Language:** Python (Flask)
- **Database:** PostgreSQL
- **Containerized:** Yes (Docker)
- **Base URL (local):** `http://127.0.0.1:8082`

**Core Features:**

- Create payment for a trip
- Process refunds
- Idempotency protection (no duplicate charges)
- PostgreSQL persistence
- Docker and Postman integration ready

---

## Run & Connect (Docker / Local)

### Run with Docker

```bash
docker-compose build
docker-compose up -d
docker ps
```

Confirm it's running:

```bash
curl http://127.0.0.1:8082/health
```

### Run Locally (Development Mode)

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Load `.env` variables manually or via `setenv.bat`:

```bash
python database_setup.py
python app.py
```

---

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `DB_HOST` | Database host | `localhost` or `db` |
| `DB_PORT` | Database port | `5433` |
| `DB_NAME` | Database name | `postgres` |
| `DB_USER` | Database user | `postgres` |
| `DB_PASS` | Database password | `Superb#915` |
| `SERVICE_PORT` | Port to run app | `8082` |
| `TRIP_SERVICE_URL` | Trip Service base URL | `http://localhost:8081` |
| `DRIVER_SERVICE_URL` | Driver Service base URL | `http://localhost:8083` |
| `RIDER_SERVICE_URL` | Rider Service base URL | `http://localhost:8084` |
| `NOTIFICATION_SERVICE_URL` | Notification Service URL | `http://localhost:8085` |
| `API_PREFIX` | API prefix | `/v1` |
| `IDEMPOTENCY_KEY_TTL` | TTL for idempotency (seconds) | `86400` |
| `ENVIRONMENT` | Environment name | `development` |
| `DEBUG` | Enable debug logs | `true` |
| `LOG_LEVEL` | Logging level | `INFO` |

Copy `.env.example` and rename to `.env` before running the container.

---

## API Endpoints

### 1. Create Payment (POST /payments)

Create a payment for a trip.

**URL**

```
POST /payments
```

**Headers**

```
Content-Type: application/json
```

**Request Body**

```json
{
  "idempotency_key": "demo-client-1",
  "trip_id": 101,
  "method": "CARD",
  "amount": 150.00,
  "metadata": { "note": "local test" }
}
```

**Response (200 Success)**

```json
{
  "payment_id": 353,
  "trip_id": 101,
  "amount": 150.0,
  "method": "CARD",
  "status": "SUCCESS",
  "reference": "PAY-20251103-dd961ae0",
  "created_at": "2025-11-03T11:23:00.145775"
}
```

**Response (202 Accepted - Async Processing)**

```json
{
  "payment_id": null,
  "status": "PENDING",
  "message": "Payment accepted for processing"
}
```

**Error Responses**

| Code | Description |
|------|-------------|
| 400 | Invalid request body or missing required fields |
| 409 | Duplicate or in-progress idempotency key |
| 500 | Internal server error |

---

### 2. Refund Payment (POST /payments/{payment_id}/refunds)

Create a refund for an existing payment.

**URL**

```
POST /payments/{payment_id}/refunds
```

**Headers**

```
Content-Type: application/json
```

**Request Body**

```json
{
  "idempotency_key": "refund-demo-1",
  "amount": 50.00,
  "metadata": { "reason": "test refund" }
}
```

**Notes:**

- `idempotency_key` is required for idempotency of refunds
- `amount` is optional; if absent, the full amount is refunded

**Response (200 Success)**

```json
{
  "payment_id": 353,
  "refund_id": 12,
  "refund_amount": 50.0,
  "status": "REFUNDED",
  "timestamp": "2025-11-03T11:25:52.660094"
}
```

**Error Responses**

| Code | Description |
|------|-------------|
| 400 | Invalid payment or refund details |
| 409 | Refund already in progress |
| 500 | Server error |

---

### 3. Health Check (GET /health)

Check the service health status.

**URL**

```
GET /health
```

**Response**

```json
{
  "status": "healthy",
  "service": "payment-service",
  "version": "1.0.0"
}
```

---

## Idempotency Behavior

Every `POST` request must include a unique `idempotency_key`.

The key is hashed (SHA-256) and stored in the `idempotency_keys` table.

**Server behavior:**

- Locks the key on first request (in-progress state)
- Returns cached response for repeated requests with the same key
- Returns 409 Conflict if the key is already being processed
- Prevents double payment for the same transaction

**Example Sequence**

| Attempt | idempotency_key | Result |
|---------|-----------------|--------|
| 1st | `demo-client-1` | Payment created |
| 2nd | `demo-client-1` | Same response (no duplicate) |
| 3rd | `demo-client-2` | New payment created |

**Client Contract:** For retryable client flows, reuse the same `idempotency_key`. If you want a new payment, generate a new key.

---

## Database Schema Summary

### payments

| Column | Type | Description |
|--------|------|-------------|
| `payment_id` | INT (PK) | Auto-increment |
| `trip_id` | INT | Foreign key to trip |
| `amount` | NUMERIC | Payment amount |
| `method` | VARCHAR | Payment mode (CARD, UPI, WALLET, etc.) |
| `status` | VARCHAR | SUCCESS / FAILED / PENDING |
| `reference` | VARCHAR | Unique payment reference |
| `idempotency_hash` | VARCHAR | Linked idempotency key hash |
| `created_at` | TIMESTAMP | Creation time |
| `updated_at` | TIMESTAMP | Last update time |

### idempotency_keys

| Column | Type | Description |
|--------|------|-------------|
| `key_hash` | VARCHAR (PK) | SHA-256 hash of key |
| `request_path` | VARCHAR | Request endpoint (e.g., POST:/payments) |
| `response_status` | INT | Stored HTTP code |
| `response_data` | JSONB | Cached response body |
| `created_at` | TIMESTAMP | Created timestamp |
| `updated_at` | TIMESTAMP | Updated timestamp |
| `expires_at` | TIMESTAMP | TTL expiration time |

### payment_refunds (if present)

| Column | Type | Description |
|--------|------|-------------|
| `refund_id` | INT (PK) | Auto-increment |
| `payment_id` | INT (FK) | Payment reference |
| `amount` | NUMERIC | Refund amount |
| `status` | VARCHAR | REFUNDED / FAILED |
| `created_at` | TIMESTAMP | Creation time |

---

## Postman Collection

Use `Payment Service - Local.postman_collection.json` (provided by the developer).

**Setup steps:**

1. Set the collection variable:
   ```
   base_url = http://127.0.0.1:8082
   idempotency_key = demo-client-1
   ```

2. Run requests in order:
   - Health Check
   - Create Payment
   - Repeat Create Payment (verify idempotency)
   - Refund Payment

A Postman Environment file can be imported to set up variables automatically.

---

## Testing & Verification

| Test | Expected Behavior |
|------|-------------------|
| Create Payment | Returns 200 or 202 |
| Duplicate Payment | Returns same response or 409 |
| Refund Payment | Creates refund record |
| Concurrent Requests | Only one payment created |
| Service Restart | Data persists via Docker volume |

**Recommended Testing Workflow:**

1. Start all services via `docker-compose up -d`
2. Run health check: `GET /health`
3. Create a payment with `idempotency_key = demo-client-1` → note `payment_id`
4. Re-run Create Payment with same key → should return same response
5. Create refund on payment with `idempotency_key = refund-demo-1`
6. Run concurrency stress test (8 concurrent requests with same key)
7. Verify only one payment was created in the database

---

## Error Codes

| Code | Meaning |
|------|---------|
| 200 | Success (synchronous) |
| 201 | Created |
| 202 | Accepted (asynchronous processing) |
| 400 | Invalid input or validation error |
| 409 | Duplicate or in-progress idempotency key |
| 500 | Server error |

**Important Note:** Clients must never assume 200 means immediately charged in the gateway. Always check the `status` field in the response (SUCCESS, PENDING, FAILED).

---

## Integration Tips for Other Services

### Trip Service

- Call `POST /payments` when a trip is completed
- Use deterministic key: `"trip-" + trip_id + "-charge"`
- Store returned `payment_id` in trip record
- Ensure trip is completed before invoking payment

### Notification Service

- Payment Service sends async callbacks after success/refund
- Payload includes: `{ payment_id, trip_id, amount, status, reference }`
- Keep your notification endpoint idempotent

### Rider/Driver UI

- Should retry on 409 after short backoff or poll payment status
- Display transaction reference (`PAY-YYYYMMDD-xxxx`) to users

### General Rules

- Never reuse the same `idempotency_key` for different operations
- Always retry 409 responses with backoff or poll payment status
- Payment gateway keys must live in secure config / secrets manager
- Never hard-code credentials in repo

---

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| 409 Conflict repeatedly | First request still processing | Wait a few seconds or retry |
| 500 Server Error | DB not reachable | Check `DB_HOST` and port in `.env` |
| Duplicate payments | Missing `idempotency_key` | Always send key in request body |
| Docker container stops | DB startup lag | Use `depends_on` in `docker-compose.yml` |
| psql connection refused | Wrong DB credentials | Verify `.env` variables match DB setup |
| Service won't start | Schema mismatch | Run `python database_setup.py` |

**Debugging Tips:**

- View container logs: `docker logs <container_name>`
- Check DB schema: `psql -h localhost -d postgres -U postgres -c "\dt"`
- Test DB connection: `python -c "import psycopg2; psycopg2.connect(...)"`

---

## Ownership

| Field | Details |
|-------|---------|
| Owner | Suresh Kumar (Payment Service Developer) |
| Service Name | Payment Service |
| Port | 8082 |
| Database | PostgreSQL |
| Dockerfile | Present in root directory |
| Repository | `payment_service/` inside main project |

---

## Quick Reference

### Create Payment (curl)

```bash
curl -X POST "http://127.0.0.1:8082/payments" \
  -H "Content-Type: application/json" \
  -d '{
    "idempotency_key": "demo-client-1",
    "trip_id": 101,
    "method": "CARD",
    "amount": 150.00
  }'
```

### Refund Payment (curl)

```bash
curl -X POST "http://127.0.0.1:8082/payments/353/refunds" \
  -H "Content-Type: application/json" \
  -d '{
    "idempotency_key": "refund-demo-1",
    "amount": 50.00
  }'
```

### Health Check (curl)

```bash
curl http://127.0.0.1:8082/health
```

### Compute Idempotency Key Hash (psql)

```sql
SELECT encode(digest('demo-client-1','sha256'),'hex') AS keyhash;
```

---

## Important Files

- `app.py` — Flask app entry point
- `api/routes/payments.py` — API endpoints
- `services/idempotency_service.py` — Idempotency helpers
- `services/payment_service.py` — Business logic
- `database_setup.py` — Creates tables and seeds data
- `Dockerfile` — Container configuration
- `docker-compose.yml` — Multi-container orchestration
- `.env.example` — Environment variables template