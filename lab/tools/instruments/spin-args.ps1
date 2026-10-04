<#
  spin-args.ps1 — read the ARGUMENTS of the syscall a hung process is spinning on.

  where-spinning.ps1 says WHERE (win32u.dll+0x12AC = NtUserCallTwoParam). That stub is
  multiplexed: many USER32 functions funnel through it and are told apart by a routine index
  passed on the stack. This grabs ESP from the suspended thread and dumps the stack words, so
  the index (and therefore the actual USER32 call being hammered) can be identified.

  Known TWOPARAM routine indices of interest for this game's shell:
      0x33 SETCURSORPOS   0x34 GETCURSORPOS   (exact values vary by Windows build)
  Whatever it is, a repeating constant in the same stack slot across samples IS the index.

    tools\instruments\spin-args.ps1 -TargetPid 22920 -Samples 8
#>
param([Parameter(Mandatory=$true)][int]$TargetPid, [int]$Samples = 8)
$ErrorActionPreference = 'Stop'
Add-Type @"
using System;using System.Runtime.InteropServices;
public class SA {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenThread(uint a,bool i,uint t);
  [DllImport("kernel32.dll")] public static extern uint Wow64SuspendThread(IntPtr h);
  [DllImport("kernel32.dll")] public static extern int ResumeThread(IntPtr h);
  [DllImport("kernel32.dll")] public static extern bool Wow64GetThreadContext(IntPtr h, byte[] c);
  [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(uint a,bool i,int p);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h,IntPtr a,byte[] b,int s,out int r);
}
"@
$proc = Get-Process -Id $TargetPid
$hp = [SA]::OpenProcess(0x0410,$false,$TargetPid)
$CTX=0x00010001; $SZ=716; $EIP=184; $ESP=196; $EBP=180
$ACC = 0x0002 -bor 0x0008 -bor 0x0040
$rows=@()
for($s=0;$s -lt $Samples;$s++){
  $proc.Refresh()
  foreach($t in $proc.Threads){
    if($t.ThreadState -ne 'Running'){ continue }
    $h=[SA]::OpenThread($ACC,$false,[uint32]$t.Id)
    if($h -eq [IntPtr]::Zero){ continue }
    try{
      if([SA]::Wow64SuspendThread($h) -ne [uint32]::MaxValue){
        $c=New-Object byte[] $SZ
        [BitConverter]::GetBytes([uint32]$CTX).CopyTo($c,0)
        if([SA]::Wow64GetThreadContext($h,$c)){
          $eip=[BitConverter]::ToUInt32($c,$EIP); $esp=[BitConverter]::ToUInt32($c,$ESP)
          $buf=New-Object byte[] 48; $n=0
          [void][SA]::ReadProcessMemory($hp,[IntPtr]$esp,$buf,48,[ref]$n)
          $words=@(); for($k=0;$k -lt 12;$k++){ $words += ('{0:X8}' -f [BitConverter]::ToUInt32($buf,$k*4)) }
          $rows += [pscustomobject]@{ eip=('{0:X8}' -f $eip); esp=('{0:X8}' -f $esp); stack=($words -join ' ') }
        }
        [void][SA]::ResumeThread($h)
      }
    } finally { [void][SA]::CloseHandle($h) }
  }
  Start-Sleep -Milliseconds 40
}
"EIP      ESP      [ESP+0] [+4]     [+8]     [+C]     [+10]    [+14]    [+18]    [+1C]    [+20]    [+24]    [+28]    [+2C]"
$rows | ForEach-Object { "{0} {1} {2}" -f $_.eip,$_.esp,$_.stack }
"`n=== stack words that are IDENTICAL across every sample (the routine index will be one) ==="
if($rows.Count -gt 1){
  $split = $rows | ForEach-Object { ,($_.stack -split ' ') }
  for($k=0;$k -lt 12;$k++){
    $vals = $split | ForEach-Object { $_[$k] } | Sort-Object -Unique
    if($vals.Count -eq 1){ "  [ESP+0x{0:X}] = {1}  (constant)" -f ($k*4), $vals[0] }
  }
}
[void][SA]::CloseHandle($hp)
