<#
  reminder-repro.ps1 - the "REMEMBER, USE THE SAVE BOOKMARK BUTTON" reminder (owner report 2026-10-03), sandbox only.

    powershell -ExecutionPolicy Bypass -File reminder-repro.ps1 -Tag fix696577 [-FocusChange] [-Save save001 -Row 1]
    $env:U32X_TEST_ENV = "I76_U32X_MODAL_PUMP=1"  -> the kill-switch control (leg-b passes I76_U32X_* names through)

  The reminder is Modal_ImageOk(0x20, ...) 0x1001933c, raised by the inventory/salvage screen fn 0x10018e90 case 0xc
  (ACCEPT SALVAGE) once per session when scene [0x100d2180]==2 and [[0x100d2164]]==1 (flag 0x100d1d90). A bookmark
  "scene 2 st 1 plays 3" reaches it: leg-b -StopAtGarage clicks ACCEPT SALVAGE, the reminder takes over, and leg-b's
  wait for the garage times out (expected; the game is left running with -NoQuit).

  1  garage-ui.ps1 -Start <save> -Row <n>   (leg-b; ends at "garage not reached" while the reminder is up)
  2  state: screen, gate, reminder flag, shell mouse; capture
  3  pointer probe: MoveTo-UI 150,150 / 500,350, read the shell mouse
  4  (-FocusChange) a notepad takes the foreground for 2 s, then the game is brought back
  5  click OK (318,262); 2 s; state + capture. Closed = screen 0xC00F (garage). One retry click if not.
  6  close: WM_CLOSE + kill of THIS pid only, STRLKUP.DLL restored, lock removed
#>
param([string]$Tag = "u32x", [string]$Save = "save001", [int]$Row = 1, [switch]$FocusChange, [int]$RowUy = -1, [string]$CloseWith = "click")
$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Lab = "C:\Users\james\i76-uncap-lab"; $G = Join-Path $Lab "game"
$I76GameDirInUse = $G
$ts = Get-Date -Format "yyyyMMdd-HHmmss"
$Out = Join-Path $Here "runs\reminder\$ts-$Tag"; New-Item -ItemType Directory -Force $Out | Out-Null
$LogPath = Join-Path $Out "log.txt"
$T0 = [Diagnostics.Stopwatch]::StartNew()
function Log([string]$m) { $l = "{0,7:n2}s {1}" -f $T0.Elapsed.TotalSeconds, $m; Add-Content $LogPath $l -Encoding UTF8; Write-Host $l }

if (Get-Process i76 -ErrorAction SilentlyContinue) { throw "an i76 process is already running" }
Log ("tag {0}  u32x.dll md5 {1}  i76shell md5 {2}  U32X_TEST_ENV='{3}'  focusChange={4}" -f $Tag,
    (Get-FileHash "$G\u32x.dll" -Algorithm MD5).Hash.ToLower().Substring(0,8),
    (Get-FileHash "$G\i76shell.dll" -Algorithm MD5).Hash.ToLower().Substring(0,8), $env:U32X_TEST_ENV, [bool]$FocusChange)

& powershell -ExecutionPolicy Bypass -File "$Here\garage-ui.ps1" -Start $Save -Row $Row -RowUy $RowUy -OutDir $Out | ForEach-Object { Log "  $_" }
. "$Here\..\lib\focuslib.ps1"; . "$Here\..\lib\inputlib.ps1"; . "$Here\..\lib\maplib.ps1"; . "$Here\..\lib\modalptr.ps1"
$proc = Get-GamePid
if (-not $proc) { Log "ABORT: no game after -Start"; exit 1 }
$myGame = $proc.Id

function CloseMine {
    try { $p = Get-Process -Id $myGame -ErrorAction SilentlyContinue
        if ($p) { Add-Type -Name SM4 -Namespace P -MemberDefinition '[DllImport("user32.dll")] public static extern bool PostMessageA(IntPtr h, uint m, IntPtr w, IntPtr l);' -ErrorAction SilentlyContinue
            [void][P.SM4]::PostMessageA($p.MainWindowHandle, 0x0010, [IntPtr]::Zero, [IntPtr]::Zero); Start-Sleep -Seconds 3
            $p = Get-Process -Id $myGame -ErrorAction SilentlyContinue; if ($p) { Stop-Process -Id $myGame -Force; Start-Sleep -Seconds 1 } }
    } catch { Log "close error: $_" }
    if (Test-Path "$G\STRLKUP.DLL.pretest") { Copy-Item "$G\STRLKUP.DLL.pretest" "$G\STRLKUP.DLL" -Force; Remove-Item "$G\STRLKUP.DLL.pretest"; Log "  STRLKUP.DLL restored" }
    Remove-Item "$G\.console-test.lock" -ErrorAction SilentlyContinue; Log "  closed pid $myGame"
}

