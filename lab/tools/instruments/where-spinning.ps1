<#
  where-spinning.ps1 — sample the instruction pointer of a hung/spinning 32-bit process.

  When the game locks up at 100% CPU with Responding=False, it is in a tight loop that never
  pumps messages. This finds WHICH loop by sampling EIP of every running thread and mapping each
  sample to the module that owns it (i76.exe / i76shell.dll / a renderer DLL / a system DLL).
  Where it spins IS the diagnosis.

  PowerShell is 64-bit and the game is 32-bit, so this uses the WOW64 context APIs
  (Wow64SuspendThread / Wow64GetThreadContext) - the plain GetThreadContext returns the 64-bit
  context of the WOW64 wrapper, not the game's real x86 EIP.

  Suspends each thread only for the microseconds needed to read its context, then resumes it.
  Safe to run against a hung process (it is already stuck), and read-only otherwise.

    tools\instruments\where-spinning.ps1              # 12 samples
    tools\instruments\where-spinning.ps1 -Samples 30
#>
param([int]$Samples = 12, [string]$ProcName = 'i76', [int]$TargetPid = 0)
$ErrorActionPreference = 'Stop'

Add-Type @"
using System;using System.Runtime.InteropServices;
public class Spin {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenThread(uint access, bool inherit, uint tid);
  [DllImport("kernel32.dll")] public static extern uint Wow64SuspendThread(IntPtr h);
  [DllImport("kernel32.dll")] public static extern int ResumeThread(IntPtr h);
  [DllImport("kernel32.dll")] public static extern bool Wow64GetThreadContext(IntPtr h, byte[] ctx);
  [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
}
"@

# pick by pid when given; otherwise the instance with real threads (a dying process can linger
# in the process list with 0 threads and shadow the one you actually want)
if ($TargetPid) { $proc = Get-Process -Id $TargetPid }
else { $proc = Get-Process $ProcName -EA SilentlyContinue | Where-Object { $_.Threads.Count -gt 0 } | Sort-Object { $_.Threads.Count } -Descending | Select-Object -First 1 }
if (-not $proc) { throw "$ProcName not running" }
Write-Host ("pid {0}  Responding={1}  threads={2}" -f $proc.Id, $proc.Responding, $proc.Threads.Count) -ForegroundColor Cyan

# module map for attributing an EIP
$mods = @()
foreach ($m in $proc.Modules) {
    $mods += [pscustomobject]@{ Name = $m.ModuleName; Base = [int64]$m.BaseAddress; End = ([int64]$m.BaseAddress + $m.ModuleMemorySize) }
}
function Attribute([int64]$eip) {
    foreach ($m in $mods) { if ($eip -ge $m.Base -and $eip -lt $m.End) { return ("{0}+0x{1:X}" -f $m.Name, ($eip - $m.Base)) } }
    return "UNKNOWN"
}

$CONTEXT_CONTROL = 0x00010001
$SZ = 716            # sizeof(WOW64_CONTEXT)
$EIP_OFF = 184       # offset of Eip in the x86 CONTEXT
$THREAD_ACCESS = 0x0002 -bor 0x0008 -bor 0x0040   # GET_CONTEXT | SUSPEND_RESUME | QUERY_INFORMATION

$hits = @{}
for ($s = 0; $s -lt $Samples; $s++) {
    $proc.Refresh()
    foreach ($t in $proc.Threads) {
        if ($t.ThreadState -ne 'Running') { continue }
        $h = [Spin]::OpenThread($THREAD_ACCESS, $false, [uint32]$t.Id)
        if ($h -eq [IntPtr]::Zero) { continue }
        try {
            if ([Spin]::Wow64SuspendThread($h) -ne [uint32]::MaxValue) {
                $ctx = New-Object byte[] $SZ
                [BitConverter]::GetBytes([uint32]$CONTEXT_CONTROL).CopyTo($ctx, 0)
                if ([Spin]::Wow64GetThreadContext($h, $ctx)) {
                    $eip = [BitConverter]::ToUInt32($ctx, $EIP_OFF)
                    $key = Attribute $eip
                    if (-not $hits.ContainsKey($key)) { $hits[$key] = @{ n = 0; eips = @{} } }
                    $hits[$key].n++
                    $e = '0x{0:X8}' -f $eip
                    $hits[$key].eips[$e] = ($hits[$key].eips[$e] + 1)
                }
                [void][Spin]::ResumeThread($h)
            }
        } finally { [void][Spin]::CloseHandle($h) }
    }
    Start-Sleep -Milliseconds 60
}

Write-Host "`n=== where the running thread(s) were caught ===" -ForegroundColor Yellow
if (-not $hits.Count) { Write-Host "  no Running thread sampled (it may alternate states) - try -Samples 40" -ForegroundColor Yellow }
foreach ($k in ($hits.Keys | Sort-Object { -$hits[$_].n })) {
    Write-Host ("  {0,-34} {1} sample(s)" -f $k, $hits[$k].n) -ForegroundColor Green
    foreach ($e in ($hits[$k].eips.Keys | Sort-Object { -$hits[$k].eips[$_] } | Select-Object -First 6)) {
        Write-Host ("      EIP {0}  x{1}" -f $e, $hits[$k].eips[$e])
    }
}
