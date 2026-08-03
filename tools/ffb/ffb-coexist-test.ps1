<#
  ffb-coexist-test.ps1 - can our FFB layer and the game hold the wheel at once?

  This decides the whole shape of the interposer, so it is measured rather than
  reasoned about.

  THE QUESTION
  Force feedback needs an EXCLUSIVE DirectInput acquisition. The game takes one
  at startup. On the face of it that means you get the engine's authored weapon
  effects OR our synthesised feel, never both, and getting ours requires patching
  out the game's FFB init (a NOP at 0x402F93).

  But exclusivity interacts with FOCUS. DirectInput auto-unacquires a device held
  at DISCL_FOREGROUND when its owner loses foreground, and I'76 acquires ONCE at
  startup and never retries (docs/FFB-LAPTOP-RECON.md: "try again next time" is a
  give-up, not a retry). If that is right then the engine's FFB is already gone
  the first time you alt-tab, and we can take the wheel with no patch at all.

  WHAT THIS DOES
  Reads the engine's own FFB state, acquires the wheel, forces the game window to
  the foreground, and re-checks - so the answer covers the case that actually
  matters (the game focused, as when you are playing) rather than only the easy
  case (the game in the background, as when you are reading this).

  Applies a small force (default 1200 of 10000) briefly. Nothing is patched.

      tools\ffb\ffb-coexist-test.ps1
      tools\ffb\ffb-coexist-test.ps1 -Force 0     # measure only, no force at all
#>
param(
    [int]$Force = 1200,
    [int]$HoldSeconds = 4
)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $here 'FfbCore.ps1')

if (-not ('CoTest' -as [type])) {
    Add-Type @"
using System;
using System.Runtime.InteropServices;
public class CoTest {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(uint a, bool i, int p);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr a, byte[] b, int s, out int r);
  [DllImport("user32.dll")]   public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")]   public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")]   public static extern bool ShowWindow(IntPtr h, int cmd);
  [DllImport("user32.dll")]   public static extern int GetWindowTextA(IntPtr h, System.Text.StringBuilder s, int n);
}
"@
}

$proc = Get-Process i76, nitro -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $proc) { Write-Host "The game is not running - nothing to test against." -ForegroundColor Red; exit 1 }
$hProc = [CoTest]::OpenProcess(0x38, $false, $proc.Id)

function GameFfbState {
    # 0x52bbd0 = FF-device-detected flag, 0x52bbcc = effect object pointer.
    # Both from docs/FFB-LAPTOP-RECON.md; meaningful only in a mission.
    $b = New-Object byte[] 4; $n = 0
    [void][CoTest]::ReadProcessMemory($hProc, [IntPtr]0x52bbd0, $b, 4, [ref]$n)
    $flag = [BitConverter]::ToInt32($b, 0)
    [void][CoTest]::ReadProcessMemory($hProc, [IntPtr]0x52bbcc, $b, 4, [ref]$n)
    $obj = [BitConverter]::ToInt32($b, 0)
    return [pscustomobject]@{ Flag = $flag; Obj = $obj }
}

function ForegroundTitle {
    $h = [CoTest]::GetForegroundWindow()
    $sb = New-Object System.Text.StringBuilder 256
    [void][CoTest]::GetWindowTextA($h, $sb, 256)
    return "$($sb.ToString()) [hwnd 0x$('{0:X}' -f [int64]$h)]"
}

Write-Host "=== BEFORE we touch anything ===" -ForegroundColor Cyan
$s0 = GameFfbState
Write-Host ("  engine FF flag      : {0}" -f $s0.Flag)
Write-Host ("  engine effect object: 0x{0:X8}" -f $s0.Obj)
Write-Host ("  foreground window   : {0}" -f (ForegroundTitle))
Write-Host ("  game window         : 0x{0:X}" -f [int64]$proc.MainWindowHandle)

