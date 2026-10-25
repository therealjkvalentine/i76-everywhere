<#
  t05-route-fps.ps1 (rc-draw lane 2026-10-20; i76-everywhere docs\records\RC-DRAW-FPS-2026-10-20.md) - gate row 9: the frame rate over
  the owner's T05 route in the cockpit, through the folder's OWN launcher preset and its own STRLKUP.DLL (nothing installed).
  Why: row 3 (trip route) measures 3 s right after DONE, while T05's scripted opening still shows the outside camera on the canyon
  road; that view reads ~112-120 fps on every preset, so a draw-distance cost on T05's long cockpit views never reached the gate.

  Route (tools\rc-draw\t05-route.json, from T05.MSN's road segments): (R) 15 s east along the canyon road from the end of the opening
  (the ridge behind the intro road), then I76_START_POS puts the car on road segment 3 at (8945, 44070) facing west and (H) it drives
  segments 3 -> 4 over the hill top (7972, 44035) toward the barn (6385, 43305; segment 4 ends 500 m short of it, before a bridge), 2.7 km at about 22 m/s, keys W / A / D sent to the
  foreground game (tools\rc-draw\rcd_drive.py --input keys). God flag via the trainer block (I76_TRAINER=1).
  Output: "t05-route: ..." lines per leg (median fps, 1 % low, lowest 1 s, metres driven, far clip read back) and a verdict line.
  Physical console, nobody playing (keys go to the foreground window). Needs the launcher's preset name in the .bat (-Preset x).

    powershell -File t05-route-fps.ps1 -GameDir <lab folder> -Launcher <lab .bat> [-ExpectFps 120] [-DryRun]
#>
param([Parameter(Mandatory)][string]$GameDir, [Parameter(Mandatory)][string]$Launcher, [double]$ExpectFps = 120, [string]$OutDir = "", [string]$LaunchArgsText = "", [switch]$DryRun)
$ErrorActionPreference = "Stop"
$LaunchArgs = @("$LaunchArgsText" -split '\s+' | Where-Object { $_ })
$Here = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)   # autotest\
. "$Here\lib\gamedir.ps1"
. "$Here\lib\focuslib.ps1"
$Lab = Get-LabRoot
try { $G = Resolve-LabGameDir $GameDir; $Launcher = Resolve-LabLauncher $Launcher } catch { "$_"; exit 1 }
$bat = Get-Content $Launcher -Raw
if ($bat -notmatch '-Preset\s+(\S+)') { "no -Preset in $Launcher"; exit 1 }
$preset = $Matches[1]
$conf = if ($bat -match 'copy /y "%~dp0Interstate 76\\(dgVoodoo[^"]*\.conf)"') { $Matches[1] } else { "" }
if (-not $OutDir) { $OutDir = Join-Path $Lab "captures\t05-route-gate" }
New-Item -ItemType Directory -Force $OutDir | Out-Null
$o = Join-Path $OutDir ("{0}-{1:yyyyMMdd-HHmmss}" -f $preset, (Get-Date))
$Suf = Split-Path -Leaf (Split-Path -Parent $G)
"t05-route: folder $G, launcher $(Split-Path -Leaf $Launcher), preset $preset, conf $(if ($conf) { $conf } else { '(as is)' }), out $o"
if ($DryRun) { "t05-route: DRY RUN, nothing started"; exit 0 }
if (Get-Process | Where-Object { $_.ProcessName -like "i76*" }) { "t05-route: an i76 process is running - not started"; exit 1 }
if ($conf) { Copy-Item (Join-Path $G $conf) (Join-Path $G "dgVoodoo.conf") -Force }
foreach ($v in (Get-ChildItem Env: | Where-Object { $_.Name -like "I76*" })) { Remove-Item "Env:$($v.Name)" }
$env:I76_START_POS = "8945,100.8,44070,-90,22"; $env:I76_FRAME_LOG = "$o.frames.csv"; $env:I76_KEEP_ACTIVE = "1"; $env:I76_TRAINER = "1"
$env:I76_MUTE = "1"; $env:I76_SHM_SUFFIX = $Suf
$t0 = Get-Date
$null = Start-Process powershell -ArgumentList (@("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$(Join-Path $G 'PLAY-i76.ps1')`"", "-GameDir", "`"$G`"", "-Exe", "i76.exe",
                  "-Preset", $preset, "-LosslessScaling", "none", "-Mission", "t05.msn", "-SkipMovies") + $LaunchArgs) -WindowStyle Hidden -PassThru
