<#
  find-camera-angle.ps1 — find the death-camera's orbit angle variable while it is spinning.

  Run this WHILE DEAD and the camera is orbiting (the orbit continues indefinitely, so there is
  no rush). It samples the camera state region and reports every value that advances steadily —
  which is the orbit angle itself, plus whatever derives from it.

  Why this rather than scanning the exe for the constant: the measured step (8.0 deg/frame at
  60 fps) matches 45 different float32 `8.0` literals in the binary, so the constant cannot be
  identified statically. Finding the live VARIABLE first, then putting a hardware write
  breakpoint on it (src/find-reads.exe), leads straight to the one instruction that advances it.

  Known camera landmarks: state block `0x4C2730` (616 bytes), FSM `0x4C2728`, Euler/limit fields
  `0x4C2964`/`68`/`6C`/`70`/`80`, constants at `0x4C2918`/`24`/`28`.

    tools\framerate\find-camera-angle.ps1                  # default sweep of the camera region
    tools\framerate\find-camera-angle.ps1 -Lo 0x4C2700 -Hi 0x4C2A00 -Seconds 6

  READ-ONLY.
#>
param(
    [int64]$Lo = 0x4C2700,
    [int64]$Hi = 0x4C2A00,
    [double]$Seconds = 6,
    [switch]$AlsoEye        # include the eye transform, as a positive control
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\..\autotest\lib\memlib.ps1"

$ctx = Mem-Open
$n = [int](($Hi - $Lo) / 4)
Write-Host ("sampling 0x{0:X}..0x{1:X} ({2} dwords) for {3}s - be DEAD and orbiting" -f $Lo, $Hi, $n, $Seconds) -ForegroundColor Cyan

$series = @{}
$frames = @()
$sw = [Diagnostics.Stopwatch]::StartNew()
while ($sw.Elapsed.TotalSeconds -lt $Seconds) {
    $blk = Mem-Floats $ctx $Lo $n
    if ($blk) {
        $frames += ,@{ t = $sw.Elapsed.TotalSeconds; f = (Mem-I32 $ctx 0x5A7E1C); v = $blk }
    }
    Start-Sleep -Milliseconds 40
}
Mem-Close $ctx
if ($frames.Count -lt 5) { throw "too few samples" }

$dur = $frames[-1].t - $frames[0].t
$dfr = $frames[-1].f - $frames[0].f
$fps = if ($dur -gt 0) { $dfr / $dur } else { 0 }
Write-Host ("{0} samples, {1:N1}s, {2:N1} fps" -f $frames.Count, $dur, $fps)

$hits = @()
for ($i = 0; $i -lt $n; $i++) {
    $vals = $frames | ForEach-Object { $_.v[$i] }
    $bad = $vals | Where-Object { [double]::IsNaN($_) -or [double]::IsInfinity($_) }
    if ($bad) { continue }
    $first = $vals[0]; $last = $vals[-1]
    $delta = $last - $first
    if ([math]::Abs($delta) -lt 1e-4) { continue }
    # steady advance: every consecutive step the same sign, and roughly equal size
    $steps = @()
    for ($k = 1; $k -lt $vals.Count; $k++) { $steps += ($vals[$k] - $vals[$k-1]) }
    $moving = $steps | Where-Object { [math]::Abs($_) -gt 1e-6 }
    if ($moving.Count -lt ($steps.Count * 0.5)) { continue }
    $pos = ($moving | Where-Object { $_ -gt 0 }).Count
    $neg = ($moving | Where-Object { $_ -lt 0 }).Count
    $monotonic = ($pos -eq 0 -or $neg -eq 0)
    $addr = $Lo + $i * 4
    $perSec = $delta / $dur
    $perFrame = if ($dfr) { $delta / $dfr } else { 0 }
    $hits += [pscustomobject]@{
        addr     = ('0x{0:X}' -f $addr)
        first    = [math]::Round($first, 5)
        last     = [math]::Round($last, 5)
        per_s    = [math]::Round($perSec, 4)
        per_fr   = [math]::Round($perFrame, 5)
        deg_s    = [math]::Round($perSec * 180 / [math]::PI, 2)   # if it is radians
        steady   = $monotonic
    }
}
if (-not $hits) { Write-Host "nothing advancing in that range - is the camera actually orbiting?" -ForegroundColor Yellow; exit 1 }
Write-Host "`nadvancing values (per_s in native units; deg_s = same value read as radians):" -ForegroundColor Green
$hits | Sort-Object -Property @{e={[math]::Abs($_.per_s)}} -Descending | Format-Table -AutoSize

Write-Host "Look for one whose rate matches the measured orbit (480 deg/s at 60fps, ~160 at 20fps)," -ForegroundColor Cyan
Write-Host "either directly (degrees) or in the deg_s column (radians). Then:" -ForegroundColor Cyan
Write-Host "  src\find-reads.exe <pid> 5 <that address>    # the writer is the per-frame step" -ForegroundColor Cyan
