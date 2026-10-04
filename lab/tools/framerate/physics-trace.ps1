<#
  physics-trace.ps1 — deterministic physics regression trace (memory only, no screenshots).

  Drives a SCRIPTED input sequence and samples the game's own state on a fixed cadence into a
  CSV. Run it at 20 Hz to make a reference, then at 60 Hz (with scaled constants) and diff:
  if the physics are equivalent, the traces match at the same elapsed time.

  FALL SPEED is the canonical check - the famous I'76 breakage is that jump/fall behaviour
  changes with frame rate. -Profile jump drives off at speed so there is airtime to measure.

  Usage:
    tools\physics-trace.ps1 -Label ref20 -Seconds 12 -Profile straight
    tools\physics-trace.ps1 -Label test60 -Seconds 12 -Profile straight
    python tools\trace-diff.py captures\traces\ref20.csv captures\traces\test60.csv
#>
param(
    [string]$Label = 'trace',
    [int]$Seconds = 12,
    [ValidateSet('straight','jump','turn','coast')][string]$Profile = 'straight',
    [int]$SampleMs = 50,
    [string]$OutDir = "$PSScriptRoot\..\..\captures\traces"
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\..\autotest\lib\memlib.ps1"
. "$PSScriptRoot\..\..\autotest\lib\focuslib.ps1"
. "$PSScriptRoot\..\..\autotest\lib\inputlib.ps1"
. "$PSScriptRoot\..\..\autotest\lib\simlib.ps1"

New-Item -ItemType Directory -Force $OutDir | Out-Null
$ctx = Mem-Open -Write
if (-not (Mem-InMission $ctx)) { throw "Not in a mission - run autotest\enter-melee.ps1 first." }

# A trace of a frozen sim is a page of identical rows that looks like real data.
# Verify the frame counter is actually advancing (focus + pause menu) before recording.
if (-not (Ensure-SimRunning $ctx)) { throw "Sim is not advancing (unfocused, or pause menu is up)." }

# Deterministic input via REAL KEY STATE, not memory writes: the engine rebuilds the input
# block from the device every frame, so a written value is overwritten before physics sees it
# (verified - throttle read back 0 the whole run). Holding the scancode down works.
$KD = 0x8; $KU = 0xA          # SCANCODE ; SCANCODE|KEYUP
function KeyDown([byte]$vk){ [Inp]::keybd_event($vk, [byte][Inp]::MapVirtualKey($vk,0), $KD, [IntPtr]::Zero) }
function KeyUp  ([byte]$vk){ [Inp]::keybd_event($vk, [byte][Inp]::MapVirtualKey($vk,0), $KU, [IntPtr]::Zero) }

# I'76 throttle is NOTCHED: tap W to wind it up. Taps alone proved unreliable (a run came
# back with speed 0.08), so we also re-assert W every sample below - the key must be HELD
# for the whole trace or the two runs aren't comparable.
for ($i=0; $i -lt 8; $i++) { KeyDown $VK.W; Start-Sleep -Milliseconds 40; KeyUp $VK.W; Start-Sleep -Milliseconds 60 }

$rows = @('t_ms,frame,x,y,z,speed,vx,vy,vz,yawrate,steer,throttle')
$sw = [Diagnostics.Stopwatch]::StartNew()
$startFrame = (Mem-Player $ctx).Frame
$next = 0
$steerHeld = $false
$inv = [Globalization.CultureInfo]::InvariantCulture
while ($sw.Elapsed.TotalSeconds -lt $Seconds) {
    $t = $sw.Elapsed.TotalMilliseconds
    if ($Profile -ne 'coast') { KeyDown $VK.W }   # keep the throttle asserted for the whole run
    if ($Profile -eq 'turn') {
        # hold A for the first half of the run, release for the second
        if ($t -lt ($Seconds * 500)) { if (-not $steerHeld) { KeyDown $VK.A; $steerHeld = $true } }
        elseif ($steerHeld) { KeyUp $VK.A; $steerHeld = $false }
    }
    if ($t -ge $next) {
        $p = Mem-Player $ctx
        if ($p) {
            # InvariantCulture + no group separators, or the CSV gets "9,855" and breaks
            $rows += (([int]$t).ToString($inv) + ',' + ($p.Frame - $startFrame).ToString($inv) + ',' +
                $p.X.ToString('R',$inv) + ',' + $p.Y.ToString('R',$inv) + ',' + $p.Z.ToString('R',$inv) + ',' +
                $p.Speed.ToString('R',$inv) + ',' + $p.VX.ToString('R',$inv) + ',' + $p.VY.ToString('R',$inv) + ',' +
                $p.VZ.ToString('R',$inv) + ',' + $p.YawRate.ToString('R',$inv) + ',' +
                $p.Steer.ToString('R',$inv) + ',' + $p.Throttle.ToString('R',$inv))
        }
        $next += $SampleMs
    }
    Start-Sleep -Milliseconds 5
}
if ($steerHeld) { KeyUp $VK.A }
for ($i=0; $i -lt 8; $i++) { KeyDown $VK.S; Start-Sleep -Milliseconds 30; KeyUp $VK.S; Start-Sleep -Milliseconds 40 }   # wind throttle back down
Mem-Close $ctx

$path = Join-Path $OutDir "$Label.csv"
$rows | Set-Content $path
Write-Host ("wrote {0} samples -> {1}" -f ($rows.Count - 1), $path) -ForegroundColor Green
