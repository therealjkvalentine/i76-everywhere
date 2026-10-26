# shellstate.ps1 - read the I'76 shell's navigation state from a running game, twice a second (read-only).
#   powershell -ExecutionPolicy Bypass -File shellstate.ps1 [-ProcessName i76 | -ProcessId N] [-Module i76shell.dll] [-Once] [-Seconds N]
# -Buttons also dumps the main-menu button list [0x100d3e7c] (id + rectangle + click point).
# Globals and meanings: shell\SCREENS.md. Addresses are VAs at the DLL's preferred base 0x10000000; the live module
# base is resolved with EnumProcessModulesEx(LIST_MODULES_32BIT) and the delta applied, so a rebased DLL reads correctly.
# Never writes to the process. Needs PROCESS_QUERY_INFORMATION | PROCESS_VM_READ (see autotest README trap 2).
param([string]$ProcessName = "i76", [int]$ProcessId = 0, [string]$Module = "i76shell.dll", [switch]$Once, [int]$Seconds = 0, [switch]$Buttons)

Add-Type -TypeDefinition @"
using System; using System.Runtime.InteropServices; using System.Text;
public static class SS {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(int a, bool i, int pid);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr a, byte[] b, int n, out IntPtr r);
  [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
  [DllImport("psapi.dll")] public static extern bool EnumProcessModulesEx(IntPtr h, IntPtr[] m, int cb, out int need, int flag);
  [DllImport("psapi.dll", CharSet=CharSet.Ansi)] public static extern int GetModuleBaseNameA(IntPtr h, IntPtr m, StringBuilder s, int n);
  public static long Base(IntPtr h, string name) {
    IntPtr[] m = new IntPtr[1024]; int need;
    if (!EnumProcessModulesEx(h, m, m.Length * IntPtr.Size, out need, 0x01)) return 0;   // LIST_MODULES_32BIT
    int n = need / IntPtr.Size;
    for (int i = 0; i < n; i++) { var sb = new StringBuilder(260); GetModuleBaseNameA(h, m[i], sb, 260);
      if (string.Equals(sb.ToString(), name, StringComparison.OrdinalIgnoreCase)) return m[i].ToInt64(); }
    return 0;
  }
  public static int I32(IntPtr h, long a) { var b = new byte[4]; IntPtr r; if (!ReadProcessMemory(h, new IntPtr(a), b, 4, out r)) return int.MinValue; return BitConverter.ToInt32(b, 0); }
  public static uint U32(IntPtr h, long a) { var b = new byte[4]; IntPtr r; if (!ReadProcessMemory(h, new IntPtr(a), b, 4, out r)) return 0xFFFFFFFF; return BitConverter.ToUInt32(b, 0); }
}
"@

$SCREEN = @{}; $S0 = @{ 0xC00D="choose-vehicle"; 0xC00E="main-menu"; 0xC00F="garage(build+repair)"; 0xC015="post-mission";
  0xC017="inventory+salvage"; 0xC01D="load-bookmark(exec)"; 0xC01E="enter-reconfig"; 0xC01F="parts-catalog";
  0xC020="mission-grid"; 0xC021="melee-form"; 0xC022="new-trip"; 0xC024="melee-form"; 0xC025="standings"; 0xC026="net-form"; 0xC008="return" }
foreach ($k in $S0.Keys) { $SCREEN[[int64]$k] = $S0[$k] }
$SFN = @{}; $F0 = @{ 0x10025a50="main-menu"; 0x10023c20="choose-vehicle"; 0x10003e70="garage"; 0x100246e0="post-mission";
  0x10018e90="inventory"; 0x10025910="parts-catalog"; 0x1001f480="mission-grid"; 0x10028610="melee/net-form"; 0x1003f980="standings"; 0x10016c80="new-trip" }
foreach ($k in $F0.Keys) { $SFN[[int64]$k] = $F0[$k] }
$MFN = @{}; $M0 = @{ 0x1000e6b0="Options"; 0x10014cd0="SaveBookmark"; 0x10013060="LoadBookmark"; 0x10011dc0="ExitGame";
  0x10013c70="ModemSetup"; 0x10014410="PlayOptions"; 0x10012db0="GraphicDetail"; 0x1000db90="AudioControl";
  0x1000ee00="ControlConfig"; 0x10007b20="Credits" }
