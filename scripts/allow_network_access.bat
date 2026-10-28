@echo off
REM Run ONCE as Administrator (right-click > Run as administrator) so other
REM computers on the GSO network can open the system on port 5000.
netsh advfirewall firewall add rule name="GSU FleetFuel (port 5000)" dir=in action=allow protocol=TCP localport=5000 profile=private,domain
echo Done. Other PCs on the same network can now open http://^<this-PC-IP^>:5000
pause
