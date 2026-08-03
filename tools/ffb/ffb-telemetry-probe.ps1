<#
  Find the player vehicle's position/velocity fields by watching them MOVE.

  WHY THIS EXISTS: a stationary car makes this impossible. Dumping the entity
  struct while parked shows plenty of world-scale floats and no way to tell a
  position from a bounding box, a spawn point or a mission constant. They only
  separate once the car is moving, and only by HOW they move.

  So: drive around for the sample window and this classifies every offset by
  behaviour rather than by value.

  Usage:
      powershell -ExecutionPolicy Bypass -File tools\ffb\ffb-telemetry-probe.ps1
      powershell ... -Seconds 45 -Range 0x400

  Be driving - accelerate, brake, turn both ways, and hit something if you can.
#>
param(
    [int]$Seconds = 30,
    [int]$Range   = 0x200,      # bytes of the entity struct to watch
    [int]$HZ      = 20
)
$ErrorActionPreference = 'Continue'

Add-Type -ErrorAction SilentlyContinue @"
using System;using System.Runtime.InteropServices;
public class TP {
 [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(uint a,bool i,int p);
 [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h,IntPtr a,byte[] b,int s,out int r);
}
"@

$proc = Get-Process i76,nitro -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $proc) { Write-Host "Game is not running." -ForegroundColor Red; exit 1 }
$hProc = [TP]::OpenProcess(0x38, $false, $proc.Id)

function RdInt([int64]$a) { $b = New-Object byte[] 4; $r = 0
    if ([TP]::ReadProcessMemory($hProc,[IntPtr]$a,$b,4,[ref]$r)) { [BitConverter]::ToInt32($b,0) } else { 0 } }
function RdBlk([int64]$a,[int]$n) { $b = New-Object byte[] $n; $r = 0
    if ([TP]::ReadProcessMemory($hProc,[IntPtr]$a,$b,$n,[ref]$r)) { $b } else { $null } }

# player_entity = [[[0x54a264]]+0x70]   (docs/GHIDRA-MEMORY-MAP.md, live-verified)
$ent = RdInt ((RdInt (RdInt 0x54a264)) + 0x70)
if ($ent -eq 0) { Write-Host "Player entity is NULL - are you in a mission?" -ForegroundColor Red; exit 1 }
Write-Host ("player entity = 0x{0:X8}" -f $ent) -ForegroundColor Cyan
Write-Host "DRIVE NOW - accelerate, brake, turn both ways, hit something. Sampling $Seconds s..." -ForegroundColor Yellow

$n = [int]($Seconds * $HZ)
$samples = New-Object System.Collections.ArrayList
for ($i = 0; $i -lt $n; $i++) {
    $blk = RdBlk $ent $Range
    if ($blk) { $null = $samples.Add($blk) }
    Start-Sleep -Milliseconds ([int](1000 / $HZ))
}
Write-Host "captured $($samples.Count) samples" -ForegroundColor Cyan

# ---- classify each 4-byte slot by HOW it moved ------------------------------
$rows = @()
for ($o = 0; $o -lt $Range; $o += 4) {
    $vals = foreach ($s in $samples) { [BitConverter]::ToSingle($s, $o) }
    $fin  = $vals | Where-Object { -not [double]::IsNaN($_) -and -not [double]::IsInfinity($_) }
    if ($fin.Count -lt ($samples.Count * 0.9)) { continue }
    $mn = ($fin | Measure-Object -Minimum).Minimum
    $mx = ($fin | Measure-Object -Maximum).Maximum
    $span = $mx - $mn
    if ($span -eq 0) { continue }

    # step statistics separate the classes:
    #   position  - large span, small SMOOTH steps, wanders monotonically
    #   velocity  - centred near 0, changes sign, moderate span
    #   matrix    - stays inside -1..1
    $steps = @(); for ($k = 1; $k -lt $fin.Count; $k++) { $steps += [math]::Abs($fin[$k] - $fin[$k-1]) }
    $meanStep = ($steps | Measure-Object -Average).Average
    $maxStep  = ($steps | Measure-Object -Maximum).Maximum
    $signs    = ($fin | Where-Object { $_ -lt 0 }).Count
    $crossesZero = ($signs -gt 0 -and $signs -lt $fin.Count)

    $cls = 'other'
    if ($mx -le 1.0001 -and $mn -ge -1.0001) { $cls = 'matrix/unit' }
    elseif ($span -gt 50 -and $meanStep -gt 0 -and $maxStep -lt ($span * 0.5)) { $cls = 'POSITION?' }
    elseif ($crossesZero -and $span -gt 0.5 -and $span -lt 200) { $cls = 'VELOCITY?' }

    $rows += [pscustomobject]@{
        Offset = ("+0x{0:X3}" -f $o); Min = [math]::Round($mn,2); Max = [math]::Round($mx,2)
        Span = [math]::Round($span,2); MeanStep = [math]::Round($meanStep,3); Class = $cls
    }
}

Write-Host "`n=== fields that MOVED, most interesting first ===" -ForegroundColor Green
$rows | Where-Object { $_.Class -in @('POSITION?','VELOCITY?') } |
    Sort-Object Class, @{e={-$_.Span}} | Format-Table -AutoSize | Out-String | Write-Host
Write-Host "=== everything else that moved ===" -ForegroundColor DarkGray
$rows | Where-Object { $_.Class -notin @('POSITION?','VELOCITY?') } |
    Sort-Object @{e={-$_.Span}} | Select-Object -First 25 | Format-Table -AutoSize | Out-String | Write-Host

$out = Join-Path $PSScriptRoot 'telemetry-probe-last.csv'
$rows | Export-Csv -NoTypeInformation -Path $out
Write-Host "full table -> $out" -ForegroundColor Cyan
Write-Host @"

READING THIS:
  Three consecutive POSITION? offsets are the world position (x,y,z) - that is
  the prize. Everything else derives from it without more RE: speed and
  acceleration from deltas, lateral acceleration (a slip proxy) against heading
  from the transform at +0x08, braking from negative longitudinal acceleration,
  and collisions from acceleration spikes.
  VELOCITY? offsets that track those deltas would be the engine's own velocity -
  nicer to read directly if present.
"@ -ForegroundColor Gray
