<#
  test-armor-candidate.ps1 — decide whether an address cluster is the PLAYER's armor.

  Same discipline that settled ammo: do not conclude from "the number looks right" or even from
  "the number moved". WRITE a damaged value and check the thing the game DISPLAYS - here the
  HUD damage panel (the car outline top-right). If the panel does not react, it is some other
  vehicle's armor, or not armor at all.

  Writes a low-but-nonzero value so the car shows damage without being destroyed, captures the
  panel, then restores the original values.

  Usage:  test-armor-candidate.ps1 -Addr 0x030F7234 -Stride 0x58 -Count 4 [-Value 20]
#>
param(
    [Parameter(Mandatory=$true)][int64]$Addr,
    [int]$Stride = 0x58,
    [int]$Count  = 4,
    [int]$Value  = 20,
    [string]$Tag = 'cand'
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\..\..\autotest\lib\focuslib.ps1"
. "$PSScriptRoot\..\..\..\autotest\lib\maplib.ps1"
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System; using System.Runtime.InteropServices;
public class ARM {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(int a,bool b,int c);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h,IntPtr a,byte[] b,int s,out int r);
  [DllImport("kernel32.dll")] public static extern bool WriteProcessMemory(IntPtr h,IntPtr a,byte[] b,int s,out int r);
}
"@
$gp = Get-GamePid
Force-Foreground $gp.MainWindowHandle | Out-Null; Start-Sleep -Milliseconds 700
$H = [ARM]::OpenProcess(0x438, $false, $gp.Id)
function Peek([int64]$a){ $b=New-Object byte[] 4; $n=0
    [void][ARM]::ReadProcessMemory($H,[IntPtr]$a,$b,4,[ref]$n); [BitConverter]::ToInt32($b,0) }
function Poke([int64]$a,[int]$v){ $b=[BitConverter]::GetBytes($v); $n=0
    [void][ARM]::WriteProcessMemory($H,[IntPtr]$a,$b,4,[ref]$n) }

$r = Get-UIRect
# HUD damage panel: the car outline + component boxes, top-right of the 640x480 UI
function Panel([string]$p){
    $b = New-Object Drawing.Bitmap 620,360
    $g = [Drawing.Graphics]::FromImage($b)
    $g.CopyFromScreen($r.X + (395*3), $r.Y + (2*3), 0, 0, (New-Object Drawing.Size(620,360)))
    $b.Save($p,[Drawing.Imaging.ImageFormat]::Png); $g.Dispose(); $b.Dispose() }

$orig = @()
for ($i = 0; $i -lt $Count; $i++) { $orig += (Peek ($Addr + $i*$Stride)) }
Write-Host ("original: {0}" -f ($orig -join ', ')) -ForegroundColor Cyan

Panel "$PSScriptRoot\..\captures\armor_${Tag}_before.png"
for ($i = 0; $i -lt $Count; $i++) { Poke ($Addr + $i*$Stride) $Value }
Start-Sleep -Milliseconds 1500
$now = @(); for ($i = 0; $i -lt $Count; $i++) { $now += (Peek ($Addr + $i*$Stride)) }
Write-Host ("after write: {0}" -f ($now -join ', ')) -ForegroundColor Cyan
Panel "$PSScriptRoot\..\captures\armor_${Tag}_after.png"

# put it back so the run does not corrupt later tests
for ($i = 0; $i -lt $Count; $i++) { Poke ($Addr + $i*$Stride) $orig[$i] }
Write-Host "restored" -ForegroundColor Green
Write-Host "compare captures/armor_${Tag}_before.png vs _after.png" -ForegroundColor Yellow
