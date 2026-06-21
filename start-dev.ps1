# start-dev.ps1
# Запускает backend (uvicorn) и frontend (npm run dev) в фоновом режиме.
# Сохраняет PID процессов, ожидает Q+Enter для остановки.

$ErrorActionPreference = 'Stop'

param(
    [switch]$Visible
)

# ---------- Paths ----------
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path -Path $ScriptDir -ChildPath "backend"
$FrontendDir = Join-Path -Path $ScriptDir -ChildPath "frontend"
$BackendLog  = Join-Path -Path $ScriptDir -ChildPath "backend-dev.log"
$FrontendLog = Join-Path -Path $ScriptDir -ChildPath "frontend-dev.log"
$BackendPid  = Join-Path -Path $ScriptDir -ChildPath ".backend.pid"
$FrontendPid = Join-Path -Path $ScriptDir -ChildPath ".frontend.pid"

# ---------- Helpers ----------
function Test-CommandAvailable {
    param([string]$CommandName)
    return (Get-Command $CommandName -ErrorAction SilentlyContinue) -ne $null
}

function Write-Step {
    param([string]$Message, [ConsoleColor]$Color = 'White')
    Write-Host $Message -ForegroundColor $Color
}

# ---------- Prerequisites ----------
if (-not (Test-CommandAvailable "python")) {
    Write-Step "ERROR: python not found in PATH. Please install Python." Red
    exit 1
}
if (-not (Test-CommandAvailable "npm")) {
    Write-Step "ERROR: npm not found in PATH. Please install Node.js / npm." Red
    exit 1
}

# ---------- Warn about stale PID files ----------
if (Test-Path -LiteralPath $BackendPid -PathType Leaf) {
    Write-Step "WARNING: .backend.pid already exists – previous backend may still be running." Yellow
}
if (Test-Path -LiteralPath $FrontendPid -PathType Leaf) {
    Write-Step "WARNING: .frontend.pid already exists – previous frontend may still be running." Yellow
}
if (Test-Path -LiteralPath $BackendPid -PathType Leaf -or Test-Path -LiteralPath $FrontendPid -PathType Leaf) {
    Write-Step "Run .\stop-dev.ps1 to clean up stale processes." Yellow
}

# ---------- Window style ----------
$WindowStyle = if ($Visible) { "Normal" } else { "Hidden" }

# ---------- Start processes ----------
$backend = $null
$frontend = $null

try {
    # --- Backend ---
    Write-Step "Starting backend (uvicorn)..." Green
    $backend = Start-Process -FilePath "python" `
        -ArgumentList "-m uvicorn app.main:app --reload --log-level info" `
        -WorkingDirectory $BackendDir `
        -WindowStyle $WindowStyle `
        -PassThru `
        -RedirectStandardOutput $BackendLog `
        -RedirectStandardError $BackendLog

    $backend.Id | Out-File -FilePath $BackendPid -Encoding utf8
    Write-Step "  backend PID $($backend.Id) -> $(Split-Path $BackendLog -Leaf)" Green

    # --- Frontend ---
    Write-Step "Starting frontend (npm run dev)..." Green
    $frontend = Start-Process -FilePath "npm" `
        -ArgumentList "run dev" `
        -WorkingDirectory $FrontendDir `
        -WindowStyle $WindowStyle `
        -PassThru `
        -RedirectStandardOutput $FrontendLog `
        -RedirectStandardError $FrontendLog

    $frontend.Id | Out-File -FilePath $FrontendPid -Encoding utf8
    Write-Step "  frontend PID $($frontend.Id) -> $(Split-Path $FrontendLog -Leaf)" Green

    # ---------- Summary ----------
    Write-Step ""
    Write-Step ("=" * 48) Cyan
    Write-Step "  Dev servers started" Cyan
    Write-Step ("=" * 48) Cyan
    Write-Step "  Backend PID : $($backend.Id)" Yellow
    Write-Step "  Frontend PID: $($frontend.Id)" Yellow
    Write-Step ""
    Write-Step "  Backend  => http://localhost:8000" Green
    Write-Step "  Frontend => http://localhost:5173" Green
    Write-Step "  Swagger  => http://localhost:8000/docs" Green
    Write-Step ""
    Write-Step "  Backend log : $BackendLog"
    Write-Step "  Frontend log: $FrontendLog"
    Write-Step ("=" * 48) Cyan
    Write-Step ""
    Write-Step "Press Q and then Enter to stop both services..." Magenta

    # ---------- Wait for stop signal ----------
    do {
        $key = Read-Host
    } while ($key -ne 'Q' -and $key -ne 'q')
}
finally {
    # ---------- Cleanup ----------
    Write-Step "`nStopping services..." Yellow

    if ($backend -and (Get-Process -Id $backend.Id -ErrorAction SilentlyContinue)) {
        Stop-Process -Id $backend.Id -Force
        Write-Step "  Backend (PID $($backend.Id)) stopped." Green
    } else {
        Write-Step "  Backend is not running." Yellow
    }

    if ($frontend -and (Get-Process -Id $frontend.Id -ErrorAction SilentlyContinue)) {
        Stop-Process -Id $frontend.Id -Force
        Write-Step "  Frontend (PID $($frontend.Id)) stopped." Green
    } else {
        Write-Step "  Frontend is not running." Yellow
    }

    Remove-Item -Path $BackendPid -Force -ErrorAction SilentlyContinue
    Remove-Item -Path $FrontendPid -Force -ErrorAction SilentlyContinue

    Write-Step "Done." Green
}
