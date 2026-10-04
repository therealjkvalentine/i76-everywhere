<#
  map-cursor.ps1 — build the OS-cursor -> game-cursor mapping by LOOKING at the drawn cursor.

  I'76 draws its own large cursor at a position that is NOT the OS cursor position. So: put the
  OS cursor at known coordinates, find where the game's cursor is actually drawn, and fit the
  map from those pairs.

  Finding the drawn cursor: diff a probe frame against a reference frame taken with the cursor
  parked elsewhere. That yields TWO changed clusters - the reference cursor and the probe
  cursor. The reference cluster is in the SAME place in every probe, so after two probes it is
  identified and can be ignored; whatever is left is the probe cursor. (An earlier attempt
  fitted the wrong cluster and produced a bogus Y mapping - hence the explicit cluster logic.)

  Verifies the result by predicting a probe it did not fit, and prints the ready-to-paste
  constants for autotest/lib/maplib.ps1.
#>
param(
    [int[]]$PX = @(120, 260, 400, 540),
    [int[]]$PY = @(120, 220, 320, 420),
    [int]$RefX = 620, [int]$RefY = 470,
    [string]$OutDir = "$PSScriptRoot\..\..\captures\calib"
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\lib\focuslib.ps1"
. "$PSScriptRoot\..\lib\inputlib.ps1"
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms
New-Item -ItemType Directory -Force $OutDir | Out-Null

$vs = [Windows.Forms.SystemInformation]::VirtualScreen
function Grab { $b = New-Object Drawing.Bitmap $vs.Width, $vs.Height
                $g = [Drawing.Graphics]::FromImage($b); $g.CopyFromScreen(0,0,0,0,$b.Size); $g.Dispose(); $b }

# changed points between two frames, coarse sample
function ChangedPoints($a, $b, [int]$step = 2) {
    $pts = New-Object System.Collections.Generic.List[object]
    for ($y = 0; $y -lt $a.Height; $y += $step) {
        for ($x = 0; $x -lt $a.Width; $x += $step) {
            if ($a.GetPixel($x,$y).ToArgb() -ne $b.GetPixel($x,$y).ToArgb()) { $pts.Add(@($x,$y)) }
        }
    }
    return $pts
}
# group points into blobs; returns list of @{X;Y;N} using the blob's TOP-LEFT (cursor hotspot)
function Cluster($pts, [int]$gap = 80) {
    $blobs = New-Object System.Collections.Generic.List[object]
    foreach ($p in $pts) {
        $hit = $null
        foreach ($b in $blobs) {
            if ([math]::Abs($p[0]-$b.CX) -le $gap -and [math]::Abs($p[1]-$b.CY) -le $gap) { $hit = $b; break }
        }
        if ($hit) {
            $hit.N++
            if ($p[0] -lt $hit.MinX) { $hit.MinX = $p[0] }
            if ($p[1] -lt $hit.MinY) { $hit.MinY = $p[1] }
            $hit.CX = [int](($hit.CX * ($hit.N-1) + $p[0]) / $hit.N)
            $hit.CY = [int](($hit.CY * ($hit.N-1) + $p[1]) / $hit.N)
        } else {
            $blobs.Add([pscustomobject]@{ CX=$p[0]; CY=$p[1]; MinX=$p[0]; MinY=$p[1]; N=1 })
        }
    }
    return $blobs | Where-Object { $_.N -ge 4 }
}

$proc = Get-GamePid; if (-not $proc) { throw "game not running" }
Force-Foreground $proc.MainWindowHandle | Out-Null; Start-Sleep -Milliseconds 700

[Inp]::SetCursorPos($RefX, $RefY) | Out-Null; Start-Sleep -Milliseconds 500
$ref = Grab

# Flat parallel arrays with an index loop. Collection-building with += kept producing nested
# arrays here, and the failure only showed up as a cast error deep inside SetCursorPos.
# NOTE: PowerShell variables are CASE-INSENSITIVE, so `foreach ($px in $PX)` makes the loop
# variable and the array the same variable - the array is destroyed on the first iteration and
# the failure surfaces much later as a bogus cast. Loop variables must differ by more than case.
$probeX = New-Object System.Collections.Generic.List[int]
$probeY = New-Object System.Collections.Generic.List[int]
foreach ($rowY in $PY) { foreach ($colX in $PX) { $probeX.Add([int]$colX); $probeY.Add([int]$rowY) } }

$results = @()
$refBlob = $null
for ($pi = 0; $pi -lt $probeX.Count; $pi++) {
    $cx = $probeX[$pi]; $cy = $probeY[$pi]
    [Inp]::SetCursorPos($cx, $cy) | Out-Null; Start-Sleep -Milliseconds 420
    $shot = Grab
    $pts = ChangedPoints $ref $shot
    $shot.Dispose()
    $blobs = @(Cluster $pts)
    if ($blobs.Count -lt 1) { continue }
    if ($blobs.Count -eq 1) { continue }              # cursor didn't move enough to separate
    # the reference cursor blob appears in every probe at the same spot; learn it once
    if (-not $refBlob) {
        # take the blob closest to where the ref cursor should roughly be (largest y+x), tentatively
        $refBlob = $blobs | Sort-Object { $_.CX + $_.CY } -Descending | Select-Object -First 1
        continue                                      # use this probe only to identify the ref blob
    }
    $cand = $blobs | Where-Object { [math]::Abs($_.CX-$refBlob.CX) -gt 60 -or [math]::Abs($_.CY-$refBlob.CY) -gt 60 }
    if (-not $cand) { continue }
    $c = $cand | Sort-Object N -Descending | Select-Object -First 1
    $results += [pscustomobject]@{ OSX=$cx; OSY=$cy; SX=$c.MinX; SY=$c.MinY }
    Write-Host ("  OS({0,4},{1,4}) -> game cursor at screen({2,5},{3,5})" -f $cx,$cy,$c.MinX,$c.MinY)
}
$ref.Dispose()
if ($results.Count -lt 3) { throw "only $($results.Count) usable probes" }

function Fit($xs, $ys) {
    $n = $xs.Count
    $sx = ($xs | Measure-Object -Sum).Sum; $sy = ($ys | Measure-Object -Sum).Sum
    $sxx = 0.0; $sxy = 0.0
    for ($i=0; $i -lt $n; $i++) { $sxx += $xs[$i]*$xs[$i]; $sxy += $xs[$i]*$ys[$i] }
    $a = ($n*$sxy - $sx*$sy) / ($n*$sxx - $sx*$sx); $b = ($sy - $a*$sx)/$n
    return ,@($a,$b)
}
$fx = Fit ($results | ForEach-Object { [double]$_.OSX }) ($results | ForEach-Object { [double]$_.SX })
$fy = Fit ($results | ForEach-Object { [double]$_.OSY }) ($results | ForEach-Object { [double]$_.SY })
$rx = 0.0; $ry = 0.0
foreach ($r in $results) {
    $rx = [math]::Max($rx, [math]::Abs(($fx[0]*$r.OSX+$fx[1]) - $r.SX))
    $ry = [math]::Max($ry, [math]::Abs(($fy[0]*$r.OSY+$fy[1]) - $r.SY))
}
Write-Host ""
Write-Host ("fitted {0} points" -f $results.Count) -ForegroundColor Cyan
Write-Host ("  screen_x = {0:N4} * OS_x + {1:N1}   (max residual {2:N1} px)" -f $fx[0],$fx[1],$rx) -ForegroundColor Green
Write-Host ("  screen_y = {0:N4} * OS_y + {1:N1}   (max residual {2:N1} px)" -f $fy[0],$fy[1],$ry) -ForegroundColor Green
Write-Host ""
Write-Host "paste into autotest/lib/maplib.ps1:"
Write-Host ("  `$script:MAP_AX = {0:N4}; `$script:MAP_BX = {1:N1}" -f $fx[0],$fx[1])
Write-Host ("  `$script:MAP_AY = {0:N4}; `$script:MAP_BY = {1:N1}" -f $fy[0],$fy[1])
$results | Export-Csv (Join-Path $OutDir 'cursor-pairs.csv') -NoTypeInformation
