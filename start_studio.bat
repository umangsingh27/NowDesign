@echo off
echo Starting NowPurchase Design Studio...

REM Auto-detect LAN IP (Windows)
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4 Address"') do (
    set LAN_IP=%%a
    goto :found_ip
)
:found_ip
set LAN_IP=%LAN_IP: =%

REM Start backend
start "NP Studio - Backend" cmd /k "cd /d %~dp0 && python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"
timeout /t 4 /nobreak > nul

REM Start frontend
start "NP Studio - Frontend" cmd /k "cd /d %~dp0frontend && npm run dev -- -H 0.0.0.0 -p 3000"

echo.
echo ============================================
echo  NowPurchase Design Studio is starting
echo ============================================
echo  This machine:  http://localhost:3000
echo  Company LAN:   http://%LAN_IP%:3000
echo  API Docs:      http://localhost:8000/docs
echo ============================================
pause
