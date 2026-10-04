<#
  uiclick.ps1 - click the shell UI reliably in EITHER mouse regime. Dot-source it.

  Since the u32x proxy became regime-aware (docs/SAVE-FREEZE-ROOT-CAUSE.md), automation has to
  match whichever regime dgVoodoo is in, and it varies between launches:
    CONFINED - dgVoodoo pins the pointer in a UI-sized box and maps it; set the cursor in UI
               coordinates (0..639 / 0..479) exactly as the old scripts did.
    FREE     - windowed mode, or the clip was released; the app receives raw SCREEN coordinates
               and the proxy translates them, so we must place the cursor where the widget
               VISUALLY is: screen = origin + ui * scale.
  Geometry is measured from the live window every call - never hardcode 3.0/760, that is only
  true for one fullscreen size and silently misses in windowed mode.
#>
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class UiClk {
  public delegate bool EP(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EP cb, IntPtr l);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr h, ref POINT p);
  [DllImport("user32.dll")] public static extern bool GetClipCursor(out RECT r);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x,int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint f,uint x,uint y,uint d,IntPtr e);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int left,top,right,bottom; }
  [StructLayout(LayoutKind.Sequential)] public struct POINT { public int x,y; }
}
"@ -ErrorAction SilentlyContinue

function Get-UiMap {
    $proc = Get-Process i76 -EA SilentlyContinue | Select-Object -First 1
    if (-not $proc) { throw "game not running" }
    $tid = $proc.Id
    $script:UiHwnd = [IntPtr]::Zero
    $cb = [UiClk+EP]{
        param($h,$l)
        $pp = 0; [void][UiClk]::GetWindowThreadProcessId($h,[ref]$pp)
        if ($pp -eq $tid -and [UiClk]::IsWindowVisible($h)) {
            $cr = New-Object UiClk+RECT; [void][UiClk]::GetClientRect($h,[ref]$cr)
            if ($cr.right -ge 64 -and $cr.bottom -ge 64) { $script:UiHwnd = $h; return $false }
        }
        return $true
    }
    [void][UiClk]::EnumWindows($cb,[IntPtr]::Zero)
    if ($script:UiHwnd -eq [IntPtr]::Zero) { throw "game window not found" }
    $cr = New-Object UiClk+RECT; [void][UiClk]::GetClientRect($script:UiHwnd,[ref]$cr)
    $org = New-Object UiClk+POINT; [void][UiClk]::ClientToScreen($script:UiHwnd,[ref]$org)
    $clip = New-Object UiClk+RECT; [void][UiClk]::GetClipCursor([ref]$clip)
    $scale = [Math]::Min($cr.right/640.0, $cr.bottom/480.0)
    [pscustomobject]@{
        Confined = ((($clip.right-$clip.left) -le 704) -and (($clip.bottom-$clip.top) -le 544))
        Scale    = $scale
        Sx       = $org.x + [int](($cr.right  - 640*$scale)/2)
        Sy       = $org.y + [int](($cr.bottom - 480*$scale)/2)
        Client   = "$($cr.right)x$($cr.bottom)"
    }
}

function Click-Ui {
    param([int]$Ux, [int]$Uy, [int]$SettleMs = 900)
    $m = Get-UiMap
    if ($m.Confined) { $X = $Ux; $Y = $Uy }
    else             { $X = [int]($m.Sx + $Ux * $m.Scale); $Y = [int]($m.Sy + $Uy * $m.Scale) }
    [void][UiClk]::SetCursorPos($X,$Y); Start-Sleep -Milliseconds 300
    [UiClk]::mouse_event(0x2,0,0,0,[IntPtr]::Zero); Start-Sleep -Milliseconds 70
    [UiClk]::mouse_event(0x4,0,0,0,[IntPtr]::Zero); Start-Sleep -Milliseconds $SettleMs
}
