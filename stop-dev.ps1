# stop-dev.ps1
# Останавливает backend и frontend, запущенные через start-dev.ps1.
# Читает PID из .backend.pid / .frontend.pid и убивает процессы.

$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendPid  = Join-Path -Path $ScriptDir -ChildPath ".backend.pid"
$FrontendPid = Join-Path -Path $ScriptDir -ChildPath ".frontend.pid"

$stoppedAny = $false

function Stop-ServiceFromPidFile {
    param(
        [string]$PidFilePath,
        [string]$ServiceName
    )
    if (-not (Test-Path -LiteralPath $PidFilePath -PathType Leaf)) {
        Write-Host "$ServiceName: PID file not found ($PidFilePath)." -ForegroundColor Yellow
        return
    }

    $pidString = (Get-Content -LiteralPath $PidFilePath -Raw).Trim()
    if ($pidString -notmatch '^\d+$') {
        Write-Host "$ServiceName: invalid PID in file ($pidString). Removing file." -ForegroundColor Yellow
        Remove-Item -LiteralPath $PidFilePath -Force -ErrorAction SilentlyContinue
        return
    }

    $pidInt = [int]$pidString
    $proc = Get-Process -Id $pidInt -ErrorAction SilentlyContinue
    if ($proc) {
        Stop-Process -Id $pidInt -Force
        Write-Host "$ServiceName (PID $pidInt) stopped." -ForegroundColor Green
        $script:stoppedAny = $true
    } else {
        Write-Host "$ServiceName (PID $pidInt) is not running." -ForegroundColor Yellow
    }

    Remove-Item -LiteralPath $PidFilePath -Force -ErrorAction SilentlyContinue
}

Stop-ServiceFromPidFile -PidFilePath $BackendPid  -ServiceName "Backend"
Stop-ServiceFromPidFile -PidFilePath $FrontendPid -ServiceName "Frontend"

if (-not $stoppedAny) {
    Write-Host "No running services found." -ForegroundColor Yellow
}
