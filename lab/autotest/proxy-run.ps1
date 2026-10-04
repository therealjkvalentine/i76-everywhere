<#
  proxy-run.ps1 - unattended sandbox run with the i76-everywhere Strlkup proxy and a chosen switch set.

  Installs music-fix\Strlkup.dll into ..\game (backing the sandbox's up as STRLKUP.DLL.pretest), boots straight
  into a mission (I76_MISSION, movies skipped), keeps the window in the foreground while Glide initialises, waits
  until the player entity exists (memlib), runs an optional command while in the mission, then kills the game and
  restores the DLL and the console-test lock. Run at the PHYSICAL CONSOLE (Glide will not init over RDP).

    .\proxy-run.ps1                                   # the 2026-10-01 "all" set, t01, 20 s in mission, then exit
    .\proxy-run.ps1 -Mission t05 -Hold 60             # mission 5, stay 60 s
    .\proxy-run.ps1 -Run { python trn_smoke.py }      # run this once the mission is up (cwd = this folder)
    .\proxy-run.ps1 -Env @{ I76_FPS_CAP = "120" }     # extra / overriding environment switches
    .\proxy-run.ps1 -Set stock                        # no switches at all (the control)
    .\proxy-run.ps1 -KeepAlive                        # do not kill the game at the end (for hands-on follow-up)
    .\proxy-run.ps1 -GameDir ..\game-alt              # drive another sandbox copy inside the lab (tools\renderers\make-renderer-copy.ps1)
    .\proxy-run.ps1 -GameArgs "-d3d"                  # another render back end (default -glide)

  Prints the proxy log lines of this run (switches that took effect) at the end, like TEST-FRAMERATE.ps1.
#>
param(
    [string]$Mission = "t01",
    [ValidateSet("all", "fixed", "stock")] [string]$Set = "all",
    [hashtable]$Env = @{},
    [scriptblock]$Run,
    [int]$Hold = 20,
    [int]$BootTimeout = 90,
    [switch]$KeepAlive,
    [string]$Dll = "C:\Users\james\i76-everywhere\music-fix\Strlkup.dll",
    [string]$GameDir = "",          # default ..\game; any other copy must live inside the lab (memlib/focuslib filter on that path)
    [string]$GameArgs = "-glide",
    [switch]$KeepInstalledDll,      # do not install -Dll: run the folder's own STRLKUP.DLL (gate-folder.ps1 on a daily-driver twin)
    [switch]$DryRun                 # print the resolved paths and exit; touches nothing
)
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "lib\gamedir.ps1")
try { $G = Resolve-LabGameDir $GameDir } catch { Write-Host "$_" -ForegroundColor Red; exit 1 }
$I76GameDirInUse = $G               # focuslib / memlib (and anything -Run dot-sources): prefer this folder's process
$Target = Join-Path $G "STRLKUP.DLL"; $Bak = "$Target.pretest"
$Lock = Join-Path $G ".console-test.lock"
. (Join-Path $PSScriptRoot "lib\focuslib.ps1")
. (Join-Path $PSScriptRoot "lib\inputlib.ps1")
. (Join-Path $PSScriptRoot "lib\memlib.ps1")

function Restore {   # retries: a just-killed game can hold STRLKUP.DLL for a few seconds (2026-10-03: a 1 s wait threw and left .pretest + the lock)
    if (-not (Test-Path $Bak)) { return }
    for ($i = 0; $i -lt 20; $i++) { try { Copy-Item $Bak $Target -Force -ErrorAction Stop; Remove-Item $Bak; return } catch { Start-Sleep -Milliseconds 500 } }
    Copy-Item $Bak $Target -Force; Remove-Item $Bak
}
if ($DryRun) {
    "proxy-run DRY RUN (nothing started): game=$G exe=$(Join-Path $G 'i76.exe') $GameArgs set=$Set mission=$Mission"
    "  proxy $(if ($KeepInstalledDll) { "as installed ($Target), no swap" } else { "$Dll -> $Target (original kept as $Bak)" }), lock $Lock, log $(Join-Path $G 'mciproxy.log')"
    exit 0
}

