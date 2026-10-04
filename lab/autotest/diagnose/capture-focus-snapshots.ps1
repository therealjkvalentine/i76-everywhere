<#
  capture-focus-snapshots.ps1 — grab the static data range focused vs unfocused.

  Half of the window-active-flag hunt; focus-flag-diff.py does the comparison (PowerShell
  diffing 1.4 MB four bytes at a time never finishes - same lesson as the cursor mapping).

  Writes focused.bin / unfocused.bin plus a note of the frame counter in each, which confirms
  the freeze actually happened.
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
public class FF2 {
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr a, byte[] b, int s, out int r);
  [DllImport("user32.dll")]   public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("kernel32.dll")] public static extern IntPtr GetConsoleWindow();
}
"@
$ctx = Mem-Open
if (-not (Mem-InMission $ctx)) { throw "get into a mission first" }
$size = [int]($Hi - $Lo)
function Snap([string]$path) {
    $buf = New-Object byte[] $size; $n = 0
    [void][FF2]::ReadProcessMemory($ctx.H, [IntPtr]$Lo, $buf, $size, [ref]$n)
    [IO.File]::WriteAllBytes($path, $buf)
}
Force-Foreground $ctx.Proc.MainWindowHandle | Out-Null
Start-Sleep -Milliseconds 1000
$f1 = (Mem-Player $ctx).Frame
Snap (Join-Path $OutDir 'focused.bin')

$other = [FF2]::GetConsoleWindow()
if ($other -eq [IntPtr]::Zero) { $other = (Get-Process -Id $PID).MainWindowHandle }
[void][FF2]::SetForegroundWindow($other)
Start-Sleep -Milliseconds 1800
$f2 = (Mem-Player $ctx).Frame
Snap (Join-Path $OutDir 'unfocused.bin')
$f3 = (Mem-Player $ctx).Frame

"base=0x{0:X}" -f $Lo | Set-Content (Join-Path $OutDir 'meta.txt')
Add-Content (Join-Path $OutDir 'meta.txt') ("frames: focused={0} unfocused={1}/{2} (delta {3})" -f $f1,$f2,$f3,($f3-$f2))
Force-Foreground $ctx.Proc.MainWindowHandle | Out-Null
Mem-Close $ctx
Write-Host ("frames {0} -> {1} -> {2}   (delta while unfocused: {3}; 0 = frozen)" -f $f1,$f2,$f3,($f3-$f2)) -ForegroundColor Cyan
Write-Host ("snapshots -> {0}" -f (Resolve-Path $OutDir)) -ForegroundColor Green
