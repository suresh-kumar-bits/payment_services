#!/bin/sh
# wait-for-postgres.sh

set -e

# Default values
DEFAULT_HOST="payment_db"
DEFAULT_PORT="5433"
DEFAULT_USER="postgres"
DEFAULT_DB="postgres"
DEFAULT_TIMEOUT=60

# Use environment variables or defaults
HOST="${1:-${DB_HOST:-$DEFAULT_HOST}}"
PORT="${DB_PORT:-$DEFAULT_PORT}"
USER="${DB_USER:-$DEFAULT_USER}"
DB="${DB_NAME:-$DEFAULT_DB}"
PASSWORD="${DB_PASS:-Superb#915}"
TIMEOUT="${WAIT_TIMEOUT:-$DEFAULT_TIMEOUT}"

# Shift arguments if host was provided as first argument
if [ "$#" -gt 0 ]; then
    shift
fi
CMD="$@"

echo "Waiting for PostgreSQL at $HOST:$PORT (timeout: ${TIMEOUT}s)..."

counter=0
until PGPASSWORD="$PASSWORD" psql -h "$HOST" -p "$PORT" -U "$USER" -d "$DB" -c '\q' 2>/dev/null; do
    counter=$((counter+1))
    
    if [ $counter -gt $TIMEOUT ]; then
        echo "❌ Timeout: PostgreSQL at $HOST:$PORT is still unavailable after ${TIMEOUT} seconds"
        exit 1
    fi
    
    echo "⏳ PostgreSQL is unavailable - attempt $counter/$TIMEOUT (sleeping 1s)"
    sleep 1
done

echo "✅ PostgreSQL is up and ready at $HOST:$PORT"

# Execute the command if provided
if [ -n "$CMD" ]; then
    echo "Executing command: $CMD"
    exec $CMD
fi