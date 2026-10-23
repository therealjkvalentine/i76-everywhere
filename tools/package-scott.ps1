<#
  package-scott.ps1 - the tester build (owner 2026-10-23: "a build that Scott can run ... the latest stable copy so he can
  give feedback"; the zips go on GitHub, so nothing of GOG's may be inside).

  ONE zip, unzipped INTO a GOG Interstate '76 folder (PLAY.bat lands beside i76.exe). It carries only what we may ship:
    _i76e\repo\      the pieces of this repo the installer needs (setup-windows.ps1, PLAY-i76.ps1, presets, controls\input.map,
                     u32x, the clean-built proxy as music-fix\Strlkup.dll, Make-Wide-Conf + its conf template, the shell patch
                     DATA (our bytes only, tools\scott\shell-keys-patch.json) and patchers, i76wheel.exe, the debug tool, the
                     controls sheet, the repo's bookmark saves, LICENSE / THIRD-PARTY)
    _i76e\dgVoodoo\  dgVoodoo 2.87.3's x86 components, UNMODIFIED (md5 checked against the release zip; Dege's readme, section
                     "Redistribution rights": "You can freely ship your game or game mod with unmodified individual dgVoodoo
                     components (files) included.")
    _i76e\AutoHotkey\ AutoHotkeyU32.exe 1.1.37.02 + its GPL licence (the pad / wheel / stick layer)
    _i76e\i76e-prepare.ps1, VERSION.txt, MD5SUMS;  PLAY.bat, PLAY-PREVIEW.bat, PLAY-T05.bat, PLAY-PREVIEW-T05.bat,
    UNINSTALL-i76e.bat, README-SCOTT.md
  The user's own i76.exe / i76shell.dll are patched IN PLACE by the first PLAY.bat (tools\scott\i76e-prepare.ps1 ->
  setup-windows.ps1, Apply-Shell-Keys.ps1, deploy-u32x.ps1), originals kept beside them. A name guard refuses to stage any
  game file (i76.exe, i76shell.dll, *.ZFS, *.MW2, *.DEF, strlkup_orig.dll, I76PATCH.DLL, movies, music ...).

    tools\package-scott.ps1 -Proxy <clean-built Strlkup.dll> -DgVoodooDir <unpacked dgVoodoo2_87_3.zip> -AhkDir <AutoHotkeyU32.exe folder>
                            [-OutDir C:\Users\james\i76-uncap-lab\downloads\scott] [-Stamp yyyymmdd] [-Stage <dir>]
  Writes <OutDir>\Interstate76-i76-everywhere-scott-<Stamp>.zip and <zip>.MD5SUMS beside it. Record: docs\records\SCOTT-BUILD-2026-10-23.md.
#>
param(
    [Parameter(Mandatory)][string]$Proxy,
    [Parameter(Mandatory)][string]$DgVoodooDir,
    [Parameter(Mandatory)][string]$AhkDir,
    [string]$OutDir = 'C:\Users\james\i76-uncap-lab\downloads\scott',
    [string]$Stamp = (Get-Date -Format 'yyyyMMdd'),
    [string]$Stage = ''
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
function Say([string]$m, [string]$c = 'Gray') { Write-Host $m -ForegroundColor $c }
function Die([string]$m) { Write-Host "package-scott: $m" -ForegroundColor Red; exit 1 }
function Md5([string]$p) { (Get-FileHash -LiteralPath $p -Algorithm MD5).Hash.ToLower() }

$sha = (git -C $repo rev-parse --short HEAD).Trim()
$dirty = @(git -C $repo status --porcelain -- setup-windows.ps1 PLAY-i76.ps1 presets controls u32x tools/Make-Wide-Conf.ps1 tools/conf tools/scott tools/i76wheel.exe tools/fix-shell-textentry.ps1 i76-remap.ahk i76-ch-fighterstick.ahk)
if ($dirty.Count) { Say "WARNING: uncommitted changes in shipped files (commit first so VERSION.txt names what shipped):`n  $($dirty -join "`n  ")" 'Yellow' }
if (-not (Test-Path -LiteralPath $Proxy)) { Die "proxy not found: $Proxy" }
$proxyMd5 = Md5 $Proxy
if (-not $Stage) { $Stage = Join-Path $env:TEMP "scott-stage-$Stamp" }
if (Test-Path -LiteralPath $Stage) { Remove-Item -LiteralPath $Stage -Recurse -Force }
$i76e = Join-Path $Stage '_i76e'; $sr = Join-Path $i76e 'repo'
New-Item -ItemType Directory -Force $sr | Out-Null

# ---- the repo pieces setup-windows.ps1 / i76e-prepare.ps1 reach for (relative to the repo root) -------------------
$files = @(
    'setup-windows.ps1', 'PLAY-i76.ps1', 'dgVoodoo.daily-driver-2026-10-03.conf', 'dgVoodoo.windows.conf',
    'i76-remap.ahk', 'i76-ch-fighterstick.ahk', 'LICENSE', 'THIRD-PARTY.md',
    'controls\input.map', 'controls\README.md',
    'u32x\deploy-u32x.ps1', 'u32x\u32x_full.dll', 'u32x\README.md',
    'tools\Make-Wide-Conf.ps1', 'tools\conf\dgVoodoo.daily-wide-ss2x-2026-10-12.conf', 'tools\i76wheel.exe',
    'tools\lint-input-map.py', 'tools\fix-shell-textentry.ps1',
    'tools\scott\Apply-Shell-Keys.ps1', 'tools\scott\shell-keys-patch.json',
    'tools\driver\DEBUG.bat', 'tools\driver\TRAINER.bat',
    'tools\debug\i76debug.py', 'tools\debug\debug_core.py', 'tools\debug\debug_trainer.py', 'tools\debug\README.md',
    'tools\debug\static\index.html', 'tools\debug\static\app.js', 'tools\debug\static\app.css', 'tools\debug\static\charts.js',
    'tools\trainer\i76trainer_gui.py', 'tools\trainer\i76trainer.py', 'tools\trainer\i76trn.h', 'tools\trainer\README-GUI.md', 'tools\trainer\waypoints.json',
    'tools\telemetry\i76tel.py', 'tools\telemetry\i76tel.h', 'tools\telemetry\i76tel_v2.h',
    'docs\Interstate76-Controls-Quick-Reference.pdf', 'docs\CONTROLS.md',
    'presets\tick19-42.psd1', 'presets\scott-preview.psd1', 'presets\best-120.psd1', 'presets\best-wide.psd1', 'presets\best-wide-balanced.psd1', 'presets\stock.psd1',
    'saves\savegame.dir'
)
$files += @(Get-ChildItem -LiteralPath (Join-Path $repo 'saves') -Filter 'save*.cmp' -File | ForEach-Object { "saves\$($_.Name)" })
foreach ($rel in $files) {
    $from = Join-Path $repo $rel
    if (-not (Test-Path -LiteralPath $from)) { Die "missing in the repo: $rel" }
    $to = Join-Path $sr $rel
    New-Item -ItemType Directory -Force (Split-Path -Parent $to) | Out-Null
    Copy-Item -LiteralPath $from -Destination $to -Force
}
New-Item -ItemType Directory -Force (Join-Path $sr 'music-fix') | Out-Null
Copy-Item -LiteralPath $Proxy -Destination (Join-Path $sr 'music-fix\Strlkup.dll') -Force
Copy-Item -LiteralPath (Join-Path $repo 'tools\scott\i76e-prepare.ps1') -Destination (Join-Path $i76e 'i76e-prepare.ps1') -Force

# ---- dgVoodoo 2.87.3, unmodified x86 components only, checked against the release zip's hashes -------------------------
$dgv = @{   # dgVoodoo2_87_3.zip (github.com/dege-diosg/dgVoodoo2/releases/tag/v2.87.3), read 2026-10-23
    '3Dfx\x86\Glide.dll' = '259a4028d85d643608d94ee8d3b9c680'; '3Dfx\x86\Glide2x.dll' = '8af442bc7718a792c0573b34bfddca78'
    '3Dfx\x86\Glide3x.dll' = '829f80cd63a4fa35e351d43491661996'; 'MS\x86\DDraw.dll' = 'ab19386de98e7368faf43615c417a1d1'
    'MS\x86\D3DImm.dll' = 'c6bdfc6233d7f32b48fc5d552c96f73a'; 'dgVoodooCpl.exe' = '487da424c4180a234caa4502628ad257'
}
$dgOut = Join-Path $i76e 'dgVoodoo'
foreach ($rel in $dgv.Keys) {
    $from = Join-Path $DgVoodooDir $rel
    if (-not (Test-Path -LiteralPath $from)) { Die "dgVoodoo file missing: $from" }
    $m = Md5 $from
    if ($m -ne $dgv[$rel]) { Die "$rel md5 $m is not the 2.87.3 release file ($($dgv[$rel])) - only unmodified components are shipped" }
    $to = Join-Path $dgOut $rel
    New-Item -ItemType Directory -Force (Split-Path -Parent $to) | Out-Null
    Copy-Item -LiteralPath $from -Destination $to -Force
}
foreach ($extra in 'QuickGuide.url', 'Doc\Readme.url', 'Doc\ReadmeGlide.url', 'Doc\ReadmeDirectX.url') {
    $from = Join-Path $DgVoodooDir $extra
    if (Test-Path -LiteralPath $from) { $to = Join-Path $dgOut $extra; New-Item -ItemType Directory -Force (Split-Path -Parent $to) | Out-Null; Copy-Item -LiteralPath $from -Destination $to -Force }
}
@"
dgVoodoo 2.87.3 by Dege - http://dege.freeweb.hu/dgVoodoo2/  (release: https://github.com/dege-diosg/dgVoodoo2/releases/tag/v2.87.3)
Copyright (c) 2013-2026 Dege. The files in this folder are the UNMODIFIED x86 components of the dgVoodoo2_87_3.zip release
package (their md5s are in ..\MD5SUMS and were checked against the release zip by tools\package-scott.ps1 on $(Get-Date -Format yyyy-MM-dd)).
The .url files point at Dege's readmes (the package ships its documentation online).

Redistribution: dgVoodoo's general readme, section 1 "Redistribution rights" (http://dege.freeweb.hu/dgVoodoo2/ReadmeGeneral/,
read 2026-10-23): "You can freely ship your game or game mod with unmodified individual dgVoodoo components (files) included."
Standalone hosting must "provide the original, unmodified .zip package"; bundling "inside launchers or frameworks, for general
use across multiple applications" is not allowed. This build is a game mod shipping unmodified individual components for one game.
"@ | Set-Content -LiteralPath (Join-Path $dgOut 'README-dgVoodoo.txt') -Encoding ascii

# ---- AutoHotkey 1.1 (GPL v2): the interpreter the pad / wheel / stick layer runs on ---------------------------------
$ahkOut = Join-Path $i76e 'AutoHotkey'; New-Item -ItemType Directory -Force $ahkOut | Out-Null
foreach ($n in 'AutoHotkeyU32.exe', 'license.txt') {
    $from = Join-Path $AhkDir $n
    if (-not (Test-Path -LiteralPath $from)) { Die "AutoHotkey file missing: $from" }
    Copy-Item -LiteralPath $from -Destination $ahkOut -Force
}
$ahkVer = (Get-Item (Join-Path $ahkOut 'AutoHotkeyU32.exe')).VersionInfo.FileVersion

# ---- launchers, uninstaller, README -------------------------------------------------------------------------------------
function Bat([string]$preset, [string]$extra, [string]$what) {
    return @"
@echo off
REM Interstate '76 - i76-everywhere tester build $Stamp (repo $sha): $what
REM Options:  --no-supersample   lighter on the GPU: the 3D is rendered at the monitor's size, not 2x
REM           --display WxH      size the picture for this monitor size instead of the one Windows reports
REM           --setup            run the setup / display step only, do not start the game     --resetup  run the setup again
REM Run at the PC itself, never over Remote Desktop. Plug a wheel / pad in BEFORE starting. README-SCOTT.md explains the rest.
setlocal
set "ARGS="
set "SETUPONLY="
:args
if "%~1"=="" goto :go
if /i "%~1"=="--no-supersample" (set "ARGS=%ARGS% -NoSupersample" & shift & goto :args)
if /i "%~1"=="--display" (set "ARGS=%ARGS% -Display %~2" & shift & shift & goto :args)
if /i "%~1"=="--setup" (set "SETUPONLY=1" & shift & goto :args)
if /i "%~1"=="--resetup" (set "ARGS=%ARGS% -Resetup" & shift & goto :args)
echo unknown option: %~1
shift
goto :args
:go
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0_i76e\i76e-prepare.ps1" -Preset $preset%ARGS%
if errorlevel 1 ( pause & exit /b 1 )
if defined SETUPONLY ( pause & exit /b 0 )
start "" /min powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0PLAY-i76.ps1" -GameDir "%~dp0." -Exe i76.exe -Preset $preset -LosslessScaling none$extra
"@
}
$t05 = ' -Mission t05.msn -SkipMovies'
Set-Content -LiteralPath (Join-Path $Stage 'PLAY.bat') (Bat 'tick19-42' '' 'STABLE - the set James plays (tick 41.667 ms, 120 fps, widescreen, 1800 m view, every promoted fix)') -Encoding ascii
Set-Content -LiteralPath (Join-Path $Stage 'PLAY-PREVIEW.bat') (Bat 'scott-preview' '' 'EXPERIMENTAL graphics preview (terrain morph, 2300 m, fog, mirror textures) on the same stable base') -Encoding ascii
Set-Content -LiteralPath (Join-Path $Stage 'PLAY-T05.bat') (Bat 'tick19-42' $t05 'STABLE, straight into mission 5 (the ridge road to the barn), no menus, a stock car') -Encoding ascii
Set-Content -LiteralPath (Join-Path $Stage 'PLAY-PREVIEW-T05.bat') (Bat 'scott-preview' $t05 'EXPERIMENTAL preview, straight into mission 5 (the ridge road to the barn)') -Encoding ascii
Set-Content -LiteralPath (Join-Path $Stage 'UNINSTALL-i76e.bat') @"
@echo off
REM Puts your Interstate '76 folder back the way GOG installed it (the setup kept every original). Close the game first.
echo This removes the i76-everywhere overlay from this folder and restores the original files.
pause
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0_i76e\i76e-prepare.ps1" -Uninstall
pause
"@ -Encoding ascii
Copy-Item -LiteralPath (Join-Path $repo 'tools\scott\README-SCOTT.md') -Destination (Join-Path $Stage 'README-SCOTT.md') -Force

# ---- the game-byte guard: nothing of GOG's may be in the stage --------------------------------------------------------
$guard = '(?i)^(i76|nitro|splash|i76wheel_orig)\.exe$|^i76shell|\.(zfs|zix|mw2|def|smk|mp3|wav|pcx|fnt|ttf|cur|ovl|msn|vcf|map)$|^strlkup_orig|^i76patch|^(goggame|win32|audiere|smackw32|anetdll|zglide|zdx5draw|zredline|getinfo|detect3d|get3d|dsetup)'
$bad = @(Get-ChildItem -LiteralPath $Stage -Recurse -File | Where-Object { $_.Name -match $guard -and $_.Name -ne 'input.map' })
if ($bad.Count) { Die "game files in the stage - NOT packed:`n  $(($bad | ForEach-Object { $_.FullName }) -join "`n  ")" }
$allowedExe = @('i76wheel.exe', 'dgVoodooCpl.exe', 'AutoHotkeyU32.exe')
$exes = @(Get-ChildItem -LiteralPath $Stage -Recurse -File | Where-Object { $_.Extension -match '^\.(exe|dll)$' -and $_.Name -notin $allowedExe -and $_.Name -notmatch '^(Glide|Glide2x|Glide3x|DDraw|D3DImm|Strlkup|u32x_full)\.dll$' })
if ($exes.Count) { Die "unexpected binaries in the stage: $(($exes | ForEach-Object { $_.Name }) -join ', ')" }

# ---- VERSION.txt + MD5SUMS, then the zip -------------------------------------------------------------------------------
$u32xMd5 = Md5 (Join-Path $sr 'u32x\u32x_full.dll')
@(
    "scott-$Stamp $sha",
    "i76-everywhere tester build, packed $(Get-Date -Format 'yyyy-MM-dd HH:mm') by tools\package-scott.ps1 from repo commit $sha",
    "proxy Strlkup.dll md5 $proxyMd5 (clean build of $sha, MSVC x86 /MT /O2)",
    "u32x_full.dll md5 $u32xMd5; dgVoodoo 2.87.3 (unmodified x86 components); AutoHotkey $ahkVer (GPL)",
    "PLAY.bat = preset tick19-42 (stable); PLAY-PREVIEW.bat = preset scott-preview (experimental graphics)"
) | Set-Content -LiteralPath (Join-Path $i76e 'VERSION.txt') -Encoding ascii
$sums = Get-ChildItem -LiteralPath $Stage -Recurse -File | Sort-Object FullName | ForEach-Object { "$(Md5 $_.FullName)  $($_.FullName.Substring($Stage.Length + 1))" }
$sums | Set-Content -LiteralPath (Join-Path $i76e 'MD5SUMS') -Encoding ascii

New-Item -ItemType Directory -Force $OutDir | Out-Null
$zip = Join-Path $OutDir "Interstate76-i76-everywhere-scott-$Stamp.zip"
if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip -Force }
Compress-Archive -Path (Join-Path $Stage '*') -DestinationPath $zip -CompressionLevel Optimal
$sums | Set-Content -LiteralPath "$zip.MD5SUMS" -Encoding ascii
$n = @(Get-ChildItem -LiteralPath $Stage -Recurse -File).Count
Say ("packed {0}: {1} files, {2:N1} MB, md5 {3}" -f $zip, $n, ((Get-Item -LiteralPath $zip).Length / 1MB), (Md5 $zip)) 'Green'
Say "stage kept at $Stage (unzip-equivalent); proxy $proxyMd5, repo $sha"
