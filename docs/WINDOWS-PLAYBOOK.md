# Interstate '76 — the Windows-box playbook (max everything)

*Deep-research synthesis (2026-07-09, adversarially sourced). The to-do list for the Windows
gaming box: max graphics, force feedback, frame-rate smoothing, multiplayer. Everything below is
cited; items marked **unverified** are exactly that — first-hand community confirmation wasn't
found and they're experiments, not guarantees.*

> **Results are in:** the playbook below was executed 2026-07-09 — see
> [FINDINGS-2026-07-WINDOWS-AND-TEXTURES.md](FINDINGS-2026-07-WINDOWS-AND-TEXTURES.md)
> for what's verified (dgVoodoo recipe, LSFG 20→40, M16 format crack, texture pipeline),
> what's dead (wrapper-level texture replacement), and what's open.
>
> **Scripted:** [`setup-windows.ps1`](../setup-windows.ps1) automates §1 plus the input.map
> fixes (§4): retires GOG's OpenGLide, deploys dgVoodoo2 x86 Glide DLLs, installs
> [`dgVoodoo.windows.conf`](../dgVoodoo.windows.conf) (20 FPS cap, Voodoo1 2MB/1TMU, 3x res,
> 8x MSAA, windowed), patches joystick5→joystick1 + mouse driving, writes `PLAY-i76.bat` +
> desktop shortcut. Force feedback stays a separate admin step
> ([`enable-force-feedback.bat`](../enable-force-feedback.bat)).
> Note for 2.87.x: `WatermarkDisplayDuration = 0` now means *infinite* — the real watermark
> switches are `3DfxWatermark = false` (Glide) / `dgVoodooWatermark = false` (DirectX).

## 1. Max graphics — dgVoodoo2 Glide, the canonical config

