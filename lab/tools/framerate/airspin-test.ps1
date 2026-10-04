<#
  airspin-test.ps1 — does the car ROTATE too far while airborne at high frame rates?

  This is the field bug: "over-rotated on the bridge and died", plus chassis roll being too
  fast. It is also the cleanest possible angular test, because while airborne:
    * no steering input is needed (so no key-timing confound - the trap that ruined the first
      yaw test), and
    * no ground contact, so terrain cannot bias it.

  Records, every frame from inside the engine, the full orientation of the render transform
  plus the angular-velocity triple, then analyse-airspin.py compares rotation ACHIEVED per
  second against the angular velocity the engine reports.

    achieved/reported ~1 at both rates      -> orientation is dt-correct
    ~1 at 20 Hz and ~3 at 60 Hz             -> orientation advanced per FRAME  <-- the bug

  Drives hard off the arena's hills to get airtime; run with an EMPTY arena (AI DRIVERS = 0)
  or collisions will corrupt the rotation.
#>
param([int]$Seconds = 30, [string]$Label = 'airspin',
      [string]$OutDir = "$PSScriptRoot\..\..\captures\traces")
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\..\autotest\lib\memlib.ps1"
. "$PSScriptRoot\..\..\autotest\lib\focuslib.ps1"
. "$PSScriptRoot\..\..\autotest\lib\inputlib.ps1"
. "$PSScriptRoot\..\..\autotest\lib\simlib.ps1"
New-Item -ItemType Directory -Force $OutDir | Out-Null

$EYE = 0x5FCDC4          # render transform: position float3 then 3x3 rotation matrix at +0x0C
$ctx = Mem-Open
if (-not (Mem-InMission $ctx)) { throw "not in a mission" }
if (-not (Ensure-SimRunning $ctx)) { throw "sim not advancing" }
$ents = @(Mem-Entities $ctx)
if ($ents.Count -gt 1) { Write-Host ("WARNING: {0} entities present - AI cars will corrupt this test" -f $ents.Count) -ForegroundColor Yellow }

$ent = Mem-PlayerEntity $ctx
$inv = [Globalization.CultureInfo]::InvariantCulture
$KD = 0x8; $KU = 0xA
function KeyDown([byte]$vk){ [Inp]::keybd_event($vk, [byte][Inp]::MapVirtualKey($vk,0), $KD, [IntPtr]::Zero) }
function KeyUp  ([byte]$vk){ [Inp]::keybd_event($vk, [byte][Inp]::MapVirtualKey($vk,0), $KU, [IntPtr]::Zero) }

for ($i=0; $i -lt 10; $i++) { KeyDown $VK.W; Start-Sleep -Milliseconds 40; KeyUp $VK.W; Start-Sleep -Milliseconds 60 }

$rows = @('t_ms,frame,vy,speed,wx,wy,wz,m0,m1,m2,m3,m4,m5,m6,m7,m8')
$sw = [Diagnostics.Stopwatch]::StartNew()
$f0 = (Mem-Player $ctx).Frame
$air = 0
while ($sw.Elapsed.TotalSeconds -lt $Seconds) {
    KeyDown $VK.W                                  # held, never tapped
    $t = $sw.Elapsed.TotalMilliseconds
    $p = Mem-Player $ctx
    if ([math]::Abs($p.VY) -gt 2) { $air++ }
    $m = @(); for ($k=0; $k -lt 9; $k++) { $m += (Mem-F32 $ctx ($EYE + 0x0C + $k*4)) }
    $wx = Mem-F32 $ctx ($ent + 0xC8); $wy = Mem-F32 $ctx ($ent + 0xCC); $wz = Mem-F32 $ctx ($ent + 0xD0)
    $rows += (([int]$t).ToString($inv) + ',' + ($p.Frame - $f0).ToString($inv) + ',' +
              $p.VY.ToString('R',$inv) + ',' + $p.Speed.ToString('R',$inv) + ',' +
              $wx.ToString('R',$inv) + ',' + $wy.ToString('R',$inv) + ',' + $wz.ToString('R',$inv) + ',' +
              (($m | ForEach-Object { $_.ToString('R',$inv) }) -join ','))
    Start-Sleep -Milliseconds 25
}
KeyUp $VK.W
$rows | Set-Content (Join-Path $OutDir "$Label.csv")
$p = Mem-Player $ctx
$fps = ($p.Frame - $f0) / $sw.Elapsed.TotalSeconds
Mem-Close $ctx
Write-Host ("{0}: {1:N1} fps, {2} samples, {3} airborne polls -> {4}.csv" -f $Label, $fps, ($rows.Count-1), $air, $Label) -ForegroundColor Green
