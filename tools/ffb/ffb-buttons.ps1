<#
  ffb-buttons.ps1 - watch the wheel's buttons and axes live, through winmm.

  WHY winmm AND NOT DirectInput: winmm is the path the 1997 engine actually
  reads (joyGetPosEx). A button that works in the Thrustmaster control panel or
  in a DirectInput test tool can still be invisible to the game, so the only
  numbering that matters is this one. `Button3` in input.map means winmm button
  index 3 as shown here.

      tools\ffb\ffb-buttons.ps1              # watch device 1 (joystick1)
      tools\ffb\ffb-buttons.ps1 -Device 2    # joystick2
      tools\ffb\ffb-buttons.ps1 -Learn       # press buttons; prints a ready-made
                                             # input.map block naming each one

  ---------------------------------------------------------------------------
  THE FAILURE THIS EXISTS FOR
  ---------------------------------------------------------------------------
  "Steering works, pedals work, force feedback works, no button does anything."
  That is NOT a device fault - and this tool proves it in five seconds. If
  presses light up here, the wheel and the driver are fine and the problem is
  in input.map, which the in-game controls menu rewrites and silently strips of
  joystick BUTTON blocks while leaving the two analog lines intact.

      grep -i joystick input.map

  If the only hits are the two axis lines, the button tier has been eaten. See
  the restore block at the bottom of input.map.
#>
param(
    [int]$Device = 1,
    [switch]$Learn,
    [int]$Seconds = 0
)
$ErrorActionPreference = 'Stop'

if (-not ('WinMM' -as [type])) {
Add-Type @"
using System;
using System.Runtime.InteropServices;
[StructLayout(LayoutKind.Sequential)] public struct JOYINFOEX {
  public uint dwSize, dwFlags, dwXpos, dwYpos, dwZpos, dwRpos, dwUpos, dwVpos;
  public uint dwButtons, dwButtonNumber, dwPOV, dwReserved1, dwReserved2;
}
[StructLayout(LayoutKind.Sequential)] public struct JOYCAPS {
  public ushort wMid, wPid;
  [MarshalAs(UnmanagedType.ByValTStr, SizeConst=32)] public string szPname;
  public uint wXmin,wXmax,wYmin,wYmax,wZmin,wZmax,wNumButtons,wPeriodMin,wPeriodMax,
         wRmin,wRmax,wUmin,wUmax,wVmin,wVmax,wCaps,wMaxAxes,wNumAxes,wMaxButtons;
  [MarshalAs(UnmanagedType.ByValTStr, SizeConst=32)] public string szRegKey;
  [MarshalAs(UnmanagedType.ByValTStr, SizeConst=260)] public string szOEMVxD;
}
public class WinMM {
  [DllImport("winmm.dll")] public static extern uint joyGetPosEx(int id, ref JOYINFOEX pji);
  [DllImport("winmm.dll")] public static extern uint joyGetDevCapsA(int id, ref JOYCAPS c, int sz);
}
"@
}