$p = $null; $sw = [Diagnostics.Stopwatch]::StartNew()
while (-not $p -and $sw.Elapsed.TotalSeconds -lt 60) { Start-Sleep -Milliseconds 500; $p = Get-Process i76 -ErrorAction SilentlyContinue | Where-Object { $_.Path -and $_.Path.StartsWith($G + "\") -and $_.StartTime -ge $t0.AddSeconds(-2) } | Select-Object -First 1 }
if (-not $p) { "t05-route: the game did not start"; exit 1 }
& (Join-Path $Lab "tools\start-mute-watch.ps1") -Pid $p.Id -Log "$o.mute.txt"
if (-not $env:HLCOST_NOSAMPLE) {
$smp = Start-Process powershell -ArgumentList @("-NoProfile","-ExecutionPolicy","Bypass","-File","`"$Here\headlook-cost\sampler.ps1`"","-GamePid",$p.Id,"-Out","`"$o.cpu.csv`"") -WindowStyle Hidden -PassThru
$gpu = Start-Process nvidia-smi -ArgumentList @("--query-gpu=timestamp,utilization.gpu,utilization.memory,clocks.sm,power.draw","--format=csv,noheader,nounits","-l","1","-f","`"$o.gpu.csv`"") -WindowStyle Hidden -PassThru -ErrorAction SilentlyContinue
}
"t05-hl: sampler pid $(if ($smp) {$smp.Id}), launch args: $($LaunchArgs -join ' ')"
try {
    for ($i = 0; $i -lt 20 -and $p.MainWindowHandle -eq [IntPtr]::Zero; $i++) { Start-Sleep -Milliseconds 500; $p.Refresh() }
    if ($p.MainWindowHandle -ne [IntPtr]::Zero) { [void](Force-Foreground $p.MainWindowHandle) }
    & python -I (Join-Path $Lab "tools\rc-draw\rcd_drive.py") --pid $p.Id --out $o --frames "$o.frames.csv" --tag t05gate --mode route --input keys 2>&1 | ForEach-Object { "  $_" }
} finally {
    $p.Refresh(); if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force; [void]$p.WaitForExit(10000) }
    if ($gpu -and -not $gpu.HasExited) { Stop-Process -Id $gpu.Id -Force -ErrorAction SilentlyContinue }
}
"t05-hl: game end epoch_ms $([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()); out $o"
$lines = @(& python -I (Join-Path $Lab "tools\rc-draw\rcd_tab.py") --one $o)
$lines | ForEach-Object { "t05-route: $_" }
$hill = $lines | Where-Object { $_ -match '^hill:' } | Select-Object -First 1
$med = if ("$hill" -match 'med ([\d.]+) fps') { [double]::Parse($Matches[1], [Globalization.CultureInfo]::InvariantCulture) } else { 0 }
$m = if ("$hill" -match ', ([\d.]+) m,') { [double]::Parse($Matches[1], [Globalization.CultureInfo]::InvariantCulture) } else { 0 }
"t05-route verdict: hill leg median {0} fps over {1} m (expect >= {2} = 90 % of {3}; the leg must cover >= 2000 m): {4}" -f $med, $m, (0.9 * $ExpectFps), $ExpectFps, $(if ($med -ge 0.9 * $ExpectFps -and $m -ge 2000) { "PASS" } else { "FAIL" })
