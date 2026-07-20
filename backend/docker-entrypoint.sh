#!/bin/sh
set -eu

if [ -z "${JWT_SECRET:-}" ]; then
    echo "JWT_SECRET must be set" >&2
    exit 1
fi

if [ -z "${AES_KEY:-}" ]; then
    echo "AES_KEY must be set" >&2
    exit 1
fi

export DB_URL="${DB_URL:-sqlite:////data/app.db}"
cd "${APP_DIR:-/app/backend}"
python -m alembic -c alembic.ini upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
