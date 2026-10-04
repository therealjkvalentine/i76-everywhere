<#
  find-control.ps1 — locate ANY I'76 UI control by clicking and watching for its effect.

  The reliable way to find a control in this game. Fitting a global OS-cursor -> screen mapping
  keeps disappointing (the drawn cursor is hard to isolate automatically, and a single affine
  fit drifts across the form), but "click here, did the thing I care about change?" always
  works and needs no mapping at all.

  You give it a sweep box in OS-cursor coordinates and a WATCH region in screen pixels; it
  clicks each grid point and reports the ones that changed the watch region.

  SAFETY: keep the sweep box away from destructive buttons (DONE / ENTER AREA / EXIT). The
  watch region should be just the readout you expect to change.

  Example - find the "A.I. DRIVERS" decrement button by watching the digits:
    tools\find-control.ps1 -X1 100 -X2 220 -Y1 250 -Y2 300 `
                           -WatchX 1150 -WatchY 855 -WatchW 200 -WatchH 60
#>
param(
    [int]$X1 = 100, [int]$X2 = 240, [int]$XStep = 10,
    [int]$Y1 = 250, [int]$Y2 = 310, [int]$YStep = 6,
    [int]$WatchX = 1150, [int]$WatchY = 855, [int]$WatchW = 220, [int]$WatchH = 60,
    [double]$Threshold = 1.0,
    [string]$OutDir = "$PSScriptRoot\..\..\captures\ctlsweep"
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\lib\focuslib.ps1"
. "$PSScriptRoot\..\lib\inputlib.ps1"
Add-Type -AssemblyName System.Drawing
New-Item -ItemType Directory -Force $OutDir | Out-Null
Get-ChildItem $OutDir -Filter *.png -EA SilentlyContinue | Remove-Item -Force

function Grab([string]$p) {
    $b = New-Object Drawing.Bitmap $WatchW, $WatchH
    $g = [Drawing.Graphics]::FromImage($b)
    try { $g.CopyFromScreen($WatchX, $WatchY, 0, 0, (New-Object Drawing.Size($WatchW, $WatchH)))
          $b.Save($p, [Drawing.Imaging.ImageFormat]::Png) } finally { $g.Dispose(); $b.Dispose() }
}
function DiffPct([string]$a, [string]$b) {
    $ia = [Drawing.Bitmap]::FromFile($a); $ib = [Drawing.Bitmap]::FromFile($b)
    try {
        $ch = 0; $tot = 0
        for ($y = 0; $y -lt $ia.Height; $y += 2) {
            for ($x = 0; $x -lt $ia.Width; $x += 2) {
                $tot++
                if ($ia.GetPixel($x,$y).ToArgb() -ne $ib.GetPixel($x,$y).ToArgb()) { $ch++ }
            }
        }
        if ($tot) { 100.0 * $ch / $tot } else { 0 }
    } finally { $ia.Dispose(); $ib.Dispose() }
}

$proc = Get-GamePid; if (-not $proc) { throw "game not running" }
Force-Foreground $proc.MainWindowHandle | Out-Null; Start-Sleep -Milliseconds 500
$base = Join-Path $OutDir 'base.png'
Grab $base
Write-Host ("sweep OS x {0}..{1}/{2}, y {3}..{4}/{5}; watching screen ({6},{7}) {8}x{9}" -f `
    $X1,$X2,$XStep,$Y1,$Y2,$YStep,$WatchX,$WatchY,$WatchW,$WatchH) -ForegroundColor Cyan

$hits = @(); $i = 0
for ($cy = $Y1; $cy -le $Y2; $cy += $YStep) {
    for ($cx = $X1; $cx -le $X2; $cx += $XStep) {
        $i++
        [Inp]::SetCursorPos($cx, $cy) | Out-Null
        Start-Sleep -Milliseconds 80
        [Inp]::mouse_event(0x2,0,0,0,[IntPtr]::Zero); Start-Sleep -Milliseconds 45
        [Inp]::mouse_event(0x4,0,0,0,[IntPtr]::Zero); Start-Sleep -Milliseconds 200
        $shot = Join-Path $OutDir ("s{0:D4}.png" -f $i)
        Grab $shot
        $d = DiffPct $base $shot
        if ($d -gt $Threshold) {
            Write-Host ("  CHANGE {0,5:N1}% at OS ({1},{2})" -f $d, $cx, $cy) -ForegroundColor Green
            $hits += [pscustomobject]@{ X=$cx; Y=$cy; Diff=$d }
            Copy-Item $shot $base -Force        # accept the new state as the baseline
        } else { Remove-Item $shot -Force -EA SilentlyContinue }
    }
}
Write-Host ("`n{0} clicks, {1} changed the watch region" -f $i, $hits.Count) -ForegroundColor Cyan
$hits | ForEach-Object { "  OS({0},{1})  {2:N1}%" -f $_.X, $_.Y, $_.Diff }
