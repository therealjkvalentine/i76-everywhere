# TEST-FRAMERATE.ps1 - hands-on test of the frame-rate fixes in the SANDBOX game (i76-uncap-lab\game).
#
#   Run at the PHYSICAL CONSOLE (Glide will not init over RDP). Never touches the playable install.
#
#   -Mode fixed     60 fps, the recommended set: I76_HIRES_CLOCK, I76_FIXED_STEP=24, I76_FRAMERATE_FIXES,
#                   I76_ENGINE_DT_FIX, I76_RENDER_INTERP   (default)
#                   24 steps/s = 41.7 ms, the mean physics step of stock play at 20 fps (46.9 / 31.2 ms steps from the
#                   GetTickCount clock). The first version used 40 (25 ms): jumps fell short and the body felt quick.
#   -Mode nointerp  the same without I76_RENDER_INTERP (physics at 40 Hz shows as judder at 60 fps)
#   -Mode stock60   60 fps, same proxy, no switches (the control)
#   -Mode stock20   20 fps via the proxy's own cap (I76_FPS_CAP=20), no other switches (the reference feel)
#   -Mode all       "fixed" plus the 2026-10-01 additions: I76_FIX_HEALTH_PCT (stock bug: a scratched core component made
#                   the car read <1% health), I76_FIX_LABEL_TABLE, I76_FAR_CLIP=1800 (far clip + 16x render pools in
#                   memory), I76_TELEMETRY=1 (UDP 7676 + shared memory; run tools	elemetry\i76tel.py to watch).
#                   The music proxy also now plays the N..15 track run and keeps the volume slider across tracks.
#
# The frame rate: this build runs at the display's 60 Hz uncapped (dgVoodoo's FPSLimit does not cap it, see
# music-fix\README.md), so only stock20 sets a cap. The script installs music-fix\Strlkup.dll from i76-everywhere,
# boots straight into the mission (t02 by default: its scripted opening hands over to the cockpit after a few
# seconds; press Esc if a pre-start screen shows), waits for the game to exit, then puts the original STRLKUP.DLL
# back. If a previous run was killed before restoring, the next run restores first. It holds the same
# .console-test.lock the capture harnesses use, so they cannot collide.
param(
    [ValidateSet("fixed", "nointerp", "stock60", "stock20", "all", "all120")] [string]$Mode = "fixed",
    [ValidateRange(0, 16)] [double]$TerrainLod = 0,
    [ValidateSet("", "16x10", "14x9", "3x2", "4x3", "wide")] [string]$Shape = "",   # picture shape; "" = the folder's own dgVoodoo.conf
    [switch]$Bare,                           # with -Preset: start i76.exe directly, without the controller/head-look layers
    [string]$Preset = "",                    # an i76-everywhere presets\<name>.psd1 (best-120, exp-detail-16, ...): REPLACES the -Mode switch set   # 0 = off; 2..8 = I76_TERRAIN_LOD experiment (terrain refines farther out)
    [string]$Mission = "",                   # "" = normal boot through the menus; e.g. t01 = straight into a mission
    [string]$Exe = "i76.exe",                # i76.exe imports u32x.dll (save-screen mouse + ghosting fix);
                                             # i76_pristine_fix.exe does not, and saving breaks there
    [double]$FixedStep = 24,
    [string]$GameDir = "",                   # "" = the sandbox (game\). Another copy must be inside the lab (autotest\lib\gamedir.ps1
                                             # refuses anything else, and the playable installs by name)
    [switch]$DryRun                          # print the resolved paths and the switch set, start nothing
)
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "autotest\lib\gamedir.ps1")
try { $G = Resolve-LabGameDir $GameDir } catch { Write-Host "$_" -ForegroundColor Red; exit 1 }
$I76GameDirInUse = $G
$NewDll = "C:\Users\james\i76-everywhere\music-fix\Strlkup.dll"
$Dll = Join-Path $G "STRLKUP.DLL"; $BakDll = "$Dll.pretest"
$Lock = Join-Path $G ".console-test.lock"
$ConfBak = Join-Path $G "dgVoodoo.conf.pre-shape"
$play = $null

function Restore {
    if (Test-Path $BakDll) { Copy-Item $BakDll $Dll -Force; Remove-Item $BakDll }
}
if ($DryRun) {
    "TEST-FRAMERATE DRY RUN (nothing started): mode=$Mode exe=$(Join-Path $G $Exe) -glide cwd=$G"
    "  proxy $NewDll -> $Dll (original kept as $BakDll), lock $Lock, log $(Join-Path $G 'mciproxy.log')"
    exit 0
}

