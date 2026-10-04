<#
  ai-speed-test.ps1 — measure an AI car's speed at the current frame rate (memory only).

  Community report: "AI cars cap around 35 mph and flutter the steering at high FPS." This
  measures it: Trip mission 1's Taurus (entity slot 2) drives off on his own, so his speed is
  a clean read of AI-driven physics with no player input involved.

  Speed is derived from the entity's world position between samples (the culling table carries
  every vehicle's position), so it works for any AI car, not just the player.

    tools\ai-speed-test.ps1 -Seconds 20 -Slot 2 -Label ai20
#>
param([int]$Seconds = 20, [int]$Slot = 2, [string]$Label = 'ai', [int]$SampleMs = 100,
      [string]$OutDir = "$PSScriptRoot\..\..\captures\traces")
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\..\autotest\lib\memlib.ps1"
. "$PSScriptRoot\..\..\autotest\lib\focuslib.ps1"
. "$PSScriptRoot\..\..\autotest\lib\inputlib.ps1"
. "$PSScriptRoot\..\..\autotest\lib\simlib.ps1"
New-Item -ItemType Directory -Force $OutDir | Out-Null

$ctx = Mem-Open
if (-not (Mem-InMission $ctx)) { throw "not in a mission" }
if (-not (Ensure-SimRunning $ctx)) { throw "sim not advancing" }

# Drive forward so the mission starts and Taurus sets off (he waits for the player).
for ($i=0; $i -lt 6; $i++) { Send-Key $VK.W 50; Start-Sleep -Milliseconds 80 }

$inv = [Globalization.CultureInfo]::InvariantCulture
$rows = @('t_ms,frame,ai_x,ai_z,ai_speed,player_speed')
$sw = [Diagnostics.Stopwatch]::StartNew()
$prev = $null; $prevT = 0.0
$peak = 0.0
while ($sw.Elapsed.TotalSeconds -lt $Seconds) {
    Send-Key $VK.W 30      # keep the player rolling so the AI keeps going
    $t = $sw.Elapsed.TotalMilliseconds
    $ents = @(Mem-Entities $ctx)
    $ai = $ents | Where-Object { $_.Index -eq $Slot } | Select-Object -First 1
    $p  = Mem-Player $ctx
    if ($ai -and $prev) {
        $dt = ($t - $prevT) / 1000.0
        if ($dt -gt 0) {
            $d = [math]::Sqrt(([math]::Pow($ai.X-$prev.X,2)) + ([math]::Pow($ai.Y-$prev.Y,2)) + ([math]::Pow($ai.Z-$prev.Z,2)))
            $spd = $d / $dt
            if ($spd -lt 200) {   # ignore respawn teleports
                if ($spd -gt $peak) { $peak = $spd }
                $rows += (([int]$t).ToString($inv) + ',' + $p.Frame.ToString($inv) + ',' +
                          $ai.X.ToString('R',$inv) + ',' + $ai.Z.ToString('R',$inv) + ',' +
                          $spd.ToString('R',$inv) + ',' + $p.Speed.ToString('R',$inv))
            }
        }
    }
    $prev = $ai; $prevT = $t
    Start-Sleep -Milliseconds $SampleMs
}
$rows | Set-Content (Join-Path $OutDir "$Label.csv")
Mem-Close $ctx
Write-Host ("AI slot {0}: peak speed {1:N2} m/s ({2:N1} mph) over {3}s -> {4}.csv" -f `
    $Slot, $peak, ($peak * 2.23694), $Seconds, $Label) -ForegroundColor Green
