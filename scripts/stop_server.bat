@echo off
REM Stop FleetFuel. Kills the watcher first so it doesn't restart the server.
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='powershell.exe'\" | Where-Object { $_.CommandLine -like '*fleetfuel_watcher.ps1*' -or $_.CommandLine -like '*xampp_watcher.ps1*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1
taskkill /FI "WINDOWTITLE eq FleetFuel Server*" /T /F >nul 2>&1
REM Also stop anything else listening on port 5000.
powershell -NoProfile -Command "Get-NetTCPConnection -State Listen -LocalPort 5000 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }" >nul 2>&1
echo FleetFuel has been stopped. You can now turn off this computer.
timeout /t 8 >nul
