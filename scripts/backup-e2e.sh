#!/usr/bin/env bash
# End-to-end check of backup → restore → drill (feature 016, T033). LOCAL MACHINE ONLY.
# It builds a throwaway compose project `sijil-bk-e2e` with synthetic data, a throwaway key and
# a throwaway passphrase, and removes everything (containers and volumes) at the end.
#
#   bash scripts/backup-e2e.sh
set -euo pipefail
cd "$(dirname "$0")/.."
# Git Bash on Windows rewrites /data/... arguments into Windows paths; Linux ignores this.
export MSYS_NO_PATHCONV=1

if [ -d /opt/sijil ] || [ "${SIJIL_SERVER:-}" = "1" ]; then
    echo "backup-e2e: refusing to run on the server (owner rule: tests on the local machine only)" >&2
    exit 1
fi

P=sijil-bk-e2e
WORK="$(mktemp -d)"
# Docker Desktop on Windows needs a Windows path for host files (Git Bash only).
if command -v cygpath >/dev/null 2>&1; then WORK="$(cygpath -m "$WORK")"; fi
ENVF="$WORK/e2e.env"
PASS="e2e-throwaway-passphrase-$RANDOM$RANDOM"
rand() { head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n'; }
PG="$(rand)"
cat > "$ENVF" <<EOF
APP_ENV=development
POSTGRES_DB=sijil
POSTGRES_USER=sijil
POSTGRES_PASSWORD=$PG
DATABASE_URL=postgresql+psycopg://sijil:$PG@db:5432/sijil
JWT_SECRET=$(rand)
COOKIE_SECURE=true
SUPERADMIN_PHONE=07700000000
SUPERADMIN_NAME=أدمن تجربة النسخ
SUPERADMIN_PASSWORD=$(rand)
DEMO_MARKETER_PASSWORD=$(rand)
OCR_MODE=fake
OTP_MODE=fake
DRIVE_MODE=fake
BACKUP_NIGHTLY_AT=23:59
EOF

export COMPOSE_PROJECT_NAME="$P"
export SIJIL_ENV_FILE="$ENVF"
export SIJIL_COMPOSE="--env-file $ENVF -f docker-compose.yml -f docker-compose.override.yml"
# shellcheck disable=SC2206
DC=(docker compose $SIJIL_COMPOSE)

ok=0
failed=0
pass() { echo "  ✔ $*"; ok=$((ok + 1)); }
bad() { echo "  ✘ $*" >&2; failed=$((failed + 1)); }

cleanup() {
    "${DC[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
    SIJIL_API_IMAGE=x SIJIL_BACKUP_IMAGE=x SIJIL_DRILL_ENV="$ENVF" POSTGRES_PASSWORD=x \
        docker compose -p "$P-drill" -f docker-compose.drill.yml --profile tools \
        down -v --remove-orphans >/dev/null 2>&1 || true
    docker volume rm "${P}_restore_staging" >/dev/null 2>&1 || true
    rm -rf "$WORK"
}
trap cleanup EXIT

state() {
    "${DC[@]}" exec -T db psql -U sijil -d sijil -At -c \
        "SELECT (SELECT count(*) FROM requests), (SELECT count(*) FROM requests WHERE deleted_at IS NULL), (SELECT count(*) FROM legacy_subscribers), (SELECT count(*) FROM sas_subscribers)"
    "${DC[@]}" exec -T api sh -c 'cd /data/uploads && sha256sum -- *.jpg 2>/dev/null | sort'
}

echo "== 1. throwaway stack"
"${DC[@]}" build api backup >/dev/null
"${DC[@]}" up -d --wait db api >/dev/null
printf '%s\n' "$PASS" | "${DC[@]}" run --rm -T --no-deps backup init-key --passphrase-stdin \
    | sed -n 's/^\(BACKUP_AGE_RECIPIENT=.*\)$/\1/p' >> "$ENVF"
grep -q '^BACKUP_AGE_RECIPIENT=age1' "$ENVF" && pass "key.age created" || bad "key.age not created"
"${DC[@]}" up -d --wait backup >/dev/null
"${DC[@]}" exec -T api python -m tests.e2e_backup_seed seed
# SC-003 timing: SIJIL_E2E_BULK_MB=1000 adds about 1 GB of files before the backup.
if [ -n "${SIJIL_E2E_BULK_MB:-}" ]; then
    "${DC[@]}" exec -T api python -m tests.e2e_backup_seed bulk "$SIJIL_E2E_BULK_MB"
fi

echo "== 2. backup"
bash scripts/backup.sh now >/dev/null && pass "manual backup" || bad "manual backup failed"
SID="$("${DC[@]}" exec -T backup python -m app.backup latest | tr -d '\r')"
state > "$WORK/before.txt"

echo "== 3. change the data, then restore"
"${DC[@]}" exec -T api python -m tests.e2e_backup_seed mutate
state > "$WORK/changed.txt"
cmp -s "$WORK/before.txt" "$WORK/changed.txt" && bad "the change did not change anything" || pass "data changed"
started=$(date +%s)
if printf '%s\n' "$PASS" | SIJIL_E2E=1 bash scripts/restore.sh "$SID" --yes-for-test --passphrase-stdin; then
    pass "restore ran in $(( $(date +%s) - started )) s"
else
    bad "restore failed"
fi
state > "$WORK/after.txt"
cmp -s "$WORK/before.txt" "$WORK/after.txt" && pass "counts and image hashes equal the snapshot" \
    || { bad "restored state differs"; diff "$WORK/before.txt" "$WORK/after.txt" >&2 || true; }
bash scripts/backup.sh list | grep -q -- '-pre_restore' && pass "pre_restore snapshot exists" \
    || bad "no pre_restore snapshot"
"${DC[@]}" exec -T db psql -U sijil -d sijil -At -c \
    "SELECT count(*) FROM audit_log WHERE action = 'backup.restore'" | grep -qx 1 \
    && pass "restore audited" || bad "restore not audited"

echo "== 4. drill"
if printf '%s\n' "$PASS" | bash scripts/backup.sh drill "$SID" --passphrase-stdin; then
    pass "drill passed"
else
    bad "drill failed on a good snapshot"
fi

echo "== 5. a damaged object"
"${DC[@]}" exec -T backup python - "$SID" <<'PY'
import sys
from app.backup.retention import read_manifest
from app.backup.store import BackupStore
store = BackupStore("/data/backups")
obj = store.image_path(read_manifest(store, sys.argv[1]).images[0].name)
data = bytearray(obj.read_bytes()); data[-1] ^= 0xFF; obj.write_bytes(bytes(data))
PY
state > "$WORK/live.txt"
if printf '%s\n' "$PASS" | bash scripts/backup.sh drill "$SID" --passphrase-stdin; then
    bad "drill passed on a damaged snapshot"
else
    pass "drill failed on a damaged snapshot"
fi
if printf '%s\n' "$PASS" | SIJIL_E2E=1 bash scripts/restore.sh "$SID" --yes-for-test --passphrase-stdin; then
    bad "restore accepted a damaged snapshot"
else
    pass "restore refused a damaged snapshot"
fi
state > "$WORK/live2.txt"
cmp -s "$WORK/live.txt" "$WORK/live2.txt" && pass "live data unchanged after the refusal" \
    || bad "live data changed after a refused restore"

echo "== 6. nothing left by the drills"
if docker volume ls --format "{{.Name}}" | grep -q "^$P-drill_"; then
    bad "a drill volume was left behind"
else
    pass "no drill volume left"
fi

echo "== result: $ok passed, $failed failed"
[ "$failed" -eq 0 ]
