<#
  test-armor-float.ps1 — write float armor across a range and watch the HUD damage panel.

  Iterative narrowing (armor-narrow.py) left a tight cluster of FLOATS around 0.05-0.09 on a
  heavily damaged car - i.e. armor looks normalised 0..1, which is why every search for the
  configured integer (711 etc.) came up empty.

  Repairing is a far better test than damaging: the car is already visibly wrecked, so writing
  1.0 should turn the panel green all over. That is a huge, unambiguous change - unlike the
  0.12%-of-pixels noise that produced an earlier false positive.

  Dumps the range as floats first so the structure is visible, then writes, captures, restores.
#>
param(
    [Parameter(Mandatory=$true)][int64]$From,
    [Parameter(Mandatory=$true)][int64]$To,
    [float]$Value = 1.0,
    [string]$Tag = 'f'
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\..\..\autotest\lib\focuslib.ps1"
. "$PSScriptRoot\..\..\..\autotest\lib\maplib.ps1"
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System; using System.Runtime.InteropServices;
public class AF {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(int a,bool b,int c);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h,IntPtr a,byte[] b,int s,out int r);
  [DllImport("kernel32.dll")] public static extern bool WriteProcessMemory(IntPtr h,IntPtr a,byte[] b,int s,out int r);
}
"@
$gp = Get-GamePid
Force-Foreground $gp.MainWindowHandle | Out-Null; Start-Sleep -Milliseconds 700
$H = [AF]::OpenProcess(0x438, $false, $gp.Id)
function PeekF([int64]$a){ $b=New-Object byte[] 4; $n=0
    [void][AF]::ReadProcessMemory($H,[IntPtr]$a,$b,4,[ref]$n); [BitConverter]::ToSingle($b,0) }
function PokeF([int64]$a,[float]$v){ $b=[BitConverter]::GetBytes($v); $n=0
    [void][AF]::WriteProcessMemory($H,[IntPtr]$a,$b,4,[ref]$n) }

$r = Get-UIRect
function Panel([string]$p){
    $b = New-Object Drawing.Bitmap 620,360
    $g = [Drawing.Graphics]::FromImage($b)
    $g.CopyFromScreen($r.X + (395*3), $r.Y + (2*3), 0, 0, (New-Object Drawing.Size(620,360)))
    $b.Save($p,[Drawing.Imaging.ImageFormat]::Png); $g.Dispose(); $b.Dispose() }

Write-Host "range 0x$('{0:X}' -f $From) .. 0x$('{0:X}' -f $To) as floats:" -ForegroundColor Cyan
$orig = @{}
for ($a = $From; $a -le $To; $a += 4) {
    $v = PeekF $a; $orig[$a] = $v
    if ([math]::Abs($v) -gt 1e-9 -and [math]::Abs($v) -lt 1e9) {
        "  0x{0:X8}  {1:N4}" -f $a, $v }
}
$cap = "$PSScriptRoot\..\captures"
Panel "$cap\armorf_${Tag}_before.png"
for ($a = $From; $a -le $To; $a += 4) { PokeF $a $Value }
Start-Sleep -Milliseconds 1500
Panel "$cap\armorf_${Tag}_after.png"
$now = @(); for ($a = $From; $a -le $To; $a += 4) { $now += (PeekF $a) }
Write-Host ("after write, first few: {0}" -f (($now | Select-Object -First 6) -join ', ')) -ForegroundColor Cyan
# leave the repair in place briefly, then restore so later runs are clean
foreach ($a in $orig.Keys) { PokeF $a $orig[$a] }
Write-Host "restored" -ForegroundColor Green
