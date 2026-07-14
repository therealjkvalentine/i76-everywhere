# Universal input remapper — AutoHotkey inside the container

*One remapper for all three platforms. The game runs under Wine (Mac), Proton (Deck) and
natively (Windows) — so instead of a per-OS tool (Karabiner on Mac, Steam Input on Deck,
X-Mouse on Windows), we run a single **Windows-native** remapper INSIDE the same prefix
everywhere: **AutoHotkey v1.1.37.02**, config checked into this repo as
[`../i76-remap.ahk`](../i76-remap.ahk). Status 2026-07-14: installed + verified headlessly on
the Mac wrapper (boot, hooks, cleanup); wheel remap shipped briefly and was **removed after a
field regression** (stuck gear key killed WASD — see the wheel warning below); **buttons 4/5
in-game test still pending user field run.***

## Why this exists

The I76 engine knows **exactly three mouse buttons** (`LeftBtn/RightBtn/MiddleBtn`, verified
in the exe) and `input.map` can't see anything else. But buttons 4/5 *do* exist at the
Windows layer — Wine's Mac driver maps physical button N≥4 to `XBUTTON1/XBUTTON2`
(`winemac.drv/mouse.c`: `data = 1 << (button - 3)` with `MOUSEEVENTF_XDOWN`). A remapper
inside the container turns those into **keys**, which `input.map` binds like any other. Since
the game itself never binds buttons 4/5, the remap is **purely additive** — even if hook
suppression ever failed, nothing double-triggers.

## Tool decision (evaluated 2026-07-14)

| Tool | Verdict |
|---|---|
| **AutoHotkey v1.1.37.02 (U32)** | **Picked.** Single portable exe, famously Wine-compatible, plain-text config (repo-friendly, agent-friendly), mouse buttons 4/5 + wheel + chords + joystick polling, `DllCall` = plausible future host for force-feedback injection experiments. v1.1 is upstream-deprecated but final-stable; v2 needs newer OS APIs and buys us nothing here. |
| JoyToKey / Joy2Key | Joystick→key only — can't touch mouse buttons. GUI-first, closed. |
| antimicroX | Gamepad-only, drags a Qt runtime into the prefix. (Fine as an OS-side tool on Deck, but that's not one-config-everywhere.) |
| X-Mouse Button Control | Mouse-only, closed, GUI-config. |
| reWASD / Interception / vJoy / ViGEm / HidHide | Kernel drivers — can't load under Wine/Proton at all. |

## Current bindings (`i76-remap.ahk`)

| Physical input | Sends key | input.map action |
|---|---|---|
| Mouse button 4 ("back") | `6` | `special1` — the default nitrous slot |
| Mouse button 5 ("forward") | `7` | `special2` |

Edit the `.ahk`, re-run `./setup-input-remapper.sh`, relaunch the game. Keys on the right are
engine key names already bound in [`input.map.reference`](input.map.reference).

**The wheel is deliberately unbound — never remap it.** AHK v1 officially does *not* support
the remap syntax for the wheel ("The following keys are not supported by the built-in
remapping method: The mouse wheel") because wheel notches have **no release event**: the
destination key goes down and never comes up. Field regression 2026-07-14: `WheelUp::=`
shipped briefly; one trackpad scroll (two-finger/momentum scrolling counts) left `=` — the
`shift_up` gear key — logically stuck, pegging the transmission and killing WASD until the
session restarted. It passed the load-time syntax check (the flaw is semantic, input-driven).
The setup script now hard-fails on bare wheel remaps; if a wheel binding is ever wanted, use
an explicit full-press hotkey (`WheelUp::SendEvent {F6}`) on a harmless action and field-test
with momentum scrolling first.

**Second mechanism (the one that killed steering, not just throttle): modal-dialog focus
theft.** A momentum-scroll burst exceeding `#MaxHotkeysPerInterval` (then 500; lab-measured
trip at exactly ~500 activations/2 s) pops AHK's modal warning dialog *inside the Wine
session*. It steals foreground focus from the game and hides behind DxWnd's HideDesktop
backdrop — the game silently stops receiving **all** keyboard input (A/D included). Rule now
baked into the config: **no construct that can ever raise a modal dialog** —
`#MaxHotkeysPerInterval 200000` + `#ErrorStdOut`, and only discrete-button hotkeys (which
can't burst). The `--test` harness also refuses to run while i76.exe is live, so probe
injections never reach a real game.

## Verified facts (don't re-derive)

- **AHK 1.1.37.02 U32 runs clean under the wrapper's Wine 10 wow64** (`A_PtrSize=4`).
- **Keyboard AND mouse LL hooks install and see injected events in this prefix** — proven by
  `./setup-input-remapper.sh --test` (SendLevel-1 `SendEvent` triggers level-0 `$F13::` and
  `XButton2::` hotkeys, including an injected `{Click X2}`).
- **`SendEvent` only.** AHK uninstalls its own hooks during `SendInput` playback, so
  SendInput can never self-trigger — and it's the mode with Wine quirks. The shipped config
  keeps AHK's default send mode (Event). Do not add `SendMode Input`.
- **No `#IfWinActive` scoping on Wine**: the script only lives while the game session lives,
  and Wine hooks only see input while a Wine window has focus. On native Windows, wrap the
  remaps in `#IfWinActive ahk_exe i76.exe` if you run the script globally.
- The old **virtual desktop** (`Explorer\Desktops → i76`) is **not active** in the DxWnd-era
  prefix (`AppDefaults\i76.exe\Explorer` is empty) — AHK and the game share the default
  desktop, so hooks reach the game. If a virtual desktop is ever reinstated, give
  `AutoHotkeyU32.exe` the same `Desktop` value or hooks will miss.

## Install

### Mac (the Sikarugir wrapper) — automated
```sh
./setup-input-remapper.sh          # download (sha256-pinned) + install + deploy config
./setup-input-remapper.sh --test   # syntax check + hook smoke test under Wine
./setup-input-remapper.sh --revert # remove; the launcher then skips it
```
The launcher stub ([`../i76-launch-stub.swift`](../i76-launch-stub.swift)) auto-starts
`C:\AutoHotkey\AutoHotkeyU32.exe C:\AutoHotkey\i76-remap.ahk` right after DxWnd when both
files exist, and its `reap()` kills it with the rest of the session (verified: 0 leftovers).
Rebuilding stubs re-signs the app → macOS re-asks the microphone question once — deny again.

### Steam Deck (Heroic + Proton)
1. Copy `AutoHotkeyU32.exe` + `i76-remap.ahk` into the game prefix at
   `drive_c/AutoHotkey/` (same layout as the Mac wrapper).
2. Copy [`../i76-with-remap.bat`](../i76-with-remap.bat) next to `i76.exe` and point Heroic
   at it (game settings → select alternative exe). The bat starts AHK, runs the game,
   and kills AHK on exit. (`start` resolves through Wine's cmd, which Proton ships.)

### Native Windows
Same two options: install AutoHotkey v1.1 (or drop the portable exe in `C:\AutoHotkey`) and
either launch via `i76-with-remap.bat` or run the script globally with the `#IfWinActive`
guard noted above.

## Future: force feedback injection

FFB on Mac is still a dead end at the Wine layer (evdev-only backend — see
[FORCE-FEEDBACK-AND-VISUALS.md](FORCE-FEEDBACK-AND-VISUALS.md)). But an in-container agent
that already hooks input is the natural host for experiments where FFB *is* reachable
(Deck/Windows): AHK's `DllCall` can poke `winmm`/DirectInput, or spawn/host a dedicated shim.
Parked idea, not a promise.
