# Hidden watcher (set up by install_autostart.bat): restarts start_server.bat
# whenever FleetFuel isn't running.
$ErrorActionPreference = "SilentlyContinue"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

# Only one watcher at a time.
$created = $false
$mutex = New-Object System.Threading.Mutex($true, "Local\FleetFuelXamppWatcher", [ref]$created)
if (-not $created) { exit }

function Test-Listening($port) {
    [bool](Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue)
}

# start_server.bat restarts the app itself, so ignore short gaps on the port
function Test-ServerWindow {
    [bool](Get-CimInstance Win32_Process -Filter "Name='cmd.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like '*start_server.bat*' })
}

$openedBrowser = $false
while ($true) {
    if (-not (Test-Listening 5000) -and -not (Test-ServerWindow)) {
        Start-Process -FilePath "$root\start_server.bat" -WorkingDirectory $root -WindowStyle Minimized
        for ($i = 0; $i -lt 60 -and -not (Test-Listening 5000); $i++) { Start-Sleep -Seconds 1 }
        # open the browser only on the first start
        if ((Test-Listening 5000) -and -not $openedBrowser) {
            Start-Process "http://127.0.0.1:5000"
            $openedBrowser = $true
        }
    }
    Start-Sleep -Seconds 3
}
