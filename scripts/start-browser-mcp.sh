#!/usr/bin/env bash
# scripts/start-browser-mcp.sh
# Starts the Playwright MCP browser bridge for MammothOS.
# First run: browser opens headed so you can complete auth. Profile is then persisted.
# Usage: bash scripts/start-browser-mcp.sh

set -euo pipefail

PROFILE_DIR="$(pwd)/tmp/mammothos-browser-profile"
mkdir -p "$PROFILE_DIR"

MODE="${MCP_BROWSER_MODE:-headed}"
BROWSER_EXECUTABLE_PATH="${MCP_BROWSER_EXECUTABLE_PATH:-}"

find_system_browser() {
  if [[ -n "$BROWSER_EXECUTABLE_PATH" ]]; then
    echo "$BROWSER_EXECUTABLE_PATH"
    return 0
  fi

  local candidate
  for candidate in chromium chromium-browser google-chrome google-chrome-stable msedge; do
    if command -v "$candidate" >/dev/null 2>&1; then
      command -v "$candidate"
      return 0
    fi
  done

  return 1
}

ensure_playwright_browser() {
  if ! npx --yes playwright show-browsers 2>/dev/null | grep -q chromium; then
    echo "Installing Playwright Chromium..."
    npx playwright install chromium
  fi
}

MODE_LABEL="$MODE"
HEADLESS_ARGS=()
if [[ "$MODE" == "system" || "$MODE" == "system-headless" || "$MODE" == "headless" ]]; then
  BROWSER_EXECUTABLE_PATH="$(find_system_browser || true)"
  if [[ -z "$BROWSER_EXECUTABLE_PATH" ]]; then
    echo "No system browser executable found."
    echo "Set MCP_BROWSER_EXECUTABLE_PATH or install chromium/google-chrome, then re-run with MCP_BROWSER_MODE=system-headless."
    exit 1
  fi
  MODE_LABEL="system-headless"
  HEADLESS_ARGS=(--browser chrome --executable-path "$BROWSER_EXECUTABLE_PATH" --headless --no-sandbox)
else
  ensure_playwright_browser
  HEADLESS_ARGS=(--browser chromium)
fi

echo "MammothOS - Browser MCP starting"
echo "  Profile: $PROFILE_DIR"
echo "  Mode: $MODE_LABEL"
echo "  Browser: ${BROWSER_EXECUTABLE_PATH:-chromium} ${HEADLESS_ARGS[*]}"
echo ""
if [[ "$MODE_LABEL" == "system-headless" ]]; then
  echo "  Fallback tip: using the system browser executable for non-interactive audits."
else
  echo "  First run tip: if a login page appears, sign in and close the auth flow."
  echo "  MammothOS will resume automatically once auth is complete."
fi
echo ""

exec npx --yes @playwright/mcp@latest \
  --user-data-dir "$PROFILE_DIR" \
  "${HEADLESS_ARGS[@]}"
