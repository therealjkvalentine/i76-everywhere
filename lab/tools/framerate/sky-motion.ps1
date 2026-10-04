<#
  sky-motion.ps1 - measure how fast the sky scrolls, in pixels/second, with nobody watching.

  Why: the sky hunt stalled because every candidate test needed a human to say "still moving".
  This is the missing instrument: capture the sky band with the car perfectly still (the
  mission-start autopilot hold is ideal - throttle held at -1, zero speed), then estimate the
  scroll between frames by 2-D shift search on a downscaled band. Prints px/s per sample pair.

  Run IN a mission, during the start hold or after braking to a stop.
    sky-motion.ps1 -Tag 60fps -Pairs 5
#>
param(
    [string]$Tag = 'probe',
    [int]$Pairs = 5,
    [double]$GapSeconds = 1.0,
    [string]$OutDir = "$PSScriptRoot\..\..\captures\sky"
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\..\autotest\lib\focuslib.ps1"
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms

$proc = Get-GamePid
if (-not $proc) { throw "sandbox game not running" }
Force-Foreground $proc.MainWindowHandle | Out-Null
Start-Sleep -Milliseconds 400
New-Item -ItemType Directory -Force $OutDir | Out-Null

# find the game content rect (reuse uiclick geometry: client rect + 4:3 letterbox)
. "$PSScriptRoot\..\..\autotest\lib\uiclick.ps1"
$m = Get-UiMap
$sx = $m.Sx; $sy = $m.Sy; $scale = $m.Scale
# sky band in UI coords: x 40..600, y 145..225 (below the hanging HUD, above the horizon)
$bx = [int]($sx + 40*$scale);  $bw = [int](560*$scale)
$by = [int]($sy + 145*$scale); $bh = [int](80*$scale)

function Grab {
    $bmp = New-Object Drawing.Bitmap $bw,$bh
    $g = [Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen($bx,$by,0,0,(New-Object Drawing.Size $bw,$bh))
    $g.Dispose()
    # downscale x4 into a gray matrix
    $w=[int]($bw/4); $h=[int]($bh/4)
    $sm = New-Object Drawing.Bitmap $bmp,(New-Object Drawing.Size $w,$h)
    $mat = New-Object 'double[,]' $h,$w
    for ($y=0;$y -lt $h;$y++){ for ($x=0;$x -lt $w;$x++){ $c=$sm.GetPixel($x,$y); $mat[$y,$x] = 0.299*$c.R+0.587*$c.G+0.114*$c.B } }
    $bmp.Dispose(); $sm.Dispose()
    ,@($mat,$w,$h)
}
function Shift([object]$A,[object]$B,[int]$w,[int]$h) {
    # search best (dx,dy) in downscaled px minimizing SAD over overlap
    $bestD = 1e18; $bestX = 0; $bestY = 0
    for ($dy=-6; $dy -le 6; $dy++) {
      for ($dx=-30; $dx -le 30; $dx++) {
        $s=0.0; $n=0
        for ($y=[Math]::Max(0,(-$dy)); $y -lt [Math]::Min($h,($h-$dy)); $y+=2) {
          for ($x=[Math]::Max(0,(-$dx)); $x -lt [Math]::Min($w,($w-$dx)); $x+=2) {
            $va = $A[$y,$x]; $vb = $B[($y+$dy),($x+$dx)]; $s += [math]::Abs($va - $vb); $n++
          }
        }
        if ($n -gt 0) { $s = $s/$n; if ($s -lt $bestD) { $bestD=$s; $bestX=$dx; $bestY=$dy } }
      }
    }
    ,@($bestX,$bestY,$bestD)
}

Write-Host ("sky band: screen ({0},{1}) {2}x{3}" -f $bx,$by,$bw,$bh)
$prev = $null
$out = @("tag,pair,dx_px,dy_px,sad,px_per_s")
for ($i=0; $i -le $Pairs; $i++) {
    $cur = Grab
    if ($null -ne $prev) {
        $r = Shift $prev[0] $cur[0] $cur[1] $cur[2]
        $pps = [math]::Sqrt($r[0]*$r[0]+$r[1]*$r[1]) * 4.0 / $GapSeconds   # x4 undoes downscale
        Write-Host ("  pair {0}: shift=({1},{2}) sad={3:N1}  -> {4:N1} px/s" -f $i,$r[0],$r[1],$r[2],$pps)
        $out += ('{0},{1},{2},{3},{4:N1},{5:N1}' -f $Tag,$i,$r[0],$r[1],$r[2],$pps)
    }
    $prev = $cur
    Start-Sleep -Milliseconds ([int]($GapSeconds*1000))
}
$out | Set-Content (Join-Path $OutDir "$Tag.csv")
Write-Host ("wrote {0}" -f (Join-Path $OutDir "$Tag.csv")) -ForegroundColor Green
