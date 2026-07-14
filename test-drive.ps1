# Interstate '76 - hands-free test drive (Windows): boot -> Instant Melee -> chase cam
# -> screenshot. The fastest repeatable way to see texture/config changes in the real
# renderer (~90s). There is NO command-line mission launch in i76.exe (verified: the
# "Mission file %s" strings are fed internally by i76shell; even BUILDER.DOC routes
# custom missions through the menu) - so this drives the menu, which hit-tests mouse
# clicks at INTERNAL 640x480 coords = raw screen pixels (window sits at 0,0).
#
# To choose the car under test: overwrite ADDON\valepre4.vcf (GOG's own ADDON override,
# = the melee form's default "GTA2" variant) with any VCF from the archive - e.g.
# vppirna1.vcf = Jade's Piranha. Back up the original first (texture-lab keeps a copy).
#
# Usage: powershell -ExecutionPolicy Bypass -File test-drive.ps1
#          [-GameDir "C:\Games\Interstate 76"] [-Shot out.png]

param(
    [string]$GameDir = "C:\Games\Interstate 76",
    [string]$Shot = "$env:USERPROFILE\Desktop\i76-testdrive.png"
)
$ErrorActionPreference = 'Stop'

Get-Process i76 -ErrorAction SilentlyContinue | Stop-Process -Force -Confirm:$false
Start-Sleep 2
Start-Process -FilePath (Join-Path $GameDir 'i76.exe') -ArgumentList '-glide' -WorkingDirectory $GameDir
Start-Sleep 42   # PLEASE STAND BY + intro spin-up

Add-Type @"
using System;
using System.Runtime.InteropServices;
public class I76Drive {
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint dx, uint dy, uint d, UIntPtr i);
}
"@
Add-Type -AssemblyName System.Drawing
$ws = New-Object -ComObject WScript.Shell
$p = Get-Process i76

function FG { [I76Drive]::SetForegroundWindow($p.MainWindowHandle) | Out-Null; Start-Sleep -Milliseconds 600 }
function Click($x, $y) {
    FG
    [I76Drive]::SetCursorPos($x, $y) | Out-Null; Start-Sleep -Milliseconds 700
    [I76Drive]::mouse_event(2,0,0,0,[UIntPtr]::Zero); Start-Sleep -Milliseconds 130
    [I76Drive]::mouse_event(4,0,0,0,[UIntPtr]::Zero); Start-Sleep -Milliseconds 1200
}

FG; $ws.SendKeys('{ESC}'); Start-Sleep 9      # skip intro (sometimes needs two)
FG; $ws.SendKeys('{ESC}'); Start-Sleep 6
Click 446 310    # MELEE
Click 489 350    # AUTO MELEE
Click 529 378    # INSTANT MELEE
Start-Sleep 2
Click 299 461    # ENTER AREA
Start-Sleep 25   # level load
FG; $ws.SendKeys('{F2}'); Start-Sleep 3       # chase cam

$bmp = New-Object System.Drawing.Bitmap 3440, 1440
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen(0, 0, 0, 0, $bmp.Size)
$bmp.Save($Shot, [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose(); $bmp.Dispose()
Write-Host "Screenshot: $Shot  (game left running in-mission)"
