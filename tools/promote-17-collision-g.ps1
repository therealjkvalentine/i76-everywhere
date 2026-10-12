# Promotion 16 in PROMOTIONS.md (script 17; prepared 2026-10-12, widened the same day to the owner-verified set; NOT
# APPLIED until the console gate passes). What the owner played on the lab twin on 2026-10-12, as one promotion:
#   1. proxy 509c6df0 (lab builds\terrain-probe-20261012\STRLKUP-drawprobe-v2tel.dll = the sign-fix source a6d621fd +
#      the opt-in I76_DRAW_PROBE census; v2 telemetry, so the trainer keeps working). The build the twin ran for every
#      owner session of the day (hill G, road 1800, shimmer S). Everything new is off unless a preset sets it.
#   2. collision G in best-wide, best-wide-balanced AND best-120: I76_COLL_DEDUPE '0' -> '1', + I76_COLL_WINDOW = '2',
#      I76_COLL_WINDOW_WHEN = 'stepframe', I76_BREAKABLE_BOX = '1' (owner, TEST-hill-G-stepframe-barbox: "G is fantastic";
#      NOT =2: the sign-fix variant H did not work for the owner). best-120 too: PLAY-16x10.bat runs the same
#      I76_FIXED_STEP=24 at 120 fps, which is what makes about 2 in 3 barricades pass through (lab
#      docs\COLLISION-MISS-2026-10-08.md, COLL-TIMING-2026-10-12.md).
#   3. road draw distance: I76_ROAD_DIST = '1800' in best-wide and best-120 (both far clip 1800; owner, TEST-hill-G-road1800:
#      "road at 1800 seems to run fine"; the 2026-10-03 t11 boot crash at 1800 was the road node pool, fixed by
#      I76_ROAD_POOL since promotion 8, auto-on with the far clip), '1200' in best-wide-balanced (its far clip is 1200:
#      road past the far clip is never drawn, and balanced exists to trim cost; lab t11 cockpit 1800 m 105-115 fps vs 1200 m
#      11.8 ms p99). The 2026-10-03 "I76_ROAD_DIST removed" comment line goes.
#   4. real supersampling: dgVoodoo.wide.conf = the measured lab conf dgVoodoo.wide-win2x-ar.conf (9c1ac5bc) with a new
#      header comment only (tools\conf\dgVoodoo.daily-wide-ss2x-2026-10-12.conf): ScalingMode stretched_ar, [Glide]
#      6880x2880 + 4x (owner, TEST-shimmer-S-win2x-ar: "S looks pretty awesome"). The 640x480 menus / movies are 4:3 with
#      side bars instead of stretched. Pointer: u32x 06467bd2 reads ScalingMode from dgVoodoo.conf and maps the shell
#      over the 4:3 fit when it is not 'stretched' (u32x_full.c shell_fills_client), so I76_U32X_SHELL_STRETCH = '1'
#      stays (it only fills the client for 'stretched'); the proxy's I76_CURSOR_MAP=1 (stretched) maps i76.exe's Esc
#      menu over the whole client, which is right: the 6880x2880 frame has the window's 21:9 shape, so _ar draws it full
#      width. Preset comments that said "ScalingMode stretched" / "menus stretched sideways" are rewritten.
#   5. PLAY-i76.ps1 2020e2bf from the repo (head tracking OPT-IN with -HeadTrack, cursor overlay OPT-IN with -CursorOverlay;
#      owner: "we don't want opentrack for experiments or even by default anywhere right now").
#   6. I76 Debug (tools\debug) in _tools\debug + the files it imports (_tools\telemetry i76tel.py / i76tel.h / i76tel_v2.h,
#      _tools\trainer i76trainer_gui.py / README-GUI.md / waypoints.json; i76trainer.py and i76trn.h are already current),
#      DEBUG.bat at the root (tools\driver\DEBUG.bat) and TRAINER.bat repointed to it (i76debug.py --any --tab trainer;
#      --classic = the old window). Owner: "not sure how to launch the trainer ... maybe drop a bat file in".
# Run with the game closed. -Plan previews; -Stage <dir> only writes the staged set there (the console gate stages it into
# the lab twin). Applying refuses until $GatedStage below holds the md5 of every staged file the gate passed with.
param([switch]$Plan, [string]$Stage)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'PromoteLib.ps1')
$repo   = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$driver = $script:PromoteDriver
$golden = $script:PromoteGolden
$stageDir = if ($Stage) { $Stage } else { Join-Path $env:TEMP "promote-17-$(Get-Date -Format yyyyMMdd-HHmmss)" }
New-Item -ItemType Directory -Force $stageDir | Out-Null

