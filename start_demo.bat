@echo off
setlocal
set "ROOT=%~dp0ai-middleman"

echo ============================================================
echo AI Middleman - starting the full local stack
echo ============================================================

cd /d "%ROOT%"
python scripts\start_all.py
if errorlevel 1 (
    echo.
    echo Backend/database/tunnel failed to start - see messages above.
    pause
    exit /b 1
)

echo.
for /f %%C in ('curl -s -o nul -w "%%{http_code}" http://localhost:5174 2^>nul') do set FRONTEND_CODE=%%C
if "%FRONTEND_CODE%"=="200" (
    echo Frontend already running at http://localhost:5174
) else (
    echo Starting frontend dashboard...
    start "AI Middleman - Frontend" cmd /k "%ROOT%\frontend\run-dev.cmd"
    echo Waiting for the dashboard to come up...
    timeout /t 6 /nobreak >nul
)
start "" "http://localhost:5174"

echo.
echo ============================================================
echo All set - backend, tunnel, and frontend are starting.
echo You can close this window; the other windows keep running.
echo ============================================================
pause
