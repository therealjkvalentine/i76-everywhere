<#
  ffb-replay.ps1 - run a captured drive through the force model and report what
  the wheel WOULD have done.

  WHY: tuning by driving needs the wheel plugged in, a mission loaded, and a hand
  on the rim, and it gives you an impression rather than a number. Most of what is
  wrong with a set of gains is measurable without any of that:

    * a channel that is saturated ~all the time carries no information (CornerRef
      was 0.55 g against a real 2.99 g max, pinned at 97% of cornering samples -
      the wheel would have been one constant weight, and no amount of driving
      would have told you WHY it felt dead);
    * a channel that never fires is dead weight;
    * force that is clipped at the limiter is force you cannot feel differences in;
    * a transient that never decays, or one that re-triggers every frame.

  So this replays a CSV through the real Mix-Update and prints the distributions.

      tools\ffb\ffb-replay.ps1                                   # last calibration drive
      tools\ffb\ffb-replay.ps1 -Csv drive.csv
      tools\ffb\ffb-replay.ps1 -Set CornerRef=1.5,CornerGain=3000
      tools\ffb\ffb-replay.ps1 -Sweep CornerRef=0.5,1.0,2.0,2.8,4.0

  ---------------------------------------------------------------------------
  WHAT A CALIBRATION CSV CANNOT TELL YOU
  ---------------------------------------------------------------------------
  ffb-calib-samples.csv carries t, speed, steer, yaw only. From those, speed,
  steer, yaw, lateral g, longitudinal g and the whole loss-of-control signal are
  exact. But roll rate, pitch rate, vertical velocity, throttle and the velocity
  vector are absent, so:

      texture and judder are UNDERSTATED, and impact cannot fire at all.

  Those are reported as "no data" rather than as zero, because zero would read as
  "this channel is quiet" when the truth is "this drive cannot say".
  ffb-interposer.ps1 -DryRun -Log logs every field; use that capture for a
  complete picture.
#>
param(
    [string]$Csv = "",
    [string[]]$Set = @(),
    [string]$Sweep = "",
    [switch]$Verbose_
)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $here 'Telemetry.ps1')
. (Join-Path $here 'FfbMixer.ps1')

if (-not $Csv) { $Csv = Join-Path $here 'ffb-calib-samples.csv' }
if (-not (Test-Path $Csv)) {
    Write-Host "no capture at $Csv" -ForegroundColor Red
    Write-Host "Record one with:  ffb-calibrate.ps1   or   ffb-interposer.ps1 -DryRun -Log drive.csv" -ForegroundColor Yellow
    exit 1
}

