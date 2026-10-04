<#
  identify-sky.ps1 — which per-frame value drives the sky animation?

  find-perframe.ps1 lists values advanced once per frame; this says which one is the sky.
  Method: with the car parked, the sky is the only thing moving in the upper part of the view.
  Measure how much the sky region changes over a second, then FREEZE a candidate (hold it at a
  constant value) and measure again. The candidate that makes sky motion stop is the one.

  Freezing is a data write only, held for the duration and then released.
#>
param([string[]]$Candidates = @('0x644334','0x501858','0x501918','0x59BCD4','0x5019B0'),
      [int]$HoldMs = 1200,
      [string]$OutDir = "$PSScriptRoot\..\..\captures\sky")
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\..\autotest\lib\memlib.ps1"
. "$PSScriptRoot\..\..\autotest\lib\focuslib.ps1"
. "$PSScriptRoot\..\..\autotest\lib\inputlib.ps1"
. "$PSScriptRoot\..\..\autotest\lib\simlib.ps1"
. "$PSScriptRoot\..\..\autotest\lib\maplib.ps1"
Add-Type -AssemblyName System.Drawing
New-Item -ItemType Directory -Force $OutDir | Out-Null

$ctx = Mem-Open -Write
if (-not (Mem-InMission $ctx)) { throw "not in a mission" }
if (-not (Ensure-SimRunning $ctx)) { throw "sim not advancing" }

function SkyDiff([string]$tag) {
    # two captures a second apart; compare the SKY BAND (upper part of the 4:3 UI)
    Capture-UI (Join-Path $OutDir "$tag`_a.png") | Out-Null
    Start-Sleep -Milliseconds 1000
    Capture-UI (Join-Path $OutDir "$tag`_b.png") | Out-Null
    $A = [Drawing.Bitmap]::FromFile((Join-Path $OutDir "$tag`_a.png"))
    $B = [Drawing.Bitmap]::FromFile((Join-Path $OutDir "$tag`_b.png"))
    # PURE SKY band only. A first attempt sampled x120-520 / y120-220 and caught terrain and
    # camera bob, so every candidate came back noisier than baseline and the test said nothing.
    # In TRIP mission 5 the gap between the ridges is clean sky with clouds:
    $sum = 0; $n = 0
    for ($y = 140; $y -lt 240; $y += 3) {
        for ($x = 150; $x -lt 550; $x += 3) {
            $pa = $A.GetPixel($x,$y); $pb = $B.GetPixel($x,$y)
            $sum += [math]::Abs($pa.R-$pb.R) + [math]::Abs($pa.G-$pb.G) + [math]::Abs($pa.B-$pb.B)
            $n++
        }
    }
    $A.Dispose(); $B.Dispose()
    return [math]::Round($sum / [math]::Max($n,1), 3)
}

$base = SkyDiff 'baseline'
Write-Host ("baseline sky motion: {0}" -f $base) -ForegroundColor Cyan

foreach ($c in $Candidates) {
    $addr = [Convert]::ToInt64($c.Substring(2), 16)
    $orig = Mem-F32 $ctx $addr
    # freeze: hold the value constant in a tight loop on a background runspace
    $job = Start-Job -ScriptBlock {
        param($procId,$addr,$val,$ms)
        Add-Type @"
using System;using System.Runtime.InteropServices;
public class FZ{ [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(uint a,bool i,int p);
 [DllImport("kernel32.dll")] public static extern bool WriteProcessMemory(IntPtr h,IntPtr a,byte[] b,int s,out int w);}
"@
        $h=[FZ]::OpenProcess(0x38,$false,$procId); $b=[BitConverter]::GetBytes([single]$val); $n=0
        $sw=[Diagnostics.Stopwatch]::StartNew()
        while($sw.Elapsed.TotalMilliseconds -lt $ms){ [void][FZ]::WriteProcessMemory($h,[IntPtr]$addr,$b,4,[ref]$n) }
    } -ArgumentList $ctx.Proc.Id, $addr, $orig, ($HoldMs + 2500)
    Start-Sleep -Milliseconds 250
    $d = SkyDiff ("frozen_" + $c.Substring(2))
    Stop-Job $job -EA SilentlyContinue; Remove-Job $job -Force -EA SilentlyContinue
    $verdict = if ($base -gt 0.5 -and $d -lt $base * 0.35) { '  <== SKY STOPPED' } else { '' }
    Write-Host ("{0} frozen -> sky motion {1}   (baseline {2}){3}" -f $c, $d, $base, $verdict)
    Start-Sleep -Milliseconds 400
}
Mem-Close $ctx
