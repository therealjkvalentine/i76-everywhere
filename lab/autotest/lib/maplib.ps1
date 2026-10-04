<#
  maplib.ps1 — the game's menu cursor, solved rather than fitted.

  ============================================================================
  THE MODEL (measured, and every constant below is derived - nothing hand-tuned)
  ============================================================================

  1. The 1997 engine hit-tests the mouse as raw **640x480** coordinates, and dgVoodoo passes
     the OS cursor through unscaled. So:

         the OS cursor position IS the engine's 640x480 UI coordinate, 1:1.

     SetCursorPos(x, y) puts the game's cursor on UI point (x, y). That is the whole trick;
     the screen position it happens to appear at is only needed for *reading* screenshots.

  2. dgVoodoo renders at [Glide] Resolution (1680x1050 = 16:10) and letterboxes that frame
     into the window preserving aspect -> on a 3440x1440 screen the frame occupies
     2304x1440 at left 568.

  3. The game's UI is 4:3 and is **pillarboxed inside** that 16:10 frame. Measured in UI units
     (480 = frame height) the frame is 768 wide, so the UI sits at units 64..704:

         unit      u  = content_h / 480                 = 3.0
         frame_w_u    = content_w / u                   = 768
         pillarbox    = (frame_w_u - 640) / 2           = 64
         ui_left_px   = content_left + pillarbox * u    = 760

         screen_x = ui_left_px + ux * u      screen_y = content_top + uy * u

  Verified: OS(159,295) lands on the AI DRIVERS [-] button, which sits at screen x~1240 -
  760 + 159*3 = 1237. It decrements the counter. Cursor position is also ABSOLUTE (same OS
  position always draws in the same place regardless of approach) - see cursor-absolute-test.ps1.

  HISTORY / WHY THIS FILE IS EMPHATIC: two earlier calibrations were two-point empirical fits
  (`screen = 3.98*OS + 393`, later `3.6*OS + 568`). Both drifted across the form and missed
  small controls. The slope was wrong because the measurement downscaled a 16:10 capture into a
  4:3 bitmap, squeezing x by 5/6 and hiding the true 1:1. If you find yourself re-fitting
  constants here, suspect your capture's aspect ratio first.
#>

if (-not ('WinRect' -as [type])) {
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class WinRect {
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
  [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X, Y; }
  [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr h, ref POINT p);
}
"@
}

$script:UI_LEFT = 760.0   # screen px of UI x=0
$script:UI_TOP  = 0.0     # screen px of UI y=0
$script:UI_U    = 3.0     # screen px per UI unit (y, and x when aspect is preserved)
$script:UI_UX   = 3.0     # screen px per UI unit in x (differs only if ScalingMode=stretched)

