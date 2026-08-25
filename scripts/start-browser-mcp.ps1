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

# Install Chromium if needed
$browsers = npx --yes playwright show-browsers 2>$null
if (($LASTEXITCODE -ne 0) -or -not ($browsers | Select-String -SimpleMatch 'chromium')) {
    Write-Host 'Installing Playwright Chromium...'
    npx --yes playwright install chromium
    if ($LASTEXITCODE -ne 0) {
        Write-Error 'Playwright Chromium install failed. Run this script locally on your Windows machine (recommended) or install browser dependencies first.'
        exit 1
    }
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
