<#
  find-render-transform.ps1 — locate the transform the RENDERER actually reads.

  The static table 0x54E11C is a cached copy: writes land, persist, and change nothing on
  screen. The renderer draws from per-entity scene nodes on the heap. Those nodes hold the
  SAME position value, so we can find them with a VALUE SEARCH (no driving needed - the car
  can sit parked), then identify the render-consumed one empirically:

      for each copy:  screenshot -> write +DY -> screenshot -> restore

  Whichever poke changes the picture is the address the 60 Hz interpolation must write.
  Image comparison is done afterwards by compare-shots.py (crops out the HUD/radar, which
  animate on their own).

  Writes 4 bytes of float DATA per candidate and restores it immediately; sandbox-only via
  the path guard. Never touches code or disk state of the game.

  Usage (sandbox, in a mission, car parked, game window visible):
    powershell -ExecutionPolicy Bypass -File tools\find-render-transform.ps1
#>
param(
    [double]$DY = 60,
    [int]$MaxCandidates = 40,
    [double]$Tol = 0.75,
    [string]$OutDir = "$PSScriptRoot\..\..\captures\rt",
    [string]$RequirePath = 'i76-uncap-lab',
    [int]$MaxRegionMB = 8,
    [int]$BudgetMB = 200
)
$ErrorActionPreference = 'Stop'
$POS_TABLE = 0x54E11C

Add-Type @"
using System;
using System.Runtime.InteropServices;
[StructLayout(LayoutKind.Sequential)]
public struct MBI3 { public IntPtr BaseAddress; public IntPtr AllocationBase; public uint AllocationProtect;
  public IntPtr RegionSize; public uint State; public uint Protect; public uint Type; }
public class FRT {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(uint a, bool i, int p);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr a, byte[] b, int s, out int r);
  [DllImport("kernel32.dll")] public static extern bool WriteProcessMemory(IntPtr h, IntPtr a, byte[] b, int s, out int w);
  [DllImport("kernel32.dll")] public static extern int VirtualQueryEx(IntPtr h, IntPtr a, out MBI3 m, int len);
  [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
}
"@
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms

$proc = Get-Process i76, nitro -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -and $_.Path -like "*$RequirePath*" } | Select-Object -First 1
if (-not $proc) { throw "Sandbox Interstate '76 is not running." }
$h = [FRT]::OpenProcess(0x438, $false, $proc.Id)   # VM_OP|VM_READ|VM_WRITE|QUERY_INFORMATION
if ($h -eq [IntPtr]::Zero) { throw "OpenProcess failed." }
New-Item -ItemType Directory -Force $OutDir | Out-Null
Get-ChildItem $OutDir -Filter *.png -ErrorAction SilentlyContinue | Remove-Item -Force

function RdF([int64]$a) { $b = New-Object byte[] 4; $n = 0
    [void][FRT]::ReadProcessMemory($h, [IntPtr]$a, $b, 4, [ref]$n); [BitConverter]::ToSingle($b,0) }
function WrF([int64]$a, [single]$v) { $b = [BitConverter]::GetBytes($v); $n = 0
    [void][FRT]::WriteProcessMemory($h, [IntPtr]$a, $b, 4, [ref]$n) }
function Shot([string]$path) {
    $vs = [Windows.Forms.SystemInformation]::VirtualScreen
    $bmp = New-Object Drawing.Bitmap $vs.Width, $vs.Height
    $g = [Drawing.Graphics]::FromImage($bmp)
    try { $g.CopyFromScreen($vs.X, $vs.Y, 0, 0, $bmp.Size); $bmp.Save($path, [Drawing.Imaging.ImageFormat]::Png) }
    finally { $g.Dispose(); $bmp.Dispose() }
}

$px = RdF $POS_TABLE; $py = RdF ($POS_TABLE + 4); $pz = RdF ($POS_TABLE + 8)
Write-Host ("player position = ({0:N2}, {1:N2}, {2:N2})" -f $px, $py, $pz) -ForegroundColor Cyan
if ($px -eq 0 -and $pz -eq 0) { throw "Position table empty - load a mission." }

# --- value search: every float3 in memory equal to the player position ---------
$addr = [int64]0x10000; $found = @(); $scanned = 0
while ($addr -lt [int64]0x7FFF0000 -and $scanned -lt ($BudgetMB * 1MB)) {
    $mbi = New-Object MBI3
    if ([FRT]::VirtualQueryEx($h, [IntPtr]$addr, [ref]$mbi, [Runtime.InteropServices.Marshal]::SizeOf($mbi)) -eq 0) { break }
    $size = [int64]$mbi.RegionSize
    if ($size -le 0) { break }
    if ($mbi.State -eq 0x1000 -and (@(0x04, 0x02, 0x40, 0x08, 0x20) -contains $mbi.Protect) -and $size -le ($MaxRegionMB * 1MB)) {
        $buf = New-Object byte[] $size; $n = 0
        if ([FRT]::ReadProcessMemory($h, [IntPtr]$mbi.BaseAddress, $buf, $size, [ref]$n) -and $n -gt 12) {
            $scanned += $n
            for ($o = 0; $o -le $n - 12; $o += 4) {
                $x = [BitConverter]::ToSingle($buf, $o)
                if ([math]::Abs($x - $px) -gt $Tol) { continue }
                $y = [BitConverter]::ToSingle($buf, $o + 4)
                if ([math]::Abs($y - $py) -gt $Tol) { continue }
                $z = [BitConverter]::ToSingle($buf, $o + 8)
                if ([math]::Abs($z - $pz) -gt $Tol) { continue }
                $found += ([int64]$mbi.BaseAddress + $o)
            }
        }
    }
    $addr += $size
}
Write-Host ("copies of the position found: {0} (scanned {1:N0} MB)" -f $found.Count, ($scanned/1MB)) -ForegroundColor Green
$found | ForEach-Object { "0x{0:X8}" -f $_ } | Set-Content (Join-Path $OutDir 'candidates.txt')
if ($found.Count -eq 0) { throw "No copies found - widen -Tol." }

# --- poke each candidate, screenshotting before/after --------------------------
$list = $found | Select-Object -First $MaxCandidates
Write-Host ("poke-testing {0} candidates with DY={1} ..." -f $list.Count, $DY) -ForegroundColor Yellow
$i = 0
foreach ($va in $list) {
    $i++
    $ay = $va + 4                      # Y component
    $orig = RdF $ay
    if ([double]::IsNaN($orig)) { continue }
    $tag = "{0:D2}_{1:X8}" -f $i, $va
    try {
        Shot (Join-Path $OutDir "$tag`_a.png")
        WrF $ay ([single]($orig + $DY))
        Start-Sleep -Milliseconds 260   # let a few frames render
        Shot (Join-Path $OutDir "$tag`_b.png")
    } finally {
        WrF $ay ([single]$orig)          # always restore
    }
    Start-Sleep -Milliseconds 120
    Write-Host ("  [{0,2}/{1}] 0x{2:X8}  y {3:N2} -> {4:N2} -> restored" -f $i, $list.Count, $va, $orig, ($orig + $DY))
}
[FRT]::CloseHandle($h) | Out-Null
Write-Host ("DONE. Screenshots in {0} - compare with compare-shots.py" -f (Resolve-Path $OutDir)) -ForegroundColor Green
