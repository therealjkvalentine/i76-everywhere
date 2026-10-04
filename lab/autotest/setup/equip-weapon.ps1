<#
  equip-weapon.ps1 — cycle a weapon slot on the Build and Repair form.

  The slot "cycle" control is the arrow glyph at the right of each weapon row. Its OS-cursor
  column is x ~= 260 (the on-screen glyph is at a different place: I'76 maps the cursor into
  its own space - see lib/maplib.ps1). Row positions, in OS cursor coords:

      #1 Top      y = 145
      #2 Top      y = 164
      #1 Rear     y = 182
      #1 Dropper  y = 200

  Each click advances that slot to the next weapon available in the car/van inventory, so to
  equip a specific weapon you cycle and look. This captures the row after every click so the
  sequence can be read back and the right number of clicks chosen.

    tools\equip-weapon.ps1 -Slot 1Top -Clicks 12
#>
param(
    [ValidateSet('1Top','2Top','1Rear','1Dropper')][string]$Slot = '1Top',
    [int]$Clicks = 12,
    [string]$OutDir = "$PSScriptRoot\..\..\captures\equip"
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\lib\focuslib.ps1"
. "$PSScriptRoot\..\lib\inputlib.ps1"
Add-Type -AssemblyName System.Drawing
New-Item -ItemType Directory -Force $OutDir | Out-Null
Get-ChildItem $OutDir -Filter *.png -EA SilentlyContinue | Remove-Item -Force

$rowY = @{ '1Top' = 145; '2Top' = 164; '1Rear' = 182; '1Dropper' = 200 }
$ARROW_X = 260
$y = $rowY[$Slot]

# strip covering just the four weapon rows, in screen pixels
$BX = 590; $BY = 495; $BW = 1000; $BH = 210
function Grab([string]$p) {
    $b = New-Object Drawing.Bitmap $BW, $BH
    $g = [Drawing.Graphics]::FromImage($b)
    try { $g.CopyFromScreen($BX, $BY, 0, 0, (New-Object Drawing.Size($BW, $BH)))
          $b.Save($p, [Drawing.Imaging.ImageFormat]::Png) } finally { $g.Dispose(); $b.Dispose() }
}

$proc = Get-GamePid; if (-not $proc) { throw "game not running" }
Force-Foreground $proc.MainWindowHandle | Out-Null
Start-Sleep -Milliseconds 400
Grab (Join-Path $OutDir 'step00.png')
Write-Host ("cycling slot {0} (OS {1},{2}) x{3}" -f $Slot, $ARROW_X, $y, $Clicks) -ForegroundColor Cyan
for ($i = 1; $i -le $Clicks; $i++) {
    [Inp]::SetCursorPos($ARROW_X, $y) | Out-Null
    Start-Sleep -Milliseconds 90
    [Inp]::mouse_event(0x2,0,0,0,[IntPtr]::Zero); Start-Sleep -Milliseconds 50
    [Inp]::mouse_event(0x4,0,0,0,[IntPtr]::Zero); Start-Sleep -Milliseconds 260
    Grab (Join-Path $OutDir ("step{0:D2}.png" -f $i))
}
Write-Host ("captured {0} states -> {1}" -f ($Clicks + 1), (Resolve-Path $OutDir)) -ForegroundColor Green
