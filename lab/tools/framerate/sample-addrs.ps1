<#
  sample-addrs.ps1 — repeatedly read a set of addresses and report mean/min/max.

  A single snapshot cannot tell a real per-frame delta-time from a value that merely happened
  to differ between two runs. Sampling the same address a few hundred times and comparing the
  MEAN at 20 Hz against the MEAN at 60 Hz does: a delta-time sits at 1/rate every frame, while
  noise wanders.

    tools\sample-addrs.ps1 -Addrs 0x654610,0x6543F8 -Seconds 4

  READ-ONLY.
#>
param(
    [Parameter(Mandatory = $true)][string[]]$Addrs,
    [double]$Seconds = 4,
    [string]$Csv
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\..\autotest\lib\memlib.ps1"

$ctx = Mem-Open
# -File passes "a,b,c" as a single argument, so split before parsing
$list = $Addrs -split '[,\s]+' | Where-Object { $_ } | ForEach-Object { [Convert]::ToInt64(($_ -replace '^0x',''), 16) }
$acc = @{}; foreach ($a in $list) { $acc[$a] = [System.Collections.Generic.List[double]]::new() }

$f0 = Mem-I32 $ctx 0x5A7E1C
$sw = [Diagnostics.Stopwatch]::StartNew()
while ($sw.Elapsed.TotalSeconds -lt $Seconds) {
    foreach ($a in $list) { $acc[$a].Add((Mem-F32 $ctx $a)) }
}
$f1 = Mem-I32 $ctx 0x5A7E1C
$fps = ($f1 - $f0) / $sw.Elapsed.TotalSeconds
Mem-Close $ctx

Write-Host ("{0:N1} fps over {1:N2}s, {2} samples each" -f $fps, $sw.Elapsed.TotalSeconds, $acc[$list[0]].Count) -ForegroundColor Cyan
$rows = foreach ($a in $list) {
    # .NET Framework 4.x (PowerShell 5.1) has no Double.IsFinite
    $v = $acc[$a] | Where-Object { -not [double]::IsNaN($_) -and -not [double]::IsInfinity($_) }
    if (-not $v) { continue }
    $mean = ($v | Measure-Object -Average).Average
    [pscustomobject]@{
        addr    = ('0x{0:X}' -f $a)
        mean    = [math]::Round($mean, 6)
        min     = [math]::Round(($v | Measure-Object -Minimum).Minimum, 6)
        max     = [math]::Round(($v | Measure-Object -Maximum).Maximum, 6)
        'x_fps' = [math]::Round($mean * $fps, 4)      # 1.0 here means the value IS 1/framerate
        fps     = [math]::Round($fps, 2)
    }
}
$rows | Format-Table -AutoSize
if ($Csv) { $rows | Export-Csv -NoTypeInformation $Csv }
