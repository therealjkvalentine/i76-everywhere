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

1. **Buy [Interstate '76 on GOG](https://www.gog.com/en/game/interstate76)** and download the
   **offline installer** (`setup_interstate_76_...exe`) to `~/Downloads` using the Deck's
   Desktop-Mode browser.
2. In Desktop Mode, download and double-click
   [`Install-I76.desktop`](../deck/Install-I76.desktop) — or run the one-liner:
   ```
   curl -Ls https://raw.githubusercontent.com/therealjkvalentine/i76-everywhere/main/deck/deck-install.sh | bash
   ```
   The zenity-guided installer ([source](../deck/deck-install.sh)) extracts YOUR installer
   (static innoextract, fetched at run time), fetches dgVoodoo 2.78.2 from the public mirror,
   applies our tuned configs + Deck input.map, auto-detects your Steam user + GE-Proton (downloads
   it if missing), registers the game with artwork, and **pre-applies the controller layout with
   zero taps** (the Steam-ROM-Manager `configset` mechanism). No game content is redistributed.
3. Switch to **Game Mode** and play. Leave QAM → Framerate Limit at its default (off): the game
   caps itself (this build at ~20 through GOG's `I76PATCH.DLL`, the 2026-10-06 build at the
   panel's refresh through `I76_GLIDE_REFRESH`). Steam keeps that setting in no file a script can
   set, which is why the installers no longer ask for it.

*Advanced controller techniques used here (mode shifts, touch menus, activators, portability) are
documented for reuse across ports in [STEAMDECK-INPUT-MODES.md](STEAMDECK-INPUT-MODES.md).*

> **NEW 2026-08-01 — a second control mode.** Everything below describes the Steam Input
> keyboard-emulation layout (the *convenience* tier). There is now also a **baseline tier** that
> runs the same AutoHotkey pad layer as the Mac and Windows builds inside the Proton prefix —
> which is what brings **rumble**, the LB shift layer, independent triggers and the look-back rear
> gun to the Deck. It trades away the trackpad radial menu and the grip buttons. Deploy with
> `./deck/deck-push.sh`; recipe, decode sheet and rollback in **[DECK-BASELINE.md](records/DECK-BASELINE.md)**.
> Not yet field-tested on Deck hardware.

> **NEW 2026-10-06: the current graphics build, for the Deck.** `./deck/deck-push-wide.sh
> deck@steamdeck.local` (from the Mac) runs [`deck/setup-deck-wide.sh`](../deck/setup-deck-wide.sh)
> on the Deck: the `Strlkup.dll` proxy with the Windows daily driver's `best-wide-balanced`
> switches set for the 1280x800 panel (`I76_ASPECT=1280x800` Hor+ widescreen, HUD squeeze, fixed
> 24 Hz physics step + render interpolation at 60 Hz (90 on an OLED), far clip 1200 m, detail x8,
> terrain-flash and TMU fixes, mp3 music), dgVoodoo at native 1280x800 + 4x MSAA with TMU 8192,
> GOG's 20 fps cap (`I76PATCH.DLL`) off, and IPXWrapper + `WINEDLLOVERRIDES` for LAN play
> ([MULTIPLAYER.md](MULTIPLAYER.md)). Switches live in `~/Games/Interstate76/i76-env.sh`, loaded by
> [`i76-deck-launch.sh`](../deck/i76-deck-launch.sh), which needs the launch options
> `"/home/deck/Games/Interstate76/i76-deck-launch.sh" %command% -glide`. `--revert` restores every
> touched file. dgVoodoo stays 2.78.2, controls are untouched (`I76_DECK_AHK=0`). **This
> supersedes the 20 fps / 4:3 advice below** (QAM framerate limit off, not 20).
> Installed on the owner's Deck (LCD, SteamOS 3.8.16) 2026-10-06 21:33, backup
> `~/Games/Interstate76/backups/pre-wide-20261006-213343`. **Run there the same evening (GE-Proton10-12,
> desktop mode, launched through Steam with the wrapper):** every switch applied, as on the Mac under
> Wine (`mciproxy.log`: aspect 20/20, HUD squeeze 2/2, framerate fixes 36/36, far clip 6/6, TMU fix,
> Glide window at 60 Hz). Booted into T01 (`I76_MISSION=t01`, test only): cockpit fills the
> 1280x800 panel, round radar and reticle, **60.0 fps steady** (`I76_FPS_LOG=5`, 6 windows; isolated
> frames to 37-47 ms). Asking for 120 Hz (`I76_GLIDE_REFRESH=120`) still gave 60.0: presentation
> is locked to the 60 Hz panel. Saves byte-identical afterwards. **Pillarbox found and fixed:**
> with a real fullscreen mode change dgVoodoo runs 640x480 and Proton scales that mode keeping 4:3
> (child window 1067x800 at x=107), so the Hor+ camera came out squeezed into a 4:3 box;
> `[GeneralExt] FullscreenAttributes = fake` presents at 1280x800 (the setup script adds it).
> Not checked: Game Mode (gamescope), driving with the physical controls, LAN play from the Deck.
>
> **2026-10-07, after the owner played it:** (1) **menu pointer** acted up and to the left of the arrow and
> bookmarks could not be loaded. dgVoodoo's `CaptureMouse` (default on) fenced the OS pointer into the
> top-left 640x480, and the game reads raw screen pixels. Fixed with `CaptureMouse = false` plus the
> proxy's new `I76_CURSOR_MAP=1` (music-fix/README.md); verified by pointer: every main-menu button
> lights under the arrow, TRIP -> LOAD BOOKMARK -> Scene 5 -> LOAD reaches the garage. The Deck runs the
> Mac build `deck/Strlkup.deck.dll` (md5 7b780281) until the MSVC build carries the switch. (2) **"a hair
> too dark"**: dgVoodoo's Glide gamma ramp has no effect under Proton (identical frames with it on and
> off), so `Brightness = 115` stands in. (3) **right stick outside the car** did nothing: the orbit was
> Shift+arrows only; now the plain arrows orbit too (controls/input.map and the Deck's map). (4)
> **Controls guide:** [deck-controls.html](deck-controls.html). (5) The Deck's left stick was already
> analog (`joystick_move` -> joystick1); the v4 table below is stale on that point. All in
> `deck/setup-deck-wide.sh`.
>
> **2026-10-08: superseded - one layout.** The Deck now plays exactly the gamepad layout (single entry,
> layout v10, the shared pad layer); see CONTROL-DOCTRINE.md. The two-profile note below is history.
>
> **2026-10-07, later: two control profiles.** `./deck/deck-push-pad.sh` adds a second library entry,
> **"Interstate 76 (pad layer)"**: Steam layout v9 (`deck/controller_neptune_i76_pad.vdf`, a plain gamepad
> plus the grips, the trackpad menu and the trackpad mouse) with the shared `i76-remap.ahk` running in the
> prefix and the shared `controls/input.map` live, so the Deck plays with the Windows/Mac pad controls (Y
> view cycle, LB shift layer). The normal entry keeps layout v8.1 and the Deck's own map; the wrapper copies
> `input.map.profile-pad` or `input.map.profile-deck` into place per launch. Smoke-tested: each entry
> swaps the right map, the pad layer runs only in the pad entry, both full screen. Not yet played by hand.
> **Found on the way:** the Deck's full-screen picture depended on `ddraw`/`d3dimm` = native overrides in
> the July prefix's registry; a fresh prefix pillarboxed. `i76-env.sh` now sets them in `WINEDLLOVERRIDES`. Its `ADDON\valepre4.vcf` is the non-stock
> 4ed297ca, as on the Mac: pick a car other than Jade's for LAN games against a stock PC.

## Docked to a TV (2026-10-13)

Owner report, Deck docked to a TV: *"the screen renders in a non 16:9 aspect ratio and the controller can't be used to
navigate the menu. Screen looks a little darker too."* Deploy: `./deck/deck-push-tv.sh` (from a PC with `ssh deck`;
runs [`deck/setup-deck-tv.sh`](../deck/setup-deck-tv.sh) on the Deck, which refuses while `i76.exe` runs, backs up
`game/Strlkup.dll`, `game/dgVoodoo.conf`, `i76-env.sh` and `i76-deck-launch.sh` to `backups/pre-tv-<date>/` with a
`NOTE.txt`, and has `--revert`).

**1. Aspect: the game draws the size Steam gives it, not the TV's.** In Game Mode gamescope runs the game in its own
Xwayland screen whose size is Steam's per-game **Game Resolution**. On *Default* the Deck gives games 1280x800 even
when docked, and gamescope scales that 16:10 picture onto the 16:9 TV with bars. Nothing inside the game can fix that
(dgVoodoo fake fullscreen presents at the screen it is given), so:

- **Owner, once:** in Game Mode, docked: *Interstate 76 > gear > Properties > General > Game Resolution* = **Native**
  (a 1080p TV) or **1920x1080** (a 4K TV: 3840x2160 with 4x MSAA is a lot for the Deck). If your SteamOS version
  shows the setting only while an external display is connected, set it docked. Handheld it changes nothing (native
  there is 1280x800).
- **The launcher follows it.** [`i76-deck-launch.sh`](../deck/i76-deck-launch.sh) reads the size of the game's own X
  screen (`xrandr` on `$DISPLAY`, else `xdpyinfo`, else libX11 through python3) and the connected HDMI/DP connector
  (`/sys/class/drm/card*-*/status`, not eDP), and per launch sets `I76_ASPECT=<W>x<H>` (Hor+ camera, HUD squeeze) and
  dgVoodoo's `[Glide] Resolution` (2x the panel = 2560x1600 handheld as before; 1x on the TV, halved while above
  1920x1080 so a 4K screen renders 1920x1080). Only the values of existing keys change, never keys
  ([GeneralExt] stays fake fullscreen, ScalingMode stretched). `deck-launch.log` gets a `display:` line with what was
  read, including any `GAMESCOPE*` variables, and a **WARNING** when a TV is connected but the game got 1280x800 (=
  Game Resolution still on Default).
