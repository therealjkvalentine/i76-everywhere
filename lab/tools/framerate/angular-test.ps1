<#
  angular-test.ps1 — is ANGULAR integration frame-coupled while linear is not?

  Field reports at 60 fps: the post-death camera spins too fast, chassis roll is too fast, and
  the car over-rotates in mid-air (died on the bridge). All three are ROTATIONAL, while every
  linear quantity measured (gravity, acceleration, velocity) is dt-correct. If orientation is
  advanced once per FRAME using the angular velocity, then at 3x the frame rate the car turns
  3x as far per second while the engine's own yaw-rate value stays the same.

  This measures both sides of that:
     yaw_rate      the engine's angular velocity  (entity +0xCC)   - rad/s, should be equal
     d(heading)/dt the ACTUAL rotation achieved   (eye matrix)     - should equal yaw_rate

  If d(heading)/dt / yaw_rate is ~1 at 20 Hz but ~3 at 60 Hz, orientation is integrated per
  frame and that is the bug behind all three reports.

  Heading comes from the eye transform's 3x3 rotation matrix at 0x5FCDC4+0x0C (verified
  render-consumed). Any consistent pair of matrix elements works - only the RATIO across frame
  rates matters.
#>
param([int]$Seconds = 8, [string]$Label = 'ang', [int]$SampleMs = 50,
      [string]$OutDir = "$PSScriptRoot\..\..\captures\traces")
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\..\autotest\lib\memlib.ps1"
. "$PSScriptRoot\..\..\autotest\lib\focuslib.ps1"
. "$PSScriptRoot\..\..\autotest\lib\inputlib.ps1"
. "$PSScriptRoot\..\..\autotest\lib\simlib.ps1"
New-Item -ItemType Directory -Force $OutDir | Out-Null

$EYE = 0x5FCDC4
$ctx = Mem-Open
if (-not (Mem-InMission $ctx)) { throw "not in a mission" }
if (-not (Ensure-SimRunning $ctx)) { throw "sim not advancing" }

# Input MUST be held, not tapped: a 25 ms tap spans ~0.5 frames at 20 Hz and ~1.5 at 60 Hz, so
# tapping delivers different steering at each rate (a first attempt produced yaw rates 15x
# apart and was meaningless). Hold the scancode down for the whole run and verify comparability
# afterwards from the APPLIED steer value the engine itself computed (+0xE0).
$KD = 0x8; $KU = 0xA
function KeyDown([byte]$vk){ [Inp]::keybd_event($vk, [byte][Inp]::MapVirtualKey($vk,0), $KD, [IntPtr]::Zero) }
function KeyUp  ([byte]$vk){ [Inp]::keybd_event($vk, [byte][Inp]::MapVirtualKey($vk,0), $KU, [IntPtr]::Zero) }

for ($i=0; $i -lt 10; $i++) { KeyDown $VK.W; Start-Sleep -Milliseconds 40; KeyUp $VK.W; Start-Sleep -Milliseconds 60 }
Start-Sleep -Milliseconds 500

$inv = [Globalization.CultureInfo]::InvariantCulture
$rows = @('t_ms,frame,heading,yawrate,speed,steer')
$sw = [Diagnostics.Stopwatch]::StartNew()
$next = 0
$f0 = (Mem-Player $ctx).Frame
while ($sw.Elapsed.TotalSeconds -lt $Seconds) {
    KeyDown $VK.W              # keep both held continuously
    KeyDown $VK.A
    $t = $sw.Elapsed.TotalMilliseconds
    if ($t -ge $next) {
        $p = Mem-Player $ctx
        $m0 = Mem-F32 $ctx ($EYE + 0x0C)
        $m2 = Mem-F32 $ctx ($EYE + 0x14)
        $heading = [math]::Atan2($m2, $m0)          # radians, wraps at +-pi
        $rows += (([int]$t).ToString($inv) + ',' + ($p.Frame - $f0).ToString($inv) + ',' +
                  $heading.ToString('R',$inv) + ',' + $p.YawRate.ToString('R',$inv) + ',' +
                  $p.Speed.ToString('R',$inv) + ',' + $p.Steer.ToString('R',$inv))
        $next += $SampleMs
    }
    Start-Sleep -Milliseconds 8
}
KeyUp $VK.A; KeyUp $VK.W
$rows | Set-Content (Join-Path $OutDir "$Label.csv")
$p = Mem-Player $ctx
$fps = ($p.Frame - $f0) / $sw.Elapsed.TotalSeconds
Mem-Close $ctx
Write-Host ("{0}: {1:N1} fps, {2} samples -> {3}.csv" -f $Label, $fps, ($rows.Count-1), $Label) -ForegroundColor Green
