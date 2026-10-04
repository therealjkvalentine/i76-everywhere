<#
  poke-frozen.ps1 — the clean attribution test for "does the renderer read this address?"

  Problem with testing while the sim runs: AI cars move, so the picture changes on its own
  and a pixel diff cannot be attributed to our write. Also the engine rewrites every position
  copy each sim tick, so a single write is reverted before a screenshot lands.

  The trick: I'76 FREEZES its simulation when the window loses focus but keeps RENDERING.
  So with the game visible-but-unfocused (windowed):
    - the scene is perfectly static  -> any pixel change is ours
    - nothing overwrites our value   -> a single write persists
  This makes the test deterministic.

  For each candidate: shot -> write Y+DY -> shot -> restore. Sandbox-only, always restores.

  REQUIREMENT: the game must be WINDOWED, VISIBLE, and NOT focused. Run it, then click on
  another window (or just leave focus where it is) - the script verifies before testing.
#>
param(
    [string]$InDir  = "$PSScriptRoot\..\..\captures\dump",
    [string]$OutDir = "$PSScriptRoot\..\..\captures\frozen",
    [double]$DY = 80,
    [string]$RequirePath = 'i76-uncap-lab'
)
$ErrorActionPreference = 'Stop'
Add-Type @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public class PF {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(uint a, bool i, int p);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr a, byte[] b, int s, out int r);
  [DllImport("kernel32.dll")] public static extern bool WriteProcessMemory(IntPtr h, IntPtr a, byte[] b, int s, out int w);
  [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
}
"@
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms

$proc = Get-Process i76, nitro -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -and $_.Path -like "*$RequirePath*" } | Select-Object -First 1
if (-not $proc) { throw "Sandbox Interstate '76 is not running." }
$h = [PF]::OpenProcess(0x38, $false, $proc.Id)
New-Item -ItemType Directory -Force $OutDir | Out-Null
Get-ChildItem $OutDir -Filter *.png -ErrorAction SilentlyContinue | Remove-Item -Force

function RdF([int64]$a) { $b = New-Object byte[] 4; $n = 0
    [void][PF]::ReadProcessMemory($h, [IntPtr]$a, $b, 4, [ref]$n); [BitConverter]::ToSingle($b,0) }
function WrF([int64]$a, [single]$v) { $b = [BitConverter]::GetBytes($v); $n = 0
    [void][PF]::WriteProcessMemory($h, [IntPtr]$a, $b, 4, [ref]$n) }
function Shot([string]$path) {
    $vs = [Windows.Forms.SystemInformation]::VirtualScreen
    $bmp = New-Object Drawing.Bitmap $vs.Width, $vs.Height
    $g = [Drawing.Graphics]::FromImage($bmp)
    try { $g.CopyFromScreen($vs.X, $vs.Y, 0, 0, $bmp.Size); $bmp.Save($path, [Drawing.Imaging.ImageFormat]::Png) }
    finally { $g.Dispose(); $bmp.Dispose() }
}

# --- confirm the sim really is frozen (that is what makes this test valid) ------
$fg = [PF]::GetForegroundWindow(); $fgPid = 0
[void][PF]::GetWindowThreadProcessId($fg, [ref]$fgPid)
Write-Host ("game focused: {0}" -f ($fgPid -eq $proc.Id))
$w = RdF 0x54E11C
Start-Sleep -Milliseconds 400
$w2 = RdF 0x54E11C
$frozen = ($w -eq $w2)
Write-Host ("player X: {0:N3} -> {1:N3}   sim frozen: {2}" -f $w, $w2, $frozen) -ForegroundColor $(if ($frozen) { 'Green' } else { 'Red' })
if (-not $frozen) { throw "Sim is RUNNING - results could not be attributed. Click another window so I'76 freezes, then re-run." }

$cands = Get-Content (Join-Path $InDir 'candidates.txt') | Where-Object { $_ -match '^0x[0-9A-Fa-f]+$' } |
         ForEach-Object { [Convert]::ToInt64($_.Substring(2), 16) }
Write-Host ("testing {0} candidates, DY={1} (sim frozen, single write each)" -f $cands.Count, $DY) -ForegroundColor Cyan
Shot (Join-Path $OutDir 'ctrl_a.png'); Start-Sleep -Milliseconds 400; Shot (Join-Path $OutDir 'ctrl_b.png')

$i = 0
foreach ($va in $cands) {
    $i++
    $ay = $va + 4
    $orig = RdF $ay
    $tag = "{0:D2}_{1:X8}" -f $i, $va
    try {
        Shot (Join-Path $OutDir "$tag`_a.png")
        WrF $ay ([single]($orig + $DY))
        Start-Sleep -Milliseconds 400
        $rb = RdF $ay
        Shot (Join-Path $OutDir "$tag`_b.png")
    } finally { WrF $ay ([single]$orig) }
    Write-Host ("  [{0}/{1}] 0x{2:X8}  {3:N2} -> {4:N2} (read {5:N2})" -f $i, $cands.Count, $va, $orig, ($orig+$DY), $rb)
    Start-Sleep -Milliseconds 150
}
[PF]::CloseHandle($h) | Out-Null
Write-Host ("DONE -> {0}" -f (Resolve-Path $OutDir)) -ForegroundColor Green
