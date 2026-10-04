<#
  check-sim.ps1 — is the SIMULATION actually running? (READ-ONLY)

  Diagnostic written after a capture returned two byte-identical snapshots while the
  frame counter advanced: renderer alive, sim frozen. I'76 pauses the sim when its
  window loses focus (and in menus / pause), while continuing to draw — so any memory
  sample taken then is stale and every "nothing moved" result is meaningless.

  Prints, once per sample: frame counter, speed, velocity, and the foreground window,
  so you can see immediately whether the sim is advancing and what state the game is in.
#>
param([int]$Samples = 10, [int]$IntervalMs = 300)

Add-Type @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public class SimChk {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(uint a, bool i, int p);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr a, byte[] b, int s, out int r);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
}
"@

$proc = Get-Process i76, nitro -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $proc) { throw "Interstate '76 is not running." }
$h = [SimChk]::OpenProcess(0x10, $false, $proc.Id)
function Rd32([int64]$a) { $b = New-Object byte[] 4; $n = 0
    if ([SimChk]::ReadProcessMemory($h, [IntPtr]$a, $b, 4, [ref]$n)) { [BitConverter]::ToInt32($b,0) } else { 0 } }
function RdF([int64]$a) { $b = New-Object byte[] 4; $n = 0
    if ([SimChk]::ReadProcessMemory($h, [IntPtr]$a, $b, 4, [ref]$n)) { [BitConverter]::ToSingle($b,0) } else { 0 } }

$fg = [SimChk]::GetForegroundWindow()
$sb = New-Object System.Text.StringBuilder 256
[void][SimChk]::GetWindowText($fg, $sb, 256)
$fgPid = 0; [void][SimChk]::GetWindowThreadProcessId($fg, [ref]$fgPid)
$isGame = ($fgPid -eq $proc.Id)
Write-Host ("foreground: '{0}' (pid {1}) - game focused: {2}" -f $sb.ToString(), $fgPid, $isGame) -ForegroundColor $(if ($isGame) { 'Green' } else { 'Red' })
if (-not $isGame) { Write-Host "GAME IS NOT FOCUSED. I'76 freezes the sim when unfocused - click the game window." -ForegroundColor Red }

$w = Rd32 0x54a264; $sub = Rd32 $w; $ent = Rd32 ($sub + 0x70)
if ($ent -eq 0) { throw "Player entity NULL - not in a mission." }
Write-Host ("entity=0x{0:X}" -f $ent)
Write-Host "frame#      speed      velocity(x,y,z)          simMoved?"
$prevF = $null; $prevS = $null; $simMoves = 0; $frameAdv = 0
for ($k = 0; $k -lt $Samples; $k++) {
    $f = Rd32 0x5A7E1C
    $s = RdF ($ent + 0xAC)
    $vx = RdF ($ent + 0xBC); $vy = RdF ($ent + 0xC0); $vz = RdF ($ent + 0xC4)
    $moved = if ($null -ne $prevS -and $s -ne $prevS) { 'YES' } else { '-' }
    if ($moved -eq 'YES') { $simMoves++ }
    if ($null -ne $prevF) { $frameAdv += ($f - $prevF) }
    "{0,-11} {1,8:N3}   ({2,7:N2},{3,6:N2},{4,7:N2})     {5}" -f $f, $s, $vx, $vy, $vz, $moved
    $prevF = $f; $prevS = $s
    Start-Sleep -Milliseconds $IntervalMs
}
Write-Host ""
Write-Host ("frames advanced: {0}   sim-state changes: {1}" -f $frameAdv, $simMoves)
if ($frameAdv -gt 0 -and $simMoves -eq 0) {
    Write-Host "VERDICT: renderer running, SIM FROZEN. Snapshots taken now are stale - unpause/focus the game." -ForegroundColor Red
} elseif ($simMoves -gt 0) {
    Write-Host "VERDICT: sim is LIVE - captures will be valid." -ForegroundColor Green
} else {
    Write-Host "VERDICT: nothing advancing at all - game may be in a menu." -ForegroundColor Yellow
}
