<#
  package-patch-kit.ps1 - the public tester build, "Interstate '76 Patch Kit (i76-everywhere)" (owner 2026-10-23: a build testers can run on their own GOG copy, the latest stable copy,
  so they can give feedback; the zips go on GitHub, so nothing of GOG's may be inside).

  ONE zip, unzipped INTO a GOG Interstate '76 folder (PLAY.bat lands beside i76.exe). It carries only what we may ship:
    _i76e\repo\      the pieces of this repo the installer needs (setup-windows.ps1, PLAY-i76.ps1, presets, controls\input.map,
                     u32x, the clean-built proxy as music-fix\Strlkup.dll, Make-Wide-Conf + its conf template, the shell patch
                     DATA (our bytes only, tools\patch-kit\shell-keys-patch.json) and patchers, i76wheel.exe, the debug tool, the
                     controls sheet, the repo's bookmark saves, LICENSE / THIRD-PARTY)
    _i76e\dgVoodoo\  dgVoodoo 2.87.5's x86 components (+ _i76e\dgVoodoo-2.87.3 fallback), UNMODIFIED (md5 checked against the release zip; Dege's readme, section
                     "Redistribution rights": "You can freely ship your game or game mod with unmodified individual dgVoodoo
                     components (files) included.")
    _i76e\AutoHotkey\ AutoHotkeyU32.exe 1.1.37.02 + its GPL licence (the pad / wheel / stick layer)
    _i76e\i76e-prepare.ps1, VERSION.txt, MD5SUMS;  PLAY.bat, PLAY-PREVIEW.bat, PLAY-T05.bat, PLAY-PREVIEW-T05.bat,
    PLAY-Nitro.bat, UNINSTALL-i76e.bat, INSTALL-EXTRAS.bat, SETTINGS.bat, FIREWALL.bat, README-PATCH-KIT.md
  The same zip goes into a GOG Nitro Pack folder (nitro.exe) since 2026-10-25 (clean-install B6: Nitro needed MSVC + a repo clone
  through Build-From-GOG): PLAY-Nitro.bat runs i76e-prepare.ps1 -Game Nitro (the same proxy, which detects nitro.exe; preset
  nitro-tick42; dgVoodoo 2.87.5 incl. D3D8 / D3D9; the Nitro shell keys from nitshell-keys-patch.json; GOG's Nitro keys). The Gold
  PLAY*.bat hand over to PLAY-Nitro.bat in a Nitro folder.
  The user's own i76.exe / i76shell.dll are patched IN PLACE by the first PLAY.bat (tools\patch-kit\i76e-prepare.ps1 ->
  setup-windows.ps1, Apply-Shell-Keys.ps1, deploy-u32x.ps1), originals kept beside them. A name guard refuses to stage any
  game file (i76.exe, i76shell.dll, *.ZFS, *.MW2, *.DEF, strlkup_orig.dll, I76PATCH.DLL, movies, music ...).

    tools\package-patch-kit.ps1 -Proxy <clean-built Strlkup.dll> -DgVoodooDir <unpacked 2.87.5> -DgVoodooFallbackDir <unpacked 2.87.3> -AhkDir <AutoHotkeyU32.exe folder>
                            [-OutDir <lab>\downloads\patch-kit] [-Version 0.8.0] [-Stamp yyyymmdd] [-Stage <dir>]
  Writes <OutDir>\Interstate76-Patch-Kit-i76-everywhere-v<Version>-<sha>.zip and <zip>.MD5SUMS beside it. Record: docs\records\TESTER-BUILD-2026-10-23.md (history).
#>
param(
    [Parameter(Mandatory)][string]$Proxy,
    [string]$ProxyCommit = '',      # the commit the proxy was built from (lab builds\nitro-port-20261021\build.ps1 -Ref); default: HEAD
    [Parameter(Mandatory)][string]$DgVoodooDir,          # dgVoodoo 2.87.5, the unpacked release (MS, 3Dfx, dgVoodooCpl.exe)
    [Parameter(Mandatory)][string]$DgVoodooFallbackDir,  # dgVoodoo 2.87.3, unpacked: kept in _i76e\dgVoodoo-2.87.3 as the swap-back fallback
    [Parameter(Mandatory)][string]$AhkDir,
    [string]$OutDir = (Join-Path $env:USERPROFILE 'i76-uncap-lab\downloads\patch-kit'),
    [string]$Version = '0.8.0',
    [string]$Stamp = (Get-Date -Format 'yyyyMMdd'),
    [string]$Stage = ''
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
function Say([string]$m, [string]$c = 'Gray') { Write-Host $m -ForegroundColor $c }
function Die([string]$m) { Write-Host "package-patch-kit: $m" -ForegroundColor Red; exit 1 }
function Md5([string]$p) { (Get-FileHash -LiteralPath $p -Algorithm MD5).Hash.ToLower() }

$sha = (git -C $repo rev-parse --short HEAD).Trim()
$dirty = @(git -C $repo status --porcelain -- setup-windows.ps1 PLAY-i76.ps1 presets controls u32x tools/Make-Wide-Conf.ps1 tools/conf tools\patch-kit tools/i76wheel.exe tools/fix-shell-textentry.ps1 tools/debug tools/driver i76-remap.ahk i76-ch-fighterstick.ahk i76-opentrack-headlook.ahk i76-opentrack-autostart.ahk i76-opentrack-autostart.ps1)
if ($dirty.Count) { Say "WARNING: uncommitted changes in shipped files (commit first so VERSION.txt names what shipped):`n  $($dirty -join "`n  ")" 'Yellow' }
if (-not (Test-Path -LiteralPath $Proxy)) { Die "proxy not found: $Proxy" }
$proxyMd5 = Md5 $Proxy
if (-not $Stage) { $Stage = Join-Path $env:TEMP "patch-kit-stage-$Stamp" }
if (Test-Path -LiteralPath $Stage) { Remove-Item -LiteralPath $Stage -Recurse -Force }
$i76e = Join-Path $Stage '_i76e'; $sr = Join-Path $i76e 'repo'
New-Item -ItemType Directory -Force $sr | Out-Null

# ---- the repo pieces setup-windows.ps1 / i76e-prepare.ps1 reach for (relative to the repo root) -------------------
$files = @(
    'setup-windows.ps1', 'PLAY-i76.ps1', 'dgVoodoo.daily-driver-2026-10-03.conf', 'dgVoodoo.windows.conf',
    'i76-remap.ahk', 'i76-ch-fighterstick.ahk', 'LICENSE', 'THIRD-PARTY.md',
    'i76-opentrack-headlook.ahk', 'i76-opentrack-autostart.ahk', 'i76-opentrack-autostart.ps1',   # the head-look layer (INSTALL-EXTRAS.bat's opentrack option puts it in _ahk\)
    'controls\input.map', 'controls\README.md',
    'u32x\deploy-u32x.ps1', 'u32x\u32x_full.dll', 'u32x\README.md',
    'tools\Make-Wide-Conf.ps1', 'tools\conf\dgVoodoo.daily-wide-ss2x-2026-10-12.conf', 'tools\i76wheel.exe',
    'tools\lint-input-map.py', 'tools\fix-shell-textentry.ps1',
    'tools\patch-kit\Apply-Shell-Keys.ps1', 'tools\patch-kit\shell-keys-patch.json', 'tools\patch-kit\nitshell-keys-patch.json',
    'tools\driver\DEBUG.bat', 'tools\driver\TRAINER.bat',
    'tools\debug\i76debug.py', 'tools\debug\debug_core.py', 'tools\debug\debug_trainer.py', 'tools\debug\debug_logger.py', 'tools\debug\debug_haptics.py', 'tools\debug\README.md',
    'tools\debug\static\index.html', 'tools\debug\static\app.js', 'tools\debug\static\app.css', 'tools\debug\static\charts.js',
    'tools\trainer\i76trainer_gui.py', 'tools\trainer\i76trainer.py', 'tools\trainer\i76trn.h', 'tools\trainer\README-GUI.md', 'tools\trainer\waypoints.json',
    'tools\telemetry\i76tel.py', 'tools\telemetry\i76tel.h', 'tools\telemetry\i76tel_v2.h',
    'docs\Interstate76-Controls-Quick-Reference.pdf', 'docs\CONTROLS.md',
    'presets\tick19-42.psd1', 'presets\preview.psd1', 'presets\best-120.psd1', 'presets\best-wide.psd1', 'presets\best-wide-balanced.psd1', 'presets\stock.psd1', 'presets\nitro-tick42.psd1',
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
Copy-Item -LiteralPath (Join-Path $repo 'tools\patch-kit\i76e-prepare.ps1') -Destination (Join-Path $i76e 'i76e-prepare.ps1') -Force
# the optional extras (INSTALL-EXTRAS.bat; content-installer lane 2026-10-25): the script and its manifest of pinned downloads - no content
foreach ($n in 'i76e-extras.ps1', 'extras.json') { Copy-Item -LiteralPath (Join-Path $repo "tools\patch-kit\$n") -Destination (Join-Path $i76e $n) -Force }

# ---- dgVoodoo 2.87.3, unmodified x86 components only, checked against the release zip's hashes -------------------------
function Ship-DgVoodoo([string]$srcDir, [hashtable]$hashes, [string]$ver, [string]$outDir, [string]$extraNote) {
    foreach ($rel in $hashes.Keys) {
        $from = Join-Path $srcDir $rel
        if (-not (Test-Path -LiteralPath $from)) { Die "dgVoodoo file missing: $from" }
        $m = Md5 $from
        if ($m -ne $hashes[$rel]) { Die "$rel md5 $m is not the $ver release file ($($hashes[$rel])) - only unmodified components are shipped" }
        $to = Join-Path $outDir $rel
        New-Item -ItemType Directory -Force (Split-Path -Parent $to) | Out-Null
        Copy-Item -LiteralPath $from -Destination $to -Force
    }
    foreach ($extra in 'QuickGuide.url', 'Doc\Readme.url', 'Doc\ReadmeGlide.url', 'Doc\ReadmeDirectX.url') {
        $from = Join-Path $srcDir $extra
        if (Test-Path -LiteralPath $from) { $to = Join-Path $outDir $extra; New-Item -ItemType Directory -Force (Split-Path -Parent $to) | Out-Null; Copy-Item -LiteralPath $from -Destination $to -Force }
    }
    $u = $ver.Replace('.', '_')
@"
dgVoodoo $ver by Dege - http://dege.freeweb.hu/dgVoodoo2/  (release: https://github.com/dege-diosg/dgVoodoo2/releases/tag/v$ver)
Copyright (c) 2013-2026 Dege. The files in this folder are the UNMODIFIED x86 components of the dgVoodoo2_$u.zip release
package (their md5s are in the MD5SUMS beside _i76e and were checked against the release by tools\package-patch-kit.ps1 on $(Get-Date -Format yyyy-MM-dd)).
The .url files point at Dege's readmes (the package ships its documentation online).
$extraNote
Redistribution: dgVoodoo's general readme, section 1 "Redistribution rights" (http://dege.freeweb.hu/dgVoodoo2/ReadmeGeneral/,
read 2026-10-23): "You can freely ship your game or game mod with unmodified individual dgVoodoo components (files) included."
Standalone hosting must "provide the original, unmodified .zip package"; bundling "inside launchers or frameworks, for general
use across multiple applications" is not allowed. This build is a game mod shipping unmodified individual components for one game.
"@ | Set-Content -LiteralPath (Join-Path $outDir 'README-dgVoodoo.txt') -Encoding ascii
}
# dgVoodoo 2.87.5 (needed on Windows 11 26100.9711+: 2.87.3's DDraw fails there), md5s from docs\records\DGVOODOO-UPDATE-2026-10-24.md s.5
$dgv5 = @{
    '3Dfx\x86\Glide.dll' = 'ad980c1620c8bb96d66d76b387aa2a1f'; '3Dfx\x86\Glide2x.dll' = '3fbe9528e7ec331e647d39155670abd2'
    '3Dfx\x86\Glide3x.dll' = '4788b491a3645dd3b576d57668e10851'; 'MS\x86\DDraw.dll' = 'c70a0ee641c3c349176fca39e4d78777'
    'MS\x86\D3DImm.dll' = '71b3bf5a20fb0df63fa1b20a3030234e'; 'dgVoodooCpl.exe' = 'ce248253d7df5df240dffe48e81ed181'
    # Nitro (2026-10-25): setup-windows deploys D3D8 / D3D9 too on nitro.exe (NITRO-WIN11-2026-10-25 s.4, the same md5s)
    'MS\x86\D3D8.dll' = 'e215a1eef240ba696331f38841234580'; 'MS\x86\D3D9.dll' = 'e9a6ec6b789cb960a2aa601e07fc95e6'
}
# dgVoodoo 2.87.3 (the fallback), dgVoodoo2_87_3.zip read 2026-10-23
$dgv3 = @{
    '3Dfx\x86\Glide.dll' = '259a4028d85d643608d94ee8d3b9c680'; '3Dfx\x86\Glide2x.dll' = '8af442bc7718a792c0573b34bfddca78'
    '3Dfx\x86\Glide3x.dll' = '829f80cd63a4fa35e351d43491661996'; 'MS\x86\DDraw.dll' = 'ab19386de98e7368faf43615c417a1d1'
    'MS\x86\D3DImm.dll' = 'c6bdfc6233d7f32b48fc5d552c96f73a'; 'dgVoodooCpl.exe' = '487da424c4180a234caa4502628ad257'
    'MS\x86\D3D8.dll' = '4127f3d9b8102eb6a985a48a1be8cbb5'; 'MS\x86\D3D9.dll' = '9b8e49162730507dd4515f20ebe328dd'
}
Ship-DgVoodoo $DgVoodooDir $dgv5 '2.87.5' (Join-Path $i76e 'dgVoodoo') ''
Ship-DgVoodoo $DgVoodooFallbackDir $dgv3 '2.87.3' (Join-Path $i76e 'dgVoodoo-2.87.3') @"

THIS IS THE FALLBACK. The build uses dgVoodoo 2.87.5 (..\dgVoodoo). To swap back to 2.87.3 (for example if an antivirus flags 2.87.5):
delete _i76e\dgVoodoo, rename this folder (_i76e\dgVoodoo-2.87.3) to _i76e\dgVoodoo, run UNINSTALL-i76e.bat, then PLAY.bat --resetup.
2.87.3 does not start on Windows 11 build 26100.9711 or later.
"@

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
REM Options:  --no-supersample   lighter on the GPU: the 3D is rendered at the monitor's size, not 2x (= I76_RENDER_SCALE 1 for this launch)
REM           --display WxH      size the picture for this monitor size instead of the one Windows reports
REM           --setup            run the setup / display step only, do not start the game     --resetup  run the setup again
REM           --voices de|en     German voice lines for this launch (INSTALL-EXTRAS.bat builds them from your German disc) / English
REM           --music-extra off  this launch without your extra music (INSTALL-EXTRAS.bat sets the folder)
REM Run at the PC itself, never over Remote Desktop. Plug a wheel / pad in BEFORE starting. README-PATCH-KIT.md explains the rest.
setlocal
REM the kit was unzipped into a Nitro Pack folder: the Nitro launcher does the rest
if not exist "%~dp0i76.exe" if exist "%~dp0nitro.exe" ( call "%~dp0PLAY-Nitro.bat" %* & exit /b )
set "ARGS="
set "PLAYARGS="
set "SETUPONLY="
REM the defaults INSTALL-EXTRAS.bat chose (German voices, extra music): KEY=VALUE lines, overridden by the options below
if exist "%~dp0_i76e\extras.env" for /f "usebackq eol=# tokens=1* delims==" %%a in ("%~dp0_i76e\extras.env") do set "%%a=%%b"
:args
if "%~1"=="" goto :go
if /i "%~1"=="--no-supersample" (set "ARGS=%ARGS% -NoSupersample" & set "PLAYARGS=%PLAYARGS% -RenderScale 1" & shift & goto :args)
if /i "%~1"=="--display" (set "ARGS=%ARGS% -Display %~2" & shift & shift & goto :args)
if /i "%~1"=="--setup" (set "SETUPONLY=1" & set "ARGS=%ARGS% -SetupOnly" & shift & goto :args)
if /i "%~1"=="--resetup" (set "ARGS=%ARGS% -Resetup" & shift & goto :args)
if /i "%~1"=="--voices" (set "I76_VOICES=%~2" & shift & shift & goto :args)
if /i "%~1"=="--music-extra" (set "I76_MUSIC_EXTRA=%~2" & shift & shift & goto :args)
echo unknown option: %~1
shift
goto :args
:go
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0_i76e\i76e-prepare.ps1" -Preset $preset %ARGS%
if errorlevel 1 ( pause & exit /b 1 )
if defined SETUPONLY exit /b 0
start "" /min powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0PLAY-i76.ps1" -GameDir "%~dp0." -Exe i76.exe -Preset $preset -LosslessScaling none$extra%PLAYARGS%
"@
}
$t05 = ' -Mission t05.msn -SkipMovies'
Set-Content -LiteralPath (Join-Path $Stage 'PLAY.bat') (Bat 'tick19-42' '' 'STABLE - the set the developer plays (tick 41.667 ms, 120 fps, widescreen, 1800 m view, every promoted fix)') -Encoding ascii
Set-Content -LiteralPath (Join-Path $Stage 'PLAY-PREVIEW.bat') (Bat 'preview' '' 'EXPERIMENTAL GRAPHICS PREVIEW (smoothed + morphing terrain, 2300 m view fading out at the far edge, sparser bushes, 1000 m mirror with full textures) on the same stable base') -Encoding ascii
Set-Content -LiteralPath (Join-Path $Stage 'PLAY-T05.bat') (Bat 'tick19-42' $t05 'STABLE, straight into mission 5 (the ridge road to the barn), no menus, a stock car') -Encoding ascii
Set-Content -LiteralPath (Join-Path $Stage 'PLAY-PREVIEW-T05.bat') (Bat 'preview' $t05 'EXPERIMENTAL GRAPHICS PREVIEW, straight into mission 5 (the ridge road to the barn), no menus, a stock car') -Encoding ascii
Set-Content -LiteralPath (Join-Path $Stage 'PLAY-Nitro.bat') @"
@echo off
REM Interstate '76 NITRO PACK - i76-everywhere tester build $Stamp (repo $sha): for a GOG Nitro Pack folder (the one with nitro.exe).
REM The same set as Gold's PLAY.bat where Nitro has it: tick 41.667 ms, up to 120 fps, widescreen (Hor+), 1200 m view, dgVoodoo 2.87.5,
REM the shell keys (Enter / Y / N / Esc in the menus). GOG's own Nitro keys are kept. Preset nitro-tick42.
REM Options:  --no-supersample   lighter on the GPU (3D at the monitor's size, not 2x)
REM           --display WxH      size the picture for this monitor size instead of the one Windows reports
REM           --setup            run the setup / display step only, do not start the game     --resetup  run the setup again
REM           --music-extra off  this launch without your extra music (INSTALL-EXTRAS.bat sets the folder)
REM Run at the PC itself, never over Remote Desktop. Plug a wheel / pad in BEFORE starting. README-PATCH-KIT.md explains the rest.
setlocal
set "ARGS="
set "PLAYARGS="
set "SETUPONLY="
if exist "%~dp0_i76e\extras.env" for /f "usebackq eol=# tokens=1* delims==" %%a in ("%~dp0_i76e\extras.env") do set "%%a=%%b"
:args
if "%~1"=="" goto :go
if /i "%~1"=="--no-supersample" (set "ARGS=%ARGS% -NoSupersample" & set "PLAYARGS=%PLAYARGS% -RenderScale 1" & shift & goto :args)
if /i "%~1"=="--display" (set "ARGS=%ARGS% -Display %~2" & shift & shift & goto :args)
if /i "%~1"=="--setup" (set "SETUPONLY=1" & set "ARGS=%ARGS% -SetupOnly" & shift & goto :args)
if /i "%~1"=="--resetup" (set "ARGS=%ARGS% -Resetup" & shift & goto :args)
if /i "%~1"=="--music-extra" (set "I76_MUSIC_EXTRA=%~2" & shift & shift & goto :args)
echo unknown option: %~1
shift
goto :args
:go
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0_i76e\i76e-prepare.ps1" -Game Nitro -Preset nitro-tick42 %ARGS%
if errorlevel 1 ( pause & exit /b 1 )
if defined SETUPONLY exit /b 0
start "" /min powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0PLAY-i76.ps1" -GameDir "%~dp0." -Exe nitro.exe -Preset nitro-tick42 -LosslessScaling none%PLAYARGS%
"@ -Encoding ascii
Set-Content -LiteralPath (Join-Path $Stage 'UNINSTALL-i76e.bat') @"
@echo off
REM Puts your Interstate '76 folder back the way GOG installed it (the setup kept every original). Close the game first.
echo This removes the i76-everywhere overlay from this folder and restores the original files.
pause
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0_i76e\i76e-prepare.ps1" -Uninstall
pause
"@ -Encoding ascii
Set-Content -LiteralPath (Join-Path $Stage 'INSTALL-EXTRAS.bat') @"
@echo off
REM Interstate '76 - i76-everywhere Patch Kit ${Version}: OPTIONAL extras. Each one says what it adds and asks first:
REM   community maps (downloaded from the sites that host them), opentrack (head look), Python (for DEBUG.bat),
REM   German voices (from your own German disc), extra music (a folder of your own songs, private).
REM INSTALL-EXTRAS.bat --list   shows what is installed. UNINSTALL-i76e.bat removes it with the rest of the kit.
setlocal
if /i "%~1"=="--list" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0_i76e\i76e-extras.ps1" -List
  pause
  exit /b 0
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0_i76e\i76e-extras.ps1" %*
pause
"@ -Encoding ascii
# SETTINGS.bat (2026-10-25, settings-file lane, docs\records\SETTINGS-FILE-2026-10-25.md): opens i76-settings.txt in Notepad. PLAY-i76.ps1
# writes the file on the first start (and -WriteSettings writes it on demand once the setup has put PLAY-i76.ps1 + presets\ in the folder).
Set-Content -LiteralPath (Join-Path $Stage 'SETTINGS.bat') @"
@echo off
REM Interstate '76 - i76-everywhere Patch Kit ${Version}: opens i76-settings.txt (graphics, controls, sound, multiplayer) in Notepad.
REM Change a value after the = sign, save, close Notepad, start the game with PLAY.bat. README-PATCH-KIT.md "Settings" explains it.
setlocal
set "PRESET=tick19-42"
if not exist "%~dp0i76.exe" if exist "%~dp0nitro.exe" set "PRESET=nitro-tick42"
if not exist "%~dp0i76-settings.txt" if exist "%~dp0PLAY-i76.ps1" powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0PLAY-i76.ps1" -GameDir "%~dp0." -Preset %PRESET% -WriteSettings >nul
if not exist "%~dp0i76-settings.txt" (
  echo i76-settings.txt is written by the first start. Start PLAY.bat ^(PLAY-Nitro.bat for the Nitro Pack^) once, then run SETTINGS.bat again.
  pause
  exit /b 1
)
start "" notepad.exe "%~dp0i76-settings.txt"
"@ -Encoding ascii
# FIREWALL.bat (owner 2026-10-25): one inbound allow rule for the game exe on private networks, self-elevating; the user runs it (never the setup: UAC)
Copy-Item -LiteralPath (Join-Path $repo 'tools\patch-kit\FIREWALL.bat') -Destination (Join-Path $Stage 'FIREWALL.bat') -Force
Copy-Item -LiteralPath (Join-Path $repo 'tools\patch-kit\README.md') -Destination (Join-Path $Stage 'README-PATCH-KIT.md') -Force

# ---- the game-byte guard: nothing of GOG's may be in the stage --------------------------------------------------------
$guard = '(?i)^(i76|nitro|splash|i76wheel_orig)\.exe$|^i76shell|^nitshell\.dll|\.(zfs|zix|mw2|def|smk|mp3|wav|pcx|fnt|ttf|cur|ovl|msn|vcf|map)$|^strlkup_orig|^i76patch|^(goggame|win32|audiere|smackw32|anetdll|zglide|zdx5draw|zredline|getinfo|detect3d|get3d|dsetup)'
$bad = @(Get-ChildItem -LiteralPath $Stage -Recurse -File | Where-Object { $_.Name -match $guard -and $_.Name -ne 'input.map' })
if ($bad.Count) { Die "game files in the stage - NOT packed:`n  $(($bad | ForEach-Object { $_.FullName }) -join "`n  ")" }
$allowedExe = @('i76wheel.exe', 'dgVoodooCpl.exe', 'AutoHotkeyU32.exe')
$exes = @(Get-ChildItem -LiteralPath $Stage -Recurse -File | Where-Object { $_.Extension -match '^\.(exe|dll)$' -and $_.Name -notin $allowedExe -and $_.Name -notmatch '^(Glide|Glide2x|Glide3x|DDraw|D3DImm|D3D8|D3D9|Strlkup|u32x_full)\.dll$' })
if ($exes.Count) { Die "unexpected binaries in the stage: $(($exes | ForEach-Object { $_.Name }) -join ', ')" }

# ---- VERSION.txt + MD5SUMS, then the zip -------------------------------------------------------------------------------
$u32xMd5 = Md5 (Join-Path $sr 'u32x\u32x_full.dll')
@(
    "patch-kit-v$Version $sha",
    "i76-everywhere tester build, packed $(Get-Date -Format 'yyyy-MM-dd HH:mm') by tools\package-patch-kit.ps1 from repo commit $sha",
    "proxy Strlkup.dll md5 $proxyMd5 (clean build of commit $(if ($ProxyCommit) { $ProxyCommit } else { $sha }), MSVC x86 /MT /O2)",
    "u32x_full.dll md5 $u32xMd5; dgVoodoo 2.87.5 (unmodified x86 components; 2.87.3 kept in _i76e\dgVoodoo-2.87.3 as fallback); AutoHotkey $ahkVer (GPL)",
    "PLAY.bat = preset tick19-42 (stable); PLAY-PREVIEW.bat = preset preview (the experimental graphics preview); PLAY-Nitro.bat = the Nitro Pack (nitro.exe), preset nitro-tick42",
    "INSTALL-EXTRAS.bat = optional extras (_i76e\i76e-extras.ps1 + extras.json: pinned downloads of community maps, opentrack, Python; German voices from the user's disc; private extra music)"
) | Set-Content -LiteralPath (Join-Path $i76e 'VERSION.txt') -Encoding ascii
$sums = Get-ChildItem -LiteralPath $Stage -Recurse -File | Sort-Object FullName | ForEach-Object { "$(Md5 $_.FullName)  $($_.FullName.Substring($Stage.Length + 1))" }
$sums | Set-Content -LiteralPath (Join-Path $i76e 'MD5SUMS') -Encoding ascii

New-Item -ItemType Directory -Force $OutDir | Out-Null
$zip = Join-Path $OutDir "Interstate76-Patch-Kit-i76-everywhere-v$Version-$sha.zip"
if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip -Force }
Compress-Archive -Path (Join-Path $Stage '*') -DestinationPath $zip -CompressionLevel Optimal
$sums | Set-Content -LiteralPath "$zip.MD5SUMS" -Encoding ascii
$n = @(Get-ChildItem -LiteralPath $Stage -Recurse -File).Count
Say ("packed {0}: {1} files, {2:N1} MB, md5 {3}" -f $zip, $n, ((Get-Item -LiteralPath $zip).Length / 1MB), (Md5 $zip)) 'Green'
Say "stage kept at $Stage (unzip-equivalent); proxy $proxyMd5, repo $sha"
