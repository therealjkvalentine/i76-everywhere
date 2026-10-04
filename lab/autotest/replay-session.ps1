<#
  replay-session.ps1 — reproduce a recorded session, optionally at a different frame rate.

  Runs the SAME state setup the recording started from (read out of the .meta.txt), then replays
  your input. Because both runs begin at the identical scripted state, the inputs land on the
  same screen / same spawn - that is the whole sync mechanism.

  For a physics A/B, replay the same recording twice at different rates and diff:
      autotest\replay-session.ps1 -Label jump -Fps 20 -Trace
      autotest\replay-session.ps1 -Label jump -Fps 60 -Trace
      python tools\analyse-fall.py captures\traces\jump-20.csv captures\traces\jump-60.csv

  -Fps sets the limiter INSIDE the DLL, so the frame rate changes without touching dgVoodoo or
  relaunching - the one thing that used to make 20 vs 60 comparisons incomparable.
#>
param(
    [Parameter(Mandatory=$true)][string]$Label,
    [int]$Fps = 20,
    [double]$Speed = 1.0,
    [switch]$Trace
)
$ErrorActionPreference = 'Stop'
$lab = Split-Path $PSScriptRoot -Parent
$out = Join-Path $lab 'captures\inputs'
$csv = Join-Path $out "$Label.csv"
$meta= Join-Path $out "$Label.meta.txt"
if (-not (Test-Path $csv)) { throw "no recording named '$Label' in $out" }

$state = 'MeleeDriving'
if (Test-Path $meta) {
    $m = Get-Content $meta | Where-Object { $_ -match '^start_state=' }
    if ($m) { $state = ($m -split '=')[1] }
}
Write-Host ("replaying '{0}' from state '{1}' at {2} fps" -f $Label, $state, $Fps) -ForegroundColor Cyan

Set-Content (Join-Path $lab 'captures\i76uncap.ctl') "fpscap=$Fps"
switch ($state) {
    'Training'       { & (Join-Path $PSScriptRoot 'enter-training.ps1') | Out-Host }
    'MeleeDriving'   { & (Join-Path $PSScriptRoot 'enter-melee.ps1') | Out-Host }
    'Mission5Garage' { & (Join-Path $PSScriptRoot 'enter-mission5.ps1') -StopAtGarage | Out-Host }
    default          { & (Join-Path $PSScriptRoot 'enter-melee.ps1') | Out-Host }
}

$proc = Get-Process i76 -EA SilentlyContinue | Where-Object { $_.Path -like '*i76-uncap-lab*' } | Select-Object -First 1
if (-not $proc) { throw "game not running" }
& (Join-Path $lab 'src\inject.exe') $proc.Id (Join-Path $lab 'src\i76uncap.dll') | Out-Null
Start-Sleep -Seconds 4
Set-Content (Join-Path $lab 'captures\i76uncap.ctl') "fpscap=$Fps"
Start-Sleep -Seconds 1

. "$PSScriptRoot\lib\focuslib.ps1"
$p2 = Get-GamePid
Force-Foreground $p2.MainWindowHandle | Out-Null
Start-Sleep -Milliseconds 700

if ($Trace) {
    Set-Content (Join-Path $lab 'captures\i76uncap.ctl') "fpscap=$Fps`nrecord=1"
    Start-Sleep -Milliseconds 600
}
& (Join-Path $lab 'src\inputrec.exe') play $csv $Speed | Out-Host
if ($Trace) {
    Set-Content (Join-Path $lab 'captures\i76uncap.ctl') "fpscap=$Fps`nrecord=0"
    Start-Sleep -Seconds 2
    $src = Join-Path $lab 'captures\traces\inproc.csv'
    $dst = Join-Path $lab ("captures\traces\{0}-{1}.csv" -f $Label, $Fps)
    if (Test-Path $src) { Copy-Item $src $dst -Force
        Write-Host ("per-frame trace -> {0} ({1} samples)" -f $dst, ((Get-Content $dst).Count - 1)) -ForegroundColor Green }
    else { Write-Host "no per-frame trace produced" -ForegroundColor Yellow }
}
