#!/usr/bin/env bash
# Publish the ocr/ folder to its public copy (AGPL-3.0, specs/006 FR-022, research R12).
#
# Run it before every deployment that changes ocr/. It copies ocr/ (and nothing else from this
# repository) into the public repository and pushes one commit that names the Sijil commit it
# came from. Needs `gh` signed in to the account that owns the public copy.
#
#   scripts/publish-ocr.sh [owner/repo]        # default: amarmuzahem9/sijil-ocr
set -euo pipefail

REPO="${1:-amarmuzahem9/sijil-ocr}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SOURCE_COMMIT="$(git -C "$ROOT" rev-parse --short HEAD)"

if [ -n "$(git -C "$ROOT" status --porcelain -- ocr)" ]; then
  echo "ocr/ has uncommitted changes; commit them first." >&2
  exit 1
fi

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

gh repo clone "$REPO" "$WORK/public" -- --quiet
# Replace everything but .git with the committed content of ocr/.
find "$WORK/public" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
git -C "$ROOT" archive HEAD ocr | tar -x -C "$WORK"
cp -a "$WORK/ocr/." "$WORK/public/"

cd "$WORK/public"
git add -A
if git diff --cached --quiet; then
  echo "The public copy is already up to date."
  exit 0
fi
git commit -q -m "Update from Sijil ${SOURCE_COMMIT}"
git push -q origin HEAD
echo "Published ocr/ from ${SOURCE_COMMIT} to https://github.com/${REPO}"
