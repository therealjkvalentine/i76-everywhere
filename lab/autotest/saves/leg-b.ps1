<#
  leg-b.ps1 - SAVES-STATE-AND-TEST-PLAN.md section 4.4 Leg B (load a bookmark, verify the car in the mission) in the
  SANDBOX game, unattended. Infrastructure (memory reads, clicks, snapshots, restore) is leg-a.ps1's, verbatim.

    powershell -ExecutionPolicy Bypass -File leg-b.ps1 [-Mode b1|b2] [-WantFile save006] [-WantRow 6] [-RowUy 330]
                                                      [-SetScene N] [-StopAtGarage] [-NoQuit]

  Mode b1 : A1..A4, pick the row whose index is -WantRow (verified by [0x10046e70], one self-correction by 23 UI px per
            row), LOAD (the record copied to 0x100579e8 must name -WantFile), ACCEPT SALVAGE, snapshot + exe globals in
            the garage, DONE, cutscene skip until the player entity exists, entity/trainer dump, quit.
  Mode b2 : the same, after installing a copy of savegame.dir in which -WantFile's scene dword was set to -SetScene by
            the browser editor's dirSetScene (dir_set_scene.mjs); the original directory is put back in finally.

  Hard rules (the brief): sandbox only; refuses if an i76* process runs or the .console-test.lock exists; backs the save
  set up to save-backup-<ts>\ with md5s; installs music-fix\Strlkup.dll over STRLKUP.DLL after copying the original to
  STRLKUP.DLL.pretest and restores it in finally; I76MUSIC_LOG=1 only; the game is closed at the end (WM_CLOSE, twice
  if the first lands in the mission and brings the shell up, Stop-Process after that).
#>
param(
    [ValidateSet("b1", "b2")] [string]$Mode = "b1",
    [string]$WantFile = "save006",
    [int]$WantRow = 6,
    [int]$RowUy = 330,                 # Leg A rows drew at UI y 193/215/239/261/285/307 (23 apart): row 6 -> 330
    [int]$SetScene = -1,               # b2: scene dword to write into WantFile's record before the boot
    [switch]$StopAtGarage,
    [switch]$NoQuit,
    [string]$GameDir = "",             # "" = the sandbox (<lab>\game); any other folder must be inside the lab (lib\gamedir.ps1)
    [string]$BackupDir = "",           # "" = <game>\save-backup-<ts> as before; gate-folder.ps1 points it outside the game folder
    [int]$Scroll = 0,                  # clicks on the LOAD board's down arrow before the row click (rows >= 10: 10, cal-probe2.ps1)
    [switch]$KeepInstalledDll,         # do not install music-fix\Strlkup.dll: run the folder's own STRLKUP.DLL
    [switch]$DryRun                    # print the resolved paths and exit; touches nothing
)
$ErrorActionPreference = "Stop"
$Lab  = "C:\Users\james\i76-uncap-lab"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
. "$Lab\autotest\lib\gamedir.ps1"
$G    = Resolve-LabGameDir $GameDir
$I76GameDirInUse = $G                  # focuslib / memlib / maplib: prefer this folder's process and conf
$NewDll = "C:\Users\james\i76-everywhere\music-fix\Strlkup.dll"
$Dll = Join-Path $G "STRLKUP.DLL"; $BakDll = "$Dll.pretest"
$Lock = Join-Path $G ".console-test.lock"
$ts = Get-Date -Format "yyyyMMdd-HHmmss"
$Bak = if ($BackupDir) { $BackupDir } else { Join-Path $G "save-backup-$ts" }
if ($DryRun) {
    "leg-b DRY RUN (nothing touched)"
    "  game dir   : $G"
    "  exe        : $(Join-Path $G 'i76.exe') -glide (cwd = game dir)"
    "  lock       : $Lock"
    "  proxy      : $(if ($KeepInstalledDll) { "the installed $Dll, no swap" } else { "$NewDll -> $Dll, original kept as $BakDll" })"
    "  save backup: $Bak"
    "  savegame   : $(Join-Path $G 'savegame.dir') (present: $(Test-Path (Join-Path $G 'savegame.dir')))"
    "  u32x / conf: $(Join-Path $G 'u32x.dll') / $(Join-Path $G 'dgVoodoo.conf')"
    "  route      : $WantFile row $WantRow at UI y $RowUy, scroll clicks $Scroll, mode $Mode"
    exit 0
}
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

