# Interstate '76 on Deck — the input pipeline, scientifically

*You asked: "why so many troubles with controls on this one?" and "give me a path to understanding
all of the components that hand off the controls and narrowing down which one causes which
behavior." This is that document.*

## 1. Why THIS game is hard (the honest answer)

Modern games read a gamepad through one API and Steam Input speaks it natively. I76 is a **1997
winmm game with a config-file input layer and point-and-click menus**, so every press crosses SIX
hand-offs, and different inputs take **different paths** through them:

```
[Deck hardware]
   │ (1) Steam Input — our .vdf config decides: emit a KEY? a MOUSE event? a VIRTUAL-PAD axis?
   ▼
[SteamOS virtual devices]  ← keyboard/mouse = uinput events; stick = virtual XInput pad
   │ (2) session — Game Mode (gamescope: one fullscreen surface, cursor scaled)
   │                vs Desktop Mode (Plasma: real windows, real focus, real cursor)
   ▼
[Wine/Proton]
   │ (3a) keys/mouse → the FOCUSED Wine window's message queue
   │ (3b) virtual pad → winebus → dinput8 → winmm joyGetPosEx   (focus-independent, polled!)
   ▼
[the game]
   │ (4) i76.exe reads: keyboard via user32, mouse via GetCursorPos/clicks, stick via winmm
   │ (5) input.map maps device channels → actions (steer, weapon_fire, …)
   ▼
[action on screen]
```

Three structural quirks do most of the damage:

- **Keyboard/mouse need window FOCUS; the winmm joystick does not** (it's polled). In Desktop Mode
  the engine renders in a **separate window** from the shell — so *analog throttle kept working
  while Space/arrows/M appeared dead*: the keys were going to whichever window had focus, the
  joystick worked regardless. This is the signature of a **focus split**, not a broken config.
- **Menus are point-and-click at 640×480** and the game reads the *absolute* cursor. Any window
  offset/scaling mismatch (Desktop Mode windows) makes clicks land where the menu isn't — cutscenes
  skip (any click anywhere) but items don't select. Fullscreen-single-surface (Game Mode) removes
  the offset; `A = Enter` (v3) bypasses the cursor entirely for menu confirm.
- **input.map sinks can list several analog sources** (`joystick1` + `mouse`). The game's arbitration
  between them is undocumented — with the OS cursor parked, the mouse source can pin an axis. That
  was the top suspect for *steer dead / throttle alive*; the Deck's input.map now lists **only
  joystick1** on both (the mouse-analog experiment moved to `input.map.with-mouse-analog`).

## 2. Symptom → layer fingerprint (what your report already proved)

| Your observation | What it fingerprints |
|---|---|
| Analog accel/brake works in-sim | Steam Input virtual pad → winmm chain is ALIVE end-to-end (layer 1–3b–5 good for Y) |
| No steering from the same stick | winmm X either not emitted (probe will show) or consumed by the mouse source in input.map (now removed) — NOT focus, NOT the game |
| B and ⧉ both toggle the in-game menu | Both were bound to ESC — and proves **⧉ Select = `button_menu`** in Valve's schema (fixed: Start=pause, Select=map) |
| A skips cutscenes but won't select menu items | Clicks arrive (layer 1–3a fine) but **coordinates are offset** (layer 2/4 mismatch) — v3 adds `A = Enter` which needs no cursor |
| Space/arrows/M/N dead in-sim, ESC alive | **Focus split** between shell + windowed engine (layer 2/3a); ESC is handled by both windows |
| Right stick moves menu but doesn't glance in-sim | Same focus split — it emits arrow *keys* (menus get them; the sim window didn't) |
| Trackpad radial (M/N/R/K) stopped in-sim | Same focus split — they're keys too |

Note the pattern: **everything dead in-sim is a keyboard/mouse emulation; everything alive is
joystick or ESC.** One cause, many symptoms.

## 3. The instrument: measure, don't guess

Two probes now exist, one per boundary:

**A. `I76 Input Probe` (new Steam shortcut on the Deck).** A tiny Windows console tool
([source](../deck/probe/i76-input-probe.c)) that reads the SAME APIs the game reads — `joyGetPosEx`
(all axes/buttons), `GetAsyncKeyState` (every key we bind), `GetCursorPos` — and logs everything for
120 s to `~/Games/Interstate76/probe/i76-probe.log`. Protocol:
1. In Steam, open **I76 Input Probe** → controller icon → apply the **same template** as the game.
2. Launch it; for 2 minutes press every input (sticks in circles, each trigger, each button, dpad,
   trackpads).
