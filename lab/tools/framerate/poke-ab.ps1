<#
  poke-ab.ps1 — which position copy does the renderer read? (A/B with ambient control)

  Attribution problem: while the sim runs, AI cars move so the picture changes on its own;
  and the engine rewrites every position copy each tick, so a single write is gone before a
  screenshot lands. This harness handles both:

    * HOLDS an absolute offset in a tight write loop, so the value is present across renders.
    * Brackets every held test with a NO-WRITE control over the same duration, so ambient
      scene motion is measured and subtracted.

  Per candidate:
    shotA (no write) -> wait -> shotB (no write)   => ambient      = diff(A,B)
    begin hold(offset) -> wait -> shotC (holding)  => ambient+eff  = diff(B,C)
    net = diff(B,C) - diff(A,B)                      the render-consumed copy has net >> 0

  Focuses the game window itself (SetForegroundWindow) so the sim runs during the test.
  Sandbox-only via the path guard; every write is restored. Analysis is done by ab-analyze.py.
#>
param(
    [string]$InDir  = "$PSScriptRoot\..\..\captures\dump",
    [string]$OutDir = "$PSScriptRoot\..\..\captures\ab",
    [double]$DX = 800,
    [double]$DY = 600,
    [double]$DZ = 800,
    [int]$HoldMs = 300,
    [string]$RequirePath = 'i76-uncap-lab'
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\..\autotest\lib\focuslib.ps1"
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class AB {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(uint a, bool i, int p);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr a, byte[] b, int s, out int r);
  [DllImport("kernel32.dll")] public static extern bool WriteProcessMemory(IntPtr h, IntPtr a, byte[] b, int s, out int w);
  [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
}
"@
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms

$proc = Get-Process i76, nitro -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -and $_.Path -like "*$RequirePath*" } | Select-Object -First 1
if (-not $proc) { throw "Sandbox Interstate '76 is not running." }
$h = [AB]::OpenProcess(0x38, $false, $proc.Id)
New-Item -ItemType Directory -Force $OutDir | Out-Null
Get-ChildItem $OutDir -Filter *.png -ErrorAction SilentlyContinue | Remove-Item -Force

# bring the game to the foreground - REQUIRED, or CopyFromScreen captures a stale frame
$foc = Force-Foreground $proc.MainWindowHandle
Write-Host ("focus success: {0}" -f $foc) -ForegroundColor $(if ($foc) { 'Green' } else { 'Red' })
if (-not $foc) { throw "Could not focus the game - screenshots would be stale." }
Start-Sleep -Milliseconds 500

function RdF([int64]$a) { $b = New-Object byte[] 4; $n = 0
    [void][AB]::ReadProcessMemory($h, [IntPtr]$a, $b, 4, [ref]$n); [BitConverter]::ToSingle($b,0) }
function Wr3([int64]$va, [single]$x, [single]$y, [single]$z) {
    $b = New-Object byte[] 12
    [BitConverter]::GetBytes($x).CopyTo($b,0); [BitConverter]::GetBytes($y).CopyTo($b,4); [BitConverter]::GetBytes($z).CopyTo($b,8)
    $n = 0; [void][AB]::WriteProcessMemory($h, [IntPtr]$va, $b, 12, [ref]$n)
}
function Shot([string]$path) {
    $vs = [Windows.Forms.SystemInformation]::VirtualScreen
    $bmp = New-Object Drawing.Bitmap $vs.Width, $vs.Height
    $g = [Drawing.Graphics]::FromImage($bmp)
    try { $g.CopyFromScreen($vs.X, $vs.Y, 0, 0, $bmp.Size); $bmp.Save($path, [Drawing.Imaging.ImageFormat]::Png) }
    finally { $g.Dispose(); $bmp.Dispose() }
}

$cands = Get-Content (Join-Path $InDir 'candidates.txt') | Where-Object { $_ -match '^0x[0-9A-Fa-f]+$' } |
         ForEach-Object { [Convert]::ToInt64($_.Substring(2), 16) }
Write-Host ("game pid {0}, {1} candidates, offset=({2},{3},{4}), hold {5}ms" -f $proc.Id, $cands.Count, $DX, $DY, $DZ, $HoldMs) -ForegroundColor Cyan

$i = 0
foreach ($va in $cands) {
    $i++
    $ox = RdF $va; $oy = RdF ($va + 4); $oz = RdF ($va + 8)
    $tag = "{0:D2}_{1:X8}" -f $i, $va
    Shot (Join-Path $OutDir "$tag`_A.png")                 # control frame 1 (no write)
    Start-Sleep -Milliseconds $HoldMs
    Shot (Join-Path $OutDir "$tag`_B.png")                 # control frame 2 (no write) -> ambient
    try {
        $sw = [Diagnostics.Stopwatch]::StartNew()
        while ($sw.Elapsed.TotalMilliseconds -lt $HoldMs) { Wr3 $va ([single]($ox+$DX)) ([single]($oy+$DY)) ([single]($oz+$DZ)) }
        Shot (Join-Path $OutDir "$tag`_C.png")             # held frame -> ambient + effect
    } finally { Wr3 $va ([single]$ox) ([single]$oy) ([single]$oz) }
    Write-Host ("  [{0}/{1}] 0x{2:X8}" -f $i, $cands.Count, $va)
    Start-Sleep -Milliseconds 120
}
[AB]::CloseHandle($h) | Out-Null
Write-Host ("DONE -> {0}" -f (Resolve-Path $OutDir)) -ForegroundColor Green
