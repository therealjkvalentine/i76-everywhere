<#
  clock-rate-test.ps1 — does the engine's own clock keep up with real time?

  The engine builds its time base from GetTickCount (0x49C920: call [0x4BC100], * 0.001) and
  stores seconds at 0x5A7E74. GetTickCount only advances in ~15.6 ms steps by default, which
  is a third of a 50 ms frame but almost a whole 16.7 ms frame - so at 60 Hz the per-frame
  delta is badly quantized.

  If the engine's clock advances SLOWER than wall time, every dt-scaled force (thrust, drag,
  gravity) is under-applied by the same ratio - which is exactly the uniform ~10-20% shortfall
  measured at 60 Hz.

  Prints engine-seconds per real-second. 1.000 = the clock is honest.
#>
param([int]$Seconds = 6)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\..\autotest\lib\memlib.ps1"
. "$PSScriptRoot\..\..\autotest\lib\focuslib.ps1"
. "$PSScriptRoot\..\..\autotest\lib\inputlib.ps1"
. "$PSScriptRoot\..\..\autotest\lib\simlib.ps1"

$ctx = Mem-Open
if (-not (Ensure-SimRunning $ctx)) { throw "sim not advancing" }
$CLOCK = 0x5A7E74
$f0 = (Mem-Player $ctx).Frame
$c0 = Mem-F32 $ctx $CLOCK
$sw = [Diagnostics.Stopwatch]::StartNew()
while ($sw.Elapsed.TotalSeconds -lt $Seconds) { Send-Key $VK.W 20; Start-Sleep -Milliseconds 60 }
$real = $sw.Elapsed.TotalSeconds
$c1 = Mem-F32 $ctx $CLOCK
$f1 = (Mem-Player $ctx).Frame
Mem-Close $ctx

$engine = $c1 - $c0
$fps = ($f1 - $f0) / $real
Write-Host ("frame rate      : {0:N1} fps" -f $fps)
Write-Host ("real elapsed    : {0:N3} s" -f $real)
Write-Host ("engine clock    : {0:N3} s" -f $engine)
Write-Host ("engine/real     : {0:N4}   <-- 1.000 means the clock is honest" -f ($(if ($real -gt 0) { $engine / $real } else { 0 }))) -ForegroundColor Yellow
Write-Host ("engine s/frame  : {0:N5}" -f $(if (($f1-$f0) -gt 0) { $engine / ($f1 - $f0) } else { 0 }))
