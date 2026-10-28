@echo off
REM FleetFuel - start the web application for the office / motorpool network.
REM The database is Firebase Firestore (online): this computer needs internet, but no XAMPP/MySQL.
REM 1. Backs up the Firestore database to backups\ (keeps the newest 30; the app also backs up every 24 hours).
REM 2. Starts the app with Waitress on port 5000 (reachable from other PCs on the same network).
REM 3. If the app ever stops unexpectedly, it is started again automatically.
REM Run install_autostart.bat once to start all of this automatically when Windows starts.
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
REM Another FleetFuel window already serves port 5000: leave it to that one
REM (on Windows two servers can share the port, and the older one keeps answering).
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
