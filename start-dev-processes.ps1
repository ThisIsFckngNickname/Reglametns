# Start backend process
$backendLog = "E:\OCProj\Reglametns\backend-dev.log"
$backendProcess = Start-Process -FilePath "python" -ArgumentList "-m uvicorn app.main:app --reload --log-level info" -WorkingDirectory "E:\OCProj\Reglametns\backend" -WindowStyle Hidden -PassThru
$backendProcess.Id | Out-File -FilePath "E:\OCProj\Reglametns\.backend.pid" -Encoding utf8
Write-Output "BACKEND_PID=$($backendProcess.Id)"

# Start frontend process
$frontendLog = "E:\OCProj\Reglametns\frontend-dev.log"
$frontendProcess = Start-Process -FilePath "npm" -ArgumentList "run dev" -WorkingDirectory "E:\OCProj\Reglametns\frontend" -WindowStyle Hidden -PassThru
$frontendProcess.Id | Out-File -FilePath "E:\OCProj\Reglametns\.frontend.pid" -Encoding utf8
Write-Output "FRONTEND_PID=$($frontendProcess.Id)"

# Wait
Start-Sleep -Seconds 5

# Check processes
$bp = Get-Process -Id $backendProcess.Id -ErrorAction SilentlyContinue
$fp = Get-Process -Id $frontendProcess.Id -ErrorAction SilentlyContinue

if ($bp) { Write-Output "BACKEND_RUNNING=true" } else { Write-Output "BACKEND_RUNNING=false" }
if ($fp) { Write-Output "FRONTEND_RUNNING=true" } else { Write-Output "FRONTEND_RUNNING=false" }

Write-Output "CHECK_DONE=true"
