<#
  farclip-soak.ps1 - backlog P1-14: I76_FAR_CLIP=1800 was only ever exercised on t01. Boot every mission directly
  with the full switch set, hold 6 s driving, press F6 (hood view) and B (binoculars) with 4 s each, take frame
  statistics, and record any CRASH line the proxy's crash logger writes. One proxy-run per mission (~45 s each).

    .\farclip-soak.ps1                      # all 40 stock missions
    .\farclip-soak.ps1 -Missions t05,m03    # a subset
    .\farclip-soak.ps1 -FarClip 2500        # the proxy's cap

  Output: runs\farclip-soak\<ts>.md (one row per mission) and the per-mission frame_stats lines.
#>
param([string[]]$Missions = @(), [string]$FarClip = "1800", [int]$Drive = 6, [int]$View = 4)
$ErrorActionPreference = "Continue"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Missions = @($Missions | ForEach-Object { $_ -split "," } | Where-Object { $_ })
if (-not $Missions) {
    $Missions = @(1..17 | ForEach-Object { "t{0:d2}" -f $_ }) + @(1..15 | ForEach-Object { "m{0:d2}" -f $_ }) + @(1..7 | ForEach-Object { "s{0:d2}" -f $_ }) + @("a01")
}
$Out = Join-Path $Here "runs\farclip-soak"; New-Item -ItemType Directory -Force $Out | Out-Null
$ts = Get-Date -Format "yyyyMMdd-HHmmss"; $Report = Join-Path $Out "$ts.md"
$fs = "C:\Users\james\i76-everywhere\tools\telemetry\frame_stats.py"
$log = "C:\Users\james\i76-uncap-lab\game\mciproxy.log"
"# far-clip soak $ts - I76_FAR_CLIP=$FarClip, full switch set, direct mission boot`n`n| mission | boot | drive | hood (F6) | binoculars (B) | crash |`n|---|---|---|---|---|---|" | Set-Content $Report
foreach ($m in $Missions) {
    $o = "$env:TEMP\soak-$m.out"; Remove-Item $o -ErrorAction SilentlyContinue
    $logLen = if (Test-Path $log) { (Get-Item $log).Length } else { 0 }
    $run = [scriptblock]::Create(". 'C:\Users\james\i76-uncap-lab\autotest\lib\inputlib.ps1'; . 'C:\Users\james\i76-uncap-lab\autotest\lib\focuslib.ps1'; cmd /c `"python $fs $Drive drive > $o 2>&1`"; `$p = Get-GamePid; Force-Foreground `$p.MainWindowHandle | Out-Null; Send-Key `$VK.F6; Start-Sleep 1; cmd /c `"python $fs $View hood >> $o 2>&1`"; Send-Key `$VK.F6; Start-Sleep 1; Send-Key ([byte]0x42); Start-Sleep 1; cmd /c `"python $fs $View binoc >> $o 2>&1`"; Send-Key ([byte]0x42)")
    $boot = & "$Here\proxy-run.ps1" -Mission $m -Hold 1 -Env @{ I76_FAR_CLIP = $FarClip } -Run $run 2>&1 | Out-String
    $bootLine = if ($boot -match "in mission after ([\d.]+) s") { "ok $($Matches[1]) s" } elseif ($boot -match "exited during boot") { "EXITED" } else { "no mission" }
    $stats = if (Test-Path $o) { Get-Content $o } else { @() }
    $driveLine = ($stats | Where-Object { $_ -like "drive:*" }) -replace "drive: ", ""
    $hoodLine = ($stats | Where-Object { $_ -like "hood:*" }) -replace "hood: ", ""
    $binocLine = ($stats | Where-Object { $_ -like "binoc:*" }) -replace "binoc: ", ""
    $crash = ""
    if (Test-Path $log) {
        $bytes = [IO.File]::ReadAllBytes($log)
        if ($bytes.Length -gt $logLen) {
            $new = [Text.Encoding]::GetEncoding(28591).GetString($bytes, $logLen, $bytes.Length - $logLen)
            $crash = (($new -split "`n") | Where-Object { $_ -match "^CRASH: code" } | Select-Object -First 1) -replace "\|.*", ""
        }
    }
    $short = { param($s) if ($s) { ($s -replace " \| bins.*", "") -replace "frames in [\d.]+ s = ", "" } else { "-" } }
    $row = "| $m | $bootLine | $(& $short $driveLine) | $(& $short $hoodLine) | $(& $short $binocLine) | $(if ($crash) { $crash.Trim() } else { 'none' }) |"
    Add-Content $Report $row; Write-Host $row
}
Write-Host "[soak] report: $Report"
