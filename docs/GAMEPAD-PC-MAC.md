# Interstate '76 with an Xbox gamepad — PC & Mac (the native winmm-joystick path)

*The Deck build uses Steam Input keyboard-emulation. On PC and Mac you can do better: the game has
native joystick support, so an Xbox pad drives it directly through the game's own axes — no
emulation. This is the SAME `joystick1` block our `input.map` already carries.*

## Why it just works (the Deck research, applied)

I76 is **winmm-joystick only** (`joyGetNumDevs`/`joyGetPosEx`, no DirectInput — confirmed in the
exe). That path is served natively on both platforms:

- **Windows (PC):** the OS feeds the Xbox pad to `joyGetPosEx` directly (XInput pads also expose a
  legacy joystick interface). Works out of the box.
- **Mac (Wine):** `winebus.sys` enumerates the pad (IOHID/SDL backend) → `dinput8` → `winmm`. This
  prefix has already enumerated an Xbox Wireless Controller (VID 045E, PID 0B20).

**Two rules from the Deck work that matter here:**
1. **Connect the pad BEFORE launching** — winmm-era games enumerate joysticks only at startup.
2. It's **`joystick1`**, not the phantom `joystick5` GOG shipped (a packager artifact). Our
   `input.map` already fixes this.

## The bindings (already in `input.map`)

| Pad control | Axis/button | Action |
|---|---|---|
| **Left stick** X / Y | `joystick1 Left/Right` / `Down/Up` | **steer** / **throttle** |
| **A** | `joystick1 Button1` | fire (`weapon_fire`) |
| **B** | `joystick1 Button2` | special 1 (nitrous slot) |
| **X** | `joystick1 Button3` | cycle weapon |
| **Y** | `joystick1 Button4` | handbrake (`e_brake`) |
| **D-pad** | `joystick1 HatUp/Down/Left/Right` | glance (look around) |

Keyboard/mouse stay live at the same time — all input methods coexist.

## Optional: throttle/brake on the triggers

More natural for a driving game. The triggers share **one** winmm axis (`Throttle`/Z — RT pushes
positive, LT negative, resting centered), so swap the throttle source in `input.map`:
```
throttle {
   - joystick1  Throttle      ← RT accelerate / LT brake (instead of left-stick Y)
}
steer {
   - joystick1  Left/Right    ← keep steering on the left stick
}
```
The right stick lands on `5thAxis`/`6thAxis` and is mostly unusable natively (winmm's 6-axis
ceiling) — leave camera glance on the D-pad/hat.

## Verify the pad is seen

Run the Wine joystick control panel against the prefix (Mac):
```
WINEPREFIX="$HOME/Applications/Sikarugir/Interstate 76 - Software (DxWnd).app/Contents/SharedSupport/prefix" \
"$HOME/Applications/Sikarugir/Interstate 76 - Software (DxWnd).app/Contents/SharedSupport/wine/bin/wine" control joy.cpl
```
The pad should list (often twice — as HID gamepad + XInput device); the test tab shows live
axes/buttons. If the game grabs a wrong/duplicate stick, set `Enable SDL=0` under
`HKLM\System\CurrentControlSet\Services\winebus` to force the single IOHID path.

**Do NOT rebind via the in-game Control Configuration menu** — it's buggy (appends/wrong-stick/
crashes). Edit `input.map` and relaunch. See [I76-GAMEPLAY-REFERENCE.md](I76-GAMEPLAY-REFERENCE.md)
for the chord/alternatives rules.
