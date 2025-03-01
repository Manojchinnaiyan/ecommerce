#!/bin/bash

set -e

# Print environment variables for debugging
echo "DATABASE_URL: $DATABASE_URL"
echo "DB_HOST: $DB_HOST"
echo "DB_PORT: $DB_PORT"
echo "DB_NAME: $DB_NAME"

# Wait for database to be ready
echo "Waiting for database connection..."
python scripts/wait-for-it.py
WAIT_EXIT_CODE=$?

if [ $WAIT_EXIT_CODE -ne 0 ]; then
    echo "Failed to connect to database. Exiting."
    exit 1
fi

# Apply database migrations
echo "Applying database migrations..."
python manage.py migrate

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Create superuser if not exists
echo "Creating superuser (if not exists)..."
python manage.py createsuperuser --noinput || true

# Start server
echo "Starting application server..."
exec "$@"