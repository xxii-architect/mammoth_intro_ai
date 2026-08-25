# scripts/start-browser-mcp.ps1
# Starts the Playwright MCP browser bridge for MammothOS (Windows).
# Usage: .\scripts\start-browser-mcp.ps1

$profileDir = Join-Path (Get-Location) "tmp\mammothos-browser-profile"
New-Item -ItemType Directory -Force -Path $profileDir | Out-Null

Write-Host "MammothOS — Browser MCP starting"
Write-Host "  Profile: $profileDir"
Write-Host "  Browser: chromium (headed)"
Write-Host ""
Write-Host "  First run tip: if a login page appears, sign in and close the auth flow."
Write-Host "  MammothOS will resume automatically once auth is complete."
Write-Host ""

# Install Chromium if needed
try {
    $null = npx playwright show-browsers 2>&1
} catch {
    Write-Host "Installing Playwright Chromium..."
    npx playwright install chromium
}

npx @playwright/mcp@latest `
    --user-data-dir "$profileDir" `
    --browser chromium `
    --viewport "1280,800"
