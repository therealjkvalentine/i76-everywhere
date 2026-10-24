# Start opentrack tracking without a click (PLAY-i76.ps1 -HeadTrack runs this hidden, from _ahk\).
#
# WHY THE OLD i76-opentrack-autostart.ahk NEVER WORKED (owner 2026-10-24: "head look does not
# automatically start opentrack but it works fine after you click it"): opentrack 2026.1 is a Qt 6 app,
# and Qt widgets are not native windows - there is no child HWND called "Start", so the AHK's
# ControlGet/ControlClick found nothing, waited 20 s and exited (reproduced 2026-10-24, n 1). It also
# took "FT_SharedMem exists" as "tracking is live", which a reader's open handle defeats.
#
# Two mechanisms now, either is enough:
#  1. opentrack's OWN game detection (Options > Game detection): PLAY-i76.ps1 -HeadTrack enables it for
#     i76.exe -> the current profile before it starts opentrack, so opentrack starts tracking by itself
#     about a second after the game's process appears, and stops when it exits (it only stops what it
#     started itself). Needs opentrack to be started AFTER the setting is written, so it covers the
#     launcher-started case.
#  2. This script, the fallback (opentrack was already open, or the detector was off): it finds the
#     opentrack main window through UI Automation and invokes the Start button by its Qt object name
#     (...groupStartStop.btnStartTracker), which does not depend on the window title, the language or
#     the layout.
# Either way success is VERIFIED: FT_SharedMem's DataID must advance (tools\ft-heartbeat.ps1 logic).
#
#   i76-opentrack-autostart.ps1 [-WaitGame] [-GraceSec 6] [-TimeoutSec 60] [-Log <file>]
#     -WaitGame  wait for i76.exe first and give opentrack's detector -GraceSec to act before clicking
#                (the launcher passes it when it enabled the detector).
# Exit 0 = tracking live, 1 = could not start it (logged), 2 = opentrack not running.
param([switch]$WaitGame, [int]$GraceSec = 6, [int]$TimeoutSec = 60, [string]$Log = '')

$ErrorActionPreference = 'Stop'
if (-not $Log) { $Log = Join-Path $env:TEMP 'i76-opentrack-autostart.log' }
function Say($s) { $line = "{0:HH:mm:ss.fff} {1}" -f (Get-Date), $s; try { Add-Content -Path $Log -Value $line } catch { }; Write-Host $line }

function Get-FtId {
    try { $m = [System.IO.MemoryMappedFiles.MemoryMappedFile]::OpenExisting('FT_SharedMem', 'Read') } catch { return $null }
    try { $v = $m.CreateViewAccessor(0, 4, 'Read'); $id = $v.ReadUInt32(0); $v.Dispose(); return $id } finally { $m.Dispose() }
}
function Test-Live([double]$sec = 1.5) {
    $a = Get-FtId
    if ($null -eq $a) { return $false }
    $end = (Get-Date).AddSeconds($sec)
    while ((Get-Date) -lt $end) {
        Start-Sleep -Milliseconds 100
        $b = Get-FtId
        if ($null -ne $b -and $b -ne $a) { return $true }
    }
    return $false
}

function Find-StartButton {
    Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
    $AE = [System.Windows.Automation.AutomationElement]
    foreach ($p in @(Get-Process -Name opentrack -ErrorAction SilentlyContinue)) {
        $c = New-Object System.Windows.Automation.PropertyCondition($AE::ProcessIdProperty, $p.Id)
        foreach ($w in $AE::RootElement.FindAll([System.Windows.Automation.TreeScope]::Children, $c)) {
            $bc = New-Object System.Windows.Automation.PropertyCondition($AE::ControlTypeProperty, [System.Windows.Automation.ControlType]::Button)
            foreach ($b in $w.FindAll([System.Windows.Automation.TreeScope]::Descendants, $bc)) {
                if ($b.Current.AutomationId -like '*btnStartTracker') { return $b }
            }
        }
    }
    return $null
}

Say "autostart: start (WaitGame=$WaitGame)"
if (-not (Get-Process -Name opentrack -ErrorAction SilentlyContinue)) { Say 'autostart: opentrack is not running - nothing to do'; exit 2 }
if (Test-Live) { Say 'autostart: tracking already live'; exit 0 }

$deadline = (Get-Date).AddSeconds($TimeoutSec)
if ($WaitGame) {
    while (-not (Get-Process -Name i76 -ErrorAction SilentlyContinue)) {
        if ((Get-Date) -gt $deadline) { Say 'autostart: no i76.exe within the timeout'; break }
        Start-Sleep -Milliseconds 500
    }
    $grace = (Get-Date).AddSeconds($GraceSec)
    while ((Get-Date) -lt $grace) {
        if (Test-Live 1.0) { Say 'autostart: live (opentrack game detection started it)'; exit 0 }
    }
}

$tries = 0
while ((Get-Date) -lt $deadline) {
    if (-not (Get-Process -Name opentrack -ErrorAction SilentlyContinue)) { Say 'autostart: opentrack exited'; exit 2 }
    if (Test-Live 1.0) { Say "autostart: live after $tries Start press(es)"; exit 0 }
    $b = $null
    try { $b = Find-StartButton } catch { Say "autostart: UIA error $($_.Exception.Message)" }
    if ($b -and $b.Current.IsEnabled) {
        try {
            $b.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
            $tries++
            Say "autostart: Start invoked (UIA, try $tries)"
            # the camera and the network take a few seconds to come up
            $wait = (Get-Date).AddSeconds(8)
            while ((Get-Date) -lt $wait) { if (Test-Live 1.0) { Say "autostart: live after $tries Start press(es)"; exit 0 } }
        } catch { Say "autostart: Invoke failed $($_.Exception.Message)" }
    } elseif ($b) {
        # Start disabled = opentrack is already tracking (Stop is the live button); wait for data
        Start-Sleep -Milliseconds 500
    } else {
        Start-Sleep -Milliseconds 500   # window still building
    }
}
Say 'autostart: FAILED - tracking not live at the timeout'
exit 1
