#!/usr/bin/env bash
# Deploy / update Sijil on the company server (behind Nginx Proxy Manager), in staging or in
# production — the mode is APP_ENV in .env (feature 016, research R11, contracts/cli.md).
# Run ON THE SERVER from the repository folder:   scripts/deploy.sh
# See deploy/server.md (install, update, go-live) and deploy/backup.md (backups, restore).
#
#   1. pre-flight checks of .env and of the server (nothing changes when one fails);
#   2. a «pre_deploy» backup of the running app (stops here if it fails);
#   3. git pull, build, start (the backup service included);
#   4. health inside the stack and through the public address;
#   5. staging only: the synthetic demo accounts;
#   6. the deploy is recorded on the backup page.
#
# Exit codes: 0 ok, 1 refused before any change, 2 the public address is not reachable,
# 8 the new version did not start (the rollback steps are printed).
set -euo pipefail
cd "$(dirname "$0")/.."
export MSYS_NO_PATHCONV=1

PUBLIC_URL="${PUBLIC_URL:-https://sijil.t3cftth.net}"
ENV_FILE="${SIJIL_DEPLOY_ENV:-.env}"
# The local checks (scripts/deploy-e2e.sh) only: their own env file, no git pull, and an overlay
# that leaves the 4 GB card reader out.
E2E=0
if [ "${SIJIL_E2E:-}" = 1 ] && [ "$ENV_FILE" != ".env" ]; then E2E=1; fi

fail() { echo "deploy: $*" >&2; exit 1; }
[ -f "$ENV_FILE" ] || fail ".env is missing — create it from .env.example (deploy/server.md, step 3)"
env_value() { grep -E "^$1=" "$ENV_FILE" | tail -n1 | cut -d= -f2- | tr -d '\r' || true; }

export SIJIL_ENV_FILE="$ENV_FILE"
DC=(docker compose --env-file "$ENV_FILE" -f docker-compose.yml -f docker-compose.server.yml)
if [ "$E2E" = 1 ] && [ -n "${SIJIL_DEPLOY_EXTRA_FILES:-}" ]; then
    DC+=(-f "$SIJIL_DEPLOY_EXTRA_FILES")
fi

# --- 1. Pre-flight checks --------------------------------------------------------------------
MODE="$(env_value APP_ENV)"
case "$MODE" in
    staging|production) ;;
    *) fail "APP_ENV in .env must be 'staging' or 'production'" ;;
esac
NPM_NETWORK="$(env_value NPM_NETWORK)"
[ -n "$NPM_NETWORK" ] || fail "NPM_NETWORK is not set in .env (deploy/server.md, step 2)"
docker network inspect "$NPM_NETWORK" >/dev/null 2>&1 \
    || fail "Docker network '$NPM_NETWORK' does not exist (deploy/server.md, step 2)"
if grep -qE '=change-me$' "$ENV_FILE"; then
    fail "a value in .env is still 'change-me' — generate real secrets (deploy/server.md, step 3)"
fi
case "$(env_value DATABASE_URL)" in
    *":$(env_value POSTGRES_PASSWORD)@db:"*) ;;
    *) fail "DATABASE_URL must contain the same password as POSTGRES_PASSWORD (deploy/server.md, step 3)" ;;
esac

# Backups (feature 016): the folder and the key exist before anything is deployed.
BACKUP_DIR="$(env_value BACKUP_DIR)"
[ -n "$BACKUP_DIR" ] || fail "BACKUP_DIR is not set in .env (deploy/backup.md, step 1)"
[ -d "$BACKUP_DIR" ] || fail "BACKUP_DIR '$BACKUP_DIR' does not exist (deploy/backup.md, step 1)"
if [ "$E2E" != 1 ]; then
    [ "$(stat -c %u "$BACKUP_DIR")" = 10001 ] && [ "$(stat -c %a "$BACKUP_DIR")" = 700 ] \
        || fail "BACKUP_DIR must belong to uid 10001 with mode 700 (deploy/backup.md, step 1)"
fi
[ -n "$(env_value BACKUP_AGE_RECIPIENT)" ] && [ -f "$BACKUP_DIR/key.age" ] \
    || fail "no backup key: run 'scripts/backup.sh init-key' and set BACKUP_AGE_RECIPIENT (deploy/backup.md, step 2)"

