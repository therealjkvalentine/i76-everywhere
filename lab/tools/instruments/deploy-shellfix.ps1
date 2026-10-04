<#
  deploy-shellfix.ps1 — install (or remove) the shell mouse fix in a game directory.

  Does two things, both reversible, with backups:
    1. copies src\u32x.dll (the USER32 coordinate proxy) beside the game
    2. patches i76shell.dll's import string "USER32.dll" -> "u32x.dll" so the shell loads the
       proxy (keeps i76shell.dll.orig)

  Only i76shell.dll is retargeted - the engine's own USER32 imports are untouched, so gameplay
  input (DirectInput driving) is unaffected.

    tools\instruments\deploy-shellfix.ps1 -GameDir <dir>            # install
    tools\instruments\deploy-shellfix.ps1 -GameDir <dir> -Restore   # put the original back
    tools\instruments\deploy-shellfix.ps1 -GameDir <dir> -Status
#>
param(
    [Parameter(Mandatory = $true)][string]$GameDir,
    [switch]$Restore,
    [switch]$Status
)
$ErrorActionPreference = 'Stop'
$proxySrc = Join-Path $PSScriptRoot '..\..\src\u32x.dll'
$proxyDst = Join-Path $GameDir 'u32x.dll'

# BOTH binaries must be retargeted. Measured live 2026-08-16: while navigating menus the SHELL
# makes zero GetCursorPos/ClipCursor calls - i76.exe owns the cursor, and it is the engine's own
# ClipCursor(0,0,640,480) that traps the pointer in the physical top-left 640x480 box ("mouse is
# too sensitive / doesn't highlight"). Patching only the shell fixed nothing the user could see.
$TARGETS = @(
    @{ Name = 'i76shell.dll'; Path = (Join-Path $GameDir 'i76shell.dll'); Backup = (Join-Path $GameDir 'i76shell.dll.orig') },
    @{ Name = 'i76.exe';      Path = (Join-Path $GameDir 'i76.exe');      Backup = (Join-Path $GameDir 'i76.exe.u32xorig') }
)

$enc = [Text.Encoding]::ASCII
$USER32 = $enc.GetBytes("USER32.dll")
$U32X   = $enc.GetBytes("u32x.dll`0`0")   # same length, NUL-padded

function Find-Str([byte[]]$hay, [byte[]]$needle) {
    for ($i = 0; $i -le $hay.Length - $needle.Length; $i++) {
        $hit = $true
        for ($j = 0; $j -lt $needle.Length; $j++) { if ($hay[$i+$j] -ne $needle[$j]) { $hit = $false; break } }
        if ($hit) { return $i }
    }
    return -1
}
function Is-Patched($path) {
    if (-not (Test-Path $path)) { return $false }
    (Find-Str ([IO.File]::ReadAllBytes($path)) ($enc.GetBytes("u32x.dll"))) -ge 0
}

if ($Status) {
    foreach ($t in $TARGETS) {
        if (-not (Test-Path $t.Path)) { "{0,-13}: MISSING" -f $t.Name; continue }
        "{0,-13}: {1}" -f $t.Name, $(if (Is-Patched $t.Path) { "PATCHED (loads u32x.dll)" } else { "stock (loads USER32.dll)" })
    }
    "{0,-13}: {1}" -f 'u32x.dll', $(if (Test-Path $proxyDst) { "present" } else { "absent" })
    exit 0
}

if (Get-Process i76 -EA SilentlyContinue | Where-Object { $_.Path -like "$GameDir*" }) {
    throw "the game in $GameDir is running - close it first"
}

if ($Restore) {
    foreach ($t in $TARGETS) {
        if (Test-Path $t.Backup) { Copy-Item $t.Backup $t.Path -Force; "restored $($t.Name) from $(Split-Path $t.Backup -Leaf)" }
        else { "no backup found for $($t.Name)" }
    }
    exit 0
}

foreach ($t in $TARGETS) {
    if (-not (Test-Path $t.Path)) { throw "$($t.Name) not found in $GameDir" }
    if (Is-Patched $t.Path) { "$($t.Name): already patched"; continue }
    $bytes = [IO.File]::ReadAllBytes($t.Path)
    $off = Find-Str $bytes $USER32
    if ($off -lt 0) { throw "USER32.dll import string not found in $($t.Name) - unexpected variant" }
    # NOTE for i76.exe: the string occurs exactly once and it IS the import-descriptor name
    # (verified). The import directory references it by RVA, so overwriting the string retargets
    # the descriptor. u32x.def exports the UNION of both modules' USER32 imports.
    if (-not (Test-Path $t.Backup)) { Copy-Item $t.Path $t.Backup; "backed up -> $(Split-Path $t.Backup -Leaf)" }
    while (($off = Find-Str $bytes $USER32) -ge 0) {
        for ($j = 0; $j -lt $U32X.Length; $j++) { $bytes[$off + $j] = $U32X[$j] }
    }
    [IO.File]::WriteAllBytes($t.Path, $bytes)
    "patched $($t.Name): USER32.dll -> u32x.dll"
}
Copy-Item $proxySrc $proxyDst -Force
"deployed u32x.dll"
