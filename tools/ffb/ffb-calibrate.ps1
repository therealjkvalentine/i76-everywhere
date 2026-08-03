<#
  ffb-calibrate.ps1 - measure the two things the force model was guessing.

  Telemetry.ps1 carries exactly two values that are assumptions rather than
  measurements, and both matter:

    TEL_YAW_SIGN   Does a positive steer input produce a positive yaw rate at
                   +0xCC? Nothing in the struct says. Get it wrong and the
                   cornering channel pushes the wrong way - the wheel helps you
                   turn INTO the corner instead of resisting, which is both
                   wrong and unsafe-feeling.

    TEL_STEER_LOCK Radians of road-wheel angle at full lock. The engine stores
                   steer as -1..1 with no stated mapping. This scales the
                   bicycle-model yaw prediction, so it sets how readily
                   understeer and oversteer trigger. 0.52 rad (30 deg) was a
                   plausible road-car default, nothing more.

  Both fall out of one short drive, so measure them instead of guessing.

  ---------------------------------------------------------------------------
  USE
  ---------------------------------------------------------------------------
      # live: drive for 30 s while this watches
      tools\ffb\ffb-calibrate.ps1

      # offline: reuse a drive already captured by the interposer
      tools\ffb\ffb-interposer.ps1 -DryRun -Log drive.csv     (drive, then Ctrl+C)
      tools\ffb\ffb-calibrate.ps1 -FromLog drive.csv

  Writes ffb-calib.json next to this script. Telemetry.ps1 picks it up on the
  next Tel-Open, so nothing needs editing by hand.

  DRIVE LIKE THIS: get above ~20 mph and make several sustained, smooth turns in
  BOTH directions. Sustained matters - the bicycle model describes steady-state
  cornering, and a flick of the wheel measures the car's transient response
  instead, which fits a lock angle that is too small.

  ---------------------------------------------------------------------------
  HOW
  ---------------------------------------------------------------------------
  Sign: correlate steer against observed yaw rate over every usable sample. If
  they agree in sign more often than not, +1; otherwise -1. This is robust - it
  needs no model, only that turning the wheel one way rotates the car one way.

  Lock: rearrange the bicycle model. From
        yawRate = (speed / wheelbase) * tan(steer * lock)
  we get
        lock = atan(yawRate * wheelbase / speed) / steer
  Evaluate per sample and take the MEDIAN, not the mean: samples taken while the
  tyres are sliding fit a smaller lock and would drag an average down, whereas
  they cannot move a median far as long as most of the drive had grip.
#>
param(
    [int]$Seconds = 30,
    [string]$FromLog = "",
    # Fit and report but do NOT write ffb-calib.json. A plain switch rather than
    # an -Apply that defaults true: a switch whose default is $true can only be
    # turned off as -Apply:$false, which does not survive being passed through
    # another shell, and quietly writing a calibration you asked it not to write
    # is a bad failure - especially when the input was synthetic test data.
    [switch]$NoWrite
)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

# Samples usable for fitting. Both thresholds exclude regimes where the model
# says nothing: below ~8 m/s the yaw rate is dominated by scrub and steering
# geometry rather than by speed, and near-centre steering divides by ~0.
$MIN_SPEED = 8.0
$MIN_STEER = 0.15

$rows = @()
# Interposer logs do not carry the geometry, so offline fits use the stock value
# measured from the wheel contact points. Live runs read it from the entity.
$wheelbase = 4.662

