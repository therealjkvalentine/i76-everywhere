<#
  poke-candidates.ps1 — which position copy does the RENDERER read?

  Takes the copies found by dump-memory.ps1 + the Python value search (candidates.txt) and,
  for each: screenshot -> write Y+DY -> screenshot -> restore. Whichever poke changes the
  picture is the transform the 60 Hz interpolation must write to.

  Writes 4 bytes of float DATA per candidate, always restored in a finally block.
  Sandbox-only via the path guard.
#>
param(
    [string]$InDir  = "$PSScriptRoot\..\..\captures\dump",
    [string]$OutDir = "$PSScriptRoot\..\..\captures\rt",
    [double]$DY = 60,
    [string]$RequirePath = 'i76-uncap-lab'
)
$ErrorActionPreference = 'Stop'
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class PC {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(uint a, bool i, int p);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr a, byte[] b, int s, out int r);
  [DllImport("kernel32.dll")] public static extern bool WriteProcessMemory(IntPtr h, IntPtr a, byte[] b, int s, out int w);
  [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
}
"@
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms

$proc = Get-Process i76, nitro -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -and $_.Path -like "*$RequirePath*" } | Select-Object -First 1
if (-not $proc) { throw "Sandbox Interstate '76 is not running." }
$h = [PC]::OpenProcess(0x38, $false, $proc.Id)
if ($h -eq [IntPtr]::Zero) { throw "OpenProcess failed." }
New-Item -ItemType Directory -Force $OutDir | Out-Null
Get-ChildItem $OutDir -Filter *.png -ErrorAction SilentlyContinue | Remove-Item -Force

function RdF([int64]$a) { $b = New-Object byte[] 4; $n = 0
    [void][PC]::ReadProcessMemory($h, [IntPtr]$a, $b, 4, [ref]$n); [BitConverter]::ToSingle($b,0) }
function WrF([int64]$a, [single]$v) { $b = [BitConverter]::GetBytes($v); $n = 0
    [void][PC]::WriteProcessMemory($h, [IntPtr]$a, $b, 4, [ref]$n) }
function Shot([string]$path) {
    $vs = [Windows.Forms.SystemInformation]::VirtualScreen
    $bmp = New-Object Drawing.Bitmap $vs.Width, $vs.Height
    $g = [Drawing.Graphics]::FromImage($bmp)
    try { $g.CopyFromScreen($vs.X, $vs.Y, 0, 0, $bmp.Size); $bmp.Save($path, [Drawing.Imaging.ImageFormat]::Png) }
    finally { $g.Dispose(); $bmp.Dispose() }
}

$cands = Get-Content (Join-Path $InDir 'candidates.txt') | Where-Object { $_ -match '^0x[0-9A-Fa-f]+$' } |
         ForEach-Object { [Convert]::ToInt64($_.Substring(2), 16) }
Write-Host ("testing {0} candidates, DY={1}" -f $cands.Count, $DY) -ForegroundColor Cyan
$i = 0
foreach ($va in $cands) {
    $i++
    $ay = $va + 4
    $orig = RdF $ay
    $tag = "{0:D2}_{1:X8}" -f $i, $va
    try {
        Shot (Join-Path $OutDir "$tag`_a.png")
        # The engine rewrites every copy each sim tick (~50 ms), so a single write is gone
        # long before a screenshot lands. Hold an ABSOLUTE target in a tight loop instead so
        # the value is present whenever the renderer happens to read it. (Absolute, not
        # read-add: reading back our own write and adding again runs away to +infinity.)
        $target = [single]($orig + $DY)
        $sw = [Diagnostics.Stopwatch]::StartNew(); $shot = $false; $stuck = 0; $tries = 0
        while ($sw.Elapsed.TotalMilliseconds -lt 1400) {
            WrF $ay $target
            $tries++
            if ([math]::Abs((RdF $ay) - $target) -lt 0.01) { $stuck++ }
            if (-not $shot -and $sw.Elapsed.TotalMilliseconds -gt 700) { Shot (Join-Path $OutDir "$tag`_b.png"); $shot = $true }
        }
        $rb = "held {0}/{1} samples" -f $stuck, $tries
    } finally { WrF $ay ([single]$orig) }
    Write-Host ("  [{0}/{1}] 0x{2:X8}  {3:N2} -> held {4:N2}: {5} -> restored" -f $i, $cands.Count, $va, $orig, ($orig+$DY), $rb)
    Start-Sleep -Milliseconds 150
}
[PC]::CloseHandle($h) | Out-Null
Write-Host ("DONE -> {0}" -f (Resolve-Path $OutDir)) -ForegroundColor Green
