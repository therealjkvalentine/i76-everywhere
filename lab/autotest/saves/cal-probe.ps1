<#
  cal-probe.ps1 - load one calibration probe save (docs/EDITOR-FIELD-TESTS.md) through leg-b.ps1, stop at the garage
  (the Build and Repair Form), then open the panes the probe asks about and capture each as a 640x480 UI image:

    form            the Build and Repair Form as loaded (leg-b's B1.7-garage.png has it too)
    engine, susp    the parts chooser opened from the Engine / Suspension row arrow
    weapon1         the chooser from the #1 Top weapon row
    special1        the chooser from the Special 1 row
    salvage         FIELD SALVAGE

  Captures go to runs\<ts>-cal-<save>\. The game is closed at the end (WM_CLOSE, then kill); leg-b restores the DLL.

    powershell -ExecutionPolicy Bypass -File cal-probe.ps1 -WantFile save009 -WantRow 9
    powershell -ExecutionPolicy Bypass -File cal-probe.ps1 -WantFile save013 -WantRow 13 -Panes form,done   # DONE into the mission
#>
param([string]$WantFile = "save009", [int]$WantRow = 9, [string[]]$Panes = @("form", "engine", "susp", "weapon1", "special1", "salvage"))
$ErrorActionPreference = "Stop"
$Panes = @($Panes | ForEach-Object { $_ -split "," } | Where-Object { $_ })   # -File passes "a,b,c" as one string
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
. "$Here\..\lib\focuslib.ps1"; . "$Here\..\lib\inputlib.ps1"; . "$Here\..\lib\maplib.ps1"
$ts = Get-Date -Format "yyyyMMdd-HHmmss"
$Out = Join-Path $Here "runs\$ts-cal-$WantFile"; New-Item -ItemType Directory -Force $Out | Out-Null
$rowUy = 193 + 23 * $WantRow
Write-Host "[cal-probe] $WantFile row $WantRow (UI y $rowUy) -> $Out" -ForegroundColor Cyan
# leg-b's finally cannot copy the DLL back while the game it left running holds it (-NoQuit): that error is expected
# and handled below, so it must not stop this script.
cmd /c "powershell -ExecutionPolicy Bypass -File `"$Here\leg-b.ps1`" -WantFile $WantFile -WantRow $WantRow -RowUy $rowUy -StopAtGarage -NoQuit > `"$Out\leg-b.out`" 2>&1"
Get-Content "$Out\leg-b.out" | Select-String "OUTCOME|B1.6 loaded|B1.7 exe|RUN ERROR|Abort" | ForEach-Object { "  $_" }
$proc = Get-GamePid
if (-not $proc) { Write-Host "[cal-probe] game not running after leg-b" -ForegroundColor Red; exit 1 }
Add-Type -Name SM2 -Namespace P -MemberDefinition '[DllImport("user32.dll")] public static extern bool PostMessageA(IntPtr h, uint m, IntPtr w, IntPtr l);'
function Grab([string]$name) { Force-Foreground $proc.MainWindowHandle | Out-Null; Start-Sleep -Milliseconds 400; Capture-UI (Join-Path $Out "$name.png"); Write-Host "  shot $name.png" }
function Open-Chooser([int]$ux, [int]$uy, [string]$name) {
    Click-UI $ux $uy 900; Grab $name
    Send-Key $VK.ESC; Start-Sleep -Milliseconds 700                                  # back to the form
    Click-UI 10 10 300                                                               # a dead spot, in case Esc opened a menu
}
try {
    Force-Foreground $proc.MainWindowHandle | Out-Null; Start-Sleep -Milliseconds 500
    foreach ($p in $Panes) {
        switch ($p) {
            "form"     { Grab "form" }
            "engine"   { Open-Chooser 287 49  "engine" }
            "susp"     { Open-Chooser 287 65  "susp" }
            "brakes"   { Open-Chooser 287 82  "brakes" }
            "weapon1"  { Open-Chooser 287 175 "weapon1" }
            "weapon4"  { Open-Chooser 287 225 "weapon4" }
            "special1" { Open-Chooser 287 283 "special1" }
            "special3" { Open-Chooser 287 317 "special3" }
            "repairs"  { Open-Chooser 445 251 "repairs" }
            "salvage"  { Click-UI 275 460 1200; Grab "salvage"; Send-Key $VK.ESC; Start-Sleep -Milliseconds 700; Grab "after-salvage" }
            "done"     { Click-UI 365 460 1200; Start-Sleep -Seconds 8; Grab "done-8s"; for ($i = 0; $i -lt 4; $i++) { Send-Key $VK.ESC; Start-Sleep -Seconds 2 }; Grab "done-mission" }
        }
    }
} finally {
    $proc.Refresh()
    if (-not $proc.HasExited) {
        [void][P.SM2]::PostMessageA($proc.MainWindowHandle, 0x0010, [IntPtr]::Zero, [IntPtr]::Zero); Start-Sleep -Seconds 5; $proc.Refresh()
        if (-not $proc.HasExited) { Stop-Process -Id $proc.Id -Force; Write-Host "  killed (WM_CLOSE ignored)" }
    }
    Get-Process | Where-Object { $_.ProcessName -like "i76*" } | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
    $G = "C:\Users\james\i76-uncap-lab\game"
    if (Test-Path "$G\STRLKUP.DLL.pretest") { Copy-Item "$G\STRLKUP.DLL.pretest" "$G\STRLKUP.DLL" -Force; Remove-Item "$G\STRLKUP.DLL.pretest"; Write-Host "  STRLKUP.DLL restored" }
    Remove-Item "$G\.console-test.lock" -ErrorAction SilentlyContinue
    Write-Host "[cal-probe] done: $Out"
}
