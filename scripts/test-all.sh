#!/usr/bin/env bash
# Merge gate (constitution Principle VIII): every check must pass.
# Requires the dev stack to be running: docker compose up -d
set -euo pipefail
cd "$(dirname "$0")/.."

step() { printf '\n=== %s ===\n' "$1"; }

step "ruff (api)"
docker compose exec -T api ruff check .
docker compose exec -T api ruff format --check .

step "pytest (api)"
docker compose exec -T api pytest

step "eslint + typecheck + vitest (web)"
docker compose exec -T web npm run lint
docker compose exec -T web npm run typecheck
docker compose exec -T web npm test

step "Playwright e2e (isolated stack)"
scripts/e2e.sh

# Feature 016, local machine only (both refuse to run on the server).
step "backup → restore → drill → weekly copy (isolated stack)"
bash scripts/backup-e2e.sh

step "deploy script checks (isolated stack)"
bash scripts/deploy-e2e.sh

printf '\nAll checks passed.\n'