# the gate fills these in (md5 prefix of every staged file it ran with); 'PENDING' = not gated yet -> apply refuses
$GatedStage = [ordered]@{ '*' = 'PENDING' }
$GateText = 'PENDING: lab autotest\overnight\phases\P8-promote17.ps1 (run-overnight.ps1 -Phase P8) on the twin with this staged set'

# ---- fixed sources (md5 pinned)
$bins = [ordered]@{
    'Interstate 76\STRLKUP.DLL'        = @('C:\Users\james\i76-uncap-lab\builds\terrain-probe-20261012\STRLKUP-drawprobe-v2tel.dll', '509c6df0')
    'Interstate 76\PLAY-i76.ps1'       = @((Join-Path $repo 'PLAY-i76.ps1'), '2020e2bf')
    'Interstate 76\dgVoodoo.wide.conf' = @((Join-Path $repo 'tools\conf\dgVoodoo.daily-wide-ss2x-2026-10-12.conf'), 'dccd379a')
}
$files = [ordered]@{}
foreach ($rel in $bins.Keys) {
    [void](Assert-BinaryMd5 -Path $bins[$rel][0] -Want $bins[$rel][1])
    $files[$rel] = $bins[$rel][0]
}
# the conf is the measured lab conf with only its header changed: check that against the lab file itself
$labConf = 'C:\Users\james\i76-uncap-lab\game-dd-20261003\Interstate 76\dgVoodoo.wide-win2x-ar.conf'
if (Test-Path -LiteralPath $labConf) {
    [void](Assert-BinaryMd5 -Path $labConf -Want '9c1ac5bc')
    $body = { param($p, $skip) (Get-Content -LiteralPath $p | Select-Object -Skip $skip) -join "`n" }
    if ((& $body $labConf 1) -ne (& $body $files['Interstate 76\dgVoodoo.wide.conf'] 8)) { throw 'REFUSED: tools\conf\dgVoodoo.daily-wide-ss2x-2026-10-12.conf is not the lab 9c1ac5bc conf below its header' }
}
$ci = Get-Content -LiteralPath $files['Interstate 76\dgVoodoo.wide.conf']
foreach ($want in '^\s*ScalingMode\s*=\s*stretched_ar\s*$', '^\s*Resolution\s*=\s*6880x2880\s*$', '^\s*Antialiasing\s*=\s*4x\s*$', '^\s*CaptureMouse\s*=\s*false\s*$', '^\s*FullScreenMode\s*=\s*false\s*$') {
    if (-not ($ci -match $want)) { throw "REFUSED: staged wide conf has no line matching $want" }
}

# ---- I76 Debug + the modules it imports (repo tools\ -> driver _tools\), and the two root launchers
$tools = [ordered]@{
    '_tools\debug\i76debug.py' = 'tools\debug\i76debug.py'; '_tools\debug\debug_core.py' = 'tools\debug\debug_core.py'
    '_tools\debug\debug_trainer.py' = 'tools\debug\debug_trainer.py'; '_tools\debug\README.md' = 'tools\debug\README.md'
    '_tools\debug\static\index.html' = 'tools\debug\static\index.html'; '_tools\debug\static\app.js' = 'tools\debug\static\app.js'
    '_tools\debug\static\app.css' = 'tools\debug\static\app.css'; '_tools\debug\static\charts.js' = 'tools\debug\static\charts.js'
    '_tools\telemetry\i76tel.py' = 'tools\telemetry\i76tel.py'; '_tools\telemetry\i76tel.h' = 'tools\telemetry\i76tel.h'
    '_tools\telemetry\i76tel_v2.h' = 'tools\telemetry\i76tel_v2.h'
    '_tools\trainer\i76trainer.py' = 'tools\trainer\i76trainer.py'; '_tools\trainer\i76trainer_gui.py' = 'tools\trainer\i76trainer_gui.py'
    '_tools\trainer\i76trn.h' = 'tools\trainer\i76trn.h'; '_tools\trainer\README-GUI.md' = 'tools\trainer\README-GUI.md'
    '_tools\trainer\waypoints.json' = 'tools\trainer\waypoints.json'
    'DEBUG.bat' = 'tools\driver\DEBUG.bat'; 'TRAINER.bat' = 'tools\driver\TRAINER.bat'
}
foreach ($rel in $tools.Keys) {
    $src = Join-Path $repo $tools[$rel]
    if (-not (Test-Path -LiteralPath $src)) { throw "REFUSED: missing $src" }
    $files[$rel] = $src
}

