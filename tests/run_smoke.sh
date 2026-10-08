#!/usr/bin/env bash
# Build the extension and run the headless smoke test against it, using a
# throwaway Blender user-resources dir so your real config is untouched.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BLENDER="${BLENDER:-/Applications/Blender.app/Contents/MacOS/Blender}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

"$BLENDER" --factory-startup --command extension build \
    --source-dir "$ROOT/sticky_notes" --output-dir "$WORK" >/dev/null
ZIP="$(ls "$WORK"/*.zip)"

BLENDER_USER_RESOURCES="$WORK/user" "$BLENDER" -b --factory-startup \
    --python "$ROOT/tests/smoke_blender.py" -- "$ZIP" "$WORK"
