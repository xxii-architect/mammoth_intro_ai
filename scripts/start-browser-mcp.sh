#!/usr/bin/env bash
# scripts/start-browser-mcp.sh
# Starts the Playwright MCP browser bridge for MammothOS.
# First run: browser opens headed so you can complete auth. Profile is then persisted.
# Usage: bash scripts/start-browser-mcp.sh

set -euo pipefail

PROFILE_DIR="$(pwd)/tmp/mammothos-browser-profile"
mkdir -p "$PROFILE_DIR"

echo "MammothOS — Browser MCP starting"
echo "  Profile: $PROFILE_DIR"
echo "  Browser: chromium (headed)"
echo ""
echo "  First run tip: if a login page appears, sign in and close the auth flow."
echo "  MammothOS will resume automatically once auth is complete."
echo ""

# Install Chromium once if needed
if ! npx --yes playwright show-browsers 2>/dev/null | grep -q chromium; then
  echo "Installing Playwright Chromium..."
  npx playwright install chromium
fi

exec npx @playwright/mcp@latest \
  --user-data-dir "$PROFILE_DIR" \
  --browser chromium \
  --viewport 1280,800
