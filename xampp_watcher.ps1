# FleetFuel watcher - runs hidden in the background (installed by install_autostart.bat).
# Keeps FleetFuel running: whenever the system is not running (after sign-in, or when its
# window was closed or the app stopped), it starts start_server.bat again within seconds.
# With a database on this computer (XAMPP), it waits until MySQL is started first; with the
# cloud database (MYSQL_HOST in .env is not this computer) it does not need XAMPP at all.
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

# Is the database on this computer? Read again each round, so editing .env needs no restart.
function Test-LocalDatabase {
    $line = Get-Content "$root\.env" -ErrorAction SilentlyContinue |
        Where-Object { $_ -match '^\s*MYSQL_HOST\s*=' } | Select-Object -First 1
    if (-not $line) { return $true }
    $dbHost = ($line -split '=', 2)[1].Trim().Trim('"').Trim("'")
    return ($dbHost -eq '' -or $dbHost -eq '127.0.0.1' -or $dbHost -eq 'localhost')
}

$openedBrowser = $false
while ($true) {
    $databaseReady = (-not (Test-LocalDatabase)) -or (Test-Listening 3306)
    if ($databaseReady -and -not (Test-Listening 5000) -and -not (Test-ServerWindow)) {
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
