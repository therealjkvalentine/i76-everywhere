# try-conf.ps1 - apply key overrides to the sandbox dgVoodoo.conf for one run, boot t01 at a refresh, freeze the car,
# screenshot the WHOLE desktop (so window geometry is visible), take frame stats + GPU sample, then the Esc-menu pin
# test, restore the conf. Overrides: "Section.Key=value;Section.Key=value".
#   .\try-conf.ps1 -Tag A -Set "General.FullScreenMode=true;Glide.Resolution=3840x2880;Glide.Antialiasing=4x"
param([string]$Tag = "A", [string]$Set = "", [string]$Refresh = "120", [switch]$Keep, [switch]$NoPin)
$ErrorActionPreference = "Continue"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$G = "C:\Users\james\i76-uncap-lab\game"; $conf = "$G\dgVoodoo.conf"; $bak = "$conf.pre-try"
$OutDir = "C:\Users\james\i76-uncap-lab\captures\graphics\try"; New-Item -ItemType Directory -Force $OutDir | Out-Null
if (Get-Process i76* -ErrorAction SilentlyContinue) { "game running"; exit 1 }
Copy-Item $conf $bak -Force
$ov = @{}; foreach ($kv in ($Set -split ";" | Where-Object { $_ })) { $a = $kv -split "=", 2; $ov[$a[0].Trim()] = $a[1].Trim() }
$sec = ""; $seen = @{}
$lines = Get-Content $conf | ForEach-Object {
    if ($_ -match '^\[(\w+)\]') { $sec = $Matches[1]; $_ }
    elseif ($_ -match '^([A-Za-z0-9_]+)\s*=' -and $ov.ContainsKey("$sec.$($Matches[1])")) { $k = "$sec.$($Matches[1])"; $seen[$k] = 1; "{0,-36}= {1}" -f $Matches[1], $ov[$k] }
    else { $_ }
}
$missing = @($ov.Keys | Where-Object { -not $seen.ContainsKey($_) }); if ($missing) { "KEYS NOT FOUND IN CONF (not applied): $($missing -join ', ')" }
[IO.File]::WriteAllLines($conf, $lines, [Text.Encoding]::ASCII)
try {
    $png = "$OutDir\$Tag.png"; $st = "$OutDir\$Tag.stats.txt"
    $run = [scriptblock]::Create("python '$Here\freeze-at.py' on; Start-Sleep -Seconds 4; . 'C:\Users\james\i76-uncap-lab\autotest\lib\focuslib.ps1'; `$p = Get-GamePid; Force-Foreground `$p.MainWindowHandle | Out-Null; Start-Sleep -Milliseconds 800; Add-Type -AssemblyName System.Drawing; `$b = New-Object Drawing.Bitmap 3440,1440; `$g = [Drawing.Graphics]::FromImage(`$b); `$g.CopyFromScreen(0,0,0,0,`$b.Size); `$b.Save('$png'); python 'C:\Users\james\i76-everywhere\tools\telemetry\frame_stats.py' 8 '$Tag' 2>&1 | Out-File '$st' -Encoding ascii; nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader 2>&1 | Out-File '$st' -Append -Encoding ascii; python '$Here\freeze-at.py' off")
    $boot = & "$Here\..\..\autotest\proxy-run.ps1" -Mission t01 -Hold 0 -Env @{ I76_GLIDE_REFRESH = $Refresh } -Run $run 2>&1 | Out-String
    if ($boot -match "CRASH|exited during boot|not in a mission") { "[$Tag] BOOT PROBLEM: " + (($boot -split "`n" | Select-String "CRASH|exited|not in").Line -join " | ") }
    "[$Tag] " + ((Get-Content $st -ErrorAction SilentlyContinue) -join " | " -replace " \| bins[^|]*", "")
    if (-not $NoPin) {
        & "$Here\..\..\autotest\test-escmenu.ps1" -Stage open -Tag "try-$Tag" 2>&1 | Select-String "menu:|cursor after" | ForEach-Object { "[$Tag] " + ($_.Line -replace "row\[.*engclip", "engclip") }
        & "$Here\..\..\autotest\test-escmenu.ps1" -Stage close | Out-Null
    }
} finally {
    Get-Process i76* -ErrorAction SilentlyContinue | Stop-Process -Force
    if (-not $Keep) { Copy-Item $bak $conf -Force }; Remove-Item $bak
    if (Test-Path "$G\STRLKUP.DLL.pretest") { Copy-Item "$G\STRLKUP.DLL.pretest" "$G\STRLKUP.DLL" -Force; Remove-Item "$G\STRLKUP.DLL.pretest" }
    Remove-Item "$G\.console-test.lock" -ErrorAction SilentlyContinue
}
