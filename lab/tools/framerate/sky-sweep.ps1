<#
  sky-sweep.ps1 — robust version of the sky identification sweep.

  Freezes each per-frame candidate in turn and measures how much the sky band changes, with
  the car STATIONARY (training mission) so the view itself is not moving. Each candidate is
  wrapped in try/catch so one failure cannot abort the sweep (the first version died after a
  single candidate).

  Freeze is done inline (no background job) by alternating short write bursts with captures,
  which avoids the job-startup cost that made the earlier sweep unreliable.
#>
param([string[]]$Candidates = @('0x644334','0x501858','0x501918','0x59BCD4','0x5019B0','0x501AE0','0x4F70F8','0x524550'),
      [string]$OutDir = "$PSScriptRoot\..\..\captures\sky")
$ErrorActionPreference = 'Continue'
. "$PSScriptRoot\..\..\autotest\lib\memlib.ps1"
. "$PSScriptRoot\..\..\autotest\lib\focuslib.ps1"
. "$PSScriptRoot\..\..\autotest\lib\maplib.ps1"
Add-Type -AssemblyName System.Drawing
New-Item -ItemType Directory -Force $OutDir | Out-Null

$ctx = Mem-Open -Write
if (-not (Mem-InMission $ctx)) { throw "not in a mission" }
Force-Foreground $ctx.Proc.MainWindowHandle | Out-Null

function BandDiff($p1, $p2) {
    $A = [Drawing.Bitmap]::FromFile($p1); $B = [Drawing.Bitmap]::FromFile($p2)
    $sum = 0; $n = 0
    for ($y = 140; $y -lt 240; $y += 4) {
        for ($x = 150; $x -lt 550; $x += 4) {
            $pa = $A.GetPixel($x,$y); $pb = $B.GetPixel($x,$y)
            $sum += [math]::Abs($pa.R-$pb.R)+[math]::Abs($pa.G-$pb.G)+[math]::Abs($pa.B-$pb.B); $n++
        }
    }
    $A.Dispose(); $B.Dispose()
    return [math]::Round($sum/[math]::Max($n,1),2)
}

# Baseline, twice, so we know the natural spread before judging anything.
$b1 = $null
foreach ($i in 1,2) {
    Capture-UI (Join-Path $OutDir "base$i`_a.png") | Out-Null
    Start-Sleep -Milliseconds 900
    Capture-UI (Join-Path $OutDir "base$i`_b.png") | Out-Null
    $d = BandDiff (Join-Path $OutDir "base$i`_a.png") (Join-Path $OutDir "base$i`_b.png")
    Write-Host ("baseline {0}: {1}" -f $i, $d) -ForegroundColor Cyan
    if (-not $b1) { $b1 = $d } else { $b1 = [math]::Max($b1,$d) }
}

foreach ($c in $Candidates) {
    try {
        $addr = [Convert]::ToInt64($c.Substring(2),16)
        $orig = Mem-F32 $ctx $addr
        Capture-UI (Join-Path $OutDir "f_$($c.Substring(2))_a.png") | Out-Null
        # hold the value inline for ~900 ms while time passes
        $sw = [Diagnostics.Stopwatch]::StartNew()
        while ($sw.Elapsed.TotalMilliseconds -lt 900) { Mem-WriteF32 $ctx $addr $orig }
        Capture-UI (Join-Path $OutDir "f_$($c.Substring(2))_b.png") | Out-Null
        $d = BandDiff (Join-Path $OutDir "f_$($c.Substring(2))_a.png") (Join-Path $OutDir "f_$($c.Substring(2))_b.png")
        $verdict = if ($d -lt $b1*0.35) { '   <== SKY STOPPED' } else { '' }
        Write-Host ("{0}  frozen -> {1}   (baseline {2}){3}" -f $c, $d, $b1, $verdict)
    } catch {
        Write-Host ("{0}  FAILED: {1}" -f $c, $_.Exception.Message) -ForegroundColor Yellow
    }
}
Mem-Close $ctx
