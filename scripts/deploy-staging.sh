#!/usr/bin/env bash
# Kept for the habit and the old documents: scripts/deploy.sh now serves staging and production
# (the mode is APP_ENV in .env; feature 016). See deploy/server.md.
exec "$(dirname "$0")/deploy.sh" "$@"
