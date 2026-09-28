# Build HMS release package - one folder for every hospital (new install + updates).
#
#   .\scripts\build_release.ps1 -Fast     # DAILY UPDATES (recommended) - Update.zip only
#   .\scripts\build_release.ps1           # FULL - Setup.exe + Update.zip (slow, first install)
#
# Auto-bumps patch version (1.0.0 -> 1.0.1). Last version: installer\VERSION
# Override:  .\scripts\build_release.ps1 -Version 2.0.0
# Rebuild same version:  .\scripts\build_release.ps1 -NoBump
#
param(
    [string]$Version = "",
    [switch]$NoBump,
    [switch]$Fast,
    [switch]$SkipBuild,
    [switch]$DesktopOnly,
    [switch]$BackendOnly
)

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$versionFile = Join-Path $root "installer\VERSION"

function Bump-PatchVersion([string]$Current) {
    $parts = $Current.Trim() -split '\.'
    if ($parts.Length -lt 2) { return "$Current.1" }
    $patch = 0
    [void][int]::TryParse($parts[-1], [ref]$patch)
    $parts[-1] = ($patch + 1).ToString()
    return ($parts -join '.')
}

if ($Version) {
    $Version | Set-Content -Path $versionFile -Encoding ASCII -NoNewline
    Write-Host "Version set to $Version" -ForegroundColor Cyan
}
elseif (-not $NoBump) {
    if (Test-Path $versionFile) {
        $current = (Get-Content $versionFile -Raw).Trim()
        $Version = Bump-PatchVersion $current
    }
    else {
        $Version = "1.0.0"
    }
    $Version | Set-Content -Path $versionFile -Encoding ASCII -NoNewline
    Write-Host "Version bumped to $Version" -ForegroundColor Cyan
}

$buildArgs = @{ Version = $Version }
if ($Fast) { $buildArgs.Fast = $true }
if ($SkipBuild) { $buildArgs.SkipBuild = $true }
if ($DesktopOnly) { $buildArgs.DesktopOnly = $true }
if ($BackendOnly) { $buildArgs.BackendOnly = $true }

& (Join-Path $root "installer\build\build.ps1") @buildArgs

Write-Host ""
Write-Host "Copy to server D:\HMS\updates (one file):" -ForegroundColor Green
Write-Host "  HMS-Update.zip" -ForegroundColor Green
if (-not $Fast) {
    Write-Host "First install only: HMS-Setup.exe" -ForegroundColor Green
}
