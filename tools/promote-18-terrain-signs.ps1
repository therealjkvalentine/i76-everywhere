# Promotion 17 in PROMOTIONS.md (script 18; prepared 2026-10-12; NOT APPLIED until the console gate passes). The owner
# played TEST-next.bat on the lab twin (= the driver + I76_TERRAIN_HULL_FIX=1 + I76_BREAKABLE_BOX=3, proxy df7b3b0b):
# "looks really great. can the brush/bush draw distance and the terrain draw distance be as far as the road draw
# distance please? seems like the collision with the signs happens a little early again but it happens 100% of the
# time which is awesome. go for it". One promotion:
#   1. proxy = a build of i76-everywhere HEAD music-fix\strlkproxy.c (the repo source now builds the promoted binary; the
#      v3 telemetry / env_* cleanup of 2026-10-10 come along, all opt-in): I76_TERRAIN_HULL_FIX, I76_BREAKABLE_BOX=3/4,
#      I76_CLUTTER_DIST up to 2500 m + I76_CLUTTER_FADE, I76_TERRAIN_LOD up to 256 + the terrain vertex guard.
#   2. in best-wide, best-wide-balanced and best-120:
#      I76_TERRAIN_HULL_FIX = '1'   (no more cockpit ground drop-outs; lab TERRAIN-DROPOUT-HILL-2026-10-12.md s.10-11)
#      I76_BREAKABLE_BOX '1' -> '4' (sign posts fall at the first ram, when the DRAWN car reaches them; =4 = =3 + timing)
#      bushes: I76_CLUTTER_DIST + I76_CLUTTER_FADE (full density to the fade distance, thinning with distance beyond)
#      terrain: I76_TERRAIN_LOD (terrain detail distance; best-120 had none of the detail keys and gets the bush and
#      terrain keys too, as roads 1800 m came to all three in promotion 16). Values: $Dist below; balanced keeps its
#      1200 m far clip (bushes to 1200 m there).
#   Lab evidence: docs\DRAW-DISTANCE-2026-10-12.md (the cost matrix), docs\SIGN-FIX-3-2026-10-12.md (sign timing).
# HELD 2026-10-12 21:30 by the lead (owner: "the dream mission is failing because it is expecting you to stay on the road"; I76_ROAD_DIST
# is the suspect): do not stage, gate or apply until that cause is confirmed. Not gated (P9 not run); $GatedStage PENDING.
# HOLD LIFTED 2026-10-17 by the owner (09 variant); gated by P9 the same day; $GatedStage / $GateText filled; applied as row 17.
# Run with the game closed. -Plan previews; -Stage <dir> only writes the staged set there (the console gate P9 stages it
# into the lab twin). Applying refuses until $GatedStage holds the md5 of every staged file the gate passed with.
param([switch]$Plan, [string]$Stage)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'PromoteLib.ps1')
$repo   = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$stageDir = if ($Stage) { $Stage } else { Join-Path $env:TEMP "promote-18-$(Get-Date -Format yyyyMMdd-HHmmss)" }
New-Item -ItemType Directory -Force $stageDir | Out-Null