function Init-CursorMap {
    <# Recompute from the real screen size + dgVoodoo's render resolution. Safe to re-call. #>
    # the conf of the caller's -GameDir when it set $I76GameDirInUse (lib\gamedir.ps1); otherwise the sandbox's
    param([string]$ConfPath = $(if ($I76GameDirInUse) { Join-Path "$I76GameDirInUse" "dgVoodoo.conf" } else { "$PSScriptRoot\..\..\game\dgVoodoo.conf" }))
    Add-Type -AssemblyName System.Windows.Forms
    $vs = [Windows.Forms.SystemInformation]::VirtualScreen
    $rw = 1680.0; $rh = 1050.0; $mode = 'stretched_ar'
    if (Test-Path $ConfPath) {
        $m = Select-String -Path $ConfPath -Pattern '^\s*Resolution\s*=\s*(\d+)\s*x\s*(\d+)' | Select-Object -First 1
        if ($m) { $rw = [double]$m.Matches[0].Groups[1].Value; $rh = [double]$m.Matches[0].Groups[2].Value }
        $s = Select-String -Path $ConfPath -Pattern '^\s*ScalingMode\s*=\s*(\S+)' | Select-Object -First 1
        if ($s) { $mode = $s.Matches[0].Groups[1].Value.ToLower() }
    }
    # Prefer the game window's ACTUAL client rect. Deriving it from the screen size only works
    # for a full-height borderless window; a small windowed mode (e.g. 640x480) is not centred
    # over the whole desktop the same way, and assuming so silently offsets every click.
    $winW = $null
    $gps = @(Get-Process i76, nitro -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 })
    $gp = $gps | Select-Object -First 1
    if ($I76GameDirInUse -and $gps.Count -gt 1) {      # several games: the one running from the caller's -GameDir
        $want = "$I76GameDirInUse".TrimEnd('\') + '\'
        $mine = @($gps | Where-Object { $_.Path -and $_.Path.StartsWith($want, [StringComparison]::OrdinalIgnoreCase) })
        if ($mine.Count -gt 0) { $gp = $mine[0] }
    }
    if ($gp) {
        $rc = New-Object WinRect+RECT
        if ([WinRect]::GetClientRect($gp.MainWindowHandle, [ref]$rc)) {
            $pt = New-Object WinRect+POINT
            [void][WinRect]::ClientToScreen($gp.MainWindowHandle, [ref]$pt)
            if ($rc.R -gt 0 -and $rc.B -gt 0) {
                $winW = [double]$rc.R; $winH = [double]$rc.B
                $winX = [double]$pt.X; $winY = [double]$pt.Y
            }
        }
    }
    if ($winW) {
        # aspect-fit the render frame inside the real client area
        $ch = $winH; $cw = $ch * ($rw / $rh)
        if ($cw -gt $winW) { $cw = $winW; $ch = $cw * ($rh / $rw) }
        $cl = $winX + ($winW - $cw) / 2.0; $ct = $winY + ($winH - $ch) / 2.0
    } else {
        # fallback: assume a full-height window centred on the desktop
        $ch = [double]$vs.Height; $cw = $ch * ($rw / $rh)
        if ($cw -gt $vs.Width) { $cw = [double]$vs.Width; $ch = $cw * ($rh / $rw) }
        $cl = ($vs.Width - $cw) / 2.0; $ct = ($vs.Height - $ch) / 2.0
    }
    # ScalingMode decides how the app's 4:3 640x480 sits inside that frame.
    # *_ar preserves the APPLICATION's aspect -> the UI is PILLARBOXED (dgVoodoo's own
    # ReadmeGeneral, and this repo's dgVoodoo.conf, both say so). Plain 'stretched' fills the
    # frame instead, which makes the x and y unit sizes differ.
    if ($mode -like '*_ar' -or $mode -eq 'centered' -or $mode -eq 'unspecified') {
        $u = $ch / 480.0
        $pillarUnits = (($cw / $u) - 640.0) / 2.0
        $script:UI_U = $u; $script:UI_UX = $u
        $script:UI_LEFT = $cl + $pillarUnits * $u
    } else {
        $u = $ch / 480.0; $pillarUnits = 0.0
        $script:UI_U = $u; $script:UI_UX = $cw / 640.0
        $script:UI_LEFT = $cl
    }
    $script:UI_TOP = $ct
    $script:FR_L = $cl; $script:FR_T = $ct; $script:FR_W = $cw; $script:FR_H = $ch
    return [pscustomobject]@{
        Screen = "$($vs.Width)x$($vs.Height)"; Render = "${rw}x${rh}"; ScalingMode = $mode
        FrameLeft = $cl; FrameW = $cw; FrameH = $ch
        PillarboxUnits = $pillarUnits
        UiLeft = $script:UI_LEFT; UiTop = $script:UI_TOP; UnitPx = $u; UnitPxX = $script:UI_UX
    }
}

