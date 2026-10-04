<#
  find-perframe.ps1 — find every value the engine advances PER FRAME instead of per second.

  The idea: park the car, touch nothing, and let the same amount of WALL-CLOCK time pass at
  20 Hz and at 60 Hz. Anything driven by real time advances by the same amount in both runs.
  Anything advanced once per frame advances 3x further at 60 Hz. That ratio is the signature.

  This is what the reported bugs look like from memory: the sky scrolling too fast, the
  post-death camera spinning too fast, chassis roll snapping over. Rather than hunt each by
  hand, this sweeps the engine's static data and lists every candidate at once.

  Scans the exe's static data range only (fast, and where animation state and timers live -
  the frame counter 0x5A7E1C is in it). Heap animation would need a wider scan.

  Usage - run once at each frame rate, then compare:
    tools\find-perframe.ps1 -Label pf20 -Seconds 6
    tools\find-perframe.ps1 -Label pf60 -Seconds 6
    python tools\analyse-perframe.py captures\perframe\pf20.csv captures\perframe\pf60.csv
#>
param([string]$Label = 'pf', [int]$Seconds = 6,
      [int64]$Lo = 0x4C0000, [int64]$Hi = 0x700000,
      [string]$OutDir = "$PSScriptRoot\..\..\captures\perframe")
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\..\autotest\lib\memlib.ps1"
. "$PSScriptRoot\..\..\autotest\lib\focuslib.ps1"
. "$PSScriptRoot\..\..\autotest\lib\inputlib.ps1"
. "$PSScriptRoot\..\..\autotest\lib\simlib.ps1"
New-Item -ItemType Directory -Force $OutDir | Out-Null

Add-Type @"
using System;
using System.Runtime.InteropServices;
public class PFScan {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(uint a, bool i, int p);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr a, byte[] b, int s, out int r);
}
"@
$ctx = Mem-Open
if (-not (Mem-InMission $ctx)) { throw "not in a mission" }
if (-not (Ensure-SimRunning $ctx)) { throw "sim not advancing" }
$h = [PFScan]::OpenProcess(0x10, $false, $ctx.Proc.Id)
$len = [int]($Hi - $Lo)

function Snap { $b = New-Object byte[] $len; $n = 0
    [void][PFScan]::ReadProcessMemory($h, [IntPtr]$Lo, $b, $len, [ref]$n); return ,$b }

# Let the car settle so physics contributes as little as possible; animations keep running.
Start-Sleep -Seconds 2
$f0 = (Mem-Player $ctx).Frame
$a = Snap
$sw = [Diagnostics.Stopwatch]::StartNew()
Start-Sleep -Seconds $Seconds
$real = $sw.Elapsed.TotalSeconds
$b = Snap
$f1 = (Mem-Player $ctx).Frame
$frames = $f1 - $f0
Mem-Close $ctx

$inv = [Globalization.CultureInfo]::InvariantCulture
$rows = @("# seconds=$($real.ToString('R',$inv)) frames=$frames fps=$([math]::Round($frames/$real,2))")
$rows += 'addr,d_float,d_int'
for ($o = 0; $o -lt $len - 4; $o += 4) {
    $ia = [BitConverter]::ToInt32($a, $o); $ib = [BitConverter]::ToInt32($b, $o)
    if ($ia -eq $ib) { continue }
    $fa = [BitConverter]::ToSingle($a, $o); $fb = [BitConverter]::ToSingle($b, $o)
    $df = if ([double]::IsNaN($fa) -or [double]::IsNaN($fb) -or [math]::Abs($fa) -gt 1e12 -or [math]::Abs($fb) -gt 1e12) { [double]::NaN } else { $fb - $fa }
    $rows += ('0x{0:X},{1},{2}' -f ($Lo + $o), $df.ToString('R',$inv), ($ib - $ia).ToString($inv))
}
$rows | Set-Content (Join-Path $OutDir "$Label.csv")
Write-Host ("{0}: {1:N1} fps over {2:N2}s, {3} changed dwords -> {4}.csv" -f $Label, ($frames/$real), $real, ($rows.Count-2), $Label) -ForegroundColor Green