# 2026-10-17: the owner chose the 09 / TEST-next-dense variant (bushes at full density to 300 m, terrain x24) over the
# 08 thin variant (fade 200, x32), and the proxy is the twin's standing build 33211f11 (lab builds\box-spec-20261014
# STRLKUP-box-b3.dll, MSVC side build of i76-everywhere 2721d68 music-fix; = 855b08d7 + opt-in AI parity / W95-18
# instruments / pad menu) on which the owner played 08 / 09. The AI parity set the TEST-next* bats carry is NOT part
# of this promotion (OWNER-TEST-LIST item 36). Record: docs\records\PROMOTION-18-2026-10-17.md.
$CandDll = 'C:\Users\james\i76-uncap-lab\builds\box-spec-20261014\STRLKUP-box-b3.dll'
$CandMd5 = '33211f11'   # built from i76-everywhere 2721d68 music-fix (strlkproxy.c blob 03097a39)
$Dist = @{
    'best-wide.psd1'          = [ordered]@{ I76_CLUTTER_DIST = '1800'; I76_CLUTTER_FADE = '300'; I76_TERRAIN_LOD = '24' }
    'best-wide-balanced.psd1' = [ordered]@{ I76_CLUTTER_DIST = '1200'; I76_CLUTTER_FADE = '300'; I76_TERRAIN_LOD = '24' }
    'best-120.psd1'           = [ordered]@{ I76_CLUTTER_DIST = '1800'; I76_CLUTTER_FADE = '300'; I76_TERRAIN_LOD = '24' }
}
$Why = @{
    I76_CLUTTER_DIST = "bushes drawn to {0} m (was {1}; owner 2026-10-12: 'brush ... as far as the road draw distance')"
    I76_CLUTTER_FADE = "... at full density to 300 m like before, then thinned as (300 / d)^2 per bush (owner 2026-10-17 chose this dense variant, TEST-next-dense, over fade 200); with terrain x24 the T05 hill-top view costs the same as the fade-200 / x32 variant, lab DRAW-DISTANCE-2026-10-12.md"
    I76_TERRAIN_LOD  = "terrain detail split distance x{0} (was {1}; the split distance grows with the square root: x24 = about 1.7 x x8): distant mounds and ridges keep their shape; the vertex guard stops splits past 28,000 vertices a frame"
}
$GatedStage = [ordered]@{
    'Interstate 76\STRLKUP.DLL' = '33211f11'
    'Interstate 76\presets\best-wide.psd1' = '3922146a'
    'Interstate 76\presets\best-wide-balanced.psd1' = '0bca8b31'
    'Interstate 76\presets\best-120.psd1' = '9b53c141'
}
$GateText = 'lab twin game-dd-20261003 with this staged set, P9 2026-10-17 (lab autotest runs overnight-20261017-164128 / -164935 / -170258): T05 Texas 13 + US 380 shield rams =4 22/22 knocked over (2 rounds), drawn bumper-to-post gap at the fall median -0.08 m, range -0.28..-0.01 (never early), 21 by the sweep / 1 engine, 0 timeouts; T05 hill-top cockpit descents n=5: TERRAIN-LOSS 0, TRIANGLE-LOSS 0, start-pos 5/5; hill feature boot: hull fix on, breakable-box =4, 10 boxes, clutter 1800 fade 300, terrain-lod x24, vertex guard on; T05 swend_1 barricade rams G + BOX=4 7/7 contacted vs pooled control 3/15, Fisher p 0.0007, A/A p 0.57 (n short of the target 10 per condition); t11 roads soak best-wide n=2 / best-120 16x10 n=1 / balanced n=1: road-pool refusals 0, in mission; gate-folder via PLAY.bat (2x SS stretched_ar conf, LAB_CURSOR_FREE) 21 PASS 0 FAIL 2 INFO (runs\gate\20261017-165008: bookmark route, trip 2/2 at 120 fps, save screen, Esc-menu Exit, melee); row 3 PLAY-16x10.bat 2/2 120 fps and PLAY-balanced.bat 2/2 120 fps; garage OK popup closed 5/5, u32x arrow on the mapped point 4/4; kill lines (sign-sweep: fault, terrain-vguard refusals) 0 over 24 boots; 1 CRASH line, at quit: AcGenral.DLL+0x98AD3 in the exe HeapDestroy teardown, the known exit fault (lab RENDER-FREEZE-2026-10-04.md s.5; 3x in the driver log under older proxies), not in play. Owner played this variant (09 = TEST-next-dense) on the twin 2026-10-17 and chose it; the AI parity set it also carried is not included'

$files = [ordered]@{}
if ($CandMd5 -ne 'PENDING') { [void](Assert-BinaryMd5 -Path $CandDll -Want $CandMd5) }
$files['Interstate 76\STRLKUP.DLL'] = $CandDll

