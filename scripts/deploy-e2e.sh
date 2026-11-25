#!/usr/bin/env bash
# Checks of scripts/deploy.sh (feature 016, T062). LOCAL MACHINE ONLY — never on the server.
# A throwaway project `sijil-dp-e2e` with its own env file, a local stand-in for the Nginx Proxy
# Manager network, a temp backup folder with a throwaway key, synthetic accounts only, no git pull
# and no public URL. Everything is removed at the end.
#
#   bash scripts/deploy-e2e.sh
set -euo pipefail
cd "$(dirname "$0")/.."
export MSYS_NO_PATHCONV=1

if [ -d /opt/sijil ] || [ "${SIJIL_SERVER:-}" = "1" ]; then
    echo "deploy-e2e: refusing to run on the server (owner rule: tests on the local machine only)" >&2
    exit 1
fi

P=sijil-dp-e2e
NET="$P-npm"
WORK="$(mktemp -d)"
if command -v cygpath >/dev/null 2>&1; then WORK="$(cygpath -m "$WORK")"; fi
BK="$WORK/backups"
mkdir -p "$BK"
ENVF="$WORK/server.env"
rand() { head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n'; }
PG="$(rand)"
PASS="deploy-e2e-throwaway-$(rand)"

write_env() {  # write_env MODE [extra lines…]
    local mode="$1"; shift
    cat > "$ENVF" <<EOF
APP_ENV=$mode
NPM_NETWORK=$NET
POSTGRES_DB=sijil
POSTGRES_USER=sijil
POSTGRES_PASSWORD=$PG
DATABASE_URL=postgresql+psycopg://sijil:$PG@db:5432/sijil
JWT_SECRET=$JWT
COOKIE_SECURE=true
SUPERADMIN_PHONE=07700000000
SUPERADMIN_NAME=أدمن تجربة النشر
SUPERADMIN_PASSWORD=$ADMIN_PW
DEMO_MARKETER_PASSWORD=$DEMO_PW
OCR_MODE=http
OTP_MODE=otpiq
OTPIQ_API_KEY=
DRIVE_MODE=google
BACKUP_DIR=$BK
BACKUP_NIGHTLY_AT=23:59
${RECIPIENT:+BACKUP_AGE_RECIPIENT=$RECIPIENT}
EOF
    local line
    for line in "$@"; do echo "$line" >> "$ENVF"; done
}
JWT="$(rand)$(rand)"
ADMIN_PW="$(rand)"
DEMO_PW="$(rand)"
RECIPIENT=""

export COMPOSE_PROJECT_NAME="$P"
export SIJIL_E2E=1
export SIJIL_DEPLOY_ENV="$ENVF"
export SIJIL_DEPLOY_NO_PULL=1
export SIJIL_DEPLOY_EXTRA_FILES="docker-compose.deploy-e2e.yml"
export PUBLIC_URL="-"
DC=(docker compose --env-file "$ENVF" -f docker-compose.yml -f docker-compose.server.yml
    -f docker-compose.deploy-e2e.yml)
export SIJIL_ENV_FILE="$ENVF"

ok=0
failed=0
pass() { echo "  ✔ $*"; ok=$((ok + 1)); }
bad() { echo "  ✘ $*" >&2; failed=$((failed + 1)); }

cleanup() {
    "${DC[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
    docker network rm "$NET" >/dev/null 2>&1 || true
    rm -rf "$WORK"
}
trap cleanup EXIT
docker network create "$NET" >/dev/null
# `run` (init-key below) uses the image as built: build it from this working tree first.
write_env staging
"${DC[@]}" build api backup >/dev/null

deploy() { bash scripts/deploy.sh >"$WORK/out.txt" 2>&1; }
expect_refused() {  # expect_refused "why" — exit 1 and no container started
    local code=0
    deploy || code=$?
    if [ "$code" = 1 ] && [ -z "$("${DC[@]}" ps -q 2>/dev/null)" ]; then
        pass "refused: $1"
    else
        bad "not refused (exit $code): $1"; tail -5 "$WORK/out.txt" >&2
    fi
}

echo "== 1. pre-flight refusals (nothing changes)"
write_env staging "JWT_SECRET=change-me"
expect_refused "a value left at change-me"
write_env staging
expect_refused "BACKUP_AGE_RECIPIENT not set / no key.age"

# The operator's first step on a new server: create the key (deploy/backup.md).
RECIPIENT="$(printf '%s\n' "$PASS" | "${DC[@]}" run --rm -T --no-deps backup init-key --passphrase-stdin \
    | sed -n 's/^BACKUP_AGE_RECIPIENT=//p' | tr -d '\r')"
[ -n "$RECIPIENT" ] && pass "init-key on the server folder" || bad "init-key failed"
"${DC[@]}" down -v --remove-orphans >/dev/null 2>&1 || true

for fake in "OCR_MODE=fake" "OTP_MODE=fake" "DRIVE_MODE=fake" "OTP_FAKE_CODE=123456"; do
    write_env production "$fake"
    expect_refused "production with $fake"
done

echo "== 2. first staging deploy"
write_env staging
if deploy; then pass "first staging deploy"; else bad "first staging deploy failed"; tail -20 "$WORK/out.txt" >&2; fi
grep -q "first install" "$WORK/out.txt" && pass "first install: no pre-deploy backup, said so" \
    || bad "no first-install note"
"${DC[@]}" exec -T db psql -U sijil -d sijil -At -c \
    "SELECT is_active FROM users WHERE phone = '07700000001'" | grep -qx t \
    && pass "staging: demo account created" || bad "staging: no demo account"
[ -n "$(ls "$BK/history" 2>/dev/null | grep -- '-deploy.json')" ] && pass "deploy recorded" \
    || bad "deploy not recorded"
"${DC[@]}" config --format json | grep -q '"published"' && bad "a host port is published" \
    || pass "no host port published"
grep -q docker.sock <("${DC[@]}" config) && bad "a Docker socket is mounted" || pass "no Docker socket"

echo "== 3. second staging deploy takes a pre-deploy backup"
if deploy; then pass "second staging deploy"; else bad "second staging deploy failed"; tail -20 "$WORK/out.txt" >&2; fi
ls "$BK/snapshots" | grep -q -- '-pre_deploy$' && pass "pre_deploy snapshot taken" \
    || bad "no pre_deploy snapshot"

echo "== 4. a failed pre-deploy backup stops before anything changes"
api_before="$("${DC[@]}" ps -q api)"
"${DC[@]}" stop backup >/dev/null 2>&1
code=0; deploy || code=$?
[ "$code" = 1 ] && pass "deploy stopped (exit 1)" || bad "deploy went on (exit $code)"
[ "$("${DC[@]}" ps -q api)" = "$api_before" ] && pass "the running api was not touched" \
    || bad "the api container changed"
"${DC[@]}" start backup >/dev/null 2>&1

echo "== 5. production"
write_env production
code=0; deploy || code=$?
[ "$code" = 1 ] && grep -q "go-live" "$WORK/out.txt" && pass "production refused while demo accounts are active" \
    || bad "production not refused with active demo accounts (exit $code)"
"${DC[@]}" exec -T api python -m app.cli go-live >/dev/null && pass "go-live" || bad "go-live failed"
if deploy; then pass "production deploy"; else bad "production deploy failed"; tail -20 "$WORK/out.txt" >&2; fi
grep -q "seed-demo" "$WORK/out.txt" && bad "seed-demo ran in production" || pass "no seed-demo in production"
"${DC[@]}" exec -T db psql -U sijil -d sijil -At -c \
    "SELECT is_active FROM users WHERE phone = '07700000001'" | grep -qx f \
    && pass "the demo account stays inactive" || bad "the demo account came back"
grep -l '"mode": "production"' "$BK"/history/*-deploy.json >/dev/null 2>&1 \
    && pass "production deploy recorded" || bad "production deploy not recorded"

echo "== 6. a new version that does not start"
write_env production "JWT_SECRET=too-short"
code=0; deploy || code=$?
[ "$code" = 8 ] && pass "health failure reported (exit 8)" || bad "health failure not reported (exit $code)"
grep -q "pre_deploy" "$WORK/out.txt" && grep -q "git checkout" "$WORK/out.txt" \
    && pass "rollback steps printed with the pre-deploy snapshot" || bad "no rollback steps"

echo "== result: $ok passed, $failed failed"
[ "$failed" -eq 0 ]