if [ "$MODE" = production ]; then
    for name in OCR_MODE OTP_MODE DRIVE_MODE; do
        [ "$(env_value "$name")" != fake ] || fail "$name=fake is not allowed in production"
    done
    [ -z "$(env_value OTP_FAKE_CODE)" ] || fail "OTP_FAKE_CODE must be empty in production"
fi

# The rendered config must not publish any host port (80/443 belong to NPM; 3000/8080/5433 are
# taken), nor give any container the Docker socket.
CONFIG="$("${DC[@]}" config --format json)" || fail "the compose configuration is invalid"
if grep -q '"published"' <<<"$CONFIG"; then fail "the configuration publishes a host port — refusing to deploy"; fi
if grep -q 'docker.sock' <<<"$CONFIG"; then fail "the configuration mounts the Docker socket — refusing to deploy"; fi

RUNNING=0
if [ -n "$("${DC[@]}" ps --status running -q api 2>/dev/null)" ]; then RUNNING=1; fi
if [ "$MODE" = production ] && [ "$RUNNING" = 1 ]; then
    "${DC[@]}" exec -T api python -m app.cli go-live --check </dev/null \
        || fail "demo accounts are still active — run go-live first: ${DC[*]} exec api python -m app.cli go-live"
fi

# --- 2. Backup of the running app -----------------------------------------------------------------
PRE="-"
if [ "$RUNNING" = 1 ]; then
    if ! "${DC[@]}" ps --status running -q backup 2>/dev/null | grep -q .; then
        fail "the backup service is not running, so no pre-deploy backup can be taken; nothing changed"
    fi
    out="$("${DC[@]}" exec -T backup python -m app.backup now --kind pre_deploy </dev/null)" \
        || fail "the pre-deploy backup failed; nothing changed"
    PRE="$(sed -n 's/^تم النسخ: \([^ ]*\).*/\1/p' <<<"$out")"
    echo "deploy: pre-deploy backup $PRE"
else
    echo "deploy: first install (the app is not running): no pre-deploy backup"
fi

# --- 3. Update the code and start ------------------------------------------------------------------
OLD="$(git rev-parse --short HEAD 2>/dev/null || echo -)"
if [ "$E2E" = 1 ] && [ "${SIJIL_DEPLOY_NO_PULL:-}" = 1 ]; then
    echo "deploy: (local check) no git pull"
else
    git pull --ff-only
fi
NEW="$(git rev-parse --short HEAD 2>/dev/null || echo -)"

record() {  # record succeeded|failed
    "${DC[@]}" run --rm -T --no-deps backup record deploy "$PRE" --mode "$MODE" \
        --old-commit "$OLD" --new-commit "$NEW" --result "$1" </dev/null >/dev/null 2>&1 \
        || echo "deploy: (the deploy could not be recorded on the backup page)" >&2
}
rollback_help() {
    cat >&2 <<EOF
deploy: the new version ($NEW) did not start. To go back:
  1. git checkout $OLD
  2. scripts/deploy.sh
  3. only if the new version changed the data: scripts/restore.sh $PRE   (the pre_deploy backup)
  Logs: ${DC[*]} logs api
EOF
}

if ! APP_COMMIT="$NEW" "${DC[@]}" up -d --build --remove-orphans --wait </dev/null; then
    record failed
    rollback_help
    exit 8
fi

# --- 4. Health: inside the stack, then through NPM ---------------------------------------------------
if ! "${DC[@]}" exec -T api python -c \
    "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health', timeout=5)" </dev/null; then
    record failed
    rollback_help
    exit 8
fi

reachable=1
if [ "$PUBLIC_URL" != "-" ]; then
    reachable=0
    for _ in $(seq 1 20); do
        if curl -fsS --max-time 5 "$PUBLIC_URL/api/health" >/dev/null 2>&1; then reachable=1; break; fi
        sleep 3
    done
fi

# --- 5. Synthetic test accounts: staging only ---------------------------------------------------------
if [ "$MODE" = staging ]; then
    echo "deploy: seed-demo (staging)"
    "${DC[@]}" exec -T api python -m app.cli seed-demo </dev/null
fi

# --- 6. Record ---------------------------------------------------------------------------------------
record succeeded
if [ "$reachable" -ne 1 ]; then
    echo "deploy: the stack is running, but $PUBLIC_URL/api/health is not reachable." >&2
    echo "  Check the Proxy Host in Nginx Proxy Manager (deploy/server.md, step 5)." >&2
    exit 2
fi
echo "deploy: OK — $MODE ($NEW) is up${PUBLIC_URL:+ at $PUBLIC_URL}."