$driverPresetMd5 = @{ 'best-wide.psd1' = 'e1a9bd26'; 'best-wide-balanced.psd1' = '75881df4'; 'best-120.psd1' = 'df936278' }
function Replace-One([string]$t, [string]$pattern, [string]$with, [string]$what) {
    $m = [regex]::Matches($t, $pattern)
    if ($m.Count -ne 1) { throw "REFUSED: $what matched $($m.Count) times (want 1)" }
    return $t.Remove($m[0].Index, $m[0].Length).Insert($m[0].Index, $with)
}
function Replace-Line([string]$t, [string]$key, [string]$line, [string]$what) {   # the KEY line -> line, same indent
    $m = [regex]::Matches($t, "(?m)^([ 	]*)$key[ 	]*=[^
]*")
    if ($m.Count -ne 1) { throw "REFUSED: $what matched $($m.Count) times (want 1)" }
    return $t.Remove($m[0].Index, $m[0].Length).Insert($m[0].Index, $m[0].Groups[1].Value + $line)
}
function Line-After([string]$t, [string]$key, [string[]]$lines, [string]$nl) {
    $m = [regex]::Match($t, "(?m)^([ \t]*)$key[ \t]*=[^\r\n]*")
    if (-not $m.Success) { throw "REFUSED: no $key line" }
    return $t.Insert($m.Index + $m.Length, (($lines | ForEach-Object { $nl + $m.Groups[1].Value + $_ }) -join ''))
}
foreach ($p in 'best-wide.psd1', 'best-wide-balanced.psd1', 'best-120.psd1') {
    $src = Assert-DriverEqualsGolden -Rel "Interstate 76\presets\$p"
    [void](Assert-BinaryMd5 -Path $src -Want $driverPresetMd5[$p])
    $t = [IO.File]::ReadAllText($src)
    $base = (Import-PowerShellDataFile $src).Env
    foreach ($k in 'I76_TERRAIN_HULL_FIX', 'I76_CLUTTER_FADE') { if ($t -match "(?m)^\s*$k\s*=") { throw "REFUSED: $p already sets $k" } }
    if ("$($base.I76_BREAKABLE_BOX)" -ne '1') { throw "REFUSED: $p has I76_BREAKABLE_BOX = '$($base.I76_BREAKABLE_BOX)', want '1' (promotion 16)" }
    $nl = if ($t.Contains("`r`n")) { "`r`n" } else { "`n" }
    $d = $Dist[$p]
    # hull fix after the camera ground fix
    $t = Line-After $t 'I76_CAM_GROUND_FIX' @("I76_TERRAIN_HULL_FIX = '1'   # the near ground no longer vanishes for a frame in cockpit view (footprint hull rebuilt; lab TERRAIN-DROPOUT-HILL-2026-10-12.md s.10-11)") $nl
    # sign timing
    $t = Replace-Line $t 'I76_BREAKABLE_BOX' ("I76_BREAKABLE_BOX   = '4'   # bar as a box (=1) + sign posts fall at the first ram, when the drawn car reaches them (sign-post sweep + render-interp timing; lab SIGN-FIX-3-2026-10-12.md)") "$p I76_BREAKABLE_BOX"
    # bushes and terrain
    $oldC = if ($base.ContainsKey('I76_CLUTTER_DIST')) { "$($base.I76_CLUTTER_DIST) m" } else { 'stock 120 m' }
    $oldT = if ($base.ContainsKey('I76_TERRAIN_LOD')) { "x$($base.I76_TERRAIN_LOD)" } else { 'stock x1' }
    $lc = "I76_CLUTTER_DIST    = '$($d.I76_CLUTTER_DIST)'   # " + ($Why.I76_CLUTTER_DIST -f $d.I76_CLUTTER_DIST, $oldC)
    $lf = "I76_CLUTTER_FADE    = '$($d.I76_CLUTTER_FADE)'   # " + $Why.I76_CLUTTER_FADE
    $lt = "I76_TERRAIN_LOD     = '$($d.I76_TERRAIN_LOD)'   # " + ($Why.I76_TERRAIN_LOD -f $d.I76_TERRAIN_LOD, $oldT)
    if ($base.ContainsKey('I76_CLUTTER_DIST')) {
        $t = Replace-Line $t 'I76_CLUTTER_DIST' $lc "$p I76_CLUTTER_DIST"
        $t = Line-After $t 'I76_CLUTTER_DIST' @($lf) $nl
        $t = Replace-Line $t 'I76_TERRAIN_LOD' $lt "$p I76_TERRAIN_LOD"
    } else {
        if ($t -match "(?m)^\s*I76_TERRAIN_LOD\s*=") { throw "REFUSED: $p sets I76_TERRAIN_LOD without I76_CLUTTER_DIST" }
        $t = Line-After $t 'I76_ROAD_DIST' @($lc, $lf, $lt) $nl
    }
    $out = Join-Path $stageDir $p; [IO.File]::WriteAllText($out, $t, [Text.Encoding]::ASCII)
    $e = (Import-PowerShellDataFile $out).Env
    $want = [ordered]@{ I76_TERRAIN_HULL_FIX = '1'; I76_BREAKABLE_BOX = '4' }; foreach ($k in $d.Keys) { $want[$k] = $d[$k] }
    foreach ($k in $want.Keys) { if ("$($e[$k])" -ne $want[$k]) { throw "REFUSED: staged $p reads $k = '$($e[$k])', want '$($want[$k])'" } }
    if (-not $e.I76_FAR_CLIP) { throw "REFUSED: staged $p has no I76_FAR_CLIP (I76_TERRAIN_LOD needs it)" }
    $diff = @(@($e.Keys) + @($base.Keys) | Sort-Object -Unique | Where-Object { "$($e[$_])" -ne "$($base[$_])" })
    $wk = @($want.Keys | Where-Object { "$($base[$_])" -ne $want[$_] } | Sort-Object)
    if (($diff -join ',') -ne ($wk -join ',')) { throw "REFUSED: staged $p changes $($diff -join ', '), want exactly $($wk -join ', ')" }
    $files["Interstate 76\presets\$p"] = $out
}

