# Promotion 16 in PROMOTIONS.md (script 17, prepared 2026-10-12; NOT APPLIED until the console gate passes): collision G.
#   1. proxy a6d621fd (lab builds\sign-fix-20261012\STRLKUP-signfix-v2tel.dll: the twin's source line 552dcb4 + =3 +
#      the coll-timing patch (I76_COLL_WINDOW_WHEN / _SCALE, I76_BREAKABLE_BOX, I76_START_POS) + the sign-fix patch
#      (I76_BREAKABLE_BOX=2); v2 telemetry, so the trainer GUI keeps working). Everything new is off unless a preset sets it.
#   2. PLAY-i76.ps1 2020e2bf from the repo (head tracking OPT-IN with -HeadTrack, cursor overlay OPT-IN with -CursorOverlay; owner 2026-10-12: "we don't want
#      opentrack for experiments or even by default anywhere right now"; HEADTRACK.bat is its own AHK launcher).
#   3. presets best-wide, best-wide-balanced AND best-120, staged from the DRIVER's own files: I76_COLL_DEDUPE '0' -> '1'
#      and + I76_COLL_WINDOW = '2', I76_COLL_WINDOW_WHEN = 'stepframe', I76_BREAKABLE_BOX = '1' (G as the owner played it,
#      lab TEST-hill-G-stepframe-barbox.bat, 2026-10-12: "G is fantastic ... we should keep G if it doesn't break anything").
#      best-120 too: PLAY-16x10.bat runs it with the same I76_FIXED_STEP=24 at 120 fps, which is what makes about 2 in 3
#      barricades pass through (lab docs\COLLISION-MISS-2026-10-08.md); without it the 16x10 launcher would be the one
#      fixed-step launcher that still misses them. The gate runs row 3 through PLAY-16x10.bat for that reason.
# Why: at 120 fps with the fixed step most frames run no physics step and the stock accept (t <= frame dt) drops most
# contacts with breakables (control 21 % per entry plane); =2 accepts the whole step, stepframe only on the frame whose
# tick moves the car (no early fly-off), BREAKABLE_BOX=1 makes the 8 m barricade bar a box instead of a 3 m sphere
# (lab docs\COLL-TIMING-2026-10-12.md; audit docs\SIGN-FIX-2026-10-12.md: the rule boxes swend_1 (18 placements in
# t05/t06/t15/s03) and one t08 swpla_1 panel only).
# Run with the game closed. -Plan previews (works before the gate); -Stage <dir> only writes the staged set there (the
# console gate stages it into the lab twin). Applying refuses until $GatedStage below holds the md5s the gate passed with.
param([switch]$Plan, [string]$Stage)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'PromoteLib.ps1')
$repo   = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$driver = $script:PromoteDriver
$golden = $script:PromoteGolden
$stageDir = if ($Stage) { $Stage } else { Join-Path $env:TEMP "promote-17-$(Get-Date -Format yyyyMMdd-HHmmss)" }
New-Item -ItemType Directory -Force $stageDir | Out-Null

# the gate fills these in (md5 of every staged file it ran with); 'PENDING' = not gated yet -> apply refuses
$GatedStage = [ordered]@{
    'Interstate 76\presets\best-wide.psd1'          = 'PENDING'
    'Interstate 76\presets\best-wide-balanced.psd1' = 'PENDING'
    'Interstate 76\presets\best-120.psd1'           = 'PENDING'
}
$GateText = 'PENDING: lab autotest\overnight\phases\P8-promote17.ps1 (run-overnight.ps1 -Phase P8) on the twin with this staged set - gate-folder 23 rows via PLAY.bat (LAB_GAME_ENV + LAB_CURSOR_FREE), row 3 via PLAY-16x10.bat and PLAY-balanced.bat, T05 barricade rams G vs control n>=21 each, 8+8 t04 drives, hill-top start check'

$bins = [ordered]@{
    'Interstate 76\STRLKUP.DLL'  = @('C:\Users\james\i76-uncap-lab\builds\sign-fix-20261012\STRLKUP-signfix-v2tel.dll', 'a6d621fd')
    'Interstate 76\PLAY-i76.ps1' = @((Join-Path $repo 'PLAY-i76.ps1'), '2020e2bf')
}
$files = [ordered]@{}
foreach ($rel in $bins.Keys) {
    [void](Assert-BinaryMd5 -Path $bins[$rel][0] -Want $bins[$rel][1])
    $files[$rel] = $bins[$rel][0]
}

