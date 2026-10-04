<#
  airborne-test.ps1 — log attitude and angular velocity while the car jumps, for a
  terrain-independent test of the mid-air over-rotation bug.

  "I rotated too far on the bridge and died" is the most consequential of the frame-coupled
  bugs, and the hardest to measure, because no two jumps are alike: takeoff speed, ramp angle
  and landing all differ between runs, so raw degrees-of-rotation cannot be compared.

  The trick is to compare a DIMENSIONLESS quantity. The entity stores angular velocity (+0xC8,
  rad/s) and the eye transform gives the attitude that angular velocity integrates into. Their
  ratio - degrees actually turned per degree-per-second commanded - is 1.0 for any jump, on any
  terrain, if the integration uses the frame delta-time. If the integrator instead advances by
  a fixed amount per frame, that ratio is 3x larger at 60 Hz. Terrain cancels out.

  Drive somewhere with jumps (Dunes or Crater; AirBase and SlickTrack are flat and yield zero
  airborne samples). Zero AI cars, or collisions add torques that are not free flight.

    tools\airborne-test.ps1 -Label air20 -Seconds 30
#>
param(
    [Parameter(Mandatory = $true)][string]$Label,
    [double]$Seconds = 30,
    [string]$OutDir
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\..\autotest\lib\memlib.ps1"
. "$PSScriptRoot\..\..\autotest\lib\inputlib.ps1"
. "$PSScriptRoot\..\..\autotest\lib\focuslib.ps1"
if (-not $OutDir) { $OutDir = Join-Path $PSScriptRoot '..\captures\air' }

$ctx = Mem-Open
if (-not (Mem-InMission $ctx)) { throw "not in a mission" }
New-Item -ItemType Directory -Force $OutDir | Out-Null
$out = Join-Path $OutDir "$Label.csv"
if (Test-Path $out) { Remove-Item $out -Force }

$VK_W = [byte]0x57
Force-Foreground $ctx.Proc.MainWindowHandle | Out-Null
$ent = Mem-PlayerEntity $ctx
$rows = New-Object System.Collections.Generic.List[object]

Key-Down $VK_W
$sw = [Diagnostics.Stopwatch]::StartNew()
while ($sw.Elapsed.TotalSeconds -lt $Seconds) {
    Key-Down $VK_W
    $a = Mem-EyeAngles $ctx
    $s = Mem-Floats $ctx ($ent + 0xAC) 12      # +0xAC speed .. +0xD0 angular velocity, one read
    if ($a -and $s) {
        $rows.Add([pscustomobject]@{
            t     = [math]::Round($sw.Elapsed.TotalSeconds, 4)
            frame = Mem-I32 $ctx 0x5A7E1C
            px    = [math]::Round($a.PX, 3)
            py    = [math]::Round($a.PY, 3)
            pz    = [math]::Round($a.PZ, 3)
            pitch = [math]::Round($a.Pitch, 4)
            roll  = [math]::Round($a.Roll, 4)
            yaw   = [math]::Round($a.Yaw, 4)
            speed = [math]::Round($s[0], 3)          # +0xAC
            vy    = [math]::Round($s[5], 4)          # +0xC0 fall speed
            avx   = [math]::Round($s[7], 5)          # +0xC8
            avy   = [math]::Round($s[8], 5)          # +0xCC yaw rate
            avz   = [math]::Round($s[9], 5)          # +0xD0
        })
    }
    Start-Sleep -Milliseconds 8
}
Key-Up $VK_W

$fps = ($rows[$rows.Count-1].frame - $rows[0].frame) / $rows[$rows.Count-1].t
$rows | Export-Csv -NoTypeInformation $out
Mem-Close $ctx
Write-Host ("{0}: {1:N1} fps, {2} samples, {3} -> {4}" -f $Label, $fps, $rows.Count, `
    ("vy range {0:N1}..{1:N1}" -f ($rows.vy | Measure-Object -Minimum).Minimum, ($rows.vy | Measure-Object -Maximum).Maximum), $out) -ForegroundColor Green
