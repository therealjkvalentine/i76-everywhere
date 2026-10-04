# conf-probe.ps1 - does dgVoodoo read game\dgVoodoo.conf at all? Flip one visible key ([Glide] 3DfxWatermark = true),
# boot, capture the frame, restore. If the 3dfx logo is not in the capture, the conf is not the one in effect.
#   .\conf-probe.ps1 [-HideGlobal]   (-HideGlobal also renames %APPDATA%\dgVoodoo\dgVoodoo.conf for the run)
#   -GameDir <dir>      another game folder inside the lab (default: the sandbox; autotest\lib\gamedir.ps1 refuses the rest)
#   -ClientRect         the conf-bisect.ps1 trial instead of the watermark: the conf is NOT edited; start i76.exe -glide,
#                       read the window's client size for ~9 s, kill. Prints "client WxH -> ACCEPTED" (wider than 1000:
#                       the borderless full-screen window) or "-> rejected" (dgVoodoo fell back to defaults: 640x480).
#                       Only meaningful with the global conf out of the way (-HideGlobal, or hidden by the caller).
#   -KeepInstalledDll   watermark run: proxy-run without the STRLKUP.DLL swap.   -DryRun: resolved paths only.
#   -OutFile <png>      watermark run: where the capture goes (default captures\graphics\<Tag>.png)
param([switch]$HideGlobal, [string]$Tag = "probe", [string]$UseConf = "",
      [string]$GameDir = "", [switch]$ClientRect, [switch]$KeepInstalledDll, [string]$OutFile = "", [switch]$DryRun)
$ErrorActionPreference = "Continue"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
. "$Here\..\..\autotest\lib\gamedir.ps1"
try { $G = Resolve-LabGameDir $GameDir } catch { "$_"; exit 1 }
$I76GameDirInUse = $G
$conf = "$G\dgVoodoo.conf"; $bak = "$conf.pre-probe"
$glob = "$env:APPDATA\dgVoodoo\dgVoodoo.conf"; $globHidden = "$env:APPDATA\dgVoodoo\dgVoodoo.conf.hidden-by-probe"
$out = if ($OutFile) { $OutFile } else { "C:\Users\james\i76-uncap-lab\captures\graphics\$Tag.png" }
if ($DryRun) {
    "conf-probe DRY RUN (nothing started): game=$G conf=$conf (backup $bak) global=$glob (present: $(Test-Path $glob); would hide: $([bool]$HideGlobal)) mode=$(if ($ClientRect) { 'client rect' } else { 'watermark' }) capture=$out"
    if (-not $ClientRect) { & "$Here\..\..\autotest\proxy-run.ps1" -Mission t01 -Hold 0 -GameDir $G -KeepInstalledDll:$KeepInstalledDll -DryRun | ForEach-Object { "  | $_" } }
    exit 0
}
if (Get-Process i76* -ErrorAction SilentlyContinue) { "game running"; exit 1 }
if ($ClientRect) {
    $lock = "$G\.console-test.lock"
    if (Test-Path $lock) { "lock held: $(Get-Content $lock -Raw)"; exit 1 }
    Add-Type -Name B -Namespace CP -MemberDefinition '[DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r); [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }'
    Set-Content $lock "conf-probe -ClientRect $PID $(Get-Date)"
    if ($HideGlobal -and (Test-Path $glob)) { Rename-Item $glob (Split-Path $globHidden -Leaf) }
    $w = 0; $h = 0; $p = $null
    try {
        "global conf present during the trial: $(Test-Path $glob); conf md5 $((Get-FileHash $conf -Algorithm MD5).Hash.Substring(0,8))"
        $p = Start-Process "$G\i76.exe" -ArgumentList "-glide" -WorkingDirectory $G -PassThru
        for ($i = 0; $i -lt 14; $i++) { Start-Sleep -Seconds 1; $p.Refresh(); if ($p.HasExited) { break }
            if ($p.MainWindowHandle -ne [IntPtr]::Zero) { $r = New-Object CP.B+RECT; [void][CP.B]::GetClientRect($p.MainWindowHandle, [ref]$r); $w = $r.R; $h = $r.B; if ($i -ge 8) { break } } }
    } finally {
        if ($p -and -not $p.HasExited) { Stop-Process -Id $p.Id -Force }; Start-Sleep -Seconds 2
        if ($HideGlobal -and (Test-Path $globHidden)) { Rename-Item $globHidden "dgVoodoo.conf" }
        Remove-Item $lock -ErrorAction SilentlyContinue
    }
    "client ${w}x${h} -> $(if ($w -gt 1000) { 'ACCEPTED' } else { 'rejected' })"
    exit $(if ($w -gt 1000) { 0 } else { 1 })
}
Copy-Item $conf $bak -Force
if ($UseConf) { Copy-Item $UseConf $conf -Force } else { (Get-Content $conf) | ForEach-Object { if ($_ -match '^3DfxWatermark\s*=') { "3DfxWatermark                       = true" } else { $_ } } | Set-Content $conf }
if ($HideGlobal -and (Test-Path $glob)) { Rename-Item $glob (Split-Path $globHidden -Leaf) }
try {
    $run = [scriptblock]::Create("python '$Here\freeze-at.py' on; Start-Sleep -Seconds 4; . 'C:\Users\james\i76-uncap-lab\autotest\lib\focuslib.ps1'; `$p = Get-GamePid; Force-Foreground `$p.MainWindowHandle | Out-Null; Start-Sleep -Milliseconds 800; & '$Here\capture-frame.ps1' -Out '$out' | Out-Null; python '$Here\freeze-at.py' off")
    & "$Here\..\..\autotest\proxy-run.ps1" -Mission t01 -Hold 0 -Run $run -GameDir $G -KeepInstalledDll:$KeepInstalledDll | Select-String "in mission|CRASH|exited"
} finally {
    Copy-Item $bak $conf -Force; Remove-Item $bak
    if ($HideGlobal -and (Test-Path $globHidden)) { Rename-Item $globHidden "dgVoodoo.conf" }
    "restored; capture $out"
}