Add-Type -TypeDefinition @"
using System; using System.Runtime.InteropServices; using System.Text;
public static class GR {
 [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(int a, bool i, int p);
 [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr a, byte[] b, int n, out IntPtr r);
 [DllImport("psapi.dll")] public static extern bool EnumProcessModulesEx(IntPtr h, IntPtr[] m, int cb, out int need, int f);
 [DllImport("psapi.dll")] public static extern int GetModuleBaseNameA(IntPtr h, IntPtr m, StringBuilder s, int n);
 [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
 [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
}
"@
$result = @()
try {
    Init-CursorMap | Out-Null
    $h = [GR]::OpenProcess(0x410, $false, $proc.Id)
    $m = New-Object IntPtr[] 512; $n = 0; [void][GR]::EnumProcessModulesEx($h, $m, 4096, [ref]$n, 1)
    $base = ($m[0..($n / [IntPtr]::Size - 1)] | Where-Object { $s = New-Object Text.StringBuilder 260; [void][GR]::GetModuleBaseNameA($h, $_, $s, 260); $s.ToString() -ieq "i76shell.dll" })[0].ToInt64()
    $d = $base - 0x10000000
    function RdB([long]$a, [int]$n = 4) { $b = New-Object byte[] $n; $r = [IntPtr]::Zero; [void][GR]::ReadProcessMemory($h, [IntPtr]$a, $b, $n, [ref]$r); $b }
    function Rd32([long]$a) { [BitConverter]::ToInt32((RdB $a), 0) }
    function St { $mo = Rd32 (0x100cc514 + $d)
        [pscustomobject]@{ Screen = (Rd32 (0x100d2168 + $d)); Sfn = (Rd32 (0x100d219c + $d)); Gate = (Rd32 (0x10043224 + $d)); Flag = (Rd32 (0x100d1d90 + $d))
                           Scene = (Rd32 (Rd32 (0x100d2180 + $d))); X = (Rd32 ($mo + 0x2c)); Y = (Rd32 ($mo + 0x30)); BtnL = (Rd32 ($mo + 0x34)); Edge = (Rd32 ($mo + 0x10)) } }
    function S([string]$tag) { $s = St; Log ("  S[{0}] screen=0x{1:X} sfn=0x{2:X8} gate={3} reminderFlag={4} scene={5} mouse=({6},{7}) btnL={8} edge={9} fg={10}" -f $tag, $s.Screen, $s.Sfn, $s.Gate, $s.Flag, $s.Scene, $s.X, $s.Y, $s.BtnL, $s.Edge, $(if ([GR]::GetForegroundWindow() -eq $proc.MainWindowHandle) { "game" } else { "other" })); $s }
    function Shot([string]$name) { Start-Sleep -Milliseconds 300; $p = Join-Path $Out "$name.png"; [void](Capture-UI $p); $p }
    function AimClick([int]$ux, [int]$uy, [string]$what) {
        MoveTo-UI $ux $uy; Start-Sleep -Milliseconds 300; $s = St
        if ([math]::Abs($s.X - $ux) -le 2 -and [math]::Abs($s.Y - $uy) -le 2) { Log "  $what aim via UI coords" }
        else {
            $sc = UI-ToScreen $ux $uy; [void][GR]::SetCursorPos($sc[0], $sc[1]); Start-Sleep -Milliseconds 300; $s2 = St
            if ([math]::Abs($s2.X - $ux) -le 2 -and [math]::Abs($s2.Y - $uy) -le 2) { Log "  $what aim via SCREEN coords ($($sc[0]),$($sc[1]))" }
            else { Log ("  {4} aim: shell mouse does not follow (UI try -> ({0},{1}), screen try -> ({2},{3})); clicking blind" -f $s.X, $s.Y, $s2.X, $s2.Y, $what); MoveTo-UI $ux $uy; Start-Sleep -Milliseconds 200 }
        }
        [Inp]::mouse_event(0x2, 0, 0, 0, [IntPtr]::Zero); Start-Sleep -Milliseconds 80; [Inp]::mouse_event(0x4, 0, 0, 0, [IntPtr]::Zero)
    }
    Log ("shell base 0x{0:X8}" -f $base)
    $s0 = S "reminder?"; [void](Shot "reminder")
    if ($s0.Screen -ne 0xC017 -or $s0.Flag -ne 1) { Log "  NOTE: not the expected reminder state (want screen 0xC017, flag 1)"; $result += "INVALID: reminder not up (screen 0x{0:X} flag {1})" -f $s0.Screen, $s0.Flag; throw "invalid" }
    $sc0 = (Get-Process -Id $myGame).TotalProcessorTime.TotalMilliseconds; Start-Sleep 1
    Log ("  i76 CPU in the modal: {0:n2} cores; WM_NULL answered: {1}" -f (((Get-Process -Id $myGame).TotalProcessorTime.TotalMilliseconds - $sc0) / 1000.0), (Test-WindowPumping $proc.MainWindowHandle))
    function P([string]$tag) {
        Start-Sleep -Milliseconds 200; $s = St; $w = Get-ModalPtr $myGame; $e = Ptr-Expect $s.X $s.Y
        $dx = $w.X - $e[0]; $dy = $w.Y - $e[1]
        Log ("  P[{0}] shell mouse ({1},{2}) -> expect arrow at ({3},{4}); u32x arrow exists={5} visible={6} at ({7},{8}) delta ({9},{10})" -f $tag, $s.X, $s.Y, $e[0], $e[1], $w.Exists, $w.Visible, $w.X, $w.Y, $dx, $dy)
        [void](Capture-UIBlt (Join-Path $Out "ptr-$tag.png"))
        ($w.Visible -and [math]::Abs($dx) -le 4 -and [math]::Abs($dy) -le 4)
    }
    MoveTo-UI 150 150; Start-Sleep -Milliseconds 500; [void](S "cur150"); $pa = P "cur150"
    MoveTo-UI 500 350; Start-Sleep -Milliseconds 500; [void](S "cur500"); $pb = P "cur500"
    $result += "pointer probe: 150,150 {0}; 500,350 {1}" -f $(if ($pa) { "on point" } else { "OFF" }), $(if ($pb) { "on point" } else { "OFF" })
    if ($FocusChange) {
        $np = Start-Process notepad -PassThru
        $nh = [IntPtr]::Zero; for ($i = 0; $i -lt 40 -and $nh -eq [IntPtr]::Zero; $i++) { Start-Sleep -Milliseconds 100; $np.Refresh(); $nh = $np.MainWindowHandle }
        Log "  notepad foreground: $(Force-Foreground $nh)"
        Start-Sleep -Milliseconds 300; [void](S "away0.3s"); Start-Sleep -Milliseconds 1700; [void](S "away2s")
        Stop-Process -Id $np.Id -Force; Start-Sleep -Milliseconds 400
        $back = Force-Foreground $proc.MainWindowHandle; Log "  Force-Foreground back: $back"
        if (-not $back) { $sc = UI-ToScreen -40 240; [void][GR]::SetCursorPos($sc[0], $sc[1]); Start-Sleep -Milliseconds 200
            [Inp]::mouse_event(0x2, 0, 0, 0, [IntPtr]::Zero); Start-Sleep -Milliseconds 80; [Inp]::mouse_event(0x4, 0, 0, 0, [IntPtr]::Zero); Start-Sleep -Milliseconds 600 }
        [void](S "back")
    } else { Force-Foreground $proc.MainWindowHandle | Out-Null; Start-Sleep -Milliseconds 300 }
    MoveTo-UI 318 262; Start-Sleep -Milliseconds 400; $pk = P "before-close"
    $result += "pointer before close: $(if ($pk) { 'on point' } else { 'OFF' })"
    switch ($CloseWith) {
        "enter" { Force-Foreground $proc.MainWindowHandle | Out-Null; Start-Sleep -Milliseconds 200; Log "  close by Enter"; Close-ByKey 0x0D }
        "space" { Force-Foreground $proc.MainWindowHandle | Out-Null; Start-Sleep -Milliseconds 200; Log "  close by Space"; Close-ByKey 0x20 }
        default { AimClick 318 262 "OK" }
    }
    Start-Sleep -Seconds 2
    $s1 = S "after-ok"; [void](Shot "after-ok")
    $closed = ($s1.Screen -eq 0xC00F)
    if (-not $closed) {
        AimClick 318 262 "OK retry"; Start-Sleep -Seconds 2; $s2 = S "after-retry"; [void](Shot "after-retry"); $closed2 = ($s2.Screen -eq 0xC00F)
        $result += "reminder: STUCK after OK (gate {0}, mouse ({1},{2})); retry: {3}" -f $s1.Gate, $s1.X, $s1.Y, $(if ($closed2) { "closed" } else { "STUCK" })
    } else { $result += "reminder: closed by $CloseWith -> garage (gate {0}), arrow visible after: {1}" -f $s1.Gate, (Get-ModalPtr $myGame).Visible }
} catch { if ("$_" -ne "invalid") { Log "ERROR: $_" } }
finally {
    Log "---- results ----"; $result | ForEach-Object { Log "  RESULT $_" }
    CloseMine
}

