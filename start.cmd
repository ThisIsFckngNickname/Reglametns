@echo off
title SRP Launcher
set ROOT_DIR=%~dp0

echo ========================================
echo   SRP — запуск сервисов (скрытый режим)
echo ========================================
echo.

:: Clean up old processes
echo [1/4] Остановка старых процессов...
powershell -Command "Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }" >nul 2>&1
powershell -Command "Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }" >nul 2>&1
timeout /t 2 /nobreak >nul
echo   OK

:: Start Backend (hidden)
echo [2/4] Launching backend (port 8000)...
powershell -Command "Start-Process -WindowStyle Hidden -FilePath 'python' -ArgumentList '-m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000' -WorkingDirectory '%ROOT_DIR%backend'"
timeout /t 3 /nobreak >nul
echo   OK

:: Start Frontend (hidden via cmd.exe, because npm.cmd is a batch file)
echo [3/4] Launching frontend (port 5173)...
powershell -Command "Start-Process -WindowStyle Hidden -FilePath 'cmd.exe' -ArgumentList '/c cd /d \"%ROOT_DIR%frontend\" && npm run dev' -RedirectStandardOutput '%ROOT_DIR%frontend-dev.log' -RedirectStandardError '%ROOT_DIR%frontend-dev.log'"
timeout /t 5 /nobreak >nul
echo   OK

:: Verify
echo [4/4] Verification...
powershell -Command "$b = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue; $f = Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue; if ($b) { Write-Host ('   Backend: http://localhost:8000 (PID ' + $b.OwningProcess + ')') } else { Write-Host '   Backend: NOT RUNNING' }; if ($f) { Write-Host ('   Frontend: http://localhost:5173 (PID ' + $f.OwningProcess + ')') } else { Write-Host '   Frontend: NOT RUNNING' }"

echo.
echo Services started in hidden mode.
echo To stop: run stop.cmd
echo.
pause
