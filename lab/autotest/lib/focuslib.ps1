<#
  focuslib.ps1 — dot-source this for a robust Force-Foreground + live-capture check.

  Two hard facts learned the slow way:
   * I'76 renders via dgVoodoo/Glide; the desktop only has a LIVE image of its window while
     the game is the FOREGROUND window. Unfocused, GDI CopyFromScreen returns a stale frame,
     so every screenshot comes back byte-identical. => must truly focus the game to test.
   * A background process's plain SetForegroundWindow is denied by Windows' foreground lock.
     Force-Foreground defeats it via AttachThreadInput + SPI_SETFOREGROUNDLOCKTIMEOUT=0 +
     an ALT tap (the documented unlock trick).
#>
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Fg {
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("kernel32.dll")] public static extern uint GetCurrentThreadId();
  [DllImport("user32.dll")] public static extern bool AttachThreadInput(uint idAttach, uint idAttachTo, bool fAttach);
  [DllImport("user32.dll")] public static extern bool SystemParametersInfo(uint a, uint b, IntPtr c, uint d);
  [DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint flags, IntPtr extra);
  [DllImport("user32.dll")] public static extern IntPtr SendMessageTimeout(IntPtr h, uint msg, IntPtr w, IntPtr l, uint flags, uint ms, out UIntPtr res);
}
"@
<#
  Is the window pumping messages? ShowWindow / BringWindowToTop / SetForegroundWindow /
  AttachThreadInput all block on a window whose thread is not pumping, with NO timeout - that
  is a hang, not an error.

  GOTCHA (cost a 120 s harness timeout): I'76's 2D shell throws its own MODAL dialogs
  ("RENAME VARIANT TO SAVE") and sits in a modal sub-loop where the main window stops
  responding. Force-Foreground hung there and the clicks it was supposed to make never fired -
  so the dialog looked unclickable when in fact nothing had clicked it.
#>
function Test-WindowPumping([IntPtr]$hwnd, [int]$timeoutMs = 600) {
    $res = [UIntPtr]::Zero
    $r = [Fg]::SendMessageTimeout($hwnd, 0, [IntPtr]::Zero, [IntPtr]::Zero, 2, $timeoutMs, [ref]$res)  # WM_NULL, SMTO_ABORTIFHUNG
    return ($r -ne [IntPtr]::Zero)
}
function Force-Foreground([IntPtr]$hwnd) {
    # already foreground: do nothing. The dance is what hangs, and it is usually unnecessary.
    if ([Fg]::GetForegroundWindow() -eq $hwnd) { return $true }
    # never run the blocking calls against a window that is not pumping
    if (-not (Test-WindowPumping $hwnd)) {
        Write-Warning "game window is not pumping (modal dialog?) - skipping focus calls. Click it directly; SetCursorPos + mouse_event still work."
        return $false
    }
    [void][Fg]::SystemParametersInfo(0x2001, 0, [IntPtr]::Zero, 0)   # SPI_SETFOREGROUNDLOCKTIMEOUT = 0
    [void][Fg]::ShowWindow($hwnd, 9)                                  # SW_RESTORE
    [void][Fg]::keybd_event(0x12, 0, 0, [IntPtr]::Zero)              # ALT down (unlock trick)
    [void][Fg]::keybd_event(0x12, 0, 2, [IntPtr]::Zero)              # ALT up
    $fg = [Fg]::GetForegroundWindow()
    $tidFg = [Fg]::GetWindowThreadProcessId($fg, [ref]([uint32]0))
    $me = [Fg]::GetCurrentThreadId()
    [void][Fg]::AttachThreadInput($me, $tidFg, $true)
    [void][Fg]::BringWindowToTop($hwnd)
    [void][Fg]::SetForegroundWindow($hwnd)
    [void][Fg]::AttachThreadInput($me, $tidFg, $false)
    Start-Sleep -Milliseconds 500
    return ([Fg]::GetForegroundWindow() -eq $hwnd)
}
function Get-GamePid([string]$RequirePath = 'i76-uncap-lab') {
    $cands = @(Get-Process i76, nitro -ErrorAction SilentlyContinue | Where-Object { $_.Path -and $_.Path -like "*$RequirePath*" })
    # several game folders in the lab (game, game-alt, game-dd-*): a caller that set $I76GameDirInUse (lib\gamedir.ps1)
    # gets the process running from THAT folder when there is one. Not set = the first match, as before.
    if ($I76GameDirInUse -and $cands.Count -gt 0) {
        $want = "$I76GameDirInUse".TrimEnd('\') + '\'
        $mine = @($cands | Where-Object { $_.Path.StartsWith($want, [StringComparison]::OrdinalIgnoreCase) })
        if ($mine.Count -gt 0) { return $mine[0] }
    }
    $cands | Select-Object -First 1
}

# Ensure the game window IS foreground before sending input - keystrokes go to the focused
# window, and a silent focus loss makes every synthetic key vanish into the desktop. That
# failure mode masqueraded as "the throttle does nothing at 60fps" for two sessions
# (2026-08-30: black unfocused game window, taps going to the wallpaper).
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class FgQ { [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow(); }
"@ -ErrorAction SilentlyContinue
function Ensure-GameFocus {
    param($Proc)
    for ($fi = 0; $fi -lt 5; $fi++) {
        if ([FgQ]::GetForegroundWindow() -eq $Proc.MainWindowHandle) { return $true }
        Force-Foreground $Proc.MainWindowHandle | Out-Null
        Start-Sleep -Milliseconds 250
    }
    return ([FgQ]::GetForegroundWindow() -eq $Proc.MainWindowHandle)
}
