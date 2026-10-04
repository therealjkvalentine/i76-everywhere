<#
  garage-ui.ps1 - one step at a time in a running sandbox shell screen (for exploring the garage panes by hand
  from a script): click a UI point, press a key, capture the 640x480 UI, or close the game and restore.

    garage-ui.ps1 -Start save009 -Row 9          leg-b to the garage, game left running (DLL stays installed)
    garage-ui.ps1 -Click 258,48 -Shot engine     click UI (258,48), wait, capture runs\garage-ui\engine.png
    garage-ui.ps1 -Shot form                     capture only
    garage-ui.ps1 -Key ESC                       press a key (VK name from inputlib's $VK table)
    garage-ui.ps1 -State                         print the shell state line (screen / menu fn / modal / mouse)
    garage-ui.ps1 -Close                         WM_CLOSE, kill, restore STRLKUP.DLL, remove the lock

  -GameDir <dir>   another game folder inside the lab (default: the sandbox, <lab>\game; lib\gamedir.ps1 refuses the rest).
                   Pass it on EVERY call of a session (-Start, -Click, -Close): the lock and STRLKUP.DLL.pretest are per folder.
  -Start extras    -RowUy <y> / -Scroll <n> (rows >= 10: -Scroll 10 and y = 193 + 23 x (row - (records - 10))),
                   -KeepInstalledDll, -BackupDir <dir> : handed to leg-b.ps1.  -OutDir <dir> : captures and leg-b output.
  -DryRun          with -Start: leg-b's dry run (resolved paths only); nothing is launched.
#>
param([string]$Start, [int]$Row = 0, [string]$Click, [string]$Shot, [string]$Key, [switch]$State, [switch]$Close, [int]$Settle = 900,
      [string]$GameDir = "", [int]$RowUy = -1, [int]$Scroll = 0, [switch]$KeepInstalledDll, [string]$BackupDir = "", [string]$OutDir = "", [switch]$DryRun)
$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
. "$Here\..\lib\gamedir.ps1"
$G = Resolve-LabGameDir $GameDir
$I76GameDirInUse = $G
$Out = if ($OutDir) { $OutDir } else { Join-Path $Here "runs\garage-ui" }; New-Item -ItemType Directory -Force $Out | Out-Null
. "$Here\..\lib\focuslib.ps1"; . "$Here\..\lib\inputlib.ps1"; . "$Here\..\lib\maplib.ps1"
if ($Start) {
    $rowUy = if ($RowUy -ge 0) { $RowUy } else { 193 + 23 * $Row }
    $extra = "-GameDir `"$G`""
    if ($Scroll -gt 0) { $extra += " -Scroll $Scroll" }
    if ($KeepInstalledDll) { $extra += " -KeepInstalledDll" }
    if ($BackupDir) { $extra += " -BackupDir `"$BackupDir`"" }
    if ($DryRun) { $extra += " -DryRun" }
    cmd /c "powershell -ExecutionPolicy Bypass -File `"$Here\leg-b.ps1`" -WantFile $Start -WantRow $Row -RowUy $rowUy -StopAtGarage -NoQuit $extra > `"$Out\leg-b-$Start.out`" 2>&1"
    if ($DryRun) { Get-Content "$Out\leg-b-$Start.out"; exit 0 }
    Get-Content "$Out\leg-b-$Start.out" | Select-String "B1.6 loaded|B1.7 exe|RUN ERROR|Abort" | ForEach-Object { "  $_" }
}
$proc = Get-GamePid
if ($proc -and -not (Test-ProcInDir $proc $G)) { Write-Host "the running game is $($proc.Path), not in -GameDir $G"; if (-not $Close) { exit 1 } }
if (-not $proc) { Write-Host "no sandbox game running"; if (-not $Close) { exit 1 } }
if ($proc) { Force-Foreground $proc.MainWindowHandle | Out-Null; Start-Sleep -Milliseconds 300 }
if ($Click) { $xy = $Click -split ","; Click-UI ([int]$xy[0]) ([int]$xy[1]) $Settle; "clicked UI ($($xy[0]),$($xy[1]))" }
if ($Key) { Send-Key $VK[$Key]; Start-Sleep -Milliseconds $Settle; "key $Key" }
if ($Shot) { Start-Sleep -Milliseconds 300; Capture-UI (Join-Path $Out "$Shot.png"); "shot $Out\$Shot.png" }
if ($State) {
    $ss = "C:\Users\james\i76-map\shell\tools\shellstate.ps1"
    if (Test-Path $ss) { & $ss -Once 2>$null | Select-Object -First 3 } else { "shellstate.ps1 not found" }
}
if ($Close) {
    Add-Type -Name SM3 -Namespace P -MemberDefinition '[DllImport("user32.dll")] public static extern bool PostMessageA(IntPtr h, uint m, IntPtr w, IntPtr l);'
    if ($proc) { [void][P.SM3]::PostMessageA($proc.MainWindowHandle, 0x0010, [IntPtr]::Zero, [IntPtr]::Zero); Start-Sleep -Seconds 4 }
    Get-Process | Where-Object { $_.ProcessName -like "i76*" } | Stop-Process -Force -ErrorAction SilentlyContinue; Start-Sleep -Seconds 1
    if (Test-Path "$G\STRLKUP.DLL.pretest") { Copy-Item "$G\STRLKUP.DLL.pretest" "$G\STRLKUP.DLL" -Force; Remove-Item "$G\STRLKUP.DLL.pretest"; "STRLKUP.DLL restored" }
    Remove-Item "$G\.console-test.lock" -ErrorAction SilentlyContinue; "closed"
}