The community-standard guide is [CahootsMalone's I76+dgVoodoo walkthrough](https://github.com/CahootsMalone/interstate-76-stuff/blob/master/running-interstate-76-gog-release-using-dgvoodoo.md)
(mirrored on the [GOG forum](https://www.gog.com/forum/interstate_series/simple_stepbystep_instructions_for_running_interstate_76_with_hardware_acceleration_using_dgvood/page1)):

1. **Delete GOG's bundled OpenGLide files** from the game dir first (glide2x.dll etc.) so
   dgVoodoo's glide2x.dll wins.
2. **3Dfx card: Voodoo Graphics, 2MB; Memory per TMU = 2048 KB, 1 TMU** — the load-bearing
   setting. I76's Glide backend was written for 2MB-TMU Voodoo 1 cards; more TMU memory causes
   "texture panics"/corruption ([VOGONS t=70951](https://www.vogons.org/viewtopic.php?t=70951)).
3. **Glide gamma ramp: ON** (this is the bright 3dfx look), **force true PCI access: ON**,
   **vSync: ON**.
4. **FPSLimit = 20** in dgVoodoo.conf — and here **dgVoodoo's limiter is the one that matters**,
   not just belt-and-braces. The exe's AiO limiter overshoots slightly (measured **~20.66** on the
   Mac software path), and **the Mission 5 canyon jump falls just short at anything over exactly 20**
   — jump distance is inversely tied to framerate ([Local Ditch: FPS jumping](https://www.localditch.com/posts/fps-jumping/)).
   dgVoodoo `FPSLimit = 20` caps the Glide buffer-swap precisely at 20, so the physics loop runs at a
   true 20 and the jump works. **Do not raise it.** Above ~30fps: jump physics, flamethrower, mortar
   range and AI driving all break ([Local Ditch FAQ](https://www.localditch.com/interstate-76/faq.html)).
   *(Nitrous helps on the ramp — bind `nitrous_on`/`nitrous_off` in `input.map`; this build ships
   them unbound.)*
5. **Resolution: force any 4:3 value** — dgVoodoo accepts dynamic specifiers (`2x`, `3x`, `Max`,
   `Max ISF`) and custom strings like `2560x1920, 60`
   ([dgVoodoo ReadmeGeneral](https://dege.freeweb.hu/dgVoodoo2/ReadmeGeneral/)). Start at `2x`,
   push to `Max ISF` / 2560x1920. Forcing 16:9 just stretches — the camera is hardcoded 4:3.
6. **Then the untested-by-the-guide upgrade:** MSAA 2x→8x (Glide tab; no I76-specific breakage
   reports — watch the HUD/sky and revert if artifacting). **Forced anisotropic filtering is NOT
   available for I76** — corrected after source-level research: dgVoodoo emulates 3Dfx TMU
   sampling in the pixel shader (bypassing the GPU sampler), so Glide games get only
   `pointsampled`/`bilinear`, never anisotropic, on Windows or Mac. Also add
   `EnableGlideGammaRamp = true` for the bright 3dfx gamma and `[GlideExt] DitheringEffect =
   pure32bit` for banding-free skies. (These three — MSAA, gamma, 32-bit — are what we pulled back
   into the Mac Voodoo config; see [VISUAL-QUALITY-MAC.md](VISUAL-QUALITY-MAC.md).)
7. **Watermark off:** `GeneralExt\WatermarkDisplayDuration = 0` in dgVoodoo.conf (or the CPL
   checkbox on older builds).
8. Known Glide-mode quirks: pause-menu mouse weirdness at forced res (navigate by keyboard);
   HUD corruption after binoculars reported by some — **nGlide is the community's plan-B
   wrapper** if dgVoodoo misbehaves on the box.

## 2. Frame-rate smoothing — honest verdict

The 20fps cap is physics-load-bearing and cannot be raised. The only way to *smoother-looking*
motion is frame interpolation on top:

> **Frame-gen does NOT change the physics base — keep `FPSLimit = 20`.** LSFG's 20→40 (or →60)
> are *interpolated display frames*; the game still simulates at the 20fps base dgVoodoo enforces,
> so the Mission 5 jump and all physics stay correct. Never "fix" smoothness by raising FPSLimit —
> that breaks the jump. Interpolate on top of 20, don't run the sim above it.

- **The realistic path: [Lossless Scaling](https://store.steampowered.com/app/993090/) (LSFG),
  ~$7.** Capture-based (WGC/DXGI desktop capture): it doesn't care that the game is from 1997 —
  it interpolates whatever the window composites. Requirements: **windowed/borderless** (dgVoodoo
  windowed mode is ideal — its output is D3D11), dgVoodoo **vSync OFF** so LS owns presentation.
  LSFG x2 → 40fps-looking, x3 → 60.
- **The honest catch:** LS's developer guidance is a ~30fps minimum base (60 ideal); at a 20fps
  base, inter-frame deltas are large and **artifacts are guaranteed** — expect HUD ghosting and
  warping on fast pans/crossing traffic ([dev guidance](https://steamcommunity.com/app/993090/discussions/0/4418677017727367960/),
  [artifact thread](https://steamcommunity.com/app/993090/discussions/0/598521781543772576/)).
  x2 artifacts less than x3. Input latency stays 20fps-ish regardless — this smooths *looks*,
  not *feel*. I76's slow flat desert is actually favorable content. **No I76-specific LSFG
  report exists — this is an experiment.** Try x2 first.
- **Working config (LS 3.2.2, set up 2026-07-09):** settings live in
  `%LOCALAPPDATA%\Lossless Scaling\Settings.xml` (app must be closed when editing). Profile:
  `FrameGeneration = LSFG3` (shows as "LSFG 3.1"), `LSFG3Mode1 = FIXED`, `LSFG3Multiplier = 2`,
  `CaptureApi = WGC` (right for a windowed game), `DrawFps = true` (proves the 20/40 split
  on-screen). Set dgVoodoo `ForceVerticalSync = false` first. Activate: focus the game,
  Ctrl+Alt+S (toggle off the same way).
- **Skip:** AMD AFMF2 (needs 60fps+ base to behave, disengages on fast motion — unverified on
  wrapped-1997 games), NVIDIA Smooth Motion (needs a per-game NVIDIA App profile i76.exe will
  never have), SVP (video players only).

## 3. Force feedback (the Sidewinder nostalgia, for real)

- Run [`enable-force-feedback.bat`](../enable-force-feedback.bat) **as Administrator** — it
  `reg copy`s `HKLM\SOFTWARE\ACTIVISION\Interstate'76FRC` → `Interstate '76` (WOW6432Node-aware,
  reversible). The Gold Edition ships the Nitro-Pack FFB code but reads the un-suffixed key
  ([PCGW](https://www.pcgamingwiki.com/wiki/Interstate_'76)).
- **Confirmed working hardware** on the GOG build: Logitech **Driving Force GT** (2024 report,
  [VOGONS t=61199](https://www.vogons.org/viewtopic.php?t=61199)); Logitech **WingMan Force 3D**
  ([GOG forum](https://www.gog.com/forum/interstate_series/gog_interstate_76_and_force_feedback_joystick_no_force_feedback_working)).
  It's standard DirectInput FFB — still works on Win10/11 wherever the vendor ships DirectInput
  FFB drivers (Logitech G HUB, Thrustmaster). Your FFB wheel+pedals should qualify; no broad
  Win10/11 wheel matrix exists, so the DFGT report is the strongest modern signal.
- Enable the joystick in-game after the registry fix. **Avoid the in-game Control Configuration
  menu for rebinding** (see input notes below) — edit `input.map` directly.

## 4. Input on Windows (same engine facts as the Mac port)

- The game is **winmm-native** (joyGetPosEx; no DirectInput for input) and has **native mouse
  driving**: analog channels `mouse Left/Right` / `mouse Down/Up`, buttons
  LeftBtn/RightBtn/MiddleBtn (exactly three — weapon 4 can't live on a mouse button).
  [`setup-mouse-and-pad.sh`](../setup-mouse-and-pad.sh) documents the exact `input.map` blocks —
  the same edits apply verbatim on Windows.
- GOG shipped `input.map` bound to a phantom **joystick5** (the packager's machine) — fix to
  your actual stick number (usually joystick1).
- The in-game Control Configuration menu is community-confirmed buggy (appends chords instead of
  replacing, binds wrong stick numbers, crash thread on GOG forums) — **edit input.map in a text
  editor instead**.
- Xbox pads: work via winmm ([GOG forum: "detects my Xbox 360 controller, even the triggers work"](https://www.gog.com/forum/interstate_series/is_1_76_compatible_with_a_gamepad));
  both triggers share one axis (`Throttle`/Z), right stick mostly unusable natively.

## 5. Multiplayer is ALIVE (Windows-only bonus)

The AiO patch (already inside the GOG exe) fixes the netcode/UPnP, and a community server runs at
**glenrio.interstate76.com** with weekly sessions (Tuesdays; Xetrem190's Discord organizes).
That's a Windows-box activity the Mac port can't do yet — worth a session.

## 6. Known dead ends (don't burn time)

- **Widescreen/FOV:** impossible — 4:3 hardcoded in the camera; 16:9 forcing stretches, HUD breaks.
- **Raising the frame cap:** breaks physics (see Local Ditch FAQ list) — the 20fps limiter stays.
- **HD textures:** no released pack exists; this repo's `tools/` has the format research
  (VQM/PAK/ZFS decoders) if that itch ever needs scratching — same ceilings on Windows.

## Cross-references

- [VERIFIED-FIXES.md](VERIFIED-FIXES.md) — every Mac-port fix (many apply to Windows too:
  input.map edits, music tracklen.nfo, 20fps facts).
- [FORCE-FEEDBACK-AND-VISUALS.md](FORCE-FEEDBACK-AND-VISUALS.md) — the full FFB analysis.
- [DXGI-DGVOODOO-RESEARCH.md](DXGI-DGVOODOO-RESEARCH.md) — dgVoodoo-under-Wine (Mac) saga;
  on real Windows none of those constraints apply (any dgVoodoo version works there).
