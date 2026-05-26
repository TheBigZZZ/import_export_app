<#
Automated smoke test for TradeDesk packaged app.

Usage: run from repository root in PowerShell (recommended in an elevated terminal):
  powershell -ExecutionPolicy Bypass -File .\scripts\smoke_test.ps1

What it does:
- Starts the packaged EXE (dist/TradeDeskERP/TradeDeskERP.exe)
- Waits for /health to respond
- Logs in using `TRADEDESK_TEST_ADMIN_USER` and `TRADEDESK_TEST_ADMIN_PASS`
- Creates a customer and a product
- Lists accounts and posts a simple voucher using two seeded accounts
- Creates a DB backup via the CLI
- Stops the app, restores the backup, restarts the app and verifies data
- Prints a pass/fail summary

Note: script assumes the app uses default settings paths (%USERPROFILE%/TradeDesk) and
that the virtualenv is at .\.venv with python available at .\.venv\Scripts\python
#>

param(
    [string]$ExePath = '',
    [string]$HealthUrl = 'http://127.0.0.1:8742/health',
    [int]$Timeout = 60
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Wait-ForHealth {
    param($Url, $TimeoutSec = 60)
    $start = Get-Date
    while ((Get-Date) -lt $start.AddSeconds($TimeoutSec)) {
        try {
            $res = Invoke-RestMethod -Uri $Url -TimeoutSec 5
            if ($res -and $res.status -eq 'ok') { return $true }
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }
    return $false
}

function ExitWithFailure($msg) {
    Write-Host "[FAIL] $msg" -ForegroundColor Red
    Exit 1
}

Write-Host "Starting TradeDesk smoke test..."

if ($ExePath -and (Test-Path $ExePath)) {
    $exePath = $ExePath
} else {
    $exePath = Join-Path (Get-Location) 'dist\TradeDeskERP\TradeDeskERP.exe'
    if (-Not (Test-Path $exePath)) {
        # try to find any exe under dist if layout differs
        $candidates = Get-ChildItem -Path (Join-Path (Get-Location) 'dist') -Recurse -Filter *.exe -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($candidates) { $exePath = $candidates.FullName } else { ExitWithFailure "Executable not found at expected path and no .exe in dist: $exePath" }
    }
}

$runId = (Get-Date).ToString('yyyyMMddHHmmss')

Write-Host "Launching EXE: $exePath"
$proc = Start-Process -FilePath $exePath -PassThru
Start-Sleep -Milliseconds 800

Write-Host "Waiting for health endpoint $HealthUrl ($Timeout s) ..."
if (-Not (Wait-ForHealth -Url $HealthUrl -TimeoutSec $Timeout)) {
    # try to show backend temp error if present
    $err = Join-Path $env:TEMP 'tradedesk-backend-error.txt'
    if (Test-Path $err) { Write-Host "Backend error file:"; Get-Content $err -Tail 200 }
    $proc | Stop-Process -Force -ErrorAction SilentlyContinue
    ExitWithFailure "Health endpoint did not respond in time."
}
Write-Host "Health OK"

# Login - credentials must be provided via environment variables for security
$loginUrl = "$HealthUrl" -replace '/health$','/api/auth/login'
$adminUser = $env:TRADEDESK_TEST_ADMIN_USER
$adminPass = $env:TRADEDESK_TEST_ADMIN_PASS
if (-not $adminUser -or -not $adminPass) {
    $proc | Stop-Process -Force -ErrorAction SilentlyContinue
    ExitWithFailure "Set TRADEDESK_TEST_ADMIN_USER and TRADEDESK_TEST_ADMIN_PASS environment variables before running this script."
}
$creds = @{ username = $adminUser; password = $adminPass } | ConvertTo-Json
Write-Host "Logging in as test admin user: $adminUser"
try {
    $tokenResp = Invoke-RestMethod -Uri $loginUrl -Method Post -Body $creds -ContentType 'application/json' -TimeoutSec 10
} catch {
    $proc | Stop-Process -Force -ErrorAction SilentlyContinue
    ExitWithFailure "Failed to login: $($_.Exception.Message)"
}
if (-not $tokenResp.access_token) { $proc | Stop-Process -Force -ErrorAction SilentlyContinue; ExitWithFailure 'Login did not return access_token' }
$authHeader = @{ Authorization = "Bearer $($tokenResp.access_token)" }
Write-Host "Logged in, token acquired."

# Create customer
$customerUrl = 'http://127.0.0.1:8742/api/customers'
$customerPayload = @{ customer_code = "SMK-CUST-$runId"; customer_name = 'Smoke Test Customer'; contact_person = 'Automated Tester'; phone = '555-0101' } | ConvertTo-Json
Write-Host "Creating customer..."
try {
    $custResp = Invoke-RestMethod -Uri $customerUrl -Method Post -Body $customerPayload -Headers $authHeader -ContentType 'application/json' -TimeoutSec 10
} catch {
    $proc | Stop-Process -Force -ErrorAction SilentlyContinue
    ExitWithFailure "Failed to create customer: $($_.Exception.Message)"
}
Write-Host "Customer created: id=$($custResp.id)"

# Create product
$productUrl = 'http://127.0.0.1:8742/api/products'
$productPayload = @{ product_code = "SMK-PROD-$runId"; product_name = 'Smoke Test Product'; unit = 'pcs'; purchase_price = 10.00; selling_price = 15.00 } | ConvertTo-Json
Write-Host "Creating product..."
try {
    $prodResp = Invoke-RestMethod -Uri $productUrl -Method Post -Body $productPayload -Headers $authHeader -ContentType 'application/json' -TimeoutSec 10
} catch {
    $proc | Stop-Process -Force -ErrorAction SilentlyContinue
    ExitWithFailure "Failed to create product: $($_.Exception.Message)"
}
Write-Host "Product created: id=$($prodResp.id)"

# Shared date stamp for smoke test payloads
$today = (Get-Date).ToString('yyyy-MM-dd')

# Create stock movement (receive stock)
$movementUrl = "http://127.0.0.1:8742/api/products/movements"
$movementPayload = @{
    product_id = $prodResp.id
    movement_type = 'in'
    quantity = 50
    movement_date = $today
    unit_cost = 10.00
    document_type = 'purchase'
    document_no = "PO-TEST-$runId"
    document_status = 'posted'
} | ConvertTo-Json -Depth 5
Write-Host "Creating stock movement (receive 50)..."
try {
    $movResp = Invoke-RestMethod -Uri $movementUrl -Method Post -Body $movementPayload -Headers $authHeader -ContentType 'application/json' -TimeoutSec 10
} catch {
    $proc | Stop-Process -Force -ErrorAction SilentlyContinue
    ExitWithFailure "Failed to create stock movement: $($_.Exception.Message)"
}
Write-Host "Stock movement created id=$($movResp.id)"

# List accounts and pick two for voucher
$accountsUrl = 'http://127.0.0.1:8742/api/accounts'
Write-Host "Listing accounts..."
try {
    $accounts = Invoke-RestMethod -Uri $accountsUrl -Headers $authHeader -TimeoutSec 10
} catch {
    $proc | Stop-Process -Force -ErrorAction SilentlyContinue
    ExitWithFailure "Failed to list accounts: $($_.Exception.Message)"
}
if ($accounts.Count -lt 2) { $proc | Stop-Process -Force -ErrorAction SilentlyContinue; ExitWithFailure 'Not enough accounts to create voucher' }
$debitAccount = $accounts[0].id
$creditAccount = $accounts[1].id
Write-Host "Using accounts: debit=$debitAccount credit=$creditAccount"

# Post a simple voucher (balanced)
$voucherUrl = 'http://127.0.0.1:8742/api/vouchers'
$voucherPayload = @{
    voucher_type = 'JV'
    transaction_date = $today
    description = 'Smoke test voucher'
    lines = @(
        @{ account_id = $debitAccount; debit = 100.00; credit = 0.00; description = 'Debit for test' },
        @{ account_id = $creditAccount; debit = 0.00; credit = 100.00; description = 'Credit for test' }
    )
} | ConvertTo-Json -Depth 5
Write-Host "Creating voucher..."
try {
    $voucherResp = Invoke-WebRequest -UseBasicParsing -Uri $voucherUrl -Method Post -Body $voucherPayload -Headers $authHeader -ContentType 'application/json' -TimeoutSec 20
    $voucherJson = $voucherResp.Content | ConvertFrom-Json
} catch {
    $errorBody = ''
    try {
        if ($_.Exception.Response) {
            $stream = $_.Exception.Response.GetResponseStream()
            if ($stream) {
                $reader = New-Object System.IO.StreamReader($stream)
                $errorBody = $reader.ReadToEnd()
            }
        }
    } catch {
        $errorBody = ''
    }
    $proc | Stop-Process -Force -ErrorAction SilentlyContinue
    ExitWithFailure "Failed to create voucher: $($_.Exception.Message) $errorBody"
}
Write-Host "Voucher posted"

# Create backup
$backupDir = Join-Path (Get-Location) 'test_backups'
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
Write-Host "Creating backup via CLI..."
# Prefer venv python, but fall back to system python if absent on CI runners
$pythonExe = Join-Path (Get-Location) '.venv\Scripts\python.exe'
if (-Not (Test-Path $pythonExe)) { $pythonExe = Join-Path (Get-Location) '.venv\Scripts\python' }
if (-Not (Test-Path $pythonExe)) {
    $sysPy = (Get-Command python -ErrorAction SilentlyContinue).Path
    if ($sysPy) { $pythonExe = $sysPy } else { $pythonExe = 'py -3' }
}

Write-Host "Calling: $pythonExe -m tradedesk.backend.cli --backup-db $backupDir"
$backupOutput = & $pythonExe -m tradedesk.backend.cli --backup-db $backupDir 2>&1
Write-Host $backupOutput
$backupLine = ($backupOutput | Select-String 'Database backup created:' -SimpleMatch).ToString()
if (-not $backupLine) { $proc | Stop-Process -Force -ErrorAction SilentlyContinue; ExitWithFailure 'Backup command did not report created file' }
$backupPath = $backupLine -replace '.*Database backup created:\s*',''
Write-Host "Backup created: $backupPath"

Write-Host "Stopping app to test restore..."
$proc | Stop-Process -Force
Start-Sleep -Seconds 1

Write-Host "Restoring backup..."
$restoreOutput = & $pythonExe -m tradedesk.backend.cli --restore-db $backupPath 2>&1
Write-Host $restoreOutput
if ($LASTEXITCODE -ne 0) { ExitWithFailure "Restore command failed: $restoreOutput" }

Write-Host "Restarting app..."
$proc2 = Start-Process -FilePath $exePath -PassThru
if (-Not (Wait-ForHealth -Url $healthUrl -TimeoutSec 60)) { $proc2 | Stop-Process -Force -ErrorAction SilentlyContinue; ExitWithFailure 'Health endpoint not available after restore and restart' }

Write-Host "Verifying restored data: fetch customer list and locate id $($custResp.id)"
$custCheckUrl = 'http://127.0.0.1:8742/api/customers'
try {
    $custCheck = Invoke-RestMethod -Uri $custCheckUrl -Headers $authHeader -TimeoutSec 10
} catch {
    $proc2 | Stop-Process -Force -ErrorAction SilentlyContinue
    ExitWithFailure "Failed to fetch customer list after restore: $($_.Exception.Message)"
}
if (-not ($custCheck | Where-Object { $_.id -eq $custResp.id -and $_.customer_name -eq 'Smoke Test Customer' })) { $proc2 | Stop-Process -Force -ErrorAction SilentlyContinue; ExitWithFailure 'Restored customer data does not match' }

# Check product stock ledger
Write-Host "Checking product stock ledger..."
$ledgerUrl = "http://127.0.0.1:8742/api/products/$($prodResp.id)/ledger"
try {
    $ledger = Invoke-RestMethod -Uri $ledgerUrl -Headers $authHeader -TimeoutSec 10
} catch {
    $proc2 | Stop-Process -Force -ErrorAction SilentlyContinue
    ExitWithFailure "Failed to fetch product ledger: $($_.Exception.Message)"
}
if ($ledger.current_stock -lt 50) { $proc2 | Stop-Process -Force -ErrorAction SilentlyContinue; ExitWithFailure 'Product stock after receive is incorrect' }

# Check reports endpoints
Write-Host "Checking reports endpoints..."
$reportsBase = 'http://127.0.0.1:8742/api/reports'
foreach ($ep in @('dashboard','trial-balance','profit-loss','stock-position')) {
    try {
        $r = Invoke-RestMethod -Uri ("$reportsBase/$ep") -Headers $authHeader -TimeoutSec 10
        Write-Host "Report $ep OK"
    } catch {
        $proc2 | Stop-Process -Force -ErrorAction SilentlyContinue
        ExitWithFailure "Report $ep failed: $($_.Exception.Message)"
    }
}

Write-Host "Smoke test PASSED" -ForegroundColor Green
Write-Host "Cleaning up: stopping app and leaving backup in $backupDir"
$proc2 | Stop-Process -Force -ErrorAction SilentlyContinue
Exit 0
