<#
  snap-static.ps1 — raw dump of the exe's static data range to a file.

  find-perframe.ps1 answers "what CHANGES every frame". This answers a different and more
  useful question: "what has a DIFFERENT VALUE at 20 Hz than at 60 Hz". A frame delta-time
  global is nearly constant within a run (so the per-frame detector never flags it) but is
  exactly 3x smaller at 60 Hz — which is the signature ratio-scan.py looks for.

    tools\snap-static.ps1 -Label at20
    tools\snap-static.ps1 -Label at60
    python tools\ratio-scan.py captures\snap\at20.bin captures\snap\at60.bin

  READ-ONLY. Takes a fraction of a second, so it can be taken at a matched moment (e.g. car
  parked in the training mission) in both runs.
#>
param(
    [Parameter(Mandatory = $true)][string]$Label,
    [int64]$Lo = 0x400000,
    [int64]$Hi = 0x900000,
    [string]$OutDir = "$PSScriptRoot\..\..\captures\snap",
    [string]$RequirePath = 'i76-uncap-lab'
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\..\autotest\lib\memlib.ps1"

$ctx = Mem-Open
New-Item -ItemType Directory -Force $OutDir | Out-Null
$out = Join-Path $OutDir "$Label.bin"
if (Test-Path $out) { Remove-Item $out -Force }   # never let a stale dump masquerade as fresh

$total = [int]($Hi - $Lo)
$buf = New-Object byte[] $total
$chunk = 0x10000
$read = 0
for ($a = $Lo; $a -lt $Hi; $a += $chunk) {
    $len = [int][math]::Min($chunk, $Hi - $a)
    $tmp = New-Object byte[] $len
    $n = 0
    if ([I76Mem]::ReadProcessMemory($ctx.H, [IntPtr]$a, $tmp, $len, [ref]$n) -and $n -gt 0) {
        [Array]::Copy($tmp, 0, $buf, [int]($a - $Lo), $n)
        $read += $n
    }
}
[IO.File]::WriteAllBytes($out, $buf)
Mem-Close $ctx
Write-Host ("{0}: {1:N0} of {2:N0} bytes read from 0x{3:X} -> {4}" -f $Label, $read, $total, $Lo, $out) -ForegroundColor Green