# ---- presets, staged from the DRIVER's own files (2026-10-12; = golden = the lab twin's)
$driverPresetMd5 = @{ 'best-wide.psd1' = '8de71421'; 'best-wide-balanced.psd1' = 'a2191719'; 'best-120.psd1' = '3c12c8d0' }
$G = [ordered]@{ I76_COLL_DEDUPE = '1'; I76_COLL_WINDOW = '2'; I76_COLL_WINDOW_WHEN = 'stepframe'; I76_BREAKABLE_BOX = '1' }
$Road = @{ 'best-wide.psd1' = '1800'; 'best-wide-balanced.psd1' = '1200'; 'best-120.psd1' = '1800' }
function Replace-One([string]$t, [string]$pattern, [string]$with, [string]$what) {
    $m = [regex]::Matches($t, $pattern)
    if ($m.Count -ne 1) { throw "REFUSED: $what matched $($m.Count) times (want 1)" }
    return $t.Remove($m[0].Index, $m[0].Length).Insert($m[0].Index, $with)
}
foreach ($p in 'best-wide.psd1', 'best-wide-balanced.psd1', 'best-120.psd1') {
    $src = Assert-DriverEqualsGolden -Rel "Interstate 76\presets\$p"
    [void](Assert-BinaryMd5 -Path $src -Want $driverPresetMd5[$p])
    $t = [IO.File]::ReadAllText($src)
    foreach ($k in 'I76_COLL_WINDOW', 'I76_COLL_WINDOW_WHEN', 'I76_BREAKABLE_BOX', 'I76_ROAD_DIST') { if ($t -match "(?m)^\s*$k\s*=") { throw "REFUSED: $p already sets $k" } }
    $nl = if ($t.Contains("`r`n")) { "`r`n" } else { "`n" }
    # collision G
    $m = [regex]::Match($t, "(?m)^([ \t]*)I76_COLL_DEDUPE[ \t]*=[ \t]*'0'[^\r\n]*")
    $ind = $m.Groups[1].Value
    $new = @(
        "I76_COLL_DEDUPE     = '1'   # one impact = one sound / damage per physics step (collision G, lab COLL-TIMING-2026-10-12.md)",
        "I76_COLL_WINDOW     = '2'   # contacts accepted over the whole physics step: barricades and signs hit at 120 fps (control: about 1 in 3)",
        "I76_COLL_WINDOW_WHEN = 'stepframe'   # ... only on the frame whose step moves the car: no fly-off before the bumper gets there",
        "I76_BREAKABLE_BOX   = '1'   # the 8 m barricade bar collides as the bar, not as a 3 m sphere reaching out in front of it"
    ) | ForEach-Object { $ind + $_ }
    $t = Replace-One $t "(?m)^[ \t]*I76_COLL_DEDUPE[ \t]*=[ \t]*'0'[^\r\n]*" ($new -join $nl) "$p I76_COLL_DEDUPE = '0'"
    # road draw distance, after the far clip line
    $fc = [regex]::Match($t, "(?m)^([ \t]*)I76_FAR_CLIP[ \t]*=[^\r\n]*")
    if (-not $fc.Success) { throw "REFUSED: $p has no I76_FAR_CLIP line" }
    $why = if ($Road[$p] -eq '1200') { "road segments drawn to the far clip (1200 here; stock 450; best-wide 1800)" } else { "road segments drawn to 1800 m like the far clip (stock 450; owner 2026-10-12: 'road at 1800 seems to run fine'; the 2026-10-03 t11 crash was the node pool, fixed by I76_ROAD_POOL since promotion 8)" }
    $t = $t.Insert($fc.Index + $fc.Length, $nl + $fc.Groups[1].Value + ("I76_ROAD_DIST       = '{0}'   # {1}" -f $Road[$p], $why))
    if ($t -match "(?m)^[ \t]*# I76_ROAD_DIST removed 2026-10-03[^\r\n]*\r?\n") { $t = Replace-One $t "(?m)^[ \t]*# I76_ROAD_DIST removed 2026-10-03[^\r\n]*\r?\n" '' "$p road comment" }
    # the wide conf is stretched_ar now
    if ($p -ne 'best-120.psd1') {
        $t = Replace-One $t "u32x maps the shell over the stretched picture \(ScalingMode = stretched\)" "u32x maps the shell where dgVoodoo draws it: 4:3 fit under stretched_ar (dgVoodoo.wide.conf since 2026-10-12), whole client under stretched" "$p SHELL_STRETCH comment"
        $t = Replace-One $t "\(dgVoodoo\.wide\.conf: \[Glide\] Resolution 5160x2160, ScalingMode stretched\);" "(dgVoodoo.wide.conf: [Glide] Resolution 6880x2880 + 4x, ScalingMode stretched_ar = 2x supersampled, 2026-10-12);" "$p conf comment"
        $t = Replace-One $t "Menus, cutscenes and 2D text are(\r?\n)# stretched sideways \(known cost\)\." ("Since 2026-10-12 the 640x480 menus, garage and movies$nl# are shown 4:3 with side bars (stretched_ar), not stretched sideways.") "$p menus comment"
    }
    $out = Join-Path $stageDir $p; [IO.File]::WriteAllText($out, $t, [Text.Encoding]::ASCII)
    $e = (Import-PowerShellDataFile $out).Env
    $want = [ordered]@{}; foreach ($k in $G.Keys) { $want[$k] = $G[$k] }; $want['I76_ROAD_DIST'] = $Road[$p]
    foreach ($k in $want.Keys) { if ("$($e[$k])" -ne $want[$k]) { throw "REFUSED: staged $p reads $k = '$($e[$k])', want '$($want[$k])'" } }
    if ("$($e.I76_FIXED_STEP)" -ne '24') { throw "REFUSED: staged $p has no I76_FIXED_STEP = '24' (the window needs the fixed step)" }
    $base = (Import-PowerShellDataFile $src).Env
    $diff = @(@($e.Keys) + @($base.Keys) | Sort-Object -Unique | Where-Object { "$($e[$_])" -ne "$($base[$_])" })
    if (($diff -join ',') -ne ((@($want.Keys) | Sort-Object) -join ',')) { throw "REFUSED: staged $p changes $($diff -join ', '), want exactly $(@($want.Keys) -join ', ')" }
    $files["Interstate 76\presets\$p"] = $out
}

