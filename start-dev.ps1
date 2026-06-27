# start-dev.ps1
# Запускает backend (uvicorn) и frontend (npm run dev) в фоновом режиме БЕЗ ОКОН.
# Использование: .\start-dev.ps1

$ErrorActionPreference = 'Stop'

# ---------- Paths ----------
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path -Path $ScriptDir -ChildPath "backend"
$FrontendDir = Join-Path -Path $ScriptDir -ChildPath "frontend"
$BackendLog  = Join-Path -Path $ScriptDir -ChildPath "backend-dev.log"
$FrontendLog = Join-Path -Path $ScriptDir -ChildPath "frontend-dev.log"
$BackendPid  = Join-Path -Path $ScriptDir -ChildPath ".backend.pid"
$FrontendPid = Join-Path -Path $ScriptDir -ChildPath ".frontend.pid"

# ---------- Helpers ----------
function Write-Step {
    param([string]$Message, [ConsoleColor]$Color = 'White')
    Write-Host $Message -ForegroundColor $Color
}

function Remove-StalePid {
    param([string]$PidFile, [string]$Label)
    if (Test-Path -LiteralPath $PidFile -PathType Leaf) {
        $oldPid = Get-Content $PidFile
        Write-Step "WARNING: Stale $Label PID file found (PID $oldPid)." Yellow
        Stop-Process -Id $oldPid -Force -ErrorAction SilentlyContinue
        Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    }
}

# ---------- Cleanup stale PIDs ----------
Remove-StalePid $BackendPid "backend"
Remove-StalePid $FrontendPid "frontend"

# ---------- Start Backend ----------
Write-Step "Starting backend (uvicorn)..." Green
$backend = Start-Process -FilePath "python" `
    -ArgumentList "-m uvicorn app.main:app --reload --log-level info" `
    -WorkingDirectory $BackendDir `
    -WindowStyle Hidden `
    -PassThru

$backend.Id | Out-File -FilePath $BackendPid -Encoding utf8
Write-Step "  backend PID $($backend.Id) (hidden)" Green

# ---------- Start Frontend ----------
Write-Step "Starting frontend (npm run dev)..." Green
$frontend = Start-Process -FilePath "cmd.exe" `
    -ArgumentList "/c cd /d `"$FrontendDir`" && npm run dev -- --host 0.0.0.0" `
    -WindowStyle Hidden `
    -PassThru

$frontend.Id | Out-File -FilePath $FrontendPid -Encoding utf8
Write-Step "  frontend PID $($frontend.Id) (hidden)" Green

# ---------- Summary ----------
Write-Step ""
Write-Step ("=" * 48) Cyan
Write-Step "  Dev servers started (ALL HIDDEN)" Cyan
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
Write-Step "  To stop: .\stop-dev.ps1  or  .\stop.cmd"
Write-Step ""
