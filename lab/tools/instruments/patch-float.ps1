<#
  patch-float.ps1 — write a float constant into the running game (sandbox only).

  Used to retune the engine's frame-dependent physics constants for a higher frame rate:
  I'76 integrates once per FRAME using a hardcoded timestep, so running at 60 Hz needs the
  step scaled by 20/60 to keep per-second behaviour identical.

  Known constants (Gold i76.exe, base 0x400000, .rdata constant pool):
      0x4BC71C = 0.05  = 1/20 s  <- the sim timestep
      0x4BC59C = 9.8            <- gravity m/s^2

  .rdata is read-only, so this VirtualProtectEx's the page first and restores protection.
  Prints the before/after value so the write is verified, never assumed.

    tools\patch-float.ps1 -Addr 0x4BC71C -Value 0.0166667      # 1/60 timestep
    tools\patch-float.ps1 -Addr 0x4BC71C -Restore              # back to 0.05
#>
param(
    [Parameter(Mandatory=$true)][int64]$Addr,
    [double]$Value = 0,
    [switch]$Restore,
    [double]$RestoreValue = 0.05,
    [string]$RequirePath = 'i76-uncap-lab'
)
$ErrorActionPreference = 'Stop'
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class PF2 {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(uint a, bool i, int p);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr a, byte[] b, int s, out int r);
  [DllImport("kernel32.dll")] public static extern bool WriteProcessMemory(IntPtr h, IntPtr a, byte[] b, int s, out int w);
  [DllImport("kernel32.dll")] public static extern bool VirtualProtectEx(IntPtr h, IntPtr a, UIntPtr size, uint newp, out uint oldp);
}
"@
$proc = Get-Process i76, nitro -EA SilentlyContinue | Where-Object { $_.Path -and $_.Path -like "*$RequirePath*" } | Select-Object -First 1
if (-not $proc) { throw "sandbox game not running" }
$h = [PF2]::OpenProcess(0x38, $false, $proc.Id)
if ($h -eq [IntPtr]::Zero) { throw "OpenProcess failed" }

$buf = New-Object byte[] 4; $n = 0
[void][PF2]::ReadProcessMemory($h, [IntPtr]$Addr, $buf, 4, [ref]$n)
$before = [BitConverter]::ToSingle($buf, 0)

$target = if ($Restore) { $RestoreValue } else { $Value }
$old = 0
[void][PF2]::VirtualProtectEx($h, [IntPtr]$Addr, [UIntPtr]::new(4), 0x04, [ref]$old)   # PAGE_READWRITE
$wb = [BitConverter]::GetBytes([single]$target)
$ok = [PF2]::WriteProcessMemory($h, [IntPtr]$Addr, $wb, 4, [ref]$n)
$dummy = 0
[void][PF2]::VirtualProtectEx($h, [IntPtr]$Addr, [UIntPtr]::new(4), $old, [ref]$dummy)

[void][PF2]::ReadProcessMemory($h, [IntPtr]$Addr, $buf, 4, [ref]$n)
$after = [BitConverter]::ToSingle($buf, 0)
"0x{0:X}: {1} -> {2}   (write ok={3}, verified={4})" -f $Addr, $before, $after, $ok, ([math]::Abs($after - $target) -lt 1e-6)
