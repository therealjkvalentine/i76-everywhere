<#
  sky-bisect.ps1 — YOU run this; it finds the sky's animation value, crash-safe.

  Freezing hundreds of values at once kept killing the game (some frozen counter is load-bearing).
  So this NEVER freezes more than -GroupSize (default 120) at a time, and checks the game is
  still alive after every hold. It sweeps groups until you see the clouds stop, then binary-
  searches inside that one group down to the address. Small groups = the game survives.

  RUN:
      powershell -ExecutionPolicy Bypass -File C:\Users\james\i76-uncap-lab\tools\framerate\sky-bisect.ps1

  EACH HOLD (default 3 s): watch ONLY the clouds, then press ONE key (no Enter):
      y = clouds stopped / slowed      n = clouds kept drifting      r = repeat this hold
  Ignore HUD/radar stutter.

  If it ever prints GAME DIED, tell me the address range and I will exclude it and hand you a
  fresh set. Otherwise it ends with WINNER: 0x.... - paste me that line.
#>
param(
    [double]$HoldSeconds = 3,
    [int]$GroupSize = 120,
    [string]$CandFile = "$PSScriptRoot\..\..\captures\sky\sky-candidates.json"
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\..\autotest\lib\memlib.ps1"

if (-not (Test-Path $CandFile)) { throw "no candidate file - run sky-hunt.py scan first" }
$ctx = Mem-Open -Write
function Alive { $a = Mem-I32 $ctx 0x5A7E1C; Start-Sleep -Milliseconds 200; $b = Mem-I32 $ctx 0x5A7E1C; return ($b -gt $a) }
if (-not (Alive)) { throw "game not running/advancing - relaunch, rescan, rerun" }

$cands = (Get-Content $CandFile -Raw | ConvertFrom-Json).cands | ForEach-Object { [int64]$_[0] } | Sort-Object -Unique
$N = $cands.Count
Write-Host ""
Write-Host "SKY BISECT (crash-safe) - $N candidates, groups of $GroupSize." -ForegroundColor Cyan
Write-Host "Watch the CLOUDS. Tap y (stopped) / n (moving) / r (repeat) after each hold." -ForegroundColor Cyan
Write-Host ""

function Ask([string]$prompt) {
    Write-Host -NoNewline ("  " + $prompt + " ")
    while ($true) { $k = [System.Console]::ReadKey($true).KeyChar.ToString().ToLower(); if ($k -in @('y','n','r')) { Write-Host $k; return $k } }
}
function Freeze([int]$lo, [int]$hi, [double]$secs) {
    $addrs = @(); $vals = @()
    for ($i = $lo; $i -lt $hi; $i++) { $addrs += $cands[$i]; $vals += (Mem-I32 $ctx $cands[$i]) }
    $sw = [Diagnostics.Stopwatch]::StartNew()
    while ($sw.Elapsed.TotalSeconds -lt $secs) { for ($i = 0; $i -lt $addrs.Count; $i++) { Mem-WriteI32 $ctx $addrs[$i] $vals[$i] } }
}
function HoldAsk([int]$lo, [int]$hi, [string]$tag) {
    while ($true) {
        Freeze $lo $hi $HoldSeconds
        if (-not (Alive)) {
            Write-Host ""
            Write-Host ("*** GAME DIED freezing [{0}:{1}) 0x{2:X}..0x{3:X} - tell me this range." -f $lo, $hi, $cands[$lo], $cands[$hi-1]) -ForegroundColor Red
            Mem-Close $ctx; exit 1
        }
        $a = Ask ("$tag [$lo`:$hi) 0x{0:X}..0x{1:X}  stop? (y/n/r)" -f $cands[$lo], $cands[$hi-1])
        if ($a -ne 'r') { return $a }
    }
}

# --- SWEEP small groups until one stops the sky ---
$winLo = -1; $winHi = -1
for ($gLo = 0; $gLo -lt $N; $gLo += $GroupSize) {
    $gHi = [math]::Min($gLo + $GroupSize, $N)
    $g = [int]($gLo / $GroupSize) + 1
    $ng = [math]::Ceiling($N / $GroupSize)
    if ((HoldAsk $gLo $gHi "group $g/$ng") -eq 'y') { $winLo = $gLo; $winHi = $gHi; break }
}
if ($winLo -lt 0) {
    Write-Host ""
    Write-Host "No group stopped the sky. The scroll is computed each frame in CODE (not a stored" -ForegroundColor Yellow
    Write-Host "value we can freeze). Tell me - I pivot to disassembling the sky update." -ForegroundColor Yellow
    Mem-Close $ctx; exit 0
}
Write-Host ("  found it in group [$winLo`:$winHi). Bisecting {0} values." -f ($winHi - $winLo)) -ForegroundColor Green

# --- BINARY SEARCH within the winning group ---
$lo = $winLo; $hi = $winHi
while ($hi - $lo -gt 1) {
    $mid = [int](($lo + $hi) / 2)
    if ((HoldAsk $lo $mid "  ") -eq 'y') { $hi = $mid }
    else {
        if ((HoldAsk $mid $hi "  ") -eq 'y') { $lo = $mid }
        else {
            Write-Host "  neither half alone stopped it - a SPLIT PAIR around index $mid. Neighbours:" -ForegroundColor Yellow
            for ($i = [math]::Max($winLo,$mid-4); $i -lt [math]::Min($winHi,$mid+4); $i++) { "    0x{0:X}" -f $cands[$i] }
            Set-Content "$PSScriptRoot\..\..\captures\sky\sky-winner.txt" (($cands[([math]::Max($winLo,$mid-4))..([math]::Min($winHi,$mid+4)-1)] | ForEach-Object { '0x{0:X}' -f $_ }) -join "`n")
            Mem-Close $ctx; exit 0
        }
    }
}
$w = $cands[$lo]
Write-Host ""
Write-Host ("WINNER: 0x{0:X}  (int {1}, float {2})" -f $w, (Mem-I32 $ctx $w), (Mem-F32 $ctx $w)) -ForegroundColor Yellow
Freeze $lo ($lo + 1) 6
if ((Ask "confirm - just that one address stopped the sky? (y/n/r)") -eq 'y') {
    Set-Content "$PSScriptRoot\..\..\captures\sky\sky-winner.txt" ("0x{0:X}" -f $w)
    Write-Host ("CONFIRMED sky driver: 0x{0:X} (saved to captures\sky\sky-winner.txt)" -f $w) -ForegroundColor Green
} else {
    Write-Host "not a single address - neighbours for me to inspect:" -ForegroundColor Yellow
    for ($i = [math]::Max($winLo,$lo-3); $i -lt [math]::Min($winHi,$lo+4); $i++) { "  0x{0:X}" -f $cands[$i] }
}
Mem-Close $ctx
