<# motion-ab.ps1 - run body-motion at both rates, 2 reps each, then analyze. #>
param([int]$Reps = 2, [string]$GameDir = "$PSScriptRoot\..\..\game")
$ErrorActionPreference = 'Stop'
$lab = Resolve-Path "$PSScriptRoot\..\.."

function Set-Rate([int]$fps) {
    $on  = Join-Path $GameDir 'I76PATCH.DLL'; $off = "$on.disabled"
    if ($fps -le 30) { if (-not (Test-Path $on)) { Rename-Item $off 'I76PATCH.DLL' } }
    else { if (Test-Path $on) { Rename-Item $on 'I76PATCH.DLL.disabled' } }
    "rate: I76PATCH " + $(if (Test-Path $on) { 'ACTIVE (~20)' } else { 'disabled (60)' })
}
function Enter-Training {
    Get-Process i76 -EA SilentlyContinue | Where-Object { $_.Path -like "$lab*" } | Stop-Process -Force -EA SilentlyContinue
    Start-Sleep -Seconds 3
    Start-Process -FilePath (Join-Path $GameDir 'i76.exe') -ArgumentList '-glide' -WorkingDirectory $GameDir
    Start-Sleep -Seconds 12
    . "$lab\autotest\lib\focuslib.ps1"; . "$lab\autotest\lib\inputlib.ps1"
    . "$lab\autotest\lib\memlib.ps1";   . "$lab\autotest\lib\uiclick.ps1"
    $p = Get-GamePid; if (-not $p) { throw "no game" }
    Force-Foreground $p.MainWindowHandle | Out-Null; Start-Sleep -Seconds 1
    for ($i=0; $i -lt 5; $i++) { Force-Foreground $p.MainWindowHandle|Out-Null; Send-Key $VK.ESC; Start-Sleep -Milliseconds 250; Send-Key $VK.ENTER; Start-Sleep -Milliseconds 700 }
    Click-Ui 218 310 1800; Click-Ui 113 351 2500; Start-Sleep -Seconds 5
    $ctx = Mem-Open; $ok = $false
    for ($i=0; $i -lt 20; $i++) { if (Mem-InMission $ctx) { $ok = $true; break }; Start-Sleep -Seconds 1 }
    Mem-Close $ctx
    if (-not $ok) { throw "did not reach mission" }
}
foreach ($rate in @(20, 60)) {
    Write-Host ("===== {0} fps =====" -f $rate) -ForegroundColor Cyan
    Get-Process i76 -EA SilentlyContinue | Where-Object { $_.Path -like "$lab*" } | Stop-Process -Force -EA SilentlyContinue
    Start-Sleep -Seconds 2
    Set-Rate $rate
    for ($r = 1; $r -le $Reps; $r++) {
        $entered = $false
        for ($try = 1; $try -le 3; $try++) { try { Enter-Training; $entered = $true; break } catch { Write-Host ("  entry failed {0}/3" -f $try) -ForegroundColor Yellow } }
        if (-not $entered) { continue }
        & "$PSScriptRoot\body-motion.ps1" -Tag ("{0}fps-r{1}" -f $rate, $r)
    }
}
Get-Process i76 -EA SilentlyContinue | Where-Object { $_.Path -like "$lab*" } | Stop-Process -Force -EA SilentlyContinue
python "$PSScriptRoot\analyze-motion.py" "$lab\captures\motion"