foreach ($k in $M0.Keys) { $MFN[[int64]$k] = $M0[$k] }

if ($ProcessId) { $p = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue } else { $p = Get-Process -Name $ProcessName -ErrorAction SilentlyContinue | Select-Object -First 1 }
if (-not $p) { Write-Host "no process '$ProcessName'"; exit 2 }
$h = [SS]::OpenProcess(0x0410, $false, $p.Id)
if ($h -eq [IntPtr]::Zero) { Write-Host "OpenProcess failed"; exit 3 }
$base = [SS]::Base($h, $Module)
if ($base -eq 0) { Write-Host "module $Module not loaded in pid $($p.Id) (not in the shell?)"; [SS]::CloseHandle($h) | Out-Null; exit 4 }
$d = $base - 0x10000000
Write-Host ("pid {0} {1} base 0x{2:x} delta 0x{3:x}" -f $p.Id, $Module, $base, $d)
$sw = [Diagnostics.Stopwatch]::StartNew()
do {
  $scr = [SS]::U32($h, 0x100d2168 + $d); $sfn = [SS]::U32($h, 0x100d219c + $d); $mfn = [SS]::U32($h, 0x100d21a0 + $d)
  $mod = [SS]::U32($h, 0x100d21a4 + $d); $mo = [SS]::U32($h, 0x100cc514 + $d)
  $mx = if ($mo) { [SS]::I32($h, $mo + 0x2c) } else { -1 }; $my = if ($mo) { [SS]::I32($h, $mo + 0x30) } else { -1 }
  $bl = if ($mo) { [SS]::U32($h, $mo + 0x34) } else { 0 }
  $pend = [SS]::U32($h, 0x100d21ac + $d); $next = [SS]::U32($h, 0x100d2194 + $d); $lw = [SS]::U32($h, 0x10055d90 + $d)
  # function pointers are absolute: compare after removing the delta
  $sfnN = if ($sfn) { $SFN[[int64]$sfn - $d] } else { "-" }; $mfnN = if ($mfn) { $MFN[[int64]$mfn - $d] } else { "-" }
  $top = if ($mod) { "popup" } elseif ($mfn) { "menu:$mfnN" } elseif ($sfn) { "screen:$sfnN" } else { "none" }
  "{0,7:n1}s top={1,-22} screen=0x{2:X4}({3}) sfn=0x{4:x8} mfn=0x{5:x8} modal=0x{6:x8} mouse=({7},{8}) L={9} pending={10} next={11} lastwidget={12}" -f `
    $sw.Elapsed.TotalSeconds, $top, $scr, $SCREEN[[int64]$scr], $sfn, $mfn, $mod, $mx, $my, $bl, $pend, $next, $lw
  if ($Buttons) {
    # main-menu button list (SCREENS.md): list [0x100d3e7c] -> +4 count, +8 array of button*; button +0 id, +4 x0, +8 x1, +0xc y0, +0x10 y1
    $lst = [SS]::U32($h, 0x100d3e7c + $d)
    if ($lst -and $lst -ne 0xFFFFFFFF) {
      $n = [SS]::I32($h, $lst + 4); $arr = [SS]::U32($h, $lst + 8)
      for ($i = 0; $i -lt [Math]::Min($n, 32); $i++) {
        $b = [SS]::U32($h, $arr + 4 * $i)
        "    button id={0,2} x={1}..{2} y={3}..{4}  click=({5},{6})" -f [SS]::I32($h,$b), [SS]::I32($h,$b+4), [SS]::I32($h,$b+8), [SS]::I32($h,$b+0xc), [SS]::I32($h,$b+0x10), [int](([SS]::I32($h,$b+4)+[SS]::I32($h,$b+8))/2), [int](([SS]::I32($h,$b+0xc)+[SS]::I32($h,$b+0x10))/2)
      }
    }
  }
  if ($Once) { break }
  Start-Sleep -Milliseconds 500
} while ($Seconds -eq 0 -or $sw.Elapsed.TotalSeconds -lt $Seconds)
[SS]::CloseHandle($h) | Out-Null
