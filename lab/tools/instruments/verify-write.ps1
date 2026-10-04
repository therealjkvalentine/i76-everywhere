<#
  verify-write.ps1 — did the write actually land? (writes 4 bytes, restores immediately)

  Distinguishes the two reasons a poke can appear to do nothing:
    (a) WriteProcessMemory silently failed / was rejected  -> read-back shows the old value
    (b) the write landed but the ENGINE overwrote it next tick, or the renderer
        doesn't read that address at all                   -> immediate read-back shows the
                                                              new value, delayed read shows old
  Sandbox-only (path guard), restores the original value in a finally block.
#>
param(
    [int64]$Addr = 0x54E120,        # player position Y in the 0x54E11C table
    [double]$Delta = 40,
    [string]$RequirePath = 'i76-uncap-lab'
)
$ErrorActionPreference = 'Stop'
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class VW {
  [DllImport("kernel32.dll", SetLastError=true)] public static extern IntPtr OpenProcess(uint a, bool i, int p);
  [DllImport("kernel32.dll", SetLastError=true)] public static extern bool ReadProcessMemory(IntPtr h, IntPtr a, byte[] b, int s, out int r);
  [DllImport("kernel32.dll", SetLastError=true)] public static extern bool WriteProcessMemory(IntPtr h, IntPtr a, byte[] b, int s, out int w);
  [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
}
"@
$proc = Get-Process i76, nitro -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -and $_.Path -like "*$RequirePath*" } | Select-Object -First 1
if (-not $proc) { throw "Sandbox I'76 not running." }
$h = [VW]::OpenProcess(0x38, $false, $proc.Id)
if ($h -eq [IntPtr]::Zero) { throw ("OpenProcess failed, win32 error {0}" -f [Runtime.InteropServices.Marshal]::GetLastWin32Error()) }
function RdF([int64]$a) { $b = New-Object byte[] 4; $n = 0
    [void][VW]::ReadProcessMemory($h, [IntPtr]$a, $b, 4, [ref]$n); [BitConverter]::ToSingle($b,0) }

$orig = RdF $Addr
Write-Host ("addr 0x{0:X}  original = {1:N3}" -f $Addr, $orig) -ForegroundColor Cyan
try {
    $buf = [BitConverter]::GetBytes([single]($orig + $Delta)); $w = 0
    $ok = [VW]::WriteProcessMemory($h, [IntPtr]$Addr, $buf, 4, [ref]$w)
    $err = [Runtime.InteropServices.Marshal]::GetLastWin32Error()
    Write-Host ("WriteProcessMemory -> ok={0} bytesWritten={1} lastError={2}" -f $ok, $w, $err) -ForegroundColor $(if ($ok) { 'Green' } else { 'Red' })
    $immediate = RdF $Addr
    Start-Sleep -Milliseconds 120
    $after120 = RdF $Addr
    Start-Sleep -Milliseconds 500
    $after620 = RdF $Addr
    Write-Host ("immediate read-back = {0:N3}   (wanted {1:N3})" -f $immediate, ($orig + $Delta))
    Write-Host ("after 120 ms        = {0:N3}" -f $after120)
    Write-Host ("after 620 ms        = {0:N3}" -f $after620)
    Write-Host ""
    if ([math]::Abs($immediate - ($orig + $Delta)) -lt 0.01) {
        Write-Host "=> WRITE WORKS. The value landed." -ForegroundColor Green
        if ([math]::Abs($after120 - $orig) -lt 1.0) {
            Write-Host "=> ...and the ENGINE OVERWROTE it within ~120 ms (it rewrites this table every sim tick)." -ForegroundColor Yellow
        } else {
            Write-Host "=> ...and it PERSISTED. So the renderer simply does not draw from this address." -ForegroundColor Yellow
        }
    } else {
        Write-Host "=> WRITE DID NOT LAND. Memory protection or wrong address - not a renderer question." -ForegroundColor Red
    }
} finally {
    $b = [BitConverter]::GetBytes([single]$orig); $n = 0
    [void][VW]::WriteProcessMemory($h, [IntPtr]$Addr, $b, 4, [ref]$n)
    [VW]::CloseHandle($h) | Out-Null
    Write-Host "restored." -ForegroundColor Green
}
