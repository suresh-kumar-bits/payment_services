# Payment Service

This repository implements a lightweight Payment Service built using Flask. It provides endpoints to charge payments for completed trips, list and query payments, process refunds, and produce receipts and metrics. The project includes a small in-memory rate limiter, idempotency support backed by a PostgreSQL table, and a Dockerfile + docker-compose setup for easy local deployment.

---

## Quick summary

- Language: Python 3.11
- Framework: Flask
- DB: PostgreSQL (schema and initial data loader provided in `database_setup.py`)
- Containerization: Docker + docker-compose
- Testing: `pytest` (test files may be present in `tests/`)

---

## Repository layout

- `app.py` - Flask application factory and main entrypoint.
- `config.py` - Centralized configuration loaded from environment variables (.env supported via python-dotenv).
- `database_setup.py` - Creates schema and loads `rhfd_payments.csv` into the `payments` table.
- `Dockerfile`, `docker-compose.yml` - Container images and compose orchestration for local setup.
- `requirements.txt` - Python dependencies.

Folders

- `api/`
  - `routes/` - Flask Blueprints for `health`, `payments`, and `metrics`.
  - `middleware/` - Error handlers and a simple in-memory rate limiter.

- `services/`
  - `payment_service.py` - Core business logic: calculate fares, create payments, refunds, receipts, metrics.
  - `idempotency_service.py` - Idempotency key handling and persistence in the `idempotency_keys` table.
  - `external_services.py` - Inter-service HTTP helpers and a payment gateway simulator.

- `database/`
  - `connection.py` - Database connection helper and context manager.

- `utils/`
  - `helpers.py` - Various small helper functions (formatting, validation, reference generation).
  - `logger.py` - Structured JSON logging (or simple formatter in DEBUG).

- `models/` - (empty or project-specific models if present)
- `tests/` - Unit/integration tests (if present).
- `rhfd_payments.csv` - Example payment data loader used by `database_setup.py`.

---

## Configuration

`config.py` centralizes configuration and reads environment variables. Important variables:

- `SERVICE_PORT` (default 8082)
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASS` (used by `database_setup.py` and `database/connection.py`)
- `TRIP_SERVICE_URL`, `NOTIFICATION_SERVICE_URL`, `RIDER_SERVICE_URL`, `DRIVER_SERVICE_URL` (URLs for inter-service calls)
- `RATE_LIMIT_ENABLED`, `RATE_LIMIT_DEFAULT`, `RATE_LIMIT_CHARGE`, `RATE_LIMIT_REFUND`
- Business rules: `BASE_FARE`, `RATE_PER_KM`, `SURGE_MULTIPLIERS`, `CANCELLATION_FEE`
- `IDEMPOTENCY_KEY_TTL` (seconds)

There is also `Config.get_database_uri()` helper for a DB URI string.

You can provide these via a `.env` file or environment variables. Example `.env`:

SERVICE_PORT=8082
DB_HOST=localhost
DB_PORT=5433
DB_NAME=postgres
DB_USER=postgres
DB_PASS=Superb#915
DEBUG=true

---

## API Endpoints

Base URL prefix: `/` (root) and `/v1` for payment-related endpoints.

1) Root
- GET `/` - Service info summary (service, version, endpoints)

2) Health & readiness
- GET `/health` - Health checks (DB connectivity and placeholders for dependencies). Returns 200 or 503 depending on DB.
- GET `/ready` - Readiness probe (checks DB). Returns 200 if ready.
- GET `/live` - Liveness probe (simple alive check).

3) Payments (Blueprint mounted at `/v1`)

- GET `/v1/payments` - List payments with optional query parameters:
  - `trip_id` (int)
  - `status` (string)
  - `method` (string)
  - `limit` (int, default 100)
  - `offset` (int, default 0)

  Response: JSON { payments: [...], count: N, limit, offset }

- GET `/v1/payments/<payment_id>` - Get a single payment by numeric ID. 404 if not found.

- POST `/v1/payments/charge` - Process a payment (idempotent). Example request body:

  {
    "idempotency_key": "unique-key-123",
    "trip_id": 123,
    "method": "CARD",
    "rider_id": 456,
    "driver_id": 789
  }

  Behavior:
  - Validates idempotency: hashed key is checked against `idempotency_keys` table. If present and valid, cached response returned.
  - Validates trip completion via `ExternalServices.validate_trip_completion` (calls `TRIP_SERVICE_URL` or returns mock in DEBUG).
  - Calculates fare using `PaymentService.calculate_fare()` or uses provided amount.
  - Calls `ExternalServices.simulate_payment_gateway()` (simulates gateway) and persists the payment in `payments` table.
  - Stores idempotency response record.
  - Triggers `ExternalServices.send_payment_notification()` (best-effort; failures are logged but don't fail the payment).

  Returns 201 for SUCCESS, 202 for PENDING/FAILED-like outcomes, or 400/500 for errors.

- POST `/v1/payments/<payment_id>/refund` - Request a refund for an existing payment.
  - Optional `idempotency_key` in body; otherwise a generated key is used for refund operations.
  - Validates payment exists and is `SUCCESS` before refunding.
  - Returns refund details JSON.

- GET `/v1/payments/<payment_id>/receipt` - Generate or fetch a receipt for a payment. Stores receipt JSON into `payment_receipts`.

4) Metrics
- GET `/metrics` - Returns JSON metrics (payments by status, by method, avg amount, total revenue).
- GET `/metrics/prometheus` - Returns Prometheus-formatted plain text metrics.

---

## Database schema (high level)

`database_setup.py` creates the following tables:
- `payments` (payment_id PK, trip_id, amount, method, status, reference, created_at, updated_at)
- `idempotency_keys` (key_hash PK, request_path, response_status, response_data JSONB, expires_at)
- `payment_refunds` (refund_id PK, payment_id FK -> payments, refund_amount, reason, status)
- `payment_receipts` (receipt_id PK, payment_id FK, receipt_number unique, receipt_data JSONB, generated_at)

There are simple indexes on frequently queried columns like `created_at`, `status`, and `trip_id`.

`database_setup.py` also supports loading initial records from `rhfd_payments.csv`.

---

## Rate limiting

A lightweight in-memory rate limiter is implemented in `api/middleware/rate_limiter.py`.
- The `@rate_limit(max_calls=50, time_window=60)` decorator is used for the charge endpoint.
- It's a per-process in-memory store using `request.remote_addr` as the key.

Note: This in-memory approach does not scale across multiple instances; use Redis or another store for production.

---

## Idempotency

Idempotency keys are hashed using SHA-256 and persisted in the `idempotency_keys` table and used to short-circuit repeated requests. TTL defaults to 24 hours and can be configured via `IDEMPOTENCY_KEY_TTL`.

---

## Logging

`utils/logger.py` exposes `get_logger(name)` which uses JSON logging in non-DEBUG mode and a human-friendly formatter in DEBUG. Log level is controlled by `LOG_LEVEL` in `config.py`.

---

## External dependencies and integration points

- Trip Service: `TRIP_SERVICE_URL` used to validate trip completion before charging.
- Notification Service: `NOTIFICATION_SERVICE_URL` for sending a post-payment notification.
- Rider / Driver services: endpoints configured via `RIDER_SERVICE_URL` and `DRIVER_SERVICE_URL` used by `external_services.py`.

In DEBUG mode, the `ExternalServices.validate_trip_completion()` will return mock completed trip data if the trip service is unreachable.

---

## Running locally (development) - Windows PowerShell

Prerequisites:
- Docker & Docker Compose (for containerized environment)
- Python 3.11 (if running locally without Docker)

1) Using Docker Compose (recommended for parity)

Open PowerShell in repository root and run:

```powershell
# Build and start postgres + payment service
docker compose up --build
```

This will:
- Start a `postgres:15-alpine` container with DB port mapped to host 5433.
- Build the payment service image and start the API at host port 8082.

Health checks are configured in the `docker-compose.yml` for both containers.

2) Local (without Docker) - fast iteration

Create virtualenv and install deps:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If you don't have PostgreSQL running on host: start a local Postgres instance (or change `DB_HOST`/`DB_PORT` to point to your DB). The `database_setup.py` expects DB reachable using values in `config.py` / env.

Run DB setup and start the app:

```powershell
python database_setup.py
python app.py
```

The service will be available at: http://localhost:8082

---

## Running tests

If the repository includes tests in `tests/`, run them with pytest. Note: tests may assume a running database or use mocks.

```powershell
# activate your venv then
pytest -q
```

If tests require database, ensure DB is available or adapt tests to use SQLite/mocks.

---

## Docker specifics

- `Dockerfile` uses `python:3.11-slim`, installs dependencies, copies code, and runs `database_setup.py` before `app.py`.
- The container runs as a non-root user `paymentservice` (UID 1000).
- `docker-compose.yml` binds the Postgres container to host port 5433 and maps service to 8082.

Notes:
- The `Dockerfile` healthcheck uses `requests` inside the container to hit `/health`.
- `docker-compose` sets DB envs for the API so it points to the `payment_db` service name as host.

---

## Security & Production considerations

- Secrets: `DB_PASS` and `POSTGRES_PASSWORD` are stored as plaintext env vars in `docker-compose.yml` for convenience. Use secrets management (Docker secrets, Vault, env injection) in production.
- Rate limiter: in-memory and not suitable for multi-instance deployments. Replace with Redis-based limiter (e.g., `limits`, `redis-py`, `flask-limiter`).
- Idempotency storage: currently in Postgres. That's acceptable; ensure proper indexing and pruning (cleanup job uses TTL).
- Observability: Structured logging is implemented. Add proper tracing (OpenTelemetry) and push metrics to Prometheus.
- Resilience: External services are called synchronously; consider async or retries with backoff for production.

---

## Known limitations & next steps

- Rate limiter is process-local — use a central store for distributed rate limits.
- No authentication or authorization implemented for endpoints — add JWT or API keys as required.
- No migration framework (e.g., Alembic). Consider adding migrations instead of `DROP/CREATE` in `database_setup.py` for production.
- No background job system for retries or notification delivery (e.g., Celery, RQ).
- Add integration tests that spin up a docker-compose test environment and run end-to-end flows.

---

## Contact & developer notes

- To change default ports or DB settings, modify environment variables or `config.py`.
- The `rhfd_payments.csv` file is used as the seed dataset for development.
- For debugging, set `DEBUG=true` in the environment or `.env` to enable friendly logging and mock fallback in `ExternalServices`.

---

If you'd like, I can:
- Add a short Postman collection or OpenAPI spec for the endpoints.
- Add a small `Makefile` or PowerShell script with common commands (start, stop, setup-db, test).
- Implement a Redis-based rate limiter and a simple health-check retry mechanism for external calls.

