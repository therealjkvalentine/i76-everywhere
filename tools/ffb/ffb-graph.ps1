<#
  ffb-graph.ps1 - replay a captured drive and draw what the force model DID.

  ffb-replay.ps1 gives you distributions - medians, percentiles, "this channel
  never fires". That catches a lot, but it cannot show you SHAPE: whether an
  impact reads as a spike or is buried in the steady floor, whether texture is a
  constant hum, whether a spin builds or snaps. Those are the questions tuning
  actually turns on, and they are questions about a curve over time.

  So this replays the same drive through the same Mix-Update and writes a
  self-contained interactive HTML report - stat tiles, stacked time-series panels
  on a shared crosshair, event markers, and a table view. No server, no CDN, no
  dependencies: one file you can open, keep, and diff against the next one.

      tools\ffb\ffb-graph.ps1                          # last capture
      tools\ffb\ffb-graph.ps1 -Csv drive2.csv
      tools\ffb\ffb-graph.ps1 -Csv drive2.csv -Set SatGain=1800,CornerGain=1200
      tools\ffb\ffb-graph.ps1 -Csv drive2.csv -From 60 -To 90   # zoom a window

  The -Set flag is the point: render the same drive under two tunes and put the
  two files side by side. That is a tuning loop that needs neither the wheel nor
  the game.
#>
param(
    [string]$Csv = "",
    [string[]]$Set = @(),
    [string]$Out = "",
    [double]$From = 0,
    [double]$To = 0,
    [int]$MaxPoints = 4000
)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $here 'Telemetry.ps1')
. (Join-Path $here 'FfbMixer.ps1')

if (-not $Csv) { $Csv = Join-Path $here 'ffb-calib-samples.csv' }
if (-not (Test-Path $Csv)) {
    Write-Host "no capture at $Csv" -ForegroundColor Red
    Write-Host "Record one with: ffb-interposer.ps1 -DryRun -Log drive.csv" -ForegroundColor Yellow
    exit 1
}
if (-not $Out) { $Out = [System.IO.Path]::ChangeExtension($Csv, $null) + "graph.html" }

$raw  = @(Import-Csv $Csv)
$cols = $raw[0].PSObject.Properties.Name
$hasFull = ($cols -contains 'longG') -and ($cols -contains 'jolt')
$has = { param($n) $cols -contains $n }

$tune = Mix-DefaultTune
$setNotes = @()
foreach ($kv in $Set) {
    foreach ($pair in ($kv -split ',')) {
        if ($pair -match '^\s*(\w+)\s*=\s*([\-\d.]+)\s*$') {
            $k = $Matches[1]; $v = [double]$Matches[2]
            if ($tune.ContainsKey($k)) { $tune[$k] = $v; $setNotes += "$k=$v" }
            else { Write-Host "unknown tunable '$k' - ignored" -ForegroundColor Yellow }
        }
    }
}

Write-Host ("replaying {0} ({1} samples, {2})" -f (Split-Path -Leaf $Csv), $raw.Count,
    $(if ($hasFull) { "full capture" } else { "calibration capture - texture/judder/impact understated" })) -ForegroundColor Cyan

# ---- replay through the REAL mixer --------------------------------------
$mix = Mix-New $tune
$rows = New-Object System.Collections.ArrayList
$events = New-Object System.Collections.ArrayList
$prevT = $null; $prevSpeed = 0.0; $longG = 0.0
$clip = 0

