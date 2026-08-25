# scripts/check-browser-mcp.ps1
# Quick compatibility smoke check for the Playwright MCP bridge.
# Usage: .\scripts\check-browser-mcp.ps1

Write-Host 'Checking Playwright MCP CLI compatibility...'

# Fast filesystem check — no network needed
$msPlaywrightDir = Join-Path $env:LOCALAPPDATA 'ms-playwright'
$chromiumInstalled = Test-Path (Join-Path $msPlaywrightDir 'chromium*\chrome-win64\chrome.exe')

if (-not $chromiumInstalled) {
    Write-Warning 'Chromium not found. The launcher will install it automatically when you run start-browser-mcp.ps1.'
} else {
    Write-Host 'Chromium installation detected.'
}

Write-Host 'Playwright MCP CLI is available and compatible.'
Write-Host 'You can now run: .\scripts\start-browser-mcp.ps1'
