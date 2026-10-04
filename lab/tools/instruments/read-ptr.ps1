Add-Type @"
using System;
using System.Runtime.InteropServices;
public class RP {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(uint a, bool i, int p);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr a, byte[] b, int s, out int r);
}
"@
$proc = Get-Process i76 -ErrorAction SilentlyContinue
if (-not $proc) { "i76 not running"; exit }
$h = [RP]::OpenProcess(0x10, $false, $proc.Id)
function Read32([int64]$a) { $b = New-Object byte[] 4; $n = 0; [void][RP]::ReadProcessMemory($h, [IntPtr]$a, $b, 4, [ref]$n); [uint32][BitConverter]::ToUInt32($b, 0) }
function ClassOf([uint32]$u) {
    if ($u -eq 0) { return 'NULL' }
    if ($u -ge 0x00400000 -and $u -lt 0x00700000) { return 'i76.exe (internal .text/.data)' }
    foreach ($m in $proc.Modules) {
        $base = [int64]$m.BaseAddress.ToInt64(); $end = $base + [int64]$m.ModuleMemorySize
        if ([int64]$u -ge $base -and [int64]$u -lt $end) { return ('{0} (+0x{1:X})' -f $m.ModuleName, ([int64]$u - $base)) }
    }
    return ('loaded module @ 0x{0:X8} (not in 32-bit module list)' -f $u)
}
foreach ($pair in @(@('BeginFrame','0x5DD2BC'), @('Flip/Present','0x5DD2C0'), @('post-ptr','0x5DD2E0'))) {
    $v = Read32 ([Convert]::ToInt64($pair[1], 16))
    '{0,-13} [{1}] -> 0x{2:X8}  {3}' -f $pair[0], $pair[1], $v, (ClassOf $v)
}
'--- renderer-ish modules (32-bit bases only) ---'
$proc.Modules | Where-Object { $_.ModuleName -match 'GLIDE|DX5|REDLINE|DDRAW|POWERVR|dgVoodoo|d3d|ZDX|ZGL|ZRE' } |
    ForEach-Object {
        $b = [int64]$_.BaseAddress.ToInt64()
        '{0,-16} base=0x{1:X}  size=0x{2:X}' -f $_.ModuleName, $b, $_.ModuleMemorySize
    }