foreach ($r in $raw) {
    $t = [double]$r.t
    $sp = [double]$r.speed; $st = [double]$r.steer; $yw = [double]$r.yaw
    if ($null -ne $prevT) {
        $dt = $t - $prevT
        if ($dt -gt 0.005 -and $dt -lt 1.0) { $longG = (($sp - $prevSpeed) / $dt) / 9.81 }
    }
    $prevT = $t; $prevSpeed = $sp
    $slip = Tel-Slip -Speed $sp -Steer $st -YawRate $yw
    $lg = if ($hasFull) { [double]$r.longG } else { $longG }
    $vy = if (& $has 'vy') { [double]$r.vy } else { 0.0 }
    $s = [pscustomobject]@{
        T = $t; Speed = $sp; SpeedMph = $sp * 2.23694; Steer = $st
        Throttle = $(if (& $has 'throttle') { [double]$r.throttle } else { 0.0 })
        YawRate = $yw
        AngVelX = $(if (& $has 'angVelX') { [double]$r.angVelX } else { 0.0 })
        AngVelZ = $(if (& $has 'angVelZ') { [double]$r.angVelZ } else { 0.0 })
        Vy = $vy
        LongG = $lg; LongAccel = ($lg * 9.81)
        LatG = (($yw * $sp) / 9.81); LatAccel = ($yw * $sp)
        HeaveAccel = 0.0; TravelPitch = $(if ($sp -gt 2.0) { [math]::Asin([math]::Max(-1.0,[math]::Min(1.0,$vy/$sp))) } else { 0.0 })
        ExpectedYaw = $slip.ExpectedYaw; Understeer = $slip.Understeer; Oversteer = $slip.Oversteer
        Jolt = $(if (& $has 'jolt') { [double]$r.jolt } else { 0.0 })
        Firing = $(if (& $has 'weapon') { $false } else { $false })
        Braking = ($lg -lt -0.05); Airborne = ([math]::Abs($vy) -gt 2.0)
        Ticks = 0; Polls = 0; Wheelbase = 4.662
    }
    $o = Mix-Update $mix $s
    if ([math]::Abs($o.Force) -ge ($tune['Clamp'] * 0.999)) { $clip++ }
    foreach ($n in $o.Notes) { $null = $events.Add([pscustomobject]@{ t = [math]::Round($t,2); label = $n }) }
    $null = $rows.Add([pscustomobject]@{
        t = [math]::Round($t,3)
        mph = [math]::Round($s.SpeedMph,1)
        steer = [math]::Round($st,3)
        force = $o.Force
        center = [int]$o.Channels['center']; corner = [int]$o.Channels['corner']
        oversteer = [int]$o.Channels['oversteer']; brake = [int]$o.Channels['brake']
        texture = [int]$o.Channels['texture']; scrub = [int]$o.Channels['scrub']
        judder = [int]$o.Channels['judder']; impact = [int]$o.Channels['impact']
        weapon = [int]$o.Channels['weapon']
        grip = [int]$o.Channels['grip%']
        surge = $o.Bus.Motion.SurgeA; sway = $o.Bus.Motion.SwayA; yawr = $o.Bus.Motion.YawRate
        lfeEng = $o.Bus.Lfe.EngineAmp; lfeEngF = $o.Bus.Lfe.EngineFreq
        lfeRoad = $o.Bus.Lfe.RoadAmp; lfeImp = $o.Bus.Lfe.ImpulseAmp
        padL = 0.0; padR = 0.0
    })
    $last = $rows[$rows.Count-1]
    $pad = Mix-RenderPad $o.Bus
    $last.padL = $pad.Left; $last.padR = $pad.Right
}

# window + downsample (stride, so shape survives)
$sel = $rows
if ($To -gt 0) { $sel = @($sel | Where-Object { $_.t -ge $From -and $_.t -le $To }) }
elseif ($From -gt 0) { $sel = @($sel | Where-Object { $_.t -ge $From }) }
$stride = [math]::Max(1, [int][math]::Ceiling($sel.Count / [double]$MaxPoints))
if ($stride -gt 1) {
    $sel = @(for ($i=0; $i -lt $sel.Count; $i += $stride) { $sel[$i] })
    Write-Host ("downsampled by {0} -> {1} points" -f $stride, $sel.Count) -ForegroundColor DarkGray
}

$absF = @($rows | ForEach-Object { [math]::Abs($_.force) } | Sort-Object)
function Pk { param($a,[double]$p) if (-not $a.Count) { 0 } else { $a[[math]::Min($a.Count-1,[int]($a.Count*$p))] } }
$stats = [pscustomobject]@{
    samples = $rows.Count
    seconds = [math]::Round(($rows[$rows.Count-1].t - $rows[0].t),1)
    medF = [int](Pk $absF 0.5); p90F = [int](Pk $absF 0.9); maxF = [int](Pk $absF 1.0)
    clipPct = [math]::Round($clip * 100.0 / $rows.Count, 2)
    quietPct = [math]::Round((@($absF | Where-Object { $_ -lt 200 }).Count) * 100.0 / $rows.Count, 1)
    clamp = [int]$tune['Clamp']
}

$payload = [pscustomobject]@{
    file = (Split-Path -Leaf $Csv); rows = $sel; events = @($events)
    stats = $stats; calib = $script:TEL_CALIB_SOURCE
    tune = ($setNotes -join ', '); full = $hasFull
} | ConvertTo-Json -Depth 6 -Compress

$tpl = Get-Content (Join-Path $here 'ffb-graph.template.html') -Raw
$html = $tpl.Replace('/*__DATA__*/', $payload)
Set-Content -Path $Out -Value $html -Encoding UTF8
Write-Host ""
Write-Host ("force median {0}  p90 {1}  max {2} of {3}   clipped {4}%   near-silent {5}%" -f `
    $stats.medF, $stats.p90F, $stats.maxF, $stats.clamp, $stats.clipPct, $stats.quietPct) -ForegroundColor Green
Write-Host ("-> {0}" -f (Resolve-Path $Out)) -ForegroundColor Cyan
