#!/usr/bin/env bash
# Sijil backups — operator commands (feature 016, contracts/cli.md, deploy/backup.md).
# Run from the repository folder:   scripts/backup.sh <command>
#
#   init-key [--dev]   once: create key.age and print BACKUP_AGE_RECIPIENT for .env
#                      (--dev: local machine only, a generated passphrase printed once)
#   now                one manual backup now
#   list               the snapshots on this machine
#
# Restore, drill and the weekly copy come with the next batches of feature 016.
set -euo pipefail
cd "$(dirname "$0")/.."

fail() { echo "backup: $*" >&2; exit 1; }
env_value() { [ -f .env ] && grep -E "^$1=" .env | tail -n1 | cut -d= -f2- | tr -d '\r' || true; }

case "$(env_value APP_ENV)" in
    staging|production) DC=(docker compose -f docker-compose.yml -f docker-compose.staging.yml) ;;
    *) DC=(docker compose) ;;
esac

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
    *)
        sed -n '2,10p' "$0" >&2
        exit 2
        ;;
esac
