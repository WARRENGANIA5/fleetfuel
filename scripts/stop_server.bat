@echo off
REM Stops FleetFuel. (The data stays safe online in Firebase Firestore.)
REM The watcher is stopped first, or it would start the system again within seconds;
REM it starts again at the next Windows sign-in (install_autostart.bat).
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='powershell.exe'\" | Where-Object { $_.CommandLine -like '*fleetfuel_watcher.ps1*' -or $_.CommandLine -like '*xampp_watcher.ps1*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1
taskkill /FI "WINDOWTITLE eq FleetFuel Server*" /T /F >nul 2>&1
REM A server started by typing "python app.py" in a terminal (whatever listens on port 5000).
powershell -NoProfile -Command "Get-NetTCPConnection -State Listen -LocalPort 5000 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }" >nul 2>&1
echo FleetFuel has been stopped. You can now turn off this computer.
timeout /t 8 >nul
