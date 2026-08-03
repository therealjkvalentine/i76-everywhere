<#
  Is force feedback actually live in the running game?

  Answers the question you cannot answer by feel ("is it the wheel, the registry,
  or the game?") by reading the engine's own FFB state out of the live process.

  RUN IT WHILE YOU ARE IN A MISSION. The FFB module is opened when a mission
  starts, not at the menu - checking at the title screen reports "not loaded"
  even on a perfectly healthy setup, which is a trap I fell into myself.

  Usage:  powershell -ExecutionPolicy Bypass -File tools\check-ffb.ps1
#>
$ErrorActionPreference = 'Continue'

Add-Type @"
using System;using System.Runtime.InteropServices;
public class FFBChk {
 [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(uint a,bool i,int p);
 [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h,IntPtr a,byte[] b,int s,out int r);
 [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
}
"@ -ErrorAction SilentlyContinue

# Confirmed by Ghidra recon PART 4 (docs/GHIDRA-MEMORY-MAP.md): the game only
# emits FFB when it has a detected device, and these two globals say whether it does.
$ADDR_PRESENT = 0x52bbd0
$ADDR_OBJECT  = 0x52bbcc

$proc = Get-Process i76,nitro -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $proc) { Write-Host "Game is not running - start it, get INTO A MISSION, then re-run." -ForegroundColor Yellow; exit 1 }
Write-Host "game: $($proc.ProcessName) (PID $($proc.Id))" -ForegroundColor Cyan

# 1. registry gate - the Gold Edition looks for this key name specifically
$key = "HKLM:\SOFTWARE\WOW6432Node\ACTIVISION\Interstate '76"
$key2 = "HKLM:\SOFTWARE\ACTIVISION\Interstate '76"
$haveKey = (Test-Path $key) -or (Test-Path $key2)
Write-Host ("registry key            : {0}" -f $(if($haveKey){"present"}else{"MISSING - run enable-force-feedback.bat AS ADMIN"})) `
    -ForegroundColor $(if($haveKey){'Green'}else{'Red'})

# 2. is anything holding the device exclusively?
$tm = Get-Process tmJoycpl,TMController* -ErrorAction SilentlyContinue
Write-Host ("Thrustmaster panel open : {0}" -f $(if($tm){"YES - CLOSE IT (it takes the device; FFB then fails and the first shot crashes)"}else{"no"})) `
    -ForegroundColor $(if($tm){'Red'}else{'Green'})

# 3. has the module been pulled in?
#
# DO NOT use $proc.Modules or `tasklist /m` for this. i76.exe is 32-bit; from
# 64-bit tooling both enumerate only the WOW64 stubs and report the FFB module as
# absent even when it is loaded and working. That false negative cost a long
# detour here (it sent me hunting a LoadLibrary failure that never happened).
#
# The reliable signal is the exe's own GetProcAddress result: 0x52bbdc holds the
# I7FF_InitSystem pointer, written only after LoadLibrary AND GetProcAddress both
# succeed. Nonzero = the module is loaded and resolved.
$h = [FFBChk]::OpenProcess(0x38,$false,$proc.Id)
function RInt($a){ $b=New-Object byte[] 4; $r=0; [void][FFBChk]::ReadProcessMemory($h,[IntPtr]$a,$b,4,[ref]$r); [BitConverter]::ToInt32($b,0) }
$initProc = RInt 0x52bbdc
$mod = ($initProc -ne 0)
Write-Host ("I7_SFRCE.DLL loaded     : {0}" -f $(if($mod){"yes (I7FF_InitSystem @ 0x{0:X8})" -f $initProc}else{"no - LoadLibrary/GetProcAddress failed"})) `
    -ForegroundColor $(if($mod){'Green'}else{'Red'})

# 4. the engine's own verdict
$present = RInt $ADDR_PRESENT
$obj     = RInt $ADDR_OBJECT
[void][FFBChk]::CloseHandle($h)

Write-Host ("FF device detected flag : {0}" -f $present) -ForegroundColor $(if($present){'Green'}else{'Red'})
Write-Host ("FF effect object ptr    : 0x{0:X8}" -f $obj) -ForegroundColor $(if($obj){'Green'}else{'Red'})

Write-Host ""
if ($present -and $obj) {
    Write-Host "FFB IS LIVE. If you feel nothing, it is effect strength/tuning, not plumbing." -ForegroundColor Green
} elseif ($mod) {
    Write-Host "MODULE LOADED BUT NO DEVICE - this is I7FF_InitSystem failing:" -ForegroundColor Red
    Write-Host "  'I7FF_InitSystem Failed to open FF Joystick.  Try again next time.'" -ForegroundColor Red
    Write-Host ""
    Write-Host "The DLL, its exports and the registry are all fine - the wheel is not being" -ForegroundColor Yellow
    Write-Host "OPENED for force feedback. FFB needs DirectInput EXCLUSIVE acquisition, and it" -ForegroundColor Yellow
    Write-Host "is attempted ONCE during startup ('try again next time'). Likely causes:" -ForegroundColor Yellow
    Write-Host "  * something else held the device at that moment - Thrustmaster control panel," -ForegroundColor Yellow
    Write-Host "    or a previous i76 that crashed without releasing it (POWER-CYCLE the wheel)" -ForegroundColor Yellow
    Write-Host "  * the game window was not foreground when it tried (exclusive acquire wants it)." -ForegroundColor Yellow
    Write-Host "    Launching Lossless Scaling first can take focus - test once with PLAY.bat." -ForegroundColor Yellow
    Write-Host "  * the wheel was connected AFTER the game started." -ForegroundColor Yellow
} else {
    Write-Host "The FFB module never loaded (LoadLibrary or GetProcAddress failed)." -ForegroundColor Red
    Write-Host "Check i7_sfrce.dll is present in the game folder and its deps resolve" -ForegroundColor Yellow
    Write-Host "(KERNEL32/USER32/ADVAPI32/ole32/WINMM/DINPUT - all ship with Windows)." -ForegroundColor Yellow
}
