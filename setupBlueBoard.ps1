$ErrorActionPreference = "Stop"
$repoRoot = $PSScriptRoot
$pythonDir = Join-Path $repoRoot "python"
$venvDir = Join-Path $pythonDir ".venv"
$pythonExe = Join-Path $venvDir "Scripts\python.exe"

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "Python launcher 'py' was not found. Install Python 3.10+ and retry."
}

if (-not (Test-Path -LiteralPath $pythonExe)) {
    Write-Host "Creating Python virtual environment..."
    & py -3 -m venv $venvDir
}

Write-Host "Installing the BlueBoard package and dependencies..."
& $pythonExe -m pip install --editable $repoRoot
Write-Host "Setup complete. Run .\scanBlueBoard.ps1 or .\runBlueBoard.ps1"
