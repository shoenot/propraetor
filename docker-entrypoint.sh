#!/bin/sh
set -e

echo "Running collectstatic..."
python manage.py collectstatic --noinput

exec "$@"
