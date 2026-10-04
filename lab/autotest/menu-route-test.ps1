<#
  menu-route-test.ps1 - enter a mission THROUGH THE MENUS (enter-melee.ps1: cold launch -> MELEE -> INSTANT MELEE ->
  ENTER AREA) with the i76-everywhere proxy and a switch set, and report whether the engine came up: player entity,
  frame counter advancing, window visible, proxy log lines. proxy-run.ps1 boots straight into a mission and never
  exercises the shell -> engine hand-over; this does.

    .\menu-route-test.ps1 -Tag a -Env @{ I76_GLIDE_REFRESH = "120" }
    .\menu-route-test.ps1 -Tag c -Env @{ I76_GLIDE_REFRESH = "120" } -U32x aug16
    .\menu-route-test.ps1 -GameDir "..\game-dd-20261003\Interstate 76" -KeepInstalledDll   # another folder inside the lab, its own proxy

  -GameDir: default the sandbox (<lab>\game); lib\gamedir.ps1 refuses anything outside the lab and the playable installs.
  -KeepInstalledDll: do not install music-fix\Strlkup.dll for the run. -DryRun: resolved paths only, nothing started.
#>
param([string]$Tag = "a", [hashtable]$Env = @{}, [ValidateSet("keep", "aug16", "new")] [string]$U32x = "keep", [ValidateSet("all", "fixed", "stock")] [string]$Set = "all",
      [string]$GameDir = "", [switch]$KeepInstalledDll, [switch]$DryRun)
