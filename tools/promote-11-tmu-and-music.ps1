# Promotion 11 (DRAFT 2026-10-04, NOT RUN - the owner decides): render-freeze fix + music fixes.
#   1. dgVoodoo [Glide] MemorySizeOfTMU 2048 -> 8192 in dgVoodoo.wide.conf AND dgVoodoo.16x10.conf (NumberOfTMUs stays 1)
#   2. I76_ZGLIDE_TMUFIX = '1' in presets\best-wide.psd1 (PLAY.bat) AND presets\best-120.psd1 (PLAY-16x10.bat, which
#      copies the 16x10 conf in: 8192 without the ZGLIDE patch lets the 2 MB boundary rule rewind onto resident textures)
#   3. the merged proxy (music-fix\Strlkup.dll): I76_FRAME_SPIKES / I76_ZGLIDE_TMUFIX / CRASH modules line, the Mac
#      side's I76_MUSIC_RESUME + I76_MUSIC_GUARD (default on), and the music run-end fix (MCI_TO exclusive, default on;
#      I76_MUSIC_TO_INCLUSIVE=1 = old). I76_MUSIC_DISC_ORDER / I76_MUSIC_SHELL=1997 stay off (not in any preset).
# Never one part without the other: TMU 4096+ without I76_ZGLIDE_TMUFIX corrupts textures (lab RENDER-FREEZE-2026-10-04.md).
# The confs and presets are staged from the DRIVER's own current files (one line changed / added each), so nothing else in
# them moves; the script refuses if driver and golden differ in any of them. Run with the game closed; -Plan previews.
param([switch]$Plan)
$ErrorActionPreference = 'Stop'
$repo   = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$driver = 'C:\Users\james\Games\Interstate76-2026-10-03'
$golden = 'C:\Users\james\Games\Interstate76-golden-2026-10-03'
$stage  = Join-Path $env:TEMP "promote-11-$(Get-Date -Format yyyyMMdd-HHmmss)"
New-Item -ItemType Directory -Force $stage | Out-Null
function Md5([string]$p) { (Get-FileHash -LiteralPath $p -Algorithm MD5).Hash.ToLower() }

$files = @{ 'Interstate 76\STRLKUP.DLL' = (Join-Path $repo 'music-fix\Strlkup.dll') }

foreach ($c in 'dgVoodoo.wide.conf', 'dgVoodoo.16x10.conf') {
    $src = Join-Path $driver "Interstate 76\$c"
    if ((Md5 $src) -ne (Md5 (Join-Path $golden "Interstate 76\$c"))) { throw "REFUSED: $c differs between driver and golden" }
    $t = [IO.File]::ReadAllText($src)
    $n = ([regex]::Matches($t, '(?m)^MemorySizeOfTMU\s*=\s*2048\s*$')).Count
    if ($n -ne 1) { throw "REFUSED: $c has $n 'MemorySizeOfTMU = 2048' lines (expected exactly 1)" }
    $t = [regex]::Replace($t, '(?m)^(MemorySizeOfTMU\s*=\s*)2048(\s*)$', '${1}8192${2}')
    $out = Join-Path $stage $c; [IO.File]::WriteAllText($out, $t, [Text.Encoding]::ASCII)
    $files["Interstate 76\$c"] = $out
}
foreach ($p in 'best-wide.psd1', 'best-120.psd1') {
    $src = Join-Path $driver "Interstate 76\presets\$p"
    if ((Md5 $src) -ne (Md5 (Join-Path $golden "Interstate 76\presets\$p"))) { throw "REFUSED: $p differs between driver and golden" }
    $t = [IO.File]::ReadAllText($src)
    if ($t -match 'I76_ZGLIDE_TMUFIX') { throw "REFUSED: $p already names I76_ZGLIDE_TMUFIX" }
    $m = [regex]::Match($t, "(?m)^(\s*)I76_FAR_CLIP\s*=.*$")
    if (-not $m.Success) { throw "REFUSED: $p has no I76_FAR_CLIP line to anchor on" }
    $nl = if ($t.Contains("`r`n")) { "`r`n" } else { "`n" }
    $line = "$($m.Groups[1].Value)I76_ZGLIDE_TMUFIX   = '1'   # with dgVoodoo MemorySizeOfTMU 8192: no ZGLIDE flush freezes, no boundary rewind (lab RENDER-FREEZE-2026-10-04.md)"
    $t = $t.Insert($m.Index + $m.Length, $nl + $line)
    $out = Join-Path $stage $p; [IO.File]::WriteAllText($out, $t, [Text.Encoding]::ASCII)
    $null = Import-PowerShellDataFile $out      # still a valid preset
    $files["Interstate 76\presets\$p"] = $out
}

& (Join-Path $PSScriptRoot 'Promote-To-Driver.ps1') -Plan:$Plan `
    -What 'render freeze: dgVoodoo TMU 8192 (wide + 16x10) with I76_ZGLIDE_TMUFIX in best-wide + best-120; merged proxy (music run end exclusive, resume + guard default on, FRAME_SPIKES/TMUFIX switches)' `
    -Gate 'lab twin game-dd-20261003, 2026-10-04, proxy 3a2c6d4a: gate rows 2-4 PASS 15/15 via PLAY.bat (runs\gate\20261004-182500) and via PLAY-16x10.bat (runs\gate\20261004-183219), grTexMaxAddress 0x7ffff0 + tmufix logged, 120 fps; soak t01/t05/t11/t12 with I76_FRAME_SPIKES (lab docs\RENDER-FREEZE-2026-10-04.md section 7); music: docs\MUSIC-TRACK-MAP.md 2026-10-04 lab test' `
    -Files $files
Write-Host "staged confs / presets: $stage"
