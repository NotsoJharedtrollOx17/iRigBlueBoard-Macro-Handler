param([ValidateSet("venv", "global")][string]$Scope = "venv", [switch]$User)
$ErrorActionPreference = "Stop"
$repoRoot = $PSScriptRoot
$pythonDir = Join-Path $repoRoot "python"
$venvDir = Join-Path $pythonDir ".venv"
$pythonExe = Join-Path $venvDir "Scripts\python.exe"

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "Python launcher 'py' was not found. Install Python 3.10+ and retry."
}

if ($Scope -eq "venv") {
    if (-not (Test-Path -LiteralPath $pythonExe)) { Write-Host "Creating Python virtual environment..."; & py -3 -m venv $venvDir }
    Write-Host "Installing the BlueBoard package into python\.venv..."
    & $pythonExe -m pip install --editable $repoRoot
    Write-Host "Setup complete. Run .\scanBlueBoard.ps1 or .\runBlueBoard.ps1"
    exit 0
}
$globalArgs = @("-m", "pip", "install", "--upgrade", $repoRoot)
if ($User) { $globalArgs += "--user" }
Write-Host "Installing the BlueBoard package into the selected global Python environment..."
& py -3 @globalArgs
Write-Host "Global installation complete. Verify with: blueboard --version"
Write-Host "If 'blueboard' is not recognized, add Python's Scripts directory to PATH."
