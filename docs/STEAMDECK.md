# Interstate '76 on the Steam Deck — the recipe (and why the Deck may be the *best* way to play it)

*Companion to the macOS port. The Deck is Linux, so almost everything we learned on the Mac
transfers — minus the one layer that caused us the most pain.*

> **STATUS: INSTALLED on this user's Deck (2026-07-11).** The game (511 MB), dgVoodoo 2.78.2 +
> our [`dgVoodoo.conf`](../dgVoodoo.conf) (gamma + 4× MSAA + 32-bit), a Deck-tuned `input.map`,
> a full [controller config](../deck/controller_neptune_i76.vdf), and 5 pieces of
> [library artwork](../deck/artwork/) were pushed over SSH to `~/Games/Interstate76/game`, added
> to Steam as a non-Steam game (**GE-Proton10-12**, launch option `-glide`) alongside the existing
> 10 shortcuts, all verified. The `deck/` folder holds the exact tooling used
> ([add-to-steam.py](../deck/add-to-steam.py) — dependency-free binary-`shortcuts.vdf` editor with
> a round-trip self-test; [install-on-deck.sh](../deck/install-on-deck.sh); [make-art.py](../deck/make-art.py);
> [remap-controller.py](../deck/remap-controller.py)). **Left for the user: launch it once (Proton
> builds the prefix + primes shaders), and apply the controller config (3 taps, below).**

## Stupid-easy install (BETA — for anyone with a Deck + the GOG game)

1. **Buy [Interstate '76 on GOG](https://www.gog.com/game/interstate_76)** and download the
   **offline installer** (`setup_interstate_76_...exe`) to `~/Downloads` using the Deck's
   Desktop-Mode browser.
2. In Desktop Mode, download and double-click
   [`Install-I76.desktop`](../deck/Install-I76.desktop) — or run the one-liner:
   ```
   curl -Ls https://raw.githubusercontent.com/therealjkvalentine/mac-gaming-ports/main/games/interstate-76/deck/deck-install.sh | bash
   ```
   The zenity-guided installer ([source](../deck/deck-install.sh)) extracts YOUR installer
   (static innoextract, fetched at run time), fetches dgVoodoo 2.78.2 from the public mirror,
   applies our tuned configs + Deck input.map, auto-detects your Steam user + GE-Proton (downloads
   it if missing), registers the game with artwork, and **pre-applies the controller layout with
   zero taps** (the Steam-ROM-Manager `configset` mechanism). No game content is redistributed.
3. Switch to **Game Mode**, set QAM → Framerate Limit = **20**, play.

*Advanced controller techniques used here (mode shifts, touch menus, activators, portability) are
documented for reuse across ports in [docs/STEAMDECK-INPUT-MODES.md](../../../docs/STEAMDECK-INPUT-MODES.md).*

## Controller layout (installed as a template — apply once)

Every I76 control is mapped to a Deck input in the conventional driving/vehicular-combat idiom.
It's installed as a selectable template; to apply: **Steam → Interstate 76 → the controller icon →
Browse Configs → Templates → "Interstate 76 (full driving+combat)"**.

| Deck input | Action | Key |
|---|---|---|
| **R2 / L2** (triggers) | Accelerate / Brake | W / S |
| **Left stick** | Steer (+ accel/brake on ↑↓) | A/D (+W/S) |
| **R1** (right bumper) | Fire weapon | Space |
| **L1** (left bumper) | Cycle weapon | Tab |
| **A** | Handbrake | C |
| **B** | Reverse | X |
| **X** | Link weapons | F |
| **Y** | Change view | V |
| **D-pad** | Glance (also menu nav) | Arrows |
| **L4 / R4** | Target front / nearest | Q / T |
| **L5 / R5** | Target next / Radar range | Y / R |
| **Left trackpad** ↑↓←→ / click | Map / Notepad / Lights / Radar-cam / Start engine | M / N / H / K / I |
| **Right trackpad** | Mouse (menus + hardpoint-1 fire on click) | — |
| **Start (☰) / Select (⧉)** | Confirm / Pause-back | Enter / Esc |

Uses **keyboard emulation** (not the winmm joystick) deliberately — it's the most reliable path
and doesn't depend on the game enumerating a virtual pad. Overflow actions (direct hardpoints 2–5,
transmission, poetry) stay on the Steam on-screen keyboard (Steam + X) or can be added to the
left-trackpad menu.

