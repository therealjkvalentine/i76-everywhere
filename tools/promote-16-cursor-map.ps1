# Promotion 15 in PROMOTIONS.md (script 16, 2026-10-08): the menu pointer follows the real mouse in widescreen.
#   1. proxy (built from main 614d38f: cursor map + I76_CURSOR_MAP_U32X=exe; also carries everything opt-in since
#      d603cccf: co-op, I76_MUSIC_THREAD, I76_GLIDE_GAMMA, I76_CURSOR_MAP_DGV) and u32x 06467bd2 (602bfbc5 source +
#      I76_U32X_SHELL_STRETCH, off by default; MSVC on this PC, so its code bytes differ from 602bfbc5).
#   2. dgVoodoo.wide.conf: CaptureMouse = false (only PLAY.bat and PLAY-balanced.bat copy it in).
#   3. presets best-wide + best-wide-balanced: + the four cursor lines, staged from the DRIVER's own files.
# Why: dgVoodoo's CaptureMouse held the OS pointer in a 640x480 box at the screen's top left and the game hit-tests raw
# pixels; the proxy now maps the pointer through the client rect (u32x/README.md, 2026-10-07), u32x keeps the shell so
# its modal arrow still works in the garage / reminder OK popups (owner, lab twin, 2026-10-08).
# Run with the game closed. -Plan previews; -Stage <dir> only writes the staged set there (for the lab twin).
param([switch]$Plan, [string]$Stage)
$ErrorActionPreference = 'Stop'
$repo   = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$driver = 'C:\Users\james\Games\Interstate76-2026-10-03'
$golden = 'C:\Users\james\Games\Interstate76-golden-2026-10-03'
$stageDir = if ($Stage) { $Stage } else { Join-Path $env:TEMP "promote-16-$(Get-Date -Format yyyyMMdd-HHmmss)" }
New-Item -ItemType Directory -Force $stageDir | Out-Null
function Md5([string]$p) { (Get-FileHash -LiteralPath $p -Algorithm MD5).Hash.ToLower() }

$bins = @{ 'Interstate 76\STRLKUP.DLL' = @((Join-Path $repo 'music-fix\Strlkup.dll'), 'c11f7f7d');
           'Interstate 76\u32x.dll'    = @((Join-Path $repo 'u32x\u32x_full.dll'),   '06467bd2') }
$files = @{}
foreach ($rel in $bins.Keys) {
    $src = $bins[$rel][0]; $want = $bins[$rel][1]
    if ((Md5 $src).Substring(0, 8) -ne $want) { throw "REFUSED: $src is $((Md5 $src).Substring(0, 8)), not the gated $want" }
    $files[$rel] = $src
}

$lines = @(
    "I76_CURSOR_MAP      = '1'     # the proxy maps the menu pointer through the window (dgVoodoo.wide.conf CaptureMouse = false)",
    "I76_CURSOR_MAP_U32X = 'exe'   # ... taking i76.exe's u32x slots; i76shell keeps u32x (its arrow in the garage / reminder OK popups)",
    "I76_U32X_SHELL_STRETCH = '1'  # u32x maps the shell over the stretched picture (ScalingMode = stretched)",
    "I76_CURSOR_MAP_DGV  = '1'     # dgVoodoo draws its cursor where the pointer really is"
)
foreach ($p in 'best-wide.psd1', 'best-wide-balanced.psd1') {
    $src = Join-Path $driver "Interstate 76\presets\$p"
    if ((Md5 $src) -ne (Md5 (Join-Path $golden "Interstate 76\presets\$p"))) { throw "REFUSED: $p differs between driver and golden" }
    $t = [IO.File]::ReadAllText($src)
    if ($t -match '(?m)^\s*I76_CURSOR_MAP\s*=') { throw "REFUSED: $p already sets I76_CURSOR_MAP" }
    $nl = if ($t.Contains("`r`n")) { "`r`n" } else { "`n" }
    $m = [regex]::Match($t, '(?m)^([ \t]*)I76_ASPECT[ \t]*=[^\r\n]*')
    if (-not $m.Success) { throw "REFUSED: $p has no I76_ASPECT line to anchor on" }
    $t = $t.Insert($m.Index + $m.Length, (($lines | ForEach-Object { $nl + $m.Groups[1].Value + $_ }) -join ''))
    $out = Join-Path $stageDir $p; [IO.File]::WriteAllText($out, $t, [Text.Encoding]::ASCII)
    $e = (Import-PowerShellDataFile $out).Env
    if ($e.I76_CURSOR_MAP -ne '1' -or $e.I76_CURSOR_MAP_U32X -ne 'exe' -or $e.I76_U32X_SHELL_STRETCH -ne '1' -or $e.I76_CURSOR_MAP_DGV -ne '1' -or $e.I76_CAM_GROUND_FIX -ne '1') { throw "REFUSED: staged $p does not read back the switches" }
    $files["Interstate 76\presets\$p"] = $out
}

