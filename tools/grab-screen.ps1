<#
  grab-screen.ps1 - screenshot the primary display to a PNG.

  WHY THIS EXISTS: diagnosing a launch by reading game memory tells you what the
  engine THINKS, not what is on screen. A run that looked like "the mission parser
  never ran" was indistinguishable from "sitting on a loading screen", "playing the
  intro movie" and "showing a modal error box behind a fullscreen window" - three
  very different problems. One screenshot separates them instantly.

      tools\grab-screen.ps1                       # -> screen.png beside this script
      tools\grab-screen.ps1 -Out C:\tmp\shot.png
      tools\grab-screen.ps1 -Delay 8              # wait 8s first
#>
param(
    [string]$Out = "",
    [int]$Delay = 0,
    # Shrink the capture so it is cheap to look at. 0 = full size.
    [int]$MaxWidth = 960
)
$ErrorActionPreference = 'Stop'
if ($Delay -gt 0) { Start-Sleep -Seconds $Delay }
if (-not $Out) { $Out = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) 'screen.png' }

Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms

$b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($b.X, $b.Y, 0, 0, $bmp.Size)
$g.Dispose()

if ($MaxWidth -gt 0 -and $bmp.Width -gt $MaxWidth) {
    $h = [int]($bmp.Height * $MaxWidth / $bmp.Width)
    $small = New-Object System.Drawing.Bitmap $MaxWidth, $h
    $g2 = [System.Drawing.Graphics]::FromImage($small)
    $g2.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $g2.DrawImage($bmp, 0, 0, $MaxWidth, $h)
    $g2.Dispose(); $bmp.Dispose(); $bmp = $small
}
$bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()
Write-Host ("{0}  ({1}x{2}, {3:N0} bytes)" -f $Out, $b.Width, $b.Height, (Get-Item $Out).Length)
