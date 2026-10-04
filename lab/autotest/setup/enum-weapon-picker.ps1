<#
  enum-weapon-picker.ps1 — page through the CHASSIS CONFIGURATION weapon picker and capture
  every page, so the full ordered weapon list can be read off the images.

  Assumes you are already on the CHASSIS CONFIGURATION FORM (Driver Entry -> CONFIGURE CHASSIS).
  Coordinates are UI units, read directly off a Capture-UI screenshot - see docs/CONFIG-OPTIONS.md.
#>
param([int]$Pages = 6, [string]$OutDir = "$PSScriptRoot\..\..\captures\weaponlist")
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\lib\focuslib.ps1"
. "$PSScriptRoot\..\lib\inputlib.ps1"
. "$PSScriptRoot\..\lib\maplib.ps1"
New-Item -ItemType Directory -Force $OutDir | Out-Null
Get-ChildItem $OutDir -Filter '*.png' | Remove-Item -Force   # never reuse a stale capture

$proc = Get-GamePid
Force-Foreground $proc.MainWindowHandle | Out-Null; Start-Sleep -Milliseconds 400

# picker controls, in UI units
$SLOT1_ARROW = @(258, 174)   # the > on weapon slot "#1 Top" - opens the picker
$SCROLL_DOWN = @(261, 349)
$PARK        = @(20, 470)

Click-UI $SLOT1_ARROW[0] $SLOT1_ARROW[1] 450
Start-Sleep -Milliseconds 1200
for ($i = 0; $i -lt $Pages; $i++) {
    [Inp]::SetCursorPos($PARK[0], $PARK[1]) | Out-Null
    Start-Sleep -Milliseconds 450
    Capture-UI (Join-Path $OutDir ("page{0:D2}.png" -f $i)) | Out-Null
    Write-Host "  captured page $i"
    # one click of the down arrow per row; do a few to advance a screenful
    for ($k = 0; $k -lt 8; $k++) { Click-UI $SCROLL_DOWN[0] $SCROLL_DOWN[1] 120; Start-Sleep -Milliseconds 90 }
    Start-Sleep -Milliseconds 400
}
Write-Host "pages -> $(Resolve-Path $OutDir)" -ForegroundColor Green
Write-Host "picker is still OPEN - click CANCEL at UI(359,357) when done." -ForegroundColor Yellow
