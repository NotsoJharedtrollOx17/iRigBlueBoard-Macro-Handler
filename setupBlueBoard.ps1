param([ValidateSet("venv", "global")][string]$Scope = "venv", [switch]$User)
$ErrorActionPreference = "Stop"
$repoRoot = $PSScriptRoot
$pythonDir = Join-Path $repoRoot "python"
$venvDir = Join-Path $pythonDir ".venv"
$pythonExe = Join-Path $venvDir "Scripts\python.exe"

function Add-ScriptsDirectoryToPath {
    param([Parameter(Mandatory = $true)][string]$ScriptsDirectory)

    if (-not (Test-Path -LiteralPath $ScriptsDirectory)) {
        throw "Python installed the package, but its Scripts directory was not found: $ScriptsDirectory"
    }

    $pathEntries = @($env:Path -split ';' | Where-Object { $_ })
    if ($pathEntries -notcontains $ScriptsDirectory) {
        $env:Path = "$ScriptsDirectory;$env:Path"
    }

    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $userEntries = @($userPath -split ';' | Where-Object { $_ })
    if ($userEntries -notcontains $ScriptsDirectory) {
        $updatedUserPath = if ([string]::IsNullOrWhiteSpace($userPath)) {
            $ScriptsDirectory
        } else {
            "$userPath;$ScriptsDirectory"
        }
        [Environment]::SetEnvironmentVariable("Path", $updatedUserPath, "User")
        Write-Host "Added Python's Scripts directory to your user PATH: $ScriptsDirectory"
        Write-Host "New terminal sessions will also recognize the 'blueboard' command."
    }
}

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
if ($LASTEXITCODE -ne 0) {
    throw "Package installation failed with exit code $LASTEXITCODE."
}

$systemScriptsDirectory = (& py -3 -c "import sysconfig; print(sysconfig.get_path('scripts'))").Trim()
$userScriptsDirectory = (& py -3 -c "import sysconfig; print(sysconfig.get_path('scripts', scheme='nt_user'))").Trim()
$scriptCandidates = @($systemScriptsDirectory, $userScriptsDirectory) | Select-Object -Unique
$scriptsDirectory = $scriptCandidates | Where-Object {
    Test-Path -LiteralPath (Join-Path $_ "blueboard.exe")
} | Select-Object -First 1

if (-not $scriptsDirectory) {
    throw "Package installation completed, but blueboard.exe was not found. Checked: $($scriptCandidates -join ', ')"
}

Add-ScriptsDirectoryToPath -ScriptsDirectory $scriptsDirectory

Write-Host "Global installation complete. Verification:"
& (Join-Path $scriptsDirectory "blueboard.exe") --version
if ($LASTEXITCODE -ne 0) {
    throw "The blueboard command failed its version check with exit code $LASTEXITCODE."
}
