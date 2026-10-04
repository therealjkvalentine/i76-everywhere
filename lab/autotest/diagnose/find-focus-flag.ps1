<#
  find-focus-flag.ps1 — find the global that says "my window is active".

  I'76 freezes its simulation (and stops presenting a live image) whenever its window loses
  focus. That single behaviour has been the biggest obstacle in this whole effort: it makes
  screenshots stale, freezes traces mid-run, and means a human can't touch the console while
  the game runs.

  The engine keeps a window-active flag (Roanish's notes call it g_window_active, tested before
  the per-frame active_tick). Find it by differential: read the static data range while
  FOCUSED, then again while UNFOCUSED, and look for a small integer that went nonzero -> zero.
  Because the sim is frozen when unfocused, very little else changes, so the flag stands out.

  Then pin it to 1 and see whether the game keeps simulating in the background.
#>
param(
    [int64]$Lo = 0x004C0000,
    [int64]$Hi = 0x00620000,
    [string]$OutDir = "$PSScriptRoot\..\..\captures\focusflag"
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\lib\memlib.ps1"
. "$PSScriptRoot\..\lib\focuslib.ps1"
. "$PSScriptRoot\..\lib\inputlib.ps1"
. "$PSScriptRoot\..\lib\simlib.ps1"
New-Item -ItemType Directory -Force $OutDir | Out-Null

Add-Type @"
using System;
using System.Runtime.InteropServices;
public class FF {
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr a, byte[] b, int s, out int r);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern IntPtr SetForegroundWindow(IntPtr h);
  [DllImport("kernel32.dll")] public static extern IntPtr GetConsoleWindow();   // kernel32, not user32
  [DllImport("user32.dll")] public static extern IntPtr GetDesktopWindow();
  [DllImport("user32.dll")] public static extern IntPtr FindWindowA(string cls, string win);
}
"@

$ctx = Mem-Open
if (-not (Mem-InMission $ctx)) { throw "get into a mission first" }
$size = [int]($Hi - $Lo)

function Snap {
    $buf = New-Object byte[] $size
    $n = 0
    [void][FF]::ReadProcessMemory($ctx.H, [IntPtr]$Lo, $buf, $size, [ref]$n)
    return $buf
}

# --- focused sample -----------------------------------------------------------
Force-Foreground $ctx.Proc.MainWindowHandle | Out-Null
Start-Sleep -Milliseconds 900
$focused = Snap
$fFrame = (Mem-Player $ctx).Frame

# --- unfocused sample ---------------------------------------------------------
# Give focus to something else. Any other top-level window will do.
$other = [FF]::GetConsoleWindow()
if ($other -eq [IntPtr]::Zero) { $other = (Get-Process -Id $PID).MainWindowHandle }
[void][FF]::SetForegroundWindow($other)
Start-Sleep -Milliseconds 1500
$unfocused = Snap
$uFrame = (Mem-Player $ctx).Frame

Write-Host ("frame counter: {0} focused -> {1} unfocused (delta {2}; 0 confirms the freeze)" -f `
    $fFrame, $uFrame, ($uFrame - $fFrame)) -ForegroundColor Cyan

# --- diff ---------------------------------------------------------------------
$cands = @()
for ($o = 0; $o -lt $size - 4; $o += 4) {
    $a = [BitConverter]::ToInt32($focused, $o)
    $b = [BitConverter]::ToInt32($unfocused, $o)
    if ($a -ne $b -and $a -ge 1 -and $a -le 16 -and $b -eq 0) {
        $cands += [pscustomobject]@{ VA = ('0x{0:X8}' -f ($Lo + $o)); Focused = $a; Unfocused = $b }
    }
}
Force-Foreground $ctx.Proc.MainWindowHandle | Out-Null
Mem-Close $ctx

Write-Host ("`n{0} candidates that went nonzero -> 0 on focus loss:" -f $cands.Count) -ForegroundColor Green
$cands | Select-Object -First 30 | ForEach-Object { "  {0}  {1} -> {2}" -f $_.VA, $_.Focused, $_.Unfocused }
$cands | Export-Csv (Join-Path $OutDir 'candidates.csv') -NoTypeInformation
