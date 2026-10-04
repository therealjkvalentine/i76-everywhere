<#
  dump-eye.ps1 — print the render-consumed eye transform at 0x5FCDC4 and check its layout.

  The chassis world matrix is not in the entity struct (only local part transforms are), but
  the view transform is a static global the renderer reads every frame, and in cockpit view it
  carries the chassis orientation. That makes chassis ROLL measurable without ever finding the
  entity's own matrix.

  Prints 16 floats and marks which 9-float window is orthonormal, so the position and matrix
  fields identify themselves.
#>
param([int]$Floats = 16, [int64]$Addr = 0x5FCDC4)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\..\autotest\lib\memlib.ps1"
$ctx = Mem-Open
$v = Mem-Floats $ctx $Addr $Floats     # ONE call - a torn read makes a rotation look non-orthonormal
if (-not $v) { throw "read failed at 0x$('{0:X}' -f $Addr)" }
for ($i = 0; $i -lt $Floats; $i++) { "  +0x{0:X2}  [{1,2}]  {2,12:N5}" -f ($i*4), $i, $v[$i] }
function Dot($a,$b){ $v[$a]*$v[$b] + $v[$a+1]*$v[$b+1] + $v[$a+2]*$v[$b+2] }
Write-Host "`northonormal 3x3 windows:" -ForegroundColor Cyan
for ($i = 0; $i -le $Floats - 9; $i++) {
    $ok = $true
    foreach ($r in 0,3,6) { if ([math]::Abs((Dot ($i+$r) ($i+$r)) - 1.0) -gt 0.02) { $ok=$false; break } }
    if ($ok) { foreach ($p in @(0,3),@(0,6),@(3,6)) { if ([math]::Abs((Dot ($i+$p[0]) ($i+$p[1]))) -gt 0.02) { $ok=$false; break } } }
    if ($ok) { Write-Host ("  matrix at float[{0}] (+0x{1:X})" -f $i, ($i*4)) -ForegroundColor Green }
}
Mem-Close $ctx
