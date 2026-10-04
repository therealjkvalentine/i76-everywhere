<#
  preset-soak.ps1 - soak an i76-everywhere preset across direct-bootable missions in the lab sandbox (P1-14 follow-up:
  the int16 terrain-vertex ceiling under the detail switches). Per mission: proxy-run with the preset's Env, then
  soak-phases.ps1 (cockpit drive / cockpit / screenshot / hood F6 / binoculars B / four glances), each phase measured
  for frame time, peak terrain vertices ([0x6442ec], ceiling 32,767) and camera mode. Records the proxy CRASH line
  and the Strlkup.dll it ran.

    .\preset-soak.ps1 -Preset best-wide -Missions t01,t02
    .\preset-soak.ps1 -Preset exp-detail-16 -Missions t05 -ExtraEnv @{ I76_ASPECT = '3440x1440' }

  -Conf (default the sandbox's dgVoodoo.aspect-wide.conf) is copied over game\dgVoodoo.conf for the batch and the
  original is put back (hash-checked) in a finally; -Conf '' leaves the folder's conf alone.
  Console: takes C:\Users\james\i76-uncap-lab\.console-owner by exclusive create (CONSOLE-LOCK.md), polling every 60 s
  while it is held, releases in the finally, and stops starting new missions after -BudgetMin minutes.
  Output: runs\preset-soak\<ts>-<preset>.md (+ .txt with the raw phase lines), captures\soak\<ts>\<preset>-<m>.png.
#>
param(
    [Parameter(Mandatory)] [string]$Preset,
    [string[]]$Missions = @(),
    [hashtable]$ExtraEnv = @{},
    [string]$Conf = "C:\Users\james\i76-uncap-lab\game\dgVoodoo.aspect-wide.conf",
    [string]$Agent = "preset-soak",
    [int]$BudgetMin = 25,
    [int]$Cockpit = 20, [int]$View = 5
)
$ErrorActionPreference = "Continue"
$Here = $PSScriptRoot
$Lab = "C:\Users\james\i76-uncap-lab"; $G = Join-Path $Lab "game"
$Owner = Join-Path $Lab ".console-owner"
$Dll = "C:\Users\james\i76-everywhere\music-fix\Strlkup.dll"
$psd = if (Test-Path $Preset) { $Preset } else { "C:\Users\james\i76-everywhere\presets\$Preset.psd1" }
$P = Import-PowerShellDataFile $psd
$Missions = @($Missions | ForEach-Object { $_ -split "," } | Where-Object { $_ })
if (-not $Missions) { $Missions = @(1..17 | ForEach-Object { "t{0:d2}" -f $_ }) }
$EnvAll = @{}; foreach ($k in $P.Env.Keys) { $EnvAll[$k] = $P.Env[$k] }
$EnvAll["I76_TELEMETRY"] = "1"
foreach ($k in $ExtraEnv.Keys) { $EnvAll[$k] = $ExtraEnv[$k] }
$ts = Get-Date -Format "yyyyMMdd-HHmmss"
$Out = Join-Path $Here "runs\preset-soak"; New-Item -ItemType Directory -Force $Out | Out-Null
$Shots = Join-Path $Lab "captures\soak\$ts"; New-Item -ItemType Directory -Force $Shots | Out-Null
$Report = Join-Path $Out "$ts-$($P.Name).md"; $Raw = Join-Path $Out "$ts-$($P.Name).txt"
$log = Join-Path $G "mciproxy.log"

# console lock: exclusive create, poll every 60 s
while ($true) {
    $busy = (Get-Process i76* -ErrorAction SilentlyContinue) -or (Test-Path "$Lab\game\.console-test.lock") -or
            (Test-Path "$Lab\game-alt\.console-test.lock") -or (Test-Path "$Lab\game-dd-20261003\.console-test.lock")
    if (-not $busy) {
        try { New-Item -ItemType File -Path $Owner -ErrorAction Stop | Out-Null; Set-Content $Owner "$Agent $(Get-Date -Format s)"; break } catch {}
    }
    $who = if (Test-Path $Owner) { (Get-Content $Owner -Raw).Trim() } else { "(game / test lock)" }
    Write-Host "[soak] console busy: $who - polling in 60 s"; Start-Sleep -Seconds 60
}
# saves and bindings: snapshot now (under the lock), compare in the finally, put back anything that changed
$SaveBak = Join-Path $env:TEMP "presetsoak-saves-$ts"; New-Item -ItemType Directory -Force $SaveBak | Out-Null
$saveFiles = @(Get-ChildItem $G -File | Where-Object { $_.Name -eq 'savegame.dir' -or $_.Name -like 'save*.cmp' -or $_.Extension -in '.def', '.spc' -or $_.Name -eq 'input.map' })
$saveFiles | ForEach-Object { Copy-Item $_.FullName $SaveBak -Force }
$saveHash = @{}; $saveFiles | ForEach-Object { $saveHash[$_.Name] = (Get-FileHash $_.FullName -Algorithm MD5).Hash }
$confDst = Join-Path $G "dgVoodoo.conf"; $confBak = "$confDst.pre-soak"; $confHash = (Get-FileHash $confDst -Algorithm MD5).Hash
$sw = [Diagnostics.Stopwatch]::StartNew()
try {
    if ($Conf) { Copy-Item $confDst $confBak -Force; Copy-Item $Conf $confDst -Force }
    $envTxt = ($EnvAll.Keys | Sort-Object | ForEach-Object { "$_=$($EnvAll[$_])" }) -join " "
    @("# preset soak $ts - $($P.Name)$(if ($ExtraEnv.Count) { ' + ' + (($ExtraEnv.Keys | ForEach-Object { "$_=$($ExtraEnv[$_])" }) -join ' ') })",
      "", "conf: $(if ($Conf) { Split-Path -Leaf $Conf } else { 'folder conf' }) | env: $envTxt", "",
      "| mission | boot | survived | cockpit fps / p99 / max ms | worst phase p99 (ms) | verts peak cockpit / hood / binoc / glance | span nodes peak (of 8000) | cams seen | crash (phase) | Strlkup.dll | screenshot |",
      "|---|---|---|---|---|---|---|---|---|---|---|") | Set-Content $Report
    foreach ($m in $Missions) {
        if ($sw.Elapsed.TotalMinutes -gt $BudgetMin) { Add-Content $Report "| (stopped: $BudgetMin-minute console budget; rest not run) |"; Write-Host "[soak] budget reached"; break }
        Get-ChildItem Env: | Where-Object { $_.Name -like "I76*" } | ForEach-Object { Remove-Item "Env:$($_.Name)" }
        $di = Get-Item $Dll; $dllTxt = "$($di.LastWriteTime.ToString('MM-dd HH:mm:ss')) $((Get-FileHash $Dll -Algorithm MD5).Hash.Substring(0,8).ToLower())"
        $o = Join-Path $env:TEMP "presetsoak-$m.out"; Remove-Item $o -ErrorAction SilentlyContinue
        $shot = Join-Path $Shots "$($P.Name)-$m.png"
        $logLen = if (Test-Path $log) { (Get-Item $log).Length } else { 0 }
        $run = [scriptblock]::Create("& '$Here\soak-phases.ps1' -Out '$o' -Shot '$shot' -Cockpit $Cockpit -View $View")
        try { $boot = & "$Here\proxy-run.ps1" -Mission $m -Hold 1 -Env $EnvAll -Run $run *>&1 | Out-String } catch { $boot = "proxy-run threw: $_" }
        # leave the folder clean for the next mission whatever happened (a held DLL once aborted the batch)
        Get-Process i76* -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "$G\*" } | ForEach-Object { $_.Kill(); [void]$_.WaitForExit(10000) }
        $pt = Join-Path $G "STRLKUP.DLL.pretest"
        for ($i = 0; $i -lt 20 -and (Test-Path $pt); $i++) { try { Copy-Item $pt (Join-Path $G "STRLKUP.DLL") -Force -ErrorAction Stop; Remove-Item $pt } catch { Start-Sleep -Milliseconds 500 } }
        $tl = Join-Path $G ".console-test.lock"
        if ((Test-Path $tl) -and ((Get-Content $tl -Raw) -like "proxy-run*")) { Remove-Item $tl }
        $bootLine = if ($boot -match "in mission after ([\d.]+) s") { "ok $($Matches[1]) s" } elseif ($boot -match "exited during boot") { "EXITED" } else { "no mission" }
        $lines = if (Test-Path $o) { @(Get-Content $o) } else { @() }
        Add-Content $Raw "== $m ($($P.Name)) boot: $bootLine"; $lines | Add-Content $Raw
        ($boot -split "`r?`n") | Where-Object { $_ -match "\[proxy-run\] (in mission|the game exited|not in a mission)|threw" } | ForEach-Object { Add-Content $Raw "   run: $($_.Trim())" }
        $crash = @()
        if (Test-Path $log) {
            $bytes = [IO.File]::ReadAllBytes($log)
            if ($bytes.Length -gt $logLen) {
                $new = [Text.Encoding]::GetEncoding(28591).GetString($bytes, $logLen, $bytes.Length - $logLen)
                $crash = @(($new -split "`n") | Where-Object { $_ -match "^CRASH: code" } | ForEach-Object { ($_ -replace "\|.*?\|.*?(\| frame.*)$", '$1').Trim() })
                ($new -split "`n") | Where-Object { $_ -match "CRASH|far-clip|terrain-lod|aspect|clutter|NOT |differs" } | ForEach-Object { Add-Content $Raw "   log: $($_.Trim())" }
            }
        }
        $get = { param($lbl) $lines | Where-Object { $_ -like "${lbl}:*" } | Select-Object -First 1 }
        $vp = { param($lbl) $l = & $get $lbl; if ($l -match "verts peak (\d+)") { $Matches[1] } else { "-" } }
        $ck = & $get "cockpit"
        $ckTxt = if ($ck -match "([\d.]+) fps \| dt mean [\d.]+ p99 ([\d.]+) max ([\d.]+)") { "$($Matches[1]) / $($Matches[2]) / $($Matches[3])" } else { "-" }
        $worst = 0.0; $worstName = "-"
        foreach ($l in $lines) { if ($l -match "^([\w-]+): .*p99 ([\d.]+)" -and [double]$Matches[2] -gt $worst) { $worst = [double]$Matches[2]; $worstName = $Matches[1] } }
        $gl = @("glance-left", "glance-right", "glance-up", "glance-down" | ForEach-Object { & $vp $_ } | Where-Object { $_ -ne "-" } | ForEach-Object { [int]$_ })
        $glMax = if ($gl.Count) { ($gl | Measure-Object -Maximum).Maximum } else { "-" }
        $cams = (@($lines | ForEach-Object { if ($_ -match "^([\w-]+): .*cam ([\d:%,]+)") { "$($Matches[1] -replace 'glance-','g')=$($Matches[2] -replace ':\d+%','' )" } }) -join " ")
        $died = $lines | Where-Object { $_ -match "DIED" } | Select-Object -First 1
        $surv = if ($bootLine -notlike "ok*") { "no boot" } elseif ($died) { "DIED in $(($died -split ':')[0])" } elseif ($lines.Count -lt 8) { "incomplete ($($lines.Count) phases)" } else { "yes" }
        $nmax = 0; $nname = "-"
        foreach ($l in $lines) { if ($l -match "^([\w-]+): .*nodes peak (\d+)" -and [int]$Matches[2] -gt $nmax) { $nmax = [int]$Matches[2]; $nname = $Matches[1] } }
        $nodesTxt = "$([int]($nmax / 16)) ($nname)"
        $crashPhase = ""
        if ($crash.Count -and $crash[0] -match "frame (\d+)") {
            $cf = [int]$Matches[1]; $crashPhase = "after the phases"
            foreach ($l in $lines) { if ($l -match "^([\w-]+): .*frames (\d+)-(\d+)" -and $cf -le [int]$Matches[3] + 2) { $crashPhase = $(if ($cf -ge [int]$Matches[2]) { "in $($Matches[1])" } else { "before $($Matches[1])" }); break } }
        }
        $crashTxt = if ($crash.Count) { (($crash -join " / ") -replace "\|", ";") + " ($crashPhase)" } else { "none" }
        $row = "| $m | $bootLine | $surv | $ckTxt | $worst ($worstName) | $(& $vp 'cockpit-drive')/$(& $vp 'cockpit') / $(& $vp 'hood') / $(& $vp 'binoc') / $glMax | $nodesTxt | $cams | $crashTxt | $dllTxt | $(if (Test-Path $shot) { $shot } else { '-' }) |"
        Add-Content $Report $row; Write-Host $row
    }
} finally {
    Get-Process i76* -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "$G\*" } | Stop-Process -Force
    if ($Conf -and (Test-Path $confBak)) { Copy-Item $confBak $confDst -Force; Remove-Item $confBak }
    $h2 = (Get-FileHash $confDst -Algorithm MD5).Hash
    Write-Host "[soak] dgVoodoo.conf restored: $(if ($h2 -eq $confHash) { 'byte-identical' } else { "MISMATCH $h2 vs $confHash" })"
    $changed = @($saveHash.Keys | Where-Object { -not (Test-Path (Join-Path $G $_)) -or (Get-FileHash (Join-Path $G $_) -Algorithm MD5).Hash -ne $saveHash[$_] })
    $extra = @(Get-ChildItem $G -File | Where-Object { ($_.Name -eq 'savegame.dir' -or $_.Name -like 'save*.cmp') -and -not $saveHash.ContainsKey($_.Name) })
    foreach ($n in $changed) { Copy-Item (Join-Path $SaveBak $n) (Join-Path $G $n) -Force }
    Write-Host "[soak] saves/bindings: $($saveHash.Count) files, $(if ($changed.Count) { "RESTORED changed: $($changed -join ', ')" } else { 'byte-identical' })$(if ($extra.Count) { "; NEW files left: $($extra.Name -join ', ')" })"
    Remove-Item $Owner -Force -ErrorAction SilentlyContinue
    Write-Host "[soak] report: $Report ($([int]$sw.Elapsed.TotalMinutes) min)"
}