# ---------------------------------------------------------------- exe globals (static VAs, no ASLR) ----------------
# mission.md: 0x4c2160 trip scene, 0x4c2164 game state (5 = running), 0x5049f0 mission file (t%02d.msn), 0x5dcea0 shell
# play mode, 0x5dcea9 car file the shell hands over, 0x5dd370 player car name, 0x6562c0/0x6562c4 mission number/type
# (2 = trip), 0x4fe520 terrain set, 0x5a7e1c frame counter; shell 0x10057a20 flags, 0x100d2164 -> exe prev-state slot.
function ExeGlobals {
    $prevPtr = RdU (Sh 0x100d2164); $prev = if ($prevPtr -and $prevPtr -ne 0xFFFFFFFF) { RdU $prevPtr } else { -1 }
    [pscustomobject]@{ Scene = (RdU 0x4c2160); GState = (RdU 0x4c2164); Msn = (CStr (RdB 0x5049f0 32)); PlayMode = (RdU 0x5dcea0)
        CarFile = (CStr (RdB 0x5dcea9 16)); CarName = (CStr (RdB 0x5dd370 16)); MNum = (RdU 0x6562c0); MType = (RdU 0x6562c4)
        Terrain = (RdU 0x4fe520); Frame = (RdU 0x5a7e1c); Flags = (RdU (Sh 0x10057a20)); Prev = $prev
        Text = ("scene={0} gstate={1} msn='{2}' playmode={3} carfile='{4}' carname='{5}' mnum={6} mtype={7} terrain={8} frame={9} shellflags=0x{10:x} prevstate={11}" -f `
            (RdU 0x4c2160), (RdU 0x4c2164), (CStr (RdB 0x5049f0 32)), (RdU 0x5dcea0), (CStr (RdB 0x5dcea9 16)), (CStr (RdB 0x5dd370 16)), (RdU 0x6562c0), (RdU 0x6562c4), (RdU 0x4fe520), (RdU 0x5a7e1c), (RdU (Sh 0x10057a20)), $prev) }
}
function PlayerEnt {
    $w = RdU 0x54a264; if (-not $w -or $w -eq 0xFFFFFFFF) { return 0 }
    $o = RdU $w; if (-not $o -or $o -eq 0xFFFFFFFF) { return 0 }
    $e = RdU ($o + 0x70); if ($e -eq 0xFFFFFFFF) { return 0 }; return $e
}
function LiveEntities {
    $n = 0
    for ($i = 0; $i -lt 16; $i++) { $b = RdB (0x54e11c + 0x20 * $i) 12; if (-not $b) { continue }
        $x = [BitConverter]::ToSingle($b, 0); $z = [BitConverter]::ToSingle($b, 8)
        if (-not [single]::IsNaN($x) -and ([math]::Abs($x) -gt 0.01 -or [math]::Abs($z) -gt 0.01)) { $n++ } }
    return $n
}
function I32s([long]$a, [int]$n) { $b = RdB $a (4 * $n); if (-not $b) { return @() }; 0..($n - 1) | ForEach-Object { [BitConverter]::ToInt32($b, 4 * $_) } }
function EntityDump([long]$e) {
    # cheats.md / trainer: +0x138 armour cur, +0x158 armour max, +0x178 armour hud; +0x148 chassis cur, +0x168 max, +0x18c hud
    [pscustomobject]@{ Ent = $e; ArmourCur = (I32s ($e + 0x138) 4); ArmourMax = (I32s ($e + 0x158) 4); ArmourHud = (I32s ($e + 0x178) 4)
        ChassisCur = (I32s ($e + 0x148) 4); ChassisMax = (I32s ($e + 0x168) 4); ChassisHud = (I32s ($e + 0x18c) 4)
        Text = ("entity 0x{0:x8} armour cur [{1}] max [{2}] hud [{3}]; chassis cur [{4}] max [{5}] hud [{6}]" -f $e, ((I32s ($e + 0x138) 4) -join ","), ((I32s ($e + 0x158) 4) -join ","), ((I32s ($e + 0x178) 4) -join ","), ((I32s ($e + 0x148) 4) -join ","), ((I32s ($e + 0x168) 4) -join ","), ((I32s ($e + 0x18c) 4) -join ",")) }
}
function ByteDiff([string]$relA, [string]$relB, [string]$label) {
    if (-not (Test-Path $relA) -or -not (Test-Path $relB)) { Log "  $label : one side missing"; return }
    $a = [IO.File]::ReadAllBytes($relA); $b = [IO.File]::ReadAllBytes($relB)
    if ($a.Length -ne $b.Length) { Log ("  {0}: sizes differ {1} -> {2}" -f $label, $a.Length, $b.Length) }
    $d = @(); for ($i = 0; $i -lt [math]::Min($a.Length, $b.Length); $i++) { if ($a[$i] -ne $b[$i]) { $d += ("{0}:{1}->{2}" -f $i, $a[$i], $b[$i]) } }
    Log ("  {0}: {1} byte(s) differ {2}" -f $label, $d.Count, $(if ($d.Count -le 24) { ($d -join " ") } else { (($d[0..23]) -join " ") + " ..." }))
}
function DumpVeh([string]$label) {
    foreach ($f in "vehscn.vcf", "vehscn.vsf") {
        $p = Join-Path $G "ADDON\$f"
        if (-not (Test-Path $p)) { Log "  $label ADDON\$f : absent"; continue }
        $chunk = if ($f -eq "vehscn.vcf") { "VCFC" } else { "VCST" }
        $o = python "C:\Users\james\i76-map\data\mod\i76mod.py" show $p $chunk 2>&1 | Out-String
        $o | Set-Content (Join-Path $Run "$label-$f-$chunk.txt") -Encoding UTF8
        $one = ($o -split "`r?`n" | Where-Object { $_ -match "armour|chassis|variant|vdf" } | ForEach-Object { ($_ -replace "\s+", " ").Trim() }) -join "; "
        Log ("  {0} ADDON\{1} md5 {2}: {3}" -f $label, $f, (Get-FileHash $p -Algorithm MD5).Hash.ToLower(), $one)
        if ($f -eq "vehscn.vcf") { python "C:\Users\james\i76-map\data\mod\i76mod.py" show $p 2>&1 | Set-Content (Join-Path $Run "$label-$f-chunks.txt") -Encoding UTF8 }
    }
}

# ==================================================================== PRE-FLIGHT =====================================
Log "leg-b.ps1 mode=$Mode wantFile=$WantFile wantRow=$WantRow rowUy=$RowUy scroll=$Scroll setScene=$SetScene stopAtGarage=$StopAtGarage game=$G keepInstalledDll=$KeepInstalledDll run=$Run" "Cyan"
Add-Type -AssemblyName System.Windows.Forms
$tss = [System.Windows.Forms.SystemInformation]::TerminalServerSession
$qs = (query session 2>&1 | Out-String)
Log ("P1 TerminalServerSession={0}; query session console line: {1}" -f $tss, (($qs -split "`n" | Where-Object { $_ -match "console" }) -join " | ").Trim())
if ($tss) { throw "RDP session: launch results invalid (AGENTS.md)" }
if (Get-Process | Where-Object { $_.ProcessName -like "i76*" }) { throw "an i76* process is running" }
if (Test-Path $Lock) { throw "lock held: $(Get-Content $Lock -Raw)" }
Set-Content $Lock "leg-b.ps1 $Mode pid $PID $(Get-Date)"
Log "P2 no i76* process; lock taken"

New-Item -ItemType Directory -Force $Bak | Out-Null
$bakList = @("savegame.dir", "reconfig.spc", "trip4.spc", "user.rpr", "I76PLYR.DEF") + (Get-ChildItem (Join-Path $G "save*.cmp") | ForEach-Object Name) + (Get-ChildItem (Join-Path $G "ADDON\vehscn.*") | ForEach-Object { "ADDON\" + $_.Name })
$md5lines = @()
foreach ($rel in $bakList) {
    $src = Join-Path $G $rel
    if (-not (Test-Path $src)) { $md5lines += "ABSENT  $rel"; continue }
    $dst = Join-Path $Bak ($rel -replace "\\", "__"); Copy-Item $src $dst
    $md5lines += ("{0}  {1}  {2}" -f (Get-FileHash $src -Algorithm MD5).Hash.ToLower(), (Get-Item $src).Length, $rel)
}
if (-not (Test-Path (Join-Path $G "ADDON\vehscn.vsf"))) { $md5lines += "ABSENT  ADDON\vehscn.vsf" }
$md5lines | Set-Content (Join-Path $Bak "md5.txt") -Encoding UTF8
Log "P3 backup -> $Bak ($($md5lines.Count) entries)"; $md5lines | ForEach-Object { Log "    $_" }

$sh = [IO.File]::ReadAllBytes("$G\i76shell.dll")
$ghost = [Text.Encoding]::ASCII.GetString([IO.File]::ReadAllBytes("$G\u32x.dll")).Contains("DisableProcessWindowsGhosting")
$conf = Select-String -Path "$G\dgVoodoo.conf" -Pattern '^\s*(CaptureMouse|FreeMouse|FullScreenMode|ScalingMode|EnableInactiveAppState)\s*=' | ForEach-Object { $_.Line.Trim() -replace "\s+", " " } | Select-Object -Unique
$sfx = powershell -NoProfile -ExecutionPolicy Bypass -File "$Lab\tools\instruments\deploy-shellfix.ps1" -GameDir $G -Status 2>&1 | Out-String
Log ("P4 i76shell.dll 0x1B52C=0x{0:X2} 0x1B535=0x{1:X2} (want 41/08); u32x DisableProcessWindowsGhosting={2}; exe md5 {3}" -f $sh[0x1B52C], $sh[0x1B535], $ghost, (Get-FileHash "$G\i76.exe" -Algorithm MD5).Hash)
Log ("P4 deploy-shellfix -Status: {0}" -f (($sfx -split "`r?`n" | Where-Object { $_.Trim() }) -join " / "))
Log ("P4 dgVoodoo.conf: {0}" -f ($conf -join "; "))
$pre = Snap "snap0-prelaunch"
DumpVeh "snap0"

# ---- B2 only: install the modified directory ------------------------------------------------------------------------
$DirOrig = Join-Path $Run "savegame.dir.orig"; $script:dirSwapped = $false
if ($SetScene -ge 0) {
    Copy-Item "$G\savegame.dir" $DirOrig
    $modp = Join-Path $Run "savegame.dir.modified"
    $o = & node "$Here\dir_set_scene.mjs" $DirOrig $WantFile $SetScene $modp 2>&1 | Out-String
    Log "B2 dir_set_scene.mjs (editor dirSetScene) exit $LASTEXITCODE :"; ($o -split "`r?`n" | Where-Object { $_.Trim() }) | ForEach-Object { Log "    $_" }
    if ($LASTEXITCODE -ne 0) { Remove-Item $Lock -ErrorAction SilentlyContinue; throw "B2: dir_set_scene failed" }
    ByteDiff $DirOrig $modp "savegame.dir orig -> modified"
    Copy-Item $modp "$G\savegame.dir" -Force; $script:dirSwapped = $true
    Log ("B2 installed modified savegame.dir md5 {0} (orig {1})" -f (Get-FileHash "$G\savegame.dir" -Algorithm MD5).Hash.ToLower(), (Get-FileHash $DirOrig -Algorithm MD5).Hash.ToLower())
    python "$Here\parse_saves.py" $G | ForEach-Object { Log "    $_" }
}

# ==================================================================== RUN ============================================
$proc = $null; $script:stepTable = @(); $script:outcome = "not started"
function Step([string]$id, [string]$state) { $script:stepTable += ("| {0} | {1:n1}s | {2} |" -f $id, $T0.Elapsed.TotalSeconds, $state); Log "STEP $id -> $state" "Cyan" }
function Abort([string]$why) { $script:outcome = "ABORTED: $why"; Log "ABORT: $why" "Red"; throw $why }
$logLen0 = 0
try {
    if (Test-Path $BakDll) { Copy-Item $BakDll $Dll -Force; Remove-Item $BakDll; Log "restored a leftover STRLKUP.DLL.pretest first" "Yellow" }
    if ($KeepInstalledDll) { Log ("-KeepInstalledDll: running the folder's own STRLKUP.DLL md5 {0} (music-fix build is {1})" -f (Get-FileHash $Dll -Algorithm MD5).Hash.ToLower(), (Get-FileHash $NewDll -Algorithm MD5).Hash.ToLower()) }
    else {
        Copy-Item $Dll $BakDll; Copy-Item $NewDll $Dll -Force
        Log ("proxy installed: STRLKUP.DLL md5 {0} (pretest {1})" -f (Get-FileHash $Dll -Algorithm MD5).Hash.ToLower(), (Get-FileHash $BakDll -Algorithm MD5).Hash.ToLower())
    }
    Get-ChildItem Env: | Where-Object { $_.Name -like "I76*" } | ForEach-Object { Remove-Item "Env:$($_.Name)" }
    $env:I76MUSIC_LOG = "1"
    # u32x switch tests (vptr-test.ps1): U32X_TEST_ENV="I76_U32X_VPTR=1;I76_U32X_VPTR_WIDEN=1" survives the scrub above.
    # Only I76_U32X_* names are accepted; unset = this line does nothing.
    if ($env:U32X_TEST_ENV) { foreach ($kv in ($env:U32X_TEST_ENV -split ";")) { $a = $kv -split "=", 2; if ($a.Count -eq 2 -and $a[0] -like "I76_U32X_*") { Set-Item "Env:$($a[0])" $a[1] } } }
    Log ("env: "+ ((Get-ChildItem Env: | Where-Object { $_.Name -like "I76*" } | ForEach-Object { "$($_.Name)=$($_.Value)" }) -join " "))
    $logLen0 = if (Test-Path "$G\mciproxy.log") { (Get-Item "$G\mciproxy.log").Length } else { 0 }

    # ---- B1.1 launch (= A1) ------------------------------------------------------------------------------------------
    [void][Inp]::mouse_event(0x1, 5, 0, 0, [IntPtr]::Zero); Start-Sleep -Milliseconds 200; [void][Inp]::mouse_event(0x1, -5, 0, 0, [IntPtr]::Zero)
    $proc = Start-Process (Join-Path $G "i76.exe") -ArgumentList "-glide" -WorkingDirectory $G -PassThru
    Log "B1.1 launched i76.exe -glide pid $($proc.Id)"
    for ($i = 0; $i -lt 5 -and -not $proc.HasExited; $i++) {
        Start-Sleep -Seconds 2; $proc.Refresh()
        if ($proc.MainWindowHandle -ne [IntPtr]::Zero) { [void](Force-Foreground $proc.MainWindowHandle) }
    }
    if ($proc.HasExited) { Abort "B1.1: process exited during boot (code $($proc.ExitCode))" }
    $proc.Refresh()
    $att = Attach
    if (-not $att) { for ($i = 0; $i -lt 60 -and -not $att; $i++) { Start-Sleep -Seconds 1; $att = Attach } }
    if (-not $att) { Abort "B1.1: i76shell.dll never loaded" }
    $s = State; Log "B1.1 state: $($s.Text)"; Log "B1.1 exe: $((ExeGlobals).Text)"; Shot "B1.1-after-launch"
    Step "B1.1" ("window up, pid {0}, {1}" -f $proc.Id, $s.Text)

    # ---- B1.2 main menu (= A2) ---------------------------------------------------------------------------------------
    $main = $null
    for ($i = 0; $i -lt 8; $i++) {
        $s = State
        if ($s.Screen -eq 0xC00E -and $s.Sfn -eq 0x10025a50) { $main = $s; break }
        if ($s.Hung) { Log "  B1.2: IsHungAppWindow TRUE at try $i" "Yellow" }
        if (Test-WindowPumping $proc.MainWindowHandle) { [void](Force-Foreground $proc.MainWindowHandle) }
        Send-Key $VK.ESC; Start-Sleep -Milliseconds 300; Send-Key $VK.ENTER; Start-Sleep -Milliseconds 800
        Log "  B1.2 try $i : $((State).Text)"
    }
    if (-not $main) { $main = WaitState "main menu" { param($s) $s.Screen -eq 0xC00E -and $s.Sfn -eq 0x10025a50 } 20 }
    Shot "B1.2-main-menu"
    if (-not $main) { Abort "B1.2: main menu never appeared" }
    Log "B1.2 exe at main menu: $((ExeGlobals).Text)"
    Step "B1.2" $main.Text

    # ---- B1.3 TRIP, B1.4 LOAD BOOKMARK (= A3, A4) --------------------------------------------------------------------
    [void](Ensure-GameFocus $proc)
    $nb0 = ButtonCount
    ClickUi 217 311 "TRIP"
    $s = State; $nb1 = ButtonCount
    if ($nb1 -eq $nb0) { Log "  TRIP click did not change the button list; retrying once" "Yellow"; ClickUi 217 311 "TRIP (retry)"; $s = State; $nb1 = ButtonCount }
    Log "B1.3 state: $($s.Text); main-menu button count $nb0 -> $nb1"; Shot "B1.3-trip"
    Step "B1.3" ("buttons {0} -> {1}; {2}" -f $nb0, $nb1, $s.Text)
    ClickUi 276 351 "LOAD BOOKMARK" 1500
    $s = WaitState "LoadBookmark menu (mfn 0x10013060)" { param($s) $s.Mfn -eq 0x10013060 } 6
    Shot "B1.4-load-bookmark"
    if (-not $s) { Abort "B1.4: LoadBookmark menu not reached: $((State).Text)" }
    Step "B1.4" $s.Text

    # ---- B1.5 pick the row for WantFile ------------------------------------------------------------------------------
    $rowBefore = (SaveStatics).LoadRow
    # rows >= 10 are below the fold: scroll the board down first (cal-probe2.ps1: 10 clicks on the arrow at 212,422)
    for ($i = 0; $i -lt $Scroll; $i++) { ClickUi 212 422 "scroll down ($($i + 1)/$Scroll)" 250 }
    ClickUi 203 $RowUy "bookmark row (UI y $RowUy)" 700
    $ss = SaveStatics; Log "B1.5 load row index [0x10046e70]: $rowBefore -> $($ss.LoadRow) (want $WantRow)"
    if ($ss.LoadRow -ne $WantRow -and $ss.LoadRow -ge 0) {
        $uy2 = $RowUy + ($WantRow - $ss.LoadRow) * 23
        Log "  self-correcting: row $($ss.LoadRow) at y $RowUy, want $WantRow -> y $uy2" "Yellow"
        ClickUi 203 $uy2 "bookmark row (corrected UI y $uy2)" 700
        $ss = SaveStatics; Log "B1.5 load row index now $($ss.LoadRow)"
    }
    Shot "B1.5-row"
    if ($ss.LoadRow -ne $WantRow) { Abort "B1.5: wanted row $WantRow, selected $($ss.LoadRow)" }
    Step "B1.5" ("row index {0} -> {1}; {2}" -f $rowBefore, $ss.LoadRow, (State).Text)

    # ---- B1.6 LOAD -> inventory; the loaded record must be WantFile --------------------------------------------------
    ClickUi 352 428 "LOAD" 500
    $s6 = WaitState "0xC01D then 0xC017 (inventory, sfn 0x10018e90)" { param($s) $s.Screen -eq 0xC017 -and $s.Sfn -eq 0x10018e90 } 20
    $rec = LoadedRecord; $g6 = ExeGlobals
    Log "B1.6 loaded record @0x100579e8: $rec"; Log "B1.6 exe after LOAD: $($g6.Text)"
    Shot "B1.6-inventory"
    if (-not $s6) { Abort "B1.6: inventory screen not reached: $((State).Text)" }
    if ($rec -notmatch ("file='{0}'" -f [regex]::Escape($WantFile))) { Abort "B1.6: loaded record is not ${WantFile}: $rec" }
    Step "B1.6" ("{0}; loaded {1}; exe {2}" -f $s6.Text, $rec, $g6.Text)

    # ---- B1.7 ACCEPT SALVAGE -> garage; snapshot 3 ---------------------------------------------------------------------
    ClickUi 412 460 "ACCEPT SALVAGE" 500
    $s7 = WaitState "garage (0xC00F, sfn 0x10003e70)" { param($s) $s.Screen -eq 0xC00F -and $s.Sfn -eq 0x10003e70 } 15
    Shot "B1.7-garage"
    if (-not $s7) { Abort "B1.7: garage not reached: $((State).Text)" }
    Step "B1.7" $s7.Text
    Start-Sleep -Milliseconds 800
    $snap1 = Snap "snap1-garage"
    Log "DIFF snapshot0 (pre-launch) -> snapshot1 (garage after load):"; DiffSnap $pre $snap1 | ForEach-Object { Log $_ }
    ByteDiff (Join-Path $Bak "I76PLYR.DEF") "$G\I76PLYR.DEF" "I76PLYR.DEF backup -> after load"
    DumpVeh "snap1"
    $g7 = ExeGlobals; Log "B1.7 exe in garage: $($g7.Text)"
    Step "B1.8" ("snapshot 1 in garage; exe {0}" -f $g7.Text)
    if ($StopAtGarage) { $script:outcome = "stopped at garage by request"; throw "stop-at-garage" }

    # ---- B1.9 DONE -> mission --------------------------------------------------------------------------------------------
    $f0 = (ExeGlobals).Frame
    ClickUi 400 460 "DONE" 500
    $tDone = [Diagnostics.Stopwatch]::StartNew(); $left = $false
    for ($i = 0; $i -lt 24; $i++) {
        $s = State; $gx = ExeGlobals
        if ($s.Modal -and $s.Modal -ne 0xFFFFFFFF) { Shot "B1.9-modal"; Log "  B1.9 modal after DONE: $($s.Text)" "Yellow" }
        Log ("  B1.9 +{0:n1}s shell {1} | exe {2} | ent 0x{3:x}" -f $tDone.Elapsed.TotalSeconds, $s.Top, $gx.Text, (PlayerEnt))
        if ($gx.Frame -ne $f0 -or (PlayerEnt) -ne 0) { $left = $true; break }
        Start-Sleep -Milliseconds 500
    }
    Shot "B1.9-after-done"
    if (-not $left) { Abort "B1.9: the exe frame counter never moved after DONE (still in the shell): $((State).Text)" }
    Step "B1.9" ("shell left after {0:n1}s; exe {1}" -f $tDone.Elapsed.TotalSeconds, (ExeGlobals).Text)

    # ---- B1.10 cutscene skip until the player entity exists (enter-mission5.ps1 step 5) -----------------------------
    $inMission = $false
    for ($i = 0; $i -lt 40; $i++) {
        $e = PlayerEnt; $n = LiveEntities
        if ($e -ne 0 -and $n -gt 0) { $inMission = $true; break }
        if (Test-WindowPumping $proc.MainWindowHandle) { [void](Force-Foreground $proc.MainWindowHandle) }
        Send-Key $VK.ESC; Start-Sleep -Milliseconds 250
        [Inp]::mouse_event(0x2, 0, 0, 0, [IntPtr]::Zero); Start-Sleep -Milliseconds 50; [Inp]::mouse_event(0x4, 0, 0, 0, [IntPtr]::Zero)
        Start-Sleep -Milliseconds 1000
        if ($i % 3 -eq 0) { Log ("  B1.10 try {0}: ent 0x{1:x} entities {2}; exe {3}" -f $i, $e, $n, (ExeGlobals).Text) }
        if ($proc.HasExited) { Abort "B1.10: process exited during the mission load (code $($proc.ExitCode))" }
    }
    Shot "B1.10-mission"
    if (-not $inMission) { Abort "B1.10: no player entity after the cutscene loop: $((ExeGlobals).Text)" }
    Start-Sleep -Seconds 2
    $e = PlayerEnt; $ed = EntityDump $e; $g10 = ExeGlobals
    Log "B1.10 exe in mission: $($g10.Text)"; Log "B1.10 $($ed.Text); live entities $(LiveEntities)"
    $tr = python "C:\Users\james\i76-everywhere\tools\trainer\i76trainer.py" --any status 2>&1 | Out-String
    $tr | Set-Content (Join-Path $Run "trainer-status.txt") -Encoding UTF8
    ($tr -split "`r?`n" | Where-Object { $_.Trim() }) | ForEach-Object { Log "    trainer: $_" }
    DumpVeh "mission"
    Step "B1.10" ("in mission; exe {0}; {1}" -f $g10.Text, $ed.Text)
    # watch 3 s: entity values stable, sim running
    for ($i = 0; $i -lt 3; $i++) { Start-Sleep -Seconds 1; Log ("  watch +{0}s frame {1} ent {2} hung={3}" -f ($i + 1), (ExeGlobals).Frame, (EntityDump (PlayerEnt)).Text, [SM]::IsHungAppWindow($proc.MainWindowHandle)) }
    Shot "B1.10b-watch"
    $script:outcome = "completed through B1.10 (mission '$($g10.Msn)' scene $($g10.Scene))"
} catch {
    if ("$_" -ne "stop-at-garage") { Log "RUN ERROR: $_" "Red"; if ($script:outcome -eq "not started") { $script:outcome = "ERROR: $_" } }
    if ($proc -and -not $proc.HasExited) { Shot "error-state" }
} finally {
    # ---- quit: WM_CLOSE; in a mission the exe may route to the shell (state 2), so WM_CLOSE a second time; kill after ----
    if ($proc -and -not $NoQuit) {
        try {
            $proc.Refresh()
            for ($round = 1; $round -le 2 -and -not $proc.HasExited; $round++) {
                [void][SM]::PostMessageA($proc.MainWindowHandle, 0x0010, [IntPtr]::Zero, [IntPtr]::Zero)
                $sw = [Diagnostics.Stopwatch]::StartNew()
                while (-not $proc.HasExited -and $sw.Elapsed.TotalSeconds -lt 10) { Start-Sleep -Milliseconds 500; $proc.Refresh() }
                if ($proc.HasExited) { Log ("QUIT WM_CLOSE round {0}: clean exit in {1:n1}s" -f $round, $sw.Elapsed.TotalSeconds) }
                else { try { Log ("QUIT WM_CLOSE round {0}: still alive after 10 s; exe {1}; shell {2}" -f $round, (ExeGlobals).Text, (State).Text) "Yellow"; Shot "quit-round$round" } catch {} }
            }
            if (-not $proc.HasExited) { Stop-Process -Id $proc.Id -Force; Start-Sleep -Seconds 1; Log "QUIT: WM_CLOSE ignored twice; killed pid $($proc.Id)" "Yellow" }
        } catch { Log "QUIT error: $_" "Yellow" }
        Get-Process | Where-Object { $_.ProcessName -like "i76*" } | ForEach-Object { Stop-Process -Id $_.Id -Force; Log "killed leftover $($_.ProcessName) $($_.Id)" "Yellow" }
    }
    if ($script:H -ne [IntPtr]::Zero) { [void][SM]::CloseHandle($script:H) }
    if (Test-Path $BakDll) {
        Copy-Item $BakDll $Dll -Force
        $ok = (Get-FileHash $Dll -Algorithm MD5).Hash -eq (Get-FileHash $BakDll -Algorithm MD5).Hash
        if ($ok) { Remove-Item $BakDll }
        Log ("restore STRLKUP.DLL from .pretest: {0} (md5 {1})" -f $(if ($ok) { "OK, .pretest removed" } else { "MD5 MISMATCH, .pretest kept" }), (Get-FileHash $Dll -Algorithm MD5).Hash.ToLower())
    } elseif ($KeepInstalledDll) { Log "restore: nothing to restore (-KeepInstalledDll)" }
    else { Log "restore: no .pretest found (nothing installed?)" "Yellow" }
    if ($script:dirSwapped) {
        Copy-Item $DirOrig "$G\savegame.dir" -Force
        $ok = (Get-FileHash "$G\savegame.dir" -Algorithm MD5).Hash -eq (Get-FileHash $DirOrig -Algorithm MD5).Hash
        Log ("B2 original savegame.dir restored: {0} (md5 {1})" -f $(if ($ok) { "OK" } else { "MD5 MISMATCH" }), (Get-FileHash "$G\savegame.dir" -Algorithm MD5).Hash.ToLower())
    }
    Remove-Item $Lock -ErrorAction SilentlyContinue
    Log "lock removed: $(-not (Test-Path $Lock))"
    try {
        Start-Sleep -Milliseconds 500
        $snapEnd = Snap "snap3-after-quit"
        Log "DIFF snapshot0 (pre-launch) -> after quit:"; DiffSnap $pre $snapEnd | ForEach-Object { Log $_ }
        ByteDiff (Join-Path $Bak "I76PLYR.DEF") "$G\I76PLYR.DEF" "I76PLYR.DEF backup -> after quit"
        DumpVeh "snap3"
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
