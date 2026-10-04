<#
  wheel-probe.ps1 - map the per-wheel structs (found via the 4x unrolled call to 0x43C960:
  wheel pointers at +0x3A8/+0x3AC/+0x3B8/+0x3BC on the entity or its logic object).
  Phase 1: dump each wheel struct; classify every dword STATIC (parameter) vs dyn (state).
  Run IN mission, ideally moving so state fields visibly change.
#>
param([int]$Bytes = 0x140, [int]$Samples = 30, [int]$IntervalMs = 80)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\..\..\autotest\lib\memlib.ps1"

$ctx = Mem-Open
$ent = Mem-PlayerEntity $ctx
if (-not $ent) { throw "no player entity" }
$logic = Mem-I32 $ctx ($ent + 0x108)
Write-Host ("entity=0x{0:X}  logic=0x{1:X}" -f $ent, $logic)

function Valid-Ptr([int64]$p) { ($p -gt 0x10000) -and ($p -lt 0x7FFF0000) }
$found = $null
foreach ($base in @(@('entity',$ent), @('logic',$logic))) {
    $name = $base[0]; $b = $base[1]
    if (-not (Valid-Ptr $b)) { continue }
    $ptrs = @(0x3A8,0x3AC,0x3B8,0x3BC) | ForEach-Object { Mem-I32 $ctx ($b + $_) }
    $ok = @($ptrs | Where-Object { Valid-Ptr $_ }).Count
    $distinct = @($ptrs | Select-Object -Unique).Count
    Write-Host ("{0}+0x3A8..: {1}  valid={2} distinct={3}" -f $name, (($ptrs | ForEach-Object { '0x{0:X}' -f $_ }) -join ' '), $ok, $distinct)
    if ($ok -eq 4 -and $distinct -eq 4 -and -not $found) { $found = @($name, $ptrs) }
}
if (-not $found) { throw "wheel pointers not resolved on either base" }
$wheels = $found[1]
Write-Host ("wheel structs via {0}: {1}" -f $found[0], (($wheels | ForEach-Object { '0x{0:X}' -f $_ }) -join ' '))

$hist = @{}
for ($s = 0; $s -lt $Samples; $s++) {
    for ($w = 0; $w -lt 4; $w++) {
        for ($off = 0; $off -lt $Bytes; $off += 4) {
            $v = Mem-F32 $ctx ($wheels[$w] + $off)
            $k = "$w,$off"
            if (-not $hist.ContainsKey($k)) { $hist[$k] = New-Object System.Collections.ArrayList }
            [void]$hist[$k].Add($v)
        }
    }
    Start-Sleep -Milliseconds $IntervalMs
}
Write-Host ""
Write-Host ("{0,-6} {1,-12} {2,-12} {3,-8} {4}" -f 'off','w0_val','range_w0','static?','same_all_wheels?')
for ($off = 0; $off -lt $Bytes; $off += 4) {
    $v0 = $hist["0,$off"]
    $fin = @($v0 | Where-Object { -not [double]::IsNaN($_) -and [math]::Abs($_) -lt 1e12 })
    if ($fin.Count -lt $Samples) { Write-Host ("0x{0:X3}  (non-float)" -f $off); continue }
    $mm = $fin | Measure-Object -Minimum -Maximum
    $rng = $mm.Maximum - $mm.Minimum
    $static = [math]::Abs($rng) -lt 1e-9
    $same = $true
    for ($w = 1; $w -lt 4; $w++) {
        $vw = @($hist["$w,$off"])[0]
        if ([double]::IsNaN($vw) -or [math]::Abs($vw - $fin[0]) -gt ([math]::Abs($fin[0])*1e-4 + 1e-6)) { $same = $false }
    }
    Write-Host ("0x{0,-4:X3} {1,-12:G6} {2,-12:G6} {3,-8} {4}" -f $off, $fin[0], $rng, $(if($static){'STATIC'}else{'dyn'}), $(if($same){'same'}else{'differs'}))
}
Mem-Close $ctx
