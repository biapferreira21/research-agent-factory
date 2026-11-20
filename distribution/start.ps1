$ErrorActionPreference = "Stop"
$kitRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonPath = Join-Path $kitRoot ".venv\Scripts\python.exe"
$healthUrl = "http://127.0.0.1:8765/api/health"
$appUrl = "http://127.0.0.1:8765/"

if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    throw "Run Install Agent Factory.cmd first."
}
function Test-FactoryHealth {
    try { return (Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2).status -eq "ok" }
    catch { return $false }
}
if (-not (Test-FactoryHealth)) {
    Start-Process -FilePath $pythonPath `
        -ArgumentList "-m", "app", "serve", "--host", "127.0.0.1", "--port", "8765", "--data", "data" `
        -WorkingDirectory $kitRoot `
        -RedirectStandardOutput (Join-Path $kitRoot "server.out.log") `
        -RedirectStandardError (Join-Path $kitRoot "server.err.log") `
        -WindowStyle Hidden
    $ready = $false
    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        Start-Sleep -Milliseconds 500
        if (Test-FactoryHealth) { $ready = $true; break }
    }
    if (-not $ready) { throw "Agent Factory did not start. Check server.err.log." }
}
Start-Process $appUrl