$staged = [ordered]@{}
foreach ($rel in $files.Keys) { $staged[$rel] = (Get-Md5 $files[$rel]).Substring(0, 8) }
if ($Stage) {
    # the staged set as files under <Stage>\set\<relative path> (what the gate installs into the twin) + its manifest
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
if ($pending.Count -or $GateText -like 'PENDING*') {
    $msg = "the console gate has not passed for this staged set (" + ($pending -join '; ') + ")"
    if (-not $Plan) { Write-Host "REFUSED: $msg" -ForegroundColor Red; exit 2 }
    Write-Host "plan only - $msg" -ForegroundColor Yellow
}
$ht = @{}; foreach ($rel in $files.Keys) { $ht[$rel] = $files[$rel] }
& (Join-Path $PSScriptRoot 'Promote-To-Driver.ps1') -Plan:$Plan `
    -What 'owner-verified set of 2026-10-12: collision G (best-wide, best-wide-balanced, best-120: I76_COLL_DEDUPE=1, I76_COLL_WINDOW=2, _WHEN=stepframe, I76_BREAKABLE_BOX=1); I76_ROAD_DIST 1800 (best-wide, best-120) / 1200 (balanced); 2x supersampled wide conf (stretched_ar, 6880x2880 + 4x: menus and movies 4:3); proxy 509c6df0 (opt-in I76_DRAW_PROBE); launcher 2020e2bf (head tracking + cursor overlay opt-in); I76 Debug in _tools\debug + DEBUG.bat, TRAINER.bat opens its Trainer tab' `
    -Gate $GateText `
    -Files $ht
Write-Host "staged: $stageDir"
