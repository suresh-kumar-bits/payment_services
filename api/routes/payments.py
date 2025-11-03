# api/routes/payments.py
from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
import threading
import json
import logging

# adapt imports to your project structure
from services.idempotency_service import IdempotencyService
from services.payment_service import PaymentService
from services.external_services import ExternalServices
from database.connection import db
from utils.helpers import validate_payment_method, is_valid_trip_id
from utils.logger import get_logger
from werkzeug.exceptions import BadRequest

logger = get_logger(__name__)
bp = Blueprint("payments", __name__, url_prefix="/payments")


def _fire_notification_async(payload):
    """Fire notification in background thread; do not block response."""
    try:
        ExternalServices.send_payment_notification(payload)
    except Exception:
        logger.exception("Background notification failed")


def _claim_idempotency_row(key_hash: str, request_key: str, ttl_hours: int = 24):
    """
    Attempt to atomically claim an idempotency key.
    Returns:
      - {'claimed': True}    -> we inserted the row and should proceed
      - {'claimed': False, 'completed': True, 'response': {...}, 'status_code': int}
      - {'claimed': False, 'in_progress': True}
    """
    try:
        # Try to insert a new idempotency row. If the key already exists, INSERT ... DO NOTHING returns no row.
        insert_sql = """
            INSERT INTO idempotency_keys (key_hash, request_path, response_status, response_data, created_at, expires_at)
            VALUES (%s, %s, NULL, NULL, %s, NOW() + INTERVAL '%s hours')
            ON CONFLICT (key_hash) DO NOTHING
            RETURNING key_hash
        """
        now = datetime.utcnow()
        with db.get_db_cursor(commit=True) as cur:
            cur.execute(insert_sql, (key_hash, request_key, now, ttl_hours))
            inserted = cur.fetchone()

        if inserted:
            # We claimed the key successfully
            return {'claimed': True}

        # Else the key already exists: fetch it to determine state
        select_sql = "SELECT response_status, response_data FROM idempotency_keys WHERE key_hash = %s"
        with db.get_db_cursor() as cur:
            cur.execute(select_sql, (key_hash,))
            row = cur.fetchone()

        if not row:
            # Strange case: no row found after conflict — treat as in progress
            return {'claimed': False, 'in_progress': True}

        response_status, response_data = row[0], row[1]

        if response_status is not None:
            # Completed earlier — return stored response
            # response_data may be JSON text; normalize to dict if needed
            try:
                payload = response_data if isinstance(response_data, dict) else json.loads(response_data)
            except Exception:
                payload = response_data
            return {'claimed': False, 'completed': True, 'response': payload, 'status_code': int(response_status)}

        # response_status is NULL => another request is processing the key
        return {'claimed': False, 'in_progress': True}

    except Exception as e:
        logger.exception("Error during idempotency claim")
        # On DB error, better to fail-safe by returning in_progress so we don't double-charge
        return {'claimed': False, 'in_progress': True}


def _mark_idempotency_completed(key_hash: str, response_obj: dict, status_code: int):
    """
    Update the idempotency row with the final response so future requests receive cached response.
    Returns True on success.
    """
    try:
        update_sql = """
            UPDATE idempotency_keys
            SET response_status = %s, response_data = %s, updated_at = %s
            WHERE key_hash = %s
        """
        with db.get_db_cursor(commit=True) as cur:
            cur.execute(update_sql, (int(status_code), json.dumps(response_obj), datetime.utcnow(), key_hash))
            return cur.rowcount > 0
    except Exception:
        logger.exception("Failed to update idempotency row with response")
        return False


