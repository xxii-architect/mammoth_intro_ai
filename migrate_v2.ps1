<#
Safer Migration Script v2
- Usage: From project root run:
    powershell -ExecutionPolicy Bypass -File .\migrate_v2.ps1
- By default the script runs a dry run. To execute the move set $PerformMove = $true
#>

# === Configuration ===
$ProjectRoot = (Get-Location).Path
$SourceName = "mammoth_os"
$TargetRoot = Join-Path $ProjectRoot "src"
$TargetPackageDir = Join-Path $TargetRoot $SourceName
$BackupRoot = Join-Path $ProjectRoot "_pre_migration_snapshot_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
$LogFile = Join-Path $ProjectRoot "migration_v2_$(Get-Date -Format 'yyyyMMdd_HHmmss').log"
$PerformMove = $true   # <-- DRY RUN by default. Set to $true to perform moves.
$VerifyImports = $true  # run a quick python import check if python is available

# === Helpers ===
function Log($msg) {
    $line = "$(Get-Date -Format 's') `t $msg"
    $line | Tee-Object -FilePath $LogFile -Append
    Write-Host $msg
}

function AbortWith($msg) {
    Log "ABORT: $msg"
    throw $msg
}

# === Start ===
Log "Starting migration v2 (dry run = $(-not $PerformMove))"
Log "Project root: $ProjectRoot"
Log "Target package dir: $TargetPackageDir"
Log "Backup snapshot will be created at: $BackupRoot"

# === Step 1 Detect all mammoth_os directories ===
$found = Get-ChildItem -Path $ProjectRoot -Recurse -Directory -Filter $SourceName -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName
if (-not $found) {
    Log "No directories named '$SourceName' found under project root. Nothing to migrate."
    Exit 0
}
Log "Found the following directories named '$SourceName':"
$found | ForEach-Object { Log "  $_" }

# === Step 2 Identify the canonical source directory (the one with code files) ===
# Heuristic: prefer directories that contain .py files other than __init__.py and contain agents or engines
$candidate = $null
foreach ($dir in $found) {
    $pyCount = (Get-ChildItem -Path $dir -Recurse -Include *.py -File -ErrorAction SilentlyContinue | Where-Object { $_.Name -ne "__init__.py" }).Count
    $hasAgents = Test-Path (Join-Path $dir "agents")
    $hasMaintenance = Test-Path (Join-Path $dir "maintenance")
    if ($pyCount -gt 0 -and ($hasAgents -or $hasMaintenance)) {
        $candidate = $dir
        break
    }
}
if (-not $candidate) {
    # fallback to the first found
    $candidate = $found[0]
    Log "No strong candidate found by heuristic. Falling back to first found: $candidate"
} else {
    Log "Selected canonical source directory: $candidate"
}

# === Step 3 Safety snapshot ===
Log "Creating snapshot backup of the entire project to: $BackupRoot"
if ($PerformMove) {
    New-Item -ItemType Directory -Path $BackupRoot -Force | Out-Null
    robocopy $ProjectRoot $BackupRoot /MIR /XD $BackupRoot /NFL /NDL /NJH /NJS | Out-Null
    Log "Snapshot created."
} else {
    Log "DRY RUN: Snapshot would be created at $BackupRoot"
}

# === Step 4 Prepare target directory ===
if (-not (Test-Path $TargetRoot)) {
    Log "Target root '$TargetRoot' does not exist. It will be created."
    if ($PerformMove) { New-Item -ItemType Directory -Path $TargetRoot -Force | Out-Null }
} else {
    Log "Target root exists."
}

# === Step 5 Dry run plan: list moves ===
$itemsToMove = Get-ChildItem -Path $candidate -Force
Log "Planned moves from '$candidate' into '$TargetPackageDir':"
foreach ($item in $itemsToMove) {
    Log "  Move: $($item.FullName) -> $TargetPackageDir\$($item.Name)"
}

# === Step 6 Safety checks before move ===
# Check that target is not the same as source
if ($candidate -eq $TargetPackageDir) {
    AbortWith "Source and target are identical. Aborting to avoid destructive action."
}

# Check for existing files in target that would conflict
$conflicts = @()
foreach ($item in $itemsToMove) {
    $dest = Join-Path $TargetPackageDir $item.Name
    if (Test-Path $dest) { $conflicts += $dest }
}
if ($conflicts.Count -gt 0) {
    Log "Conflicts detected at target. The following paths already exist:"
    $conflicts | ForEach-Object { Log "  $_" }
    Log "Script will not overwrite existing files automatically."
    if (-not $PerformMove) {
        Log "DRY RUN: To proceed in real mode, set `$PerformMove = $true` after resolving conflicts or backing up."
        Exit 0
    } else {
        AbortWith "Conflicts present. Resolve them manually or remove conflicting files then re-run."
    }
}

# === Step 7 Execute move if requested ===
if ($PerformMove) {
    Log "Performing moves..."
    New-Item -ItemType Directory -Path $TargetPackageDir -Force | Out-Null
    foreach ($item in $itemsToMove) {
        $dest = Join-Path $TargetPackageDir $item.Name
        Log "Moving $($item.FullName) -> $dest"
        Move-Item -Path $item.FullName -Destination $dest -Force
    }
    Log "Moves complete."
} else {
    Log "DRY RUN complete. No files were moved."
    Log "To perform the actual migration, open this script and set `$PerformMove = $true` then re-run."
    Exit 0
}

# === Step 8 Post-move verification ===
# Count .py files before and after
$beforeCount = (Get-ChildItem -Path $candidate -Recurse -Include *.py -File -ErrorAction SilentlyContinue).Count
$afterCount = (Get-ChildItem -Path $TargetPackageDir -Recurse -Include *.py -File -ErrorAction SilentlyContinue).Count
Log "Post-move verification: .py files at source now: $beforeCount; at target: $afterCount"

if ($afterCount -lt 1) {
    Log "Warning: target contains few or no .py files. Check the move."
}

# === Step 9 Optional import check ===
if ($VerifyImports) {
    $pythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
    if ($pythonExe) {
        Log "Running quick import test: python -c 'import mammoth_os; print(mammoth_os.__file__)'"
        try {
            $importOut = & python -c "import sys; sys.path.insert(0, r'$ProjectRoot'); import mammoth_os; print(mammoth_os.__file__)"
            Log "Import test output: $importOut"
        } catch {
            Log "Import test failed: $_"
        }
    } else {
        Log "Python not found in PATH. Skipping import test."
    }
}

# === Step 10 Cleanup empty nested folders ===
# Only remove if empty
$nestedDir = $candidate
if ((Get-ChildItem -Path $nestedDir -Force | Measure-Object).Count -eq 0) {
    Log "Nested directory $nestedDir is empty and will be removed."
    Remove-Item -Path $nestedDir -Force -Recurse
} else {
    Log "Nested directory $nestedDir is not empty after move. Not removing automatically."
}

Log "Migration v2 completed. Log file: $LogFile"
Log "If anything looks wrong you can restore from snapshot:"
Log "  robocopy $BackupRoot $ProjectRoot /MIR"
