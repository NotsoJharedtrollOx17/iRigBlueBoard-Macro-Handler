$ErrorActionPreference = "Stop"
$pythonExe = Join-Path $PSScriptRoot "python\.venv\Scripts\python.exe"
$mainScript = Join-Path $PSScriptRoot "python\src\main.py"

if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "Python environment not found. Run .\setupBlueBoard.ps1 first."
}

& $pythonExe $mainScript run @args
