# Promotion 3a (2026-10-03): hotfix. best-wide carried I76_ROAD_DIST=1800, which overflows the engine's depth-bucket
# node pool (exe+0x9051B): trip mission t11 crashed at boot 2/2 and t01/t05/t13/t15/t16 logged the fault (lab
# docs/SOAK-BEST-WIDE-2026-10-03.md). The presets now leave roads at stock 450 m. Text files only.
param([switch]$Plan)
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$files = @{}
foreach ($n in 'best-wide', 'exp-detail-8', 'exp-detail-16') { $files["Interstate 76\presets\$n.psd1"] = Join-Path $repo "presets\$n.psd1" }
& (Join-Path $PSScriptRoot 'Promote-To-Driver.ps1') -Plan:$Plan `
    -What 'HOTFIX: drop I76_ROAD_DIST=1800 from best-wide and the exp-detail presets (t11 crashed at boot)' `
    -Gate 'lab soak t01-t17 2026-10-03: crash exe+0x9051B only with I76_ROAD_DIST (bisect on t11: removing it alone stops the crash; 600 m clean n=1; 900-1800 crash); every other switch passed' `
    -Files $files