$conf = Join-Path $driver 'Interstate 76\dgVoodoo.wide.conf'
if ((Md5 $conf) -ne (Md5 (Join-Path $golden 'Interstate 76\dgVoodoo.wide.conf'))) { throw "REFUSED: dgVoodoo.wide.conf differs between driver and golden" }
$t = [IO.File]::ReadAllText($conf)
$n = ([regex]::Matches($t, '(?m)^CaptureMouse(\s*)=\s*true')).Count
if ($n -ne 1) { throw "REFUSED: dgVoodoo.wide.conf has $n 'CaptureMouse = true' lines (want 1)" }
$t = [regex]::Replace($t, '(?m)^CaptureMouse(\s*)=\s*true', 'CaptureMouse$1= false')
$out = Join-Path $stageDir 'dgVoodoo.wide.conf'; [IO.File]::WriteAllText($out, $t, [Text.Encoding]::ASCII)
$files['Interstate 76\dgVoodoo.wide.conf'] = $out

if ($Stage) {
    foreach ($rel in ($files.Keys | Sort-Object)) { "{0}  {1}  <- {2}" -f (Md5 $files[$rel]).Substring(0, 8), $rel, $files[$rel] }
    return
}
& (Join-Path $PSScriptRoot 'Promote-To-Driver.ps1') -Plan:$Plan `
    -What 'menu pointer follows the real mouse in widescreen (PLAY.bat, PLAY-balanced.bat): proxy cursor map I76_CURSOR_MAP (+_U32X=exe, _DGV), u32x 06467bd2 (I76_U32X_SHELL_STRETCH), dgVoodoo.wide.conf CaptureMouse false; best-wide + best-wide-balanced + the four cursor lines' `
    -Gate 'lab twin game-dd-20261003 with the staged set (driver files + this promotion: proxy c11f7f7d, u32x 06467bd2, wide conf CaptureMouse false, best-wide 8de71421 / best-wide-balanced a2191719), 2026-10-08: gate-folder via PLAY.bat with LAB_GAME_ENV = best-wide + LAB_CURSOR_FREE (clicks placed where drawn, every click verified by the shell mouse) 23 PASS 0 FAIL (runs\gate\20261008-204529: conf, bookmark route 3/3, trip 2/2 at 120 fps, save screen NO/YES with the u32x modal arrow up, Esc-menu Exit where drawn, melee, lint, saves identical, no drift; FFB INFO no wheel); same with best-wide-cursor minus CAM_GROUND_FIX 203527 all PASS; row 3 PLAY-16x10.bat (new binaries, conf unchanged) 2/2 120 fps and PLAY-balanced.bat 2/2 120 fps, only D (launcher copies its conf); popup-repro (garage DONE without engine) arrow on the mapped point 5/5 delta 0, closed 4/4 (focused + click/Enter/Space after a focus change); owner n=1 on the lab twin: garage popup arrow follows, menus fine (that is the fix)' `
    -Files $files
Write-Host "staged: $stageDir"
