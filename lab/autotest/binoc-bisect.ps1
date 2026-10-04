<#
  binoc-bisect.ps1 - which switch makes the depth-bucket span-node pool overflow (CRASH write at exe+0x9051B,
  docs/SOAK-BEST-WIDE-2026-10-03.md)? Per variant: boot -Mission with the preset's Env minus the named switches,
  cycle binoculars on 3 s / off 2 s -Cycles times, count the proxy CRASH lines. Same console lock and conf handling
  as preset-soak.ps1 (takes .console-owner, wide conf in for the batch, both restored in the finally).

    .\binoc-bisect.ps1 -Variants 'full','-I76_ROAD_DIST','-I76_TERRAIN_LOD'      # '-X,-Y' drops several
#>
param([string]$Preset = "best-wide", [string]$Mission = "t01", [string[]]$Variants = @("full"), [int]$Cycles = 3,
      [string]$Conf = "C:\Users\james\i76-uncap-lab\game\dgVoodoo.aspect-wide.conf", [string]$Agent = "binoc-bisect")
$ErrorActionPreference = "Continue"
$Here = $PSScriptRoot; $Lab = "C:\Users\james\i76-uncap-lab"; $G = Join-Path $Lab "game"; $Owner = Join-Path $Lab ".console-owner"
$P = Import-PowerShellDataFile "C:\Users\james\i76-everywhere\presets\$Preset.psd1"
$log = Join-Path $G "mciproxy.log"
$Out = Join-Path $Here "runs\preset-soak\$(Get-Date -Format 'yyyyMMdd-HHmmss')-bisect-$Preset-$Mission.md"
while ($true) {
    $busy = (Get-Process i76* -ErrorAction SilentlyContinue) -or (Test-Path "$Lab\game\.console-test.lock") -or
            (Test-Path "$Lab\game-alt\.console-test.lock") -or (Test-Path "$Lab\game-dd-20261003\.console-test.lock")
    if (-not $busy) { try { New-Item -ItemType File -Path $Owner -ErrorAction Stop | Out-Null; Set-Content $Owner "$Agent $(Get-Date -Format s)"; break } catch {} }
    Write-Host "[bisect] console busy - polling in 60 s"; Start-Sleep -Seconds 60
}
$confDst = Join-Path $G "dgVoodoo.conf"; $confBak = "$confDst.pre-bisect"; $confHash = (Get-FileHash $confDst -Algorithm MD5).Hash
try {
    if ($Conf) { Copy-Item $confDst $confBak -Force; Copy-Item $Conf $confDst -Force }
    "# binoculars on/off bisect - $Preset on $Mission, $Cycles cycles (B 3 s on, 2 s off)`n`n| variant | dropped | boot | CRASH lines (exe offset, frame, cam mode) | binoc fps |`n|---|---|---|---|---|" | Set-Content $Out
    foreach ($v in $Variants) {
        # variant: 'full', '-A,-B' (drop switches) or 'A=1,B=2' (override values)
        $drop = @(if ($v -ne "full" -and $v -notmatch "=") { $v.TrimStart('-') -split ",-?" })
        $envV = @{}; foreach ($k in $P.Env.Keys) { if ($drop -notcontains $k) { $envV[$k] = $P.Env[$k] } }
        if ($v -match "=") { foreach ($kv in $v -split ",") { $kk, $vv = $kv -split "=", 2; $envV[$kk.Trim()] = $vv.Trim() } }
        $envV["I76_TELEMETRY"] = "1"
        Get-ChildItem Env: | Where-Object { $_.Name -like "I76*" } | ForEach-Object { Remove-Item "Env:$($_.Name)" }
        $o = Join-Path $env:TEMP "bisect-$Mission.out"; Remove-Item $o -ErrorAction SilentlyContinue
        $logLen = if (Test-Path $log) { (Get-Item $log).Length } else { 0 }
        $run = [scriptblock]::Create(". '$Here\lib\inputlib.ps1'; . '$Here\lib\focuslib.ps1'; `$g = Get-GamePid; Start-Sleep 2; for (`$c = 0; `$c -lt $Cycles; `$c++) { [void](Force-Foreground `$g.MainWindowHandle); Send-Key ([byte]0x42); & python '$Here\lib\phase_stats.py' `$g.Id 3 binoc$c >> '$o'; [void](Force-Foreground `$g.MainWindowHandle); Send-Key ([byte]0x42); & python '$Here\lib\phase_stats.py' `$g.Id 2 off$c >> '$o' }")
        try { $boot = & "$Here\proxy-run.ps1" -Mission $Mission -Hold 1 -Env $envV -Run $run *>&1 | Out-String } catch { $boot = "threw: $_" }
        Get-Process i76* -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "$G\*" } | ForEach-Object { $_.Kill(); [void]$_.WaitForExit(10000) }
        $pt = Join-Path $G "STRLKUP.DLL.pretest"
        for ($i = 0; $i -lt 20 -and (Test-Path $pt); $i++) { try { Copy-Item $pt (Join-Path $G "STRLKUP.DLL") -Force -ErrorAction Stop; Remove-Item $pt } catch { Start-Sleep -Milliseconds 500 } }
        $tl = Join-Path $G ".console-test.lock"; if ((Test-Path $tl) -and ((Get-Content $tl -Raw) -like "proxy-run*")) { Remove-Item $tl }
        $crash = @()
        if (Test-Path $log) { $b = [IO.File]::ReadAllBytes($log); if ($b.Length -gt $logLen) {
            $crash = @(([Text.Encoding]::GetEncoding(28591).GetString($b, $logLen, $b.Length - $logLen) -split "`n") | Where-Object { $_ -match "^CRASH: code" } |
                ForEach-Object { if ($_ -match "\((exe\+0x[0-9A-Fa-f]+)\).*frame (\d+) .*mode (\d+)") { "$($Matches[1]) f$($Matches[2]) m$($Matches[3])" } else { $_.Trim() } }) } }
        $lines = if (Test-Path $o) { @(Get-Content $o) } else { @() }
        $phaseOf = { param($f) foreach ($l in $lines) { if ($l -match "^(\w+): .*frames (\d+)-(\d+)" -and [int]$f -le [int]$Matches[3] + 2) { return $(if ([int]$f -ge [int]$Matches[2]) { "in $($Matches[1])" } else { "before $($Matches[1])" }) } }; "after" }
        $crashTxt = if ($crash.Count) { ($crash | ForEach-Object { if ($_ -match " f(\d+) ") { "$_ ($(& $phaseOf $Matches[1]))" } else { $_ } }) -join "; " } else { "none" }
        $fps = ($lines | Where-Object { $_ -like "binoc*" } | ForEach-Object { if ($_ -match "([\d.]+) fps") { $Matches[1] } }) -join " / "
        $bootTxt = if ($boot -match "in mission after ([\d.]+) s") { "ok" } else { "FAILED" }
        $row = "| $v | $($drop -join ' ') | $bootTxt | $crashTxt | $fps |"; Add-Content $Out $row; Write-Host $row
    }
} finally {
    Get-Process i76* -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "$G\*" } | Stop-Process -Force
    if ($Conf -and (Test-Path $confBak)) { Copy-Item $confBak $confDst -Force; Remove-Item $confBak }
    Write-Host "[bisect] conf $(if ((Get-FileHash $confDst -Algorithm MD5).Hash -eq $confHash) { 'byte-identical' } else { 'MISMATCH' }); report $Out"
    Remove-Item $Owner -Force -ErrorAction SilentlyContinue
}
