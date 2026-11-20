param(
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"
$healthUrl = "http://127.0.0.1:8765/api/health"
$appUrl = "http://127.0.0.1:8765/"
$stdoutPath = Join-Path $projectRoot "server.out.log"
$stderrPath = Join-Path $projectRoot "server.err.log"

if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    throw "Python environment not found at $pythonPath. Create .venv and install the project first."
}

function Test-FactoryHealth {
    try {
        $health = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2
        return $health.status -eq "ok"
    }
    catch {
        return $false
    }
}

if (-not (Test-FactoryHealth)) {
    Start-Process -FilePath $pythonPath `
        -ArgumentList "-m", "app.cli", "serve", "--host", "127.0.0.1", "--port", "8765", "--data", "data" `
        -WorkingDirectory $projectRoot `
        -RedirectStandardOutput $stdoutPath `
        -RedirectStandardError $stderrPath `
        -WindowStyle Hidden

    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        Start-Sleep -Milliseconds 500
        if (Test-FactoryHealth) {
            $ready = $true
            break
        }
    }
    if (-not $ready) {
        $details = if (Test-Path -LiteralPath $stderrPath) {
            (Get-Content -LiteralPath $stderrPath -Tail 12) -join [Environment]::NewLine
        }
        else {
            "No server error log was created."
        }
        throw "Agent Factory did not start.`n$details"
    }
}

Write-Host "Agent Factory is ready at $appUrl"
if (-not $NoBrowser) {
    Start-Process $appUrl
}
