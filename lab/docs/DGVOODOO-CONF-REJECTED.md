# The sandbox's dgVoodoo.conf was being rejected (found 2026-10-02)

**Fact, measured:** dgVoodoo 2.87.3 rejected `game\dgVoodoo.conf` as a whole and silently used the global
`%APPDATA%\dgVoodoo\dgVoodoo.conf` (a 2020 file, `Version 0x270`: FullScreenMode true, `Resolution = h:1920, v:1440`,
Glide antialiasing appdriven, forced vsync). With the global file hidden it fell to defaults (raw 640x480 window).
Every "this knob does nothing" result since August traces to this: `FPSLimit`, `CaptureMouse`, `FreeMouse`, forced
`Resolution = WxH, R`, the 3360x2100 "supersampling", 8x MSAA. The 0..1920x1440 pointer box was the global conf's
resolution, not a dgVoodoo defect.

**How it was found:** a 15-run capture matrix (1x .. 3x internal resolution, MSAA 0/4/8) produced identical frames,
GPU load and memory. `tools\graphics\conf-probe.ps1` then set `3DfxWatermark = true`: no logo. With the global file
hidden the window collapsed to 640x480. A minimal clean conf was honoured. `tools\graphics\conf-bisect.ps1 -Each`
(every key alone beside a sentinel `ScalingMode = stretched_ar`, window size as the read-out) named the lines:

| rejected line | why |
|---|---|
| `[General] EnableInactiveAppState = true` | not a [General] key (it belongs to [Glide] only); added 2026-08-09 as "the fix" for the unfocused freeze |
| `[DirectX] EnableInactiveAppState = true` | same |
| `[GeneralExt] WindowedAttributes = border` | not a valid value (`borderless` is) |

Without those the conf is accepted (confirmed by the same detector, and by a watermark probe in a mission).

**What the accepted file then did:** `FullScreenMode = false` makes the Glide resolution the WINDOW size, so
3360x2100 overflowed the 3440x1440 screen. The intended picture needs fake fullscreen. The fixed sandbox conf:
`FullScreenMode = true` + `FullscreenAttributes = fake`, `ScalingMode = stretched_ar`, `[Glide] Resolution =
3840x2880` (2x of the 1920x1440 4:3 picture), `Antialiasing = 4x`, `[DirectX] Resolution = 1920x1440`,
`FPSLimit = 0`. Measured on t01 at `I76_GLIDE_REFRESH=120`: 120.1 fps, edges antialiased, GPU memory 1.7 GB (was
1.07 GB), the pointer roams the whole screen (no box), bookmark route completes, option 6 through the trip menus
120.0 fps, and the Esc-menu Exit is hit at its DRAWN position with `I76_U32X_MENU_BOX=0`.
The rejected file is kept as `game\dgVoodoo.conf.rejected-20261002`.

**Consequences to re-check:** docs/CONFIG-OPTIONS.md entries verified between 2026-08-09 and 2026-10-02 (they were
measured under the global conf), the "unfocused game keeps running" claim, docs/framerate/README.md section 6
("FPSLimit ignored", "60 accepted"), MOUSE-ESC-MENU-AND-SAVE-SCREEN.md's box analysis, and the daily driver's conf
(same family: `WindowedAttributes = borderless`, no stray EnableInactiveAppState, so it may be accepted - probe it).
