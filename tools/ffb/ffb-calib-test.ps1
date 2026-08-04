<#
  ffb-calib-test.ps1 - does the calibrator recover a gain it is GIVEN?

  WHY THIS EXISTS, and the history is the point:

  Version 1 fitted a steering lock by taking the MEDIAN of per-sample ratios and
  reported 5.8 deg from a real drive, confidently, with a 100%-confidence sign
  beside it. Version 2 replaced the estimator with a regression through the origin,
  validated it against synthetic drives, and returned 6.2 deg from the next real
  drive. The estimator was never the problem.

  The problem was the MODEL. I'76 has no tyre model - lateral acceleration is
  exactly proportional to steering input and independent of speed
  (latAccel = a * steer, R^2 = 0.9995). Fitting a fixed steering lock to a
  constant-lateral-g car yields an answer that falls with speed and settles
  wherever the drive spent its time. Both "bad fits" were the arithmetic faithfully
  reporting that a wrong model does not fit.

  The lesson worth encoding: synthetic tests built from the SAME assumption as the
  code cannot catch a wrong assumption. Version 2's tests passed while the model
  was wrong, because the test generator used the kinematic model too. So this file
  now generates from the MEASURED relation, and test 5 deliberately feeds
  kinematic-model data to confirm the fit REJECTS it rather than silently fitting.

      tools\ffb\ffb-calib-test.ps1
#>
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$tmp  = Join-Path $env:TEMP ("i76calib_" + [System.Guid]::NewGuid().ToString("N").Substring(0, 8))
New-Item -ItemType Directory -Path $tmp -Force | Out-Null

$pass = 0; $fail = 0
function Check {
    param([string]$Name, [bool]$Cond, [string]$Detail = "")
    if ($Cond) { $script:pass++; Write-Host ("  PASS  " + $Name) -ForegroundColor Green }
    else { $script:fail++; Write-Host ("  FAIL  " + $Name + $(if ($Detail) { "  ($Detail)" } else { "" })) -ForegroundColor Red }
}

# Synthesise a drive from the MEASURED handling model: yaw = a*steer/speed,
# clamped, with a first-order lag so the transient bias that broke the original
# per-sample estimator is present in the data.
function New-Drive {
    param([string]$Path, [double]$A, [scriptblock]$SteerFn, [scriptblock]$SpeedFn,
          [double]$Tau = 0.35, [double]$Dur = 30.0, [double]$YawMax = 2.95,
          [switch]$Kinematic)
    $lines = New-Object System.Collections.ArrayList
    $null = $lines.Add("t,speed,steer,yaw")
    $yaw = 0.0; $dt = 0.02
    for ($t = $dt; $t -lt $Dur; $t += $dt) {
        $steer = & $SteerFn $t
        $sp = & $SpeedFn $t
        if ($Kinematic) {
            # the WRONG model, on purpose (see test 5): yaw rises with speed
            $target = ($sp / 4.662) * [math]::Tan($steer * 0.52)
        } else {
            $target = if ($sp -gt 0.5) { $A * $steer / $sp } else { 0.0 }
            if ($target -gt $YawMax) { $target = $YawMax }
            elseif ($target -lt -$YawMax) { $target = -$YawMax }
        }
        $yaw += ($target - $yaw) * ($dt / $Tau)
        $null = $lines.Add(("{0:0.000},{1:0.000},{2:0.000},{3:0.0000}" -f $t, $sp, $steer, $yaw))
    }
    $lines | Set-Content -Path $Path -Encoding ASCII
}