if (Get-Process | Where-Object { $_.ProcessName -like "i76*" }) { Write-Host "an i76 process is already running" -ForegroundColor Red; exit 1 }
if (Test-Path $Lock) { Write-Host "lock held: $(Get-Content $Lock -Raw)" -ForegroundColor Red; exit 1 }
Restore
Set-Content $Lock "proxy-run $Set $Mission pid $PID $(Get-Date)"
$p = $null
try {
    if (-not $KeepInstalledDll) { Copy-Item $Target $Bak; Copy-Item $Dll $Target -Force }
    foreach ($v in "I76_HIRES_CLOCK", "I76_FIXED_STEP", "I76_FRAMERATE_FIXES", "I76_ENGINE_DT_FIX", "I76_RENDER_INTERP",
                   "I76_PHYS_RATE", "I76_FPS_CAP", "I76_FIX_HEALTH_PCT", "I76_FIX_LABEL_TABLE", "I76_FAR_CLIP", "I76_TELEMETRY",
                   "I76_MISSION", "I76_SKIP_MOVIES", "I76_TRAINER") { Remove-Item "Env:$v" -ErrorAction SilentlyContinue }
    if ($Set -ne "stock") {
        $env:I76_HIRES_CLOCK = "1"; $env:I76_FIXED_STEP = "24"; $env:I76_FRAMERATE_FIXES = "1"; $env:I76_ENGINE_DT_FIX = "1"; $env:I76_RENDER_INTERP = "1"
    }
    if ($Set -eq "all") { $env:I76_FIX_HEALTH_PCT = "1"; $env:I76_FIX_LABEL_TABLE = "1"; $env:I76_FAR_CLIP = "1800"; $env:I76_TELEMETRY = "1" }
    foreach ($k in $Env.Keys) { Set-Item "Env:$k" $Env[$k] }
    if ($Mission) { $env:I76_MISSION = "$Mission.msn"; $env:I76_SKIP_MOVIES = "1" }
    $env:I76MUSIC_LOG = "1"
    $logPath = Join-Path $G "mciproxy.log"
    $logStart = if (Test-Path $logPath) { (Get-Content $logPath).Count } else { 0 }

    Add-Type -Name M -Namespace W -MemberDefinition '[DllImport("user32.dll")] public static extern void mouse_event(uint f, int x, int y, uint d, UIntPtr e);'
    [W.M]::mouse_event(1, 5, 0, 0, [UIntPtr]::Zero); Start-Sleep -Milliseconds 200; [W.M]::mouse_event(1, -5, 0, 0, [UIntPtr]::Zero)
    Write-Host "[proxy-run] game=$G args=$GameArgs set=$Set mission=$Mission env: $(($Env.Keys | ForEach-Object { "$_=$($Env[$_])" }) -join ' ')" -ForegroundColor Cyan
    $p = Start-Process (Join-Path $G "i76.exe") -ArgumentList $GameArgs -WorkingDirectory $G -PassThru
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $ctx = $null; $in = $false
    while ($sw.Elapsed.TotalSeconds -lt $BootTimeout -and -not $p.HasExited) {
        Start-Sleep -Seconds 2; $p.Refresh()
        if ($p.MainWindowHandle -ne [IntPtr]::Zero) {
            [void](Force-Foreground $p.MainWindowHandle)
            # the direct mission boot parks on the scripted opening (state 0x4fe534 = 0x20, docs/MISSION-LAUNCH.md);
            # Esc skips it and starts the gameplay loop. Enter / Space do nothing there.
            if ($sw.Elapsed.TotalSeconds -gt 8) { Send-Key $VK.ESC }
        }
        try {
            if (-not $ctx) { $ctx = Mem-Open }
            if ((Mem-InMission $ctx) -and (@(Mem-Entities $ctx).Count -gt 0)) { $in = $true; break }
        } catch { $ctx = $null }
    }
    if ($p.HasExited) { Write-Host "[proxy-run] the game exited during boot (exit $($p.ExitCode))" -ForegroundColor Red }
    elseif (-not $in) { Write-Host "[proxy-run] not in a mission after $BootTimeout s" -ForegroundColor Red }
    else {
        $pl = Mem-Player $ctx
        Write-Host ("[proxy-run] in mission after {0:N0} s - speed {1:N1} m/s, {2} entities" -f $sw.Elapsed.TotalSeconds, $pl.Speed, @(Mem-Entities $ctx).Count) -ForegroundColor Green
        if ($Run) { Push-Location $PSScriptRoot; try { & $Run } finally { Pop-Location } }
        if ($Hold -gt 0) { Start-Sleep -Seconds $Hold }
    }
    if ($ctx) { Mem-Close $ctx }
} finally {
    if ($p -and -not $KeepAlive) { try { $p.Refresh(); if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force; [void]$p.WaitForExit(10000); Start-Sleep -Seconds 1 } } catch {} }
    if (-not $KeepAlive) { Restore; Remove-Item $Lock -ErrorAction SilentlyContinue }
    else { Write-Host "[proxy-run] -KeepAlive: the game is still running with the test DLL; restore with: Copy-Item '$Bak' '$Target'; Remove-Item '$Bak','$Lock'" -ForegroundColor Yellow }
    if (Test-Path $logPath) {
        $lines = Get-Content $logPath
        Write-Host "[proxy-run] proxy log, this run:"
        $lines[$logStart..($lines.Count - 1)] | Where-Object { $_ -match "hires|engine-dt|framerate-fixes|fixed-step|render-interp|fps-cap|far-clip|fix-|telemetry|trainer|CRASH|UNEXPECTED|NOT " } |
            Select-Object -Unique | ForEach-Object { "  $_" }
    }
}
