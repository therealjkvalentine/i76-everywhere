<#
  inputlib.ps1 — dot-source for keystroke/click injection into the focused game.

  Uses keybd_event / mouse_event (hardware-level) rather than SendKeys, because I'76 reads
  input via DirectInput/GetAsyncKeyState which ignores posted WM_KEY messages. Send-Key uses
  scan codes (the reliable path for DirectInput games). The game must be foreground first
  (see focuslib.ps1 Force-Foreground).
#>
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Inp {
  [DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint flags, IntPtr extra);
  [DllImport("user32.dll")] public static extern uint MapVirtualKey(uint code, uint type);
  [DllImport("user32.dll")] public static extern void mouse_event(uint flags, int dx, int dy, uint data, IntPtr extra);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
}
"@
function Mouse-MoveRel([int]$dx, [int]$dy) { [Inp]::mouse_event(0x1, $dx, $dy, 0, [IntPtr]::Zero) }  # MOUSEEVENTF_MOVE (DirectInput relative)
$KEYEVENTF_KEYUP     = 0x2
$KEYEVENTF_SCANCODE  = 0x8
function Send-Key([byte]$vk, [int]$holdMs = 40) {
    $scan = [Inp]::MapVirtualKey($vk, 0)
    [Inp]::keybd_event($vk, $scan, $KEYEVENTF_SCANCODE, [IntPtr]::Zero)             # down (scancode)
    Start-Sleep -Milliseconds $holdMs
    [Inp]::keybd_event($vk, $scan, ($KEYEVENTF_SCANCODE -bor $KEYEVENTF_KEYUP), [IntPtr]::Zero)  # up
}
function Hold-Key([byte]$vk, [int]$ms) {
    # press-and-hold for driving: repeatedly assert down for the duration, then release
    $scan = [Inp]::MapVirtualKey($vk, 0)
    $sw = [Diagnostics.Stopwatch]::StartNew()
    while ($sw.Elapsed.TotalMilliseconds -lt $ms) {
        [Inp]::keybd_event($vk, $scan, $KEYEVENTF_SCANCODE, [IntPtr]::Zero)
        Start-Sleep -Milliseconds 15
    }
    [Inp]::keybd_event($vk, $scan, ($KEYEVENTF_SCANCODE -bor $KEYEVENTF_KEYUP), [IntPtr]::Zero)
}
# Non-blocking press/release. Hold-Key blocks for its whole duration, which is useless when you
# need to hold throttle AND steer while sampling memory in between. Writing the engine's input
# block directly does not work - it is refilled from the keyboard every frame - so held keys are
# the only way to give a control input that is identical at any frame rate.
function Key-Down([byte]$vk) {
    [Inp]::keybd_event($vk, [Inp]::MapVirtualKey($vk, 0), $KEYEVENTF_SCANCODE, [IntPtr]::Zero)
}
function Key-Up([byte]$vk) {
    [Inp]::keybd_event($vk, [Inp]::MapVirtualKey($vk, 0), ($KEYEVENTF_SCANCODE -bor $KEYEVENTF_KEYUP), [IntPtr]::Zero)
}
function Click([int]$x, [int]$y) {
    [void][Inp]::SetCursorPos($x, $y); Start-Sleep -Milliseconds 60
    [Inp]::mouse_event(0x2, 0, 0, 0, [IntPtr]::Zero)   # left down
    Start-Sleep -Milliseconds 50
    [Inp]::mouse_event(0x4, 0, 0, 0, [IntPtr]::Zero)   # left up
}
# common virtual-key codes
$VK = @{ ESC=0x1B; ENTER=0x0D; SPACE=0x20; UP=0x26; DOWN=0x28; LEFT=0x25; RIGHT=0x27;
         W=0x57; A=0x41; S=0x53; D=0x44; N=0x4E; T=0x54; Y=0x59; F1=0x70; F10=0x79 }