$staged = [ordered]@{}
foreach ($rel in $files.Keys) { $staged[$rel] = (Get-Md5 $files[$rel]).Substring(0, 8) }
if ($Stage) {
    foreach ($rel in $files.Keys) {
        $dst = Join-Path $stageDir "set\$rel"; New-Item -ItemType Directory -Force (Split-Path $dst) | Out-Null
        Copy-Item -LiteralPath $files[$rel] -Destination $dst -Force
        if ((Get-Md5 $dst).Substring(0, 8) -ne $staged[$rel]) { throw "REFUSED: staged copy of $rel did not read back" }
    }
    ($files.Keys | ForEach-Object { "{0}`t{1}" -f $staged[$_], $_ }) | Set-Content (Join-Path $stageDir 'manifest.tsv') -Encoding ASCII
    foreach ($rel in $files.Keys) { "{0}  {1}  <- {2}" -f $staged[$rel], $rel, $files[$rel] }
    return
}
$pending = @($files.Keys | Where-Object { $GatedStage[$_] -ne $staged[$_] }) + @($GatedStage.Keys | Where-Object { -not $files.Contains($_) })
if ($pending.Count -or $GateText -like 'PENDING*' -or $CandMd5 -eq 'PENDING') {
    $msg = "the console gate has not passed for this staged set (" + ($pending -join '; ') + ")"
    if (-not $Plan) { Write-Host "REFUSED: $msg" -ForegroundColor Red; exit 2 }
    Write-Host "plan only - $msg" -ForegroundColor Yellow
}
$ht = @{}; foreach ($rel in $files.Keys) { $ht[$rel] = $files[$rel] }
& (Join-Path $PSScriptRoot 'Promote-To-Driver.ps1') -Plan:$Plan `
    -What 'TEST-next + the owner''s two requests (2026-10-12): I76_TERRAIN_HULL_FIX=1; I76_BREAKABLE_BOX 1 -> 4 (sign posts fall at the first ram when the drawn car reaches them); bushes to the road distance, dense variant chosen by the owner 2026-10-17 (I76_CLUTTER_DIST 1800 / balanced 1200 + I76_CLUTTER_FADE 300); terrain detail I76_TERRAIN_LOD 8 -> 24 (best-120: new); proxy 33211f11 (i76-everywhere 2721d68); the AI parity set is not included' `
    -Gate $GateText `
    -Files $ht
Write-Host "staged: $stageDir"
