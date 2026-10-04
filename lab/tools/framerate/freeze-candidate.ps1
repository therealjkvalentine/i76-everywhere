<#
  freeze-candidate.ps1 — hold one per-frame value constant so a HUMAN can see what stops.

  Automated pixel comparison could not identify which per-frame value drives the sky: the
  sampled band kept catching terrain and camera motion, and every candidate came back noisier
  than baseline. A person looking at the screen settles it instantly.

  Run this, watch the game for the duration, and note whether the SKY stops moving.

    tools\freeze-candidate.ps1 -Addr 0x644334 -Seconds 10

  Candidates from find-perframe.ps1 (ratio ~3 = advanced once per frame):
    0x644334   0x501858   0x501918   0x59BCD4   0x5019B0   0x4F70F8   0x524550

  Data write only, released when the timer ends.
#>
param([Parameter(Mandatory=$true)][string]$Addr, [int]$Seconds = 10, [switch]$AsDouble)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\..\autotest\lib\memlib.ps1"
. "$PSScriptRoot\..\..\autotest\lib\focuslib.ps1"

$a = [Convert]::ToInt64($Addr.Substring(2), 16)
$ctx = Mem-Open -Write
if (-not (Mem-InMission $ctx)) { throw "not in a mission" }
Force-Foreground $ctx.Proc.MainWindowHandle | Out-Null
$orig = Mem-F32 $ctx $a
Write-Host ("freezing {0} (current value {1}) for {2}s - WATCH THE SKY" -f $Addr, $orig, $Seconds) -ForegroundColor Cyan

$job = Start-Job -ScriptBlock {
    param($procId, $addr, $val, $secs, $dbl)
    Add-Type @"
using System;using System.Runtime.InteropServices;
public class FZ2{ [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(uint a,bool i,int p);
 [DllImport("kernel32.dll")] public static extern bool WriteProcessMemory(IntPtr h,IntPtr a,byte[] b,int s,out int w);}
"@
    $h = [FZ2]::OpenProcess(0x38, $false, $procId)
    $b = if ($dbl) { [BitConverter]::GetBytes([double]$val) } else { [BitConverter]::GetBytes([single]$val) }
    $n = 0
    $sw = [Diagnostics.Stopwatch]::StartNew()
    while ($sw.Elapsed.TotalSeconds -lt $secs) { [void][FZ2]::WriteProcessMemory($h, [IntPtr]$addr, $b, $b.Length, [ref]$n) }
} -ArgumentList $ctx.Proc.Id, $a, $orig, $Seconds, $AsDouble.IsPresent

Start-Sleep -Seconds ($Seconds + 1)
Stop-Job $job -EA SilentlyContinue; Remove-Job $job -Force -EA SilentlyContinue
Mem-Close $ctx
Write-Host "released." -ForegroundColor Green
