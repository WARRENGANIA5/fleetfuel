# FleetFuel watcher - runs hidden in the background (installed by install_autostart.bat).
# Keeps FleetFuel running: whenever the system is not running (after sign-in, or when its
# window was closed or the app stopped), it starts start_server.bat again within seconds.
# The database is Firebase Firestore (online), so nothing else has to be started first.
$ErrorActionPreference = "SilentlyContinue"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

# Only one watcher at a time.
$created = $false
$mutex = New-Object System.Threading.Mutex($true, "Local\FleetFuelXamppWatcher", [ref]$created)
if (-not $created) { exit }

function Test-Listening($port) {
    [bool](Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue)
}

# A start_server.bat window already running restarts the app by itself, so a
# brief gap on port 5000 (e.g. during a restart) must not start a second one.
function Test-ServerWindow {
    [bool](Get-CimInstance Win32_Process -Filter "Name='cmd.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like '*start_server.bat*' })
}

$openedBrowser = $false
while ($true) {
    if (-not (Test-Listening 5000) -and -not (Test-ServerWindow)) {
        Start-Process -FilePath "$root\start_server.bat" -WorkingDirectory $root -WindowStyle Minimized
        for ($i = 0; $i -lt 60 -and -not (Test-Listening 5000); $i++) { Start-Sleep -Seconds 1 }
        # Open the system once per sign-in; later restarts happen quietly.
        if ((Test-Listening 5000) -and -not $openedBrowser) {
            Start-Process "http://127.0.0.1:5000"
            $openedBrowser = $true
        }
    }
    Start-Sleep -Seconds 3
}
