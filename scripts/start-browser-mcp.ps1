# scripts/start-browser-mcp.ps1
# Starts the Playwright MCP browser bridge for MammothOS (Windows).
# Usage: .\scripts\start-browser-mcp.ps1

$profileDir = Join-Path (Get-Location) 'tmp\mammothos-browser-profile'
New-Item -ItemType Directory -Force -Path $profileDir | Out-Null

Write-Host 'MammothOS - Browser MCP starting'
Write-Host "  Profile: $profileDir"
Write-Host '  Browser: chromium (headed)'
Write-Host ''
Write-Host '  First run tip: if a login page appears, sign in and close the auth flow.'
Write-Host '  MammothOS will resume automatically once auth is complete.'
Write-Host ''

# Install Chromium if not already present (filesystem check — fast, no network roundtrip)
$msPlaywrightDir = Join-Path $env:LOCALAPPDATA 'ms-playwright'
$chromiumInstalled = Test-Path (Join-Path $msPlaywrightDir 'chromium*\chrome-win64\chrome.exe')
if (-not $chromiumInstalled) {
    Write-Host 'Installing Playwright Chromium (first time only)...'
    npx --yes playwright install chromium
    if ($LASTEXITCODE -ne 0) {
        Write-Error 'Playwright Chromium install failed. Ensure Node.js is installed and try again.'
        exit 1
    }
} else {
    Write-Host 'Chromium already installed — skipping download.'
}

$mcpArgs = @(
    '--yes'
    '@playwright/mcp@latest'
    '--user-data-dir'
    $profileDir
    '--browser'
    'chromium'
)

& npx @mcpArgs