function Get-Fit {
    param([string]$Csv)
    $out = & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $here 'ffb-calibrate.ps1') `
        -FromLog $Csv -NoWrite 2>&1 | Out-String
    $a = $null; $sign = $null; $r2 = $null; $rejected = $false
    foreach ($ln in ($out -split "`r?`n")) {
        if ($ln -match 'steady only\s+\(\s*\d+ samples\): a =\s*([\d.]+)') { $a = [double]$Matches[1] }
        elseif ($ln -match 'all usable\s+\(\s*\d+ samples\): a =\s*([\d.]+)' -and $null -eq $a) { $a = [double]$Matches[1] }
        if ($ln -match 'TEL_YAW_SIGN = (-?\d+)') { $sign = [int]$Matches[1] }
        if ($ln -match 'R\^2\s+([\d.]+), residual') { $r2 = [double]$Matches[1] }
        if ($ln -match 'POOR FIT|IMPLAUSIBLE|NOT ENOUGH') { $rejected = $true }
    }
    return [pscustomobject]@{ A = $a; Sign = $sign; R2 = $r2; Rejected = $rejected; Raw = $out }
}

$sustained = { param($t) @(0.0, 0.55, 0.0, -0.55)[[int]($t / 3.0) % 4] }
$sinus     = { param($t) 0.55 * [math]::Sin($t * 0.9) }
$midSpeed  = { param($t) 16.0 + 3.0 * [math]::Sin($t * 0.25) }
# The real drive was 80-93 mph almost throughout, which is what made a
# speed-dependent model unidentifiable. Keep a case like it.
$fastSpeed = { param($t) 39.0 + 2.0 * [math]::Sin($t * 0.3) }
$wideSpeed = { param($t) 8.0 + 16.0 * (0.5 + 0.5 * [math]::Sin($t * 0.2)) }

Write-Host "`n=== 1. sustained turns, a = 29.3 (2.99 g) ===" -ForegroundColor Cyan
$p = Join-Path $tmp 'sustained.csv'
New-Drive -Path $p -A 29.3 -SteerFn $sustained -SpeedFn $midSpeed
$f = Get-Fit $p
Check "recovers a gain" ($null -ne $f.A) "got '$($f.A)'"
if ($f.A) { Check "within 10% of 29.3" ([math]::Abs($f.A - 29.3) -lt 2.9) ("got {0:0.0}" -f $f.A) }
Check "sign is +1" ($f.Sign -eq 1) "got $($f.Sign)"
Check "reports a good R^2" ($f.R2 -ge 0.90) "R2 $($f.R2)"
Check "not rejected" (-not $f.Rejected) ""

Write-Host "`n=== 2. sinusoidal steering - all transition ===" -ForegroundColor Cyan
$p = Join-Path $tmp 'sinus.csv'
New-Drive -Path $p -A 29.3 -SteerFn $sinus -SpeedFn $midSpeed
$f = Get-Fit $p
Check "still within 10%" ($f.A -and [math]::Abs($f.A - 29.3) -lt 2.9) ("got {0:0.0}" -f $f.A)

Write-Host "`n=== 3. HIGH speed only - the case that defeated the old model ===" -ForegroundColor Cyan
# A single-lock model fitted to this returned ~6 deg. A lateral-gain model has no
# speed-dependent parameter to lose, so it must recover the same answer here.
$p = Join-Path $tmp 'fast.csv'
New-Drive -Path $p -A 29.3 -SteerFn $sustained -SpeedFn $fastSpeed
$f = Get-Fit $p
Check "recovers the SAME gain at 87 mph" ($f.A -and [math]::Abs($f.A - 29.3) -lt 2.9) ("got {0:0.0}" -f $f.A)

Write-Host "`n=== 4. a different gain is tracked, not echoed ===" -ForegroundColor Cyan
$p = Join-Path $tmp 'soft.csv'
New-Drive -Path $p -A 15.0 -SteerFn $sustained -SpeedFn $wideSpeed
$f = Get-Fit $p
Check "tracks a = 15.0" ($f.A -and [math]::Abs($f.A - 15.0) -lt 1.5) ("got {0:0.0}" -f $f.A)

Write-Host "`n=== 5. KINEMATIC data is REJECTED, not fitted ===" -ForegroundColor Cyan
# The guard against the mistake that actually happened. If the engine did follow a
# fixed steering lock, yaw would RISE with speed and the lateral-gain model would
# not describe it - the fit must say so rather than return a confident number.
# Version 2's tests generated kinematic data and asserted a kinematic fit, which
# is why they passed while the model was wrong.
$p = Join-Path $tmp 'kinematic.csv'
New-Drive -Path $p -A 29.3 -SteerFn $sustained -SpeedFn $wideSpeed -Kinematic
$f = Get-Fit $p
Check "rejects data from a different handling model" ($f.Rejected -or ($f.R2 -lt 0.90)) `
    ("R2 $($f.R2), a $($f.A), rejected $($f.Rejected)")

Write-Host "`n=== 6. inverted yaw is detected ===" -ForegroundColor Cyan
$p = Join-Path $tmp 'inv.csv'
New-Drive -Path $p -A -29.3 -SteerFn $sustained -SpeedFn $midSpeed
$f = Get-Fit $p
Check "sign is -1" ($f.Sign -eq -1) "got $($f.Sign)"

Write-Host "`n=== 7. a no-information drive is REJECTED ===" -ForegroundColor Cyan
$p = Join-Path $tmp 'useless.csv'
New-Drive -Path $p -A 29.3 -SteerFn { param($t) 0.02 * [math]::Sin($t) } -SpeedFn { param($t) 2.0 }
$f = Get-Fit $p
Check "refuses to fit a crawl with the wheel centred" $f.Rejected "a=$($f.A)"

Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
Write-Host ""
Write-Host ("=== {0} passed, {1} failed ===" -f $pass, $fail) `
    -ForegroundColor $(if ($fail -eq 0) { 'Green' } else { 'Red' })
if ($fail -gt 0) { exit 1 }
