<#
  validate-cursor-map.ps1 — measure how wrong the derived cursor mapping is.

  Puts the OS cursor at a grid of positions, screenshots each, and locates the game's drawn
  cursor by differencing against a frame with the cursor parked off in a corner. Reports the
  residual between where maplib PREDICTED the cursor would be drawn and where it actually was.

  This is a check, not a calibration - maplib derives its numbers from the screen size and
  dgVoodoo's render resolution. If residuals here are more than a few pixels, the derivation
  is wrong (or ScalingMode isn't aspect-preserving), not the fit.
#>
param([string]$OutDir = "$PSScriptRoot\..\..\captures\cursorvalidate")
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\lib\focuslib.ps1"
. "$PSScriptRoot\..\lib\inputlib.ps1"
. "$PSScriptRoot\..\lib\maplib.ps1"
Add-Type -AssemblyName System.Drawing
New-Item -ItemType Directory -Force $OutDir | Out-Null

$cal = Init-CursorMap
Write-Host ("derived: contentLeft={0} contentTop={1} scaleX={2} scaleY={3}" -f `
    $cal.ContentLeft, $cal.ContentTop, $cal.ScaleX, $cal.ScaleY) -ForegroundColor Cyan

$proc = Get-GamePid
Force-Foreground $proc.MainWindowHandle | Out-Null
Start-Sleep -Milliseconds 600

$rect = Get-ContentRect
function Grab {
    $b = New-Object Drawing.Bitmap $rect.W, $rect.H
    $g = [Drawing.Graphics]::FromImage($b)
    $g.CopyFromScreen($rect.X, $rect.Y, 0, 0, (New-Object Drawing.Size($rect.W, $rect.H)))
    $g.Dispose(); return $b
}
function ToGray([Drawing.Bitmap]$bm) {
    # lock once; per-pixel GetPixel over 2304x1440 takes minutes
    $bd = $bm.LockBits((New-Object Drawing.Rectangle 0,0,$bm.Width,$bm.Height),
        [Drawing.Imaging.ImageLockMode]::ReadOnly, [Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $n = $bm.Width * $bm.Height * 4
    $buf = New-Object byte[] $n
    [Runtime.InteropServices.Marshal]::Copy($bd.Scan0, $buf, 0, $n)
    $bm.UnlockBits($bd); return $buf
}

# baseline with the cursor parked bottom-right of the 640x480 space
[Inp]::SetCursorPos(635, 475) | Out-Null; Start-Sleep -Milliseconds 400
$base = Grab; $baseBuf = ToGray $base

$probes = @(@(120,120), @(320,120), @(500,120), @(120,300), @(320,300), @(500,300), @(220,420), @(420,420))
$rows = @()
foreach ($p in $probes) {
    [Inp]::SetCursorPos($p[0], $p[1]) | Out-Null
    Start-Sleep -Milliseconds 350
    $shot = Grab; $buf = ToGray $shot

    # centroid of changed pixels = the drawn cursor
    $sx = 0.0; $sy = 0.0; $cnt = 0
    for ($y = 0; $y -lt $rect.H; $y += 2) {
        $row = $y * $rect.W * 4
        for ($x = 0; $x -lt $rect.W; $x += 2) {
            $i = $row + $x * 4
            $d = [math]::Abs([int]$buf[$i] - [int]$baseBuf[$i]) +
                 [math]::Abs([int]$buf[$i+1] - [int]$baseBuf[$i+1]) +
                 [math]::Abs([int]$buf[$i+2] - [int]$baseBuf[$i+2])
            if ($d -gt 90) { $sx += $x; $sy += $y; $cnt++ }
        }
    }
    $shot.Dispose()
    if ($cnt -lt 20) { Write-Host "  OS($($p[0]),$($p[1])): no cursor found" -ForegroundColor DarkYellow; continue }
    # centroid is the middle of the arrow sprite; its hotspot is the top-left tip
    $ax = $sx / $cnt; $ay = $sy / $cnt
    $pred = OS-ToScreen $p[0] $p[1]
    $rows += [pscustomobject]@{
        OSX = $p[0]; OSY = $p[1]
        PredX = $pred[0] - $rect.X; PredY = $pred[1] - $rect.Y
        ActX = [int]$ax; ActY = [int]$ay
        DX = [int]($ax - ($pred[0] - $rect.X)); DY = [int]($ay - ($pred[1] - $rect.Y))
        Pixels = $cnt
    }
}
$base.Dispose()
$rows | Format-Table -AutoSize
if ($rows.Count) {
    # a constant offset is just the sprite's centroid-vs-hotspot; SPREAD is what matters
    $mdx = ($rows | Measure-Object DX -Average).Average
    $mdy = ($rows | Measure-Object DY -Average).Average
    $spx = ($rows | ForEach-Object { [math]::Abs($_.DX - $mdx) } | Measure-Object -Maximum).Maximum
    $spy = ($rows | ForEach-Object { [math]::Abs($_.DY - $mdy) } | Measure-Object -Maximum).Maximum
    Write-Host ("mean offset (sprite centroid vs hotspot): {0:N1}, {1:N1} px" -f $mdx, $mdy) -ForegroundColor Cyan
    Write-Host ("max spread about the mean: {0:N1}, {1:N1} px  <- this is the mapping error" -f $spx, $spy) -ForegroundColor Green
    $rows | Export-Csv (Join-Path $OutDir 'residuals.csv') -NoTypeInformation
}
