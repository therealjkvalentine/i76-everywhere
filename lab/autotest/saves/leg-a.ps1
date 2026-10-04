<#
  leg-a.ps1 - SAVES-STATE-AND-TEST-PLAN.md section 4 Leg A (save a bookmark) in the SANDBOX game, unattended.

    powershell -ExecutionPolicy Bypass -File leg-a.ps1 [-Mode enter|type] [-RowUy 261] [-NoQuit]

  Mode enter : A1..A9, A10a (Enter on the empty/pre-filled name -> overwrite prompt or direct save), A11, A12, quit.
  Mode type  : A1..A9, A10b (type AUTOSAVE1 by three escalating methods, the name buffer at i76shell+0x57f3c read
               after each), Enter, A12, quit.

  Hard rules (the brief): sandbox only (C:\Users\james\i76-uncap-lab\game); refuses if an i76* process runs or the
  .console-test.lock exists; backs the save set up to save-backup-<ts>\ with md5s before the first launch; installs
  music-fix\Strlkup.dll over STRLKUP.DLL after copying the original to STRLKUP.DLL.pretest and restores it in finally
  (TEST-FRAMERATE.ps1 convention); I76MUSIC_LOG=1 and no other I76_* variable; the game is killed at the end
  (WM_CLOSE first, Stop-Process after 10 s).

  Every step is confirmed by STATE read from the process (shell globals per shell\SCREENS.md, the same addresses
  shellstate.ps1 reads), with a screenshot beside it for the report. Output: runs\<ts>\log.txt, step-*.png,
  snap*.json, parse*.txt.
#>
param(
    [ValidateSet("enter", "type")] [string]$Mode = "enter",
    [int]$RowUy = 261,                 # A5: harness-measured 3rd row (enter-mission5.ps1 -SceneY 782 -> UI y 261)
    [string]$TypeText = "AUTOSAVE1",
    [switch]$NoQuit
)
$ErrorActionPreference = "Stop"
$Lab  = "C:\Users\james\i76-uncap-lab"
$G    = Join-Path $Lab "game"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$NewDll = "C:\Users\james\i76-everywhere\music-fix\Strlkup.dll"
$Dll = Join-Path $G "STRLKUP.DLL"; $BakDll = "$Dll.pretest"
$Lock = Join-Path $G ".console-test.lock"
$ts = Get-Date -Format "yyyyMMdd-HHmmss"
$Run = Join-Path $Here "runs\$ts-$Mode"; New-Item -ItemType Directory -Force $Run | Out-Null
$LogPath = Join-Path $Run "log.txt"
$T0 = [Diagnostics.Stopwatch]::StartNew()
function Log([string]$m, [string]$c = "Gray") {
    $line = "{0,8:n2}s {1}" -f $T0.Elapsed.TotalSeconds, $m
    Add-Content -Path $LogPath -Value $line -Encoding UTF8; Write-Host $line -ForegroundColor $c
}

. "$Lab\autotest\lib\focuslib.ps1"
. "$Lab\autotest\lib\inputlib.ps1"
. "$Lab\autotest\lib\uiclick.ps1"