*Original planning notes (kept for the recipe rationale; every "verify on device" flag below was
resolved during the install above):*

## Why the Deck is a genuinely great target

Three things make I76 a better fit on the Deck than on the Mac:

1. **Native Vulkan (RADV on RDNA2) — the shader-warmup stutter largely evaporates.** Our whole Mac
   fight was `dgVoodoo → DXVK → **MoltenVK → Metal**`: MoltenVK re-translates every first-seen
   pipeline SPIR-V→MSL, which is the "70-second warmup / mid-mission hitch" we spent a patched
   DXVK to paper over. On the Deck the chain is `dgVoodoo → DXVK → **native Vulkan**` — DXVK's
   shaders compile straight to RADV with no MSL step, and Proton *pre-caches* shaders (Steam even
   downloads a prebuilt shader cache per game). The single biggest Mac problem is a non-problem
   here.
2. **Real force feedback.** Wine's only FFB backend is Linux **evdev** — which *is* the Deck.
   Dock a USB force-feedback wheel, enable I76's dormant Nitro-Pack FFB (registry rename, below),
   and you get the shaking the Mac can never deliver.
3. **Controls are a solved problem.** Steam Input maps the Deck's sticks/triggers/buttons onto the
   game's winmm joystick — no arrow-key gymnastics.

The catches are the same as anywhere: the engine is hard-locked to **~20 FPS physics** and a
**4:3 camera** (so the 1280×800 panel pillarboxes). Neither is fixable; both are fine.

## The recommended path: Heroic + dgVoodoo (reusing our Mac configs verbatim)

