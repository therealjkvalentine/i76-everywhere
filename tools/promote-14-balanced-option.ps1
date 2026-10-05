# Promotion 14 (2026-10-05): an EXTRA launch option, PLAY-balanced.bat -> preset best-wide-balanced (widescreen,
# 120 fps, best-wide with the detail switches trimmed where the 2026-10-05 per-switch cost run found cost and little
# visible benefit; lab autotest\runs\twin-sync-20261005\COST.md). PLAY.bat (best-wide) stays the default and is not touched.
# New files only: Interstate 76\presets\best-wide-balanced.psd1 and PLAY-balanced.bat in the folder root.
# Run with the game closed; -Plan previews and writes nothing.
param([switch]$Plan)
$ErrorActionPreference = 'Stop'
$repo  = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$stage = Join-Path $env:TEMP "promote-14-$(Get-Date -Format yyyyMMdd-HHmmss)"
New-Item -ItemType Directory -Force $stage | Out-Null
$psd = Join-Path $repo 'presets\best-wide-balanced.psd1'
$e = (Import-PowerShellDataFile $psd).Env
foreach ($k in 'I76_ZGLIDE_TMUFIX', 'I76_INPUT_LATCH', 'I76_AI_BACKAWAY_GRID', 'I76_ASPECT', 'I76_FAR_CLIP') { if (-not $e.$k) { throw "REFUSED: best-wide-balanced.psd1 lacks $k" } }
# the launcher with CRLF line ends, like the driver's other .bat files
$bat = Join-Path $stage 'PLAY-balanced.bat'
$t = ([IO.File]::ReadAllText((Join-Path $repo 'tools\driver\PLAY-balanced.bat'))) -replace "`r?`n", "`r`n"
[IO.File]::WriteAllText($bat, $t, [Text.Encoding]::ASCII)
& (Join-Path $PSScriptRoot 'Promote-To-Driver.ps1') -Plan:$Plan `
    -What 'extra launch option PLAY-balanced.bat (preset best-wide-balanced: best-wide with the costly low-benefit detail switches trimmed); PLAY.bat stays best-wide' `
    -Gate 'lab twin game-dd-20261003 (= driver after promotion 12, proxy 89a97d25, TMU 8192), 2026-10-05: gate-folder row 3 (trip route through PLAY-balanced.bat) 2/2 engine up at 120 fps, far-clip 1200 logged, S + D PASS (runs\gate\20261005-101026); cost run on t04 open desert (circle drive 75 s + binoculars 10 s, best-wide vs each switch halved, n=2-3 per condition): cockpit 120 fps / CPU ~8.7 ms per frame / GPU 3D ~33 % in every condition; binoculars base 79 fps [72..86] n=3, far 1200 99 fps n=1 valid (terrain vertices 15.8k -> 4.3k); other halvings within spread (lab autotest\runs\twin-sync-20261005\COST.md)' `
    -Files @{ 'Interstate 76\presets\best-wide-balanced.psd1' = $psd; 'PLAY-balanced.bat' = $bat }
