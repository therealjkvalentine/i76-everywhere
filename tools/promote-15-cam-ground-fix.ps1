# Promotion 14 in PROMOTIONS.md (script 15, 2026-10-05): the terrain-to-sky flash fix.
#   1. proxy music-fix\Strlkup.dll built from i76-everywhere main with I76_CAM_GROUND_FIX (+ I76_FLASH_PROBE and
#      I76_MIRROR_RATE=2, both opt-in and in no preset; also carries the opt-in I76_JOY_MAP / I76_JOY_SYNTH /
#      I76_NO_MINIMIZE of 54049d6 / ef8564c). The driver runs 89a97d25.
#   2. presets best-wide, best-wide-balanced and best-120: + I76_CAM_GROUND_FIX = '1' (one line each, only if missing),
#      staged from the DRIVER's own files so nothing else in them moves; refuses if driver and golden differ.
# Mechanism (lab docs/RENDER-FREEZE-2026-10-04.md s.9): renderer_QueueTerrain skips ALL terrain for a frame when the eye
# is < 0.01 m above the terrain height under it (0x4929b0 -> 0 at 0x492a13); the sky drawn before stays = the flash.
# The fix lifts the camera 0.05 m above the ground for the terrain SETUP only (footprint/quadtree), the view is unchanged.
# Run with the game closed; -Plan previews and writes nothing.
param([switch]$Plan)
$ErrorActionPreference = 'Stop'
$repo   = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$driver = 'C:\Users\james\Games\Interstate76-2026-10-03'
$golden = 'C:\Users\james\Games\Interstate76-golden-2026-10-03'
$stage  = Join-Path $env:TEMP "promote-15-$(Get-Date -Format yyyyMMdd-HHmmss)"
New-Item -ItemType Directory -Force $stage | Out-Null
function Md5([string]$p) { (Get-FileHash -LiteralPath $p -Algorithm MD5).Hash.ToLower() }

$dll = Join-Path $repo 'music-fix\Strlkup.dll'
$tested = 'd603cccf'
if ((Md5 $dll).Substring(0, 8) -ne $tested) { throw "REFUSED: music-fix\Strlkup.dll is $((Md5 $dll).Substring(0, 8)), not the gated $tested (rebuilt since? re-gate it first)" }
$files = @{ 'Interstate 76\STRLKUP.DLL' = $dll }

# md5 of each staged preset as gated on the lab twin (driver file + this one line), 2026-10-05
$gated = @{ 'best-wide.psd1' = '7f0da1672542cd0827ac2d0b45b38178'; 'best-wide-balanced.psd1' = '89222f80209d5992e4ea31eb3efc6169'; 'best-120.psd1' = '3c12c8d05bfcb6b3eb0f734bb32c307f' }
$line = "I76_CAM_GROUND_FIX  = '1'   # terrain kept when the eye dips under the ground (stock skips ALL terrain that frame = the terrain-to-sky flash; lab RENDER-FREEZE-2026-10-04.md s.9)"
foreach ($p in 'best-wide.psd1', 'best-wide-balanced.psd1', 'best-120.psd1') {
    $src = Join-Path $driver "Interstate 76\presets\$p"
    if ((Md5 $src) -ne (Md5 (Join-Path $golden "Interstate 76\presets\$p"))) { throw "REFUSED: $p differs between driver and golden" }
    $t = [IO.File]::ReadAllText($src)
    if ($t -match '(?m)^\s*I76_CAM_GROUND_FIX\s*=') { Write-Host "$p already sets I76_CAM_GROUND_FIX - left as is"; continue }
    $nl = if ($t.Contains("`r`n")) { "`r`n" } else { "`n" }
    $m = [regex]::Match($t, '(?m)^([ \t]*)I76_FAR_CLIP[ \t]*=[^\r\n]*')
    if (-not $m.Success) { throw "REFUSED: $p has no I76_FAR_CLIP line to anchor on" }
    $t = $t.Insert($m.Index + $m.Length, $nl + $m.Groups[1].Value + $line)
    $out = Join-Path $stage $p; [IO.File]::WriteAllText($out, $t, [Text.Encoding]::ASCII)
    if ((Import-PowerShellDataFile $out).Env.I76_CAM_GROUND_FIX -ne '1') { throw "REFUSED: staged $p does not read back the switch" }
    if ((Md5 $out) -ne $gated[$p]) { throw "REFUSED: staged $p is $(Md5 $out), not the gated $($gated[$p]) (driver preset changed since the gate?)" }
    $files["Interstate 76\presets\$p"] = $out
}

& (Join-Path $PSScriptRoot 'Promote-To-Driver.ps1') -Plan:$Plan `
    -What 'terrain-to-sky flash fix: proxy with I76_CAM_GROUND_FIX (+ opt-in I76_FLASH_PROBE, I76_MIRROR_RATE=2); best-wide, best-wide-balanced, best-120 + I76_CAM_GROUND_FIX' `
    -Gate 'lab twin game-dd-20261003 (= driver after promotion 13), proxy d603cccf, 2026-10-05: deterministic test (car held 3 m under its resting height for 8 s, t04, proxy trainer FREEZE_POS) n=3 each: without the switch 0 terrain vertices for the whole hold, sky below the horizon; with it 0 zero-terrain frames, ~1930 lifts per hold, 0 refused, ground drawn; t04 god-mode circle drives 150 s: zero-terrain events 3/3/0 without (n=3), 0 with (n=4, 378 lifts in one); gate rows 2-4 through PLAY.bat with best-wide + I76_CAM_GROUND_FIX 15/15 PASS (runs\gate\20261005-112713), row 3 through PLAY-16x10.bat (best-120 + switch) 2/2 at 120 fps, only D (the launcher copies its own conf in; runs\gate\20261005-113421); 0 CRASH (lab docs/RENDER-FREEZE-2026-10-04.md s.9)' `
    -Files $files
Write-Host "staged presets: $stage"
