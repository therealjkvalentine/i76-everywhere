<#
  collision-test.ps1 — does the car pass THROUGH obstacles more often at high frame rate?

  Reported 2026-08-10: on the training level the car drives clean through a cactus about two
  thirds of the time at 60 fps and collides correctly the other third. Intermittency like that
  is the signature of a per-frame collision test whose cadence changed with frame rate — and it
  is the only bug on the list that affects GAMEPLAY rather than just the picture.

  Measuring it needs a counted repro, not an anecdote, because the outcome is probabilistic:
  run the same approach N times at each frame rate and compare HIT RATE.

  Method — a collision is detected from motion, not from graphics:
    * drive straight at full throttle from the spawn for a fixed distance
    * sample speed and position every frame
    * a HIT is a sudden speed loss (>= $HitDrop m/s within 0.25 s) while still on the ground;
      a MISS is arriving at the far end having never lost speed
  Terrain bumps are excluded by requiring the drop to be sharp and the car to be grounded.

  Each pass drives out and then reverses back toward the spawn, so the same obstacle field is
  re-approached without needing a mission restart.

    tools\framerate\collision-test.ps1 -Label coll20 -Passes 8

  Compare two runs with analyse-collision.py.
#>
param(
    [Parameter(Mandatory = $true)][string]$Label,
    [int]$Passes = 8,
    [double]$OutSeconds = 6,      # drive away from spawn
    [double]$BackSeconds = 6,     # reverse back
    [double]$HitDrop = 4.0,       # m/s lost within 0.25 s to count as an impact
    [string]$OutDir
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\..\autotest\lib\memlib.ps1"
. "$PSScriptRoot\..\..\autotest\lib\inputlib.ps1"
. "$PSScriptRoot\..\..\autotest\lib\focuslib.ps1"
if (-not $OutDir) { $OutDir = Join-Path $PSScriptRoot '..\..\captures\collision' }

$ctx = Mem-Open
if (-not (Mem-InMission $ctx)) { throw "not in a mission" }
New-Item -ItemType Directory -Force $OutDir | Out-Null
$out = Join-Path $OutDir "$Label.csv"
if (Test-Path $out) { Remove-Item $out -Force }

$VK_W = [byte]0x57; $VK_X = [byte]0x58
Force-Foreground $ctx.Proc.MainWindowHandle | Out-Null
$ent = Mem-PlayerEntity $ctx
$rows = New-Object System.Collections.Generic.List[object]

for ($pass = 1; $pass -le $Passes; $pass++) {
    foreach ($leg in @(@{ key = $VK_W; secs = $OutSeconds; dir = 'out' },
                       @{ key = $VK_X; secs = $BackSeconds; dir = 'back' })) {
        $sw = [Diagnostics.Stopwatch]::StartNew()
        while ($sw.Elapsed.TotalSeconds -lt $leg.secs) {
            Key-Down $leg.key
            $a = Mem-EyeAngles $ctx
            $s = Mem-Floats $ctx ($ent + 0xAC) 8      # +0xAC speed .. +0xC0 vy
            if ($a -and $s) {
                $rows.Add([pscustomobject]@{
                    pass  = $pass
                    leg   = $leg.dir
                    t     = [math]::Round($sw.Elapsed.TotalSeconds, 4)
                    frame = Mem-I32 $ctx 0x5A7E1C
                    speed = [math]::Round($s[0], 3)
                    vy    = [math]::Round($s[5], 3)
                    px    = [math]::Round($a.PX, 2)
                    py    = [math]::Round($a.PY, 2)
                    pz    = [math]::Round($a.PZ, 2)
                })
            }
            Start-Sleep -Milliseconds 8
        }
        Key-Up $leg.key
        Start-Sleep -Milliseconds 300
    }
    Write-Host ("pass {0}/{1} done" -f $pass, $Passes) -ForegroundColor DarkGray
}
Key-Up $VK_W; Key-Up $VK_X

$fps = ($rows[$rows.Count-1].frame - $rows[0].frame) / ($rows | Measure-Object -Property t -Sum).Sum
$rows | Export-Csv -NoTypeInformation $out
Mem-Close $ctx
Write-Host ("{0}: {1} passes, {2} samples -> {3}" -f $Label, $Passes, $rows.Count, $out) -ForegroundColor Green
Write-Host "now: python tools\framerate\analyse-collision.py <this csv> <other csv>" -ForegroundColor Cyan
