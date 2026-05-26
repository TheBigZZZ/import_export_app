param(
    [string]$PythonExe = ".\\.venv\\Scripts\\python.exe",
    [switch]$BuildInstaller
)

$ErrorActionPreference = "Stop"

# Locate a PyInstaller spec file under packaging
$specCandidates = Get-ChildItem -Path .\packaging -Filter *.spec -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $specCandidates) {
    Write-Host "No .spec file found under packaging/ -- skipping Windows EXE build"
    Exit 0
}
$specPath = $specCandidates.FullName

if (!(Test-Path $PythonExe)) {
    # fallback to system python if venv not present
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) {
        $PythonExe = $cmd.Path
        Write-Host "Using system python: $PythonExe"
    } else {
        # try the py launcher
        $pyCmd = "py -3"
        try {
            $pyPath = (Get-Command py -ErrorAction SilentlyContinue).Path
            if ($pyPath) { $PythonExe = "py -3"; Write-Host "Using py launcher: $PythonExe" }
        } catch {
            throw "Python executable not found: $PythonExe"
        }
    }
}

Write-Host "Installing packaging dependency..."
& $PythonExe -m pip install pyinstaller==6.20.0
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install pyinstaller"
}

# Normalize and install the app's pinned runtime requirements so PyInstaller
# can collect all backend modules (including pydantic-based schemas).
$normalizeScript = Join-Path (Get-Location) 'packaging\normalize_requirements.py'
if (Test-Path $normalizeScript) {
    Write-Host "Normalizing pinned requirements encoding..."
    & $PythonExe $normalizeScript
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to normalize requirements encoding"
    }
}

$requirementsPath = Join-Path (Get-Location) 'packaging\requirements-pinned.txt'
if (Test-Path $requirementsPath) {
    Write-Host "Installing pinned runtime requirements..."
    & $PythonExe -m pip install -r $requirementsPath
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install pinned runtime requirements"
    }
}

Write-Host "Building executable with PyInstaller using spec: $specPath"
& $PythonExe -m PyInstaller --noconfirm --clean "$specPath"
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed"
}

Write-Host "Build completed. Output: .\\dist\\TradeDeskERP"

if ($BuildInstaller) {
    $isccCandidates = @(
        "$env:LOCALAPPDATA\\Programs\\Inno Setup 6\\ISCC.exe",
        "C:\\Program Files\\Inno Setup 6\\ISCC.exe",
        "C:\\Program Files (x86)\\Inno Setup 6\\ISCC.exe"
    )

    $iscc = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $iscc) {
        throw "Inno Setup compiler not found. Install Inno Setup 6 first."
    }

    Write-Host "Building installer with Inno Setup..."
    & $iscc ".\\packaging\\TradeDeskERP.iss"
    if ($LASTEXITCODE -ne 0) {
        throw "Inno Setup build failed"
    }

    Write-Host "Installer completed. Output: .\\dist\\TradeDeskERP-Setup.exe"
}