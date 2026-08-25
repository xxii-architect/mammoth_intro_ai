#!/usr/bin/env bash
# scripts/check-browser-mcp.sh
# Quick compatibility smoke check for the Playwright MCP bridge.
# Usage: bash scripts/check-browser-mcp.sh

set -euo pipefail

echo "Checking Playwright MCP CLI compatibility..."

if ! npx --yes @playwright/mcp@latest --help >/dev/null 2>&1; then
  echo "Playwright MCP CLI did not start correctly. Ensure Node.js + npx are installed." >&2
  exit 1
fi

if ! npx --yes playwright show-browsers 2>/dev/null | grep -q chromium; then
  echo "Chromium is not installed yet. The launcher will install it automatically when you run bash scripts/start-browser-mcp.sh."
fi

echo "Playwright MCP CLI is available and compatible."
echo "You can now run: bash scripts/start-browser-mcp.sh"
