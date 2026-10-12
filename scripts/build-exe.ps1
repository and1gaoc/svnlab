$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$buildPath = Join-Path $projectRoot "build"
$distPath = Join-Path $projectRoot "dist"

foreach ($target in @($buildPath, $distPath)) {
    $absoluteTarget = [System.IO.Path]::GetFullPath($target)
    $absoluteRoot = [System.IO.Path]::GetFullPath($projectRoot).TrimEnd('\') + '\'
    if (-not $absoluteTarget.StartsWith($absoluteRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to clean a path outside the project: $absoluteTarget"
    }
    if (Test-Path -LiteralPath $absoluteTarget) {
        Get-ChildItem -LiteralPath $absoluteTarget -Force |
            Remove-Item -Recurse -Force
    } else {
        New-Item -ItemType Directory -Path $absoluteTarget | Out-Null
    }
}

Push-Location $projectRoot
try {
    uv run --extra build pyinstaller --clean --noconfirm svnlab.spec
} finally {
    Pop-Location
}

$executable = Join-Path $distPath "SVNLab.exe"
if (-not (Test-Path -LiteralPath $executable)) {
    throw "Build completed without producing $executable"
}

Write-Host "Built: $executable"
