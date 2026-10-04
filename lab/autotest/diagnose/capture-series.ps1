<#
  capture-series.ps1 — MULTI-snapshot capture for the position hunt (READ-ONLY).

  Why: a single straight-line pair cannot tell world POSITION from "distance to the thing
  you're driving at" — both shrink/grow at your speed. Position is the field whose delta
  tracks the VELOCITY VECTOR through turns, every time. So this records a series of
  snapshots while you drive with plenty of turning, and the offline analysis keeps only
  offsets that match velocity across EVERY consecutive pair.

  Waits for a live sim (value must be CHANGING, not just non-zero: I'76 freezes the sim
  when its window loses focus while the renderer keeps running).

  Read-only: ReadProcessMemory only.

  Usage: start it, click into the game, then DRIVE WITH TURNS (left, right, straight)
  until it says DONE.
    powershell -ExecutionPolicy Bypass -File tools\capture-series.ps1
#>
param(
    [string]$OutDir = "$PSScriptRoot\..\..\captures\series",
    [int]$Snapshots = 14,
    [int]$IntervalMs = 260,
    [int]$EntBytes = 0x6000,
    [double]$MinSpeed = 3.0,
    [int]$WaitSeconds = 150
)
$ErrorActionPreference = 'Stop'

Add-Type @"
using System;
using System.Runtime.InteropServices;
public class CapS {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(uint a, bool i, int p);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr a, byte[] b, int s, out int r);
  [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
}
"@
$proc = Get-Process i76, nitro -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $proc) { throw "Interstate '76 is not running." }
$h = [CapS]::OpenProcess(0x10, $false, $proc.Id)
function Rd32([int64]$a) { $b = New-Object byte[] 4; $n = 0
    if ([CapS]::ReadProcessMemory($h, [IntPtr]$a, $b, 4, [ref]$n)) { [BitConverter]::ToInt32($b,0) } else { 0 } }
function RdF([int64]$a) { $b = New-Object byte[] 4; $n = 0
    if ([CapS]::ReadProcessMemory($h, [IntPtr]$a, $b, 4, [ref]$n)) { [BitConverter]::ToSingle($b,0) } else { 0 } }
function RdPaged([int64]$a, [int]$s) {
    $page = 0x1000; $acc = New-Object 'System.Collections.Generic.List[byte]'
    for ($off = 0; $off -lt $s; $off += $page) {
        $chunk = [Math]::Min($page, $s - $off); $b = New-Object byte[] $chunk; $n = 0
        if (-not ([CapS]::ReadProcessMemory($h, [IntPtr]($a + $off), $b, $chunk, [ref]$n)) -or $n -ne $chunk) { break }
        $acc.AddRange($b)
    }
    if ($acc.Count -gt 0) { ,$acc.ToArray() } else { $null }
}

$w = Rd32 0x54a264; $sub = Rd32 $w; $ent = Rd32 ($sub + 0x70)
if ($ent -eq 0) { throw "Player entity NULL - load a mission first." }
New-Item -ItemType Directory -Force $OutDir | Out-Null
Get-ChildItem $OutDir -Filter *.bin -ErrorAction SilentlyContinue | Remove-Item -Force
Write-Host ("entity=0x{0:X}  capturing {1} snapshots x 0x{2:X} bytes" -f $ent, $Snapshots, $EntBytes) -ForegroundColor Cyan
Write-Host "Waiting for a LIVE sim - click the GAME window and drive (turns please)..." -ForegroundColor Yellow

$deadline = (Get-Date).AddSeconds($WaitSeconds)
$prev = RdF ($ent + 0xAC); $chg = 0
do {
    Start-Sleep -Milliseconds 100
    $spd = RdF ($ent + 0xAC)
    if ($spd -ne $prev) { $chg++ } else { $chg = 0 }
    $prev = $spd
    if ($chg -ge 3 -and $spd -ge $MinSpeed) { break }
} while ((Get-Date) -lt $deadline)
if (-not ($chg -ge 3 -and $spd -ge $MinSpeed)) { throw ("No live motion (last {0:N2}). Is the game focused and driving?" -f $spd) }
Write-Host ("LIVE ({0:N2} m/s). Recording - KEEP DRIVING, TURN LEFT AND RIGHT." -f $spd) -ForegroundColor Green

$sw = [Diagnostics.Stopwatch]::StartNew()
$rows = @()
for ($k = 0; $k -lt $Snapshots; $k++) {
    $t = $sw.Elapsed.TotalSeconds
    $vx = RdF ($ent + 0xBC); $vy = RdF ($ent + 0xC0); $vz = RdF ($ent + 0xC4)
    $blk = RdPaged $ent $EntBytes
    if ($blk) { [IO.File]::WriteAllBytes((Join-Path $OutDir ("s{0:D2}.bin" -f $k)), $blk) }
    $rows += ("{0},{1},{2},{3},{4}" -f $k, $t, $vx, $vy, $vz)
    Write-Host ("  [{0,2}] t={1,6:N3}s  v=({2,7:N2},{3,5:N2},{4,7:N2})" -f $k, $t, $vx, $vy, $vz)
    Start-Sleep -Milliseconds $IntervalMs
}
@('idx,t,vx,vy,vz') + $rows | Set-Content (Join-Path $OutDir 'series.csv')
Write-Host ("DONE - {0} snapshots in {1}" -f $Snapshots, (Resolve-Path $OutDir)) -ForegroundColor Green
[CapS]::CloseHandle($h) | Out-Null
