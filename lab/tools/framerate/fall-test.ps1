<#
  fall-test.ps1 — terrain-independent gravity measurement using the in-process recorder.

  Every earlier comparison was confounded: the car drives onto different terrain at different
  frame rates, so later samples compare different SITUATIONS, not different rates. Free fall
  is the one measurement terrain cannot bias - once the car is airborne, only gravity acts.

  Drives hard to get airborne, records EVERY FRAME from inside the engine (record=1 in the
  ctl file -> captures/traces/inproc.csv), then analyse-fall.py fits dvy/dt over the airborne
  samples only.

    tools\fall-test.ps1 -Label fall60 -Seconds 25
#>
param([string]$Label = 'fall', [int]$Seconds = 25,
      [string]$Ctl = "$PSScriptRoot\..\..\captures\i76uncap.ctl",
      [string]$Rec = "$PSScriptRoot\..\..\captures\traces\inproc.csv",
      [string]$OutDir = "$PSScriptRoot\..\..\captures\traces")
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\..\autotest\lib\memlib.ps1"
. "$PSScriptRoot\..\..\autotest\lib\focuslib.ps1"
. "$PSScriptRoot\..\..\autotest\lib\inputlib.ps1"
. "$PSScriptRoot\..\..\autotest\lib\simlib.ps1"

$ctx = Mem-Open
if (-not (Mem-InMission $ctx)) { throw "not in a mission" }
if (-not (Ensure-SimRunning $ctx)) { throw "sim not advancing" }

# Delete the old recording FIRST. Without this a run that records nothing (game unfocused ->
# no frames -> no flush) silently leaves the previous file in place and gets copied as if it
# were fresh - which produced two byte-identical "20 Hz" and "60 Hz" traces.
Remove-Item $Rec -Force -ErrorAction SilentlyContinue
Set-Content $Ctl "extras=0`ninterp=0`npace=0`nenabled=1`nrecord=1"
Start-Sleep -Milliseconds 800

# Drive hard, with occasional turns, to launch off the arena's hills.
$sw = [Diagnostics.Stopwatch]::StartNew()
$airborne = 0; $frozen = 0
$lastFrame = (Mem-Player $ctx).Frame
while ($sw.Elapsed.TotalSeconds -lt $Seconds) {
    Send-Key $VK.W 25
    $p = Mem-Player $ctx
    if ([math]::Abs($p.VY) -gt 3) { $airborne++ }
    # The sim freezes if focus is lost mid-run; re-assert it whenever frames stop advancing.
    if ($p.Frame -eq $lastFrame) {
        $frozen++
        if ($frozen % 10 -eq 0) { Force-Foreground $ctx.Proc.MainWindowHandle | Out-Null }
    } else { $frozen = 0 }
    $lastFrame = $p.Frame
    # weave so we cross ridges rather than settling on flat ground
    if ((($sw.Elapsed.TotalSeconds) % 8) -lt 2) { Send-Key $VK.A 25 }
    elseif ((($sw.Elapsed.TotalSeconds) % 8) -lt 4) { Send-Key $VK.D 25 }
    Start-Sleep -Milliseconds 25
}
Set-Content $Ctl "extras=0`ninterp=0`npace=0`nenabled=1`nrecord=0"
Start-Sleep -Milliseconds 2000      # let the DLL flush
Mem-Close $ctx

if (-not (Test-Path $Rec)) {
    Write-Host "NO RECORDING PRODUCED - the game was probably never presenting frames (unfocused)." -ForegroundColor Red
    exit 1
}
Copy-Item $Rec (Join-Path $OutDir "$Label.csv") -Force
$n = (Get-Content (Join-Path $OutDir "$Label.csv")).Count - 1
Write-Host ("recorded {0} per-frame samples ({1} airborne polls) -> {2}.csv" -f $n, $airborne, $Label) -ForegroundColor Green
