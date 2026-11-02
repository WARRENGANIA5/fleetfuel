@echo off
REM Start FleetFuel on port 5000 (needs internet for Firestore).
REM Backs up the database first, and restarts the app if it crashes.
cd /d "%~dp0.."
title FleetFuel Server

netstat -ano | find ":5000 " | find "LISTENING" >nul
if not errorlevel 1 (
    echo FleetFuel is already running on this computer: http://127.0.0.1:5000
    timeout /t 8 >nul
    exit /b 0
)

"venv\Scripts\python.exe" backup_database.py

echo.
echo Open the system on this computer:   http://127.0.0.1:5000
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /R /C:"IPv4 Address"') do echo Open from other PCs on the network:  http:%%a:5000
echo (Keep this window open while the system is in use. If it is closed, the FleetFuel watcher
echo  installed by install_autostart.bat starts the system again within a few seconds.)
echo.

:run
REM Already running on port 5000, don't start a second one.
netstat -ano | find ":5000 " | find "LISTENING" >nul
if not errorlevel 1 (
    echo [%date% %time%] FleetFuel is already running in another window. This window will close.
    timeout /t 8 >nul
    exit /b 0
)
"venv\Scripts\python.exe" app.py
echo.
echo [%date% %time%] The system stopped. Starting it again in 10 seconds... (close this window to stop it)
timeout /t 10 /nobreak >nul
goto run
