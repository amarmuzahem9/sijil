#!/usr/bin/env bash
# Run the Playwright e2e suite against an isolated, freshly created stack.
# The stack and its volumes are always removed afterwards, so every run starts from the same state.
set -euo pipefail
cd "$(dirname "$0")/.."

DC=(docker compose -p sijil-e2e -f docker-compose.yml -f docker-compose.e2e.yml)

cleanup() { "${DC[@]}" --profile e2e down -v --remove-orphans >/dev/null 2>&1 || true; }
trap cleanup EXIT

cleanup
"${DC[@]}" up -d --build --wait db api web proxy
# A throwaway backup key for this stack (feature 016): its passphrase is random and forgotten.
E2E_BACKUP_RECIPIENT="$(head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n' \
    | "${DC[@]}" run --rm -T --no-deps backup init-key --passphrase-stdin \
    | sed -n 's/^BACKUP_AGE_RECIPIENT=//p' | tr -d '\r')"
export E2E_BACKUP_RECIPIENT
"${DC[@]}" up -d --wait backup
"${DC[@]}" exec -T api python -m app.cli seed-demo --e2e
# Last month's links for commissions.spec.ts (feature 017): the browser has no test clock.
"${DC[@]}" exec -T api python -m tests.e2e_commission_seed
# Records of three sources for subscriber-file.spec.ts (feature 018).
"${DC[@]}" exec -T api python -m tests.e2e_subscriber_seed
"${DC[@]}" --profile e2e run --rm --build e2e "$@"
