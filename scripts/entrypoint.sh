#!/bin/bash

set -e

# Wait for database to be ready
python scripts/wait-for-it.py

# Apply database migrations
echo "Applying database migrations..."
python manage.py migrate

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Create superuser if not exists
python manage.py createsuperuser --noinput || true

# Start server
exec "$@"