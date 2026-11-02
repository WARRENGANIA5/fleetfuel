@echo off
REM Run once as Administrator to open port 5000 on the office network.
netsh advfirewall firewall add rule name="GSU FleetFuel (port 5000)" dir=in action=allow protocol=TCP localport=5000 profile=private,domain
echo Done. Other PCs on the same network can now open http://^<this-PC-IP^>:5000
pause