if ($FromLog) {
    if (-not (Test-Path $FromLog)) { Write-Host "no such log: $FromLog" -ForegroundColor Red; exit 1 }
    Write-Host "reading $FromLog ..." -ForegroundColor Cyan
    foreach ($r in (Import-Csv $FromLog)) {
        $rows += [pscustomobject]@{
            Speed = [double]$r.speed; Steer = [double]$r.steer; Yaw = [double]$r.yaw
        }
    }
    Write-Host "  $($rows.Count) samples" -ForegroundColor Cyan
} else {
    . (Join-Path $here 'Telemetry.ps1')
    $ctx = Tel-Open
    Write-Host ("telemetry OK - entity 0x{0:X8}, wheelbase {1:0.00} m" -f $ctx.Ent, $ctx.Wheelbase) -ForegroundColor Green
    Write-Host ""
    Write-Host "DRIVE NOW for $Seconds s." -ForegroundColor Yellow
    Write-Host "Get above 20 mph and make several SUSTAINED turns, both directions." -ForegroundColor Yellow
    Write-Host ""
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $lastNote = 0
    while ($sw.Elapsed.TotalSeconds -lt $Seconds) {
        $s = Tel-Sample $ctx
        if ($s) {
            $rows += [pscustomobject]@{ Speed = $s.Speed; Steer = $s.Steer; Yaw = $s.YawRate }
            $el = [int]$sw.Elapsed.TotalSeconds
            if ($el -ne $lastNote) {
                $lastNote = $el
                $usable = ($rows | Where-Object { $_.Speed -gt $MIN_SPEED -and [math]::Abs($_.Steer) -gt $MIN_STEER }).Count
                Write-Host ("`r  {0,3}s   {1,5:0.0} mph   steer {2,6:0.00}   yaw {3,7:0.000}   usable {4,4}" -f `
                    ($Seconds - $el), $s.SpeedMph, $s.Steer, $s.YawRate, $usable) -NoNewline
            }
        }
        Start-Sleep -Milliseconds 20
    }
    Write-Host ""
    $wheelbase = $ctx.Wheelbase
    Tel-Close $ctx
}

# ---- filter ---------------------------------------------------------------
$use = @($rows | Where-Object { $_.Speed -gt $MIN_SPEED -and [math]::Abs($_.Steer) -gt $MIN_STEER `
                               -and [math]::Abs($_.Yaw) -gt 0.02 })
Write-Host ""
Write-Host ("usable samples: {0} of {1}" -f $use.Count, $rows.Count) -ForegroundColor Cyan
if ($use.Count -lt 25) {
    Write-Host ""
    Write-Host "NOT ENOUGH DATA - nothing written." -ForegroundColor Red
    Write-Host "Need 25+ samples above $MIN_SPEED m/s (18 mph) with the wheel turned" -ForegroundColor Yellow
    Write-Host "past $MIN_STEER. Drive faster, turn more, and hold the turns." -ForegroundColor Yellow
    exit 1
}

# ---- sign ----------------------------------------------------------------
$agree = 0; $disagree = 0
foreach ($r in $use) {
    if ([math]::Sign($r.Steer) -eq [math]::Sign($r.Yaw)) { $agree++ } else { $disagree++ }
}
$sign = if ($agree -ge $disagree) { 1 } else { -1 }
$conf = [math]::Max($agree, $disagree) / [double]$use.Count
Write-Host ""
Write-Host "--- yaw sign ---" -ForegroundColor Green
Write-Host ("  steer and yaw agree in {0} samples, disagree in {1}" -f $agree, $disagree)
Write-Host ("  TEL_YAW_SIGN = {0}   (confidence {1:0}%)" -f $sign, ($conf * 100))
if ($conf -lt 0.8) {
    Write-Host "  LOW CONFIDENCE - the drive probably mixed sustained turns with" -ForegroundColor Yellow
    Write-Host "  counter-steering or sliding. Re-run with smoother turns." -ForegroundColor Yellow
}

# ---- steer lock ----------------------------------------------------------
$locks = @()
foreach ($r in $use) {
    $y = $r.Yaw * $sign
    # Only same-signed pairs can fit a positive lock; opposite-signed samples are
    # the car rotating against the steering (a slide), which this model does not
    # describe.
    if ([math]::Sign($y) -ne [math]::Sign($r.Steer)) { continue }
    $arg = $y * $wheelbase / $r.Speed
    if ([math]::Abs($arg) -ge 1.5) { continue }        # atan domain sanity
    $l = [math]::Atan($arg) / $r.Steer
    if ($l -gt 0.02 -and $l -lt 1.4) { $locks += $l }  # 1..80 deg
}
if ($locks.Count -lt 15) {
    Write-Host ""
    Write-Host "Could not fit a steering lock ($($locks.Count) valid samples)." -ForegroundColor Yellow
    Write-Host "Sign result above is still good. Keeping the existing lock." -ForegroundColor Yellow
    $lock = $null
} else {
    $sorted = $locks | Sort-Object
    $lock = $sorted[[int]($sorted.Count / 2)]
    $p25 = $sorted[[int]($sorted.Count * 0.25)]
    $p75 = $sorted[[int]($sorted.Count * 0.75)]
    Write-Host ""
    Write-Host "--- steering lock ---" -ForegroundColor Green
    Write-Host ("  {0} fitted samples" -f $locks.Count)
    Write-Host ("  median {0:0.000} rad = {1:0.0} deg   (quartiles {2:0.0}..{3:0.0} deg)" -f `
        $lock, ($lock * 180 / [math]::PI), ($p25 * 180 / [math]::PI), ($p75 * 180 / [math]::PI))
    $spread = ($p75 - $p25) / [math]::Max(0.001, $lock)
    if ($spread -gt 0.6) {
        Write-Host "  WIDE SPREAD - a lot of the drive was sliding, or the turns were" -ForegroundColor Yellow
        Write-Host "  brief. The median is still the best estimate available." -ForegroundColor Yellow
    }
}

# ---- write --------------------------------------------------------------
if (-not $NoWrite) {
    $out = @{
        TEL_YAW_SIGN   = $sign
        TEL_STEER_LOCK = $(if ($lock) { [math]::Round($lock, 4) } else { 0.52 })
        Wheelbase      = [math]::Round($wheelbase, 3)
        Samples        = $use.Count
        SignConfidence = [math]::Round($conf, 3)
        Source         = $(if ($FromLog) { $FromLog } else { "live" })
    }
    $p = Join-Path $here 'ffb-calib.json'
    ($out | ConvertTo-Json) | Set-Content -Path $p -Encoding ASCII
    Write-Host ""
    Write-Host "written -> $p" -ForegroundColor Green
    Write-Host "Telemetry.ps1 loads this automatically on the next run." -ForegroundColor Green
}
