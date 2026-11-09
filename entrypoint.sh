#!/bin/sh
set -e

if [ -z "${SECRET_KEY:-}" ]; then
    SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(50))')"
    export SECRET_KEY
    printf '%s' "$SECRET_KEY" > /app/.runtime_secret_key
    chmod 600 /app/.runtime_secret_key
fi

python manage.py migrate --noinput
python manage.py collectstatic --noinput
exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3