# winmm ids are 0-based; input.map's joystick1 is id 0.
$id = $Device - 1
$caps = New-Object JOYCAPS
$sz = [Runtime.InteropServices.Marshal]::SizeOf($caps)
if ([WinMM]::joyGetDevCapsA($id, [ref]$caps, $sz) -ne 0) {
    Write-Host "joystick$Device is not present at the winmm layer." -ForegroundColor Red
    Write-Host "The game reads THIS layer, so if the wheel is missing here the game" -ForegroundColor Yellow
    Write-Host "cannot see it either - regardless of what the vendor panel shows." -ForegroundColor Yellow
    exit 1
}
Write-Host ("joystick{0}: {1}" -f $Device, $caps.szPname) -ForegroundColor Green
Write-Host ("  {0} buttons, {1} axes   (input.map device token: joystick{2})" -f `
    $caps.wNumButtons, $caps.wNumAxes, $Device) -ForegroundColor DarkGray
Write-Host ""

function Read-Joy {
    $j = New-Object JOYINFOEX
    $j.dwSize = [Runtime.InteropServices.Marshal]::SizeOf($j)
    $j.dwFlags = 0xFF                     # JOY_RETURNALL
    if ([WinMM]::joyGetPosEx($id, [ref]$j) -ne 0) { return $null }
    return $j
}

$nb = [int]$caps.wNumButtons
$order = New-Object System.Collections.ArrayList
$prev = 0

if ($Learn) {
    Write-Host "LEARN MODE - press each button you want bound, in this order:" -ForegroundColor Yellow
    Write-Host "  1. FIRE   2. NITROUS/special   3. WEAPON CYCLE   4. HANDBRAKE" -ForegroundColor Yellow
    Write-Host "  (any extras after that are just listed)   Ctrl+C when done." -ForegroundColor Yellow
} else {
    Write-Host "Press buttons and turn the wheel. Ctrl+C to stop." -ForegroundColor Yellow
}
Write-Host ""

$sw = [System.Diagnostics.Stopwatch]::StartNew()
$canDraw = $true
try { [Console]::SetCursorPosition([Console]::CursorLeft, [Console]::CursorTop) } catch { $canDraw = $false }
$baseRow = if ($canDraw) { [Console]::CursorTop } else { 0 }

while ($true) {
    if ($Seconds -gt 0 -and $sw.Elapsed.TotalSeconds -gt $Seconds) { break }
    $j = Read-Joy
    if ($j) {
        # rising edges, so a held button is recorded once
        $newly = $j.dwButtons -band (-bnot $prev)
        for ($b = 0; $b -lt $nb; $b++) {
            if ($newly -band (1 -shl $b)) {
                $n = $b + 1
                if (-not $order.Contains($n)) { $null = $order.Add($n) }
                if (-not $canDraw) { Write-Host ("  Button{0} pressed" -f $n) -ForegroundColor Green }
            }
        }
        $prev = $j.dwButtons

        if ($canDraw) {
            [Console]::SetCursorPosition(0, $baseRow)
            $line = "  buttons: "
            for ($b = 0; $b -lt $nb; $b++) {
                $on = ($j.dwButtons -band (1 -shl $b)) -ne 0
                $line += if ($on) { "[{0,2}]" -f ($b + 1) } else { " {0,2} " -f ($b + 1) }
            }
            Write-Host $line.PadRight(100)
            Write-Host ("  axes: X {0,5}  Y {1,5}  Z {2,5}  R {3,5}  U {4,5}  V {5,5}   POV {6}" -f `
                $j.dwXpos, $j.dwYpos, $j.dwZpos, $j.dwRpos, $j.dwUpos, $j.dwVpos, $j.dwPOV).PadRight(100)
            Write-Host ("  pressed so far, in order: {0}" -f `
                $(if ($order.Count) { ($order | ForEach-Object { "Button$_" }) -join ' ' } else { "(none yet)" })).PadRight(100)
        }
    }
    Start-Sleep -Milliseconds 25
}

# ---- emit a ready-made input.map block ------------------------------------
if ($order.Count) {
    $acts = @('weapon_fire','special1','weapon_cycle','e_brake')
    Write-Host ""
    Write-Host "=== paste into input.map (replaces the wheel button tier) ===" -ForegroundColor Green
    Write-Host ""
    for ($i = 0; $i -lt [math]::Min($acts.Count, $order.Count); $i++) {
        Write-Host ("{0} {{" -f $acts[$i])
        Write-Host ("   + joystick{0}  Button{1}" -f $Device, $order[$i])
        Write-Host "}"
    }
    if ($order.Count -gt $acts.Count) {
        Write-Host ""
        Write-Host ("  also pressed: {0}" -f `
            (($order | Select-Object -Skip $acts.Count | ForEach-Object { "Button$_" }) -join ' ')) -ForegroundColor DarkGray
        Write-Host "  bind those to any action name that exists in the exe - verify with" -ForegroundColor DarkGray
        Write-Host "  tools\lint-input-map.py before launching." -ForegroundColor DarkGray
    }
}
