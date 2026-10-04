<#
  cactus-ab.ps1 - the full 20 vs 60 fps collision A/B, one command. MUST run with the
  physical console session active (3D will not init over RDP - the boot hangs Not Responding).

  Protocol (memory rule: control first, n stated):
    for each rate in 20, 60:
        set the rate     (I76PATCH.DLL present = ~20 fps cap; renamed .disabled = 60)
        for run in 1..Runs:
            cold-launch -> menus -> TRAINING   (mission reload = fresh, standing cacti)
            cactus-gauntlet.ps1 -Tag "<rate>fps-run<n>"   (5 cactus approaches per run)
    then analyze-cactus.py over captures\cactus\*.csv

  The 20 fps pass doubles as the CLASSIFIER CALIBRATION: at 20 fps the reported behaviour is
  "collides correctly", so on-trunk approaches there must classify as hits or the classifier
  (not the game) is wrong.
#>
param(
    [int]$Runs = 3,
    [string]$GameDir = "$PSScriptRoot\..\..\game",
    [int[]]$Rates = @(20, 60)
)
$ErrorActionPreference = 'Stop'
$lab = Resolve-Path "$PSScriptRoot\..\.."

function Set-Rate([int]$fps) {
    $on  = Join-Path $GameDir 'I76PATCH.DLL'
    $off = Join-Path $GameDir 'I76PATCH.DLL.disabled'
    if ($fps -le 30) {
        if (-not (Test-Path $on)) {
            if (Test-Path $off) { Rename-Item $off 'I76PATCH.DLL' }
            else { throw "no I76PATCH.DLL(.disabled) in $GameDir - cannot set 20 fps" }
        }
    } else {
        if (Test-Path $on) { Rename-Item $on 'I76PATCH.DLL.disabled' }
    }
    "rate set: I76PATCH " + $(if (Test-Path $on) { 'ACTIVE (~20 fps)' } else { 'disabled (60 fps)' })
}

function Enter-Training {
    Get-Process i76 -EA SilentlyContinue | Where-Object { $_.Path -like "$lab*" } | Stop-Process -Force -EA SilentlyContinue
    Start-Sleep -Seconds 3
    Start-Process -FilePath (Join-Path $GameDir 'i76.exe') -ArgumentList '-glide' -WorkingDirectory $GameDir
    Start-Sleep -Seconds 12
    . "$lab\autotest\lib\focuslib.ps1"; . "$lab\autotest\lib\inputlib.ps1"
    . "$lab\autotest\lib\memlib.ps1";   . "$lab\autotest\lib\uiclick.ps1"
    $p = Get-GamePid
    if (-not $p) { throw "game did not start" }
    Force-Foreground $p.MainWindowHandle | Out-Null
    Start-Sleep -Seconds 1
    for ($i=0; $i -lt 5; $i++) { Force-Foreground $p.MainWindowHandle | Out-Null; Send-Key $VK.ESC; Start-Sleep -Milliseconds 250; Send-Key $VK.ENTER; Start-Sleep -Milliseconds 700 }
    Click-Ui 218 310 1800     # TRIP
    Click-Ui 113 351 2500     # TRAINING
    Start-Sleep -Seconds 6
    $ctx = Mem-Open
    $ok = $false
    for ($i = 0; $i -lt 20; $i++) {
        if (Mem-InMission $ctx) { $ok = $true; break }
        Start-Sleep -Seconds 1
    }
    Mem-Close $ctx
    if (-not $ok) { throw "did not reach the training mission" }
}

foreach ($rate in $Rates) {
    Write-Host ("===== {0} fps pass =====" -f $rate) -ForegroundColor Cyan
    Get-Process i76 -EA SilentlyContinue | Where-Object { $_.Path -like "$lab*" } | Stop-Process -Force -EA SilentlyContinue
    Start-Sleep -Seconds 2
    Set-Rate $rate
    for ($r = 1; $r -le $Runs; $r++) {
        Write-Host ("--- run {0}/{1} ---" -f $r, $Runs)
        $entered = $false
        for ($try = 1; $try -le 3; $try++) {
            try { Enter-Training; $entered = $true; break }
            catch { Write-Host ("  mission entry failed (try {0}/3): {1}" -f $try, $_.Exception.Message) -ForegroundColor Yellow }
        }
        if (-not $entered) { Write-Host "  skipping run - could not enter mission" -ForegroundColor Red; continue }
        & "$PSScriptRoot\cactus-gauntlet.ps1" -Tag ("{0}fps-run{1}" -f $rate, $r)
    }
}
Get-Process i76 -EA SilentlyContinue | Where-Object { $_.Path -like "$lab*" } | Stop-Process -Force -EA SilentlyContinue
Write-Host "all runs done - analysis:" -ForegroundColor Green
python "$PSScriptRoot\analyze-cactus.py" "$lab\captures\cactus"
