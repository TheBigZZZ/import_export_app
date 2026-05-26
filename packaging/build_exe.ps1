Param(
    [string]$DistDir = "dist",
    [string]$Spec = "packaging/pyinstaller/tradedesk.spec",
    [switch]$OneFile = $true
)

Write-Host "Building TradeDesk executable..."

if (-not (Get-Command pyinstaller -ErrorAction SilentlyContinue)) {
    Write-Host "pyinstaller not found. Install it in the active venv: pip install pyinstaller" -ForegroundColor Yellow
    exit 2
}

if ($OneFile) {
    Write-Host "Using entrypoint launcher.py with --onefile"
    $addData = "frontend/assets;frontend/assets"
    pyinstaller --noconfirm --onefile --add-data $addData launcher.py
} else {
    Write-Host "Building using spec file: $Spec"
    pyinstaller --noconfirm $Spec
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "PyInstaller failed with exit code $LASTEXITCODE" -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host "Build finished. Check the $DistDir folder for the executable." -ForegroundColor Green