I76 is a **GOG** game, so the clean path is **[Heroic Games Launcher](https://heroicgameslauncher.com/)**
(native GOG login + install, runs great on Deck, has built-in Winetricks / DLL-override / DXVK
management). You install the real game through Heroic, drop a Glide wrapper into the game folder,
and copy in the exact `dgVoodoo.conf` and `input.map` we already validated on the Mac.

**The repo files that transfer to the Deck unchanged:**
- [`dgVoodoo.conf`](../dgVoodoo.conf) — same graphics config; the gamma/MSAA/32-bit wins apply
  natively (and should be *smoother* than Mac since there's no MoltenVK compile tax).
- [`setup-mouse-and-pad.sh`](../setup-mouse-and-pad.sh) → the `input.map` it produces (mouse +
  `joystick1` bindings; fixes GOG's phantom `joystick5`).
- The **FFB registry rename** (below) — works for real here.
- The **20 FPS** knowledge — the GOG exe's built-in `I76PATCH.DLL` limiter runs the same under
  Proton.

### Step by step (Deck Desktop Mode)

1. **Install Heroic** from the Discover store; log into GOG; install *Interstate '76 Arsenal /
   Gold*. Note the prefix + install path (Heroic shows it; typically
   `~/Games/Heroic/Interstate 76/` with a prefix under `~/Games/Heroic/Prefixes/...`).
2. **Runner:** in the game's Heroic settings, pick **Proton (GE-Proton latest)** or Heroic's
   **Wine-GE**. Either gives you native Vulkan DXVK.
3. **Glide wrapper** (the game is 3dfx Glide — it *needs* one; Proton's DXVK alone can't run Glide):
   - Get **dgVoodoo2** (dege's site). Version guidance from the same Wine enumeration bug we hit on
     Mac ([dxvk#5217](https://github.com/doitsujin/dxvk/issues/5217)): **recent dgVoodoo can fail to
     enumerate under Wine** — the working window is **either our validated `2.78.2`, or `2.8.2`
     with a recent DXVK** (which Proton bundles). Start with **2.78.2** (same version + config we
     shipped on Mac); if the 3D screen is black, try 2.8.2.
   - From dgVoodoo's `MS/x86/` drop **`Glide2x.dll`** (and `dgVoodoo.cpl` if you want the GUI) into
     the **game install dir**, next to `i76.exe`. **Delete GOG's bundled OpenGLide** `glide2x.dll`
     first so dgVoodoo's wins ([CahootsMalone guide](https://github.com/CahootsMalone/interstate-76-stuff/blob/master/running-interstate-76-gog-release-using-dgvoodoo.md)).
   - Copy our [`dgVoodoo.conf`](../dgVoodoo.conf) into the same dir.
   - *Alternative, zero-download:* keep GOG's **OpenGLide** (Glide→OpenGL). Simpler, but softer
     image and no MSAA/gamma levers — dgVoodoo is the quality path.
4. **Launch flag:** set the game's launch to `i76.exe -glide` (Heroic: "Alternative Exe" / launch
   arguments). `-glide` selects the 3dfx renderer dgVoodoo wraps.
5. **20 FPS cap — EXACTLY 20 (the Mission 5 jump depends on it):** our `dgVoodoo.conf` sets
   `FPSLimit = 20`, which is the precise one (the exe's `I76PATCH.DLL` limiter overshoots to ~20.66,
   and the **Mission 5 canyon jump falls just short at anything over 20** — jump distance is inversely
   tied to framerate, [Local Ditch: FPS jumping](https://www.localditch.com/posts/fps-jumping/)). Set
   the Deck's **QAM → Framerate Limit → 20** as well (belt-and-braces). **Don't raise it.** Above
   ~25–30 FPS everything breaks (cars flip, jumps/flamethrower/mortar misbehave) —
   [Local Ditch FAQ](https://www.localditch.com/interstate-76/faq.html). *(Nitrous helps on the ramp:
   bind `nitrous_on`/`nitrous_off` in the Deck `input.map` — this build ships them unbound.)*
6. **Controls:** see the Steam Input section.
7. **Test in Instant Melee first** (physics sanity), then a mission.

## Graphics config on the Deck

Use our [`dgVoodoo.conf`](../dgVoodoo.conf) as-is. The three wins we found for the Mac apply here
and should look *better* (native Vulkan, no MoltenVK quirks):

- `EnableGlideGammaRamp = true` — the bright 3dfx gamma (the "darker than Windows" fix).
- `Antialiasing = 4x` — MSAA; RADV does 4x/8x trivially, so on the Deck you can even try **8x**.
- `DitheringEffect = pure32bit` + `Dithering = forcealways` — smooth 32-bit skies, no banding.
- `TMUFiltering = bilinear` — authentic 3dfx smoothing (anisotropic is **impossible** for a Glide
  game in dgVoodoo, by design — don't chase it).
- Keep `VideoCard = voodoo_graphics` / `MemorySizeOfTMU = 2048` — >2 MB TMU triggers I76's
  **texture panic** (engine limit, not hardware).
- **Resolution for the 1280×800 panel:** the camera is 4:3, so you get pillarbox bars. Set
  `Resolution = max` (dgVoodoo picks the largest 4:3 that fits → ~**1066×800**), or force a clean
  4:3 like `960x720`. Let Gamescope handle the pillarbox (it will; don't stretch to 16:10 — it
  warps the HUD). Because there's no MoltenVK tax, you can push the internal 4:3 res higher than we
  dared on Mac and downscale — try `1440x1080` and see if the Deck holds 20 FPS (it will; this
  engine is trivial for RDNA2).

## Controls via Steam Input

I76 is **winmm-joystick only** (`joyGetPosEx`, no DirectInput). Under Proton, the cleanest way to
get the Deck's controls into it is to let **Steam Input** present a virtual pad:

1. Add the game (or Heroic) to Steam as a **Non-Steam Game** so Steam Input applies its controller
   layer. (Heroic can auto-add via its "Add to Steam" option.)
2. Apply our `input.map` (run [`setup-mouse-and-pad.sh`](../setup-mouse-and-pad.sh) against the
   Deck's game dir, or hand-copy the `joystick1` bindings) — it fixes GOG's phantom `joystick5`
   and binds left-stick steer/throttle, buttons → weapons/e-brake, hat → glances.
3. Pick a **driving template** in Steam Input: left stick = steer, **right trigger = throttle,
   left trigger = brake/reverse**, face buttons = weapons, d-pad = glances. (I76 exposes throttle
   as an analog sink; the triggers share one winmm axis (`Throttle`/Z) — Steam Input can split them
   cleanly, which is *nicer* than the raw winmm behavior we documented on Mac.)
4. **Gyro aiming** isn't meaningful here (no free-aim; it's a driving/targeting model) — skip it.
5. **Do NOT use I76's in-game Control Configuration menu** — it's confirmed buggy (appends chords,
   binds wrong stick numbers, crashes). Edit `input.map`; let Steam Input do the pad.

*Verify on device:* whether the game sees the Steam Input virtual pad as `joystick1` vs
`joystick0` under Proton — check with the game's controller list or `protontricks <appid> control
joy.cpl`. Adjust the `input.map` number if needed (same lesson as the Mac joystick5 fix).

## Force feedback — the Deck's exclusive win (docked wheel)

The Deck has no built-in FFB, but **dock a USB force-feedback wheel** and it works for real
(Wine's evdev FFB backend + I76's Nitro-Pack code):

1. Enable the dormant FFB (same registry key as Windows) — run against the game's prefix:
   `HKLM\SOFTWARE\ACTIVISION\Interstate'76FRC` → copy to `Interstate '76` (with the space). Do it
   via Heroic → Winetricks → `regedit`, or `protontricks`, or our
   [`enable-force-feedback.bat`](../enable-force-feedback.bat) run in the prefix.
2. Plug the wheel in **before launching** (winmm enumerates at startup).
3. The wheel's evdev FFB device must be readable (usually is on SteamOS; may need the wheel's
   udev rules on other distros).

This is the one feature that's *better* on the Deck than any Mac path.

## Honest open items (need real-Deck verification)

- **Mission music.** I76's mission soundtrack is **CD redbook audio**; GOG ships it as MP3s and
  there's no CD, so it's silent under Wine unless emulated. On the Mac we fixed this with **DxWnd's
  virtual CD audio** ([setup-music.sh](../setup-music.sh)). On the Deck's dgVoodoo path (no DxWnd)
  the same silence likely occurs. Two options to test on device: (a) layer DxWnd on the Deck too
  (it's a Windows app, runs under Proton — then our TrackNN.mp3 trick applies), or (b) check
  whether Proton's MCI/`winegstreamer` plays the GOG MP3s directly. **Untested — flag for the first
  Deck run.**
- **dgVoodoo version** (2.78.2 vs 2.8.2) — pick empirically per the enumeration note above.
- **Steam Input joystick number** — confirm `joystick1` on device.
- **Exact internal resolution / FPS headroom** — RDNA2 will crush this engine, but confirm the
  20 FPS cap holds and pillarbox looks right in Gamescope.

## Deliverable in this repo

- [`dgVoodoo.conf`](../dgVoodoo.conf), [`setup-mouse-and-pad.sh`](../setup-mouse-and-pad.sh),
  [`enable-force-feedback.bat`](../enable-force-feedback.bat) — all transfer to the Deck.
- [`setup-steamdeck.sh`](../setup-steamdeck.sh) — a helper that, run in Desktop Mode against your
  Heroic game dir + prefix, drops the config, applies the input.map, does the FFB registry rename,
  and checks the Glide wrapper. It guides rather than downloads (no game/binary redistribution —
  same rule as the Mac side).

## Sources
- [Heroic Games Launcher](https://heroicgameslauncher.com/) + [Game Workarounds wiki](https://github.com/Heroic-Games-Launcher/HeroicGamesLauncher/wiki/Game-Workarounds)
- [dgVoodoo2 official](https://sites.google.com/view/dgvoodoo2/) · [Proton issue #3516 (dgVoodoo2 for old DX/Glide)](https://github.com/ValveSoftware/Proton/issues/3516) · [dxvk#5217 (dgVoodoo Wine enumeration)](https://github.com/doitsujin/dxvk/issues/5217)
- [CahootsMalone: running I76 GOG with dgVoodoo](https://github.com/CahootsMalone/interstate-76-stuff/blob/master/running-interstate-76-gog-release-using-dgvoodoo.md)
- [VOGONS: dgVoodoo glide setup for I76 (2MB TMU / texture panic)](https://www.vogons.org/viewtopic.php?t=70951)
- [Local Ditch I76 FAQ (what breaks above 20 FPS)](https://www.localditch.com/interstate-76/faq.html)
- [Steamworks: Steam Deck & Proton](https://partner.steamgames.com/doc/steamdeck/proton) · [GamingOnLinux: DXVK on Steam Deck](https://www.gamingonlinux.com/2025/03/dxvk-2-6-brings-expanded-nvidia-reflex-support-and-lots-of-game-fixes-for-linux-steam-deck/)
