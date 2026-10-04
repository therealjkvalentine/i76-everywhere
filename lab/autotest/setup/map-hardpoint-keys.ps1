<#
  map-hardpoint-keys.ps1 — which number key fires which hardpoint?

  The .vcf gives each WEPN chunk a hardpoint index (0..3). The number keys fire hardpoints
  directly. Rather than assume key N == hardpoint N, press each key and watch which ammo
  counter on the HUD drops - the same "verify the stimulus" discipline that caught fire being
  Enter rather than Space.

  Captures the ammo strip after each key so the mapping is read off the images.
#>
param([int]$Taps = 6)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\lib\focuslib.ps1"
. "$PSScriptRoot\..\lib\inputlib.ps1"
. "$PSScriptRoot\..\lib\maplib.ps1"
Add-Type -AssemblyName System.Drawing
$out = "$PSScriptRoot\..\..\captures\hardpoints"
New-Item -ItemType Directory -Force $out | Out-Null
Get-ChildItem $out -Filter '*.png' | Remove-Item -Force

$gp = Get-GamePid
Force-Foreground $gp.MainWindowHandle | Out-Null
Start-Sleep -Milliseconds 700
$r = Get-UIRect
# the four ammo rows live top-left of the HUD
function Ammo([string]$tag) {
    $b = New-Object Drawing.Bitmap 560,150
    $g = [Drawing.Graphics]::FromImage($b)
    $g.CopyFromScreen($r.X + (195*3), $r.Y + (2*3), 0, 0, (New-Object Drawing.Size(560,150)))
    $b.Save((Join-Path $out "$tag.png"), [Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose(); $b.Dispose()
}
Ammo '0_start'
# VK for '1'..'5' are 0x31..0x35
foreach ($n in 1..5) {
    $vk = 0x30 + $n
    for ($i = 0; $i -lt $Taps; $i++) { Send-Key $vk 60; Start-Sleep -Milliseconds 220 }
    Start-Sleep -Milliseconds 600
    Ammo ("key$n")
    Write-Host "  pressed '$n' x$Taps"
}
Write-Host "captures -> $(Resolve-Path $out)" -ForegroundColor Green
Write-Host "compare 0_start.png against key1..key5.png; whichever counter dropped is that key's hardpoint" -ForegroundColor Yellow
