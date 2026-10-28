@echo off
REM Stops FleetFuel from starting automatically (see install_autostart.bat).
del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\FleetFuel Server.cmd" 2>nul
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='powershell.exe'\" | Where-Object { $_.CommandLine -like '*xampp_watcher.ps1*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1
echo FleetFuel will no longer start automatically. Start it with start_server.bat when needed.
timeout /t 8 >nul
