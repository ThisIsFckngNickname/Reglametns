# stop-dev.ps1
# РћСЃС‚Р°РЅР°РІР»РёРІР°РµС‚ backend Рё frontend РїРѕ PID-С„Р°Р№Р»Р°Рј.

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendPid  = Join-Path -Path $ScriptDir -ChildPath ".backend.pid"
$FrontendPid = Join-Path -Path $ScriptDir -ChildPath ".frontend.pid"
$BackendLog  = Join-Path -Path $ScriptDir -ChildPath "backend-dev.log"
$FrontendLog = Join-Path -Path $ScriptDir -ChildPath "frontend-dev.log"

function Stop-ByPidFile {
    param([string]$PidFile, [string]$Label)
    if (Test-Path -LiteralPath $PidFile -PathType Leaf) {
        $processId = Get-Content $PidFile
        Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
        Write-Host "  $Label (PID $processId) stopped." Green
        Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    } else {
        Write-Host "  ${Label}: no PID file found." Yellow
    }
}

Write-Host "Stopping services..." Yellow
Stop-ByPidFile $BackendPid "Backend"
Stop-ByPidFile $FrontendPid "Frontend"
Write-Host "Done." Green
