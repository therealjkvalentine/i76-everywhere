<#
  ffb-calib-test.ps1 - does the calibrator recover a lock it is GIVEN?

  WHY THIS EXISTS: the first version of ffb-calibrate.ps1 reported 5.8 degrees of
  steering lock from a real drive, confidently, with a 100%-confidence sign
  alongside it. The true value is ~20-30. Nothing in the output said it was wrong -
  it took noticing that a 0.101 rad lock cannot produce the 1.6 rad/s yaw the car
  had already been observed to reach.

  A fitting routine that cannot be checked against a known answer will do that to
  you again. So: synthesise drives from a KNOWN lock, including the first-order
  yaw lag that caused the original error, and assert the fit comes back.

      tools\ffb\ffb-calib-test.ps1
#>
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$tmp  = Join-Path $env:TEMP ("i76calib_" + [System.Guid]::NewGuid().ToString("N").Substring(0, 8))
New-Item -ItemType Directory -Path $tmp -Force | Out-Null

$WB = 4.662
$pass = 0; $fail = 0
function Check {
    param([string]$Name, [bool]$Cond, [string]$Detail = "")
    if ($Cond) { $script:pass++; Write-Host ("  PASS  " + $Name) -ForegroundColor Green }
    else { $script:fail++; Write-Host ("  FAIL  " + $Name + $(if ($Detail) { "  ($Detail)" } else { "" })) -ForegroundColor Red }
}

# Synthesise a drive. The first-order lag on yaw is the whole point: it is what
# biases a per-sample lock estimate downward, because mid-transition the steer is
# already large while the yaw is still building.
function New-Drive {
    param([string]$Path, [double]$Lock, [scriptblock]$SteerFn,
          [double]$Speed = 16.0, [double]$Tau = 0.35, [double]$Dur = 30.0)
    $lines = New-Object System.Collections.ArrayList
    $null = $lines.Add("t,speed,steer,yaw")
    $yaw = 0.0; $dt = 0.02
    for ($t = $dt; $t -lt $Dur; $t += $dt) {
        $steer = & $SteerFn $t
        $sp = $Speed + 3.0 * [math]::Sin($t * 0.25)
        $target = ($sp / $WB) * [math]::Tan($steer * $Lock)
        $yaw += ($target - $yaw) * ($dt / $Tau)
        $null = $lines.Add(("{0:0.000},{1:0.000},{2:0.000},{3:0.0000}" -f $t, $sp, $steer, $yaw))
    }
    $lines | Set-Content -Path $Path -Encoding ASCII
}

# Run the real script and scrape the preferred fit out of its output. An
# integration test on purpose - it exercises the path the user actually runs.
function Get-Fit {
    param([string]$Csv)
    $out = & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $here 'ffb-calibrate.ps1') `
        -FromLog $Csv -NoWrite 2>&1 | Out-String
    $lock = $null; $sign = $null; $ratio = $null; $rejected = $false
    foreach ($ln in ($out -split "`r?`n")) {
        if ($ln -match 'steady only\s+\(\s*\d+ samples\):\s+([\d.]+) rad') { $lock = [double]$Matches[1] }
        elseif ($ln -match 'all usable\s+\(\s*\d+ samples\):\s+([\d.]+) rad' -and $null -eq $lock) { $lock = [double]$Matches[1] }
        if ($ln -match 'TEL_YAW_SIGN = (-?\d+)') { $sign = [int]$Matches[1] }
        if ($ln -match 'predicts (\d+)% of') { $ratio = [int]$Matches[1] }
        if ($ln -match 'FAILS|IMPLAUSIBLE|NOT ENOUGH') { $rejected = $true }
    }
    return [pscustomobject]@{ Lock = $lock; Sign = $sign; Ratio = $ratio; Rejected = $rejected; Raw = $out }
}

Write-Host "`n=== 1. sustained turns, lock 0.40 rad (22.9 deg) ===" -ForegroundColor Cyan
$p = Join-Path $tmp 'sustained.csv'
New-Drive -Path $p -Lock 0.40 -SteerFn {
    param($t) @(0.0, 0.55, 0.0, -0.55)[[int]($t / 3.0) % 4] }
$f = Get-Fit $p
Check "recovers a lock" ($null -ne $f.Lock) "got '$($f.Lock)'"
if ($f.Lock) {
    Check "within 20% of ground truth 0.40" ([math]::Abs($f.Lock - 0.40) -lt 0.08) ("got {0:0.000}" -f $f.Lock)
    # The specific failure that shipped: 0.101 rad. Guard the magnitude directly.
    Check "NOT the old broken magnitude (~0.10)" ($f.Lock -gt 0.20) ("got {0:0.000}" -f $f.Lock)
}
Check "sign is +1" ($f.Sign -eq 1) "got $($f.Sign)"
Check "falsification check passes" ($f.Ratio -ge 45) "ratio $($f.Ratio)%"
Check "not rejected" (-not $f.Rejected) ""

Write-Host "`n=== 2. sinusoidal steering - ALL transition, the case that broke it ===" -ForegroundColor Cyan
$p = Join-Path $tmp 'sinus.csv'
New-Drive -Path $p -Lock 0.40 -SteerFn { param($t) 0.55 * [math]::Sin($t * 0.9) }
$f = Get-Fit $p
Check "still recovers within 20%" ($f.Lock -and [math]::Abs($f.Lock - 0.40) -lt 0.08) ("got {0:0.000}" -f $f.Lock)
Check "NOT the old broken magnitude" ($f.Lock -gt 0.20) ("got {0:0.000}" -f $f.Lock)

Write-Host "`n=== 3. a genuinely different lock (0.60 rad) is not just echoed ===" -ForegroundColor Cyan
# Guards against a fit that always returns something near the default.
$p = Join-Path $tmp 'wide.csv'
New-Drive -Path $p -Lock 0.60 -SteerFn {
    param($t) @(0.0, 0.5, 0.0, -0.5)[[int]($t / 3.0) % 4] }
$f = Get-Fit $p
Check "tracks a wider lock" ($f.Lock -and [math]::Abs($f.Lock - 0.60) -lt 0.12) ("got {0:0.000}" -f $f.Lock)

Write-Host "`n=== 4. inverted yaw is detected ===" -ForegroundColor Cyan
$p = Join-Path $tmp 'inv.csv'
New-Drive -Path $p -Lock -0.40 -SteerFn {
    param($t) @(0.0, 0.55, 0.0, -0.55)[[int]($t / 3.0) % 4] }
$f = Get-Fit $p
Check "sign is -1" ($f.Sign -eq -1) "got $($f.Sign)"

Write-Host "`n=== 5. a useless drive is REJECTED, not fitted ===" -ForegroundColor Cyan
# Crawling with the wheel barely off centre carries no information. The old
# version would happily fit it and write the result.
$p = Join-Path $tmp 'useless.csv'
New-Drive -Path $p -Lock 0.40 -Speed 2.0 -SteerFn { param($t) 0.02 * [math]::Sin($t) }
$f = Get-Fit $p
Check "refuses to fit a no-information drive" $f.Rejected "lock=$($f.Lock)"

Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
Write-Host ""
Write-Host ("=== {0} passed, {1} failed ===" -f $pass, $fail) `
    -ForegroundColor $(if ($fail -eq 0) { 'Green' } else { 'Red' })
if ($fail -gt 0) { exit 1 }
