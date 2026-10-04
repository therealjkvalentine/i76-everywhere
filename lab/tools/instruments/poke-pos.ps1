<#
  poke-pos.ps1 — does the renderer actually READ the position table at 0x54E11C?

  The 60 Hz design assumes the table found by the heap scan is what the renderer draws
  from (not a collision/culling list). This proves it: offset an entity's position and
  see whether the picture moves.

  WRITES to game memory - but only 12 bytes of float DATA (a position triple), never code,
  never disk, and it restores the original values on exit (including on Ctrl-C/failure).
  Intended for the SANDBOX copy: -RequirePath defaults to the lab's game folder so it
  refuses to touch any other instance.

  Two modes, because I'76 rewrites this table every sim tick:
    -Hold <sec>   write continuously (default) - beats the sim's rewrite, works while playing
    -Frozen       single write, for when the sim is frozen (game window unfocused). The
                  renderer keeps drawing while the sim is stopped, so the value survives -
                  the cleanest possible test of "does the renderer read this".

  Usage (sandbox, in a mission):
    powershell -ExecutionPolicy Bypass -File tools\poke-pos.ps1 -Index 0 -DX 0 -DY 40 -Hold 4
    powershell -ExecutionPolicy Bypass -File tools\poke-pos.ps1 -Frozen -Shot
#>
param(
    [int]$Index = 0,               # 0 = player, 1..6 = AI cars
    [double]$DX = 0,
    [double]$DY = 40,              # default: lift 40 m straight up - unmistakable on screen
    [double]$DZ = 0,
    [double]$Hold = 4,             # seconds to hold the offset (continuous write)
    [switch]$Frozen,               # single write instead (use when sim is frozen)
    [switch]$Shot,                 # capture before/after screenshots
    [string]$RequirePath = 'i76-uncap-lab',
    [string]$ShotDir = "$PSScriptRoot\..\..\captures\shots"
)
$ErrorActionPreference = 'Stop'
$POS_TABLE = 0x54E11C
$STRIDE    = 0x20

Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Poke {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(uint a, bool i, int p);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr a, byte[] b, int s, out int r);
  [DllImport("kernel32.dll")] public static extern bool WriteProcessMemory(IntPtr h, IntPtr a, byte[] b, int s, out int w);
  [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
}
"@
Add-Type -AssemblyName System.Drawing

$proc = Get-Process i76, nitro -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -and $_.Path -like "*$RequirePath*" } | Select-Object -First 1
if (-not $proc) {
    $any = Get-Process i76, nitro -ErrorAction SilentlyContinue
    if ($any) { throw ("Found I'76 but not under '$RequirePath' (path: {0}). Refusing to write to a non-sandbox instance." -f $any[0].Path) }
    throw "The sandbox Interstate '76 is not running."
}
# 0x10 VM_READ | 0x20 VM_WRITE | 0x08 VM_OPERATION
$h = [Poke]::OpenProcess(0x38, $false, $proc.Id)
if ($h -eq [IntPtr]::Zero) { throw "OpenProcess failed." }
Write-Host ("target: pid {0}  {1}" -f $proc.Id, $proc.Path) -ForegroundColor Cyan

function RdF([int64]$a) { $b = New-Object byte[] 4; $n = 0
    if ([Poke]::ReadProcessMemory($h, [IntPtr]$a, $b, 4, [ref]$n)) { [BitConverter]::ToSingle($b,0) } else { [double]::NaN } }
function WrF([int64]$a, [single]$v) { $b = [BitConverter]::GetBytes($v); $n = 0
    [void][Poke]::WriteProcessMemory($h, [IntPtr]$a, $b, 4, [ref]$n) }
function Shot([string]$tag) {
    if (-not $Shot) { return }
    New-Item -ItemType Directory -Force $ShotDir | Out-Null
    $bmp = New-Object Drawing.Bitmap ([Windows.Forms.SystemInformation]::VirtualScreen.Width), ([Windows.Forms.SystemInformation]::VirtualScreen.Height)
    $g = [Drawing.Graphics]::FromImage($bmp)
    try {
        $g.CopyFromScreen(0, 0, 0, 0, $bmp.Size)
        $p = Join-Path $ShotDir ("{0}.png" -f $tag)
        $bmp.Save($p, [Drawing.Imaging.ImageFormat]::Png)
        Write-Host ("  screenshot -> {0}" -f $p)
    } catch { Write-Host ("  screenshot failed: {0}" -f $_.Exception.Message) -ForegroundColor Yellow }
    finally { $g.Dispose(); $bmp.Dispose() }
}
Add-Type -AssemblyName System.Windows.Forms

$base = $POS_TABLE + $Index * $STRIDE
$ox = RdF $base; $oy = RdF ($base + 4); $oz = RdF ($base + 8); $rad = RdF ($base + 0xC)
if ([double]::IsNaN($ox)) { throw "Could not read the position table." }
if ($ox -eq 0 -and $oz -eq 0) { throw ("Slot {0} is empty (all zero) - load a mission, or pick another -Index." -f $Index) }
Write-Host ("idx {0}: pos=({1:N2}, {2:N2}, {3:N2}) radius={4:N3}" -f $Index, $ox, $oy, $oz, $rad) -ForegroundColor Green
Write-Host ("offset = ({0:N1}, {1:N1}, {2:N1})  mode = {3}" -f $DX, $DY, $DZ, $(if ($Frozen) { 'single write (frozen sim)' } else { "hold $Hold s" }))

Shot 'before'
$restored = $false
function Restore {
    if ($script:restored) { return }
    WrF $base ([single]$ox); WrF ($base + 4) ([single]$oy); WrF ($base + 8) ([single]$oz)
    $script:restored = $true
    Write-Host "restored original position." -ForegroundColor Green
}
try {
    if ($Frozen) {
        WrF $base ([single]($ox + $DX)); WrF ($base + 4) ([single]($oy + $DY)); WrF ($base + 8) ([single]($oz + $DZ))
        Start-Sleep -Milliseconds 900
        Shot 'after'
        Write-Host ("read back: ({0:N2}, {1:N2}, {2:N2})" -f (RdF $base), (RdF ($base+4)), (RdF ($base+8)))
    } else {
        $sw = [Diagnostics.Stopwatch]::StartNew(); $shotTaken = $false
        while ($sw.Elapsed.TotalSeconds -lt $Hold) {
            $cx = RdF $base; $cy = RdF ($base + 4); $cz = RdF ($base + 8)
            WrF $base ([single]($cx + $DX)); WrF ($base + 4) ([single]($cy + $DY)); WrF ($base + 8) ([single]($cz + $DZ))
            if (-not $shotTaken -and $sw.Elapsed.TotalSeconds -gt ($Hold / 2)) { Shot 'after'; $shotTaken = $true }
            Start-Sleep -Milliseconds 16
        }
    }
} finally {
    Restore
    [Poke]::CloseHandle($h) | Out-Null
}
Write-Host ""
Write-Host "WHAT TO LOOK FOR: with -DY 40 the car (or the whole view, if idx 0 drives the camera)" -ForegroundColor Yellow
Write-Host "should jump into the air and drop back. If NOTHING moved on screen, this table is not" -ForegroundColor Yellow
Write-Host "what the renderer reads - the scene copies at 0x02FF7D70/0x03030818 are the next target." -ForegroundColor Yellow
