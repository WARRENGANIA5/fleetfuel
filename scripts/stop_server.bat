@echo off
REM Stops FleetFuel. (The data stays safe online in Firebase Firestore.)
taskkill /FI "WINDOWTITLE eq FleetFuel Server*" /T /F >nul 2>&1
echo FleetFuel has been stopped. You can now turn off this computer.
timeout /t 8 >nul