# the driver presets this was prepared against (2026-10-12; = golden = the lab twin's)
$driverPresetMd5 = @{ 'best-wide.psd1' = '8de71421'; 'best-wide-balanced.psd1' = 'a2191719'; 'best-120.psd1' = '3c12c8d0' }
$G = [ordered]@{ I76_COLL_DEDUPE = '1'; I76_COLL_WINDOW = '2'; I76_COLL_WINDOW_WHEN = 'stepframe'; I76_BREAKABLE_BOX = '1' }
foreach ($p in 'best-wide.psd1', 'best-wide-balanced.psd1', 'best-120.psd1') {
    $src = Assert-DriverEqualsGolden -Rel "Interstate 76\presets\$p"
    [void](Assert-BinaryMd5 -Path $src -Want $driverPresetMd5[$p])
    $t = [IO.File]::ReadAllText($src)
    foreach ($k in 'I76_COLL_WINDOW', 'I76_COLL_WINDOW_WHEN', 'I76_BREAKABLE_BOX') { if ($t -match "(?m)^\s*$k\s*=") { throw "REFUSED: $p already sets $k" } }
    $m = [regex]::Matches($t, "(?m)^([ \t]*)I76_COLL_DEDUPE([ \t]*)=[ \t]*'0'[^\r\n]*")
    if ($m.Count -ne 1) { throw "REFUSED: $p has $($m.Count) I76_COLL_DEDUPE = '0' lines (want 1)" }
    $nl = if ($t.Contains("`r`n")) { "`r`n" } else { "`n" }
    $ind = $m[0].Groups[1].Value
    $new = @(
        "I76_COLL_DEDUPE     = '1'   # one impact = one sound / damage per physics step (collision G, lab COLL-TIMING-2026-10-12.md)",
        "I76_COLL_WINDOW     = '2'   # contacts accepted over the whole physics step: barricades and signs hit at 120 fps (control: about 1 in 3)",
        "I76_COLL_WINDOW_WHEN = 'stepframe'   # ... only on the frame whose step moves the car: no fly-off before the bumper gets there",
        "I76_BREAKABLE_BOX   = '1'   # the 8 m barricade bar collides as the bar, not as a 3 m sphere reaching out in front of it"
    ) | ForEach-Object { $ind + $_ }
    $t = $t.Remove($m[0].Index, $m[0].Length).Insert($m[0].Index, ($new -join $nl))
    $out = Join-Path $stageDir $p; [IO.File]::WriteAllText($out, $t, [Text.Encoding]::ASCII)
    $e = (Import-PowerShellDataFile $out).Env
    foreach ($k in $G.Keys) { if ("$($e[$k])" -ne $G[$k]) { throw "REFUSED: staged $p reads $k = '$($e[$k])', want '$($G[$k])'" } }
    if ("$($e.I76_FIXED_STEP)" -ne '24') { throw "REFUSED: staged $p has no I76_FIXED_STEP = '24' (the window needs the fixed step)" }
    $base = (Import-PowerShellDataFile $src).Env
    $diff = @(@($e.Keys) + @($base.Keys) | Sort-Object -Unique | Where-Object { "$($e[$_])" -ne "$($base[$_])" })
    if (($diff -join ',') -ne ((@($G.Keys) | Sort-Object) -join ',')) { throw "REFUSED: staged $p changes $($diff -join ', '), want exactly $(@($G.Keys) -join ', ')" }
    $files["Interstate 76\presets\$p"] = $out
}

$staged = [ordered]@{}
foreach ($rel in $files.Keys) { $staged[$rel] = (Get-Md5 $files[$rel]).Substring(0, 8) }
if ($Stage) {
    foreach ($rel in $files.Keys) { "{0}  {1}  <- {2}" -f $staged[$rel], $rel, $files[$rel] }
    return
}
$pending = @($GatedStage.Keys | Where-Object { $GatedStage[$_] -ne $staged[$_] })
if ($pending.Count -or $GateText -like 'PENDING*') {
    $msg = "the console gate has not passed for this staged set: " + (($GatedStage.Keys | ForEach-Object { "$_ staged $($staged[$_]) gated $($GatedStage[$_])" }) -join '; ')
    if (-not $Plan) { Write-Host "REFUSED: $msg" -ForegroundColor Red; exit 2 }
    Write-Host "plan only - $msg" -ForegroundColor Yellow
}
& (Join-Path $PSScriptRoot 'Promote-To-Driver.ps1') -Plan:$Plan `
    -What 'collision G (PLAY.bat, PLAY-balanced.bat, PLAY-16x10.bat): proxy a6d621fd (I76_COLL_WINDOW_WHEN, I76_BREAKABLE_BOX, I76_START_POS, all opt-in) + best-wide, best-wide-balanced, best-120 with I76_COLL_DEDUPE=1, I76_COLL_WINDOW=2, I76_COLL_WINDOW_WHEN=stepframe, I76_BREAKABLE_BOX=1; launcher PLAY-i76.ps1 2020e2bf (head tracking and the cursor overlay opt-in)' `
    -Gate $GateText `
    -Files $files
Write-Host "staged: $stageDir"
