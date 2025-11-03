# Payment Service — Integration Guide

This document explains everything your teammates need to integrate with the Payment Service. It includes quick start instructions (Docker & local), environment variables, API endpoints with request/response examples, idempotency behavior, database schema highlights, Postman guidance, expected error codes, testing notes, and troubleshooting tips.

Use this markdown as the authoritative reference when wiring other services (Trip Service, Rider, Driver, Notification, etc.) to the Payment Service.

## Table of Contents

- [Quick Summary](#quick-summary)
- [Run & Connect](#run--connect)
- [Environment Variables](#environment-variables)
- [API Endpoints](#api-endpoints)
- [Idempotency](#idempotency)
- [Database Schema](#database-schema)
- [Postman Collection & Environment](#postman-collection--environment)
- [Testing & Verification](#testing--verification)
- [Errors & Status Codes](#errors--status-codes)
- [Logging, Metrics & Monitoring](#logging-metrics--monitoring)
- [Integration Tips](#integration-tips)
- [Troubleshooting](#troubleshooting)
- [Contact & Ownership](#contact--ownership)
- [Quick Reference](#quick-reference)

## Quick Summary

**Service responsibility:** Create payments, store payment records, prevent duplicates using idempotency, process refunds, and send notifications asynchronously.

**Base URL** (local/default): `http://127.0.0.1:8082` (Postman collection variable: `{{base_url}}`)

**Primary endpoints:**

- `POST /payments` — create a payment
- `POST /payments/{payment_id}/refunds` — refund a payment
- `GET /health` — service health

**Idempotency:** Client provides `idempotency_key` in the request body. The server hashes it and ensures only one processing flow occurs for that key.

## Run & Connect

### Docker (Recommended for Integration)

If the team uses Docker Compose (project `docker-compose.yml`):

```bash
# Build and run (from project root)
docker-compose build
docker-compose up -d   # -d runs in background
docker ps              # check running containers
```

Check health:

```bash
curl http://127.0.0.1:8082/health
```

### Local (Development)

Create virtualenv and install dependencies:

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Set environment variables (or call `setenv.bat` if provided).

Create database and seed:

```bash
python database_setup.py
```

Run:

```bash
python app.py
```

## Environment Variables

These are the variables your service expects (from `.env`):

- `DB_HOST` — Postgres host (e.g., `localhost` or `db` inside Docker)
- `DB_PORT` — Postgres port (example: `5433`)
- `DB_NAME` — database name
- `DB_USER` — database user
- `DB_PASS` — database password
- `SERVICE_PORT` — service port (default: `8082`)
- `TRIP_SERVICE_URL` — Trip Service URL
- `DRIVER_SERVICE_URL` — Driver Service URL
- `RIDER_SERVICE_URL` — Rider Service URL
- `NOTIFICATION_SERVICE_URL` — Notification Service URL
- `API_PREFIX` — prefix for API endpoints (e.g., `/v1` if used)
- `IDEMPOTENCY_KEY_TTL` — TTL seconds for idempotency records (default: `86400` = 24h)
- `ENVIRONMENT` — environment name
- `DEBUG` — debug mode flag
- `LOG_LEVEL` — logging level

**Note:** Do not commit credentials to VCS. Share `.env.example` (with placeholders) with the team.

## API Endpoints

Base: `{{base_url}}` (Postman collection variable). Example: `http://127.0.0.1:8082`

### POST /payments

Create a payment (charge a trip).

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
  "idempotency_key": "string_required",
  "trip_id": 101,
  "method": "CARD",
  "amount": 150.00,
  "metadata": { "note": "optional" }
}
```

**Notes:**

- `idempotency_key` is required and must be a non-empty string
- `method` should be one of the allowed methods (CARD, UPI, WALLET, NETBANKING, etc.)
- `amount` must be non-negative if provided; if not provided, the service may calculate from trip data

**Success Response** (HTTP 200 or 201/202)

```json
{
  "payment_id": 353,
  "trip_id": 101,
  "amount": 150.0,
  "method": "CARD",
  "status": "SUCCESS",
  "reference": "PAY-20251103-xxxx",
  "created_at": "2025-11-03T11:23:00.145775"
}
```

**Pending Response** (HTTP 202)

```json
{
  "payment_id": null,
  "status": "PENDING",
  "message": "Payment accepted for processing"
}
```

**Conflict** (HTTP 409)

```json
{
  "error": "Request with same idempotency key is already in progress"
}
```

**Bad Request** (HTTP 400)

```json
{
  "error": "Missing required fields: idempotency_key, trip_id"
}
```

**Server Error** (HTTP 500)

```json
{
  "error": "Payment processing failed"
}
```

### POST /payments/{payment_id}/refunds

Create a refund for a payment.

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
  "metadata": { "reason": "user requested" }
}
```

**Notes:**

- `idempotency_key` is required for idempotency of refunds
- `amount` is optional; if absent, the full amount is refunded

**Success Response** (HTTP 200)

```json
{
  "payment_id": 353,
  "refund_id": 12,
  "refund_amount": 50.0,
  "status": "REFUNDED",
  "timestamp": "2025-11-03T11:25:52.660094"
}
```

**Error Responses:**

- `400` — validation error (bad amount, payment not refundable, etc.)
- `409` — refund with same idempotency key already in progress
- `500` — server error

### GET /health

Basic health check.

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

(You may also have `/v1/health` depending on `API_PREFIX`.)

## Idempotency

**Where:** Client must send `idempotency_key` in the request body (both for create-payment and refunds).

**Hashing:** Server computes a deterministic hash (SHA-256 hex) of the raw key and stores it.

**Claiming:** On first request for a key, the server atomically inserts an idempotency row with `response_status = NULL` to indicate in-progress. This claim prevents races and duplicate charges.

**Completed:** After processing, server UPDATEs the row with `response_status` (HTTP code) and `response_data` (JSON). Later requests with the same key:

- If completed: server returns stored `response_data` and `response_status`
- If in-progress: server returns 409 Conflict (client can retry after a pause)

**TTL / Cleanup:** Idempotency rows have `expires_at` (e.g., 24h). A cleanup job (cron) is recommended to delete expired rows.

**Client contract:** For retryable client flows, reuse the same `idempotency_key`. If you want a new payment, generate a new key.

## Database Schema

### Important Tables & Columns (Summary)

#### payments

- `payment_id` (PK) — int
- `trip_id` — int
- `amount` — numeric
- `method` — varchar
- `status` — varchar (e.g., PENDING, SUCCESS, FAILED)
- `reference` — unique payment reference (string)
- `idempotency_hash` — varchar (sha256 hex)
- `created_at`, `updated_at` — timestamps

#### idempotency_keys

- `key_hash` (PK) — sha256 hex string
- `request_path` — e.g., `POST:/payments`
- `response_status` — int (HTTP)
- `response_data` — jsonb (cached response)
- `created_at`, `expires_at`, `updated_at` — timestamps

#### payment_refunds (if present)

- `refund_id` — int
- `payment_id` (FK) — int
- `amount` — numeric
- `status` — varchar
- `created_at` — timestamp

**Notes:**

- `idempotency_hash` in `payments` links to the idempotency row
- `payments.reference` is unique and typically generated as `PAY-YYYYMMDD-<shorthash>`

## Postman Collection & Environment

Import the Payment Service - Local collection (JSON provided by the developer).

Set collection variable `base_url` to `http://127.0.0.1:8082`.

**Important variables:**

- `idempotency_key` — set a fixed value (e.g., `demo-client-1`) to test idempotency repeatably
- `last_payment_id` — populated automatically by the Create Payment request test script

**Sharing:**

- Export the collection (v2.1) and share JSON with teammates
- Optionally export an Environment file including `base_url` and example keys

## Testing & Verification

Recommended workflow:

1. Start all services (your service + DB) via `docker-compose up -d`
2. Health check: `GET {{base_url}}/health`
3. Create a payment with `idempotency_key = demo-client-1` → note `payment_id`
4. Re-run Create Payment with same key → should return same response (no duplicate), or 409 if attempted while in-progress
5. Request refund on `payment_id` with `idempotency_key = refund-demo-1` → check single refund created
6. Concurrency stress: run 8 concurrent requests (same `idempotency_key`) — only one payment should be created. Use the provided `concurrency_test.py` if available
7. Check DB: idempotency row exists and `response_status` is set; `payments` table contains one row for that idempotency hash

## Errors & Status Codes

- `200` — successful synchronous creation or refund result
- `201` — (if returned) resource created
- `202` — accepted / pending asynchronous processing
- `400` — client validation error (bad/missing fields)
- `409` — idempotency key in-progress (client should retry later or poll)
- `500` — server error (generic). Server logs include stack traces (do not expose full error in production responses)

**Important note:** Clients must never assume 200 means immediately charged in the gateway; check `status` field (SUCCESS, PENDING, FAILED) in response.

## Logging, Metrics & Monitoring

**Logs:** Printed to container stdout — view with `docker logs <container>`

**Metrics endpoint** (if present): Check `/metrics` or whatever the service exposes

**Health endpoint:** `GET /health` (or `/v1/health` if prefixed)

**Important:** Ensure notification calls are async in the service so slow downstream services do not block payment flow.

## Integration Tips

**Trip Service should:**

- Ensure a trip is completed before invoking `POST /payments`
- Provide `trip_id` and optionally `amount` (or let Payment Service calculate fare)
- Pass a deterministic `idempotency_key` (e.g., `trip-<trip_id>-charge`) to avoid duplicates

**Notification Service:**

- Payment Service will call it asynchronously with payload `{ payment_id, trip_id, amount, status, reference }`
- Keep the notification endpoint idempotent as well

**Rider/Driver UI:**

- Should retry on 409 after a short backoff, or poll the payment status via an internal API if implemented

**Secrets:**

- Payment gateway keys must live in secure config / secrets manager; never hard-code in repo

## Troubleshooting

### Duplicate Payments on Concurrency Test

**Likely cause:** Old code used SELECT before INSERT.

**Fix:** Use atomic `INSERT ... ON CONFLICT DO NOTHING RETURNING` (or a DB-level claim) and UPDATE to store response after processing.

### psql Connection Refused

**Check:** `DB_HOST` and `DB_PORT`. In Docker Compose, DB service name is typically the host (e.g., `db`). Use `docker logs` to view DB startup errors.

### Postman Shows 409 Repeatedly

**Means:** Previous request still in-progress (server marked row with NULL response).

**Fix:** Wait a short time and re-run; or check server logs to ensure process completed.

### Response 500

**Check:** Server logs for stack trace. Common issues:

- DB not ready
- Schema mismatch (run `database_setup.py`)
- Missing env vars

## Contact & Ownership

**Service owner:** [Your Name] (replace with actual)

**GitHub repo / path:** `payment_service/` (root)

**Important files:**

- `app.py` — Flask app entry
- `api/routes/payments.py` — endpoints
- `services/idempotency_service.py` — idempotency helpers
- `services/payment_service.py` — business logic
- `database_setup.py` — creates tables & seeds `rhfd_payments.csv`
- `Dockerfile`, `docker-compose.yml` — containerization
- `README.md` — run instructions

## Quick Reference

### curl — Create Payment

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

### curl — Refund

```bash
curl -X POST "http://127.0.0.1:8082/payments/353/refunds" \
  -H "Content-Type: application/json" \
  -d '{
    "idempotency_key": "refund-demo-1",
    "amount": 50.00
  }'
```

### Compute Idempotency Key Hash (in psql)

```sql
SELECT encode(digest('demo-client-1','sha256'),'hex') AS keyhash;
```