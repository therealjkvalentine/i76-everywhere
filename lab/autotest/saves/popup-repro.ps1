<#
  popup-repro.ps1 - GARAGE-POPUP-STUCK.md section 6 (BACKLOG P1-19), steps 1-8 in one unattended run, sandbox only.

    powershell -ExecutionPolicy Bypass -File popup-repro.ps1 -Tag u32x [-Trials 2] [-SkipCursorProbe]
    $env:U32X_TEST_ENV = "I76_U32X_PUMPS=0"  -> the step-9 control (leg-b passes I76_U32X_* names through)

  1  garage-ui.ps1 -Start save009 -Row 9 (leg-b to the garage, game left running)
  2  engine row's PartRec file name -> "null" (read back; the game is killed at the end, never saved)
  3  DONE (UI 400,460) -> "CAN'T GET VERY FAR WITHOUT AN ENGINE"
  4  (trial 1) pointer probe while the popup is up: MoveTo-UI 150,150 / 500,350, read the shell mouse, capture
  5  (trial 1) click OK (318,262) with the game focused: baseline that the hit rect works
  6  DONE again; a notepad takes the foreground (the owner's Alt+Tab); gate read at 0.3 / 1 / 2 s
  7  notepad closed, Force-Foreground the game (or a click on its picture), click OK, wait 3 s, gate + mouse twice,
     CPU of i76.exe, capture; popup up or not is judged from the pixels of the popup panel
  8  garage-ui.ps1 -Close (kill, STRLKUP.DLL restored, lock removed)
  Trials repeat 6-7 while the popup keeps closing; a stuck popup ends the run.
  Results: runs\popup\<ts>-<tag>\log.txt + PNGs.
  2026-10-03 (section 9, F7 + modal pointer): -GameDir <lab folder>; -CloseWith click,enter,space (cycled per trial:
  how the popup is closed after the focus change); every probe also reads the u32x pointer window (class u32xVptr)
  and compares its hot spot with the shell mouse mapped onto the picture; ptr-*.png are CAPTUREBLT captures.
#>
param([string]$Tag = "u32x", [int]$Trials = 2, [switch]$SkipCursorProbe, [string]$Save = "save009", [int]$Row = 9,
      [string]$GameDir = "", [string[]]$CloseWith = @("click"))
$ErrorActionPreference = "Stop"
$CloseWith = @($CloseWith | ForEach-Object { $_ -split ',' } | Where-Object { $_ })
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Lab = "C:\Users\james\i76-uncap-lab"; $G = $(if ($GameDir) { $GameDir.TrimEnd([char]92) } else { Join-Path $Lab "game" })
$GdArg = @(); if ($GameDir) { $GdArg = @("-GameDir", $G) }
$I76GameDirInUse = $G
$ts = Get-Date -Format "yyyyMMdd-HHmmss"
$Out = Join-Path $Here "runs\popup\$ts-$Tag"; New-Item -ItemType Directory -Force $Out | Out-Null
$LogPath = Join-Path $Out "log.txt"
$T0 = [Diagnostics.Stopwatch]::StartNew()
function Log([string]$m) { $l = "{0,7:n2}s {1}" -f $T0.Elapsed.TotalSeconds, $m; Add-Content $LogPath $l -Encoding UTF8; Write-Host $l }

if (Get-Process i76 -ErrorAction SilentlyContinue) { throw "an i76 process is already running" }
Log ("tag {0}  u32x.dll md5 {1}  i76shell md5 {2}  U32X_TEST_ENV='{3}'" -f $Tag,
    (Get-FileHash "$G\u32x.dll" -Algorithm MD5).Hash.ToLower().Substring(0,8),
    (Get-FileHash "$G\i76shell.dll" -Algorithm MD5).Hash.ToLower().Substring(0,8), $env:U32X_TEST_ENV)

# ---- 1. to the garage ----
& powershell -ExecutionPolicy Bypass -File "$Here\garage-ui.ps1" -Start $Save -Row $Row -OutDir $Out @GdArg | ForEach-Object { Log "  $_" }
. "$Here\..\lib\focuslib.ps1"; . "$Here\..\lib\inputlib.ps1"; . "$Here\..\lib\maplib.ps1"; . "$Here\..\lib\modalptr.ps1"
trap { Log "ERROR: $_"; & powershell -ExecutionPolicy Bypass -File "$Here\garage-ui.ps1" -Close @GdArg | ForEach-Object { Log "  $_" }; exit 1 }
$proc = Get-GamePid
if ($proc -and $GameDir -and -not $proc.Path.StartsWith($G + "\", [StringComparison]::OrdinalIgnoreCase)) { Log "ABORT: game $($proc.Path) is not in $G"; exit 1 }
if (-not $proc) { Log "ABORT: no game after -Start"; exit 1 }
$myGame = $proc.Id
Init-CursorMap | Out-Null

Add-Type -TypeDefinition @"
using System; using System.Runtime.InteropServices; using System.Text;
public static class GP {
 [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(int a, bool i, int p);
 [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr a, byte[] b, int n, out IntPtr r);
 [DllImport("kernel32.dll")] public static extern bool WriteProcessMemory(IntPtr h, IntPtr a, byte[] b, int n, out IntPtr r);
 [DllImport("psapi.dll")] public static extern bool EnumProcessModulesEx(IntPtr h, IntPtr[] m, int cb, out int need, int f);
 [DllImport("psapi.dll")] public static extern int GetModuleBaseNameA(IntPtr h, IntPtr m, StringBuilder s, int n);
 [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
 [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
}
"@
$h = [GP]::OpenProcess(0x438, $false, $proc.Id)
$m = New-Object IntPtr[] 512; $n = 0; [void][GP]::EnumProcessModulesEx($h, $m, 4096, [ref]$n, 1)
$base = ($m[0..($n / [IntPtr]::Size - 1)] | Where-Object { $s = New-Object Text.StringBuilder 260; [void][GP]::GetModuleBaseNameA($h, $_, $s, 260); $s.ToString() -ieq "i76shell.dll" })[0].ToInt64()
$d = $base - 0x10000000
function RdB([long]$a, [int]$n = 4) { $b = New-Object byte[] $n; $r = [IntPtr]::Zero; [void][GP]::ReadProcessMemory($h, [IntPtr]$a, $b, $n, [ref]$r); $b }
function Rd32([long]$a) { [BitConverter]::ToInt32((RdB $a), 0) }
function St { $mo = Rd32 (0x100cc514 + $d); [pscustomobject]@{ Gate = (Rd32 (0x10043224 + $d)); X = (Rd32 ($mo + 0x2c)); Y = (Rd32 ($mo + 0x30)); BtnL = (Rd32 ($mo + 0x34)); Edge = (Rd32 ($mo + 0x10)) } }
function S([string]$tag) { $s = St; Log ("  S[{0}] gate={1} mouse=({2},{3}) btnL={4} edge={5} fg={6}" -f $tag, $s.Gate, $s.X, $s.Y, $s.BtnL, $s.Edge, $(if ([GP]::GetForegroundWindow() -eq $proc.MainWindowHandle) { "game" } else { "other" })); $s }
function Guard { $others = @(Get-Process i76 -ErrorAction SilentlyContinue | Where-Object { $_.Id -ne $myGame }); if ($others.Count) { Log "ABORT: an i76 process this script did not start appeared (pid $($others.Id))"; throw "foreign i76" } }
Log ("shell base 0x{0:X8}" -f $base)
$ss = "C:\Users\james\i76-map\shell\tools\shellstate.ps1"
if (Test-Path $ss) { & $ss -Once 2>$null | Select-Object -First 3 | ForEach-Object { Log "  state: $_" } }
[void](S "garage")

# ---- pixel judge: popup panel UI 179..460 x 194..286 ----
Add-Type -AssemblyName System.Drawing
function Panel([string]$png) {
    $bmp = [Drawing.Bitmap]::FromFile($png); $v = New-Object System.Collections.Generic.List[int]
    for ($y = 196; $y -lt 286; $y += 3) { for ($x = 181; $x -lt 459; $x += 3) { $c = $bmp.GetPixel($x, $y); $v.Add([int](($c.R + $c.G + $c.B) / 3)) } }
    $bmp.Dispose(); , $v.ToArray()
}
function Dist($a, $b) { $s = 0.0; for ($i = 0; $i -lt $a.Length; $i++) { $s += [math]::Abs($a[$i] - $b[$i]) }; $s / $a.Length }
function Shot([string]$name) { Start-Sleep -Milliseconds 300; $p = Join-Path $Out "$name.png"; [void](Capture-UI $p); $p }
function Judge([string]$png) {
    $v = Panel $png; $dp = Dist $v $script:PopupRef; $dg = Dist $v $script:GarageRef
    $up = $dp -lt $dg; Log ("  judge {0}: dist popup={1:n1} garage={2:n1} -> {3}" -f (Split-Path $png -Leaf), $dp, $dg, $(if ($up) { "POPUP UP" } else { "popup gone" })); $up
}

Force-Foreground $proc.MainWindowHandle | Out-Null
$script:GarageRef = Panel (Shot "garage")

# ---- 2. engine row file name -> "null" ----
$rec = Rd32 ((Rd32 ((Rd32 ((Rd32 (0x1005209c + $d)) + 8)))))
$orig = RdB ($rec + 0x2e) 8
Log ("  engine PartRec 0x{0:X8} name bytes before: {1} '{2}'" -f $rec, (($orig | ForEach-Object { $_.ToString("x2") }) -join " "), ([Text.Encoding]::ASCII.GetString($orig) -replace "`0.*", ""))
$w = [IntPtr]::Zero
[void][GP]::WriteProcessMemory($h, [IntPtr]($rec + 0x2e), [Text.Encoding]::ASCII.GetBytes("null`0"), 5, [ref]$w)
$rb = RdB ($rec + 0x2e) 5; $rbs = ($rb | ForEach-Object { $_.ToString("x2") }) -join " "
Log "  read back: $rbs"
if ($rbs -ne "6e 75 6c 6c 00") { Log "ABORT: poke did not land"; exit 1 }

# adaptive click: the owner aims at the drawn control; we aim through whichever mapping the shell mouse follows
# (after a focus change dgVoodoo's clip is released and the pointer stays in the FREE regime: UI = (x-760)/3)
function AimClick([int]$ux, [int]$uy, [string]$what) {
    MoveTo-UI $ux $uy; Start-Sleep -Milliseconds 300; $s = St
    if ([math]::Abs($s.X - $ux) -le 2 -and [math]::Abs($s.Y - $uy) -le 2) { Log "  $what aim via UI coords (shell mouse follows 1:1)" }
    else {
        $sc = UI-ToScreen $ux $uy; [void][GP]::SetCursorPos($sc[0], $sc[1]); Start-Sleep -Milliseconds 300; $s2 = St
        if ([math]::Abs($s2.X - $ux) -le 2 -and [math]::Abs($s2.Y - $uy) -le 2) { Log "  $what aim via SCREEN coords ($($sc[0]),$($sc[1])) (free-pointer regime)" }
        else { Log ("  {6} aim: shell mouse does not follow (UI try -> ({0},{1}), screen try -> ({2},{3})); clicking at UI {4},{5} blind" -f $s.X, $s.Y, $s2.X, $s2.Y, $ux, $uy, $what); MoveTo-UI $ux $uy; Start-Sleep -Milliseconds 200 }
    }
    [Inp]::mouse_event(0x2, 0, 0, 0, [IntPtr]::Zero); Start-Sleep -Milliseconds 80; [Inp]::mouse_event(0x4, 0, 0, 0, [IntPtr]::Zero)
}
function ClickOK([string]$tag) { AimClick 318 262 "OK" }
function P([string]$tag) {
    Start-Sleep -Milliseconds 200; $s = St; $w = Get-ModalPtr $myGame; $e = Ptr-Expect $s.X $s.Y
    $dx = $w.X - $e[0]; $dy = $w.Y - $e[1]
    Log ("  P[{0}] shell mouse ({1},{2}) -> expect arrow at ({3},{4}); u32x arrow exists={5} visible={6} at ({7},{8}) delta ({9},{10})" -f $tag, $s.X, $s.Y, $e[0], $e[1], $w.Exists, $w.Visible, $w.X, $w.Y, $dx, $dy)
    [void](Capture-UIBlt (Join-Path $Out "ptr-$tag.png"))
    [pscustomobject]@{ Visible = $w.Visible; Ok = ($w.Visible -and [math]::Abs($dx) -le 4 -and [math]::Abs($dy) -le 4); X = $w.X; Y = $w.Y }
}
function CloseBy([string]$how) {
    switch ($how) {
        "enter" { Force-Foreground $proc.MainWindowHandle | Out-Null; Start-Sleep -Milliseconds 200; Log "  close by Enter"; Close-ByKey 0x0D }
        "space" { Force-Foreground $proc.MainWindowHandle | Out-Null; Start-Sleep -Milliseconds 200; Log "  close by Space"; Close-ByKey 0x20 }
        default { ClickOK "ok" }
    }
}
function Done([string]$name) {
    Force-Foreground $proc.MainWindowHandle | Out-Null
    AimClick 400 460 "DONE"; Start-Sleep -Milliseconds 900
    $p = Shot $name; [void](S $name); $p
}

$result = @()
try {
    $p1 = Done "popup1"; $script:PopupRef = Panel $p1
    Log ("  popup1 vs garage panel distance {0:n1} (must be large for the judge to mean anything)" -f (Dist $script:PopupRef $script:GarageRef))
    if (-not $SkipCursorProbe) {
        # ---- 4. competing explanation: does the pointer (shell mouse, drawn pencil) follow while the popup is up? ----
        MoveTo-UI 150 150; Start-Sleep -Milliseconds 500; [void](S "cur150"); [void](Shot "cur150"); $pa = P "cur150"
        MoveTo-UI 500 350; Start-Sleep -Milliseconds 500; [void](S "cur500"); [void](Shot "cur500"); $pb = P "cur500"
        $result += "pointer probe (focused): 150,150 {0}; 500,350 {1}; moved {2}" -f $(if ($pa.Ok) { "on point" } else { "OFF" }), $(if ($pb.Ok) { "on point" } else { "OFF" }), ($pa.X -ne $pb.X -or $pa.Y -ne $pb.Y)
        # ---- 5. baseline OK click, focused ----
        ClickOK "ok-baseline"; Start-Sleep -Milliseconds 1200; [void](S "after-ok-baseline")
        $up = Judge (Shot "after-ok-baseline")
        $result += "baseline OK (focused): $(if ($up) { 'STUCK' } else { 'closed' })"
        if ($up) { Log "baseline OK did not close the popup - stopping"; throw "baseline" }
    }
    for ($t = 1; $t -le $Trials; $t++) {
        Guard
        Log "---- trial ${t}: DONE, focus change, back, OK ----"
        $pt = Done "popup-t$t"
        if (-not (Judge $pt)) { Log "  DONE did not raise the popup - trial invalid, stopping"; $result += "trial ${t}: INVALID (no popup)"; break }
        $np = Start-Process notepad -PassThru
        $nh = [IntPtr]::Zero; for ($i = 0; $i -lt 40 -and $nh -eq [IntPtr]::Zero; $i++) { Start-Sleep -Milliseconds 100; $np.Refresh(); $nh = $np.MainWindowHandle }
        $ff = Force-Foreground $nh
        Log "  notepad pid $($np.Id) foreground: $ff"
        Start-Sleep -Milliseconds 300; $a = S "away0.3s"; Start-Sleep -Milliseconds 700; $b = S "away1s"; Start-Sleep -Milliseconds 1000; $c = S "away2s"
        Stop-Process -Id $np.Id -Force; Start-Sleep -Milliseconds 400
        $pump = Test-WindowPumping $proc.MainWindowHandle
        $back = Force-Foreground $proc.MainWindowHandle
        Log "  game pumping (WM_NULL answered): $pump; Force-Foreground: $back"
        if (-not $back) {
            # as the owner would: click the game picture (a black-bar spot, no control) to activate it
            $sc = UI-ToScreen -40 240; [void][GP]::SetCursorPos($sc[0], $sc[1]); Start-Sleep -Milliseconds 200
            [Inp]::mouse_event(0x2, 0, 0, 0, [IntPtr]::Zero); Start-Sleep -Milliseconds 80; [Inp]::mouse_event(0x4, 0, 0, 0, [IntPtr]::Zero); Start-Sleep -Milliseconds 600
            Log "  activated by a click on the picture: fg game = $([GP]::GetForegroundWindow() -eq $proc.MainWindowHandle)"
        }
        [void](S "back")
        MoveTo-UI 318 262; Start-Sleep -Milliseconds 400; $pk = P "back-t$t"
        $how = $CloseWith[($t - 1) % $CloseWith.Count]
        CloseBy $how
        Start-Sleep -Seconds 3
        $cpu0 = (Get-Process -Id $proc.Id).TotalProcessorTime.TotalMilliseconds
        $e = S "after3s"; Start-Sleep -Seconds 2; $f = S "after5s"
        $cpu = ((Get-Process -Id $proc.Id).TotalProcessorTime.TotalMilliseconds - $cpu0) / 2000.0
        Log ("  i76 CPU over 2 s: {0:n2} cores" -f $cpu)
        $up = Judge (Shot "after-ok-t$t")
        $pg = Get-ModalPtr $myGame
        $line = "trial ${t} [$how; arrow after focus back: $(if ($pk.Ok) { 'on point' } else { 'OFF' }), after close visible=$($pg.Visible)]: gate away {0}/{1}/{2}, after OK {3}/{4}, mouse after ({5},{6}), pumping={7}, popup {8}" -f $a.Gate, $b.Gate, $c.Gate, $e.Gate, $f.Gate, $f.X, $f.Y, $pump, $(if ($up) { "STUCK" } else { "closed" })
        Log $line; $result += $line
        if ($up) {
            # one more chance as a player would: a second click on OK
            ClickOK "ok-t$t-retry"; Start-Sleep -Seconds 2; [void](S "retry")
            $up2 = Judge (Shot "after-ok-t$t-retry"); $result += "trial ${t} retry click: $(if ($up2) { 'STUCK' } else { 'closed' })"
            if ($up2) { break }
        }
    }
} finally {
    Log "---- results ----"; $result | ForEach-Object { Log "  $_" }
    Log "---- 8. close (no save) ----"
    & powershell -ExecutionPolicy Bypass -File "$Here\garage-ui.ps1" -Close @GdArg | ForEach-Object { Log "  $_" }
}
