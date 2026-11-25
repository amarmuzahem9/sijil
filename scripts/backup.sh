#!/usr/bin/env bash
# Sijil backups — operator commands (feature 016, contracts/cli.md, deploy/backup.md).
# Run from the repository folder:   scripts/backup.sh <command>
#
#   init-key [--dev]          once: create key.age and print BACKUP_AGE_RECIPIENT for .env
#                             (--dev: local machine only, a generated passphrase printed once)
#   now                       one manual backup now
#   list                      the snapshots on this machine
#   drill [SNAPSHOT_ID]       restore drill in an isolated throwaway stack (asks the passphrase)
#   status                    last backup, external copy, drill, and the warnings
#
# Restore: scripts/restore.sh. The weekly external copy comes with batch 5 of feature 016.
set -euo pipefail
cd "$(dirname "$0")/.."
# Git Bash on Windows rewrites /data/... arguments into Windows paths; Linux ignores this.
export MSYS_NO_PATHCONV=1

fail() { echo "backup: $*" >&2; exit "${2:-1}"; }
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

drill() {
    local sid="" from_stdin=0 external=0 arg
    for arg in "$@"; do
        case "$arg" in
            --passphrase-stdin) from_stdin=1 ;;
            --external) external=1 ;;
            -*) fail "unknown option $arg" 2 ;;
            *) sid="$arg" ;;
        esac
    done
    local src=() source=() label=server
    if [ "$external" = 1 ]; then
        local ext
        ext="$(env_value BACKUP_EXTERNAL_DIR)"
        [ -f "$ext/.sijil-external" ] || fail "the external drive is not mounted at '$ext'" 5
        src=(-v "$ext:/external:ro")
        source=(--source /external)
        label=external
    fi
    # Read the passphrase first: `docker compose run/exec -T` would read this script's stdin.
    local pass=""
    if [ "$from_stdin" = 1 ]; then IFS= read -r pass; fi
    live() { "${DC[@]}" run --rm -T --no-deps "${src[@]}" backup "$@" </dev/null; }
    [ -n "$sid" ] || sid="$(live latest "${source[@]}" | tr -d '\r')"
    [ -n "$sid" ] || fail "no snapshot found"


    # The drill's own throwaway secrets (never the server's .env).
    local work denv rand
    work="$(mktemp -d)"
    if command -v cygpath >/dev/null 2>&1; then work="$(cygpath -m "$work")"; fi
    denv="$work/drill.env"
    rand() { head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n'; }
    local pg
    pg="$(rand)"
    cat > "$denv" <<EOF
APP_ENV=staging
POSTGRES_PASSWORD=$pg
DATABASE_URL=postgresql+psycopg://sijil:$pg@db:5432/sijil
JWT_SECRET=$(rand)
COOKIE_SECURE=true
SUPERADMIN_PHONE=07700000000
SUPERADMIN_NAME=تجربة الاسترجاع
SUPERADMIN_PASSWORD=$(rand)
DEMO_MARKETER_PASSWORD=$(rand)
OCR_MODE=http
OTP_MODE=otpiq
OTPIQ_API_KEY=
DRIVE_MODE=google
BACKUP_DIR=/data/src
EOF
    export SIJIL_DRILL_ENV="$denv" SIJIL_API_IMAGE="${P}-api" SIJIL_BACKUP_IMAGE="${P}-backup"
    local drill=(docker compose -p "${P}-drill" -f docker-compose.drill.yml --env-file "$denv"
        --profile tools)
    # shellcheck disable=SC2064
    trap "${drill[*]} down -v --remove-orphans >/dev/null 2>&1; rm -rf '$work'" EXIT

    echo "تجربة الاسترجاع للنسخة $sid في نسخة معزولة بلا شبكة…"
    local code=0
    # Start from nothing: no volume left over from an earlier drill.
    "${drill[@]}" down -v --remove-orphans >/dev/null 2>&1 </dev/null || true
    "${drill[@]}" up -d --wait db >/dev/null </dev/null
    # The encrypted files only, streamed in; no volume is shared with the live stack. `files`
    # checks the snapshot first; pipefail makes its refusal stop the drill.
    if ! "${DC[@]}" run --rm -T --no-deps "${src[@]}" --entrypoint bash backup -o pipefail -c \
        "python -m app.backup files $sid ${source[*]} | tar -C ${source[1]:-/data/backups} -cf - -T -" \
        | "${drill[@]}" run --rm -T --no-deps --entrypoint sh restorer -c 'tar -xf - -C /data/src'
    then
        code=7
    fi

    local result=""
    if [ "$code" -ne 0 ]; then
        :
    elif [ "$from_stdin" = 1 ]; then
        printf '%s\n' "$pass" | "${drill[@]}" run --rm -T --no-deps restorer restore-into "$sid" \
            --staging /data/restore-staging --uploads /data/uploads --passphrase-stdin || code=$?
    else
        "${drill[@]}" run --rm --no-deps restorer restore-into "$sid" \
            --staging /data/restore-staging --uploads /data/uploads || code=$?
    fi
    if [ "$code" -eq 0 ]; then
        "${drill[@]}" up -d --wait api >/dev/null </dev/null || code=1
    fi
    # The copy must have no route out (no OTP, no notification, no Google).
    if [ "$code" -eq 0 ] && "${drill[@]}" exec -T api python -c \
        "import urllib.request; urllib.request.urlopen('https://www.google.com', timeout=5)" \
        >/dev/null 2>&1 </dev/null; then
        echo "backup: the drill copy can reach the internet — stopped" >&2
        code=1
    fi
    if [ "$code" -eq 0 ]; then
        result="$("${drill[@]}" run --rm -T --no-deps restorer verify-restored "$sid" \
            --uploads /data/uploads </dev/null | tail -n1)" || code=6
    else
        result="{\"passed\": false, \"reason\": \"restore_refused\", \"compared\": {}}"
        code=6
    fi
    printf '%s\n' "$result" | "${DC[@]}" exec -T backup python -m app.backup record drill "$sid" \
        --source-label "$label"
    if [ "$code" -eq 0 ]; then
        echo "تجربة الاسترجاع نجحت: $result"
    else
        echo "تجربة الاسترجاع فشلت: $result" >&2
    fi
    return "$code"
}

cmd="${1:-}"
shift || true
case "$cmd" in
    init-key)
        if [ "${1:-}" = "--dev" ]; then
            case "$(env_value APP_ENV)" in
                staging|production) fail "--dev is for a local machine only" ;;
            esac
            # A throwaway passphrase for local tests, never for real data.
            pass="dev-$("${DC[@]}" run --rm -T --no-deps --entrypoint python backup \
                -c 'import secrets; print(secrets.token_urlsafe(18))' | tr -d '\r')"
            printf '%s\n' "$pass" \
                | "${DC[@]}" run --rm -T --no-deps backup init-key --passphrase-stdin
            echo "كلمة سر التجربة المحلية (تظهر مرة واحدة): $pass"
        else
            # Interactive: age asks for the passphrase on this terminal (Enter = a generated one).
            "${DC[@]}" run --rm --no-deps backup init-key
        fi
        ;;
    now)
        "${DC[@]}" exec -T backup python -m app.backup now --kind manual
        ;;
    list)
        "${DC[@]}" exec -T backup python -m app.backup list
        ;;
    drill)
        drill "$@"
        ;;
    status)
        "${DC[@]}" exec -T backup python -m app.backup status
        ;;
    *)
        sed -n '2,13p' "$0" >&2
        exit 2
        ;;
esac
