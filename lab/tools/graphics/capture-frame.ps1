<#
  capture-frame.ps1 - full-frame screenshot of the running game's presented Glide frame, at screen resolution
  (no rescale: one PNG pixel is one panel pixel, which is what the variants are compared at).

    .\capture-frame.ps1 -Out ..\..\captures\graphics\2x.png

  The rectangle comes from autotest\lib\maplib.ps1 (the game window's real client rect, the conf's 16:10 frame
  aspect-fitted into it): 2304x1440 at x 568 on the 3440x1440 panel. It prints the rectangle it used; if that is
  not 2304x1440, the variant changed the presented geometry and its crops are not comparable.
  Call it from proxy-run.ps1 -Run { ... } while the mission is up and the game window is in the foreground.
#>
param([Parameter(Mandatory)] [string]$Out)
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "..\..\autotest\lib\maplib.ps1")
$m = Init-CursorMap
$r = Get-FrameRect
Add-Type -AssemblyName System.Drawing
$dir = Split-Path -Parent $Out
if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Force $dir | Out-Null }
$b = New-Object Drawing.Bitmap $r.W, $r.H
$g = [Drawing.Graphics]::FromImage($b)
$g.CopyFromScreen($r.X, $r.Y, 0, 0, (New-Object Drawing.Size($r.W, $r.H)))
$b.Save($Out, [Drawing.Imaging.ImageFormat]::Png)
$g.Dispose(); $b.Dispose()
"[capture-frame] {0}: {1}x{2} at ({3},{4}), conf render {5}, scaling {6}" -f $Out, $r.W, $r.H, $r.X, $r.Y, $m.Render, $m.ScalingMode
