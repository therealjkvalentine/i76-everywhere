<#
  poke-probe.ps1 — why did a WriteProcessMemory not stick?

  Three different failures look identical if you only read back after a delay:
    1. the write failed        -> WriteProcessMemory returns false; check GetLastError
    2. the page is not writable-> VirtualQueryEx protection says so
    3. the write SUCCEEDED and the game overwrote it again -> immediate read differs from
       the delayed read

  Distinguishing them matters: (3) means the address IS the live value but is refreshed from
  somewhere else each frame, which is a finding, not a failure.
#>
param([Parameter(Mandatory=$true)][int64]$Addr, [int]$Value = 50)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\..\autotest\lib\focuslib.ps1"
Add-Type @"
using System; using System.Runtime.InteropServices;
public class PP {
  [StructLayout(LayoutKind.Sequential)] public struct MBI {
    public IntPtr BaseAddress, AllocationBase; public uint AllocationProtect;
    public IntPtr RegionSize; public uint State, Protect, Type; }
  [DllImport("kernel32.dll",SetLastError=true)] public static extern IntPtr OpenProcess(int a,bool b,int c);
  [DllImport("kernel32.dll",SetLastError=true)] public static extern bool ReadProcessMemory(IntPtr h,IntPtr a,byte[] b,int s,out int r);
  [DllImport("kernel32.dll",SetLastError=true)] public static extern bool WriteProcessMemory(IntPtr h,IntPtr a,byte[] b,int s,out int r);
  [DllImport("kernel32.dll",SetLastError=true)] public static extern int VirtualQueryEx(IntPtr h,IntPtr a,out MBI m,int len);
  [DllImport("kernel32.dll",SetLastError=true)] public static extern bool VirtualProtectEx(IntPtr h,IntPtr a,UIntPtr s,uint p,out uint old);
}
"@
$gp = Get-GamePid
$H = [PP]::OpenProcess(0x438, $false, $gp.Id)
"process $($gp.Id), handle $H"

$mbi = New-Object PP+MBI
[void][PP]::VirtualQueryEx($H, [IntPtr]$Addr, [ref]$mbi, [Runtime.InteropServices.Marshal]::SizeOf($mbi))
$names = @{ 0x01='NOACCESS'; 0x02='READONLY'; 0x04='READWRITE'; 0x08='WRITECOPY';
            0x10='EXECUTE'; 0x20='EXECUTE_READ'; 0x40='EXECUTE_READWRITE'; 0x80='EXECUTE_WRITECOPY' }
$pn = $names[[int]$mbi.Protect]; if(-not $pn){ $pn = ('0x{0:X}' -f $mbi.Protect) }
"region base 0x{0:X}  size 0x{1:X}  state 0x{2:X}  protect {3}" -f `
    $mbi.BaseAddress.ToInt64(), $mbi.RegionSize.ToInt64(), $mbi.State, $pn

function Peek([int64]$a){ $b=New-Object byte[] 4; $n=0
    [void][PP]::ReadProcessMemory($H,[IntPtr]$a,$b,4,[ref]$n); [BitConverter]::ToInt32($b,0) }

"before          : $(Peek $Addr)"
$buf = [BitConverter]::GetBytes([int]$Value); $wrote = 0
$ok = [PP]::WriteProcessMemory($H, [IntPtr]$Addr, $buf, 4, [ref]$wrote)
$err = [Runtime.InteropServices.Marshal]::GetLastWin32Error()
"WriteProcessMemory -> $ok (bytes=$wrote, lastError=$err)"
"immediately after: $(Peek $Addr)"
Start-Sleep -Milliseconds 300
"after 300ms     : $(Peek $Addr)"
Start-Sleep -Milliseconds 1500
"after 1.8s      : $(Peek $Addr)"
Write-Host ""
Write-Host "immediate==Value but later!=Value  => live value, refreshed each frame" -ForegroundColor Yellow
Write-Host "immediate!=Value                   => the write never landed" -ForegroundColor Yellow