$raw = @(Import-Csv $Csv)
$cols = $raw[0].PSObject.Properties.Name
$hasFull = ($cols -contains 'longG') -and ($cols -contains 'jolt')
Write-Host ("replaying {0} ({1} samples, {2} capture)" -f `
    (Split-Path -Leaf $Csv), $raw.Count, $(if ($hasFull) { "full" } else { "calibration" })) -ForegroundColor Cyan
Write-Host ("calibration: {0}" -f $script:TEL_CALIB_SOURCE) -ForegroundColor DarkGray
if (-not $hasFull) {
    Write-Host "NOTE: no roll/pitch/heave/throttle in this capture - texture and judder" -ForegroundColor Yellow
    Write-Host "      are understated and impact cannot fire. See the header." -ForegroundColor Yellow
}

# ---- rebuild Tel-Sample-shaped rows --------------------------------------
# Derived exactly as the live path does, and slip comes from Tel-Slip itself so
# this exercises the real logic rather than a copy of it.
function Build-Samples {
    param($Raw, [bool]$Full)
    $out = New-Object System.Collections.ArrayList
    $prevT = $null; $prevSpeed = 0.0; $longG = 0.0
    foreach ($r in $Raw) {
        $t = [double]$r.t; $sp = [double]$r.speed; $st = [double]$r.steer; $yw = [double]$r.yaw
        if ($null -ne $prevT) {
            $dt = $t - $prevT
            if ($dt -gt 0.005 -and $dt -lt 1.0) { $longG = (($sp - $prevSpeed) / $dt) / 9.81 }
        }
        $prevT = $t; $prevSpeed = $sp
        $slip = Tel-Slip -Speed $sp -Steer $st -YawRate $yw
        $null = $out.Add([pscustomobject]@{
            T = $t; Speed = $sp; SpeedMph = $sp * 2.23694; Steer = $st; Throttle = $(if ($Full) { [double]$r.throttle } else { 0.0 })
            YawRate = $yw
            RollRate  = $(if ($Full -and ($Raw[0].PSObject.Properties.Name -contains 'rollRate')) { [double]$r.rollRate } else { 0.0 })
            PitchRate = $(if ($Full -and ($Raw[0].PSObject.Properties.Name -contains 'pitchRate')) { [double]$r.pitchRate } else { 0.0 })
            Vy        = $(if ($Full -and ($Raw[0].PSObject.Properties.Name -contains 'vy')) { [double]$r.vy } else { 0.0 })
            LongG = $(if ($Full) { [double]$r.longG } else { $longG })
            LatG  = ($yw * $sp) / 9.81
            ExpectedYaw = $slip.ExpectedYaw; Understeer = $slip.Understeer; Oversteer = $slip.Oversteer
            Jolt = $(if ($Full) { [double]$r.jolt } else { 0.0 })
            Braking = $(if ($Full) { ([double]$r.throttle) -lt -0.05 } else { $longG -lt -0.05 })
            Airborne = $false; Ticks = 0; Polls = 0; Wheelbase = 4.662
        })
    }
    return $out
}
$samples = Build-Samples $raw $hasFull

$ALL_CH = @('center','corner','oversteer','brake','texture','scrub','judder','impact')
$UNAVAILABLE = if ($hasFull) { @() } else { @('texture','judder','impact') }

function Run-Replay {
    param($Samples, $Tune)
    $mix = Mix-New $Tune
    $acc = @{}; foreach ($c in $ALL_CH) { $acc[$c] = New-Object System.Collections.ArrayList }
    $forces = New-Object System.Collections.ArrayList
    $clip = 0; $impacts = 0
    foreach ($s in $Samples) {
        $o = Mix-Update $mix $s
        foreach ($c in $ALL_CH) { $null = $acc[$c].Add([math]::Abs([double]$o.Channels[$c])) }
        $null = $forces.Add([double]$o.Force)
        if ([math]::Abs($o.Force) -ge ($Tune['Clamp'] * 0.999)) { $clip++ }
        foreach ($n in $o.Notes) { if ($n -match 'IMPACT') { $impacts++ } }
    }
    return [pscustomobject]@{ Ch = $acc; Forces = $forces; Clip = $clip; Impacts = $impacts; Mix = $mix }
}

function Pct { param($V, [double]$P) $s = @($V | Sort-Object); if (-not $s.Count) { return 0 }; return $s[[math]::Min($s.Count - 1, [int]($s.Count * $P))] }

# ---- apply -Set overrides -------------------------------------------------
$tune = Mix-DefaultTune
foreach ($kv in $Set) {
    foreach ($pair in ($kv -split ',')) {
        if ($pair -match '^\s*(\w+)\s*=\s*([\-\d.]+)\s*$') {
            $k = $Matches[1]; $v = [double]$Matches[2]
            if ($tune.ContainsKey($k)) { $tune[$k] = $v; Write-Host ("  set {0} = {1}" -f $k, $v) -ForegroundColor Green }
            else { Write-Host ("  unknown tunable '{0}' - ignored" -f $k) -ForegroundColor Yellow }
        }
    }
}

# ---- sweep mode -----------------------------------------------------------
if ($Sweep) {
    if ($Sweep -notmatch '^\s*(\w+)\s*=\s*(.+)$') { Write-Host "use -Sweep Name=v1,v2,v3" -ForegroundColor Red; exit 1 }
    $key = $Matches[1]; $vals = $Matches[2] -split ',' | ForEach-Object { [double]$_ }
    if (-not $tune.ContainsKey($key)) { Write-Host "unknown tunable '$key'" -ForegroundColor Red; exit 1 }
    Write-Host ""
    Write-Host ("--- sweeping {0} ---" -f $key) -ForegroundColor Green
    Write-Host ("  {0,10}  {1,8}  {2,8}  {3,8}  {4,8}" -f $key, "med|F|", "p90|F|", "max|F|", "clip%")
    foreach ($v in $vals) {
        $t2 = @{}; foreach ($k in $tune.Keys) { $t2[$k] = $tune[$k] }
        $t2[$key] = $v
        $r = Run-Replay $samples $t2
        $abs = @($r.Forces | ForEach-Object { [math]::Abs($_) })
        Write-Host ("  {0,10:0.###}  {1,8:0}  {2,8:0}  {3,8:0}  {4,7:0.0}%" -f `
            $v, (Pct $abs 0.5), (Pct $abs 0.9), (($abs | Measure-Object -Maximum).Maximum),
            ($r.Clip * 100.0 / $samples.Count))
    }
    exit 0
}