# ---------------------------------------------------------------- process memory (read-only) -------------------
Add-Type -TypeDefinition @"
using System; using System.Runtime.InteropServices; using System.Text;
public static class SM {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(int a, bool i, int pid);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr a, byte[] b, int n, out IntPtr r);
  [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
  [DllImport("psapi.dll")] public static extern bool EnumProcessModulesEx(IntPtr h, IntPtr[] m, int cb, out int need, int flag);
  [DllImport("psapi.dll", CharSet=CharSet.Ansi)] public static extern int GetModuleBaseNameA(IntPtr h, IntPtr m, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool PostMessageA(IntPtr h, uint msg, IntPtr w, IntPtr l);
  [DllImport("user32.dll")] public static extern bool IsHungAppWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern uint SendInput(uint n, INPUT[] inputs, int size);
  [DllImport("user32.dll")] public static extern uint MapVirtualKeyA(uint code, uint type);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
  [StructLayout(LayoutKind.Sequential)] public struct KEYBDINPUT { public ushort wVk; public ushort wScan; public uint dwFlags; public uint time; public IntPtr dwExtraInfo; }
  [StructLayout(LayoutKind.Explicit)] public struct INPUTUNION { [FieldOffset(0)] public KEYBDINPUT ki; [FieldOffset(0)] public long pad1; [FieldOffset(8)] public long pad2; [FieldOffset(16)] public long pad3; [FieldOffset(24)] public long pad4; }
  [StructLayout(LayoutKind.Sequential)] public struct INPUT { public uint type; public INPUTUNION u; }
  public static long Base(IntPtr h, string name) {
    IntPtr[] m = new IntPtr[1024]; int need;
    if (!EnumProcessModulesEx(h, m, m.Length * IntPtr.Size, out need, 0x01)) return 0;
    int n = need / IntPtr.Size;
    for (int i = 0; i < n; i++) { var sb = new StringBuilder(260); GetModuleBaseNameA(h, m[i], sb, 260);
      if (string.Equals(sb.ToString(), name, StringComparison.OrdinalIgnoreCase)) return m[i].ToInt64(); }
    return 0;
  }
  public static byte[] Read(IntPtr h, long a, int n) { var b = new byte[n]; IntPtr r; if (!ReadProcessMemory(h, new IntPtr(a), b, n, out r)) return null; return b; }
  public static uint U32(IntPtr h, long a) { var b = Read(h, a, 4); if (b == null) return 0xFFFFFFFF; return BitConverter.ToUInt32(b, 0); }
  public static int I32(IntPtr h, long a) { var b = Read(h, a, 4); if (b == null) return int.MinValue; return BitConverter.ToInt32(b, 0); }
  // SendInput with KEYEVENTF_SCANCODE (0x8), key up adds 0x2
  public static uint KeyScan(ushort scan, bool up) {
    var inp = new INPUT[1]; inp[0].type = 1; inp[0].u.ki.wVk = 0; inp[0].u.ki.wScan = scan; inp[0].u.ki.dwFlags = (uint)(0x8 | (up ? 0x2 : 0));
    return SendInput(1, inp, Marshal.SizeOf(typeof(INPUT)));
  }
}
"@

$TblScreen = @{}; @{ 0xC00D="choose-vehicle"; 0xC00E="main-menu"; 0xC00F="garage"; 0xC015="post-mission"; 0xC017="inventory+salvage";
  0xC01D="load-bookmark(exec)"; 0xC01E="enter-reconfig"; 0xC01F="parts-catalog"; 0xC020="mission-grid"; 0xC022="new-trip"; 0xC008="return" }.GetEnumerator() | ForEach-Object { $TblScreen[("{0:x8}" -f [int64]$_.Key)] = $_.Value }
$TblSfn = @{}; @{ 0x10025a50="main-menu"; 0x10023c20="choose-vehicle"; 0x10003e70="garage"; 0x100246e0="post-mission"; 0x10018e90="inventory";
  0x10025910="parts-catalog"; 0x1001f480="mission-grid"; 0x10016c80="new-trip" }.GetEnumerator() | ForEach-Object { $TblSfn[("{0:x8}" -f [int64]$_.Key)] = $_.Value }
$TblMfn = @{}; @{ 0x1000e6b0="Options"; 0x10014cd0="SaveBookmark"; 0x10013060="LoadBookmark"; 0x10011dc0="ExitGame"; 0x10014410="PlayOptions" }.GetEnumerator() | ForEach-Object { $TblMfn[("{0:x8}" -f [int64]$_.Key)] = $_.Value }
function Nm($tbl, $v) { $n = $tbl[("{0:x8}" -f [int64]$v)]; if ($n) { $n } else { "-" } }

$script:H = [IntPtr]::Zero; $script:D = 0; $script:Proc = $null
function Attach {
    $script:Proc = Get-GamePid
    if (-not $script:Proc) { throw "sandbox i76 not running" }
    if ($script:H -ne [IntPtr]::Zero) { [void][SM]::CloseHandle($script:H) }
    $script:H = [SM]::OpenProcess(0x0410, $false, $script:Proc.Id)
    if ($script:H -eq [IntPtr]::Zero) { throw "OpenProcess failed" }
    $base = [SM]::Base($script:H, "i76shell.dll")
    if ($base -eq 0) { return $false }
    $script:D = $base - 0x10000000
    Log ("attached pid {0}, i76shell.dll base 0x{1:x} delta 0x{2:x}" -f $script:Proc.Id, $base, $script:D)
    return $true
}
function Sh([long]$va) { return $va + $script:D }          # shell VA -> live address
function RdU([long]$a) { [SM]::U32($script:H, $a) }
function RdI([long]$a) { [SM]::I32($script:H, $a) }
function RdB([long]$a, [int]$n) { [SM]::Read($script:H, $a, $n) }
function CStr([byte[]]$b) { if (-not $b) { return "<unreadable>" }; $i = [Array]::IndexOf($b, [byte]0); if ($i -lt 0) { $i = $b.Length }; [Text.Encoding]::GetEncoding(28591).GetString($b, 0, $i) }
function Unrebase([uint32]$fp) { if ($fp -eq 0 -or $fp -eq 0xFFFFFFFF) { return [int64]$fp }; [int64]$fp - $script:D }

function State {
    # the shellstate.ps1 line, plus the save-screen statics
    $scr = RdU (Sh 0x100d2168); $sfn = RdU (Sh 0x100d219c); $mfn = RdU (Sh 0x100d21a0); $mod = RdU (Sh 0x100d21a4)
    $mo = RdU (Sh 0x100cc514); $mx = -1; $my = -1; $bl = 0
    if ($mo -and $mo -ne 0xFFFFFFFF) { $mx = RdI ($mo + 0x2c); $my = RdI ($mo + 0x30); $bl = RdU ($mo + 0x34) }
    $pend = RdU (Sh 0x100d21ac); $next = RdU (Sh 0x100d2194); $lw = RdU (Sh 0x10055d90)
    $sfnN = Nm $TblSfn (Unrebase $sfn); $mfnN = Nm $TblMfn (Unrebase $mfn)
    $top = if ($mod -and $mod -ne 0xFFFFFFFF) { "popup" } elseif ($mfn) { "menu:$mfnN" } elseif ($sfn) { "screen:$sfnN" } else { "none" }
    $scene = RdU 0x4c2160
    $hung = [SM]::IsHungAppWindow($script:Proc.MainWindowHandle)
    [pscustomobject]@{ Screen = $scr; ScreenName = (Nm $TblScreen $scr); Sfn = (Unrebase $sfn); SfnName = $sfnN; Mfn = (Unrebase $mfn); MfnName = $mfnN
        Modal = $mod; Mouse = "$mx,$my"; Btn = $bl; Pending = $pend; Next = $next; LastWidget = $lw; Scene = $scene; Hung = $hung; Top = $top
        Text = ("top={0,-20} screen=0x{1:X4}({2}) sfn=0x{3:x8}({4}) mfn=0x{5:x8}({6}) modal=0x{7:x8} mouse=({8}) L={9} pending={10} next={11} lastwidget={12} scene={13} hung={14}" -f `
            $top, $scr, (Nm $TblScreen $scr), (Unrebase $sfn), $sfnN, (Unrebase $mfn), $mfnN, $mod, "$mx,$my", $bl, $pend, $next, $lw, $scene, $hung) }
}
function SaveStatics {
    # SaveMenu statics (shell SAVE.md section 3): edit record 0x10057f38, name buffer 0x10057f3c (32), row-picked 0x10057f74,
    # slot 0x10057f80, overwrite slot 0x10057f84, region list 0x10057f88, bookmark list 0x10057f8c; load row index [0x10046e70]
    $name = CStr (RdB (Sh 0x10057f3c) 32)
    [pscustomobject]@{ Name = $name; NameHex = (($(RdB (Sh 0x10057f3c) 12) | ForEach-Object { $_.ToString("x2") }) -join "")
        RecScene = (RdU (Sh 0x10057f38)); RowPicked = (RdU (Sh 0x10057f74)); Slot = (RdI (Sh 0x10057f80)); OwSlot = (RdI (Sh 0x10057f84))
        Regions = (RdU (Sh 0x10057f88)); List = (RdU (Sh 0x10057f8c)); LoadRow = (RdI (Sh 0x10046e70))
        Text = ("name='{0}' hex={1} recScene={2} rowPicked={3} slot={4} owSlot={5} regions=0x{6:x} list=0x{7:x} loadRow={8}" -f `
            $name, (($(RdB (Sh 0x10057f3c) 12) | ForEach-Object { $_.ToString("x2") }) -join ""), (RdU (Sh 0x10057f38)), (RdU (Sh 0x10057f74)), (RdI (Sh 0x10057f80)), (RdI (Sh 0x10057f84)), (RdU (Sh 0x10057f88)), (RdU (Sh 0x10057f8c)), (RdI (Sh 0x10046e70))) }
}
function ButtonCount {
    # main-menu button list [0x100d3e7c] -> +4 count (SCREENS.md); grows when the TRIP sub-menu opens
    $lst = RdU (Sh 0x100d3e7c); if ($lst -and $lst -ne 0xFFFFFFFF) { return (RdI ($lst + 4)) }; return -1
}
function LoadedRecord {
    # the Load menu copies the chosen 60-byte dir record to 0x100579e8 (plan 2.2)
    $b = RdB (Sh 0x100579e8) 60
    if (-not $b) { return "<unreadable>" }
    "scene={0} name='{1}' file='{2}' +0x34={3} flags={4}" -f [BitConverter]::ToUInt32($b, 0), (CStr $b[4..35]), (CStr $b[36..51]), [BitConverter]::ToUInt32($b, 52), [BitConverter]::ToUInt32($b, 56)
}
function WaitState([string]$what, [scriptblock]$pred, [double]$maxS = 10, [int]$pollMs = 250) {
    $sw = [Diagnostics.Stopwatch]::StartNew(); $s = $null
    while ($sw.Elapsed.TotalSeconds -lt $maxS) {
        $s = State
        if (& $pred $s) { Log ("  reached {0} after {1:n1}s: {2}" -f $what, $sw.Elapsed.TotalSeconds, $s.Text) "Green"; return $s }
        Start-Sleep -Milliseconds $pollMs
    }
    Log ("  NOT reached {0} within {1}s; state: {2}" -f $what, $maxS, $s.Text) "Yellow"
    return $null
}
# ---------------------------------------------------------------- screenshots ---------------------------------------
Add-Type -AssemblyName System.Drawing
function Shot([string]$name) {
    try {
        $hw = $script:Proc.MainWindowHandle; $r = New-Object SM+RECT; [void][SM]::GetWindowRect($hw, [ref]$r)
        $w = $r.R - $r.L; $h = $r.B - $r.T; if ($w -le 0 -or $h -le 0) { Log "  shot ${name}: empty window rect"; return }
        $b = New-Object Drawing.Bitmap $w, $h; $g = [Drawing.Graphics]::FromImage($b)
        $g.CopyFromScreen($r.L, $r.T, 0, 0, (New-Object Drawing.Size($w, $h)))
        $s = New-Object Drawing.Bitmap 960, 720; $g2 = [Drawing.Graphics]::FromImage($s); $g2.DrawImage($b, 0, 0, 960, 720)
        $p = Join-Path $Run "$name.png"; $s.Save($p, [Drawing.Imaging.ImageFormat]::Png)
        $g.Dispose(); $g2.Dispose(); $b.Dispose(); $s.Dispose()
        Log "  shot $name.png (window $($r.L),$($r.T) ${w}x${h})"
    } catch { Log "  shot $name failed: $_" "Yellow" }
}
# ---------------------------------------------------------------- snapshots -----------------------------------------
$SnapFiles = @("savegame.dir", "ADDON\vehscn.vcf", "ADDON\vehscn.vsf", "reconfig.spc", "trip4.spc", "user.rpr", "I76PLYR.DEF")
function Snap([string]$label) {
    $rows = @()
    $files = $SnapFiles | ForEach-Object { Join-Path $G $_ }
    $files += (Get-ChildItem (Join-Path $G "save*.cmp") | ForEach-Object FullName)
    foreach ($f in $files) {
        if (Test-Path $f) { $i = Get-Item $f; $rows += [pscustomobject]@{ file = $f.Substring($G.Length + 1); size = $i.Length; md5 = (Get-FileHash $f -Algorithm MD5).Hash.ToLower(); mtime = $i.LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss.fff") } }
        else { $rows += [pscustomobject]@{ file = $f.Substring($G.Length + 1); size = -1; md5 = "ABSENT"; mtime = "" } }
    }
    $rows | ConvertTo-Json | Set-Content (Join-Path $Run "$label.json") -Encoding UTF8
    Log "  $label :"
    foreach ($r in $rows) { Log ("    {0,-22} {1,7} {2} {3}" -f $r.file, $r.size, $r.md5, $r.mtime) }
    python "$Here\parse_saves.py" $G | Set-Content (Join-Path $Run "$label-parse.txt") -Encoding UTF8
    return $rows
}
function DiffSnap($a, $b) {
    $out = @()
    $names = @($a.file) + @($b.file) | Sort-Object -Unique
    foreach ($n in $names) {
        $x = $a | Where-Object file -eq $n; $y = $b | Where-Object file -eq $n
        if (-not $x) { $out += "  NEW      $n size $($y.size) md5 $($y.md5)"; continue }
        if (-not $y) { $out += "  GONE     $n"; continue }
        if ($x.md5 -ne $y.md5) { $out += "  CHANGED  $n size $($x.size)->$($y.size) md5 $($x.md5)->$($y.md5) mtime $($y.mtime)" }
        else { $out += "  same     $n" }
    }
    return $out
}
# ---------------------------------------------------------------- input ---------------------------------------------
function ShellMouse {
    $mo = RdU (Sh 0x100cc514)
    if ($mo -and $mo -ne 0xFFFFFFFF) { return ,@((RdI ($mo + 0x2c)), (RdI ($mo + 0x30))) }
    return ,@(-1, -1)
}
function ClickUi([int]$ux, [int]$uy, [string]$what, [int]$settle = 900) {
    # The OS cursor IS the UI coordinate (maplib.ps1 model). Run 1 (2026-10-01 19:08) confirmed it the hard way: a click placed
    # by the screen mapping (760+3*ux) was read by the shell as (639,479) and missed TRIP. So: place 1:1, then verify with the
    # shell's own mouse object (0x100cc514 +0x2c/+0x30, SCREENS.md) before pressing; the screen mapping is only a fallback.
    [void][Inp]::SetCursorPos($ux, $uy); Start-Sleep -Milliseconds 250
    $m = ShellMouse; $mode = "1:1"
    if ([math]::Abs($m[0] - $ux) -gt 3 -or [math]::Abs($m[1] - $uy) -gt 3) {
        $map = Get-UiMap
        $sx = [int]($map.Sx + $ux * $map.Scale); $sy = [int]($map.Sy + $uy * $map.Scale)
        [void][Inp]::SetCursorPos($sx, $sy); Start-Sleep -Milliseconds 250
        $m2 = ShellMouse
        if ([math]::Abs($m2[0] - $ux) -le 3 -and [math]::Abs($m2[1] - $uy) -le 3) { $mode = "screen($sx,$sy)"; $m = $m2 }
        else {
            [void][Inp]::SetCursorPos($ux, $uy); Start-Sleep -Milliseconds 200; $m = ShellMouse
            $mode = "1:1 UNVERIFIED (shell saw $($m2[0]),$($m2[1]) for the screen mapping)"
        }
    }
    Log ("click {0} at UI ({1},{2}) mode={3} shell-mouse=({4},{5})" -f $what, $ux, $uy, $mode, $m[0], $m[1])
    [Inp]::mouse_event(0x2, 0, 0, 0, [IntPtr]::Zero); Start-Sleep -Milliseconds 70
    [Inp]::mouse_event(0x4, 0, 0, 0, [IntPtr]::Zero); Start-Sleep -Milliseconds $settle
}
function PostKey([IntPtr]$hw, [byte]$vk) {
    $scan = [SM]::MapVirtualKeyA($vk, 0)
    [void][SM]::PostMessageA($hw, 0x100, [IntPtr]$vk, [IntPtr](($scan -shl 16) -bor 1))
    Start-Sleep -Milliseconds 40
    [void][SM]::PostMessageA($hw, 0x101, [IntPtr]$vk, [IntPtr]((($scan -shl 16) -bor 1) -bor 0xC0000000))
}
function PostChar([IntPtr]$hw, [char]$c) { [void][SM]::PostMessageA($hw, 0x102, [IntPtr][int]$c, [IntPtr]1) }
function SendInputKey([byte]$vk) {
    $scan = [SM]::MapVirtualKeyA($vk, 0)
    [void][SM]::KeyScan([uint16]$scan, $false); Start-Sleep -Milliseconds 40; [void][SM]::KeyScan([uint16]$scan, $true)
}
function TypeWith([string]$method, [string]$text) {
    $hw = $script:Proc.MainWindowHandle
    foreach ($ch in $text.ToCharArray()) {
        $vk = [byte][char]::ToUpper($ch)           # A..Z, 0..9 share VK and ASCII
        switch ($method) {
            "keybd_event" { Send-Key $vk 40 }
            "SendInput"   { SendInputKey $vk }
            "PostMessage" { PostKey $hw $vk }
            "WM_CHAR"     { PostChar $hw $ch }
        }
        Start-Sleep -Milliseconds 60
    }
    Start-Sleep -Milliseconds 300
}
function PressEnter([string]$method) {
    $hw = $script:Proc.MainWindowHandle
    switch ($method) { "keybd_event" { Send-Key $VK.ENTER 40 } "SendInput" { SendInputKey 0x0D } default { PostKey $hw 0x0D } }
}
function FileMtime([string]$rel) { $p = Join-Path $G $rel; if (Test-Path $p) { (Get-Item $p).LastWriteTime } else { [datetime]0 } }
function WaitWrite([string]$rel, [datetime]$before, [double]$maxS = 4) {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    while ($sw.Elapsed.TotalSeconds -lt $maxS) { if ((FileMtime $rel) -gt $before) { Log ("  {0} written after {1:n2}s" -f $rel, $sw.Elapsed.TotalSeconds) "Green"; return $true }; Start-Sleep -Milliseconds 100 }
    return $false
}

# ==================================================================== PRE-FLIGHT =====================================
Log "leg-a.ps1 mode=$Mode run=$Run" "Cyan"
Add-Type -AssemblyName System.Windows.Forms
$tss = [System.Windows.Forms.SystemInformation]::TerminalServerSession
$qs = (query session 2>&1 | Out-String)
Log ("P1 TerminalServerSession={0}; query session console line: {1}" -f $tss, (($qs -split "`n" | Where-Object { $_ -match "console" }) -join " | ").Trim())
if ($tss) { throw "RDP session: launch results invalid (AGENTS.md)" }
if (Get-Process | Where-Object { $_.ProcessName -like "i76*" }) { throw "an i76* process is running" }
if (Test-Path $Lock) { throw "lock held: $(Get-Content $Lock -Raw)" }
Set-Content $Lock "leg-a.ps1 $Mode pid $PID $(Get-Date)"
Log "P2 no i76* process; lock taken"

$Bak = Join-Path $G "save-backup-$ts"; New-Item -ItemType Directory -Force $Bak | Out-Null
$bakList = @("savegame.dir", "reconfig.spc", "trip4.spc", "user.rpr", "I76PLYR.DEF") + (Get-ChildItem (Join-Path $G "save*.cmp") | ForEach-Object Name) + (Get-ChildItem (Join-Path $G "ADDON\vehscn.*") | ForEach-Object { "ADDON\" + $_.Name })
$md5lines = @()
foreach ($rel in $bakList) {
    $src = Join-Path $G $rel
    if (-not (Test-Path $src)) { $md5lines += "ABSENT  $rel"; continue }
    $dst = Join-Path $Bak ($rel -replace "\\", "__"); Copy-Item $src $dst
    $md5lines += ("{0}  {1}  {2}" -f (Get-FileHash $src -Algorithm MD5).Hash.ToLower(), (Get-Item $src).Length, $rel)
}
$md5lines | Set-Content (Join-Path $Bak "md5.txt") -Encoding UTF8
Log "P3 backup -> $Bak ($($md5lines.Count) entries)"; $md5lines | ForEach-Object { Log "    $_" }

$sh = [IO.File]::ReadAllBytes("$G\i76shell.dll")
$ghost = [Text.Encoding]::ASCII.GetString([IO.File]::ReadAllBytes("$G\u32x.dll")).Contains("DisableProcessWindowsGhosting")
$conf = Select-String -Path "$G\dgVoodoo.conf" -Pattern '^\s*(CaptureMouse|FreeMouse|FullScreenMode|ScalingMode|EnableInactiveAppState)\s*=' | ForEach-Object { $_.Line.Trim() -replace "\s+", " " } | Select-Object -Unique
$sfx = powershell -NoProfile -ExecutionPolicy Bypass -File "$Lab\tools\instruments\deploy-shellfix.ps1" -GameDir $G -Status 2>&1 | Out-String
Log ("P4 i76shell.dll 0x1B52C=0x{0:X2} 0x1B535=0x{1:X2} (want 41/08); u32x DisableProcessWindowsGhosting={2} (KNOWN BLOCKER if False: screen may die ~6s into the Save screen); exe md5 {3}" -f $sh[0x1B52C], $sh[0x1B535], $ghost, (Get-FileHash "$G\i76.exe" -Algorithm MD5).Hash)
Log ("P4 deploy-shellfix -Status: {0}" -f (($sfx -split "`r?`n" | Where-Object { $_.Trim() }) -join " / "))
Log ("P4 dgVoodoo.conf: {0}" -f ($conf -join "; "))
$pre = Snap "snap0-prelaunch"

# ==================================================================== RUN ============================================
$proc = $null; $script:stepTable = @(); $script:outcome = "not started"
function Step([string]$id, [string]$state) { $script:stepTable += ("| {0} | {1:n1}s | {2} |" -f $id, $T0.Elapsed.TotalSeconds, $state); Log "STEP $id -> $state" "Cyan" }
function Abort([string]$why) { $script:outcome = "ABORTED: $why"; Log "ABORT: $why" "Red"; throw $why }
$logLen0 = 0
try {
    if (Test-Path $BakDll) { Copy-Item $BakDll $Dll -Force; Remove-Item $BakDll; Log "restored a leftover STRLKUP.DLL.pretest first" "Yellow" }
    Copy-Item $Dll $BakDll; Copy-Item $NewDll $Dll -Force
    Log ("proxy installed: STRLKUP.DLL md5 {0} (pretest {1})" -f (Get-FileHash $Dll -Algorithm MD5).Hash.ToLower(), (Get-FileHash $BakDll -Algorithm MD5).Hash.ToLower())
    Get-ChildItem Env: | Where-Object { $_.Name -like "I76*" } | ForEach-Object { Remove-Item "Env:$($_.Name)" }
    $env:I76MUSIC_LOG = "1"
    Log ("env: " + ((Get-ChildItem Env: | Where-Object { $_.Name -like "I76*" } | ForEach-Object { "$($_.Name)=$($_.Value)" }) -join " "))
    $logLen0 = if (Test-Path "$G\mciproxy.log") { (Get-Item "$G\mciproxy.log").Length } else { 0 }

    # ---- A1 launch, keep foreground while it boots (TEST-FRAMERATE.ps1 pattern) --------------------------------------
    [void][Inp]::mouse_event(0x1, 5, 0, 0, [IntPtr]::Zero); Start-Sleep -Milliseconds 200; [void][Inp]::mouse_event(0x1, -5, 0, 0, [IntPtr]::Zero)
    $proc = Start-Process (Join-Path $G "i76.exe") -ArgumentList "-glide" -WorkingDirectory $G -PassThru
    Log "A1 launched i76.exe -glide pid $($proc.Id)"
    for ($i = 0; $i -lt 5 -and -not $proc.HasExited; $i++) {
        Start-Sleep -Seconds 2; $proc.Refresh()
        if ($proc.MainWindowHandle -ne [IntPtr]::Zero) { [void](Force-Foreground $proc.MainWindowHandle) }
    }
    if ($proc.HasExited) { Abort "A1: process exited during boot (code $($proc.ExitCode))" }
    $proc.Refresh()
    $att = Attach
    if (-not $att) {
        # the shell DLL loads after the intro movies; wait for it
        for ($i = 0; $i -lt 60 -and -not $att; $i++) { Start-Sleep -Seconds 1; $att = Attach }
    }
    if (-not $att) { Abort "A1: i76shell.dll never loaded" }
    Log ("debug: SFN count {0}; Nm(0x10025a50)={1}; live sfn raw=0x{2:x8} unrebased=0x{3:x8} key={4}" -f $TblSfn.Count, (Nm $TblSfn 0x10025a50), (RdU (Sh 0x100d219c)), (Unrebase (RdU (Sh 0x100d219c))), ("{0:x8}" -f [int64](Unrebase (RdU (Sh 0x100d219c)))))
    $s = State; Log "A1 state: $($s.Text)"; Shot "A1-after-launch"
    Step "A1" ("window up, pid {0}, {1}" -f $proc.Id, $s.Text)

    # ---- A2 Esc, Enter until the main menu (screen 0xC00E / sfn 0x10025a50) -------------------------------------------
    $main = $null
    for ($i = 0; $i -lt 8; $i++) {
        $s = State
        if ($s.Screen -eq 0xC00E -and $s.Sfn -eq 0x10025a50) { $main = $s; break }
        if ($s.Hung) { Log "  A2: IsHungAppWindow TRUE at try $i" "Yellow" }
        if (Test-WindowPumping $proc.MainWindowHandle) { [void](Force-Foreground $proc.MainWindowHandle) }
        Send-Key $VK.ESC; Start-Sleep -Milliseconds 300; Send-Key $VK.ENTER; Start-Sleep -Milliseconds 800
        Log "  A2 try $i : $((State).Text)"
    }
    if (-not $main) { $main = WaitState "main menu" { param($s) $s.Screen -eq 0xC00E -and $s.Sfn -eq 0x10025a50 } 20 }
    Shot "A2-main-menu"
    if (-not $main) { Abort "A2: main menu never appeared" }
    Step "A2" $main.Text

    # ---- A3 TRIP ---------------------------------------------------------------------------------------------------
    [void](Ensure-GameFocus $proc)
    $nb0 = ButtonCount
    ClickUi 217 311 "TRIP"
    $s = State; $nb1 = ButtonCount; Log "A3 state: $($s.Text); main-menu button count $nb0 -> $nb1"; Shot "A3-trip"
    Step "A3" ("buttons {0} -> {1}; {2}" -f $nb0, $nb1, $s.Text)
    # ---- A4 LOAD BOOKMARK --------------------------------------------------------------------------------------------
    ClickUi 276 351 "LOAD BOOKMARK" 1500
    $s = WaitState "LoadBookmark menu (mfn 0x10013060)" { param($s) $s.Mfn -eq 0x10013060 } 6
    Shot "A4-load-bookmark"
    if (-not $s) { Abort "A4: LoadBookmark menu not reached: $((State).Text)" }
    Step "A4" $s.Text
    # ---- A5 pick a row ---------------------------------------------------------------------------------------------
    $rowBefore = (SaveStatics).LoadRow
    ClickUi 203 $RowUy "bookmark row (UI y $RowUy)" 700
    $ss = SaveStatics; Log "A5 load row index [0x10046e70]: $rowBefore -> $($ss.LoadRow)"; Shot "A5-row"
    Step "A5" ("row index {0} -> {1}; {2}" -f $rowBefore, $ss.LoadRow, (State).Text)
    # ---- A6 LOAD -----------------------------------------------------------------------------------------------------
    ClickUi 352 428 "LOAD" 500
    $s6 = WaitState "0xC01D then 0xC017 (inventory, sfn 0x10018e90)" { param($s) $s.Screen -eq 0xC017 -and $s.Sfn -eq 0x10018e90 } 20
    $rec = LoadedRecord; Log "A6 loaded record @0x100579e8: $rec ; scene counter 0x4c2160 = $((State).Scene); flags [0x10057a20]=0x$((RdU (Sh 0x10057a20)).ToString('x')) (bit 2 = the vcf/vsf write branch, plan 2.2 step 5); exe prev-state [0x100d2164]->$((RdU (RdU (Sh 0x100d2164))))"
    Shot "A6-inventory"
    if (-not $s6) { Abort "A6: inventory screen not reached: $((State).Text)" }
    Step "A6" ("{0}; loaded {1}" -f $s6.Text, $rec)
    # ---- A7 ACCEPT SALVAGE ---------------------------------------------------------------------------------------------
    ClickUi 412 460 "ACCEPT SALVAGE" 500
    $s7 = WaitState "garage (0xC00F, sfn 0x10003e70)" { param($s) $s.Screen -eq 0xC00F -and $s.Sfn -eq 0x10003e70 } 15
    Shot "A7-garage"
    if (-not $s7) { Abort "A7: garage not reached: $((State).Text)" }
    Step "A7" $s7.Text
    # ---- A8 snapshot 1 -------------------------------------------------------------------------------------------------
    Start-Sleep -Milliseconds 800
    $snap1 = Snap "snap1-garage"
    Step "A8" "snapshot 1 taken (see snap1-garage.json)"
    $ss = SaveStatics; Log "A8 save statics before SAVE BOOKMARK: $($ss.Text)"

    # ---- A9 SAVE BOOKMARK: the edit loop is modal and the u32x here has no ghosting fix, so everything from here to
    #      the commit must happen inside ~5 s. No Force-Foreground past this point (focuslib gotcha).
    $dirBefore = FileMtime "savegame.dir"
    $tSave = [Diagnostics.Stopwatch]::StartNew()
    ClickUi 560 460 "SAVE BOOKMARK" 600
    $s9 = State; $ss9 = SaveStatics
    Log ("A9 +{0:n2}s state: {1}" -f $tSave.Elapsed.TotalSeconds, $s9.Text); Log ("A9 statics: {0}" -f $ss9.Text)
    $inEdit = ($ss9.Slot -eq -1 -and $ss9.List -ne 0)
    Step "A9" ("{0}; statics {1}; inEdit={2}" -f $s9.Text, $ss9.Text, $inEdit)
    if (-not $inEdit) { Shot "A9-not-in-edit"; Abort "A9: Save edit loop not detected (slot=$($ss9.Slot) list=0x$($ss9.List.ToString('x')))" }

    $typedBy = "none"
    if ($Mode -eq "type") {
        # ---- A10b typing: three methods, buffer read after each --------------------------------------------------------
        foreach ($m in "keybd_event", "SendInput", "PostMessage", "WM_CHAR") {
            TypeWith $m $TypeText
            $ss = SaveStatics
            Log ("A10b +{0:n2}s after {1}: {2}" -f $tSave.Elapsed.TotalSeconds, $m, $ss.Text)
            $hung = [SM]::IsHungAppWindow($proc.MainWindowHandle); if ($hung) { Log "  window reported hung" "Yellow" }
            if ($ss.Name.Length -gt 0) { $typedBy = $m; break }
        }
        Step "A10b" ("typing landed by: {0}; buffer '{1}'" -f $typedBy, (SaveStatics).Name)
        Shot "A10b-typed"
    }
    # ---- A10a / commit: Enter ---------------------------------------------------------------------------------------
    $enterMethod = if ($typedBy -in "keybd_event", "SendInput", "PostMessage") { $typedBy } else { "keybd_event" }
    PressEnter $enterMethod
    Log ("A10 +{0:n2}s Enter sent by {1}" -f $tSave.Elapsed.TotalSeconds, $enterMethod)
    Start-Sleep -Milliseconds 700
    $s10 = State; $ss10 = SaveStatics
    Log ("A10 +{0:n2}s state: {1}" -f $tSave.Elapsed.TotalSeconds, $s10.Text); Log ("A10 statics: {0}" -f $ss10.Text)
    $written = (FileMtime "savegame.dir") -gt $dirBefore
    $pumping = Test-WindowPumping $proc.MainWindowHandle 300
    Log ("A10 dir written={0} pumping={1} hung={2}" -f $written, $pumping, [SM]::IsHungAppWindow($proc.MainWindowHandle))
    Shot "A10-after-enter"
    $step10 = if ($Mode -eq "type") { "A10b-Enter" } else { "A10a" }
    if ($written) { Step $step10 ("direct save; {0}; {1}" -f $s10.Text, $ss10.Text) }
    elseif ($ss10.OwSlot -ge 0 -and -not $pumping) { Step $step10 ("overwrite prompt (Modal_YesNo, not pumping) owSlot={0}; {1}" -f $ss10.OwSlot, $s10.Text) }
    else { Step $step10 ("no save, no prompt detected; {0}; {1}" -f $s10.Text, $ss10.Text) }

    # ---- A11 overwrite prompt: YES -----------------------------------------------------------------------------------
    if (-not $written) {
        ClickUi 393 258 "YES (overwrite)" 200
        Log ("A11 +{0:n2}s YES clicked" -f $tSave.Elapsed.TotalSeconds)
        $written = WaitWrite "savegame.dir" $dirBefore 4
        $s11 = State; Log ("A11 +{0:n2}s state: {1}; statics {2}" -f $tSave.Elapsed.TotalSeconds, $s11.Text, (SaveStatics).Text)
        Shot "A11-after-yes"
        if (-not $written) {
            # maybe that was NO (re-enters the edit loop): try Enter again then the other button
            Log "A11: no write after YES click; pressing Enter again and clicking the other button (450,258)" "Yellow"
            PressEnter $enterMethod; Start-Sleep -Milliseconds 700
            Log ("A11b statics: {0}; state {1}" -f (SaveStatics).Text, (State).Text)
            ClickUi 450 258 "other button (450,258)" 200
            $written = WaitWrite "savegame.dir" $dirBefore 4
            Shot "A11b-after-other"
        }
        Step "A11" ("YES/NO handled; dir written={0}; {1}" -f $written, (State).Text)
    }
    # ---- A12 snapshot 2 ------------------------------------------------------------------------------------------------
    Start-Sleep -Milliseconds 500
    $snap2 = Snap "snap2-after-save"
    $s12 = State; Log "A12 state: $($s12.Text); statics $((SaveStatics).Text)"
    Shot "A12-after-save"
    Step "A12" ("snapshot 2; dir written={0}; {1}" -f $written, $s12.Text)
    Log "DIFF snapshot1 -> snapshot2:"; DiffSnap $snap1 $snap2 | ForEach-Object { Log $_ }
    Log ("A12 +{0:n2}s since SAVE BOOKMARK; hung={1} pumping={2}" -f $tSave.Elapsed.TotalSeconds, [SM]::IsHungAppWindow($proc.MainWindowHandle), (Test-WindowPumping $proc.MainWindowHandle 300))
    # watch the screen for the ghost (P4) a few seconds more, for the record
    for ($i = 0; $i -lt 4; $i++) { Start-Sleep -Seconds 1; Log ("  watch +{0:n1}s hung={1} pumping={2} {3}" -f $tSave.Elapsed.TotalSeconds, [SM]::IsHungAppWindow($proc.MainWindowHandle), (Test-WindowPumping $proc.MainWindowHandle 300), (State).Text) }
    Shot "A12b-watch"
    $script:outcome = "completed through A12 (dir written=$written, typedBy=$typedBy)"
} catch {
    Log "RUN ERROR: $_" "Red"
    if ($script:outcome -eq "not started") { $script:outcome = "ERROR: $_" }
    if ($proc -and -not $proc.HasExited) { Shot "error-state" }
} finally {
    # ---- A13 quit: WM_CLOSE first, kill after 10 s ------------------------------------------------------------------------
    if ($proc -and -not $NoQuit) {
        try {
            $proc.Refresh()
            if (-not $proc.HasExited) {
                [void][SM]::PostMessageA($proc.MainWindowHandle, 0x0010, [IntPtr]::Zero, [IntPtr]::Zero)
                $sw = [Diagnostics.Stopwatch]::StartNew()
                while (-not $proc.HasExited -and $sw.Elapsed.TotalSeconds -lt 10) { Start-Sleep -Milliseconds 500; $proc.Refresh() }
                if ($proc.HasExited) { Log ("A13 WM_CLOSE: clean exit in {0:n1}s" -f $sw.Elapsed.TotalSeconds) }
                else { Stop-Process -Id $proc.Id -Force; Start-Sleep -Seconds 1; Log "A13 WM_CLOSE ignored for 10 s; killed pid $($proc.Id)" "Yellow" }
            } else { Log "A13 process already gone (exit code $($proc.ExitCode))" }
        } catch { Log "A13 quit error: $_" "Yellow" }
        Get-Process | Where-Object { $_.ProcessName -like "i76*" } | ForEach-Object { Stop-Process -Id $_.Id -Force; Log "killed leftover $($_.ProcessName) $($_.Id)" "Yellow" }
    }
    if ($script:H -ne [IntPtr]::Zero) { [void][SM]::CloseHandle($script:H) }
    # restore STRLKUP.DLL and drop the lock FIRST (run 1: a later exception in this block skipped the restore)
    if (Test-Path $BakDll) {
        Copy-Item $BakDll $Dll -Force
        $ok = (Get-FileHash $Dll -Algorithm MD5).Hash -eq (Get-FileHash $BakDll -Algorithm MD5).Hash
        if ($ok) { Remove-Item $BakDll }
        Log ("restore STRLKUP.DLL from .pretest: {0} (md5 {1})" -f $(if ($ok) { "OK, .pretest removed" } else { "MD5 MISMATCH, .pretest kept" }), (Get-FileHash $Dll -Algorithm MD5).Hash.ToLower())
    } else { Log "restore: no .pretest found (nothing installed?)" "Yellow" }
    Remove-Item $Lock -ErrorAction SilentlyContinue
    Log "lock removed: $(-not (Test-Path $Lock))"
    try {
        Start-Sleep -Milliseconds 500
        $snapEnd = Snap "snap3-after-quit"
        if (Test-Path "$G\mciproxy.log") {
            $bytes = [IO.File]::ReadAllBytes("$G\mciproxy.log"); $new = [Text.Encoding]::GetEncoding(28591).GetString($bytes, $logLen0, $bytes.Length - $logLen0)
            $new | Set-Content (Join-Path $Run "mciproxy-this-run.log") -Encoding UTF8
            Log ("mciproxy.log: {0} new bytes this run -> mciproxy-this-run.log; ABORTED lines: {1}" -f ($bytes.Length - $logLen0), (($new -split "`n" | Where-Object { $_ -match "ABORTED" }).Count))
        }
    } catch { Log "post-run bookkeeping error: $_" "Yellow" }
    Log "OUTCOME: $($script:outcome)" "Cyan"
    Log "STEP TABLE:"; $script:stepTable | ForEach-Object { Log $_ }
    $script:stepTable | Set-Content (Join-Path $Run "steps.md") -Encoding UTF8
}
