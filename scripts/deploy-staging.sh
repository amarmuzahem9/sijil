#!/usr/bin/env bash
# Deploy / update Sijil staging on the company server (behind Nginx Proxy Manager).
# Run ON THE SERVER from the repository folder:   scripts/deploy-staging.sh
# See deploy/staging.md for the one-time setup (.env, NPM network, NPM Proxy Host).
set -euo pipefail
cd "$(dirname "$0")/.."

PUBLIC_URL="${PUBLIC_URL:-https://sijil.t3cftth.net}"
DC=(docker compose -f docker-compose.yml -f docker-compose.staging.yml)

fail() { echo "deploy-staging: $*" >&2; exit 1; }

# --- 1. Pre-flight checks ----------------------------------------------------------
[ -f .env ] || fail ".env is missing — create it from .env.example (deploy/staging.md, step 3)"
env_value() { grep -E "^$1=" .env | tail -n1 | cut -d= -f2- | tr -d '\r'; }

[ "$(env_value APP_ENV)" = "staging" ] || fail "APP_ENV in .env must be 'staging'"
NPM_NETWORK="$(env_value NPM_NETWORK)"
[ -n "$NPM_NETWORK" ] || fail "NPM_NETWORK is not set in .env (deploy/staging.md, step 2)"
docker network inspect "$NPM_NETWORK" >/dev/null 2>&1 \
    || fail "Docker network '$NPM_NETWORK' does not exist (deploy/staging.md, step 2)"
if grep -qE '=change-me$' .env; then
    fail "a value in .env is still 'change-me' — generate real secrets (deploy/staging.md, step 3)"
fi
case "$(env_value DATABASE_URL)" in
    *":$(env_value POSTGRES_PASSWORD)@db:"*) ;;
    *) fail "DATABASE_URL must contain the same password as POSTGRES_PASSWORD (deploy/staging.md, step 3)" ;;
esac

# The rendered config must not publish any host port (80/443 belong to NPM; 3000/8080/5433 are taken).
if "${DC[@]}" config --format json | grep -q '"published"'; then
    fail "the staging configuration publishes a host port — refusing to deploy"
fi

# --- 2. Update code and start ----------------------------------------------------------
git pull --ff-only
"${DC[@]}" up -d --build --remove-orphans --wait

# --- 3. Health: inside the stack, then through NPM ---------------------------------------
"${DC[@]}" exec -T api python -c \
    "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health', timeout=5)" \
    || fail "API health check failed — see: ${DC[*]} logs api"

ok=0
for _ in $(seq 1 20); do
    if curl -fsS --max-time 5 "$PUBLIC_URL/api/health" >/dev/null 2>&1; then ok=1; break; fi
    sleep 3
done

# --- 4. Synthetic test accounts (refused automatically when APP_ENV=production) -------------
"${DC[@]}" exec -T api python -m app.cli seed-demo

if [ "$ok" -ne 1 ]; then
    echo "deploy-staging: the stack is running, but $PUBLIC_URL/api/health is not reachable." >&2
    echo "  Check the Proxy Host in Nginx Proxy Manager (deploy/staging.md, step 5)." >&2
    exit 2
fi
echo "deploy-staging: OK — $PUBLIC_URL is up."
