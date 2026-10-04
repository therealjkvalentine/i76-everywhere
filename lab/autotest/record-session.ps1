<#
  record-session.ps1 — record YOUR input from a known, reproducible game state.

  THE SYNC PROBLEM AND HOW THIS SOLVES IT
  A recording is only replayable if the game is in the same state when replay starts. So this
  script does the state setup itself (launch, menus, into the mission), and only THEN starts
  recording. Replay runs the identical setup first, so your inputs land on the same screen at
  the same place.

  That means: DON'T set the game up yourself before running this. Let it do it.

    autotest\record-session.ps1 -To Training -Label jump
    autotest\record-session.ps1 -To MeleeForm -Label equip-flamer
    autotest\record-session.ps1 -To Mission5Garage -Label equip-m5

  WHILE RECORDING
    * F9   - drop a marker (press it just before the jump, or at each menu step).
             Markers are logged so I can find the interesting moment in the trace.
    * F12  - stop recording.
    * Don't alt-tab. I'76 freezes its simulation when it loses focus, and a recording made
      across a focus loss will not replay the same way.

  Everything lands in captures\inputs\<label>.csv (+ .meta.txt describing the start state).
#>
param(
    [Parameter(Mandatory=$true)][ValidateSet('Training','MeleeForm','MeleeDriving','Mission5Garage','MainMenu')]
    [string]$To,
    [Parameter(Mandatory=$true)][string]$Label,
    [int]$MaxSeconds = 300,
    [int]$Fps = 20
)
$ErrorActionPreference = 'Stop'
$lab  = Split-Path $PSScriptRoot -Parent
$out  = Join-Path $lab 'captures\inputs'
$rec  = Join-Path $lab 'src\inputrec.exe'
New-Item -ItemType Directory -Force $out | Out-Null
if (-not (Test-Path $rec)) { throw "inputrec.exe not built" }

# frame rate is set in-DLL so it can be changed later without disturbing the recording
Set-Content (Join-Path $lab 'captures\i76uncap.ctl') "fpscap=$Fps"

Write-Host "setting up the game state ($To) - do not touch the mouse or keyboard yet..." -ForegroundColor Cyan
switch ($To) {
    'Training'       { & (Join-Path $PSScriptRoot 'enter-training.ps1') | Out-Host }
    'MeleeDriving'   { & (Join-Path $PSScriptRoot 'enter-melee.ps1') | Out-Host }
    'Mission5Garage' { & (Join-Path $PSScriptRoot 'enter-mission5.ps1') -StopAtGarage | Out-Host }
    'MeleeForm'      { & (Join-Path $PSScriptRoot 'enter-melee.ps1') -StopAtForm | Out-Host }
    'MainMenu'       { & (Join-Path $PSScriptRoot 'enter-melee.ps1') -StopAtMainMenu | Out-Host }
}

# inject the DLL so the frame rate is controllable and per-frame recording is available
$proc = Get-Process i76 -EA SilentlyContinue | Where-Object { $_.Path -like '*i76-uncap-lab*' } | Select-Object -First 1
if ($proc) { & (Join-Path $lab 'src\inject.exe') $proc.Id (Join-Path $lab 'src\i76uncap.dll') | Out-Null; Start-Sleep -Seconds 4 }

$csv = Join-Path $out "$Label.csv"
@(
  "label=$Label"
  "start_state=$To"
  "fpscap=$Fps"
  "recorded=$(Get-Date -Format s)"
  "game=$($proc.Path)"
) | Set-Content (Join-Path $out "$Label.meta.txt")

Write-Host ""
Write-Host "=== READY ===" -ForegroundColor Green
Write-Host "Click into the GAME window, then do the thing." -ForegroundColor Green
Write-Host "  F9  = marker (press before the jump / at each menu step)" -ForegroundColor Yellow
Write-Host "  F12 = stop recording" -ForegroundColor Yellow
Write-Host "  do NOT alt-tab - focus loss freezes the sim and breaks replay" -ForegroundColor Yellow
Write-Host ""
for ($i = 5; $i -ge 1; $i--) { Write-Host "  recording starts in $i..." ; Start-Sleep -Seconds 1 }
Write-Host "RECORDING NOW" -ForegroundColor Red

& $rec rec $csv $MaxSeconds | Out-Host

if (Test-Path $csv) {
    $n = (Get-Content $csv).Count - 1
    $marks = (Select-String -Path $csv -Pattern '^\d+\.\d+,0,120,0,' | Measure-Object).Count   # F9 = vk 120, down
    Write-Host ""
    Write-Host ("saved {0} events ({1} markers) -> {2}" -f $n, $marks, $csv) -ForegroundColor Green
    Write-Host ("replay with:  autotest\replay-session.ps1 -Label {0} -Fps 20" -f $Label)
}
