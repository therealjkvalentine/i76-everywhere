# Promotion 12 (DRAFT 2026-10-04, NOT RUN - the owner decides): every fix of 2026-10-04 in one step. Supersedes the
# promote-11 draft (run this one instead; it is idempotent over a promote-11 that was already applied).
#   1. the consolidated proxy music-fix\Strlkup.dll (89a97d25, i76-everywhere b903730): music run end exclusive +
#      I76_MUSIC_DISC_ORDER / I76_MUSIC_SHELL (opt-in, in no preset), I76_ZGLIDE_TMUFIX + I76_FRAME_SPIKES,
#      I76_AI_BACKAWAY_GRID (opt-in, in no preset), the trainer cheat-marker guard (always on with the trainer) and
#      I76_INPUT_LATCH. The driver runs f9b0c481, which has none of these.
#   2. dgVoodoo [Glide] MemorySizeOfTMU 2048 -> 8192 in dgVoodoo.wide.conf AND dgVoodoo.16x10.conf (NumberOfTMUs stays 1)
#   3. presets\best-wide.psd1 (PLAY.bat) and presets\best-120.psd1 (PLAY-16x10.bat): + I76_ZGLIDE_TMUFIX = '1' and
#      + I76_INPUT_LATCH = '1' (each line only if missing). I76_AI_BACKAWAY_GRID is NOT added: its own acceptance tests
#      (T12 opening n=5, AI pinned-car regression; lab docs/2026-10-04-milk-truck-opening-divergence.md s9) have not run.
#   4. the trainer (campaign-safe holds, 'Turn off cheater options') into _tools\trainer, and the save editor
#      (--check reports I76PLYR.DEF play options, --clear-cheat-options) into the folder root.
# Never TMU 8192 without I76_ZGLIDE_TMUFIX (4096+ without it corrupts textures: lab RENDER-FREEZE-2026-10-04.md); both
# come in this one promotion. Confs and presets are staged from the DRIVER's own current files (one value changed /
# lines added), so nothing else in them moves; refuses if driver and golden differ in any of them.
# Run with the game closed; -Plan previews and writes nothing to either folder.
param([switch]$Plan)
$ErrorActionPreference = 'Stop'
$repo   = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$driver = 'C:\Users\james\Games\Interstate76-2026-10-03'
$golden = 'C:\Users\james\Games\Interstate76-golden-2026-10-03'
$stage  = Join-Path $env:TEMP "promote-12-$(Get-Date -Format yyyyMMdd-HHmmss)"
New-Item -ItemType Directory -Force $stage | Out-Null
function Md5([string]$p) { (Get-FileHash -LiteralPath $p -Algorithm MD5).Hash.ToLower() }

$dll = Join-Path $repo 'music-fix\Strlkup.dll'
if ((Md5 $dll).Substring(0, 8) -ne '89a97d25') { throw "REFUSED: music-fix\Strlkup.dll is $((Md5 $dll).Substring(0, 8)), not the tested 89a97d25 (rebuilt since? re-gate it first)" }
$files = @{ 'Interstate 76\STRLKUP.DLL' = $dll }

foreach ($c in 'dgVoodoo.wide.conf', 'dgVoodoo.16x10.conf') {
    $src = Join-Path $driver "Interstate 76\$c"
    if ((Md5 $src) -ne (Md5 (Join-Path $golden "Interstate 76\$c"))) { throw "REFUSED: $c differs between driver and golden" }
    $t = [IO.File]::ReadAllText($src)
    $n2048 = ([regex]::Matches($t, '(?m)^MemorySizeOfTMU\s*=\s*2048\s*$')).Count
    $n8192 = ([regex]::Matches($t, '(?m)^MemorySizeOfTMU\s*=\s*8192\s*$')).Count
    if ($n2048 -eq 1 -and $n8192 -eq 0) {
        $t = [regex]::Replace($t, '(?m)^(MemorySizeOfTMU\s*=\s*)2048(\s*)$', '${1}8192${2}')
        $out = Join-Path $stage $c; [IO.File]::WriteAllText($out, $t, [Text.Encoding]::ASCII)
        $files["Interstate 76\$c"] = $out
    } elseif ($n2048 -eq 0 -and $n8192 -eq 1) { Write-Host "$c already at 8192 - left as is" }
    else { throw "REFUSED: $c has $n2048 x 2048 and $n8192 x 8192 MemorySizeOfTMU lines (expected exactly one)" }
}