Write-Host "`n=== acquiring the wheel (game in its current focus state) ===" -ForegroundColor Cyan
$dev = $null
try {
    $dev = Ffb-Open
    Write-Host ("  ACQUIRED: {0}" -f $dev.Name) -ForegroundColor Green
} catch {
    Write-Host "  ACQUIRE FAILED: $_" -ForegroundColor Red
    Write-Host "  -> the game holds the device even unfocused; the NOP patch route is required." -ForegroundColor Yellow
    exit 2
}

$hr = Ffb-Constant $dev $Force
Write-Host ("  SetParameters hr    : 0x{0:X8}  {1}" -f $hr, $(if ($hr -ge 0) { "OK" } else { "FAILED" }))

Write-Host "`n=== forcing the GAME to the foreground (the case that matters) ===" -ForegroundColor Cyan
[void][CoTest]::ShowWindow($proc.MainWindowHandle, 9)      # SW_RESTORE
[void][CoTest]::SetForegroundWindow($proc.MainWindowHandle)
Start-Sleep -Milliseconds 900
$fg = ForegroundTitle
Write-Host ("  foreground window   : {0}" -f $fg)
$reallyFocused = ([int64][CoTest]::GetForegroundWindow() -eq [int64]$proc.MainWindowHandle)
if (-not $reallyFocused) {
    Write-Host "  NOTE: focus did NOT actually move to the game (Windows blocks" -ForegroundColor Yellow
    Write-Host "  SetForegroundWindow from a background process). The result below is" -ForegroundColor Yellow
    Write-Host "  therefore NOT a test of the focused case - click the game and re-run." -ForegroundColor Yellow
}

$results = @()
for ($i = 0; $i -lt $HoldSeconds; $i++) {
    Start-Sleep -Seconds 1
    $h = Ffb-Constant $dev $Force
    $results += $h
    Write-Host ("  t+{0}s  hr 0x{1:X8}  {2}" -f ($i + 1), $h, $(if ($h -ge 0) { "still ours" } else { "LOST" }))
}

$s1 = GameFfbState
Write-Host "`n=== AFTER ===" -ForegroundColor Cyan
Write-Host ("  engine FF flag      : {0} -> {1}" -f $s0.Flag, $s1.Flag)
Write-Host ("  engine effect object: 0x{0:X8} -> 0x{1:X8}" -f $s0.Obj, $s1.Obj)

try { $null = Ffb-Constant $dev 0 } catch { }   # $null = : it returns an HRESULT now
try { Ffb-Close $dev } catch { }
Write-Host "  wheel released." -ForegroundColor Cyan

$kept = ($results | Where-Object { $_ -ge 0 }).Count
Write-Host "`n=== VERDICT ===" -ForegroundColor Green
if ($kept -eq $results.Count -and $reallyFocused) {
    Write-Host "  We held the wheel for the whole window WITH THE GAME FOCUSED." -ForegroundColor Green
    Write-Host "  Coexistence works: no patch needed. The engine's own FFB is" -ForegroundColor Green
    Write-Host "  whatever the flag above says - if it went to 0, its effects are" -ForegroundColor Green
    Write-Host "  gone for this session, which is the price and it is paid once." -ForegroundColor Green
} elseif ($kept -eq $results.Count) {
    Write-Host "  We held the wheel, but focus never actually moved to the game," -ForegroundColor Yellow
    Write-Host "  so this does NOT yet answer the focused case. Click the game" -ForegroundColor Yellow
    Write-Host "  window and run this again to settle it." -ForegroundColor Yellow
} else {
    Write-Host "  We LOST the device ($kept of $($results.Count) writes succeeded)." -ForegroundColor Red
    Write-Host "  The game reclaims it, so the interposer needs either the NOP" -ForegroundColor Red
    Write-Host "  patch at 0x402F93 or the reacquire loop in ffb-interposer.ps1." -ForegroundColor Red
}