$ErrorActionPreference = "Continue"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
. "$Here\lib\gamedir.ps1"
try { $G = Resolve-LabGameDir $GameDir } catch { "$_"; exit 1 }
$I76GameDirInUse = $G                  # memlib: prefer this folder's process
$log = "$G\mciproxy.log"
if ($DryRun) {
    "menu-route-test DRY RUN (nothing started): game=$G set=$Set u32x=$U32x lock=$G\.console-test.lock log=$log"
    "  proxy $(if ($KeepInstalledDll) { "as installed ($G\STRLKUP.DLL), no swap" } else { "music-fix\Strlkup.dll -> $G\STRLKUP.DLL (original kept as STRLKUP.DLL.pretest)" })"
    & powershell -ExecutionPolicy Bypass -File "$Here\enter-melee.ps1" -GameDir $G -DryRun 2>&1 | ForEach-Object { "  | $_" }
    exit 0
}
if (Get-Process i76* -ErrorAction SilentlyContinue) { "an i76 process is running"; exit 1 }
if (Test-Path "$G\.console-test.lock") { "lock held"; exit 1 }
Set-Content "$G\.console-test.lock" "menu-route-test $Tag $PID"
$u32xBak = $null
try {
    if (-not $KeepInstalledDll) {
        if (-not (Test-Path "$G\STRLKUP.DLL.pretest")) { Copy-Item "$G\STRLKUP.DLL" "$G\STRLKUP.DLL.pretest" }
        Copy-Item "C:\Users\james\i76-everywhere\music-fix\Strlkup.dll" "$G\STRLKUP.DLL" -Force
    }
    if ($U32x -ne "keep") {
        $u32xBak = "$G\u32x.dll.menutest"; Copy-Item "$G\u32x.dll" $u32xBak -Force
        $src = if ($U32x -eq "aug16") { "$G\u32x.dll.aug16" } else { "C:\Users\james\i76-uncap-lab\src\u32x_new.dll" }
        Copy-Item $src "$G\u32x.dll" -Force
    }
    foreach ($v in "I76_HIRES_CLOCK", "I76_FIXED_STEP", "I76_FRAMERATE_FIXES", "I76_ENGINE_DT_FIX", "I76_RENDER_INTERP", "I76_FPS_CAP", "I76_FIX_HEALTH_PCT",
                   "I76_FIX_LABEL_TABLE", "I76_FAR_CLIP", "I76_TELEMETRY", "I76_MISSION", "I76_SKIP_MOVIES", "I76_GLIDE_REFRESH", "I76_TRAINER", "I76_CD_LOG", "I76_CWD_FIX") { Remove-Item "Env:$v" -ErrorAction SilentlyContinue }
    if ($Set -ne "stock") { $env:I76_HIRES_CLOCK = "1"; $env:I76_FIXED_STEP = "24"; $env:I76_FRAMERATE_FIXES = "1"; $env:I76_ENGINE_DT_FIX = "1"; $env:I76_RENDER_INTERP = "1" }
    if ($Set -eq "all") { $env:I76_FIX_HEALTH_PCT = "1"; $env:I76_FIX_LABEL_TABLE = "1"; $env:I76_FAR_CLIP = "1800"; $env:I76_TELEMETRY = "1" }
    foreach ($k in $Env.Keys) { Set-Item "Env:$k" $Env[$k] }
    $env:I76MUSIC_LOG = "1"
    $len = if (Test-Path $log) { (Get-Item $log).Length } else { 0 }
    "[$Tag] set=$Set u32x=$U32x ($((Get-FileHash "$G\u32x.dll" -Algorithm MD5).Hash.Substring(0,8))) env: $(($Env.Keys | ForEach-Object { "$_=$($Env[$_])" }) -join ' ')"
    $out = & powershell -ExecutionPolicy Bypass -File "$Here\enter-melee.ps1" -GameDir $G 2>&1 | Out-String
    $rc = $LASTEXITCODE
    . "$Here\lib\memlib.ps1"
    $p = Get-Process i76 -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($p) {
        $c = Mem-Open; $f0 = Mem-I32 $c 0x5a7e1c; Start-Sleep -Seconds 2; $f1 = Mem-I32 $c 0x5a7e1c
        "[$Tag] enter-melee exit $rc | player 0x{0:x} | mode 0x{1:x} gstate {2} | frames/s {3} | window '{4}' responding {5}" -f (Mem-PlayerEntity $c), (Mem-I32 $c 0x4fe534), (Mem-I32 $c 0x4c2164), (($f1 - $f0) / 2), $p.MainWindowTitle, $p.Responding
        Mem-Close $c
        Add-Type -Name V -Namespace MR -MemberDefinition '[DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h); [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h); [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();' -ErrorAction SilentlyContinue
        "[$Tag] hwnd 0x{0:x} visible {1} minimized {2} foreground {3}" -f [int64]$p.MainWindowHandle, [MR.V]::IsWindowVisible($p.MainWindowHandle), [MR.V]::IsIconic($p.MainWindowHandle), ([MR.V]::GetForegroundWindow() -eq $p.MainWindowHandle)
        if ($rc -ne 0) { "[$Tag] FAILED - stacks:"; python "$Here\..\tools\instruments\stackscan.py" 2>&1 | Where-Object { $_ -match "i76|I76SHELL|ZGLIDE|u32x|Strlkup|glide2x|DDRAW|first" } | Select-Object -First 12 | ForEach-Object { "    " + $_.Substring(0, [Math]::Min(900, $_.Length)) } }
        "[$Tag] shell: " +((& powershell -ExecutionPolicy Bypass -File C:\Users\james\i76-map\shell\tools\shellstate.ps1 -Once 2>$null | Select-Object -Skip 1 -First 1) -replace "\s+", " ")
    } else { "[$Tag] enter-melee exit $rc | the game is NOT running (crashed or exited)" }
    ($out -split "`n" | Select-Object -Last 3) | ForEach-Object { "    $_".TrimEnd() }
    $b = if (Test-Path $log) { [IO.File]::ReadAllBytes($log) } else { [byte[]]@() }; if ($len -gt $b.Length) { $len = 0 }; $new = [Text.Encoding]::GetEncoding(28591).GetString($b, $len, $b.Length - $len)
    ($new -split "`n") | Where-Object { $_ -match "glide-refresh|CRASH|MSGBOX|UNEXPECTED" } | Select-Object -First 10 | ForEach-Object { "    " + $_.Substring(0, [Math]::Min(200, $_.Length)) }
} finally {
    Get-Process | Where-Object { $_.ProcessName -like "i76*" } | Stop-Process -Force -ErrorAction SilentlyContinue; Start-Sleep -Seconds 1
    if (Test-Path "$G\STRLKUP.DLL.pretest") { Copy-Item "$G\STRLKUP.DLL.pretest" "$G\STRLKUP.DLL" -Force; Remove-Item "$G\STRLKUP.DLL.pretest" }
    if ($u32xBak) { Copy-Item $u32xBak "$G\u32x.dll" -Force; Remove-Item $u32xBak }
    Remove-Item "$G\.console-test.lock" -ErrorAction SilentlyContinue
}
