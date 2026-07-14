# Control doctrine — two tiers, so critical actions never depend on a Steam Deck

*Written 2026-07-14. The problem this solves: the Deck config is gorgeous, but it leans on things
that **only exist on a Steam Deck running Steam Input** — trackpad label-wheels, back grips
(L4/L5/R4/R5), mode/menu shifts, R3 look-at-target, and keyboard/mouse **emulation**. A person
playing on a plain Xbox pad on PC or Mac (or a Deck user who turns Steam Input off) has none of
that. So we split the control design into two tiers with a hard rule between them.*

> **The rule:** every action a player **needs to drive and fight** must be fully reachable in the
> **BASELINE** tier. The **CONVENIENCE** tier only *adds* speed and discoverability on top. No
> critical action may live *only* in the convenience tier.

---

## Tier 1 — BASELINE (any Xbox controller, no Steam Input)

**What it is:** the game's own native gamepad support. I76 is a **winmm-joystick** title
(`joyGetPosEx`, no DirectInput/XInput API — confirmed in the exe). Windows feeds an Xbox pad to that
legacy joystick interface directly; on Mac, Wine's `winebus.sys` → `dinput8` → `winmm` does the
same. So the pad drives the game through the game's **own `input.map` `joystick1` bindings** — zero
Steam Input, zero emulation. This is also exactly what a Deck falls back to if Steam Input is off.

**Two hard constraints from the winmm era:**
1. **Connect the pad BEFORE launching.** winmm enumerates joysticks once, at startup.
2. It must bind **`joystick1`**, not the phantom `joystick5` GOG's packaging left behind.

**What baseline must cover (the critical set):** steer, throttle/brake, fire, cycle weapon,
handbrake, one active-special (nitrous), and camera glance. All of these are in `input.map`'s
`joystick1` blocks — see [input.map.reference](input.map.reference) and the layout table in
[GAMEPAD-PC-MAC.md](GAMEPAD-PC-MAC.md).

**What baseline does *not* try to do:** navigate the game's **menus** with the pad. I76's menus are
mouse/keyboard-driven; a native joystick doesn't move a menu cursor. Baseline players use
keyboard/mouse for menus (all input methods are live simultaneously — the pad doesn't lock them
out). The convenience tier is what makes menus pad-navigable (A→Enter, stick/dpad→cursor).

### Baseline layout (native `joystick1`)

| Pad control | winmm channel | Action | `input.map` |
|---|---|---|---|
| Left stick X | `Left/Right` | **steer** (analog) | `steer` |
| Left stick Y | `Up/Down` | **throttle/brake** (analog) | `throttle` |
| A | `Button1` | **fire** (contextual) | `weapon_fire` |
| B | `Button2` | **special 1** (nitrous slot) | `special1` |
| X | `Button3` | **cycle weapon** | `weapon_cycle` |
| Y | `Button4` | **handbrake** | `e_brake` |
| D-pad | `HatUp/Down/Left/Right` | **glance** (look around) | `pilot_glance_*` |

*Optional swap (more natural for driving): move `throttle` from left-stick Y to the **triggers**
(`joystick1 Throttle` — RT accel / LT brake share one winmm axis). Documented in GAMEPAD-PC-MAC.md.*

**Status: proposed, needs one field-test.** Two things can only be resolved on real hardware with a
real pad — the **device token** (`joystick1` vs the bare `Joystick` the live file currently uses)
and the **button numbering** (whether A really is `Button1`, etc.). The decode sheet in
GAMEPAD-PC-MAC.md walks the user through confirming both in ~2 minutes. Until confirmed, treat the
button/axis numbers as assumed, not verified.

---

## Tier 2 — CONVENIENCE (Steam Deck / Steam Input only, additive)

**What it is:** the Steam Input layer configured in
[`deck/controller_neptune_i76.vdf`](../deck/controller_neptune_i76.vdf) ("Option 1 v8, all-in-one
wheel"). Steam Input **captures** the physical controller and re-emits **keyboard + mouse** events,
which is why `input.map` also carries a full WASD + mouse binding set — that's the sink for this
tier's emulation, *not* a second baseline.

**What it adds (never the sole home of a critical action):**
- **Left-trackpad touch-menu wheel** — labeled slices for utilities/weapons (map, poetry, horn,
  binoculars, hardpoints). Discoverability tool; the same actions also have direct bindings.
- **Back grips L4/L5/R4/R5** — targeting, handbrake, extra specials.
- **R3 look-at-target**, right-stick glance, mode shifts (hold L1 → alt layer).
- **A → Enter/click** so the pad navigates menus and skips cutscenes.

**Why it can't be the baseline:** none of trackpads, back grips, R3-as-button-plus-look, or
keyboard-emulation exist on a bare Xbox pad. If a critical action lived only here, a PC/Mac pad
player (or Steam-Input-off Deck) would be unable to perform it.

---

## How the two tiers coexist in one `input.map`

`input.map` is a **single file** shipped to every platform. It carries **both** binding sets at
once, and I76 lets all input methods run simultaneously:

- **On the Deck with Steam Input ON:** the physical pad is consumed by Steam and re-emitted as
  **keyboard/mouse** → the game's WASD + mouse bindings fire. The `joystick1` blocks are **inert**
  (the game sees no winmm joystick, because Steam took the device). Convenience tier is live.
- **On PC/Mac with a bare pad (Steam Input off):** the pad enumerates as a **winmm joystick** →
  the `joystick1` blocks fire. Keyboard/mouse bindings stay available for menus and desktop players.
  Baseline tier is live.

Because they target different sinks, the two sets don't fight — **as long as the same physical
device isn't delivered to the game twice.** The one failure mode to watch: a Deck (or PC) setup
where Steam Input emulates keyboard/mouse **and** the raw pad is *also* visible to winmm → double
input (stick both steers via joystick1 AND via emulated WASD). If steering ever feels doubled or
fights itself, that's the cause; the fix is to ensure Steam Input fully captures the device (it
does in the current Deck config, which is why driving is clean there).

### The alternatives rule (don't make a chord by accident)

To give one action **two bindings** (keyboard OR pad button), use **separate blocks** with the same
action name. Multiple `+` lines *inside one block* mean a **chord** — all required at once (this bit
`special1` before). See the chord trap in [I76-GAMEPLAY-REFERENCE.md](I76-GAMEPLAY-REFERENCE.md).

```
special1 { + keyboard Six }         ← 6 works on its own
special1 { + joystick1 Button2 }    ← OR the B button      (correct: two alternatives)

special1 { + keyboard Six
           + joystick1 Button2 }    ← WRONG: chord, needs 6 AND B together
```

---

## Doctrine checklist (apply to every control change)

- [ ] Does this action belong to the **critical set** (drive/fire/cycle/handbrake/special/glance)?
      If yes, it **must** have a `joystick1` binding, not only a Deck-wheel/back-button binding.
- [ ] If it's convenience-only (trackpad wheel slice, mode shift, look-at-target) — fine, but
      confirm the critical actions it *duplicates* also exist in baseline.
- [ ] New pad binding uses a **separate block** (alternative), never a chord, unless a chord is
      intended.
- [ ] Probe any **unknown** `input.map` action token before committing (`deck/probe/`) — unknown
      names can error the parser at load.
- [ ] Baseline changes get field-tested with the **actual Xbox pad on Mac/PC** (pad connected
      *before* launch); Deck-only changes get tested in **Game Mode**.
