<#
  death-cam-test.ps1 — measure the post-death camera orbit rate.

  Of the four frame-coupled bugs reported from play, this is the one that is unambiguously an
  animation rather than physics, and it is now measurable: when the player dies the view orbits
  the wreck, and the eye transform at 0x5FCDC4 gives that orbit's yaw directly.

  Dying reliably is the awkward part. A zero-AI melee is right for physics work but there is
  nobody to kill you, and driving into scenery is slow and unreliable - so this run KEEPS the
  AI cars (-KeepAI) and simply drives at them. Their interference does not matter here: the
  measurement starts once the player is already dead and stationary.

    tools\death-cam-test.ps1 -Label death20 -Seconds 150

  Detection is left to the analyser: the signature is eye yaw advancing steadily while the
  player's speed sits at zero.
#>
param(
    [Parameter(Mandatory = $true)][string]$Label,
    [double]$Seconds = 150,
    [double]$MinTargetDist = 400,   # skip the mission escort; drive at the opposition
    [string]$OutDir
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\..\autotest\lib\memlib.ps1"
. "$PSScriptRoot\..\..\autotest\lib\inputlib.ps1"
. "$PSScriptRoot\..\..\autotest\lib\focuslib.ps1"
if (-not $OutDir) { $OutDir = Join-Path $PSScriptRoot '..\captures\death' }

$ctx = Mem-Open
if (-not (Mem-InMission $ctx)) { throw "not in a mission" }
New-Item -ItemType Directory -Force $OutDir | Out-Null
$out = Join-Path $OutDir "$Label.csv"
if (Test-Path $out) { Remove-Item $out -Force }

$VK_W = [byte]0x57; $VK_A = [byte]0x41; $VK_D = [byte]0x44; $VK_X = [byte]0x58   # X = reverse
Force-Foreground $ctx.Proc.MainWindowHandle | Out-Null
$rows = New-Object System.Collections.Generic.List[object]
$ent = Mem-PlayerEntity $ctx
$stillFrames = 0; $deadAt = $null; $hasMoved = $false
$stuckFor = 0; $unstickDir = $true; $sp = 0

Key-Down $VK_W
$sw = [Diagnostics.Stopwatch]::StartNew()
while ($sw.Elapsed.TotalSeconds -lt $Seconds) {
    $t = $sw.Elapsed.TotalSeconds
    $a = Mem-EyeAngles $ctx
    # HUNT a distant vehicle. Two policies were tried and failed first:
    #   * a fixed weave kept the car circling in a 342 x 95 m box for 300 s, meeting nobody;
    #   * "nearest entity" then spent 300 s chasing slot 1 at 79 m - which is TAURUS, the
    #     mission escort. The opposition sits 500-3000 m out in clusters.
    # So skip anything closer than $MinTargetDist and drive at the nearest thing beyond it.
    # Stuck recovery. Driving at a distant target jams the car against terrain, and holding the
    # throttle into a hillside does nothing forever: one run sat at 0.95 m/s in a 34 x 96 m box
    # for the full 420 s. Back up and turn out of it.
    if (-not $deadAt -and $hasMoved -and $sp -lt 1.5) { $stuckFor++ } else { $stuckFor = 0 }
    if ($stuckFor -gt 150) {
        Key-Up $VK_W; Key-Up $VK_A; Key-Up $VK_D
        $rev = [Diagnostics.Stopwatch]::StartNew()
        while ($rev.Elapsed.TotalSeconds -lt 1.8) {
            Key-Down $VK_X; Key-Down $(if ($unstickDir) { $VK_A } else { $VK_D })
            Start-Sleep -Milliseconds 20
        }
        Key-Up $VK_X; Key-Up $VK_A; Key-Up $VK_D
        $unstickDir = -not $unstickDir      # alternate, so a corner cannot trap it forever
        $stuckFor = 0
        continue
    }
    if (-not $deadAt -and $a) {
        Key-Down $VK_W
        $best = $null; $bestD = [double]::MaxValue
        foreach ($en in Mem-Entities $ctx) {
            if ($en.Index -eq 0) { continue }
            $dd = [math]::Sqrt([math]::Pow($en.X - $a.PX, 2) + [math]::Pow($en.Z - $a.PZ, 2))
            if ($dd -gt $MinTargetDist -and $dd -lt $bestD) { $bestD = $dd; $best = $en }
        }
        if ($best) {
            $want = [math]::Atan2($best.X - $a.PX, $best.Z - $a.PZ) * 180.0 / [math]::PI
            $err = ($want - $a.Yaw) % 360
            if ($err -gt 180) { $err -= 360 } elseif ($err -lt -180) { $err += 360 }
            if ($err -gt 8)      { Key-Up $VK_A; Key-Down $VK_D }
            elseif ($err -lt -8) { Key-Up $VK_D; Key-Down $VK_A }
            else                 { Key-Up $VK_A; Key-Up $VK_D }
        }
    }
    $e = Mem-PlayerEntity $ctx
    $sp = if ($e) { Mem-F32 $ctx ($e + 0xAC) } else { 0 }
    # Log EVERY sample. Guarding on `if ($a)` dropped precisely the frames this test exists to
    # capture: Mem-EyeAngles returns null when the forward vector collapses, which is what the
    # transform does at the moment of death, so a run recorded zero post-death frames.
    $raw = Mem-Floats $ctx 0x5FCDC4 12
    $rows.Add([pscustomobject]@{
        t = [math]::Round($t,4); frame = Mem-I32 $ctx 0x5A7E1C
        yaw   = $(if ($a) { [math]::Round($a.Yaw,4) }   else { 'NaN' })
        pitch = $(if ($a) { [math]::Round($a.Pitch,4) } else { 'NaN' })
        roll  = $(if ($a) { [math]::Round($a.Roll,4) }  else { 'NaN' })
        px = [math]::Round($raw[0],2); py = [math]::Round($raw[1],2); pz = [math]::Round($raw[2],2)
        fx = [math]::Round($raw[6],5); fy = [math]::Round($raw[7],5); fz = [math]::Round($raw[8],5)
        ux = [math]::Round($raw[9],5); uy = [math]::Round($raw[10],5); uz = [math]::Round($raw[11],5)
        speed = [math]::Round($sp,3); ent = $e
    })
    # once stationary for a while, stop driving and just watch the camera. "Stationary" only
    # counts after the car has actually driven - at the spawn it is stopped too, and an earlier
    # run declared death at t=3.4s before the player had moved at all.
    if ($sp -gt 5) { $hasMoved = $true }
    if ($hasMoved -and $sp -lt 0.2) { $stillFrames++ } else { $stillFrames = 0 }
    if (-not $deadAt -and $hasMoved -and ($stillFrames -gt 120 -or $e -eq 0)) {
        $deadAt = $t
        Key-Up $VK_W; Key-Up $VK_A; Key-Up $VK_D
        Write-Host ("stationary/dead at t={0:N1}s - watching the camera" -f $t) -ForegroundColor Yellow
    }
    if ($deadAt -and ($t - $deadAt) -gt 20) { break }
    Start-Sleep -Milliseconds 8
}
Key-Up $VK_W; Key-Up $VK_A; Key-Up $VK_D

$fps = ($rows[$rows.Count-1].frame - $rows[0].frame) / $rows[$rows.Count-1].t
$rows | Export-Csv -NoTypeInformation $out
Mem-Close $ctx
Write-Host ("{0}: {1:N1} fps, {2} samples, dead at {3} -> {4}" -f $Label, $fps, $rows.Count, `
    $(if ($deadAt) { '{0:N1}s' -f $deadAt } else { 'never' }), $out) -ForegroundColor Green
