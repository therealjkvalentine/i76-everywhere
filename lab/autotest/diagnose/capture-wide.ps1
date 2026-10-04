<#
  capture-wide.ps1 — WIDE two-snapshot capture for the position-offset hunt (READ-ONLY).

  Why this exists: the first hunts scanned 0x200..0x1000 bytes of the player entity and
  found nothing moving like world position. The repo's own notes say the car struct is
  >0xa738 bytes — so those scans covered under 10% of it. This grabs the whole thing,
  plus the vehicle-LOGIC object ([ent+0x108]) and the FFB param block (0x4f2328, where
  the sibling FFB thread found RPM at +0xC), then writes raw snapshots for offline diff.

  It WAITS for the car to be moving (speed > -MinSpeed) and then captures automatically,
  so you can just drive — no timing coordination needed.

  Read-only: ReadProcessMemory only, never writes to the game.

  Usage (physical console, in a mission, then drive):
    powershell -ExecutionPolicy Bypass -File tools\capture-wide.ps1
#>
param(
    [string]$OutDir = "$PSScriptRoot\..\..\captures",
    [double]$MinSpeed = 5.0,
    [int]$GapMs = 700,
    [int]$EntBytes = 0xC000,
    [int]$WaitSeconds = 90
)
$ErrorActionPreference = 'Stop'

Add-Type @"
using System;
using System.Runtime.InteropServices;
public class CapW {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(uint a, bool i, int p);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr a, byte[] b, int s, out int r);
  [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
}
"@

$proc = Get-Process i76, nitro -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $proc) { throw "Interstate '76 is not running." }
$h = [CapW]::OpenProcess(0x10, $false, $proc.Id)
if ($h -eq [IntPtr]::Zero) { throw "OpenProcess failed." }

# NOTE: helper names must not collide with PowerShell aliases (ri = Remove-Item!).
function Rd32([int64]$a) { $b = New-Object byte[] 4; $n = 0
    if ([CapW]::ReadProcessMemory($h, [IntPtr]$a, $b, 4, [ref]$n) -and $n -eq 4) { [BitConverter]::ToInt32($b,0) } else { 0 } }
function RdF([int64]$a) { $b = New-Object byte[] 4; $n = 0
    if ([CapW]::ReadProcessMemory($h, [IntPtr]$a, $b, 4, [ref]$n) -and $n -eq 4) { [BitConverter]::ToSingle($b,0) } else { 0 } }
function RdBlk([int64]$a, [int]$s) { $b = New-Object byte[] $s; $n = 0
    if ([CapW]::ReadProcessMemory($h, [IntPtr]$a, $b, $s, [ref]$n) -and $n -gt 0) { ,$b } else { $null } }
# Page-wise read: a big struct may not span contiguous readable pages, and one
# failed page must not lose the whole capture. Reads until the first bad page.
function RdPaged([int64]$a, [int]$s) {
    $page = 0x1000
    $acc = New-Object 'System.Collections.Generic.List[byte]'
    for ($off = 0; $off -lt $s; $off += $page) {
        $chunk = [Math]::Min($page, $s - $off)
        $b = New-Object byte[] $chunk; $n = 0
        if (-not ([CapW]::ReadProcessMemory($h, [IntPtr]($a + $off), $b, $chunk, [ref]$n)) -or $n -ne $chunk) { break }
        $acc.AddRange($b)
    }
    if ($acc.Count -gt 0) { ,$acc.ToArray() } else { $null }
}

$w = Rd32 0x54a264; $sub = Rd32 $w; $ent = Rd32 ($sub + 0x70)
if ($ent -eq 0) { throw "Player entity is NULL - load a mission first." }
$logic = Rd32 ($ent + 0x108)
New-Item -ItemType Directory -Force $OutDir | Out-Null
Write-Host ("entity=0x{0:X}  logic=0x{1:X}  scanning 0x{2:X} bytes" -f $ent, $logic, $EntBytes) -ForegroundColor Cyan