- **Override:** `I76_DECK_DISPLAY=handheld|tv|auto|off` in `i76-env.sh` or in front of the wrapper in the launch
  options. `off` = the old behaviour (env's `I76_ASPECT`, conf untouched).
- **Not yet read on the Deck itself:** the Deck was offline when this was built (no mDNS answer, tailscale node offline
  since May), so which of xrandr / xdpyinfo exist on this SteamOS and what gamescope reports were not observed. The
  first docked launch's `deck-launch.log` answers it; the fallback without any reading is the panel's 1280x800.

**2. Controller in the menus: `I76_PAD_MENU=1`** (proxy, [`music-fix/padmenu.c`](../music-fix/padmenu.c)). Only while
the shell is up (game state `[0x4c2164] == 6`) or the in-mission Esc menu (`[0x4fe534] == 0x10`): **left stick** and
**D-pad** move the pointer (accelerating; a D-pad tap is a 2-pixel nudge), **A** clicks (the pad layer's own A click
does it when AHK runs; the proxy then does not click twice), **B** = Esc, **Start** = Enter. All XInput slots are read
and merged (docked, the Deck's controller and the TV pad are both connected). In a mission the thread does nothing;
unset, there is no thread. The pad layer's keys for those buttons (D-pad = H/I/N/M, Start = M, B = Tab) are dropped
on their way into the game while the button is held, so they no longer type into the bookmark name. Side build
`deck/Strlkup.deck-padmenu.dll` md5 `2f2b8170` = the deployed `509c6df0`'s own source (lab
`builds\terrain-probe-20261012\src`) + `padmenu.c`, MSVC x86 (lab `builds\pad-menu-20261013`); static checks only
(exports identical to 509c6df0, imports SendInput / FindWindowA / GetForegroundWindow, the state reads verified
against the exe: `0x404b30 cmp [0x4fe534],0x10`, one `cmp [0x4c2164],6`). **The OK popups** (garage refusals, the
save reminder) do not present frames, so the pencil freezes there; the pointer still moves and A on OK still works,
and **Start (Enter) closes them only with the F7 shell patch** ([`tools/patch-shell-f7.py`](../tools/patch-shell-f7.py))
- the Deck's `i76shell.dll` was not checked (offline); the launch log's md5 line or `md5sum game/i76shell.dll`
tells. **Esc in the garage opens Control Configuration**: back out of it with its own button and never rebind there
(the launcher restores `input.map` on every launch anyway).

**Pad menu v3 (2026-10-14).** Owner, after v2: *"the left stick as mouse in menus isn't working consistently. Sometimes it
doesn't move the cursor and it doesn't seem to move it right over the correct mouse coordinates."* The Deck was offline
(no mDNS, tailscale node offline), so no Deck log was read; the cause below is from the code. v2 moved only the OS
pointer (SetCursorPos) and let the game read it back through the cursor map, and every poll it resynchronised its own
position from GetCursorPos whenever that differed from its last warp target by more than 2 px. Under gamescope a warp
from the app can land late or not at all, so a warp that had not landed by the next poll (8 ms) dragged the pad position
back to where the pointer still was: the stick "did nothing", and between polls the game's read-back and the pad's
target disagreed ("not over the right coordinates"). v3 ([`music-fix/padmenu.c`](../music-fix/padmenu.c) +
[`cursormap.c`](../music-fix/cursormap.c)):

- **The pad is the source of truth while it drives.** Its position (640x480 UI units) goes to the cursor map, whose
  GetCursorPos / GetCursorInfo / PeekMessageA mouse-lParam slots in i76.exe and i76shell.dll return it. The hit-test and
  the clicks (ours, or the pad layer's AHK `Click`) land on the pad position whether or not the OS pointer followed.
- The OS pointer is still warped there for the visible arrow; each warp is read back on the next poll and counted.
  `mciproxy.log`: `pad-menu: warp to (x,y) read back (x,y) - not landed` (first 6), and every on/off line carries the
  totals (warps, landed, not landed, moved by something else) plus state, mode and the foreground owner.
- The pointer goes back to the OS when something else moves it (read-back changed between two polls without a warp of
  ours: trackpad, mouse) or the game calls SetCursorPos.
- **Gating:** also the exe's other non-driving pages (state 5, mode not 1 / 0x20 / 0): the Esc menu's Exit dialog takes
  the mode out of 0x10, so v2 stopped exactly there. Pointer and A only on those pages. Another process's window in
  front stops it only after 400 ms.
- Switches: `I76_PAD_MENU_VIRTUAL=0` (v2 behaviour, for an A/B), `I76_PAD_MENU_PAGES=0` (v2 gate). Needs `I76_CURSOR_MAP`
  (the Deck has it); without it v3 falls back to warping only and says so.
- **Steam Input:** the left stick must be a plain stick (`joystick_move`, as in `controller_neptune_i76_pad.vdf`), not
  Joystick Mouse / As Mouse: a stick that is also a Steam mouse moves the OS pointer at the same time, which v3 reads as
  "something else moved it". The right trackpad stays a mouse; v3 hands over cleanly between the two.
- **Open:** whether gamescope draws its arrow at the warped position. If the owner sees buttons light up under a pencil
  that does not move, the game side is right and the arrow is the compositor's; the log's warp counts tell which.
- Build: lab `builds\pad-menu-v3-20261014` (509c6df0's source, = 2f2b8170's, + padmenu.c v3 + the cursormap pad slots),
  MSVC x86, `deck/Strlkup.deck-padmenu.dll` md5 **8bc52939**; static checks: the five exports equal 509c6df0's, imports
  add GetClassNameA; the repo source compiles too. Not run on a Deck yet: owner test 39, 2026-10-14 follow-up.

**Night missions (T06, T12; melee M04, M12), owner 2026-10-14: "the textures seem wrong".** Not diagnosed: no Deck log or
picture was available. What was ruled out from the files: the launcher changes only `[Glide] Resolution` and
`[General] Brightness / Contrast / Color` (all 100), nothing texture-related, and rewrites them on every launch, so no
stale TV value survives into handheld. Known causes of wrong textures in this setup, now checked on every launch (a
`conf:` line in deck-launch.log with every texture-relevant dgVoodoo value, and a WARNING for each): `MemorySizeOfTMU`
above 2048 without `I76_ZGLIDE_TMUFIX=1` (textures overwritten in play, "texture exchange"), and `[GlideExt]
DitheringEffect` other than `pure32bit` (16-bit rendering: magenta/purple night ground, CHANGELOG / HD-TEXTURES-RESEARCH).
Remaining differences from the PC: dgVoodoo 2.78.2 (PC 2.87.3) under DXVK, `ForceEmulatingTruePCIAccess` false (PC true;
LFB timing, not textures), the Glide gamma lift (1.3 handheld, 1.45 TV) on a very dark night palette, and on a TV the
HDMI range (limited/full mismatch crushes exactly the night shadows). Also fixed: docked with Game Resolution on Default,
the TV profile rendered at 1x 1280x800 (shimmer on far textures); it now renders 2x like handheld (`I76_TV_SS_800`).
Next step: the owner's screenshot + the `conf:` line.

*Alternative without the proxy, for an external pad:* Steam Input is per controller type, so the TV pad has its own
layout for this shortcut. Steam button > Controller settings with the pad selected: put the **right stick on "Mouse"
(or Joystick Mouse) in a second action set** "Menus" and switch to it with a held/long-pressed button, with A = left
click there. It works without any game change but is a mode the player must remember to switch (the right stick is
the glance in the driving set) and it does nothing for the Deck's own controller; the proxy switch follows the game's
own menu state instead. The Deck's built-in right trackpad stays a mouse in both.

**3. Darker on the TV.** The launcher now has a brightness profile per display. Handheld unchanged (gamma 1.3,
dgVoodoo Brightness 100). TV: `I76_TV_GAMMA=1.45` (3D picture only; higher = brighter mid-tones without clipping),
`I76_TV_BRIGHTNESS` / `I76_TV_CONTRAST` / `I76_TV_COLOR` (dgVoodoo [General], 100 = neutral, also reach the menus and
movies; Brightness is linear and clips highlights above ~115). Edit them in `~/Games/Interstate76/i76-env.sh` (the
block at the end) and relaunch. Before tuning the game, check the TV chain, which is the usual cause:

- **HDMI range.** PCs send full-range RGB (0-255); many TVs expect limited (16-235) on HDMI. Full sent into a TV set to
  limited crushes the shadows: darker, details lost in black - exactly "a little darker". Set the TV's HDMI black
  level / RGB range to **Auto** or **Full/High** for that input (Samsung "HDMI Black Level", LG "Black Level", Sony
  "HDMI video range"). The opposite mismatch looks washed out, not darker. A SteamOS-side range switch was not
  verified here.
- **HDR.** If the TV is HDR and SteamOS runs the external display in HDR (Settings > Display), an SDR game like this
  one is mapped into HDR and often looks dim; turn HDR off for the TV, or raise the SDR brightness setting if your
  SteamOS version shows one.
- **Picture mode.** Game/PC mode, not Cinema/Filmmaker (those target a dark room). The Deck's own brightness slider
  does not change an external display.

### Owner test: docked to the TV (2026-10-13; OWNER-TEST-LIST item 39)

1. **Set Game Resolution** (above) to Native, docked. Launch Interstate 76 from Game Mode.
2. **Aspect.** The main menu and the mission picture fill the 16:9 TV, no black bars left/right. In a mission (T01 or
   Instant Melee): round wheels, round radar, the 3D not stretched sideways (a wider view, not fatter cars).
3. **Menus with the controller.** Left stick moves the pencil, D-pad nudges it; A on TRIP, then LOAD BOOKMARK, pick a
   bookmark, LOAD, into the garage, DONE into the mission. B goes back a screen. On a garage OK popup: A on OK (the
   pencil may look frozen - the pointer still moves), then Start: does Enter close it? In the mission: Esc menu (Select),
   move to Graphic Detail with the stick, A opens it, Exit with A, B closes the menu. Driving afterwards unchanged.
4. **Brightness.** Compared with handheld: still darker? Try the TV's HDMI black level first, then
   `I76_TV_GAMMA=1.6` in i76-env.sh. Report the values you like.
5. **Handheld again** (undocked): unchanged - fills the panel, same brightness, the stick also moves the menu pointer now.
6. Send `~/Games/Interstate76/deck-launch.log` and `game/mciproxy.log` (the `display:` and `pad-menu:` lines).

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
   tied to framerate, [Local Ditch: FPS jumping](https://www.localditch.com/posts/fps-jumping/)). *(2026-10-07: superseded on the Deck by the 2026-10-06 build, whose fixed physics step keeps the
   jump distances at any frame rate; there the QAM limit stays at its default.)* **On a build without
   the fixed step, don't raise it.** Above
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
   *(2026-07-19 disassembly note: the Gold `i76.exe` FFB init is unconditional — no registry gate
   was found in the binary ([FFB-DEEP-DIVE.md](records/FFB-DEEP-DIVE.md) §2). The community rename step is
   likely harmless cargo cult on Gold; keep doing it until a Deck run confirms, since it costs
   nothing. Actual requirements: `i7_sfrce.dll` beside the exe + an FFB device present at launch.)*
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

## Controller-track open items (from the 2026-07-12 session handoff)

Carried over from the live-Deck config sessions (template "Option 1 v8" confirmed working:
analog drive, right-stick glance + R3 look-at-target, triggers, bumpers, d-pad utilities).
The cross-platform two-tier directive from that handoff shipped as
[CONTROL-DOCTRINE.md](CONTROL-DOCTRINE.md); these are what's still open:

- **Wheel slices should show FUNCTIONS, not key glyphs.** The touch-menu slices render the
  keyboard-key image Steam auto-picks; the user wants "Fire All"/"Map"/"Poetry". The binding
  format ([STEAMDECK-INPUT-MODES.md](STEAMDECK-INPUT-MODES.md) §4) is
  `key_press KEY, Label, icon.png, #bg #fg` — check label-vs-glyph display priority, else ship
  small function icons (`TouchMenuIcons/` relative to the shortcut's Start Dir — untested for
  non-Steam shortcuts).
- **v8 field-test follow-ups** (ask for results, then tune): is the 13-slot left wheel usable
  or drop to ~8 (weapons 4/5 were cut for the 13-grid budget)? Does L3 = Special 1 (key 6) drop
  the rear weapon (bound as a separate `special1 { + keyboard Six }` block, not a chord)? Is
  F2 the right "chase" preset for Y (cameras are fixed F1..F11)? Do the enhanced textures look
  cleaner in-cockpit (deployed to `game/ADDON/`, rollback `game/ADDON.pre-hd-pack`, not yet
  visually confirmed)?
- **Analog external camera experiment**: the exe has `track_yaw_delta`/`track_pitch_delta`
  action tokens — try binding to pad axes (winmm R/U) + a mode-shifted right stick for chase-cam
  panning. Probe the tokens with `deck/probe/` first (unknown action names can error the parser).
  Note the memory-RE finding ([MEMORY-MAP-INDEX.md](MEMORY-MAP-INDEX.md)): the analog `pilot_*`
  COCKPIT-look actions are NOT wired to the input.map parser — the external `track_*` channels
  may or may not share that fate; that's what the probe answers.
- **Menu mouse / touchscreen still unsolved**: both fail to select in-game menus — it's the
  game's internal 640×480 cursor, not the input method. Candidates: gamescope scaling flags
  (`-w/-h/-W/-H`, `--force-grab-cursor`), a dgVoodoo cursor option, or matching the in-game
  resolution. Low priority (d-pad + A covers menus). Three-cursor analysis:
  [DECK-INPUT-SCIENCE.md](records/DECK-INPUT-SCIENCE.md).
- **Untested / beta**: the Option 2 "Racing" template (triggers = gas/brake) has never been
  user-tried; `deck/deck-install.sh` has never run end-to-end on a fresh Deck (watch:
  innoextract 1.9 may choke on GOG's Inno Setup 6.3 repacks — ship a static build from master
  with a "run setup.exe via Proton" fallback); `add-to-steam.py`'s user-id/GE-Proton autodetect
  is unverified on other machines.

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
