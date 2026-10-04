# option6-trip-test.ps1 - run TEST-FRAMERATE.ps1 in a given mode exactly as the .bat does, then walk the menus by
# clicks (TRIP -> LOAD BOOKMARK -> row -> LOAD -> ACCEPT SALVAGE -> DONE), and report whether the engine came up
# (player entity, frame rate from the proxy heartbeat). Closes the game so TEST-FRAMERATE restores the sandbox.
#
#   -GameDir <dir>      another game folder inside the lab (default: the sandbox, <lab>\game; lib\gamedir.ps1 refuses
#                       anything outside the lab and the playable installs). Handed to TEST-FRAMERATE.ps1 -GameDir.
#   -Launcher <file>    start THIS .bat / .cmd / .ps1 instead of TEST-FRAMERATE.ps1 (the daily-driver twin's PLAY.bat ->
#                       PLAY-i76.ps1 -Preset ...), then walk the same clicks. The launcher must be a file inside the lab
#                       and the game it starts must run from -GameDir, or the test stops and kills what was started.
#                       Nothing is installed in this mode: the folder's own STRLKUP.DLL runs; every I76* variable is
#                       removed from this process first so the launcher's preset is the only source of switches.
#                       A .ps1 gets `-GameDir "<dir>"` unless -LauncherArgs is given; a .bat gets -LauncherArgs only.
#   -Scroll <n>         clicks on the LOAD board's down arrow before the row click (rows >= 10: 10, saves\cal-probe2.ps1)
#   -CheckFfb           once the engine is up, run i76-everywhere\tools\check-ffb.ps1 (it only reads) and print "ffb: ..."
#   -ShotDir <dir>      where the desktop screenshot goes (default %TEMP%)
#   -DryRun             print what would be started, with the resolved paths; starts nothing
param([string]$Mode = "all120", [int]$RowUy = 262,
      [string]$GameDir = "", [string]$Launcher = "", [string]$LauncherArgs = "", [int]$Scroll = 0, [switch]$CheckFfb,
      [string]$ShotDir = "", [switch]$DryRun)