if (Get-Process | Where-Object { $_.ProcessName -like "i76*" }) {
    Write-Host "An i76 process is already running (another test?). Close it first." -ForegroundColor Red; exit 1
}
if (Test-Path $Lock) {
    Write-Host "Lock held: $(Get-Content $Lock -Raw)" -ForegroundColor Red
    Write-Host "If no test is running, delete $Lock and retry." ; exit 1
}
Restore                                                   # leftovers from a killed run
Set-Content $Lock "TEST-FRAMERATE $Mode pid $PID $(Get-Date)"
try {
    Copy-Item $Dll $BakDll
    Copy-Item $NewDll $Dll -Force

    foreach ($v in "I76_HIRES_CLOCK", "I76_FIXED_STEP", "I76_FRAMERATE_FIXES", "I76_ENGINE_DT_FIX", "I76_RENDER_INTERP",
                   "I76_PHYS_RATE", "I76_FPS_CAP", "I76_FIX_HEALTH_PCT", "I76_FIX_LABEL_TABLE", "I76_FAR_CLIP", "I76_TELEMETRY", "I76_GLIDE_REFRESH") {
        Remove-Item "Env:$v" -ErrorAction SilentlyContinue
    }
    if ($Mode -eq "fixed" -or $Mode -eq "nointerp" -or $Mode -eq "all" -or $Mode -eq "all120") {
        $env:I76_HIRES_CLOCK = "1"; $env:I76_FIXED_STEP = "$FixedStep"; $env:I76_FRAMERATE_FIXES = "1"; $env:I76_ENGINE_DT_FIX = "1"
    }
    if ($Mode -eq "fixed" -or $Mode -eq "all" -or $Mode -eq "all120") { $env:I76_RENDER_INTERP = "1" }
    if ($Mode -eq "all120") { $env:I76_GLIDE_REFRESH = "120" }   # 2026-10-02: ZGLIDE asks dgVoodoo for 60 Hz; the proxy substitutes 120
    Remove-Item Env:I76_TERRAIN_LOD -ErrorAction SilentlyContinue; if ($TerrainLod -ge 1) { $env:I76_TERRAIN_LOD = "$TerrainLod" }
    if ($Mode -eq "all" -or $Mode -eq "all120") { $env:I76_FIX_HEALTH_PCT = "1"; $env:I76_FIX_LABEL_TABLE = "1"; $env:I76_FAR_CLIP = "1800"; $env:I76_TELEMETRY = "1" }
    if ($Mode -eq "stock20") { $env:I76_FPS_CAP = "20" }
    if ($Preset) {
        $pf = "C:\Users\james\i76-everywhere\presets\$Preset.psd1"
        if (-not (Test-Path $pf)) { throw "no preset $pf" }
        Get-ChildItem Env: | Where-Object { $_.Name -like "I76_*" -and $_.Name -ne "I76_ASPECT_COCKPIT_FOV" } | ForEach-Object { Remove-Item "Env:$($_.Name)" }   # the .bat's cockpit-width answer survives
        $pd = Import-PowerShellDataFile $pf
        foreach ($k in $pd.Env.Keys) { Set-Item "Env:$k" $pd.Env[$k] }
    }
    if ($Mission) { $env:I76_MISSION = "$Mission.msn"; $env:I76_SKIP_MOVIES = "1" }
    $env:I76MUSIC_LOG = "1"
    # picture shape: one of the dgVoodoo.aspect-<shape>.conf files in the game folder, restored after the run
    if ($Shape) {
        $shapeConf = Join-Path $G "dgVoodoo.aspect-$Shape.conf"
        if (-not (Test-Path $shapeConf)) { throw "no $shapeConf" }
        Copy-Item (Join-Path $G "dgVoodoo.conf") $ConfBak -Force
        Copy-Item $shapeConf (Join-Path $G "dgVoodoo.conf") -Force
        if ($Shape -eq "wide") { if (-not $env:I76_ASPECT) { $env:I76_ASPECT = "3440x1440" } } else { Remove-Item Env:I76_ASPECT -ErrorAction SilentlyContinue }
    }

    # nudge the mouse: a sleeping monitor leaves Glide uninitialised and the game sits at boot (state 1) forever
    Add-Type -Name M -Namespace W -MemberDefinition '[DllImport("user32.dll")] public static extern void mouse_event(uint f, int x, int y, uint d, UIntPtr e);'
    [W.M]::mouse_event(1, 5, 0, 0, [UIntPtr]::Zero); Start-Sleep -Milliseconds 200; [W.M]::mouse_event(1, -5, 0, 0, [UIntPtr]::Zero)
    Write-Host "[TEST-FRAMERATE] $(if ($Preset) { "preset=$Preset" } else { "mode=$Mode" })  shape=$(if ($Shape) { $Shape } else { 'folder conf' })  exe=$Exe  mission=$Mission  game=$G" -ForegroundColor Cyan
    Write-Host "  proxy: $NewDll (built $((Get-Item $NewDll).LastWriteTime.ToString('yyyy-MM-dd HH:mm')))"
    Write-Host "  switches for this run:"
    Get-ChildItem Env: | Where-Object { $_.Name -like "I76_*" } | Sort-Object Name | ForEach-Object { Write-Host ("    {0,-22} = {1}" -f $_.Name, $_.Value) }
    Write-Host "  Press Esc if a pre-start screen shows. Quit the game normally when done."
    if ($Preset -and -not $Bare) {
        # the daily driver's own route: PLAY-i76.ps1 starts the pad/wheel layer, the stick layer, the mouse-wheel helper
        # and head look, exactly as PLAY.bat does there; the I76_* set above reaches the game through the inherited env
        Write-Host "  launching through PLAY-i76.ps1 (pad, wheel, stick and head-look layers as in the daily driver)"
        # PLAY-i76.ps1 returns when the game has exited (it waits, then stops its helpers)
        $play = Start-Process powershell -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
            "`"C:\Users\james\i76-everywhere\PLAY-i76.ps1`"", "-GameDir", "`"$G`"", "-Exe", $Exe, "-Preset", $Preset, "-LosslessScaling", "none", "-OpenTrack", "`"`"" -PassThru -NoNewWindow
        $p = $null
        for ($i = 0; $i -lt 40 -and -not $p; $i++) { Start-Sleep -Seconds 1; $p = Get-Process i76 -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "$G\*" } | Select-Object -First 1 }
        if (-not $p) { $play.WaitForExit(); throw "the game did not start through PLAY-i76.ps1" }
    } else {
        $p = Start-Process (Join-Path $G $Exe) -ArgumentList "-glide" -WorkingDirectory $G -PassThru
    }
    # dgVoodoo/Glide only runs its window in the foreground; keep it there while it boots (autotest\lib\focuslib.ps1)
    . (Join-Path $PSScriptRoot "autotest\lib\focuslib.ps1")
    for ($i = 0; $i -lt 10 -and -not $p.HasExited; $i++) {
        Start-Sleep -Seconds 2; $p.Refresh()
        if ($p.MainWindowHandle -ne [IntPtr]::Zero) { [void](Force-Foreground $p.MainWindowHandle) }
    }
    $p.WaitForExit()
    if ($play) { [void]$play.WaitForExit(30000) }   # let PLAY-i76.ps1 stop its helpers before the proxy is restored
    Start-Sleep -Seconds 1
    $log = Join-Path $G "mciproxy.log"
    if (Test-Path $log) {
        Write-Host "[TEST-FRAMERATE] proxy log, this run (switches that took effect):"
        $lines = Get-Content $log
        $start = ($lines | Select-String "strlkproxy: IAT patch" | Select-Object -Last 1).LineNumber
        $from = if ($start) { [Math]::Max(0, $start - 20) } else { 0 }
        $lines[$from..($lines.Count - 1)] | Where-Object { $_ -match "hires|engine-dt|framerate-fixes|fixed-step|render-interp|fps-cap|glide-refresh|fix-health|far-clip|trainer|UNEXPECTED" } |
            Select-Object -Unique | ForEach-Object { "  $_" }
    }
} finally {
    Restore
    if (Test-Path $ConfBak) { Copy-Item $ConfBak (Join-Path $G "dgVoodoo.conf") -Force; Remove-Item $ConfBak; Write-Host "[TEST-FRAMERATE] restored the folder's dgVoodoo.conf." }
    Remove-Item $Lock -ErrorAction SilentlyContinue
    Write-Host "[TEST-FRAMERATE] restored the sandbox's STRLKUP.DLL."
}
