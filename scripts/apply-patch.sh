#!/usr/bin/env bash
# scripts/apply-patch.sh
# One-word helper to apply a Mammoth Mind patch with git am --3way.
# Cleans up automatically if the patch does not apply.
# Usage: bash scripts/apply-patch.sh path/to/change.patch

set -euo pipefail

usage() {
  echo "Usage: bash scripts/apply-patch.sh <patch-file>" >&2
  echo "Applies a Mammoth Mind patch via 'git am --3way' with a safe abort on failure." >&2
}

if [[ $# -ne 1 ]]; then
  usage
  exit 2
fi

PATCH_FILE="$1"

if [[ ! -f "$PATCH_FILE" ]]; then
  echo "Patch file not found: $PATCH_FILE" >&2
  exit 1
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Not inside a git repository. Run this from your repo root." >&2
  exit 1
fi

if [[ -n "$(git status --porcelain)" ]]; then
  echo "Working tree has uncommitted changes. Commit or stash them first." >&2
  exit 1
fi

echo "Applying $PATCH_FILE with git am --3way ..."

if git am --3way "$PATCH_FILE"; then
  echo "Applied successfully."
  echo "Undo it with: git reset --hard HEAD~1"
else
  echo "git am failed - aborting to restore a clean state (git am --abort)." >&2
  git am --abort || true
  exit 1
fi