@bp.route("", methods=["POST"])
def create_payment():
    """
    POST /payments
    Body:
      - idempotency_key (str) required
      - trip_id (int) required
      - method (str) required
      - amount (optional) numeric
      - metadata (optional) dict
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'error': 'Invalid or missing JSON body'}), 400

    # required fields
    required = ['idempotency_key', 'trip_id', 'method']
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({'error': f"Missing required fields: {', '.join(missing)}"}), 400

    raw_key = str(data.get('idempotency_key', '')).strip()
    if not raw_key:
        return jsonify({'error': 'idempotency_key must be non-empty'}), 400

    try:
        trip_id = int(data.get('trip_id'))
    except Exception:
        return jsonify({'error': 'trip_id must be an integer'}), 400

    if not is_valid_trip_id(trip_id):
        return jsonify({'error': 'Invalid trip_id'}), 400

    method = str(data.get('method')).upper()
    if not validate_payment_method(method):
        return jsonify({'error': f'Unsupported payment method. Allowed: CARD, WALLET, UPI, CASH'}), 400

    metadata = data.get('metadata') if isinstance(data.get('metadata'), dict) else {}
    provided_amount = data.get('amount', None)
    amount = None
    if provided_amount is not None:
        try:
            # PaymentService expects amount as float; keep validation simple and strict
            amount = float(provided_amount)
            if amount < 0:
                return jsonify({'error': 'amount must be non-negative'}), 400
        except Exception:
            return jsonify({'error': 'Invalid amount format'}), 400

    # Idempotency: generate hash and try to claim
    key_hash = IdempotencyService.generate_hash(raw_key)
    request_key = f"{request.method}:{request.path}"
    ttl_hours = current_app.config.get('IDEMPOTENCY_TTL_HOURS', 24)

    claim = _claim_idempotency_row(key_hash, request_key, ttl_hours)
    if not claim.get('claimed', False):
        if claim.get('completed'):
            return jsonify(claim['response']), claim.get('status_code', 200)
        if claim.get('in_progress'):
            return jsonify({'error': 'Request with same idempotency key is already in progress'}), 409
        # fallback
        return jsonify({'error': 'Unable to claim idempotency key'}), 409

    # We own the idempotency key — proceed with processing
    try:
        # Validate trip completion via ExternalServices
        is_completed, trip_data = ExternalServices.validate_trip_completion(trip_id)
        if not is_completed:
            # Mark idempotency and return 400 — client should correct and retry
            resp = {'error': 'Trip not completed or not found'}
            _mark_idempotency_completed(key_hash, resp, 400)
            return jsonify(resp), 400

        # Determine amount if not provided
        if amount is None:
            try:
                fare = PaymentService.calculate_fare(trip_data)
                amount = float(fare)
            except Exception:
                amount = 0.0

        # Prepare payload for gateway (simulate)
        payment_payload = {
            'trip_id': trip_id,
            'amount': amount,
            'method': method,
            'metadata': metadata
        }

        gateway_resp = ExternalServices.simulate_payment_gateway(payment_payload)
        # gateway_resp expected keys: status (SUCCESS/FAILED/PENDING), gateway_id, message, maybe error_code
        status = gateway_resp.get('status', 'FAILED')
        if status == 'SUCCESS':
            payment_status = 'SUCCESS'
        elif status == 'PENDING':
            payment_status = 'PENDING'
        else:
            payment_status = 'FAILED'

        # Persist payment via PaymentService.create_payment
        payment_data = {
            'trip_id': trip_id,
            'amount': amount,
            'method': method,
            'status': payment_status,
            'idempotency_hash': key_hash,
            'gateway_details': gateway_resp
        }
        created = PaymentService.create_payment(payment_data)

    except BadRequest as e:
        # Business-level validation from PaymentService
        logger.info("PaymentService rejected request: %s", e)
        resp = {'error': str(e)}
        _mark_idempotency_completed(key_hash, resp, 400)
        return jsonify(resp), 400
    except Exception as e:
        logger.exception("Unexpected error during payment processing")
        resp = {'error': 'Payment processing failed'}
        # mark idempotency to avoid double-charging; depending on policy you may leave it open for retry.
        _mark_idempotency_completed(key_hash, resp, 500)
        return jsonify(resp), 500

    # Mark idempotency completed with saved payment
    try:
        status_code = 200 if created.get('status') == 'SUCCESS' else 202
        _mark_idempotency_completed(key_hash, created, status_code)
    except Exception:
        logger.exception("Failed to persist idempotency completion")

    # Fire notification asynchronously (do not block)
    try:
        threading.Thread(target=_fire_notification_async, args=(created,), daemon=True).start()
    except Exception:
        logger.exception("Failed to spawn notification thread")

    return jsonify(created), status_code


@bp.route("/<int:payment_id>/refunds", methods=["POST"])
def create_refund(payment_id):
    """
    POST /payments/<payment_id>/refunds
    Body:
      - idempotency_key (str) required for refund idempotency
      - amount (optional) positive float
      - metadata (optional) dict
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'error': 'Invalid or missing JSON body'}), 400

    raw_key = str(data.get('idempotency_key', '')).strip()
    if not raw_key:
        return jsonify({'error': 'idempotency_key is required for refund idempotency'}), 400

    provided_amount = data.get('amount', None)
    refund_amount = None
    if provided_amount is not None:
        try:
            refund_amount = float(provided_amount)
            if refund_amount <= 0:
                return jsonify({'error': 'refund amount must be positive'}), 400
        except Exception:
            return jsonify({'error': 'Invalid refund amount'}), 400

    metadata = data.get('metadata') if isinstance(data.get('metadata'), dict) else {}

    # Claim idempotency
    key_hash = IdempotencyService.generate_hash(raw_key)
    request_key = f"{request.method}:{request.path}"
    ttl_hours = current_app.config.get('IDEMPOTENCY_TTL_HOURS', 24)

    claim = _claim_idempotency_row(key_hash, request_key, ttl_hours)
    if not claim.get('claimed', False):
        if claim.get('completed'):
            return jsonify(claim['response']), claim.get('status_code', 200)
        if claim.get('in_progress'):
            return jsonify({'error': 'Refund with same idempotency key is already in progress'}), 409
        return jsonify({'error': 'Unable to claim idempotency key'}), 409

    # Perform refund
    try:
        refund_result = PaymentService.process_refund(payment_id, refund_amount)
    except BadRequest as e:
        logger.info("Refund rejected: %s", e)
        resp = {'error': str(e)}
        _mark_idempotency_completed(key_hash, resp, 400)
        return jsonify(resp), 400
    except Exception:
        logger.exception("Unexpected error during refund processing")
        resp = {'error': 'Refund processing failed'}
        _mark_idempotency_completed(key_hash, resp, 500)
        return jsonify(resp), 500

    # Mark idempotency completed
    try:
        status_code = 200 if refund_result.get('status') in ('REFUNDED', 'SUCCESS') else 202
        _mark_idempotency_completed(key_hash, refund_result, status_code)
    except Exception:
        logger.exception("Failed to persist refund idempotency completion")

    # Fire notification asynchronously
    try:
        threading.Thread(target=_fire_notification_async, args=(refund_result,), daemon=True).start()
    except Exception:
        logger.exception("Failed to spawn refund notification thread")

    return jsonify(refund_result), status_code
