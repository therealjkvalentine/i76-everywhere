<#
  Build-From-GOG.ps1 - ONE command: a fresh GOG install folder of Interstate '76 (Gold, i76.exe) in, a working i76-everywhere
  copy out (owner 2026-10-23 night: "make sure that our repo can build a working copy of the game from a new GOG install for Gold
  and Nitro"). The source folder is only read; the copy is made beside it (-OutDir) and set up there.

  Gold, the steps (each is an existing repo tool, nothing forked):
    1. tools\build-proxy.ps1 -Ref <sha>       the proxy Strlkup.dll from that commit (MSVC x86, deterministic)
    2. tools\package-patch-kit.ps1                 the tester overlay (launchers, presets, u32x, dgVoodoo 2.87.5 (+ 2.87.3 fallback), AutoHotkey, the shell
                                               key patch data, controls, saves) staged from this repo + that proxy; NO game bytes
    3. copy -GogDir -> -OutDir, the stage over it (the same as unzipping the tester zip into a GOG folder)
    4. _i76e\i76e-prepare.ps1 -Preset <p>      the first-run setup (setup-windows.ps1, Apply-Shell-Keys, u32x, dgVoodoo, controls)
                                               + the display fit (Make-Wide-Conf: dgVoodoo.wide.conf + the presets' I76_ASPECT)
    Then <OutDir>\PLAY.bat (stable, tick19-42) / PLAY-PREVIEW.bat (preview) / PLAY-T05*.bat start it; UNINSTALL-i76e.bat
    puts the GOG files back. README-PATCH-KIT.md in the copy explains the launchers and keys.

  Nitro Pack (nitro.exe): the same steps; step 4 runs i76e-prepare.ps1 -Game Nitro (since 2026-10-25 the kit's own Nitro route).
  Gold only, Nitro only, or both (owner 2026-10-25): -GogDir is a game folder (i76.exe or nitro.exe), or a folder that holds the
  game folders (e.g. "C:\GOG Games" with "Interstate 76" and/or "Interstate 76 Nitro Pack"): every game found there is built into
  -OutDir\<its folder name>, and a game that is not there is named and skipped (with -Game Gold / Nitro only that one).

    tools\Build-From-GOG.ps1 -GogDir "C:\GOG Games\Interstate 76" -OutDir "C:\Games\I76-everywhere" [-Ref HEAD] [-Preset tick19-42]
                             [-Display 3440x1440] [-NoSupersample] [-DgVoodooDir <unpacked dgVoodoo2_87_5.zip>] [-DgVoodooFallbackDir <unpacked dgVoodoo2_87_3.zip>] [-AhkDir <AutoHotkeyU32.exe dir>]
  dgVoodoo 2.87.5 (the build's; 2.87.3's DirectDraw crashes at the first frame on Windows 11 26100.9711, docs/records/NITRO-WIN11-2026-10-25.md),
  dgVoodoo 2.87.3 (the kit's swap-back fallback) and AutoHotkey 1.1.37.02 are downloaded into %LOCALAPPDATA%\i76e-cache on first use when not given (the packer
  checks every dgVoodoo file's md5 against the release). Needs: git and PowerShell 5.1; the VS 2019 Build Tools (C++ x86) only to build the proxy -
  without them (or with -Proxy <Strlkup.dll>) the prebuilt proxy is used. A player needs none of this: the Patch Kit zip does the same for Gold and Nitro.
#>
param([Parameter(Mandatory)][string]$GogDir, [Parameter(Mandatory)][string]$OutDir, [string]$Ref = 'HEAD',
      [ValidateSet('auto', 'Gold', 'Nitro')][string]$Game = 'auto', [string]$Preset = '',
      [string]$Display = '', [switch]$NoSupersample, [string]$DgVoodooDir = '', [string]$DgVoodooFallbackDir = '', [string]$AhkDir = '', [string]$Proxy = '', [switch]$Force)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
function Say([string]$m, [string]$c = 'Gray') { Write-Host $m -ForegroundColor $c }
function Die([string]$m) { Write-Host "Build-From-GOG: $m" -ForegroundColor Red; exit 1 }
function Md5([string]$p) { (Get-FileHash -LiteralPath $p -Algorithm MD5).Hash.ToLower() }

if (-not (Test-Path -LiteralPath $GogDir -PathType Container)) { Die "-GogDir $GogDir is not a folder" }
$GogDir = (Resolve-Path -LiteralPath $GogDir).Path.TrimEnd('\')
# the games to build: [kind, source folder, output folder]
$jobs = @()
$direct = if (Test-Path -LiteralPath "$GogDir\i76.exe") { 'Gold' } elseif (Test-Path -LiteralPath "$GogDir\nitro.exe") { 'Nitro' } else { '' }
if ($direct) { $jobs += , @($direct, $GogDir, $OutDir) }
else {
    foreach ($d in @(Get-ChildItem -LiteralPath $GogDir -Directory -ErrorAction SilentlyContinue)) {
        $k = if (Test-Path -LiteralPath (Join-Path $d.FullName 'i76.exe')) { 'Gold' } elseif (Test-Path -LiteralPath (Join-Path $d.FullName 'nitro.exe')) { 'Nitro' } else { '' }
        if ($k -and -not @($jobs | Where-Object { $_[0] -eq $k }).Count) { $jobs += , @($k, $d.FullName, (Join-Path $OutDir $d.Name)) }
    }
}
if ($Game -ne 'auto') { $jobs = @($jobs | Where-Object { $_[0] -eq $Game }) }
foreach ($k in 'Gold', 'Nitro') {
    if (($Game -eq 'auto' -or $Game -eq $k) -and -not @($jobs | Where-Object { $_[0] -eq $k }).Count) {
        $what = if ($k -eq 'Gold') { "Interstate '76 Gold (i76.exe)" } else { "the Nitro Pack (nitro.exe)" }
        Say "    $what : not in $GogDir$(if (-not $direct) { ' or its sub-folders' }) - skipped" 'Yellow'
    }
}
if (-not $jobs.Count) { Die "nothing to build: no i76.exe or nitro.exe in $GogDir$(if (-not $direct) { ' or its sub-folders' })" }
foreach ($j in $jobs) {
    foreach ($mark in 'i76.exe.u32xorig', 'strlkup_orig.dll', '_i76e', 'nitro.exe.u32xorig') {
        if (Test-Path -LiteralPath "$($j[1])\$mark") { Die "$($j[1]) is not a fresh GOG install ($mark present) - point -GogDir at an untouched copy" }
    }
    if (Test-Path -LiteralPath $j[2]) { if (-not $Force) { Die "$($j[2]) exists (pass -Force to replace it)" } }
}
$sha = (git -C $repo rev-parse --short $Ref).Trim()
$work = Join-Path $env:LOCALAPPDATA "i76e-cache\build-$sha"
New-Item -ItemType Directory -Force $work | Out-Null
foreach ($j in $jobs) {
    $exeName = if ($j[0] -eq 'Gold') { 'i76.exe' } else { 'nitro.exe' }
    Say "=== Build-From-GOG: $($j[0]) from $($j[1]) -> $($j[2]) (repo $sha); $exeName md5 $(Md5 "$($j[1])\$exeName") ===" 'Cyan'
}

# ---- third-party components: given, or downloaded once into the cache ----------------------------------------------------
$cache = Join-Path $env:LOCALAPPDATA 'i76e-cache'
# dgVoodoo: Dege's official GitHub release zips, sha256-pinned (the release assets' digests, read 2026-10-25); package-patch-kit.ps1
# then checks every shipped component's md5 against the release.
function Get-DgVoodoo([string]$ver, [string]$sha256) {
    $u = $ver.Substring(2).Replace('.', '_'); $dir = Join-Path $cache "dgVoodoo2_$u"
    if (Test-Path -LiteralPath "$dir\3Dfx\x86\Glide2x.dll") { return $dir }
    New-Item -ItemType Directory -Force $cache | Out-Null
    $z = Join-Path $cache "dgVoodoo2_$u.zip"
    Say "    downloading dgVoodoo $ver (github.com/dege-diosg/dgVoodoo2)"
    Invoke-WebRequest -UseBasicParsing "https://github.com/dege-diosg/dgVoodoo2/releases/download/v$ver/dgVoodoo2_$u.zip" -OutFile $z
    $got = (Get-FileHash -LiteralPath $z -Algorithm SHA256).Hash.ToLower()
    if ($got -ne $sha256) { Remove-Item -LiteralPath $z -Force; Die "dgVoodoo2_$u.zip sha256 $got is not the release's $sha256" }
    Expand-Archive -LiteralPath $z -DestinationPath $dir -Force
    return $dir
}
if (-not $DgVoodooDir) { $DgVoodooDir = Get-DgVoodoo '2.87.5' '5ffde6927f7355ca3fdd5d785b581256a8e6539fa13e395a891ade6ba1040850' }
if (-not $DgVoodooFallbackDir) { $DgVoodooFallbackDir = Get-DgVoodoo '2.87.3' '6fb954bed55bf70e948c5045a663a9df31ea206faf105e327bafe46c318f867f' }
if (-not $AhkDir) {
    $AhkDir = Join-Path $cache 'AutoHotkey_1.1.37.02'
    if (-not (Test-Path -LiteralPath "$AhkDir\AutoHotkeyU32.exe")) {
        $z = Join-Path $cache 'AutoHotkey_1.1.37.02.zip'
        Say "    downloading AutoHotkey 1.1.37.02 (autohotkey.com)"
        Invoke-WebRequest -UseBasicParsing 'https://www.autohotkey.com/download/1.1/AutoHotkey_1.1.37.02.zip' -OutFile $z
        Expand-Archive -LiteralPath $z -DestinationPath $AhkDir -Force
    }
}

# ---- 1. the proxy: -Proxy <dll>, else built from the commit (MSVC), else the commit's own prebuilt music-fix\Strlkup.dll ---------
# clean-install 2026-10-25 (B6): a player has no compiler; the Patch Kit zip is the no-compiler route for Gold AND Nitro, and this
# script now takes the same prebuilt proxy when the VS 2019 Build Tools are missing.
$pdir = Join-Path $work 'proxy'
$vcvars = 'C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\VC\Auxiliary\Build\vcvars32.bat'
if ($Proxy) {
    if (-not (Test-Path -LiteralPath $Proxy)) { Die "-Proxy $Proxy not found" }
    $proxy = (Resolve-Path -LiteralPath $Proxy).Path; $proxyFrom = 'given (-Proxy)'
} elseif (Test-Path -LiteralPath $vcvars) {
    $b = & (Join-Path $PSScriptRoot 'build-proxy.ps1') -Ref $sha -OutDir $pdir
    if ($LASTEXITCODE) { Die 'the proxy build failed (see above)' }
    Say "    $b"
    $proxy = Join-Path $pdir 'Strlkup.dll'; $proxyFrom = "built from $sha"
} else {
    New-Item -ItemType Directory -Force $pdir | Out-Null
    $proxy = Join-Path $pdir 'Strlkup.dll'
    $p = Start-Process git -ArgumentList @('-C', "`"$repo`"", 'show', "${sha}:music-fix/Strlkup.dll") -NoNewWindow -Wait -PassThru -RedirectStandardOutput $proxy
    if ($p.ExitCode -or -not (Test-Path -LiteralPath $proxy) -or (Get-Item -LiteralPath $proxy).Length -lt 100000) { Die "no compiler (VS 2019 Build Tools) and no prebuilt music-fix\Strlkup.dll at $sha - pass -Proxy <Strlkup.dll> (the Patch Kit zip carries one in _i76e\repo\music-fix)" }
    $proxyFrom = "the prebuilt music-fix\Strlkup.dll committed at $sha (no compiler on this PC)"
}
Say "    proxy: $proxyFrom, md5 $(Md5 $proxy)"

# ---- 2. the overlay stage (package-patch-kit.ps1: the guard keeps every game file out) ------------------------------------------
$stage = Join-Path $work 'stage'
& (Join-Path $PSScriptRoot 'package-patch-kit.ps1') -Proxy $proxy -ProxyCommit $sha -DgVoodooDir $DgVoodooDir -DgVoodooFallbackDir $DgVoodooFallbackDir -AhkDir $AhkDir -OutDir (Join-Path $work 'zip') -Stamp "build-$sha" -Stage $stage
if ($LASTEXITCODE) { Die 'package-patch-kit.ps1 failed' }
$failed = @()
foreach ($j in $jobs) {
$Game = $j[0]; $src = $j[1]; $OutDir = $j[2]
# ---- 3. the copy, the overlay over it (the same as unzipping the kit into the GOG folder) ------------------------------------------
if (Test-Path -LiteralPath $OutDir) { Remove-Item -LiteralPath $OutDir -Recurse -Force }   # -Force was checked above
New-Item -ItemType Directory -Force (Split-Path -Parent $OutDir) | Out-Null
Say "    copying $src -> $OutDir"
Copy-Item -LiteralPath $src -Destination $OutDir -Recurse
Copy-Item -Path (Join-Path $stage '*') -Destination $OutDir -Recurse -Force
# ---- 4. the first-run setup + display fit (what the first PLAY.bat / PLAY-Nitro.bat does), without starting the game ----------------
# Gold: preset tick19-42; Nitro (2026-10-25: the kit's Nitro route, i76e-prepare.ps1 -Game Nitro): preset nitro-tick42, GOG's Nitro
# keys, dgVoodoo 2.87.5 incl. D3D8 / D3D9, the Nitro shell keys. -Display not given = the monitor of the PC the copy is played on
# is read again by every PLAY*.bat (clean-install B8: building elsewhere no longer bakes this PC's monitor in).
$pa = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $OutDir '_i76e\i76e-prepare.ps1'), '-Game', $Game, '-NoPause')
if ($Preset) { $pa += @('-Preset', $Preset) }
if ($Display) { $pa += @('-Display', $Display) }
if ($NoSupersample) { $pa += '-NoSupersample' }
& powershell.exe @pa
if ($LASTEXITCODE) { Say "Build-From-GOG: $Game - i76e-prepare.ps1 exited $LASTEXITCODE; $OutDir is set up only partly (read the lines above and $OutDir\_i76e\setup.log)" 'Red'; $failed += $Game; continue }
if ($Game -eq 'Gold') { Say "=== done: $OutDir\PLAY.bat (stable) / PLAY-PREVIEW.bat (graphics preview); README-PATCH-KIT.md there; UNINSTALL-i76e.bat undoes it ===" 'Green' }
else { Say "=== done: $OutDir\PLAY-Nitro.bat (preset $(if ($Preset -and $Preset -ne 'tick19-42') { $Preset } else { 'nitro-tick42' })); README-PATCH-KIT.md there; UNINSTALL-i76e.bat undoes it ===" 'Green' }
}
if ($failed.Count) { exit 1 }
exit 0