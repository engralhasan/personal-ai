# ==============================================================================
# J.A.R.V.I.S. Personal AI Desktop Assistant - PowerShell Launcher
# ==============================================================================

$Host.UI.RawUI.WindowTitle = "J.A.R.V.I.S. Desktop Assistant Launcher"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host "           J.A.R.V.I.S. Personal AI Desktop Assistant Launcher               " -ForegroundColor Cyan
Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Check Python
try {
    $pythonVersion = & python --version 2>&1
    Write-Host "[+] Found Python: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "[-] Python is not installed or not in PATH!" -ForegroundColor Red
    Read-Host "Press Enter to exit..."
    exit 1
}

# 2. Virtual Environment Setup
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "[*] Creating virtual environment (.venv)..." -ForegroundColor Yellow
    & python -m venv .venv
    & ".\.venv\Scripts\Activate.ps1"
    Write-Host "[*] Installing required packages..." -ForegroundColor Yellow
    & pip install -r requirements.txt
    Write-Host "[+] Setup complete." -ForegroundColor Green
} else {
    & ".\.venv\Scripts\Activate.ps1"
}

# 3. Check .env configuration
if (-not (Test-Path ".env")) {
    Write-Host "[*] Creating default .env configuration..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host "[+] .env created. You can customize your model or API key." -ForegroundColor Cyan
}

# 4. Launch Assistant
Write-Host ""
Write-Host "==============================================================================" -ForegroundColor Green
Write-Host "[*] Launching J.A.R.V.I.S. Assistant..." -ForegroundColor Green
Write-Host "==============================================================================" -ForegroundColor Green
Write-Host ""

& python main.py

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "[-] Application stopped with exit code: $LASTEXITCODE" -ForegroundColor Red
    Read-Host "Press Enter to exit..."
}