# --- wait for a LIVE sim ------------------------------------------------------
# Speed alone is not enough: I'76 freezes the simulation when its window loses focus
# (renderer keeps drawing), so a frozen car holds a stale non-zero speed forever and a
# magnitude-only trigger fires instantly on dead data. That produced two byte-identical
# snapshots twice. Require the value to actually CHANGE across consecutive samples.
Write-Host ("Waiting for a LIVE sim: speed > {0} m/s AND changing. Click the GAME window and drive (up to {1}s)..." -f $MinSpeed, $WaitSeconds) -ForegroundColor Yellow
$deadline = (Get-Date).AddSeconds($WaitSeconds)
$prev = RdF ($ent + 0xAC)
$changes = 0
do {
    Start-Sleep -Milliseconds 100
    $spd = RdF ($ent + 0xAC)
    if ($spd -ne $prev) { $changes++ } else { $changes = 0 }   # want consecutive motion
    $prev = $spd
    if ($changes -ge 3 -and $spd -ge $MinSpeed) { break }
} while ((Get-Date) -lt $deadline)
if (-not ($changes -ge 3 -and $spd -ge $MinSpeed)) {
    throw ("No LIVE motion seen (last speed {0:N2}, consecutive changes {1}). Is the game window focused and the car driving?" -f $spd, $changes)
}
Write-Host ("LIVE sim confirmed ({0:N2} m/s, changing) - capturing. KEEP DRIVING STRAIGHT." -f $spd) -ForegroundColor Green

# --- snapshot A / B ----------------------------------------------------------
$vx = RdF ($ent + 0xBC); $vy = RdF ($ent + 0xC0); $vz = RdF ($ent + 0xC4)
$fA = Rd32 0x5A7E1C
$sw = [Diagnostics.Stopwatch]::StartNew()
$entA = RdPaged $ent $EntBytes
$logA = if ($logic) { RdPaged $logic 0x2000 } else { $null }
$ffbA = RdBlk 0x4f2328 0x16c
Start-Sleep -Milliseconds $GapMs
$entB = RdPaged $ent $EntBytes
$logB = if ($logic) { RdPaged $logic 0x2000 } else { $null }
$ffbB = RdBlk 0x4f2328 0x16c
$el = $sw.Elapsed.TotalSeconds
$fB = Rd32 0x5A7E1C
$spd2 = RdF ($ent + 0xAC)

if (-not $entA -or -not $entB) { throw "Entity read failed." }
[IO.File]::WriteAllBytes((Join-Path $OutDir 'entA.bin'), $entA)
[IO.File]::WriteAllBytes((Join-Path $OutDir 'entB.bin'), $entB)
if ($logA -and $logB) { [IO.File]::WriteAllBytes((Join-Path $OutDir 'logA.bin'), $logA); [IO.File]::WriteAllBytes((Join-Path $OutDir 'logB.bin'), $logB) }
if ($ffbA -and $ffbB) { [IO.File]::WriteAllBytes((Join-Path $OutDir 'ffbA.bin'), $ffbA); [IO.File]::WriteAllBytes((Join-Path $OutDir 'ffbB.bin'), $ffbB) }

# Metadata as plain lines (ConvertTo-Json on arrays of floats is fussy in PS5.1).
$lines = @(
    "entity=0x{0:X}" -f $ent
    "logic=0x{0:X}"  -f $logic
    "entBytes={0}"   -f $entA.Length
    "vel={0} {1} {2}" -f $vx, $vy, $vz
    "speedA={0}"     -f $spd
    "speedB={0}"     -f $spd2
    "elapsed={0}"    -f $el
    "frames={0}"     -f ($fB - $fA)
    "expDisp={0} {1} {2}" -f ($vx*$el), ($vy*$el), ($vz*$el)
)
$lines | Set-Content (Join-Path $OutDir 'meta.txt')
Write-Host ("CAPTURED {0} bytes x2. vel=({1:N2},{2:N2},{3:N2}) elapsed={4:N3}s frames={5} expDisp=({6:N2},{7:N2},{8:N2})" -f `
    $entA.Length, $vx, $vy, $vz, $el, ($fB-$fA), ($vx*$el), ($vy*$el), ($vz*$el)) -ForegroundColor Green
Write-Host ("Wrote to {0}" -f (Resolve-Path $OutDir)) -ForegroundColor Green
[CapW]::CloseHandle($h) | Out-Null
