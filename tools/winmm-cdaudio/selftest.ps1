<#
  selftest.ps1 - exercise the CD-audio emulation WITHOUT the game.

  WHY: after installing the proxy the game ran, music was heard, and no log was
  written - which leaves it genuinely unclear whether the proxy did anything or
  whether the music came from somewhere else. Rather than guess, drive the DLL
  directly: open "cdaudio", ask how many tracks it has, play track 7, check it
  reports itself playing, stop, close.

  If this passes, the emulation works and any remaining problem is about how the
  GAME talks to it. If it fails, the problem is here and the game is irrelevant.

  MUST RUN IN 32-BIT POWERSHELL - the DLL is x86. This script re-launches itself
  under SysWOW64 automatically, since forgetting that is the single easiest way to
  waste a round (see docs/MUSIC.md on the same false negative for module lists).

      tools\winmm-cdaudio\selftest.ps1
      tools\winmm-cdaudio\selftest.ps1 -Track 3 -Seconds 6
#>
param(
    [int]$Track = 7,
    [int]$Seconds = 5,
    [string]$GameDir = "",
    [switch]$Relaunched
)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

# ---- make sure we are 32-bit ---------------------------------------------
if ([IntPtr]::Size -ne 4) {
    if ($Relaunched) { Write-Host "Could not get a 32-bit host." -ForegroundColor Red; exit 1 }
    $ps32 = "$env:WINDIR\SysWOW64\WindowsPowerShell\v1.0\powershell.exe"
    if (-not (Test-Path $ps32)) { Write-Host "No 32-bit PowerShell at $ps32" -ForegroundColor Red; exit 1 }
    Write-Host "(64-bit host - relaunching under SysWOW64)" -ForegroundColor DarkGray
    # -GameDir is only forwarded when it has a value: passing an EMPTY string as a
    # named [string] parameter makes PowerShell read the NEXT token as its value,
    # so "-GameDir '' -Relaunched" fails with "Missing an argument for parameter".
    $fwd = @('-NoProfile','-ExecutionPolicy','Bypass','-File',$PSCommandPath,
             '-Track',$Track,'-Seconds',$Seconds,'-Relaunched')
    if ($GameDir) { $fwd += @('-GameDir', $GameDir) }
    & $ps32 @fwd
    exit $LASTEXITCODE
}

# ---- locate the game folder (the DLL finds music\ relative to itself) ----
if (-not $GameDir) {
    foreach ($c in @(
        "C:\Users\james\Downloads\Interstate76-i76-everywhere-portable-20260801\Interstate 76",
        "C:\Games\Interstate 76", "C:\GOG Games\Interstate 76")) {
        if (Test-Path (Join-Path $c 'i76.exe')) { $GameDir = $c; break }
    }
}
if (-not $GameDir -or -not (Test-Path (Join-Path $GameDir 'music'))) {
    Write-Host "Need the game folder (with music\). Pass -GameDir." -ForegroundColor Red; exit 1
}

$built = Join-Path $here 'winmm.dll'
if (-not (Test-Path $built)) { Write-Host "Build it first: build.ps1" -ForegroundColor Red; exit 1 }

# Load a COPY under a different name, from the game folder. Different name so this
# never collides with the real winmm already loaded in this process; game folder so
# the DLL's own "music\ beside me" lookup resolves.
$testDll = Join-Path $GameDir 'i76cda-selftest.dll'
Copy-Item $built $testDll -Force
$env:I76_CDAUDIO_LOG = "1"

Add-Type @"
using System;
using System.Runtime.InteropServices;
public class ST {
  [DllImport("kernel32.dll", SetLastError=true)] public static extern IntPtr LoadLibraryA(string p);
  [DllImport("kernel32.dll")] public static extern IntPtr GetProcAddress(IntPtr h, string n);
  [DllImport("kernel32.dll")] public static extern bool FreeLibrary(IntPtr h);
  public delegate uint MciSendCommand(uint id, uint msg, uint flags, IntPtr parms);
}
"@

