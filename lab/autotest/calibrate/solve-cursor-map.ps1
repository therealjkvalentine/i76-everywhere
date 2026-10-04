<#
  solve-cursor-map.ps1 — measure the OS -> engine(640x480) cursor transform directly.

  Locates the DRAWN cursor by differencing against a parked-cursor reference frame and taking
  the densest compact window, rather than a centroid over the whole frame. The earlier attempt
  used a whole-frame centroid, which averaged the cursor together with menu items that brighten
  on hover - that is where the >1000 px residuals came from.

  Guard: the top-left corner animates on its own (see cursor-absolute-test), so it is masked.
#>
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\lib\focuslib.ps1"
. "$PSScriptRoot\..\lib\inputlib.ps1"
. "$PSScriptRoot\..\lib\maplib.ps1"
Add-Type -AssemblyName System.Drawing
$out = "$PSScriptRoot\..\..\captures\cursorsolve"
New-Item -ItemType Directory -Force $out | Out-Null
$proc = Get-GamePid; Force-Foreground $proc.MainWindowHandle | Out-Null
Start-Sleep -Milliseconds 600
$r = Get-ContentRect

function Buf640 {
    $b = New-Object Drawing.Bitmap $r.W, $r.H
    $g = [Drawing.Graphics]::FromImage($b)
    $g.CopyFromScreen($r.X, $r.Y, 0, 0, (New-Object Drawing.Size($r.W, $r.H)))
    $s = New-Object Drawing.Bitmap 640, 480
    $g2 = [Drawing.Graphics]::FromImage($s); $g2.InterpolationMode = 'NearestNeighbor'
    $g2.DrawImage($b, 0, 0, 640, 480)
    $bd = $s.LockBits((New-Object Drawing.Rectangle 0,0,640,480),
        [Drawing.Imaging.ImageLockMode]::ReadOnly, [Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $buf = New-Object byte[] (640*480*4)
    [Runtime.InteropServices.Marshal]::Copy($bd.Scan0, $buf, 0, $buf.Length)
    $s.UnlockBits($bd); $g.Dispose(); $g2.Dispose(); $b.Dispose(); $s.Dispose()
    return $buf
}
$PARK = @(20, 460)

function FindCursor([int]$ox, [int]$oy, $ref) {
    [Inp]::SetCursorPos($ox, $oy) | Out-Null; Start-Sleep -Milliseconds 400
    $cur = Buf640
    $best = -1; $bx = -1; $by = -1
    for ($y = 6; $y -lt 470; $y += 3) {
        for ($x = 60; $x -lt 634; $x += 3) {     # mask the animating top-left corner
            $n = 0
            for ($dy = 0; $dy -lt 24; $dy += 3) {
                $yy = $y + $dy; if ($yy -ge 480) { break }
                $row = $yy * 640 * 4
                for ($dx = 0; $dx -lt 24; $dx += 3) {
                    $xx = $x + $dx; if ($xx -ge 640) { break }
                    $i = $row + $xx * 4
                    $d = [math]::Abs([int]$cur[$i]   - [int]$ref[$i]) +
                         [math]::Abs([int]$cur[$i+1] - [int]$ref[$i+1]) +
                         [math]::Abs([int]$cur[$i+2] - [int]$ref[$i+2])
                    if ($d -gt 110) { $n++ }
                }
            }
            if ($n -gt $best) { $best = $n; $bx = $x; $by = $y }
        }
    }
    return [pscustomobject]@{ X = $bx; Y = $by; Score = $best }
}

[Inp]::SetCursorPos($PARK[0], $PARK[1]) | Out-Null; Start-Sleep -Milliseconds 500
$ref = Buf640

$probes = @(@(100,100), @(300,100), @(500,100), @(100,350), @(300,350), @(500,350))
$rows = @()
foreach ($p in $probes) {
    $f = FindCursor $p[0] $p[1] $ref
    Write-Host ("  OS({0,3},{1,3}) -> drawn near ({2,3},{3,3})  score={4}" -f $p[0],$p[1],$f.X,$f.Y,$f.Score)
    if ($f.Score -ge 8) { $rows += [pscustomobject]@{ OSX=$p[0]; OSY=$p[1]; EX=$f.X; EY=$f.Y } }
}
if ($rows.Count -lt 4) { Write-Host "not enough clean detections" -ForegroundColor Yellow; exit 1 }

function Fit($xs, $ys) {
    $n=$xs.Count; $sx=0.0;$sy=0.0;$sxx=0.0;$sxy=0.0
    for($i=0;$i -lt $n;$i++){ $sx+=$xs[$i]; $sy+=$ys[$i]; $sxx+=$xs[$i]*$xs[$i]; $sxy+=$xs[$i]*$ys[$i] }
    $a=($n*$sxy-$sx*$sy)/($n*$sxx-$sx*$sx); $b=($sy-$a*$sx)/$n
    return @($a,$b)
}
$fx = Fit ($rows.OSX) ($rows.EX)
$fy = Fit ($rows.OSY) ($rows.EY)
Write-Host ""
Write-Host ("engine_x = {0:N4} * OS_x + {1:N1}" -f $fx[0], $fx[1]) -ForegroundColor Green
Write-Host ("engine_y = {0:N4} * OS_y + {1:N1}" -f $fy[0], $fy[1]) -ForegroundColor Green
$rows | Export-Csv (Join-Path $out 'anchors.csv') -NoTypeInformation
