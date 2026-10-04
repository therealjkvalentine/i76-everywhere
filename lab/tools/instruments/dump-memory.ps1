<#
  dump-memory.ps1 — one-shot dump of all writable memory (READ-ONLY). No motion needed.

  Companion to find-copies.py. Splitting the work this way matters: searching 200 MB in a
  PowerShell byte loop is ~50M iterations and effectively never finishes, while a bulk
  ReadProcessMemory dump plus a Python/struct search takes seconds.

  Writes dump.bin (regions concatenated) + regions.csv (base,size in file order) + pos.txt.
#>
param(
    [string]$OutDir = "$PSScriptRoot\..\..\captures\dump",
    [string]$RequirePath = 'i76-uncap-lab',
    [int]$MaxRegionMB = 8,
    [int]$BudgetMB = 220
)
$ErrorActionPreference = 'Stop'
Add-Type @"
using System;
using System.Runtime.InteropServices;
[StructLayout(LayoutKind.Sequential)]
public struct MBI4 { public IntPtr BaseAddress; public IntPtr AllocationBase; public uint AllocationProtect;
  public IntPtr RegionSize; public uint State; public uint Protect; public uint Type; }
public class DM {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(uint a, bool i, int p);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr a, byte[] b, int s, out int r);
  [DllImport("kernel32.dll")] public static extern int VirtualQueryEx(IntPtr h, IntPtr a, out MBI4 m, int len);
  [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
}
"@
$proc = Get-Process i76, nitro -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -and $_.Path -like "*$RequirePath*" } | Select-Object -First 1
if (-not $proc) { throw "Sandbox Interstate '76 is not running." }
$h = [DM]::OpenProcess(0x410, $false, $proc.Id)
if ($h -eq [IntPtr]::Zero) { throw "OpenProcess failed." }
New-Item -ItemType Directory -Force $OutDir | Out-Null

function RdF([int64]$a) { $b = New-Object byte[] 4; $n = 0
    [void][DM]::ReadProcessMemory($h, [IntPtr]$a, $b, 4, [ref]$n); [BitConverter]::ToSingle($b,0) }
$px = RdF 0x54E11C; $py = RdF 0x54E120; $pz = RdF 0x54E124
"{0} {1} {2}" -f $px, $py, $pz | Set-Content (Join-Path $OutDir 'pos.txt')
Write-Host ("player position = ({0:N2}, {1:N2}, {2:N2})" -f $px, $py, $pz) -ForegroundColor Cyan

$fs = [IO.File]::Create((Join-Path $OutDir 'dump.bin'))
$lines = @(); $addr = [int64]0x10000; $total = 0
try {
    while ($addr -lt [int64]0x7FFF0000 -and $total -lt ($BudgetMB * 1MB)) {
        $mbi = New-Object MBI4
        if ([DM]::VirtualQueryEx($h, [IntPtr]$addr, [ref]$mbi, [Runtime.InteropServices.Marshal]::SizeOf($mbi)) -eq 0) { break }
        $size = [int64]$mbi.RegionSize
        if ($size -le 0) { break }
        if ($mbi.State -eq 0x1000 -and (@(0x04,0x02,0x40,0x08,0x20) -contains $mbi.Protect) -and $size -le ($MaxRegionMB * 1MB)) {
            $buf = New-Object byte[] $size; $n = 0
            if ([DM]::ReadProcessMemory($h, [IntPtr]$mbi.BaseAddress, $buf, $size, [ref]$n) -and $n -gt 0) {
                $fs.Write($buf, 0, $n)
                $lines += ("{0:X8},{1}" -f [int64]$mbi.BaseAddress, $n)
                $total += $n
            }
        }
        $addr += $size
    }
} finally { $fs.Close() }
$lines | Set-Content (Join-Path $OutDir 'regions.csv')
Write-Host ("dumped {0:N1} MB in {1} regions -> {2}" -f ($total/1MB), $lines.Count, (Resolve-Path $OutDir)) -ForegroundColor Green
[DM]::CloseHandle($h) | Out-Null
