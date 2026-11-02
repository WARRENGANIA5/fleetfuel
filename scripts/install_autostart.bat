@echo off
REM Run once on the server PC. Starts the watcher at every Windows sign-in.
REM Undo with uninstall_autostart.bat.
cd /d "%~dp0"
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
(
    echo @echo off
    echo start "" powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0fleetfuel_watcher.ps1"
) > "%STARTUP%\FleetFuel Server.cmd"
start "" powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0fleetfuel_watcher.ps1"
echo Done. FleetFuel now starts automatically when you sign in to Windows.
echo Tip: turn off Sleep (Settings ^> System ^> Power) so the system stays available to the office.
timeout /t 10 >nul
