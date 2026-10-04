<#
  run-matrix.ps1 - capture every graphics variant under the same conditions (GRAPHICS-ENHANCEMENT.md section 6):
  apply the variant conf, boot t01 at 120 Hz with the full switch set, freeze the car at one fixed spot through the
  trainer block (identical view every run), capture the presented frame at panel resolution, take 10 s of frame
  statistics and one GPU sample, restore the conf. 'live' = the sandbox conf as it is (first and last), '1x' twice.

    .\run-matrix.ps1 [-Variants live,1x,1x,2x,...] [-Refresh 120]
  Output: ..\..\captures\graphics\<ts>\<nn>-<variant>.png and results.md
#>
param([string[]]$Variants = @("live", "1x", "1x", "1x-msaa8", "1.5x", "1.5x-msaa4", "2x", "2x-msaa4", "2x-msaa8", "2x-bicubic", "2x-lanczos3", "3x", "3x-bicubic", "live-tmu-appdriven", "live"), [string]$Refresh = "120")
$ErrorActionPreference = "Continue"
$Variants = @($Variants | ForEach-Object { $_ -split "," } | Where-Object { $_ })
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$ts = Get-Date -Format "yyyyMMdd-HHmmss"
$Out = Join-Path $Here "..\..\captures\graphics\$ts"; New-Item -ItemType Directory -Force $Out | Out-Null; $Out = (Resolve-Path $Out).Path
$fs = "C:\Users\james\i76-everywhere\tools\telemetry\frame_stats.py"
$freeze = Join-Path $Here "freeze-at.py"
"# graphics matrix $ts (t01, refresh $Refresh, car frozen at the same spot)`n`n| # | variant | frame rect | frame stats | GPU |`n|---|---|---|---|---|" | Set-Content "$Out\results.md"
$n = 0
foreach ($v in $Variants) {
    $n++; $tag = "{0:d2}-{1}" -f $n, $v
    if ($v -ne "live") { & "$Here\apply-conf.ps1" -Variant $v 2>&1 | Select-Object -Last 1 }
    $png = "$Out\$tag.png"; $st = "$Out\$tag.stats.txt"; $cap = "$Out\$tag.cap.txt"; $gpu = "$Out\$tag.gpu.txt"
    $run = [scriptblock]::Create("python '$freeze' on; Start-Sleep -Seconds 4; . 'C:\Users\james\i76-uncap-lab\autotest\lib\focuslib.ps1'; `$p = Get-GamePid; Force-Foreground `$p.MainWindowHandle | Out-Null; Start-Sleep -Milliseconds 800; & '$Here\capture-frame.ps1' -Out '$png' *> '$cap'; python '$fs' 10 '$tag' 2>&1 | Out-File '$st' -Encoding ascii; nvidia-smi --query-gpu=utilization.gpu,memory.used,power.draw --format=csv,noheader 2>&1 | Out-File '$gpu' -Encoding ascii; python '$freeze' off")
    $boot = & "$Here\..\..\autotest\proxy-run.ps1" -Mission t01 -Hold 0 -Env @{ I76_GLIDE_REFRESH = $Refresh } -Run $run 2>&1 | Out-String
    if ($v -ne "live") { & "$Here\apply-conf.ps1" -Restore 2>&1 | Select-Object -Last 1 }
    $rect = if (Test-Path $cap) { ((Get-Content $cap) -join " ") -replace ".*: (\d+x\d+ at \([\d,]+\)).*", '$1' } else { "-" }
    $stats = if (Test-Path $st) { ((Get-Content $st) -join " ") -replace " \| bins.*", "" -replace "^[^:]+: ", "" } else { "-" }
    $g = if (Test-Path $gpu) { (Get-Content $gpu) -join " " } else { "-" }
    $crash = if ($boot -match "CRASH|exited during boot|not in a mission") { " **BOOT/CRASH PROBLEM**" } else { "" }
    $row = "| $n | $v | $rect | $stats$crash | $g |"; Add-Content "$Out\results.md" $row; Write-Host $row
}
Write-Host "[matrix] $Out"
