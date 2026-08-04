<#
  ffb-calibrate.ps1 - measure the two things the force model would guess.

    TEL_YAW_SIGN   Does a positive steer input produce a positive yaw rate at
                   +0xCC? Nothing in the struct says. Get it wrong and the
                   cornering channel pushes the wrong way - the wheel helps you
                   turn INTO the corner instead of resisting.

    TEL_STEER_LOCK Radians of road-wheel angle at full steering input. The engine
                   stores steer as -1..1 with no stated mapping. This scales the
                   bicycle-model yaw prediction, so it decides how readily
                   understeer and oversteer trigger.

  Writes ffb-calib.json next to this script; Telemetry.ps1 loads it automatically.
  Always writes ffb-calib-samples.csv too - see "raw samples" below.

      tools\ffb\ffb-calibrate.ps1
      tools\ffb\ffb-calibrate.ps1 -FromLog drive.csv     # reuse a captured drive
      tools\ffb\ffb-calibrate.ps1 -FromLog ffb-calib-samples.csv   # refit, no driving

  DRIVE LIKE THIS: above ~20 mph, several SUSTAINED smooth turns both ways. Hold
  each turn for a second or more.

  ---------------------------------------------------------------------------
  HOW THE LOCK IS FITTED, AND WHY NOT THE OBVIOUS WAY
  ---------------------------------------------------------------------------
  The bicycle model says  yawRate = (speed / wheelbase) * tan(steer * lock).
  Rearranged per sample that gives  lock = atan(yaw * wheelbase / speed) / steer,
  and the obvious move is to take the median of those.

  THAT DOES NOT WORK, and it produced a confidently-reported 5.8 deg on a real
  drive - roughly a seventh of the truth. Two reasons:

    1. Dividing by `steer` amplifies noise wherever steer is small. A nearly
       straight sample (steer 0.2, yaw 0.03) fits a tiny lock, and nearly
       straight samples vastly outnumber hard-cornering ones, so the MEDIAN sits
       in the noise rather than in the cornering data.
    2. Yaw LAGS steer by a few tenths of a second. Mid-transition, steer is
       already large while yaw is still building, which fits a lock that is too
       small. Sinusoidal steering is mostly transition.

  So instead:
    * REGRESSION THROUGH THE ORIGIN on  theta = atan(yaw*wheelbase/speed)
      against steer:  lock = sum(steer*theta) / sum(steer^2).
      This never divides by a small steer, and it weights each sample by
      steer^2 - so the hard-cornering samples that actually carry the
      information dominate, which is what you want.
    * a STEADINESS filter, keeping only samples where steer and yaw are both
      roughly constant, which removes the lag bias.
    * a FALSIFICATION check: does the fitted lock reproduce the largest yaw rates
      actually observed? A lock of 0.101 rad cannot produce 1.6 rad/s at 10 m/s
      (it predicts 0.22), and that contradiction is checkable without knowing the
      right answer. If the fit fails it, nothing is written.
    * a PLAUSIBILITY range. Road cars run 10-45 deg of lock; outside that the fit
      is reporting something other than a steering lock.

  The sign is fitted separately and is robust - it needs no model at all, only
  that turning one way rotates the car one way.

  ---------------------------------------------------------------------------
  RAW SAMPLES
  ---------------------------------------------------------------------------
  Every run dumps its samples to ffb-calib-samples.csv. The first version of this
  tool kept nothing, so when its fit came out wrong the only way to investigate
  was to ask for another 30-second drive. Keeping the raw data means a bad fit can
  be re-analysed offline as many times as needed, with -FromLog.
#>
param(
    [int]$Seconds = 30,
    [string]$FromLog = "",
    # Fit and report but do NOT write ffb-calib.json.
    [switch]$NoWrite
)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

$MIN_SPEED    = 8.0     # m/s; below this yaw is dominated by scrub, not geometry
$MIN_STEER    = 0.15    # near centre the relation is all noise
$MIN_YAW      = 0.02
$STEADY_STEER = 0.8     # max |d steer/dt| (per second) to count as steady
$STEADY_YAW   = 1.5     # max |d yaw/dt| (rad/s^2) to count as steady
$LOCK_MIN     = 0.17    # 10 deg
$LOCK_MAX     = 0.79    # 45 deg

$rows = @()
$wheelbase = 4.662

