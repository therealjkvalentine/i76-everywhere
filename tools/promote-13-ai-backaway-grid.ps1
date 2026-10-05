# Promotion 13 (2026-10-05): I76_AI_BACKAWAY_GRID = '1' in presets\best-wide.psd1 (PLAY.bat) and presets\best-120.psd1
# (PLAY-16x10.bat). The switch is already in the driver's proxy 89a97d25 (promotion 11); this only turns it on.
# The AI back_away stuck test (4 ring samples < 0.1, indexed by the frame stamp) then counts 20 Hz grid ticks instead of
# rendered frames, so at 120 fps a car still settling at spawn no longer reverses (T12 milk-truck opening).
# Presets are staged from the DRIVER's own current files (one line added, only where missing; nothing else moves);
# refuses if driver and golden differ in either. Run with the game closed; -Plan previews and writes nothing.
param([switch]$Plan)
$ErrorActionPreference = 'Stop'
$driver = 'C:\Users\james\Games\Interstate76-2026-10-03'
$golden = 'C:\Users\james\Games\Interstate76-golden-2026-10-03'
$stage  = Join-Path $env:TEMP "promote-13-$(Get-Date -Format yyyyMMdd-HHmmss)"
New-Item -ItemType Directory -Force $stage | Out-Null
function Md5([string]$p) { (Get-FileHash -LiteralPath $p -Algorithm MD5).Hash.ToLower() }

$k = 'I76_AI_BACKAWAY_GRID'
# the exact line the twin's gated presets carry, so the staged files are byte-identical to the ones tested
$line = "I76_AI_BACKAWAY_GRID = '1'   # AI back_away stuck test on the 20 Hz grid, not 4 rendered frames: T12 opening 5/5 as vanilla (lab 2026-10-04 milk-truck doc s7-9)"
$files = @{}
foreach ($p in 'best-wide.psd1', 'best-120.psd1') {
    $src = Join-Path $driver "Interstate 76\presets\$p"
    if ((Md5 $src) -ne (Md5 (Join-Path $golden "Interstate 76\presets\$p"))) { throw "REFUSED: $p differs between driver and golden" }
    $t = [IO.File]::ReadAllText($src)
    if ($t -match "(?m)^\s*$k\s*=") { Write-Host "$p already sets $k - left as is"; continue }
    $nl = if ($t.Contains("`r`n")) { "`r`n" } else { "`n" }
    $m = [regex]::Match($t, "(?m)^(\s*)I76_FAR_CLIP\s*=.*$")
    if (-not $m.Success) { throw "REFUSED: $p has no I76_FAR_CLIP line to anchor on" }
    $t = $t.Insert($m.Index + $m.Length, $nl + $m.Groups[1].Value + $line)
    $out = Join-Path $stage $p; [IO.File]::WriteAllText($out, $t, [Text.Encoding]::ASCII)
    $e = (Import-PowerShellDataFile $out).Env
    if ($e.$k -ne '1' -or $e.I76_ZGLIDE_TMUFIX -ne '1' -or $e.I76_INPUT_LATCH -ne '1') { throw "REFUSED: staged $p does not read back $k / TMUFIX / INPUT_LATCH" }
    $files["Interstate 76\presets\$p"] = $out
}
if ($files.Count -eq 0) { Write-Host 'nothing to promote: both presets already set the switch.'; exit 0 }

& (Join-Path $PSScriptRoot 'Promote-To-Driver.ps1') -Plan:$Plan `
    -What 'AI back-away grid on: best-wide (PLAY.bat) + best-120 (PLAY-16x10.bat) + I76_AI_BACKAWAY_GRID = 1 (switch already in proxy 89a97d25)' `
    -Gate 'lab twin game-dd-20261003 synced to the driver (proxy 89a97d25, TMU 8192), presets + I76_AI_BACKAWAY_GRID, 2026-10-05: gate-folder rows 2-4 PLAY.bat 14/15 (runs\gate\20261005-082031) and PLAY-16x10.bat 14/15 (20261005-082723), the one FAIL each = row D, the launcher copies its own conf in (as in every earlier gate); route 3/3 to B1.10 + trip 2/2 at 120 fps each; proxy logged ai-backaway-grid read back ok in all 4 launcher sessions, 0 CRASH; T12 opening best-wide n=2 + best-120 n=1: cut 6.6 s 3/3, no east excursion (vanilla 6.6 s 7/7; best-wide without the switch 0/5); 2026-10-04: T12 n=5 5/5, pinned-AI back_away still fires, t01/t05/t11 openings unchanged' `
    -Files $files
Write-Host "staged presets: $stage"
