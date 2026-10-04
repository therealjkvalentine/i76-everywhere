<#
  capture-cursor-probes.ps1 — put the OS cursor at known points and photograph each one.

  Half of the cursor-mapping job. PowerShell captures the frames (fast); map-cursor.py does the
  pixel work (PowerShell GetPixel over a 3440x1440 frame is ~1.2M calls per probe and never
  finishes). Writes ref.png + pNNN.png plus probes.csv listing the OS coordinate of each frame.

  Run with any I'76 menu/form on screen.
#>
param(
    [int[]]$PX = @(120, 260, 400, 540),
    [int[]]$PY = @(120, 220, 320, 420),
    [int]$RefX = 640, [int]$RefY = 460,
    [string]$OutDir = "$PSScriptRoot\..\..\captures\calib"
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\lib\focuslib.ps1"
. "$PSScriptRoot\..\lib\inputlib.ps1"
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms
New-Item -ItemType Directory -Force $OutDir | Out-Null
Get-ChildItem $OutDir -Filter *.png -EA SilentlyContinue | Remove-Item -Force

$vs = [Windows.Forms.SystemInformation]::VirtualScreen
function Shot([string]$path) {
    $b = New-Object Drawing.Bitmap $vs.Width, $vs.Height
    $g = [Drawing.Graphics]::FromImage($b)
    try { $g.CopyFromScreen(0,0,0,0,$b.Size); $b.Save($path, [Drawing.Imaging.ImageFormat]::Png) }
    finally { $g.Dispose(); $b.Dispose() }
}

$proc = Get-GamePid; if (-not $proc) { throw "game not running" }
Force-Foreground $proc.MainWindowHandle | Out-Null; Start-Sleep -Milliseconds 700

[Inp]::SetCursorPos($RefX, $RefY) | Out-Null; Start-Sleep -Milliseconds 500
Shot (Join-Path $OutDir 'ref.png')

# loop variables must not differ from the parameter names by case alone - PowerShell is
# case-insensitive, so `foreach ($px in $PX)` would destroy $PX on the first iteration.
$rows = @('idx,osx,osy')
$i = 0
foreach ($rowY in $PY) {
    foreach ($colX in $PX) {
        [Inp]::SetCursorPos([int]$colX, [int]$rowY) | Out-Null
        Start-Sleep -Milliseconds 400
        Shot (Join-Path $OutDir ("p{0:D3}.png" -f $i))
        $rows += ("{0},{1},{2}" -f $i, $colX, $rowY)
        $i++
    }
}
$rows | Set-Content (Join-Path $OutDir 'probes.csv')
Write-Host ("captured ref + {0} probes -> {1}" -f $i, (Resolve-Path $OutDir)) -ForegroundColor Green
Write-Host ("reference cursor parked at OS ({0},{1})" -f $RefX, $RefY)
