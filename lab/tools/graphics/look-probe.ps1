# look-probe.ps1 - what does a given dgVoodoo.conf actually put on the screen in a given game folder?
# Installs the conf into the folder for one run (restores after), boots t01 through proxy-run, screenshots the whole
# desktop to captures\graphics\look\<tag>.png. -HideGlobal renames the %APPDATA% conf for the run.
param([Parameter(Mandatory)] [string]$GameDir, [Parameter(Mandatory)] [string]$Conf, [string]$Tag = "look", [switch]$HideGlobal, [string]$Set = "stock", [hashtable]$Env = @{})
$ErrorActionPreference = "Continue"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$dst = Join-Path $GameDir "dgVoodoo.conf"; $bak = "$dst.pre-look"
$glob = "$env:APPDATA\dgVoodoo\dgVoodoo.conf"
$out = "C:\Users\james\i76-uncap-lab\captures\graphics\look"; New-Item -ItemType Directory -Force $out | Out-Null
if (Get-Process i76* -ErrorAction SilentlyContinue) { "game running"; exit 1 }
Copy-Item $dst $bak -Force; Copy-Item $Conf $dst -Force
if ($HideGlobal -and (Test-Path $glob)) { Rename-Item $glob "dgVoodoo.conf.hidden-by-look" }
try {
    $png = "$out\$Tag.png"
    $run = [scriptblock]::Create("Start-Sleep -Seconds 3; Add-Type -AssemblyName System.Drawing; `$b = New-Object Drawing.Bitmap 3440,1440; `$g = [Drawing.Graphics]::FromImage(`$b); `$g.CopyFromScreen(0,0,0,0,`$b.Size); `$b.Save('$png'); `$s = New-Object Drawing.Bitmap `$b, 1147, 480; `$s.Save('$out\$Tag-view.png'); python 'C:\Users\james\i76-everywhere\tools\telemetry\frame_stats.py' 6 '$Tag' 2>&1 | Out-File '$out\$Tag.stats.txt' -Encoding ascii")
    & "$Here\..\..\autotest\proxy-run.ps1" -GameDir $GameDir -Mission t01 -Set $Set -Env $Env -Hold 0 -Run $run 2>&1 | Select-String "in mission|CRASH|exited|not in a mission"
    "[$Tag] $png"
    if (Test-Path "$out\$Tag.stats.txt") { ((Get-Content "$out\$Tag.stats.txt") -join " ") -replace " \| bins.*", "" }
} finally {
    Get-Process i76* -ErrorAction SilentlyContinue | Stop-Process -Force
    Copy-Item $bak $dst -Force; Remove-Item $bak
    if (Test-Path "$env:APPDATA\dgVoodoo\dgVoodoo.conf.hidden-by-look") { Rename-Item "$env:APPDATA\dgVoodoo\dgVoodoo.conf.hidden-by-look" "dgVoodoo.conf" }
}
