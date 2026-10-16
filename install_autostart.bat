@echo off
REM Run ONCE on the server PC. Afterwards a small hidden watcher starts every time this
REM Windows account signs in. As soon as MySQL runs (e.g. you press Start on MySQL in the
REM XAMPP Control Panel), it starts FleetFuel and opens http://127.0.0.1:5000 in the browser.
REM To turn this off again, run uninstall_autostart.bat.
cd /d "%~dp0"
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
(
    echo @echo off
    echo start "" powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0xampp_watcher.ps1"
) > "%STARTUP%\FleetFuel Server.cmd"
start "" powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0xampp_watcher.ps1"
echo Done. Start Apache and MySQL in XAMPP and FleetFuel opens automatically.
echo Tip: turn off Sleep (Settings ^> System ^> Power) so the system stays available to the office.
timeout /t 10 >nul
