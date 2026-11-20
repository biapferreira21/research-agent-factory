$ErrorActionPreference = "Stop"
$kitRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPython = Join-Path $kitRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
    $pythonCommand = $null
    $pythonArguments = @()
    if (Get-Command py.exe -ErrorAction SilentlyContinue) {
        foreach ($version in @("-3.13", "-3.12")) {
            & py.exe $version -c "import sys; assert (3, 12) <= sys.version_info[:2] <= (3, 13)" 2>$null
            if ($LASTEXITCODE -eq 0) {
                $pythonCommand = "py.exe"
                $pythonArguments = @($version)
                break
            }
        }
    }
    if (-not $pythonCommand -and (Get-Command python.exe -ErrorAction SilentlyContinue)) {
        & python.exe -c "import sys; assert (3, 12) <= sys.version_info[:2] <= (3, 13)" 2>$null
        if ($LASTEXITCODE -eq 0) { $pythonCommand = "python.exe" }
    }
    if (-not $pythonCommand) {
        throw "Python 3.12 or 3.13 was not found. Install it from python.org and run this installer again."
    }
    & $pythonCommand @pythonArguments -m venv (Join-Path $kitRoot ".venv")
}

$wheel = Get-ChildItem -LiteralPath (Join-Path $kitRoot "packages") -Filter "*.whl" | Select-Object -First 1
if (-not $wheel) { throw "The SDK wheel is missing from packages." }
& $venvPython -m pip install $wheel.FullName
if ($LASTEXITCODE -ne 0) { throw "Package installation failed." }
Write-Host "`nREADY // Double-click Start Agent Factory.cmd"
