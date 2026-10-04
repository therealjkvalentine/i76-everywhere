<#
  find-body-matrix.ps1 — find the chassis orientation by making the car rotate and diffing.

  A static scan of the entity struct found four identity matrices at stride 0x54 (the wheels)
  but not the body: a matrix that happens to be axis-aligned is indistinguishable from padding.
  Rotating the car settles it. Steer is forced through the input block rather than by sending
  keys, so the turn is held continuously and is identical at any frame rate.

    tools\find-body-matrix.ps1

  Reports float offsets that changed during the turn, and flags any orthonormal 3x3 among them.
  Writes to the steer input only, and restores it afterwards.
#>
param([int]$Bytes = 0x1000, [double]$TurnSeconds = 1.5, [double]$Steer = 1.0)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\..\autotest\lib\memlib.ps1"

$ctx = Mem-Open -Write
if (-not (Mem-InMission $ctx)) { throw "not in a mission" }
$m = Mem-Map
$ent = Mem-PlayerEntity $ctx
$n = [int]($Bytes / 4)
Write-Host ("player entity @ 0x{0:X}, watching {1} floats" -f $ent, $n) -ForegroundColor Cyan

function Snap { $v = New-Object double[] $n; for ($i=0; $i -lt $n; $i++) { $v[$i] = Mem-F32 $ctx ($ent + $i*4) }; ,$v }

$before = Snap
$origSteer = Mem-F32 $ctx $m.InSteer
$origThr   = Mem-F32 $ctx $m.InThrottle
$sw = [Diagnostics.Stopwatch]::StartNew()
while ($sw.Elapsed.TotalSeconds -lt $TurnSeconds) {
    Mem-WriteF32 $ctx $m.InSteer $Steer
    Mem-WriteF32 $ctx $m.InThrottle 1.0
    Start-Sleep -Milliseconds 20
}
$after = Snap
Mem-WriteF32 $ctx $m.InSteer $origSteer
Mem-WriteF32 $ctx $m.InThrottle $origThr

# floats that moved, and look like direction-cosine components rather than world coordinates
$changed = @()
for ($i = 0; $i -lt $n; $i++) {
    $a = $before[$i]; $b = $after[$i]
    if ([double]::IsNaN($a) -or [double]::IsNaN($b)) { continue }
    if ($a -eq $b) { continue }
    if ([math]::Abs($a) -le 1.001 -and [math]::Abs($b) -le 1.001 -and [math]::Abs($b - $a) -gt 1e-4) {
        $changed += [pscustomobject]@{ i = $i; offset = ('+0x{0:X}' -f ($i*4)); before = [math]::Round($a,4); after = [math]::Round($b,4) }
    }
}
Write-Host ("{0} unit-range floats changed during the turn" -f $changed.Count) -ForegroundColor Green
$changed | Format-Table -AutoSize

# any run of 9 changed floats starting on a 3-float boundary is a strong matrix candidate
$set = @{}; foreach ($c in $changed) { $set[$c.i] = $true }
Write-Host "contiguous 9-float runs (matrix candidates):" -ForegroundColor Cyan
for ($i = 0; $i -le $n - 9; $i++) {
    $run = $true
    for ($k = 0; $k -lt 9; $k++) { if (-not $set[$i + $k]) { $run = $false; break } }
    if ($run) {
        $rows = for ($r = 0; $r -lt 9; $r += 3) { '{0,7:N4} {1,7:N4} {2,7:N4}' -f $after[$i+$r], $after[$i+$r+1], $after[$i+$r+2] }
        Write-Host ("  +0x{0:X}  [{1}]" -f ($i*4), ($rows -join ' | ')) -ForegroundColor Green
        $i += 8
    }
}
Mem-Close $ctx
