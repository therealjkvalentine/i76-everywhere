<#
  find-orientation.ps1 — locate the player's orientation matrix inside the entity struct.

  Orientation was the blocker for the mid-air over-rotation and chassis-roll bugs: angular
  velocity is known (+0xC8) but not what it integrates into. A rotation matrix does not need to
  be guessed at, because it identifies itself - three consecutive float3 rows, each of unit
  length and mutually perpendicular. Scanning the struct for that pattern finds it outright.

    tools\find-orientation.ps1              # dump + identify
    tools\find-orientation.ps1 -Watch 5     # then print the matrix live for 5s

  READ-ONLY.
#>
param([int]$Bytes = 0x300, [double]$Watch = 0)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\..\autotest\lib\memlib.ps1"

$ctx = Mem-Open
if (-not (Mem-InMission $ctx)) { throw "not in a mission" }
$ent = Mem-PlayerEntity $ctx
Write-Host ("player entity @ 0x{0:X}" -f $ent) -ForegroundColor Cyan

function Read-Floats($base, $count) {
    $v = New-Object double[] $count
    for ($i = 0; $i -lt $count; $i++) { $v[$i] = Mem-F32 $ctx ($base + $i * 4) }
    return $v
}
function Dot($f, $a, $b) { $f[$a]*$f[$b] + $f[$a+1]*$f[$b+1] + $f[$a+2]*$f[$b+2] }

$n = [int]($Bytes / 4)
$f = Read-Floats $ent $n

$hits = @()
for ($i = 0; $i -le $n - 9; $i++) {
    $ok = $true
    foreach ($r in 0, 3, 6) {
        $l = Dot $f ($i+$r) ($i+$r)
        if ([double]::IsNaN($l) -or [math]::Abs($l - 1.0) -gt 0.02) { $ok = $false; break }
    }
    if (-not $ok) { continue }
    # rows must also be mutually perpendicular, or any three unit vectors would qualify
    foreach ($p in @(0,3),@(0,6),@(3,6)) {
        if ([math]::Abs((Dot $f ($i+$p[0]) ($i+$p[1]))) -gt 0.02) { $ok = $false; break }
    }
    if ($ok) {
        $hits += [pscustomobject]@{
            offset = ('+0x{0:X}' -f ($i * 4))
            addr   = ('0x{0:X}' -f ($ent + $i * 4))
            row0   = ('{0,7:N4} {1,7:N4} {2,7:N4}' -f $f[$i],   $f[$i+1], $f[$i+2])
            row1   = ('{0,7:N4} {1,7:N4} {2,7:N4}' -f $f[$i+3], $f[$i+4], $f[$i+5])
            row2   = ('{0,7:N4} {1,7:N4} {2,7:N4}' -f $f[$i+6], $f[$i+7], $f[$i+8])
        }
        $i += 8   # don't report the same matrix nine times at shifted offsets
    }
}
if ($hits) {
    Write-Host ("{0} orthonormal 3x3 block(s) in the first 0x{1:X} bytes:" -f $hits.Count, $Bytes) -ForegroundColor Green
    $hits | Format-Table -AutoSize
} else {
    Write-Host "no orthonormal 3x3 found - orientation may be a quaternion or Euler triple" -ForegroundColor Yellow
}

if ($Watch -gt 0 -and $hits) {
    $o = [Convert]::ToInt64(($hits[0].addr -replace '^0x',''), 16)
    $sw = [Diagnostics.Stopwatch]::StartNew()
    while ($sw.Elapsed.TotalSeconds -lt $Watch) {
        $m = Read-Floats $o 9
        Write-Host ("{0,7:N4} {1,7:N4} {2,7:N4} | {3,7:N4} {4,7:N4} {5,7:N4} | {6,7:N4} {7,7:N4} {8,7:N4}" -f $m)
        Start-Sleep -Milliseconds 250
    }
}
Mem-Close $ctx