3. Quit. The log now shows exactly what Steam Input + Proton delivered *at the game's API boundary*
   — with no game logic involved. Anything that appears here but not in-game = the game's layer
   (input.map / focus). Anything missing here = Steam Input/Wine's layer.

**B. `evdev-tap.py` (Linux side, over SSH).** Lists `/dev/input` devices and streams events from
Steam Input's virtual devices — what Wine *receives* before translating. Distinguishes "Steam Input
never emitted it" from "Wine dropped it."

With A + B, every one of the six layers is pinned between two measurements — no more guessing.

## 4. What changed in this round (v3)

- **Fullscreen/focus**: dgVoodoo is already `FullScreenMode=true`; the windowed engine + focus split
  + menu-mouse offset are all **Desktop Mode** artifacts. **Test in Game Mode** (Steam button →
  Power → Switch to Game Mode) — gamescope composits one fullscreen surface and scales the cursor.
- **FPS counter removed** (it was our `dxvk.hud` debug line in `dxvk.conf`).
- **Steering de-confounded**: Deck `input.map` steer/throttle now read **joystick1 only**.
- **A = Enter + click** → menu confirm that ignores cursor offset, still skips cutscenes.
- **Start = pause (Esc), ⧉ Select = map (M)** — matching your "Select shouldn't confirm" call.
- **Option 2 (Racing)** now exists as a second template: triggers = gas/brake, bumpers = fire/cycle,
  stick = steer, A=confirm, B=reverse, X=fire-all, Y=view, R4=handbrake, L3=horn, R3=binoculars.
- Templates are **versioned in the title** ("Option 1 v3", "Option 2 v1") so we always know what's
  loaded. Because you already selected the template, **editing the template file + restarting Steam
  hot-updates your active config** — no UI steps needed for future tweaks.

## 5. Your decode sheet (fill in, I'll fix in minutes)

When you test, note per input — the shorthand is enough:

```
L-stick L/R : steers? analog?      L-stick U/D : gas/brake analog?
R2 / L2     : fires / fire-all?    R1 / L1     : cycles / targets?
A           : menu confirm? cutscene skip? (in-sim: anything?)
B / X / Y   : esc? reverse? view?  L3 / R3     : handbrake? untarget?
D-pad NSEW  : engine/lights/horn/binoc?
L-trackpad NSEW + click : map/notepad/radar±/engine?
R-trackpad  : cursor moves in menu? click selects?
Start / ⧉  : pause? map?
And: Game Mode or Desktop Mode when you tested; engine fullscreen this time?
```

## 6. Round-2 results (user field test) — three more layers decoded

The user's Game-Mode test confirmed the focus-split theory: **steering, fullscreen, menu-confirm,
and firing all came alive at once.** Residue decoded:

- **Trackpad "double-tap" on map/notepad**: v3's rebuilt trackpad group dropped Valve's
  per-activator `settings` (`repeat_rate`, `haptic_intensity`) and group `edge_binding_radius`,
  and added a `click` input Valve never had. v4 restores Valve's structure verbatim (keys swapped
  only). Lesson: **surgical binding swaps beat structural rebuilds** — Valve's activator settings
  are load-bearing.
- **Right stick moved menus but didn't glance in-sim**: menus read arrows as Windows VK codes;
  the sim reads `KEYBOARD.MAP`-style scancode tokens where extended arrows are `Grey*Arrow` —
  the same token split we hit on macOS, opposite direction. Fix: `input.map` now binds glance to
  **both** flavors (separate alternative blocks).
- **"Y does too many things"**: Y sent `V` = the game's *dash/combat-view toggle* (looks like
  hide-dash + zoom). Real cameras are fixed **F-keys** in `gamekey.map` (F1 cockpit, F3 chase…).
  v4: Y = F3 external, double-tap Y = F1 cockpit.

### Option 1 v4 (live)
| Input | Action | | Input | Action |
|---|---|---|---|---|
| L-stick | steer + throttle (analog) | | A | confirm / select / skip (Enter+click) |
| L3 | horn | | B | cycle weapon (Tab) |
| R-stick | glance ←→↑↓ | | X | reverse |
| R3 | look at target (E) | | Y | ext view (F3) · double-tap = cockpit (F1) |
| R2 | fire weapon (Space, hold repeats) | | RB | handbrake (C) |
| L2 | fire secondary (hardpoint 2) | | LB | next target (Y) |
| D-pad | arrows: menu nav + glance | | Start / ⧉ | pause / map |
| L-trackpad | ↑map ↓notepad ←radar-range →radar-cam | | L4/L5 | engine start / lights |
| R-trackpad | mouse + click | | R4/R5 | target nearest / binoculars |
