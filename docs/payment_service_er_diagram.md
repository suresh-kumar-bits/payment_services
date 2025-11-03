## Payment Service Database Schema

This document outlines the database schema for the Payment Service.

### Data Ownership

As per the database-per-service pattern, this service is the sole owner of all data related to payments, refunds, and receipts.

### Table Structure

#### 1. `payments` table
This is the main table for all financial transactions.
* `payment_id` (Primary Key, Integer): The unique ID for the payment.
* `trip_id` (Integer): The ID of the trip this payment is for.
* `amount` (Numeric): The total amount charged.
* `method` (Varchar): The payment method (e.g., 'CARD', 'WALLET').
* `status` (Varchar): The final status (e.g., 'SUCCESS', 'FAILED').
* `reference` (Varchar): The payment gateway reference code.
* `created_at` (Timestamp): When the payment was recorded.
* `updated_at` (Timestamp): When the record was last updated.

#### 2. `idempotency_keys` table
This table is critical for preventing duplicate charges.
* `idempotency_key` (Primary Key, Varchar): The unique key sent by the client for a charge request.
* `request_hash` (Varchar): A hash of the request payload to ensure it hasn't changed.
* `payment_id` (Foreign Key -> `payments.payment_id`): The payment record that was created by this key.
* `status` (Varchar): The status of the idempotent request (e.g., 'PENDING', 'COMPLETED').
* `created_at` (Timestamp): When the request was first seen.

#### 3. `payment_refunds` table
This table stores all refund transactions.
* `refund_id` (Primary Key, Serial): The unique ID for the refund.
* `original_payment_id` (Foreign Key -> `payments.payment_id`): The original payment that is being refunded.
* `amount` (Numeric): The amount refunded.
* `reason` (Varchar): The reason for the refund.
* `status` (Varchar): The status of the refund (e.g., 'SUCCESS', 'FAILED').
* `reference` (Varchar): The payment gateway reference for the refund.
* `created_at` (Timestamp): When the refund was recorded.

#### 4. `payment_receipts` table
This table stores information about generated receipts.
* `receipt_id` (Primary Key, Serial): The unique ID for the receipt.
* `payment_id` (Foreign Key -> `payments.payment_id`): The payment this receipt is for.
* `receipt_url` (Varchar): A link to the generated receipt (e.g., an S3 URL).
* `generated_at` (Timestamp): When the receipt was created.
* `data_snapshot` (JSON): A JSON blob of the payment/trip details at the time of receipt generation.