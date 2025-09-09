#!/bin/bash

set -e

echo "Running migrations..."
python manage.py migrate

# echo "Collecting static files..."
# python manage.py collectstatic --noinput

echo "Starting Gunicorn server..."
exec gunicorn wajo_backend.wsgi:application --workers 3 --bind 0.0.0.0:8000