# ---- single run -----------------------------------------------------------
$r = Run-Replay $samples $tune
$n = $samples.Count

Write-Host ""
Write-Host "--- per channel (|contribution|, over all samples) ---" -ForegroundColor Green
Write-Host ("  {0,-10} {1,7} {2,7} {3,7}  {4,7}  {5}" -f "channel", "med", "p90", "max", "active%", "note")
foreach ($c in $ALL_CH) {
    $v = @($r.Ch[$c])
    $active = (@($v | Where-Object { $_ -gt 1 }).Count) * 100.0 / $n
    $mx = ($v | Measure-Object -Maximum).Maximum
    $note = ""
    if ($UNAVAILABLE -contains $c) { $note = "no data in this capture" }
    elseif ($mx -lt 1) { $note = "NEVER FIRES" }
    elseif ($active -gt 90 -and (Pct $v 0.5) -gt ($mx * 0.9)) { $note = "SATURATED - carries no information" }
    elseif ($active -lt 2) { $note = "fires rarely" }
    Write-Host ("  {0,-10} {1,7:0} {2,7:0} {3,7:0}  {4,6:0.0}%  {5}" -f `
        $c, (Pct $v 0.5), (Pct $v 0.9), $mx, $active, $note)
}

$abs = @($r.Forces | ForEach-Object { [math]::Abs($_) })
Write-Host ""
Write-Host "--- total force ---" -ForegroundColor Green
Write-Host ("  median {0:0}   p90 {1:0}   max {2:0}   clamp {3}" -f `
    (Pct $abs 0.5), (Pct $abs 0.9), (($abs | Measure-Object -Maximum).Maximum), $tune['Clamp'])
Write-Host ("  clipped at the limiter: {0:0.0}% of samples" -f ($r.Clip * 100.0 / $n))
$quiet = (@($abs | Where-Object { $_ -lt 200 }).Count) * 100.0 / $n
Write-Host ("  near-silent (<200): {0:0.0}% of samples" -f $quiet)
if (($r.Clip * 100.0 / $n) -gt 10) {
    Write-Host "  >10% clipped - differences up there cannot be felt. Lower the gains." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "--- loss of control ---" -ForegroundColor Green
$u = @($samples | Where-Object { $_.Understeer -gt 0.3 })
$o = @($samples | Where-Object { $_.Oversteer  -gt 0.3 })
Write-Host ("  understeer >0.3 : {0,4} samples ({1:0.0}%)" -f $u.Count, ($u.Count * 100.0 / $n))
Write-Host ("  oversteer  >0.3 : {0,4} samples ({1:0.0}%)" -f $o.Count, ($o.Count * 100.0 / $n))
Write-Host ("  impacts triggered: {0}" -f $r.Impacts)
if ($o.Count -gt 0) {
    Write-Host "  worst oversteer moments (the spins and hits):"
    foreach ($s in (@($samples | Sort-Object { -$_.Oversteer } | Select-Object -First 4))) {
        Write-Host ("     t {0,6:0.0}s  {1,5:0.0} mph  steer {2,6:0.00}  yaw {3,6:0.00}  expected {4,6:0.00}  O {5:0.00}" -f `
            $s.T, $s.SpeedMph, $s.Steer, $s.YawRate, $s.ExpectedYaw, $s.Oversteer)
    }
}
Write-Host ""
Write-Host "Tune with -Set / -Sweep, then judge the result on the wheel - this" -ForegroundColor DarkGray
Write-Host "measures whether the model is USABLE, not whether it feels good." -ForegroundColor DarkGray
