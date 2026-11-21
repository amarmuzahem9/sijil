#!/bin/sh
# Startup order (research.md R7): migrate → bootstrap main admin → serve.
set -e

alembic upgrade head
python -m app.cli bootstrap

# Extra args (e.g. --reload in development) are appended by docker compose `command:`.
exec uvicorn app.main:app \
    --host 0.0.0.0 --port 8000 \
    --proxy-headers --forwarded-allow-ips "${TRUSTED_PROXY_CIDRS:-127.0.0.1}" \
    "$@"
