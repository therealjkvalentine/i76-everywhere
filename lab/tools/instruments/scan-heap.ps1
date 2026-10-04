<#
  scan-heap.ps1 — whole-heap differential snapshot to find world POSITION (READ-ONLY).

  Why: the position float3 is not in the player entity's allocation (verified: the entity
  block ends at +0x6000 and no triple there tracks the velocity vector), and guessing
  neighbouring structs is slow. This snapshots EVERY committed readable region of the
  process three times while the car drives, recording velocity and timing at each. The
  offline analysis then finds any float3, anywhere in memory, whose two deltas match
  velocity*dt on both intervals - which position must, and almost nothing else does.

  Requires a LIVE sim (value must be CHANGING - I'76 freezes the sim when unfocused).
  Drive STRAIGHT at a steady speed; two intervals with consistent motion is all it needs.

  Read-only: ReadProcessMemory + VirtualQueryEx only.

  Usage: start it, click into the game, drive straight until it prints DONE.
    powershell -ExecutionPolicy Bypass -File tools\scan-heap.ps1
#>
param(
    [string]$OutDir = "$PSScriptRoot\..\..\captures\heap",
    [double]$MinSpeed = 5.0,
    [int]$GapMs = 350,
    [int]$WaitSeconds = 150,
    [int]$MaxRegionMB = 8,
    [int]$BudgetMB = 160
)
$ErrorActionPreference = 'Stop'

Add-Type @"
using System;
using System.Runtime.InteropServices;
[StructLayout(LayoutKind.Sequential)]
public struct MBI { public IntPtr BaseAddress; public IntPtr AllocationBase; public uint AllocationProtect;
  public IntPtr RegionSize; public uint State; public uint Protect; public uint Type; }
public class HScan {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(uint a, bool i, int p);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr a, byte[] b, int s, out int r);
  [DllImport("kernel32.dll")] public static extern int VirtualQueryEx(IntPtr h, IntPtr a, out MBI m, int len);
  [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
}
"@
$proc = Get-Process i76, nitro -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $proc) { throw "Interstate '76 is not running." }
# 0x10 PROCESS_VM_READ | 0x400 PROCESS_QUERY_INFORMATION.
# VM_READ alone makes VirtualQueryEx fail (returns 0) and the region list comes back empty.
$h = [HScan]::OpenProcess(0x410, $false, $proc.Id)
if ($h -eq [IntPtr]::Zero) { throw "OpenProcess failed." }
function Rd32([int64]$a) { $b = New-Object byte[] 4; $n = 0
    if ([HScan]::ReadProcessMemory($h, [IntPtr]$a, $b, 4, [ref]$n)) { [BitConverter]::ToInt32($b,0) } else { 0 } }
function RdF([int64]$a) { $b = New-Object byte[] 4; $n = 0
    if ([HScan]::ReadProcessMemory($h, [IntPtr]$a, $b, 4, [ref]$n)) { [BitConverter]::ToSingle($b,0) } else { 0 } }

$w = Rd32 0x54a264; $sub = Rd32 $w; $ent = Rd32 ($sub + 0x70)
if ($ent -eq 0) { throw "Player entity NULL - load a mission first." }
New-Item -ItemType Directory -Force $OutDir | Out-Null
Get-ChildItem $OutDir -Filter *.bin -ErrorAction SilentlyContinue | Remove-Item -Force

# --- enumerate committed, readable regions -----------------------------------
$regions = @(); $addr = [int64]0x10000; $limit = [int64]0x7FFF0000; $total = 0
while ($addr -lt $limit) {
    $mbi = New-Object MBI
    $r = [HScan]::VirtualQueryEx($h, [IntPtr]$addr, [ref]$mbi, [Runtime.InteropServices.Marshal]::SizeOf($mbi))
    if ($r -eq 0) { break }
    $size = [int64]$mbi.RegionSize
    if ($size -le 0) { break }
    $isCommit = ($mbi.State -eq 0x1000)
    # readable, writable data pages only (skip images' code, guard, noaccess)
    $okProt = @(0x04, 0x02, 0x40, 0x08, 0x20) -contains $mbi.Protect
    if ($isCommit -and $okProt -and $size -le ($MaxRegionMB * 1MB) -and $total -lt ($BudgetMB * 1MB)) {
        $regions += [pscustomobject]@{ Base = [int64]$mbi.BaseAddress; Size = $size }
        $total += $size
    }
    $addr += $size
}
Write-Host ("regions: {0}   total {1:N1} MB   entity=0x{2:X}" -f $regions.Count, ($total/1MB), $ent) -ForegroundColor Cyan
$regions | ForEach-Object { "{0:X8},{1}" -f $_.Base, $_.Size } | Set-Content (Join-Path $OutDir 'regions.csv')

Write-Host "Waiting for a LIVE sim - click the GAME window and drive STRAIGHT..." -ForegroundColor Yellow
$deadline = (Get-Date).AddSeconds($WaitSeconds)
$prev = RdF ($ent + 0xAC); $chg = 0
do {
    Start-Sleep -Milliseconds 100
    $spd = RdF ($ent + 0xAC)
    if ($spd -ne $prev) { $chg++ } else { $chg = 0 }
    $prev = $spd
    if ($chg -ge 3 -and $spd -ge $MinSpeed) { break }
} while ((Get-Date) -lt $deadline)
if (-not ($chg -ge 3 -and $spd -ge $MinSpeed)) { throw ("No live motion (last {0:N2})." -f $spd) }
Write-Host ("LIVE ({0:N2} m/s). Snapshotting - KEEP DRIVING STRAIGHT." -f $spd) -ForegroundColor Green

function Snap([int]$idx) {
    $fs = [IO.File]::Create((Join-Path $OutDir ("h{0}.bin" -f $idx)))
    try {
        foreach ($rg in $regions) {
            $b = New-Object byte[] $rg.Size; $n = 0
            if ([HScan]::ReadProcessMemory($h, [IntPtr]$rg.Base, $b, $rg.Size, [ref]$n) -and $n -gt 0) { $fs.Write($b, 0, $n) }
            else { $fs.Write((New-Object byte[] $rg.Size), 0, $rg.Size) }   # keep offsets aligned
        }
    } finally { $fs.Close() }
}
$meta = @('idx,t,vx,vy,vz,speed')
$sw = [Diagnostics.Stopwatch]::StartNew()
for ($k = 0; $k -lt 3; $k++) {
    $t = $sw.Elapsed.TotalSeconds
    $vx = RdF ($ent + 0xBC); $vy = RdF ($ent + 0xC0); $vz = RdF ($ent + 0xC4); $sp = RdF ($ent + 0xAC)
    Snap $k
    $meta += ("{0},{1},{2},{3},{4},{5}" -f $k, $t, $vx, $vy, $vz, $sp)
    Write-Host ("  snap {0}: t={1:N3}s v=({2:N2},{3:N2},{4:N2})" -f $k, $t, $vx, $vy, $vz)
    if ($k -lt 2) { Start-Sleep -Milliseconds $GapMs }
}
$meta | Set-Content (Join-Path $OutDir 'meta.csv')
Write-Host ("DONE - 3 heap snapshots in {0}" -f (Resolve-Path $OutDir)) -ForegroundColor Green
[HScan]::CloseHandle($h) | Out-Null