$ErrorActionPreference = "Continue"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
. "$Here\lib\gamedir.ps1"
try { $G = Resolve-LabGameDir $GameDir; if ($Launcher) { $Launcher = Resolve-LabLauncher $Launcher } } catch { "$_"; exit 1 }
$I76GameDirInUse = $G                  # focuslib / memlib / maplib: prefer this folder's process and conf
$Lock = Join-Path $G ".console-test.lock"
$tag = if ($Launcher) { "launcher" } else { $Mode }
$tfArgs = "-NoProfile -ExecutionPolicy Bypass -File `"$Here\..\TEST-FRAMERATE.ps1`" -Mode $Mode -GameDir `"$G`""
$launchDesc = if (-not $Launcher) { "powershell $tfArgs" }
              elseif ($Launcher -match '(?i)\.ps1$') { if (-not $LauncherArgs) { $LauncherArgs = "-GameDir `"$G`"" }; "powershell -NoProfile -ExecutionPolicy Bypass -File `"$Launcher`" $LauncherArgs" }
              else { "cmd /c `"`"$Launcher`" $LauncherArgs`"" }
if ($DryRun) {
    "option6-trip-test DRY RUN (nothing started)"
    "  game dir : $G"
    "  launch   : $launchDesc"
    "  lock     : $Lock $(if ($Launcher) { '(taken and removed by this script)' } else { '(TEST-FRAMERATE.ps1 owns it)' })"
    "  route    : TRIP (217,311) -> LOAD BOOKMARK (276,351) -> $Scroll scroll click(s) at (212,422) -> row (320,$RowUy) -> LOAD (352,428) -> ACCEPT SALVAGE (412,460) -> DONE (400,460)"
    "  u32x     : $(Join-Path $G 'u32x.dll')   STRLKUP: $(Join-Path $G 'STRLKUP.DLL')$(if ($Launcher) { ' (as installed, no swap)' } else { ' (music-fix build for the run, .pretest restored)' })"
    if (-not $Launcher) { & powershell -NoProfile -ExecutionPolicy Bypass -File "$Here\..\TEST-FRAMERATE.ps1" -Mode $Mode -GameDir $G -DryRun | ForEach-Object { "  | $_" } }
    exit 0
}
. "$Here\lib\focuslib.ps1"; . "$Here\lib\inputlib.ps1"; . "$Here\lib\maplib.ps1"; . "$Here\lib\memlib.ps1"
if (Get-Process i76* -ErrorAction SilentlyContinue) { "an i76 process is running"; exit 1 }
$tf = $null; $lockMine = $false
function Stop-Mine {      # the game, then what this script owns (lock, .pretest); the launcher's helpers stop themselves
    Get-Process i76 -ErrorAction SilentlyContinue | Stop-Process -Force
    Start-Sleep -Seconds 4
    if ($Launcher) {
        # PLAY-i76.ps1 waits for the game and then stops its helpers (wheel, AHK layers): give it time, report leftovers
        $root = Split-Path -Parent $Launcher
        for ($i = 0; $i -lt 20; $i++) {
            $left = @(Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue | Where-Object { $_.ProcessId -ne $PID -and $_.CommandLine -and $_.CommandLine.IndexOf($root, [StringComparison]::OrdinalIgnoreCase) -ge 0 -and $_.CommandLine -notmatch 'option6-trip-test|gate-folder' })
            if ($left.Count -eq 0) { break }; Start-Sleep -Seconds 1
        }
        if ($left.Count -gt 0) { "launcher script still running after 20 s (not killed): pid $(($left | ForEach-Object ProcessId) -join ', ')" } else { "launcher script exited on its own" }
        if ($lockMine) { Remove-Item $Lock -ErrorAction SilentlyContinue }
    } else {
        if ($tf -and -not $tf.HasExited) { Stop-Process -Id $tf.Id -Force -ErrorAction SilentlyContinue; "TEST-FRAMERATE window closed by the test (it waits for a key)" }
        if (Test-Path "$G\STRLKUP.DLL.pretest") { Copy-Item "$G\STRLKUP.DLL.pretest" "$G\STRLKUP.DLL" -Force; Remove-Item "$G\STRLKUP.DLL.pretest" }
        Remove-Item $Lock -ErrorAction SilentlyContinue
    }
    "sandbox: $G STRLKUP $((Get-Item "$G\STRLKUP.DLL").Length) B, lock $(Test-Path $Lock)"
}
if ($Launcher) {
    if (Test-Path $Lock) { "lock held: $(Get-Content $Lock -Raw)"; exit 1 }
    Set-Content $Lock "option6-trip-test -Launcher pid $PID $(Get-Date)"; $lockMine = $true
    Get-ChildItem Env: | Where-Object { $_.Name -like "I76*" } | ForEach-Object { Remove-Item "Env:$($_.Name)" }
    "[$tag] starting: $launchDesc"
    if ($Launcher -match '(?i)\.ps1$') { $tf = Start-Process powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$Launcher`" $LauncherArgs" -WorkingDirectory (Split-Path -Parent $Launcher) -PassThru -WindowStyle Minimized }
    else { $tf = Start-Process cmd.exe -ArgumentList "/c `"`"$Launcher`" $LauncherArgs`"" -WorkingDirectory (Split-Path -Parent $Launcher) -PassThru -WindowStyle Minimized }
    # the launcher starts its helpers first: wait for the game process (60 s), then give it the 12 s the default mode gives
    $any = $null
    for ($i = 0; $i -lt 60 -and -not $any; $i++) { Start-Sleep -Seconds 1; $any = Get-Process i76, nitro -ErrorAction SilentlyContinue | Select-Object -First 1 }
    if ($any -and -not (Test-ProcInDir $any $G)) {
        "[$tag] engine up: False | the launcher started $($any.Path), which is NOT in -GameDir $G - killed, nothing clicked"
        Stop-Mine; exit 1
    }
    if ($any) { $age = ((Get-Date) - $any.StartTime).TotalSeconds; if ($age -lt 12) { Start-Sleep -Seconds ([int](12 - $age)) } }
} else {
    $tf = Start-Process powershell -ArgumentList $tfArgs -PassThru -WindowStyle Minimized
    Start-Sleep -Seconds 12
}
$p = Get-GamePid; if (-not $p) { "game did not start"; "[$tag] engine up: False | the game did not start"; Stop-Mine; exit 1 }
for ($i = 0; $i -lt 6; $i++) { Force-Foreground $p.MainWindowHandle | Out-Null; Send-Key $VK.ESC; Start-Sleep -Milliseconds 300; Send-Key $VK.ENTER; Start-Sleep -Milliseconds 800 }
Click-UI 217 311 900                 # TRIP
Click-UI 276 351 1500                # LOAD BOOKMARK
for ($i = 0; $i -lt $Scroll; $i++) { Click-UI 212 422 250 }   # rows >= 10: scroll the board to the bottom
Click-UI 320 $RowUy 700              # the bookmark row
Click-UI 352 428 3000                # LOAD
Click-UI 412 460 2000                # ACCEPT SALVAGE -> garage
Click-UI 400 460 2000                # DONE -> mission
$c = Mem-Open; $ok = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    if ((Mem-PlayerEntity $c) -ne 0 -and (Mem-I32 $c 0x5a7e1c) -gt 0) { $ok = $true; break }
    Force-Foreground $p.MainWindowHandle | Out-Null; Send-Key $VK.ESC
}
# frame rate twice over the same 3 s: the proxy's trainer heartbeat (Local\I76Trainer +76) and the exe's own frame
# counter (0x5a7e1c). A heartbeat that does not move reads 0.0 (no trainer block in this build / preset, or a stale
# mapping): the exe counter is the fallback.
$f0 = Mem-I32 $c 0x5a7e1c; $swf = [Diagnostics.Stopwatch]::StartNew()
$fps = python -c "import mmap,struct,time; m=mmap.mmap(-1,168,tagname='Local\\I76Trainer'); a=struct.unpack_from('<I',m,76)[0]; time.sleep(3); b=struct.unpack_from('<I',m,76)[0]; print('%.1f' % ((b-a)/3.0))"
$f1 = Mem-I32 $c 0x5a7e1c; $exeFps = if ($swf.Elapsed.TotalSeconds -gt 0) { (($f1 - $f0) / $swf.Elapsed.TotalSeconds).ToString("0.0", [Globalization.CultureInfo]::InvariantCulture) } else { "-" }
"[$tag] engine up: $ok | player 0x{0:x} | gstate {1} | exe frame {2} | proxy fps {3} | u32x {4} | exe fps {5} | game {6}" -f (Mem-PlayerEntity $c), (Mem-I32 $c 0x4c2164), (Mem-I32 $c 0x5a7e1c), $fps, (Get-FileHash "$G\u32x.dll" -Algorithm MD5).Hash.Substring(0, 8), $exeFps, $p.Path
Mem-Close $c
if ($CheckFfb) {
    $ffb = "C:\Users\james\i76-everywhere\tools\check-ffb.ps1"
    if (-not $ok) { "ffb: not run (the engine is not up; check-ffb needs a mission)" }
    elseif (-not (Test-Path $ffb)) { "ffb: not run ($ffb not found)" }
    else { & powershell -NoProfile -ExecutionPolicy Bypass -File $ffb 2>&1 | ForEach-Object { "ffb: $_" } }
}
$shot = Join-Path $(if ($ShotDir) { $ShotDir } else { $env:TEMP }) "option6-$tag.png"
try { Add-Type -AssemblyName System.Drawing; $bm = New-Object Drawing.Bitmap 3440,1440; $gg = [Drawing.Graphics]::FromImage($bm); $gg.CopyFromScreen(0,0,0,0,$bm.Size); $sm = New-Object Drawing.Bitmap $bm, 1147, 480; $sm.Save($shot); "screenshot $shot" } catch { "screenshot failed: $_" }
Stop-Mine
