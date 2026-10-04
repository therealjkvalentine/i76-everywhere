<#
  find-weapon-ui.ps1 — find the control that changes a weapon slot, by clicking and looking.

  The Build and Repair form's weapon rows have a small arrow glyph, but clicking where it
  appears did nothing, and I'76 maps the cursor into its own space so the on-screen position is
  not the click position. Rather than keep guessing, sweep candidate points and detect the
  effect: screenshot the WEAPONS block after each click and compare it to the baseline. When
  the slot text changes, that point is the control.

  SAFETY: the sweep is confined to the weapons block. It never goes near DONE / FIELD SALVAGE /
  SAVE BOOKMARK, so a stray click cannot leave the garage or alter the save.

  Run with the Build and Repair form open:
      autotest\enter-mission5.ps1 -SceneY 833 -StopAtGarage
      tools\find-weapon-ui.ps1
#>
param(
    [int]$X1 = 380, [int]$X2 = 560, [int]$XStep = 15,     # OS-cursor sweep box (weapons block)
    [int]$Y1 = 165, [int]$Y2 = 240, [int]$YStep = 8,
    [string]$OutDir = "$PSScriptRoot\..\..\captures\weapui"
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\lib\focuslib.ps1"
. "$PSScriptRoot\..\lib\inputlib.ps1"
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms
New-Item -ItemType Directory -Force $OutDir | Out-Null
Get-ChildItem $OutDir -Filter *.png -EA SilentlyContinue | Remove-Item -Force

# The WEAPONS block on the Build and Repair form, in screen pixels.
$BOX = @{ X = 590; Y = 480; W = 1000; H = 260 }
function Grab([string]$path) {
    $b = New-Object Drawing.Bitmap $BOX.W, $BOX.H
    $g = [Drawing.Graphics]::FromImage($b)
    try { $g.CopyFromScreen($BOX.X, $BOX.Y, 0, 0, (New-Object Drawing.Size($BOX.W, $BOX.H)))
          $b.Save($path, [Drawing.Imaging.ImageFormat]::Png) }
    finally { $g.Dispose(); $b.Dispose() }
}
function DiffPct([string]$a, [string]$b) {
    $ia = [Drawing.Bitmap]::FromFile($a); $ib = [Drawing.Bitmap]::FromFile($b)
    try {
        $changed = 0; $total = 0
        for ($y = 0; $y -lt $ia.Height; $y += 3) {
            for ($x = 0; $x -lt $ia.Width; $x += 3) {
                $total++
                if ($ia.GetPixel($x,$y).ToArgb() -ne $ib.GetPixel($x,$y).ToArgb()) { $changed++ }
            }
        }
        if ($total) { 100.0 * $changed / $total } else { 0 }
    } finally { $ia.Dispose(); $ib.Dispose() }
}

$proc = Get-GamePid; if (-not $proc) { throw "game not running" }
Force-Foreground $proc.MainWindowHandle | Out-Null
Start-Sleep -Milliseconds 500
$base = Join-Path $OutDir 'base.png'
Grab $base
Write-Host ("sweeping X {0}..{1} step {2}, Y {3}..{4} step {5}" -f $X1,$X2,$XStep,$Y1,$Y2,$YStep) -ForegroundColor Cyan

$hits = @()
$i = 0
for ($y = $Y1; $y -le $Y2; $y += $YStep) {
    for ($x = $X1; $x -le $X2; $x += $XStep) {
        $i++
        [Inp]::SetCursorPos($x, $y) | Out-Null
        Start-Sleep -Milliseconds 90
        [Inp]::mouse_event(0x2,0,0,0,[IntPtr]::Zero); Start-Sleep -Milliseconds 50
        [Inp]::mouse_event(0x4,0,0,0,[IntPtr]::Zero); Start-Sleep -Milliseconds 220
        $shot = Join-Path $OutDir ("p{0:D4}.png" -f $i)
        Grab $shot
        $d = DiffPct $base $shot
        if ($d -gt 1.0) {
            Write-Host ("  CHANGE {0:N1}% at OS ({1},{2})" -f $d, $x, $y) -ForegroundColor Green
            $hits += [pscustomobject]@{ X = $x; Y = $y; Diff = $d; Shot = $shot }
            Copy-Item $shot $base -Force      # new baseline: the UI has a new state
        } else {
            Remove-Item $shot -Force -EA SilentlyContinue
        }
    }
}
Write-Host ("`n{0} clicks, {1} produced a change in the weapons block" -f $i, $hits.Count) -ForegroundColor Cyan
$hits | ForEach-Object { "  ({0},{1})  {2:N1}%  {3}" -f $_.X, $_.Y, $_.Diff, (Split-Path $_.Shot -Leaf) }
