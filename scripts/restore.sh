#!/usr/bin/env bash
# Restore Sijil from one backup: database and card images together (feature 016, FR-012–FR-014,
# research R7, deploy/backup.md). Run from the repository folder:
#
#   scripts/restore.sh [SNAPSHOT_ID] [--from-external]
#
# Without SNAPSHOT_ID the latest snapshot is used. Steps:
#   1. show the snapshot and what will be lost, and ask you to type its date;
#   2. check it (complete, not damaged, not from a newer version) — nothing changes yet;
#   3. take a «pre_restore» backup of the current state;
#   4. ask the passphrase, decrypt and check every image into a staging volume;
#   5. stop api and backup, recreate the database, replace the images, start again, check health;
#   6. record the restore (backup page + audit log).
set -euo pipefail
cd "$(dirname "$0")/.."
# Git Bash on Windows rewrites /data/... arguments into Windows paths; Linux ignores this.
export MSYS_NO_PATHCONV=1

fail() { echo "restore: $*" >&2; exit "${2:-7}"; }
env_value() { [ -f .env ] && grep -E "^$1=" .env | tail -n1 | cut -d= -f2- | tr -d '\r' || true; }

if [ -n "${SIJIL_COMPOSE:-}" ]; then
    # shellcheck disable=SC2206
    DC=(docker compose $SIJIL_COMPOSE)
else
    case "$(env_value APP_ENV)" in
        staging|production) DC=(docker compose -f docker-compose.yml -f docker-compose.staging.yml) ;;
        *) DC=(docker compose) ;;
    esac
fi
P="${COMPOSE_PROJECT_NAME:-sijil}"

SID=""
EXTERNAL=0
FROM_STDIN=0
YES_FOR_TEST=0
for arg in "$@"; do
    case "$arg" in
        --from-external) EXTERNAL=1 ;;
        --passphrase-stdin) FROM_STDIN=1 ;;
        --yes-for-test) YES_FOR_TEST=1 ;;
        -*) fail "unknown option $arg" 2 ;;
        *) SID="$arg" ;;
    esac
done
if [ "$YES_FOR_TEST" = 1 ] && [ "${SIJIL_E2E:-}" != 1 ]; then
    fail "--yes-for-test is only for scripts/backup-e2e.sh" 2
fi
# Read the passphrase line before any docker command: `docker compose run/exec -T` would
# otherwise read this script's stdin.
PASS=""
if [ "$FROM_STDIN" = 1 ]; then IFS= read -r PASS; fi

# Where the snapshot is read from: the server's backup folder, or the external drive.
SRC=()
if [ "$EXTERNAL" = 1 ]; then
    EXT="$(env_value BACKUP_EXTERNAL_DIR)"
    [ -n "$EXT" ] || fail "BACKUP_EXTERNAL_DIR is not set in .env"
    [ -f "$EXT/.sijil-external" ] || fail "the external drive is not mounted at $EXT"
    SRC=(-v "$EXT:/external:ro")
    SOURCE=(--source /external)
else
    SOURCE=()
fi
backup_cmd() { "${DC[@]}" run --rm -T --no-deps "${SRC[@]}" backup "$@" </dev/null; }

[ -n "$SID" ] || SID="$(backup_cmd latest "${SOURCE[@]}" | tr -d '\r')"
[ -n "$SID" ] || fail "no snapshot found"

# --- 1. what will be restored, and what will be lost ------------------------------------------
SHOWN="$(backup_cmd show "$SID" "${SOURCE[@]}")" || fail "snapshot $SID cannot be read"
echo "$SHOWN" | grep -v '^DATE='
DATE="$(echo "$SHOWN" | sed -n 's/^DATE=//p' | tr -d '\r')"
cat <<EOF

تحذير: كل ما حدث بعد هذه النسخة يضيع: الطلبات والقرارات والربط والاستيرادات بعد وقتها،
وأي «حذف مشترك» بعدها يرجع (البيانات الممسوحة تعود كما كانت في النسخة).
قبل الاسترجاع تؤخذ نسخة «pre_restore» من الوضع الحالي، فيمكن الرجوع إليه.

EOF
if [ "$YES_FOR_TEST" != 1 ]; then
    read -r -p "للتأكيد اكتب تاريخ النسخة ($DATE): " typed </dev/tty
    [ "$typed" = "$DATE" ] || fail "التاريخ غير مطابق، لم يتغيّر شيء" 7
fi

# --- 2. check before touching anything -----------------------------------------------------------
backup_cmd check "$SID" "${SOURCE[@]}" || fail "the snapshot is damaged or from a newer version; nothing changed"

# --- 3. a backup of the current state ------------------------------------------------------------
PRE_OUT="$("${DC[@]}" exec -T backup python -m app.backup now --kind pre_restore </dev/null)" \
    || fail "the pre_restore backup failed; nothing changed"
PRE="$(echo "$PRE_OUT" | sed -n 's/^تم النسخ: \([^ ]*\).*/\1/p')"
echo "نسخة قبل الاسترجاع: $PRE"

# --- 4–5. passphrase, stage, stop, restore, swap ----------------------------------------------------
STAGING="${P}_restore_staging"
docker volume rm "$STAGING" >/dev/null 2>&1 || true
docker volume create "$STAGING" >/dev/null

"${DC[@]}" stop api backup >/dev/null
restore_args=(restore-into "$SID" "${SOURCE[@]}" --staging /data/restore-staging --uploads /data/live-uploads)
run_args=(run --rm --no-deps "${SRC[@]}" -v "$STAGING:/data/restore-staging" -v "${P}_uploads:/data/live-uploads")
status=0
if [ "$FROM_STDIN" = 1 ]; then
    printf '%s\n' "$PASS" | "${DC[@]}" "${run_args[@]}" -T backup "${restore_args[@]}" --passphrase-stdin || status=$?
else
    "${DC[@]}" "${run_args[@]}" backup "${restore_args[@]}" || status=$?
fi
docker volume rm "$STAGING" >/dev/null 2>&1 || true

"${DC[@]}" up -d --wait api backup >/dev/null || fail "the app did not start; see: ${DC[*]} logs api" 1
if [ "$status" -ne 0 ]; then
    echo "restore: refused (nothing restored)." >&2
    echo "  If the database was already recreated, restore the state before: scripts/restore.sh $PRE" >&2
    exit 7
fi

# --- 6. record ---------------------------------------------------------------------------------
"${DC[@]}" exec -T backup python -m app.backup record restore "$SID" --pre-restore "$PRE" </dev/null
echo "restore: OK — $SID restored. The state before it is $PRE."