# --- the only two conversions you need -------------------------------------------------
# UI/OS coordinate (640x480) -> where it is drawn on screen
function UI-ToScreen([double]$ux, [double]$uy) {
    return ,@([int][math]::Round($script:UI_LEFT + $ux * $script:UI_UX),
              [int][math]::Round($script:UI_TOP  + $uy * $script:UI_U))
}
# screen pixel -> the UI/OS coordinate that reaches it
function Screen-ToUI([double]$sx, [double]$sy) {
    return ,@([int][math]::Round(($sx - $script:UI_LEFT) / $script:UI_UX),
              [int][math]::Round(($sy - $script:UI_TOP)  / $script:UI_U))
}
# back-compat names (older scripts call these)
function OS-ToScreen([double]$ox, [double]$oy) { UI-ToScreen $ox $oy }
function Screen-ToOS([double]$sx, [double]$sy) { Screen-ToUI $sx $sy }

# --- clicking ---------------------------------------------------------------------------
# PREFERRED: click a UI coordinate read straight off a Capture-UI screenshot.
function Click-UI([int]$ux, [int]$uy, [int]$settle = 350) {
    [Inp]::SetCursorPos($ux, $uy) | Out-Null
    Start-Sleep -Milliseconds $settle
    [Inp]::mouse_event(0x2, 0, 0, 0, [IntPtr]::Zero)
    Start-Sleep -Milliseconds 60
    [Inp]::mouse_event(0x4, 0, 0, 0, [IntPtr]::Zero)
}
function MoveTo-UI([int]$ux, [int]$uy) { [Inp]::SetCursorPos($ux, $uy) | Out-Null }
# for callers that only know a screen pixel
function MoveTo-Screen([int]$sx, [int]$sy) { $o = Screen-ToUI $sx $sy; [Inp]::SetCursorPos($o[0], $o[1]) | Out-Null }
function Click-Screen([int]$sx, [int]$sy, [int]$settle = 350) {
    $o = Screen-ToUI $sx $sy; Click-UI $o[0] $o[1] $settle
}

# --- capture ----------------------------------------------------------------------------
# The whole 16:10 rendered frame (what the game actually shows).
function Get-FrameRect {
    return [pscustomobject]@{ X=[int]$script:FR_L; Y=[int]$script:FR_T
                              W=[int]$script:FR_W; H=[int]$script:FR_H }
}
# Just the 4:3 UI area — the region that maps 1:1 to OS cursor coordinates.
function Get-UIRect {
    return [pscustomobject]@{ X=[int]$script:UI_LEFT; Y=[int]$script:UI_TOP
                              W=[int](640*$script:UI_UX); H=[int](480*$script:UI_U) }
}
function Get-ContentRect { Get-FrameRect }   # back-compat

<#
  Capture-UI — screenshot cropped to the UI and rescaled so that
  **1 image pixel == 1 UI unit == 1 OS cursor coordinate**.

  This is the point of the whole file: open the PNG, find the control you want, read its
  pixel coordinate, and Click-UI that exact number. No sweeping, no calibration, no guessing.
  Aspect is preserved by construction (640x480 UI -> 640x480 image), which is what the old
  measurement got wrong.
#>
function Capture-UI([string]$Path, [int]$W = 640, [int]$H = 480) {
    Add-Type -AssemblyName System.Drawing
    $r = Get-UIRect
    $b = New-Object Drawing.Bitmap $r.W, $r.H
    $g = [Drawing.Graphics]::FromImage($b)
    $g.CopyFromScreen($r.X, $r.Y, 0, 0, (New-Object Drawing.Size($r.W, $r.H)))
    $s = New-Object Drawing.Bitmap $W, $H
    $g2 = [Drawing.Graphics]::FromImage($s); $g2.InterpolationMode = 'HighQualityBicubic'
    $g2.DrawImage($b, 0, 0, $W, $H)
    if ($Path) { $s.Save($Path, [Drawing.Imaging.ImageFormat]::Png) }
    $g.Dispose(); $g2.Dispose(); $b.Dispose()
    if ($Path) { $s.Dispose(); return $Path }
    return $s
}
Init-CursorMap | Out-Null