$add = [ordered]@{
    'I76_ZGLIDE_TMUFIX' = "I76_ZGLIDE_TMUFIX   = '1'   # with dgVoodoo MemorySizeOfTMU 8192: no ZGLIDE flush freezes, no 2 MB boundary rewind (lab RENDER-FREEZE-2026-10-04.md)"
    'I76_INPUT_LATCH'   = "I76_INPUT_LATCH     = '1'   # ignition (I) / lights (H) presses survive frames without a physics step (lab 2026-10-04: 50/50 vs 13/50)"
}
foreach ($p in 'best-wide.psd1', 'best-120.psd1') {
    $src = Join-Path $driver "Interstate 76\presets\$p"
    if ((Md5 $src) -ne (Md5 (Join-Path $golden "Interstate 76\presets\$p"))) { throw "REFUSED: $p differs between driver and golden" }
    $t = [IO.File]::ReadAllText($src); $changed = $false
    $nl = if ($t.Contains("`r`n")) { "`r`n" } else { "`n" }
    foreach ($k in $add.Keys) {
        if ($t -match "(?m)^\s*$k\s*=") { Write-Host "$p already sets $k - left as is"; continue }
        $m = [regex]::Match($t, "(?m)^(\s*)I76_FAR_CLIP\s*=.*$")
        if (-not $m.Success) { throw "REFUSED: $p has no I76_FAR_CLIP line to anchor on" }
        $t = $t.Insert($m.Index + $m.Length, $nl + $m.Groups[1].Value + $add[$k]); $changed = $true
    }
    if ($changed) {
        $out = Join-Path $stage $p; [IO.File]::WriteAllText($out, $t, [Text.Encoding]::ASCII)
        $e = (Import-PowerShellDataFile $out).Env      # still a valid preset, with both switches
        if ($e.I76_ZGLIDE_TMUFIX -ne '1' -or $e.I76_INPUT_LATCH -ne '1') { throw "REFUSED: staged $p does not read back both switches" }
        $files["Interstate 76\presets\$p"] = $out
    }
}

# trainer + save editor (the promotion-9 layout: code in _tools\trainer, save editor in the root)
$files['i76-save-editor.py']               = Join-Path $repo 'i76-save-editor.py'
$files['_tools\trainer\i76trainer_gui.py'] = Join-Path $repo 'tools\trainer\i76trainer_gui.py'
$files['_tools\trainer\i76trainer.py']     = Join-Path $repo 'tools\trainer\i76trainer.py'
$files['_tools\trainer\i76trn.h']          = Join-Path $repo 'tools\trainer\i76trn.h'
$files['_tools\trainer\README-GUI.md']     = Join-Path $repo 'tools\trainer\README-GUI.md'

& (Join-Path $PSScriptRoot 'Promote-To-Driver.ps1') -Plan:$Plan `
    -What 'all 2026-10-04 fixes: consolidated proxy 89a97d25 (music run end / disc order / shell 1997, ZGLIDE TMUFIX, FRAME_SPIKES, AI back-away grid, trainer cheat-marker guard, input latch); dgVoodoo TMU 8192 (wide + 16x10); best-wide + best-120 + I76_ZGLIDE_TMUFIX + I76_INPUT_LATCH; trainer (campaign-safe, Turn off cheater options) + save editor (--clear-cheat-options)' `
    -Gate 'lab copy game-test-20261004 (twin files), proxy 89a97d25, 2026-10-04: ignition/lights taps at 120 fps n=50 per key per condition: latch off I 13/50 H 7/50, latch on 50/50 + 50/50, stock 20 fps 50/50 + 50/50; cheat marker t01 forced win after one Esc-menu close: God/Ammo hold marker 0 + win advances (n=2 each), Repair/Teleport n=1, control n=3; old proxy f9b0c481 God n=2 / Ammo n=1 refused; Play Options 0x08 refused n=4; recovery (proxy uncheat n=1, i76trainer.py uncheat n=1) then win advances; save editor --clear-cheat-options 0x08 -> 0x00 on a scratch copy; gate rows 2-4 PLAY.bat 15/15 PASS, PLAY-16x10.bat 14/15 (only D: the launcher copies its own conf in) with best-wide/best-120 + TMUFIX + INPUT_LATCH + AI_BACKAWAY_GRID; soak t01+t05 0 spikes / 0 flushes / 0 rewinds / 0 crash, 120 fps' `
    -Files $files
Write-Host "staged confs / presets: $stage"
