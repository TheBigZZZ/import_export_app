<#
Cleanup script for TradeDesk local backend and app data.
Stops lingering backend/launcher processes, clears keyring tokens, removes PID file,
and optionally deletes the user TradeDesk directory (backup first).

Usage examples:
  # Dry-run: show processes
  .\cleanup_tradedesk.ps1 -WhatIf

  # Stop processes and remove PID file
  .\cleanup_tradedesk.ps1

  # Stop processes and delete user data (DANGEROUS: backs up first)
  .\cleanup_tradedesk.ps1 -DeleteData
#>

param(
    [switch]$DeleteData
)

Write-Host "Searching for TradeDesk processes..."

$matches = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'tradedesk|uvicorn|launcher|TradeDesk' }
if (-not $matches) {
    Write-Host "No matching processes found."
} else {
    $matches | Select-Object ProcessId, CommandLine | Format-Table -AutoSize
    foreach ($p in $matches) {
        try {
            Write-Host "Stopping PID $($p.ProcessId)..."
            Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop
        } catch {
            Write-Warning "Could not stop PID $($p.ProcessId): $_"
            # Try taskkill as fallback
            & taskkill /PID $p.ProcessId /F /T 2>$null
        }
    }
}

# Remove PID file if present
$pidFile = Join-Path $env:USERPROFILE "TradeDesk\backend.pid"
if (Test-Path $pidFile) {
    try {
        Remove-Item -Path $pidFile -Force
        Write-Host "Removed PID file: $pidFile"
    } catch {
        Write-Warning "Could not remove PID file: $_"
    }
}

# Clear stored keyring tokens using the virtualenv's python if present
$venvPython = Join-Path (Get-Location) '.venv\Scripts\python.exe'
if (Test-Path $venvPython) {
    Write-Host "Clearing keyring tokens using $venvPython"
    & $venvPython - <<'PY'
import keyring
for k in ('access_token','refresh_token'):
    try:
        keyring.delete_password('TradeDeskERP', k)
        print('deleted', k)
    except Exception as e:
        print('could not delete', k, e)
PY
} else {
    Write-Host "No venv python found at $venvPython, skipping keyring cleanup."
}

if ($DeleteData) {
    $dataDir = Join-Path $env:USERPROFILE 'TradeDesk'
    if (Test-Path $dataDir) {
        $backup = "$dataDir.bak_$(Get-Date -Format 'yyyyMMddHHmmss')"
        Write-Host "Backing up $dataDir to $backup"
        try {
            Move-Item -Path $dataDir -Destination $backup -Force
            Write-Host "Backup complete."
        } catch {
            Write-Warning "Backup failed: $_"
        }
    } else {
        Write-Host "No data directory found at $dataDir"
    }
}

Write-Host "Cleanup complete."