# --- MCI constants (mmsystem.h) ---
$MCI_OPEN=0x0803; $MCI_CLOSE=0x0804; $MCI_PLAY=0x0806; $MCI_STOP=0x0808
$MCI_SET=0x080D;  $MCI_STATUS=0x0814
$MCI_OPEN_TYPE=0x00002000; $MCI_STATUS_ITEM=0x00000100
$MCI_SET_TIME_FORMAT=0x00000400; $MCI_FROM=0x00000004
$MCI_FORMAT_TMSF=10
$ITEM_LENGTH=1; $ITEM_POSITION=2; $ITEM_NUMTRACKS=3; $ITEM_MODE=4; $ITEM_MEDIA_PRESENT=5
$MODE_STOP=525; $MODE_PLAY=526; $MODE_PAUSE=529

$pass=0; $fail=0
function Check { param([string]$n,[bool]$c,[string]$d="")
    if ($c) { $script:pass++; Write-Host "  PASS  $n" -ForegroundColor Green }
    else { $script:fail++; Write-Host ("  FAIL  $n" + $(if($d){"  ($d)"})) -ForegroundColor Red } }

$h = [ST]::LoadLibraryA($testDll)
try {
    Write-Host ("loaded {0} -> handle 0x{1:X}" -f (Split-Path -Leaf $testDll), [int64]$h) -ForegroundColor Cyan
    Check "DLL loads in a 32-bit process" ($h -ne [IntPtr]::Zero) "LoadLibrary failed: $([ComponentModel.Win32Exception]::new([Runtime.InteropServices.Marshal]::GetLastWin32Error()).Message)"
    if ($h -eq [IntPtr]::Zero) { exit 1 }

    $pAddr = [ST]::GetProcAddress($h, "mciSendCommandA")
    Check "exports mciSendCommandA" ($pAddr -ne [IntPtr]::Zero)
    if ($pAddr -eq [IntPtr]::Zero) { exit 1 }
    $mci = [Runtime.InteropServices.Marshal]::GetDelegateForFunctionPointer($pAddr, [ST+MciSendCommand])

    # ---- MCI_OPEN "cdaudio" : the call that fails with no optical drive ----
    $devType = [Runtime.InteropServices.Marshal]::StringToHGlobalAnsi("cdaudio")
    $op = [Runtime.InteropServices.Marshal]::AllocHGlobal(20)
    for ($i=0;$i -lt 20;$i+=4) { [Runtime.InteropServices.Marshal]::WriteInt32($op,$i,0) }
    [Runtime.InteropServices.Marshal]::WriteIntPtr($op, 8, $devType)   # lpstrDeviceType
    $rc = $mci.Invoke(0, $MCI_OPEN, $MCI_OPEN_TYPE, $op)
    $devId = [Runtime.InteropServices.Marshal]::ReadInt32($op, 4)
    Write-Host ("  MCI_OPEN cdaudio -> rc {0}, deviceId 0x{1:X}" -f $rc, $devId)
    Check "MCI_OPEN cdaudio SUCCEEDS (real winmm returns 266 here)" ($rc -eq 0) "rc $rc"
    Check "hands back a device id" ($devId -ne 0)
    if ($rc -ne 0) { exit 1 }

    # ---- how many tracks? ----
    $sp = [Runtime.InteropServices.Marshal]::AllocHGlobal(16)
    function Status { param([int]$item,[int]$track=0)
        for ($i=0;$i -lt 16;$i+=4) { [Runtime.InteropServices.Marshal]::WriteInt32($script:sp,$i,0) }
        [Runtime.InteropServices.Marshal]::WriteInt32($script:sp, 8, $item)
        [Runtime.InteropServices.Marshal]::WriteInt32($script:sp, 12, $track)
        $r = $script:mci.Invoke($script:devId, $script:MCI_STATUS, $script:MCI_STATUS_ITEM, $script:sp)
        return @($r, [Runtime.InteropServices.Marshal]::ReadInt32($script:sp, 4))
    }
    $n = Status $ITEM_NUMTRACKS
    Write-Host ("  tracks reported: {0}" -f $n[1])
    Check "reports a sensible track count" ($n[1] -ge 8 -and $n[1] -le 30) "got $($n[1])"
    $mp = Status $ITEM_MEDIA_PRESENT
    Check "reports media present" ($mp[1] -ne 0)

    # ---- set TMSF, play a track ----
    $setp = [Runtime.InteropServices.Marshal]::AllocHGlobal(12)
    [Runtime.InteropServices.Marshal]::WriteInt32($setp,0,0)
    [Runtime.InteropServices.Marshal]::WriteInt32($setp,4,$MCI_FORMAT_TMSF)
    [Runtime.InteropServices.Marshal]::WriteInt32($setp,8,0)
    $rcSet = $mci.Invoke($devId, $MCI_SET, $MCI_SET_TIME_FORMAT, $setp)
    Check "accepts MCI_SET time format TMSF" ($rcSet -eq 0) "rc $rcSet"

    $pp = [Runtime.InteropServices.Marshal]::AllocHGlobal(12)
    [Runtime.InteropServices.Marshal]::WriteInt32($pp,0,0)
    [Runtime.InteropServices.Marshal]::WriteInt32($pp,4,$Track)   # TMSF: track in low byte
    [Runtime.InteropServices.Marshal]::WriteInt32($pp,8,0)
    $rcPlay = $mci.Invoke($devId, $MCI_PLAY, $MCI_FROM, $pp)
    Write-Host ("  MCI_PLAY track $Track -> rc {0}" -f $rcPlay)
    Check "MCI_PLAY accepted" ($rcPlay -eq 0) "rc $rcPlay"

    Start-Sleep -Milliseconds 1200
    $m = Status $ITEM_MODE
    Write-Host ("  mode: {0} ({1})" -f $m[1], $(switch($m[1]){525{'stopped'}526{'playing'}529{'paused'}default{'?'}}))
    Check "reports itself PLAYING" ($m[1] -eq $MODE_PLAY) "mode $($m[1])"

    $p1 = (Status $ITEM_POSITION)[1]
    Start-Sleep -Seconds ([Math]::Max(2,$Seconds))
    $p2 = (Status $ITEM_POSITION)[1]
    Check "position advances while playing" ($p2 -ne $p1) "p1=$p1 p2=$p2"
    Write-Host ("  (you should have heard track $Track for ~$Seconds s)") -ForegroundColor Cyan

    $lenAll = (Status $ITEM_LENGTH)[1]
    Check "reports a disc length" ($lenAll -ne 0) "got $lenAll"

    $rcStop = $mci.Invoke($devId, $MCI_STOP, 0, [IntPtr]::Zero)
    Check "MCI_STOP accepted" ($rcStop -eq 0) "rc $rcStop"
    Start-Sleep -Milliseconds 400
    $m2 = Status $ITEM_MODE
    Check "reports STOPPED after stop" ($m2[1] -ne $MODE_PLAY) "mode $($m2[1])"

    $rcClose = $mci.Invoke($devId, $MCI_CLOSE, 0, [IntPtr]::Zero)
    Check "MCI_CLOSE accepted" ($rcClose -eq 0) "rc $rcClose"
}
finally {
    if ($h -ne [IntPtr]::Zero) { [void][ST]::FreeLibrary($h) }
    Remove-Item $testDll -Force -ErrorAction SilentlyContinue
    $log = Join-Path $GameDir 'winmm-cdaudio.log'
    if (Test-Path $log) {
        Write-Host ""
        Write-Host "--- proxy log ---" -ForegroundColor DarkGray
        Get-Content $log -Tail 30 | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkGray }
    } else {
        Write-Host ""
        Write-Host "NO LOG WRITTEN - the proxy's DllMain did not run, or logging was off." -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host ("=== {0} passed, {1} failed ===" -f $pass, $fail) `
    -ForegroundColor $(if ($fail -eq 0) { 'Green' } else { 'Red' })
if ($fail -gt 0) { exit 1 }
