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

# ---- lock: regression through the origin --------------------------------
function Fit-Lock {
    param($Set, [int]$Sign, [double]$WB)
    $sxy = 0.0; $sxx = 0.0; $used = 0
    foreach ($r in $Set) {
        $y = $r.Yaw * $Sign
        if ([math]::Sign($y) -ne [math]::Sign($r.Steer)) { continue }   # sliding; model silent
        $arg = $y * $WB / $r.Speed
        if ([math]::Abs($arg) -ge 1.5) { continue }
        $theta = [math]::Atan($arg)
        $sxy += $r.Steer * $theta
        $sxx += $r.Steer * $r.Steer
        $used++
    }
    if ($sxx -le 0 -or $used -lt 10) { return $null }
    return [pscustomobject]@{ Lock = ($sxy / $sxx); Used = $used }
}

$steady = @($usable | Where-Object {
    [math]::Abs($_.dSteer) -lt $STEADY_STEER -and [math]::Abs($_.dYaw) -lt $STEADY_YAW })

$fitAll    = Fit-Lock $usable $sign $wheelbase
$fitSteady = Fit-Lock $steady $sign $wheelbase

Write-Host ""
Write-Host "--- steering lock ---" -ForegroundColor Green
if ($fitAll) {
    Write-Host ("  all usable   ({0,4} samples): {1:0.000} rad = {2,5:0.0} deg" -f `
        $fitAll.Used, $fitAll.Lock, ($fitAll.Lock * 180 / [math]::PI))
}
if ($fitSteady) {
    Write-Host ("  steady only  ({0,4} samples): {1:0.000} rad = {2,5:0.0} deg   <-- preferred" -f `
        $fitSteady.Used, $fitSteady.Lock, ($fitSteady.Lock * 180 / [math]::PI))
} else {
    Write-Host ("  steady only: too few samples ({0}) - the drive was all transitions." -f $steady.Count) -ForegroundColor Yellow
}

$fit = if ($fitSteady) { $fitSteady } else { $fitAll }
$lock = if ($fit) { $fit.Lock } else { $null }

# ---- falsification: reproduce the biggest observed yaw rates ------------
# Independent of knowing the right answer: whatever the lock is, the model built
# from it has to be able to produce the yaw rates the car demonstrably reached.
$verdict = "ok"
if ($lock) {
    $top = @($usable | Sort-Object { -[math]::Abs($_.Yaw) } | Select-Object -First 10)
    $obs = 0.0; $pred = 0.0
    foreach ($r in $top) {
        $obs  += [math]::Abs($r.Yaw)
        $pred += [math]::Abs(($r.Speed / $wheelbase) * [math]::Tan($r.Steer * $lock))
    }
    $ratio = if ($obs -gt 0) { $pred / $obs } else { 0 }
    Write-Host ""
    Write-Host ("  check: at the 10 highest-yaw samples the fitted model predicts {0:0}% of" -f ($ratio * 100))
    Write-Host  "         the yaw actually observed."
    if ($ratio -lt 0.45) {
        Write-Host "  FAILS - a lock this small cannot produce the yaw rates this car reached." -ForegroundColor Red
        $verdict = "failed-falsification"
    }
}
if ($lock -and ($lock -lt $LOCK_MIN -or $lock -gt $LOCK_MAX)) {
    Write-Host ("  IMPLAUSIBLE - {0:0.0} deg is outside the 10-45 deg range road cars use." -f `
        ($lock * 180 / [math]::PI)) -ForegroundColor Red
    $verdict = "implausible"
}

# ---- write ---------------------------------------------------------------
$writeLock = ($lock -ne $null -and $verdict -eq "ok")
if (-not $NoWrite) {
    $out = @{
        TEL_YAW_SIGN   = $sign
        TEL_STEER_LOCK = $(if ($writeLock) { [math]::Round($lock, 4) } else { 0.52 })
        LockFitted     = $writeLock
        LockVerdict    = $verdict
        Wheelbase      = [math]::Round($wheelbase, 3)
        Samples        = $usable.Count
        SteadySamples  = $steady.Count
        SignConfidence = [math]::Round($conf, 3)
        Source         = $(if ($FromLog) { $FromLog } else { "live" })
    }
    $p = Join-Path $here 'ffb-calib.json'
    ($out | ConvertTo-Json) | Set-Content -Path $p -Encoding ASCII
    Write-Host ""
    if ($writeLock) {
        Write-Host "written -> $p" -ForegroundColor Green
        Write-Host "Both values measured. Telemetry.ps1 loads this on the next run." -ForegroundColor Green
    } else {
        Write-Host "written -> $p  (SIGN ONLY)" -ForegroundColor Yellow
        Write-Host "The lock fit did not survive checking, so the default 0.52 rad (30 deg)" -ForegroundColor Yellow
        Write-Host "is kept rather than a number that is demonstrably wrong. The sign is" -ForegroundColor Yellow
        Write-Host "solid and is what matters most - a wrong sign inverts the wheel." -ForegroundColor Yellow
        Write-Host ""
        Write-Host "To improve the lock fit: hold each turn for a second or more at a" -ForegroundColor Yellow
        Write-Host "steady angle. Then refit without driving again:" -ForegroundColor Yellow
        Write-Host "  ffb-calibrate.ps1 -FromLog ffb-calib-samples.csv" -ForegroundColor Yellow
    }
}
