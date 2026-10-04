<#
  calibrate-cursor.ps1 — measure the OS-cursor -> on-screen-cursor mapping properly.

  I'76 maps the mouse into its own space, so the cursor you see is NOT at the OS cursor
  position. An earlier two-point fit worked near the main menu but drifted badly elsewhere on
  the form (clicks landed ~120 px off), which is why "set AI drivers to 0" kept missing.

  Method: park the cursor far away, take a baseline, then for each probe point move the OS
  cursor there and diff the screen. The only thing that changed is the drawn cursor, so the
  bounding box of the difference IS the on-screen cursor position. Fit a least-squares affine
  map from those pairs.

  Run with any I'76 menu/form on screen (it needs a static background):
      tools\calibrate-cursor.ps1
#>
param(
    [int[]]$ProbeX = @(80, 200, 320, 440, 560),
    [int[]]$ProbeY = @(60, 160, 260, 360, 440),
    [string]$OutDir = "$PSScriptRoot\..\..\captures\calib"
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\lib\focuslib.ps1"
. "$PSScriptRoot\..\lib\inputlib.ps1"
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms
New-Item -ItemType Directory -Force $OutDir | Out-Null

$vs = [Windows.Forms.SystemInformation]::VirtualScreen
function Grab {
    $b = New-Object Drawing.Bitmap $vs.Width, $vs.Height
    $g = [Drawing.Graphics]::FromImage($b)
    try { $g.CopyFromScreen(0, 0, 0, 0, $b.Size) } finally { $g.Dispose() }
    return $b
}
function CursorBox($base, $shot) {
    # bounding box of changed pixels = the drawn cursor
    $minx = 99999; $miny = 99999; $maxx = -1; $maxy = -1
    for ($y = 0; $y -lt $base.Height; $y += 2) {
        for ($x = 0; $x -lt $base.Width; $x += 2) {
            if ($base.GetPixel($x,$y).ToArgb() -ne $shot.GetPixel($x,$y).ToArgb()) {
                if ($x -lt $minx) { $minx = $x }; if ($x -gt $maxx) { $maxx = $x }
                if ($y -lt $miny) { $miny = $y }; if ($y -gt $maxy) { $maxy = $y }
            }
        }
    }
    if ($maxx -lt 0) { return $null }
    # cursor hotspot is the top-left of the glyph
    return @{ X = $minx; Y = $miny; W = $maxx-$minx; H = $maxy-$miny }
}

$proc = Get-GamePid; if (-not $proc) { throw "game not running" }
Force-Foreground $proc.MainWindowHandle | Out-Null
Start-Sleep -Milliseconds 600

[Inp]::SetCursorPos(5, 5) | Out-Null      # park far from the probe grid
Start-Sleep -Milliseconds 500
$base = Grab

$pairs = @()
foreach ($py in $ProbeY) {
    foreach ($px in $ProbeX) {
        [Inp]::SetCursorPos($px, $py) | Out-Null
        Start-Sleep -Milliseconds 260
        $shot = Grab
        $box = CursorBox $base $shot
        $shot.Dispose()
        if ($box -and $box.W -lt 120 -and $box.H -lt 120) {
            $pairs += [pscustomobject]@{ OSX=$px; OSY=$py; SX=$box.X; SY=$box.Y }
            Write-Host ("  OS({0,4},{1,4}) -> screen({2,5},{3,5})" -f $px,$py,$box.X,$box.Y)
        }
    }
}
$base.Dispose()
if ($pairs.Count -lt 4) { throw "not enough probe points resolved ($($pairs.Count))" }

# least-squares fit: screen = a*OS + b, independently per axis
function Fit($os, $scr) {
    $n = $os.Count
    $sx = ($os | Measure-Object -Sum).Sum; $sy = ($scr | Measure-Object -Sum).Sum
    $sxx = 0.0; $sxy = 0.0
    for ($i = 0; $i -lt $n; $i++) { $sxx += $os[$i]*$os[$i]; $sxy += $os[$i]*$scr[$i] }
    $a = ($n*$sxy - $sx*$sy) / ($n*$sxx - $sx*$sx)
    $b = ($sy - $a*$sx) / $n
    return ,@($a, $b)
}
$fx = Fit ($pairs | ForEach-Object { [double]$_.OSX }) ($pairs | ForEach-Object { [double]$_.SX })
$fy = Fit ($pairs | ForEach-Object { [double]$_.OSY }) ($pairs | ForEach-Object { [double]$_.SY })

# residuals tell you whether a single affine map is actually good enough
$rx = 0.0; $ry = 0.0
foreach ($p in $pairs) {
    $rx = [math]::Max($rx, [math]::Abs(($fx[0]*$p.OSX + $fx[1]) - $p.SX))
    $ry = [math]::Max($ry, [math]::Abs(($fy[0]*$p.OSY + $fy[1]) - $p.SY))
}
Write-Host ""
Write-Host ("{0} points fitted" -f $pairs.Count) -ForegroundColor Cyan
Write-Host ("screen_x = {0:N4} * OS_x + {1:N1}    (max residual {2:N1} px)" -f $fx[0], $fx[1], $rx) -ForegroundColor Green
Write-Host ("screen_y = {0:N4} * OS_y + {1:N1}    (max residual {2:N1} px)" -f $fy[0], $fy[1], $ry) -ForegroundColor Green
Write-Host ""
Write-Host "inverse (put these in autotest/lib/maplib.ps1):"
Write-Host ("  OS_x = (screen_x - {0:N1}) / {1:N4}" -f $fx[1], $fx[0])
Write-Host ("  OS_y = (screen_y - {0:N1}) / {1:N4}" -f $fy[1], $fy[0])
$pairs | Export-Csv (Join-Path $OutDir 'pairs.csv') -NoTypeInformation