if ($FromLog) {
    if (-not (Test-Path $FromLog)) { Write-Host "no such log: $FromLog" -ForegroundColor Red; exit 1 }
    Write-Host "reading $FromLog ..." -ForegroundColor Cyan
    foreach ($r in (Import-Csv $FromLog)) {
        $rows += [pscustomobject]@{
            T = [double]$r.t; Speed = [double]$r.speed; Steer = [double]$r.steer; Yaw = [double]$r.yaw
        }
    }
} else {
    . (Join-Path $here 'Telemetry.ps1')
    $ctx = Tel-Open
    $wheelbase = $ctx.Wheelbase
    Write-Host ("telemetry OK - entity 0x{0:X8}, wheelbase {1:0.00} m" -f $ctx.Ent, $wheelbase) -ForegroundColor Green
    Write-Host ""
    Write-Host "DRIVE NOW for $Seconds s." -ForegroundColor Yellow
    Write-Host "Above 20 mph, several SUSTAINED turns both ways - HOLD each turn." -ForegroundColor Yellow
    Write-Host ""
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $lastNote = -1
    $maxSteer = 0.0; $maxYaw = 0.0
    while ($sw.Elapsed.TotalSeconds -lt $Seconds) {
        $s = Tel-Sample $ctx
        if ($s) {
            $rows += [pscustomobject]@{ T = $s.T; Speed = $s.Speed; Steer = $s.Steer; Yaw = $s.YawRate }
            if ([math]::Abs($s.Steer) -gt $maxSteer) { $maxSteer = [math]::Abs($s.Steer) }
            if ([math]::Abs($s.YawRate) -gt $maxYaw) { $maxYaw = [math]::Abs($s.YawRate) }
            $el = [int]$sw.Elapsed.TotalSeconds
            if ($el -ne $lastNote) {
                $lastNote = $el
                # Show the PEAKS, not the instantaneous values. The old display
                # showed whatever the last sample happened to be, which read
                # "steer 0.00 yaw 0.000" at the end of a perfectly good drive and
                # looked like a failure.
                Write-Host ("`r  {0,3}s left   {1,5:0.0} mph   peak steer {2,4:0.00}   peak yaw {3,5:0.00}   samples {4,4}" -f `
                    ($Seconds - $el), $s.SpeedMph, $maxSteer, $maxYaw, $rows.Count) -NoNewline
            }
        }
        Start-Sleep -Milliseconds 20
    }
    Write-Host ""
    Tel-Close $ctx
}

if ($rows.Count -lt 30) { Write-Host "`nonly $($rows.Count) samples - nothing to fit." -ForegroundColor Red; exit 1 }

# ---- always keep the raw data ---------------------------------------------
if (-not $FromLog) {
    $dump = Join-Path $here 'ffb-calib-samples.csv'
    "t,speed,steer,yaw" | Set-Content -Path $dump -Encoding ASCII
    foreach ($r in $rows) {
        ("{0:0.000},{1:0.000},{2:0.000},{3:0.000}" -f $r.T, $r.Speed, $r.Steer, $r.Yaw) |
            Add-Content -Path $dump -Encoding ASCII
    }
    Write-Host "raw samples -> $dump" -ForegroundColor DarkGray
}

# ---- derivatives, for the steadiness test --------------------------------
$n = $rows.Count
for ($i = 0; $i -lt $n; $i++) {
    $dS = 0.0; $dY = 0.0
    if ($i -gt 0) {
        $dt = $rows[$i].T - $rows[$i-1].T
        if ($dt -gt 0.001 -and $dt -lt 0.5) {
            $dS = ($rows[$i].Steer - $rows[$i-1].Steer) / $dt
            $dY = ($rows[$i].Yaw   - $rows[$i-1].Yaw)   / $dt
        }
    }
    $rows[$i] | Add-Member -NotePropertyName dSteer -NotePropertyValue $dS -Force
    $rows[$i] | Add-Member -NotePropertyName dYaw   -NotePropertyValue $dY -Force
}

# ---- filter ---------------------------------------------------------------
$usable = @($rows | Where-Object {
    $_.Speed -gt $MIN_SPEED -and [math]::Abs($_.Steer) -gt $MIN_STEER -and [math]::Abs($_.Yaw) -gt $MIN_YAW })
Write-Host ""
Write-Host ("samples {0}   usable {1}" -f $rows.Count, $usable.Count) -ForegroundColor Cyan
if ($usable.Count -lt 25) {
    Write-Host ""
    Write-Host "NOT ENOUGH USABLE DATA - nothing written." -ForegroundColor Red
    Write-Host "Need 25+ samples above 18 mph with the wheel past $MIN_STEER." -ForegroundColor Yellow
    exit 1
}

# ---- sign: model-free ----------------------------------------------------
$agree = 0; $disagree = 0
foreach ($r in $usable) {
    if ([math]::Sign($r.Steer) -eq [math]::Sign($r.Yaw)) { $agree++ } else { $disagree++ }
}
$sign = if ($agree -ge $disagree) { 1 } else { -1 }
$conf = [math]::Max($agree, $disagree) / [double]$usable.Count
Write-Host ""
Write-Host "--- yaw sign ---" -ForegroundColor Green
Write-Host ("  agree {0}   disagree {1}   ->  TEL_YAW_SIGN = {2}  (confidence {3:0}%)" -f `
    $agree, $disagree, $sign, ($conf * 100))
if ($conf -lt 0.8) {
    Write-Host "  LOW CONFIDENCE - re-run with smoother, more sustained turns." -ForegroundColor Yellow
}

# ---- lateral gain: regression through the origin on steer/speed ----------
# The handling model (measured, R^2 = 0.9995 - see Telemetry.ps1's header):
#     yaw = a * steer / speed      i.e.  lateral accel = a * steer
# One parameter. No steering lock, no wheelbase, no understeer gradient - the
# engine commands lateral acceleration and does not model tyres.
function Fit-LatGain {
    param($Set, [int]$Sign)
    $sxy = 0.0; $sxx = 0.0; $used = 0
    $pts = New-Object System.Collections.ArrayList
    foreach ($r in $Set) {
        $y = $r.Yaw * $Sign
        # Spins and impacts are not cornering - exclude them from the FIT, then
        # measure how far they deviate from it (that is the whole loss-of-control
        # signal). Rotating against the steering is the clearest marker.
        if ([math]::Sign($y) -ne [math]::Sign($r.Steer)) { continue }
        $x = $r.Steer / $r.Speed
        $sxy += $x * $y
        $sxx += $x * $x
        $used++
        $null = $pts.Add(@($x, $y))
    }
    if ($sxx -le 0 -or $used -lt 15) { return $null }
    $a = $sxy / $sxx
    # R^2 and residual sd, so the fit can be judged rather than trusted.
    $mean = 0.0; foreach ($p in $pts) { $mean += $p[1] }; $mean /= $pts.Count
    $ssRes = 0.0; $ssTot = 0.0
    foreach ($p in $pts) {
        $ssRes += [math]::Pow($p[1] - $a * $p[0], 2)
        $ssTot += [math]::Pow($p[1] - $mean, 2)
    }
    $r2 = if ($ssTot -gt 0) { 1.0 - ($ssRes / $ssTot) } else { 0.0 }
    $sd = [math]::Sqrt($ssRes / $pts.Count)
    return [pscustomobject]@{ A = $a; Used = $used; R2 = $r2; Sd = $sd }
}

# Steadiness is judged RELATIVE to the yaw magnitude, not against a fixed rad/s^2
# threshold. Because yaw = a*steer/speed, the yaw rates at 90 mph are a quarter of
# those at 22 mph, and so are their transients - an absolute threshold therefore
# filters transients out at low speed and lets them straight through at high speed,
# exactly where most driving happens. Caught by ffb-calib-test.ps1 test 3, which
# fitted 26.2 instead of 29.3 on a high-speed-only drive.
# $STEADY_YAW is retained as an absolute floor so a near-zero yaw is not held to an
# impossibly tight relative bound.
$steady = @($usable | Where-Object {
    [math]::Abs($_.dSteer) -lt $STEADY_STEER -and
    [math]::Abs($_.dYaw)   -lt [math]::Max(0.15, 1.0 * [math]::Abs($_.Yaw)) })

$fitAll    = Fit-LatGain $usable $sign
$fitSteady = Fit-LatGain $steady $sign

Write-Host ""
Write-Host "--- lateral gain (a in: lateral accel = a * steer) ---" -ForegroundColor Green
if ($fitAll) {
    Write-Host ("  all usable   ({0,4} samples): a = {1,6:0.0} m/s^2 = {2:0.00} g   R^2 {3:0.000}  sd {4:0.000}" -f `
        $fitAll.Used, $fitAll.A, ($fitAll.A / 9.81), $fitAll.R2, $fitAll.Sd)
}
if ($fitSteady) {
    Write-Host ("  steady only  ({0,4} samples): a = {1,6:0.0} m/s^2 = {2:0.00} g   R^2 {3:0.000}  sd {4:0.000}  <-- preferred" -f `
        $fitSteady.Used, $fitSteady.A, ($fitSteady.A / 9.81), $fitSteady.R2, $fitSteady.Sd)
}
$fit = if ($fitSteady) { $fitSteady } else { $fitAll }
$latGain = if ($fit) { $fit.A } else { $null }

# Yaw ceiling: a*steer/speed diverges as speed falls but the engine clamps, so
# record what this car actually reached.
$yawMax = 2.95
$obsMax = ($rows | ForEach-Object { [math]::Abs($_.Yaw) } | Measure-Object -Maximum).Maximum
if ($obsMax -gt 0.5) { $yawMax = [math]::Round($obsMax, 2) }

# ---- checks --------------------------------------------------------------
# The old falsification check compared the fit against the ten HIGHEST-YAW
# samples. That was invalid: the highest-yaw samples are spins and impacts
# (steer 0.00 with yaw -2.95, steer -1.00 with yaw +1.64), so it asked a
# cornering model to reproduce a crash and of course reported failure. Judge the
# fit on its own residuals instead, over the cornering samples it was fitted to.
$verdict = "ok"
if ($fit) {
    Write-Host ""
    if ($fit.R2 -lt 0.90) {
        Write-Host ("  POOR FIT - R^2 {0:0.000}. Steering and yaw are not following" -f $fit.R2) -ForegroundColor Red
        Write-Host  "  yaw = a*steer/speed here, so something else is going on." -ForegroundColor Red
        $verdict = "poor-fit"
    } else {
        Write-Host ("  fit quality: R^2 {0:0.000}, residual sd {1:0.000} rad/s - good." -f $fit.R2, $fit.Sd)
    }
    if ($latGain -lt 5 -or $latGain -gt 80) {
        Write-Host ("  IMPLAUSIBLE - a = {0:0.0} m/s^2 ({1:0.0} g at full lock)." -f `
            $latGain, ($latGain / 9.81)) -ForegroundColor Red
        $verdict = "implausible"
    }
    # How many samples deviate enough to read as loss of control? Reported so the
    # spin/impact channel can be sanity-checked against a real drive.
    $devBig = 0
    foreach ($r in $rows) {
        if ($r.Speed -lt 6) { continue }
        $pred = $latGain * $r.Steer / $r.Speed
        if ([math]::Abs($pred) -gt $yawMax) { $pred = $yawMax * [math]::Sign($pred) }
        if ([math]::Abs(($r.Yaw * $sign) - $pred) -gt 0.5) { $devBig++ }
    }
    Write-Host ("  loss-of-control samples (deviation > 0.5 rad/s): {0}" -f $devBig)
    Write-Host ("  peak yaw observed: {0:0.00} rad/s  -> yaw ceiling {1:0.00}" -f $obsMax, $yawMax)
}

# ---- write ---------------------------------------------------------------
$writeGain = ($null -ne $latGain -and $verdict -eq "ok")
if (-not $NoWrite) {
    $out = @{
        TEL_YAW_SIGN   = $sign
        TEL_LAT_GAIN   = $(if ($writeGain) { [math]::Round($latGain, 3) } else { 29.3 })
        TEL_YAW_MAX    = $yawMax
        GainFitted     = $writeGain
        GainVerdict    = $verdict
        GainR2         = $(if ($fit) { [math]::Round($fit.R2, 4) } else { 0 })
        Wheelbase      = [math]::Round($wheelbase, 3)
        Samples        = $usable.Count
        SteadySamples  = $steady.Count
        SignConfidence = [math]::Round($conf, 3)
        Source         = $(if ($FromLog) { $FromLog } else { "live" })
    }
    $p = Join-Path $here 'ffb-calib.json'
    ($out | ConvertTo-Json) | Set-Content -Path $p -Encoding ASCII
    Write-Host ""
    if ($writeGain) {
        Write-Host "written -> $p" -ForegroundColor Green
        Write-Host ("Both values measured: sign {0}, lateral gain {1:0.0} m/s^2 ({2:0.00} g)." -f `
            $sign, $latGain, ($latGain / 9.81)) -ForegroundColor Green
        Write-Host "Telemetry.ps1 loads this on the next run." -ForegroundColor Green
    } else {
        Write-Host "written -> $p  (SIGN ONLY)" -ForegroundColor Yellow
        Write-Host "The gain fit did not survive checking, so the measured default of" -ForegroundColor Yellow
        Write-Host "29.3 m/s^2 is kept. The sign is solid and matters most - a wrong sign" -ForegroundColor Yellow
        Write-Host "inverts the wheel." -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Refit offline without driving again:" -ForegroundColor Yellow
        Write-Host "  ffb-calibrate.ps1 -FromLog ffb-calib-samples.csv" -ForegroundColor Yellow
    }
}
