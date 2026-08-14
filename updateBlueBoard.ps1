param(
    [ValidateSet("venv", "global")][string]$Scope = "venv",
    [switch]$User
)
$ErrorActionPreference = "Stop"
$repoRoot = $PSScriptRoot

$changes = @(git -C $repoRoot status --porcelain)
if ($LASTEXITCODE -ne 0) { throw "Could not inspect the Git repository." }
if ($changes.Count -gt 0) {
    throw "Update stopped: commit or stash local changes before running this script."
}

Write-Host "Updating the local main branch from origin/main..."
git -C $repoRoot fetch origin main
if ($LASTEXITCODE -ne 0) {
    throw "Could not fetch origin/main."
}
$hasMain = git -C $repoRoot show-ref --verify --quiet refs/heads/main
if ($LASTEXITCODE -eq 0) {
    git -C $repoRoot switch main
} else {
    git -C $repoRoot switch --track -c main origin/main
}
if ($LASTEXITCODE -ne 0) {
    throw "Could not switch to the local main branch."
}
git -C $repoRoot pull --ff-only origin main
if ($LASTEXITCODE -ne 0) {
    throw "Git update from origin/main failed. Resolve the repository state, then retry."
}

$setupScript = Join-Path $repoRoot "setupBlueBoard.ps1"
$setupArgs = @("-Scope", $Scope)
if ($User) { $setupArgs += "-User" }
Write-Host "Refreshing the selected installation..."
& $setupScript @setupArgs
