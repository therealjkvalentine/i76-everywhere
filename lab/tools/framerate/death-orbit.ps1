<#
  death-orbit.ps1 — self-destruct and measure the post-death camera orbit rate.

  Replaces the old drive-around-and-hope approach: melee AI cannot kill the player (400 s of
  ramming proved it), but `CTRL+ALT+X` detonates the car on demand, so a death is now scriptable.

  Timing matters. The orbit window is SHORT — a few seconds — because the mission then ends and
  drops to the STANDINGS screen, at which point the frame counter `0x5A7E1C` stops advancing
  entirely. So this samples flat out from the instant of detonation and stops the moment the
  frame counter stalls, rather than logging for a fixed duration (a fixed 8 s window measured
  0.0 fps and an orbit of 0 degrees, because it was all standings screen).

    tools\framerate\death-orbit.ps1 -Label orbit20

  Reports deg/s and deg/frame. Compare across frame rates: deg/s scaling ~3x while deg/frame
  stays put means the orbit advances a fixed step per FRAME — i.e. frame-coupled, and the fix is
  to scale that step by the frame delta-time.
#>
param(
    [Parameter(Mandatory = $true)][string]$Label,
    [double]$MaxSeconds = 12,
    [string]$OutDir
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\..\autotest\lib\memlib.ps1"
. "$PSScriptRoot\..\..\autotest\lib\focuslib.ps1"
. "$PSScriptRoot\..\..\autotest\lib\cheatlib.ps1"
if (-not $OutDir) { $OutDir = Join-Path $PSScriptRoot '..\..\captures\death' }

$ctx = Mem-Open
if (-not (Mem-InMission $ctx)) { throw "not in a mission" }
New-Item -ItemType Directory -Force $OutDir | Out-Null
$out = Join-Path $OutDir "$Label.csv"
if (Test-Path $out) { Remove-Item $out -Force }

Force-Foreground $ctx.Proc.MainWindowHandle | Out-Null
Start-Sleep -Milliseconds 400
Write-Host "detonating (CTRL+ALT+X)..." -ForegroundColor Yellow
Send-SelfDestruct

$rows = New-Object System.Collections.Generic.List[object]
$sw = [Diagnostics.Stopwatch]::StartNew()
$lastFrame = -1; $stalled = 0
while ($sw.Elapsed.TotalSeconds -lt $MaxSeconds) {
    $fr = Mem-I32 $ctx 0x5A7E1C
    $a  = Mem-EyeAngles $ctx
    if ($a) {
        $rows.Add([pscustomobject]@{
            t = [math]::Round($sw.Elapsed.TotalSeconds, 4); frame = $fr
            yaw = [math]::Round($a.Yaw, 4); pitch = [math]::Round($a.Pitch, 4)
        })
    }
    # the mission ends into STANDINGS, where the frame counter freezes - stop there
    if ($fr -eq $lastFrame) { $stalled++ } else { $stalled = 0; $lastFrame = $fr }
    if ($stalled -gt 60) { break }
    Start-Sleep -Milliseconds 15
}
Mem-Close $ctx

# keep only the moving-camera portion: frames actually advancing
$live = @($rows | Group-Object frame | ForEach-Object { $_.Group[0] } | Sort-Object t)
if ($live.Count -lt 8) { Write-Host "too few live frames ($($live.Count)) - was the car alive when this started?" -ForegroundColor Red; exit 1 }
$rows | Export-Csv -NoTypeInformation $out

$tot = 0.0
for ($k = 1; $k -lt $live.Count; $k++) {
    $d = $live[$k].yaw - $live[$k-1].yaw
    while ($d -gt 180) { $d -= 360 }
    while ($d -lt -180) { $d += 360 }
    $tot += $d
}
$dur = $live[-1].t - $live[0].t
$dfr = $live[-1].frame - $live[0].frame
$fps = if ($dur -gt 0) { $dfr / $dur } else { 0 }
Write-Host ("{0}: {1:N1} fps, {2} live frames over {3:N2}s" -f $Label, $fps, $live.Count, $dur) -ForegroundColor Green
Write-Host ("  total yaw {0:N1} deg" -f $tot)
Write-Host ("  ORBIT: {0:N2} deg/s   =   {1:N3} deg/frame" -f ($tot / $dur), ($tot / $dfr)) -ForegroundColor Cyan
Write-Host ("  -> {0}" -f $out) -ForegroundColor DarkGray
