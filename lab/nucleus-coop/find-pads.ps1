# find-pads.ps1 - list the winmm joystick ids Interstate '76 would see, and tell the pads apart (2026-10-05).
# The game reads joysticks only through winmm joyGetPosEx (README, finding 1); this calls the same API from a 32-bit
# PowerShell (the game is 32-bit), so the ids printed here are the ids to put in Interstate76.js JOY_WINMM.
# Usage: plug the pads in, then   powershell -ExecutionPolicy Bypass -File find-pads.ps1 [-Seconds 30]
# Then press a button (or move a stick) on ONE pad at a time: the script prints which id moved.
param([int]$Seconds = 30)
if ([Environment]::Is64BitProcess) {   # re-run in 32-bit PowerShell
    $ps32 = "$env:WINDIR\SysWOW64\WindowsPowerShell\v1.0\powershell.exe"
    & $ps32 -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath -Seconds $Seconds; exit $LASTEXITCODE
}
Add-Type @"
using System; using System.Runtime.InteropServices;
public class FP {
  [StructLayout(LayoutKind.Sequential)] public struct JOYINFOEX { public int dwSize, dwFlags, X, Y, Z, R, U, V, Buttons, ButtonNumber, POV, Reserved1, Reserved2; }
  [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Ansi)] public struct JOYCAPS {
    public ushort wMid, wPid; [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)] public string szPname;
    public int wXmin, wXmax, wYmin, wYmax, wZmin, wZmax, wNumButtons, wPeriodMin, wPeriodMax, wRmin, wRmax, wUmin, wUmax, wVmin, wVmax, wCaps, wMaxAxes, wNumAxes, wMaxButtons;
    [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)] public string szRegKey; [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 260)] public string szOEMVxD; }
  [DllImport("winmm.dll")] public static extern int joyGetPosEx(int id, ref JOYINFOEX j);
  [DllImport("winmm.dll", CharSet = CharSet.Ansi)] public static extern int joyGetDevCapsA(IntPtr id, ref JOYCAPS c, int size);
}
"@
function Poll($id) { $j = New-Object FP+JOYINFOEX; $j.dwSize = 52; $j.dwFlags = 0xFF; $rc = [FP]::joyGetPosEx($id, [ref]$j); return @{ rc = $rc; j = $j } }
$present = @()
for ($id = 0; $id -lt 16; $id++) {
    $p = Poll $id
    if ($p.rc -eq 0) {
        $c = New-Object FP+JOYCAPS; [void][FP]::joyGetDevCapsA([IntPtr]$id, [ref]$c, [Runtime.InteropServices.Marshal]::SizeOf($c))
        "winmm id $id : present  '$($c.szPname)'  VID/PID-ish $($c.wMid)/$($c.wPid)  axes $($c.wNumAxes) buttons $($c.wNumButtons)"
        $present += $id
    }
}
if (-not $present) { "no winmm joystick present (ids 0..15 all fail). Plug a pad in and run again."; exit 1 }
""
"Now press a button or move a stick on ONE pad at a time ($Seconds s)..."
$last = @{}; foreach ($id in $present) { $last[$id] = (Poll $id).j }
$end = (Get-Date).AddSeconds($Seconds)
while ((Get-Date) -lt $end) {
    foreach ($id in $present) {
        $n = (Poll $id).j; $o = $last[$id]
        $moved = ($n.Buttons -ne $o.Buttons) -or ([Math]::Abs($n.X - $o.X) -gt 8000) -or ([Math]::Abs($n.Y - $o.Y) -gt 8000)
        if ($moved) { "  winmm id $id moved (buttons 0x{0:X} X {1} Y {2})" -f $n.Buttons, $n.X, $n.Y; $last[$id] = $n }
    }
    Start-Sleep -Milliseconds 100
}
""
"Put these ids in Interstate76.js: JOY_WINMM = [15, <id of player 2's pad>, ...]  (15 = no pad, the keyboard player)."
