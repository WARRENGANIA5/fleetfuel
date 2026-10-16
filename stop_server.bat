@echo off
REM Stops FleetFuel and shuts MySQL down cleanly. Use this before turning off
REM the server PC: turning it off while MySQL runs can corrupt its tables.
taskkill /FI "WINDOWTITLE eq FleetFuel Server*" /T /F >nul 2>&1
"C:\xampp\mysql\bin\mysqladmin.exe" -u root shutdown >nul 2>&1
echo FleetFuel and MySQL have been stopped. You can now turn off this computer.
timeout /t 8 >nul
