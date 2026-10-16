@echo off
REM Run ONCE on the server PC. Installs XAMPP MySQL as a Windows service that
REM starts when Windows starts and is shut down cleanly when Windows shuts down.
REM Without it, turning the PC off while MySQL runs in a window can corrupt its
REM tables (this happened on 2026-10-16). Asks for administrator permission.
net session >nul 2>&1
if errorlevel 1 (
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

sc query mysql >nul 2>&1
if not errorlevel 1 goto start_service

echo Stopping MySQL that is running in a window...
"C:\xampp\mysql\bin\mysqladmin.exe" -u root shutdown >nul 2>&1
timeout /t 5 /nobreak >nul

echo Installing the MySQL service...
"C:\xampp\mysql\bin\mysqld.exe" --install mysql --defaults-file="C:\xampp\mysql\bin\my.ini"
if errorlevel 1 (
    echo Installing the service failed.
    pause
    exit /b 1
)
sc config mysql start= auto >nul

:start_service
sc query mysql | find "RUNNING" >nul
if errorlevel 1 net start mysql
echo.
echo Done. MySQL now runs as a Windows service and stops cleanly when Windows shuts down.
timeout /t 10 >nul
