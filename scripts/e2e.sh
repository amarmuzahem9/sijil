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
"${DC[@]}" exec -T api python -m app.cli seed-demo --e2e
"${DC[@]}" --profile e2e run --rm --build e2e "$@"
