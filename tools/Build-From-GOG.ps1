<#
  Build-From-GOG.ps1 - ONE command: a fresh GOG install folder of Interstate '76 (Gold, i76.exe) in, a working i76-everywhere
  copy out (owner 2026-10-23 night: "make sure that our repo can build a working copy of the game from a new GOG install for Gold
  and Nitro"). The source folder is only read; the copy is made beside it (-OutDir) and set up there.

  Gold, the steps (each is an existing repo tool, nothing forked):
    1. tools\build-proxy.ps1 -Ref <sha>       the proxy Strlkup.dll from that commit (MSVC x86, deterministic)
    2. tools\package-scott.ps1                 the tester overlay (launchers, presets, u32x, dgVoodoo 2.87.3, AutoHotkey, the shell
                                               key patch data, controls, saves) staged from this repo + that proxy; NO game bytes
    3. copy -GogDir -> -OutDir, the stage over it (the same as unzipping the tester zip into a GOG folder)
    4. _i76e\i76e-prepare.ps1 -Preset <p>      the first-run setup (setup-windows.ps1, Apply-Shell-Keys, u32x, dgVoodoo, controls)
                                               + the display fit (Make-Wide-Conf: dgVoodoo.wide.conf + the presets' I76_ASPECT)
    Then <OutDir>\PLAY.bat (stable, tick19-42) / PLAY-PREVIEW.bat (scott-preview) / PLAY-T05*.bat start it; UNINSTALL-i76e.bat
    puts the GOG files back. README-SCOTT.md in the copy explains the launchers and keys.

  Nitro Pack (nitro.exe): see -Game Nitro below (docs\records\FRESH-GOG-BUILD-2026-10-23.md).

    tools\Build-From-GOG.ps1 -GogDir "C:\GOG Games\Interstate 76" -OutDir "C:\Games\I76-everywhere" [-Ref HEAD] [-Preset tick19-42]
                             [-Display 3440x1440] [-NoSupersample] [-DgVoodooDir <unpacked dgVoodoo2_87_3.zip>] [-AhkDir <AutoHotkeyU32.exe dir>]
  dgVoodoo 2.87.3 and AutoHotkey 1.1.37.02 are downloaded into %LOCALAPPDATA%\i76e-cache on first use when not given (the packer
  checks every dgVoodoo file's md5 against the release). Needs: git, the VS 2019 Build Tools (C++ x86), PowerShell 5.1.
#>
param([Parameter(Mandatory)][string]$GogDir, [Parameter(Mandatory)][string]$OutDir, [string]$Ref = 'HEAD',
      [ValidateSet('auto', 'Gold', 'Nitro')][string]$Game = 'auto', [string]$Preset = '',
      [string]$Display = '', [switch]$NoSupersample, [string]$DgVoodooDir = '', [string]$AhkDir = '', [switch]$Force)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
function Say([string]$m, [string]$c = 'Gray') { Write-Host $m -ForegroundColor $c }
function Die([string]$m) { Write-Host "Build-From-GOG: $m" -ForegroundColor Red; exit 1 }
function Md5([string]$p) { (Get-FileHash -LiteralPath $p -Algorithm MD5).Hash.ToLower() }

$GogDir = (Resolve-Path -LiteralPath $GogDir).Path.TrimEnd('\')
if ($Game -eq 'auto') { $Game = if (Test-Path -LiteralPath "$GogDir\i76.exe") { 'Gold' } elseif (Test-Path -LiteralPath "$GogDir\nitro.exe") { 'Nitro' } else { Die "no i76.exe or nitro.exe in $GogDir" } }
$exeName = if ($Game -eq 'Gold') { 'i76.exe' } else { 'nitro.exe' }
if (-not (Test-Path -LiteralPath "$GogDir\$exeName")) { Die "no $exeName in $GogDir" }
foreach ($mark in 'i76.exe.u32xorig', 'strlkup_orig.dll', '_i76e', 'nitro.exe.u32xorig') {
    if (Test-Path -LiteralPath "$GogDir\$mark") { Die "$GogDir is not a fresh GOG install ($mark present) - point -GogDir at an untouched copy" }
}
if (Test-Path -LiteralPath $OutDir) { if (-not $Force) { Die "$OutDir exists (pass -Force to replace it)" }; Remove-Item -LiteralPath $OutDir -Recurse -Force }
$sha = (git -C $repo rev-parse --short $Ref).Trim()
$work = Join-Path $env:LOCALAPPDATA "i76e-cache\build-$sha"
New-Item -ItemType Directory -Force $work | Out-Null
Say "=== Build-From-GOG: $Game from $GogDir -> $OutDir (repo $sha) ===" 'Cyan'
Say "    $exeName md5 $(Md5 "$GogDir\$exeName")"

# ---- third-party components: given, or downloaded once into the cache ----------------------------------------------------
$cache = Join-Path $env:LOCALAPPDATA 'i76e-cache'
if (-not $DgVoodooDir) {
    $DgVoodooDir = Join-Path $cache 'dgVoodoo2_87_3'
    if (-not (Test-Path -LiteralPath "$DgVoodooDir\3Dfx\x86\Glide2x.dll")) {
        $z = Join-Path $cache 'dgVoodoo2_87_3.zip'
        Say "    downloading dgVoodoo 2.87.3 (github.com/dege-diosg/dgVoodoo2)"
        Invoke-WebRequest -UseBasicParsing 'https://github.com/dege-diosg/dgVoodoo2/releases/download/v2.87.3/dgVoodoo2_87_3.zip' -OutFile $z
        Expand-Archive -LiteralPath $z -DestinationPath $DgVoodooDir -Force
    }
}
if (-not $AhkDir) {
    $AhkDir = Join-Path $cache 'AutoHotkey_1.1.37.02'
    if (-not (Test-Path -LiteralPath "$AhkDir\AutoHotkeyU32.exe")) {
        $z = Join-Path $cache 'AutoHotkey_1.1.37.02.zip'
        Say "    downloading AutoHotkey 1.1.37.02 (autohotkey.com)"
        Invoke-WebRequest -UseBasicParsing 'https://www.autohotkey.com/download/1.1/AutoHotkey_1.1.37.02.zip' -OutFile $z
        Expand-Archive -LiteralPath $z -DestinationPath $AhkDir -Force
    }
}

# ---- 1. the proxy from the commit -------------------------------------------------------------------------------------------
$pdir = Join-Path $work 'proxy'
$b = & (Join-Path $PSScriptRoot 'build-proxy.ps1') -Ref $sha -OutDir $pdir
if ($LASTEXITCODE) { Die 'the proxy build failed (see above)' }
Say "    $b"
$proxy = Join-Path $pdir 'Strlkup.dll'

if ($Game -eq 'Gold') {
    # ---- 2. the overlay stage (package-scott.ps1: the guard keeps every game file out) ----------------------------------------
    $stage = Join-Path $work 'stage'
    & (Join-Path $PSScriptRoot 'package-scott.ps1') -Proxy $proxy -ProxyCommit $sha -DgVoodooDir $DgVoodooDir -AhkDir $AhkDir -OutDir (Join-Path $work 'zip') -Stamp "build-$sha" -Stage $stage
    if ($LASTEXITCODE) { Die 'package-scott.ps1 failed' }
    # ---- 3. the copy, the overlay over it ------------------------------------------------------------------------------------------
    Say "    copying $GogDir -> $OutDir"
    Copy-Item -LiteralPath $GogDir -Destination $OutDir -Recurse
    Copy-Item -Path (Join-Path $stage '*') -Destination $OutDir -Recurse -Force
    # ---- 4. the first-run setup + display fit (what the first PLAY.bat does), without starting the game -----------------------------
    $pa = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $OutDir '_i76e\i76e-prepare.ps1'), '-Preset', $(if ($Preset) { $Preset } else { 'tick19-42' }))
    if ($Display) { $pa += @('-Display', $Display) }
    if ($NoSupersample) { $pa += '-NoSupersample' }
    & powershell.exe @pa
    if ($LASTEXITCODE) { Die "i76e-prepare.ps1 exited $LASTEXITCODE - the copy is set up only partly; read the lines above" }
    Say "=== done: $OutDir\PLAY.bat (stable) / PLAY-PREVIEW.bat (graphics preview); README-SCOTT.md there; UNINSTALL-i76e.bat undoes it ===" 'Green'
    exit 0
}

# ---- Nitro ----------------------------------------------------------------------------------------------------------------------
Die 'Nitro: not wired yet (FRESH-GOG-BUILD-2026-10-23.md)'
