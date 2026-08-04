<#
  ffb-calib-test.ps1 - does the calibrator recover a model it is GIVEN?

  WHY THIS EXISTS, and the history is the whole point. Three wrong answers shipped
  before this file could catch them:

    1. MEDIAN OF PER-SAMPLE RATIOS for a single fixed lock -> 5.8 deg, reported
       confidently with a 100%-confidence sign beside it.
    2. REGRESSION THROUGH THE ORIGIN for a single fixed lock -> 6.2 deg. A better
       estimator behind the same wrong model. The estimator was blamed twice.
    3. LATERAL-G BRANCH ALONE -> R^2 = 0.9997, which looked like the answer. But
       that drive was 80-93 mph throughout, entirely above the regime crossover.
       On the next drive it produced 158 FALSE understeer samples.

  Mistake 3 is the one worth guarding hardest, because it PASSED every test that
  existed. Two lessons, both encoded below:

    * Synthetic tests built from the same assumption as the code cannot catch a
      wrong assumption. The previous generator used the model being tested, so its
      tests were green while the model was half wrong.
    * A high R^2 proves nothing if the data only covers part of the model's domain.
      Tests 3 and 4 feed single-regime drives and require the calibrator to REFUSE
      them, R^2 notwithstanding.

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

# Synthesise a drive from the MEASURED two-regime model, with a first-order lag so
# the transient bias that broke estimator 1 is present in the data.
function New-Drive {
    param([string]$Path, [double]$A, [scriptblock]$SteerFn, [scriptblock]$SpeedFn,
          [double]$Lock = 0.76, [double]$Tau = 0.35, [double]$Dur = 40.0,
          [double]$YawMax = 3.2)
    $lines = New-Object System.Collections.ArrayList
    $null = $lines.Add("t,speed,steer,yaw")
    $yaw = 0.0; $dt = 0.02
    for ($t = $dt; $t -lt $Dur; $t += $dt) {
        $steer = & $SteerFn $t
        $sp = & $SpeedFn $t
        $target = 0.0
        if ($sp -gt 0.5) {
            $aS  = [math]::Abs($steer)
            $kin = ($sp / 4.662) * [math]::Tan($aS * [math]::Abs($Lock))
            $lat = [math]::Abs($A) * $aS / $sp
            $mag = [math]::Min($kin, $lat)
            if ($mag -gt $YawMax) { $mag = $YawMax }
            # a negative A encodes an inverted-yaw car
            $sgn = if (($steer -lt 0) -ne ($A -lt 0)) { -1 } else { 1 }
            $target = $sgn * $mag
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
    $a = $null; $lock = $null; $sign = $null; $r2 = $null
    $rejected = $false; $thinCoverage = $false
    foreach ($ln in ($out -split "`r?`n")) {
        if ($ln -match 'steady only\s+\(\s*\d+\): a =\s*([\d.]+).*lock ([\d.]+) rad') {
            $a = [double]$Matches[1]; $lock = [double]$Matches[2]
        } elseif ($ln -match 'all usable\s+\(\s*\d+\): a =\s*([\d.]+).*lock ([\d.]+) rad' -and $null -eq $a) {
            $a = [double]$Matches[1]; $lock = [double]$Matches[2]
        }
        if ($ln -match 'TEL_YAW_SIGN = (-?\d+)') { $sign = [int]$Matches[1] }
        if ($ln -match 'R\^2\s+([\d.]+), residual') { $r2 = [double]$Matches[1] }
        if ($ln -match 'INSUFFICIENT COVERAGE') { $thinCoverage = $true; $rejected = $true }
        if ($ln -match 'POOR FIT|IMPLAUSIBLE|NOT ENOUGH') { $rejected = $true }
        if ($ln -match '\(SIGN ONLY\)') { $rejected = $true }
    }
    return [pscustomobject]@{
        A = $a; Lock = $lock; Sign = $sign; R2 = $r2
        Rejected = $rejected; ThinCoverage = $thinCoverage; Raw = $out
    }
}

$sustained = { param($t) @(0.0, 0.6, 0.0, -0.6)[[int]($t / 2.5) % 4] }
$sinus     = { param($t) 0.6 * [math]::Sin($t * 0.9) }
# Sweeps 5..30 m/s, so it crosses the 12 m/s regime boundary in both directions.
$bothRegimes = { param($t) 5.0 + 25.0 * (0.5 + 0.5 * [math]::Sin($t * 0.22)) }
$fastOnly    = { param($t) 38.0 + 3.0 * [math]::Sin($t * 0.3) }
$slowOnly    = { param($t) 6.0 + 2.0 * [math]::Sin($t * 0.3) }

Write-Host "`n=== 1. both regimes covered: a = 31.0, lock = 0.76 (43.5 deg) ===" -ForegroundColor Cyan
$p = Join-Path $tmp 'both.csv'
New-Drive -Path $p -A 31.0 -Lock 0.76 -SteerFn $sustained -SpeedFn $bothRegimes
$f = Get-Fit $p
Check "recovers a gain and a lock" ($null -ne $f.A -and $null -ne $f.Lock) "a=$($f.A) lock=$($f.Lock)"
if ($f.A)    { Check "a within 10% of 31.0"    ([math]::Abs($f.A - 31.0) -lt 3.1)      ("got {0:0.0}" -f $f.A) }
if ($f.Lock) { Check "lock within 15% of 0.76" ([math]::Abs($f.Lock - 0.76) -lt 0.115) ("got {0:0.000}" -f $f.Lock) }
if ($f.Lock) { Check "lock is NOT the old broken ~0.10" ($f.Lock -gt 0.25) ("got {0:0.000}" -f $f.Lock) }
Check "sign is +1" ($f.Sign -eq 1) "got $($f.Sign)"
Check "accepted" (-not $f.Rejected) ""

Write-Host "`n=== 2. sinusoidal steering - all transition ===" -ForegroundColor Cyan
$p = Join-Path $tmp 'sinus.csv'
New-Drive -Path $p -A 31.0 -Lock 0.76 -SteerFn $sinus -SpeedFn $bothRegimes
$f = Get-Fit $p
Check "a still within 15%"    ($f.A -and [math]::Abs($f.A - 31.0) -lt 4.7)       ("got {0:0.0}" -f $f.A)
Check "lock still within 20%" ($f.Lock -and [math]::Abs($f.Lock - 0.76) -lt 0.16) ("got {0:0.000}" -f $f.Lock)

Write-Host "`n=== 3. HIGH-SPEED-ONLY drive must be REFUSED ===" -ForegroundColor Cyan
# THE test. This is mistake 3 exactly: only the lateral-g branch is constrained,
# so the lock is a guess - and R^2 will look excellent regardless. A calibrator
# that accepts this is the one that produced 158 false understeer samples.
$p = Join-Path $tmp 'fast.csv'
New-Drive -Path $p -A 31.0 -Lock 0.76 -SteerFn $sustained -SpeedFn $fastOnly
$f = Get-Fit $p
Check "flagged as insufficient regime coverage" $f.ThinCoverage "R2=$($f.R2) a=$($f.A) lock=$($f.Lock)"
Check "high R^2 did NOT buy acceptance" ($f.Rejected) "R2=$($f.R2) rejected=$($f.Rejected)"

Write-Host "`n=== 4. LOW-SPEED-ONLY drive must also be REFUSED ===" -ForegroundColor Cyan
# The mirror image: only the geometry branch is constrained, so `a` is a guess.
$p = Join-Path $tmp 'slow.csv'
New-Drive -Path $p -A 31.0 -Lock 0.76 -SteerFn $sustained -SpeedFn $slowOnly
$f = Get-Fit $p
Check "flagged as insufficient regime coverage" $f.ThinCoverage "R2=$($f.R2) a=$($f.A) lock=$($f.Lock)"

Write-Host "`n=== 5. different parameters are tracked, not echoed ===" -ForegroundColor Cyan
# Guards against a fit that always returns something near the defaults.
$p = Join-Path $tmp 'other.csv'
New-Drive -Path $p -A 22.0 -Lock 0.50 -SteerFn $sustained -SpeedFn $bothRegimes
$f = Get-Fit $p
Check "tracks a = 22.0"   ($f.A -and [math]::Abs($f.A - 22.0) -lt 3.0)        ("got {0:0.0}" -f $f.A)
Check "tracks lock = 0.50" ($f.Lock -and [math]::Abs($f.Lock - 0.50) -lt 0.12) ("got {0:0.000}" -f $f.Lock)

Write-Host "`n=== 6. inverted yaw is detected ===" -ForegroundColor Cyan
$p = Join-Path $tmp 'inv.csv'
New-Drive -Path $p -A -31.0 -Lock 0.76 -SteerFn $sustained -SpeedFn $bothRegimes
$f = Get-Fit $p
Check "sign is -1" ($f.Sign -eq -1) "got $($f.Sign)"

Write-Host "`n=== 7. a no-information drive is REFUSED ===" -ForegroundColor Cyan
$p = Join-Path $tmp 'useless.csv'
New-Drive -Path $p -A 31.0 -SteerFn { param($t) 0.02 * [math]::Sin($t) } -SpeedFn { param($t) 2.0 }
$f = Get-Fit $p
Check "refuses a crawl with the wheel centred" $f.Rejected "a=$($f.A)"

Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
Write-Host ""
Write-Host ("=== {0} passed, {1} failed ===" -f $pass, $fail) `
    -ForegroundColor $(if ($fail -eq 0) { 'Green' } else { 'Red' })
if ($fail -gt 0) { exit 1 }
