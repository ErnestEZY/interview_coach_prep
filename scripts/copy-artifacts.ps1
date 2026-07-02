<#
.SYNOPSIS
    Copies built APK and/or MSI artifacts into the apps/ folder.
.PARAMETER TauriOnly
    Copy only the Tauri MSI/NSIS artifact.
.PARAMETER FlutterOnly
    Copy only the Flutter APK artifact.
.NOTES
    Run with no flags to copy both.
#>
param(
    [switch]$TauriOnly,
    [switch]$FlutterOnly
)

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent

# ── Paths ───────────────────────────────────────────────────────────────────
$ApkSrc   = Join-Path $Root "mobile_app\build\app\outputs\flutter-apk\app-release.apk"
$ApkDest  = Join-Path $Root "apps\apk\app-release.apk"

$MsiSrc   = Get-ChildItem (Join-Path $Root "src-tauri\target\release\bundle\msi") `
               -Filter "*.msi" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1 -ExpandProperty FullName
$NsisSrc  = Get-ChildItem (Join-Path $Root "src-tauri\target\release\bundle\nsis") `
               -Filter "*.exe" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1 -ExpandProperty FullName
$MsiDest  = Join-Path $Root "apps\msi"

# ── Flutter APK ──────────────────────────────────────────────────────────────
if (-not $TauriOnly) {
    if (Test-Path $ApkSrc) {
        New-Item -ItemType Directory -Path (Split-Path $ApkDest) -Force | Out-Null
        Copy-Item -Path $ApkSrc -Destination $ApkDest -Force
        Write-Host "[APK]  Copied -> apps\apk\app-release.apk" -ForegroundColor Green
    } else {
        Write-Warning "[APK]  Source not found: $ApkSrc"
    }
}

# ── Tauri MSI / NSIS ─────────────────────────────────────────────────────────
if (-not $FlutterOnly) {
    New-Item -ItemType Directory -Path $MsiDest -Force | Out-Null

    if ($MsiSrc) {
        $MsiFileName = Split-Path $MsiSrc -Leaf
        Copy-Item -Path $MsiSrc -Destination (Join-Path $MsiDest $MsiFileName) -Force
        Write-Host "[MSI]  Copied -> apps\msi\$MsiFileName" -ForegroundColor Green
    } else {
        Write-Warning "[MSI]  No .msi found in src-tauri\target\release\bundle\msi"
    }

    if ($NsisSrc) {
        $NsisFileName = Split-Path $NsisSrc -Leaf
        Copy-Item -Path $NsisSrc -Destination (Join-Path $MsiDest $NsisFileName) -Force
        Write-Host "[NSIS] Copied -> apps\msi\$NsisFileName" -ForegroundColor Green
    }
}

Write-Host "`nArtifact copy complete." -ForegroundColor Cyan
