$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$uiDir = Join-Path $repoRoot "ui\mad-architecht-command-center"
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $uiDir)) {
    throw "UI directory not found: $uiDir"
}

function Test-PortOpen {
    param([int]$Port)
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $iar = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
        $success = $iar.AsyncWaitHandle.WaitOne(500, $false)
        if ($success -and $client.Connected) {
            $client.EndConnect($iar)
            $client.Close()
            return $true
        }
        $client.Close()
        return $false
    } catch {
        return $false
    }
}

function Test-BackendHealthy {
    try {
        $response = Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/api/entitlements" -TimeoutSec 3
        return ($response.status -eq "ok")
    } catch {
        return $false
    }
}

function Get-ListenerProcess {
    param([int]$Port)
    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $conn) {
        return $null
    }
    return Get-CimInstance Win32_Process -Filter "ProcessId = $($conn.OwningProcess)" -ErrorAction SilentlyContinue
}

if (Test-Path $venvPython) {
    $pythonPath = $venvPython
} else {
    $pythonPath = "python"
}

try {
    & $pythonPath --version | Out-Null
} catch {
    throw "Python is not available. Install Python or create .venv first."
}

try {
    & cmd /c "npm --version" | Out-Null
} catch {
    throw "npm is not available. Install Node.js first."
}

$startedBackend = $false
$startedFrontend = $false

if (-not (Test-PortOpen -Port 8000)) {
    $backendCommand = @(
        "Set-Location '$repoRoot'",
        "& '$pythonPath' -m uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload"
    ) -join "; "
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCommand | Out-Null
    $startedBackend = $true
} else {
    if (Test-BackendHealthy) {
        Write-Host "Backend is already running and healthy on port 8000."
    } else {
        $listener = Get-ListenerProcess -Port 8000
        Write-Host "Port 8000 is in use, but MammothOS backend health check failed."
        if ($listener) {
            Write-Host "Listener PID: $($listener.ProcessId)"
            Write-Host "Listener command: $($listener.CommandLine)"
        }
        Write-Host "Stop that process, then re-run start-mammothos.bat."
    }
}

if (-not (Test-PortOpen -Port 5173)) {
    $frontendCommand = @(
        "Set-Location '$uiDir'",
        "npx vite --host 0.0.0.0 --port 5173"
    ) -join "; "
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCommand | Out-Null
    $startedFrontend = $true
} else {
    Write-Host "Frontend already appears to be running on port 5173."
}

if ($startedBackend -or $startedFrontend) {
    Write-Host "Started MammothOS services in separate terminal windows."
} else {
    Write-Host "No new service windows were started."
}
Write-Host "UI: http://localhost:5173"
Write-Host "API: http://localhost:8000/api/health"
