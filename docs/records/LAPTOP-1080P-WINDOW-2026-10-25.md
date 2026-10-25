# Laptop 1080p window: the default 2x picture is cropped (2026-10-25)

Question: with the kit's defaults on a 1920x1080 panel, is the game window 3840x2160 (2x supersample used as the window size, so the
screen shows the top-left quarter), or does dgVoodoo scale the 2x frame to the panel?

**Verdict: cropped. With the shipped defaults (render scale 2) the game window is 3840x2160 on a 1920x1080 desktop and the panel shows
only its top-left quarter (about 1/4 of the picture, HUD and sky enlarged 2x). Render scale 1 and `--windowed` are correct.** This is a
v0.8.0 blocker for every 1080p player on the stable PLAY.bat.

## Measurements (laptop, 1920x1080 panel, no DPI scaling, kit v0.8.0 935f897 copy in `C:\i76-bench\w1080\gold`, PLAY-T05.bat, FFB off, movies skipped)

Rects read with GetWindowRect / GetClientRect from a per-monitor-DPI-aware probe inside the console session (`tools\win1080\win-probe.ps1`,
lab); desktop GetSystemMetrics 1920x1080 in every row. Screenshot = CopyFromScreen of the whole screen.

| mode | scale | window rect | client rect | visible on panel |
|---|---|---|---|---|
| default PLAY-T05.bat | 2 (3840x2160) | (0,0)-(3840,2160) | 3840x2160 | CROPPED: top-left quarter (n 3: g-t05-def, g-t05-ctl2, fix runs b) |
| default, `--no-supersample` | 1 | (0,0)-(1920,1080) | 1920x1080 | yes (n 2: g-t05-s1c, g-t05-fix1) |
| `-Windowed auto` | 2 | (0,0)-(1040,584) | 1040x584 | yes, whole picture in a 1040x584 window (g-t05-win2c) |
| `-Windowed auto -RenderScale 1` | 1 | (440,248)-(1480,832) | 1040x584 | yes (g-t05-win1b) |
| default (Gold PLAY.bat, menu phase) | 2 | (0,0)-(1920,1080) | 0x0, iconic | n/a: minimized-looking window until the mission starts |
| fix: `FullScreenMode = true` | 2 | (0,0)-(1920,1080) | 1920x1080 | **yes, whole picture, 2x render kept** (g-t05-fixA; screenshot shows cockpit, HUD, mirror complete) |
| Nitro default (P01) | 2 | window minimized (-32000,-32000) at every sample (n 2); third run an "Unhandled Exception" box at 640x480 | - | not readable (see below) |
| Nitro `-RenderScale 1` | 1 | (0,0)-(1920,1080) | 1920x1080 | yes (n-p01-s1) |
| Nitro `-Windowed auto` | 2 | (0,0)-(1040,584) | 1040x584 | yes |

Clients that PrintWindow dump 3840x2160 came back black (DirectX surface); the screen capture is the evidence (`captures\laptop-bench\win1080\`
in the lab: `g-t05-def.t60.screen.png` cropped, `g-t05-fixA.t75.screen.png` correct).

## Mechanism and fix

The kit's conf (`dgVoodoo.wide.conf`, from the daily driver) is `[General] FullScreenMode = false`, `FullscreenAttributes = fake`,
`WindowedAttributes = borderless`, `ScalingMode = stretched_ar`, `[Glide] Resolution = 3840x2160` (render scale 2 x the display). In
windowed mode dgVoodoo makes the forced Glide resolution the window size, so the borderless window is 3840x2160 on a 1920x1080 desktop
(the owner's 3440x1440 screen is the same shape: 6880x2880 window; there the daily driver has presumably always run through a
different present path or sat unnoticed). The fix proven in one boot with the 2x render intact: set `[General] FullScreenMode = true`
in the conf the launcher uses (both `dgVoodoo.wide.conf` and the `dgVoodoo.conf` it is copied to). dgVoodoo then keeps the 3840x2160 render
target and presents it scaled into a panel-sized (1920x1080) window (rect (0,0)-(1920,1080), `[Glide] Resolution` unchanged
3840x2160). `FullscreenAttributes = fake` stays (modal dialogs). Not verified: whether `FullScreenMode = true` changes the menu pointer
map (proxy cursor-map / u32x read the conf), Alt+Enter behaviour, or the 3440x1440 daily driver. n 1 at scale 2 (a second 2x boot and the
`FullscreenAttributes = default` variant exited at start: the harness's back-to-back launches die within 3 s unless ~25 s apart; fixed in
the probe, not re-run). Make-Wide-Conf / PLAY-i76's render-scale writer should emit `FullScreenMode = true` when [Glide] Resolution exceeds the display.

## Were the earlier laptop screenshots cropped?

Yes for every Gold default-scale run: the t05-early / userenv / scs-a pictures (dash enlarged across the top, sky below, Firewall prompt
in front) are this 3840x2160 window (`play-i76.log`: `render: 2x (3840x2160) ... display 1920x1080`; render-keys record measured the
window 3840x2160). The clean-install "renders correctly" judgments for Gold on the laptop were made from such screenshots only where the
picture was a menu (640x480 4:3 shell is scaled by the same window, so the menu screenshots are cropped too when the window is 3840).
Nitro P01 "HUD enlarged and cropped" is the same cause (the Nitro default is also scale 2); I could not read its rect here because the
window sat minimized in two runs and the third crashed with an "Unhandled Exception" dialog at 640x480 (n 1, not investigated).

## Harness notes
The laptop's first run of any exe path shows the Windows Firewall prompt (blocks the picture in the screenshot; Allow was clicked at
857,683); a game window can be minimized-iconic at sample time (probe now restores it); launches within 3 s of the previous game's exit
die at start (probe waits 25 s). Probe, plans and setfs.ps1: lab `tools\win1080\`.
