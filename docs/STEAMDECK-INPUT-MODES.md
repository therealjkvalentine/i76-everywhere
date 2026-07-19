# Steam Deck Input Modes — advanced Steam Input for game ports

Reusable reference for hand-authoring `controller_neptune*.vdf` layouts for complex /
old games (I'76-style keyboard sims, CRPGs, flight sims). Everything here was verified
against primary sources: Valve's Steamworks docs, Valve's own shipped configs on a real
Deck (`~/.steam/steam/controller_base/basicui_neptune.vdf`), EmuDeck's shipped template
(`emudeck_controller_steamdeck_radial_menus.vdf`), and real exported community layouts
(GTA V Steam Controller config, Guild Wars 2 Deck layout). Sources at the bottom.

Our shipping model (established for Interstate '76): author the vdf in-repo, install to
`~/.steam/steam/controller_base/templates/` on the Deck over SSH, user applies via
**Controller Settings > Browse Configs > Templates**. See "Portability" for why this is
the right model for non-Steam shortcuts.

---

## 1. VDF anatomy (version 3, controller_neptune)

Top level `"controller_mappings"` contains, in order:

| Block | Purpose |
|---|---|
| `"version" "3"` | modern format (Deck exports are v3; old SC configs are v2) |
| `"title"` / `"description"` | shown in the template picker. Plain strings OR `#Token` referencing `"localization"` |
| `"controller_type" "controller_neptune"` | required for the Deck to list it as a Deck template |
| `"actions"` | action sets (one entry per full control scheme) |
| `"action_layers"` | overlay layers (optional) |
| `"group"` (many) | one per input-source behavior: `dpad`, `four_buttons`, `switches`, `trigger`, `joystick_move`, `joystick_mouse`, `absolute_mouse`, `scrollwheel`, `touch_menu`, `radial_menu`, `reference` |
| `"preset"` (one per action set/layer) | wires groups to physical sources via `group_source_bindings` |
| `"settings"` | global settings |

**Binding string = 4 comma-separated fields.** This is the single most useful
undocumented fact for discoverability:

```
"binding"    "key_press LEFT_SHIFT, Save State, EmuDeck_SaveState.png, #232323 #00AD00"
              ^command            ^label       ^icon                  ^bg-hex fg-hex
```

(verbatim from EmuDeck's shipped Deck template). The label is what Steam renders in the
configurator's binding list, in touch/radial menu slices, and in the on-change toast;
the icon (png) and colors render on menu slices. Our existing `key_press SPACE, Fire
weapon` comments are therefore not comments at all — **they are UI labels**. Keep them
human-readable everywhere.

`group_source_bindings` maps group id -> physical source + state:

```
"group_source_bindings"
{
    "6"      "switch active"
    "0"      "button_diamond active"
    "7"      "dpad active"
    "1"      "left_trackpad active"
    "59"     "right_joystick active modeshift"     // <- modeshift target, see §2
    "19"     "left_trackpad inactive"              // defined but not enabled
}
```

Sources: `switch` (all shoulder/back/start/select), `button_diamond`, `dpad`,
`joystick`, `right_joystick`, `left_trackpad`, `right_trackpad`, `left_trigger`,
`right_trigger`, `gyro`. States: `active`, `inactive`, `active modeshift`.
Group ids must be unique (duplicates silently overwrite — community vdf-editing guide).

---

## 2. Mode shifts (hold a button, another source is repurposed)

A mode shift temporarily swaps the *group* driving one source while a chosen button is
held; release reverts. Perfect for "hold L4 -> dpad becomes horn/lights/engine".

Two pieces, both required:

**(a) The shifted group is a normal `"group"`, registered in the preset with
`active modeshift`.** Verbatim from Valve's own `basicui_neptune.vdf`:

```
"preset"
{
    "id"        "1"
    "name"      "WebBrowser"
    "group_source_bindings"
    {
        "16"    "switch active"
        "58"    "right_joystick active"
        "59"    "right_joystick active modeshift"    // group 59 replaces 58 while shifted
        ...
    }
}
```

**(b) The shift button carries a `mode_shift <source> <group_id>` binding** as an
ordinary activator binding. Verbatim from the same Valve file (left trackpad click
shifts the right joystick into group 59):

```
"left_click"
{
    "activators"
    {
        "Full_Press"
        {
            "bindings"
            {
                "binding"        "mode_shift right_joystick 59"
            }
            "settings"
            {
                "interruptable"        "0"
            }
        }
    }
}
```

Same syntax confirmed in the community GTA V config (v2-era):
`"left_trigger_threshold"  "mode_shift right_trigger 41"` with preset entry
`"41"  "right_trigger active modeshift"`.

Rules and gotchas (Valve mode-shifting doc + Steam Input Wiki):

- **One modeshift per source** per action set ("Each device that can use an Input Style
  can have a single modeshift associated with it").
- **Targets can be**: dpad, button pad, mouse, joystick modes, gyro, touch/radial menus.
  **You cannot shift the `switches` group or trigger pull states** — those are the
  things that *hold* shifts, not the things that get shifted.
- Any digital input can be the shift button (bumpers, back grips L4/L5/R4/R5, trackpad
  click, trigger threshold). Back grips are ideal for sims: no thumb leaves a stick.
- Set the shift button's binding `"interruptable" "0"` (note Valve's spelling) so its
  own normal function doesn't also fire — exactly what Valve does above. Steam Input
  Wiki's alternative: make the normal function Interruptible + add a Long_Press with an
  empty binding (`controller_action empty_binding`).
- Mode shift is *hold-only*. If you need a latched switch, use an action layer (§3).

**I'76 example** — hold L4, dpad becomes utilities:

```
"group"
{
    "id"        "30"
    "mode"      "dpad"
    "inputs"
    {
        "dpad_north"
        {
            "activators" { "Full_Press" { "bindings" {
                "binding"        "key_press H, Horn, ,"
            } } }
        }
        "dpad_west"
        {
            "activators" { "Full_Press" { "bindings" {
                "binding"        "key_press L, Headlights, ,"
            } } }
        }
    }
}
```

with `"30"  "dpad active modeshift"` in the preset, and on `button_back_left`
(L4) inside the `switches` group: `"binding"  "mode_shift dpad 30"` +
`"interruptable" "0"`.

---

## 3. Action sets vs action layers

**Action sets** replace the *whole* control scheme (drive-set vs menu-set). **Layers**
overlay deltas on the current set — untouched inputs fall through to the base set
(Steamworks: layers "do not wholesale replace what is already active... but apply
small modifications"). Layers stack; later layers win conflicts; switching sets clears
all layers (Steamworks Action Set Layers doc).

VDF, verbatim from the Guild Wars 2 Deck layout (a real hand-shared
`controller_neptune.vdf`):

```
"actions"
{
    "Default"
    {
        "title"        "Default"
        "legacy_set"   "1"
    }
}
"action_layers"
{
    "Preset_1000001"
    {
        "title"             "Slot skills"
        "legacy_set"        "1"
        "set_layer"         "1"
        "parent_set_name"   "Default"
    }
    "Preset_1000002"
    {
        "title"             "Profession skills"
        ...
    }
}
```

Each set *and* each layer then gets its own `"preset"` block (preset `"name"` matches
the actions/action_layers key). In a layer's preset, only the groups you override are
listed.

**Switching bindings** are ordinary `controller_action` bindings (all observed in real
files — GW2 layout and EmuDeck template):

```
"binding"    "controller_action hold_layer 3 0 0, , "          // layer active while held
"binding"    "controller_action add_layer 2 0 0, , "           // latch a layer on
"binding"    "controller_action remove_layer 2 0 0, Unlock skills, , "
"binding"    "controller_action CHANGE_PRESET 2 1 1, Menus, , "      // switch action set
"binding"    "controller_action CHANGE_PRESET 32765 1 1, Return to Main Menu, , "
```

First argument = target preset/layer id (by position; GW2's first layer =
`Preset_1000001` is targeted as id 2 — Default set is 1 — so ids follow definition
order). `32765` is a magic id: community vdf guide documents it as "previous preset";
EmuDeck uses it as "return to main menu" from every sub-set. Trailing two args are
consistently `0 0` for hold/add/remove_layer and `1 1` for CHANGE_PRESET in shipped
files; author new bindings by cloning these. (Semantics of the trailing args are
undocumented — don't invent values.)

**Hold vs toggle:** `hold_layer` = hold-to-shift (like a modeshift but can rebind *any*
input, not just one source). `add_layer`/`remove_layer` on separate presses = toggle.
The Deck UI equivalents are "Hold Action Layer" / "Apply Action Layer" / "Remove
Action Layer".

**Sim community practice:** Elite Dangerous's famous configs (e.g. "Steam Falcon")
chain layers with radial menus — each radial slice applies a layer whose trackpad is
another radial, giving a menu *tree* covering 100+ bindings (Frontier forums guide).
Steamworks' own example is a vehicle game: base set + "car"/"boat" layer on top.
For I'76: a `Default` driving set + a hold-layer on L5 for salvage/utility, + a `Menus`
action set with dpad-as-arrows for the shell/Melee menus, switched by a Start long-press
or automatically (see `action_set_trigger_cursor_show`/`_hide` in Valve's basicui
settings — sets can auto-swap on cursor visibility, useful only if the game shows a
cursor in menus).

**Caveats (why we prefer modeshifts when a single source suffices):**

- **Stuck layers**: if the hold button is itself rebound inside the layer, the release
  event can be eaten and the layer sticks (Steam Input Wiki warns about exactly this).
  Never rebind the hold button inside its own layer; belt-and-braces fix is binding
  `remove_layer` on a Release_Press of the same button.
- Removing a layer releases any outputs it was holding and clears toggles mid-flight
  (Steam Controller forum reports) — don't put toggled states you need to survive
  (e.g. headlights) inside a transient layer.
- Applying an already-active layer is a no-op; changing sets clears layers (Steamworks).
- Discoverability of *which* layer is active is poor — always set a label on the
  switch binding and rely on Steam's on-change toast ("Display Action Set on Change").
- Steam Input Wiki's design advice, worth adopting verbatim as policy: "robust is good,
  simple is robust" — prefer chords/modeshifts, use few layers, never overlapping ones.

---

## 4. Touch menus and radial menus (trackpads)

Both are on-screen overlays with labeled, icon-capable slices — the single best
discoverability tool on Deck. Differences (Steamworks Touch Menus / Radial Menus docs):

| | touch_menu | radial_menu |
|---|---|---|
| selection | grid; finger *position* on pad selects | virtual pointer aimed from center |
| slice counts | fixed grids: 2, 4, 7, 9, 12, 13, 16 | free-form, up to 20 |
| activation | touch (no click needed) | direction + release/click |
| best for | muscle-memory hotbars (relative touch = fast) | deliberate pick-one-of-N wheels |

Practical slice count from shipped configs: EmuDeck uses 4–12 per menu; community sim
wheels (weapon select) sit at 4–8 — beyond ~8 radial slices get thin on a 1280x800
screen. Unbound slots render blank (touch) or don't render (radial).

VDF, verbatim from EmuDeck's shipped Deck template (`mode` can be `touch_menu` or
`radial_menu` — inputs are named `touch_menu_button_N` in **both**):

```
"group"
{
    "id"        "18"
    "mode"      "touch_menu"
    "name"      "Citra Hotkeys"
    "inputs"
    {
        "touch_menu_button_0"
        {
            "activators"
            {
                "Long_Press"
                {
                    "bindings"
                    {
                        "binding"        "key_press LEFT_SHIFT, Save State, EmuDeck_SaveState.png, #232323 #00AD00"
                    }
                    "settings"
                    {
                        "long_press_time"        "300"
                    }
                }
            }
        }
        "touch_menu_button_1"
        {
            "activators"
            {
                "Full_Press"
                {
                    "bindings"
                    {
                        "binding"        "key_press PAGE_UP, Pause/Play, EmuDeck_Pause.png, #232323 #00ADAD"
                    }
                }
            }
        }
    }
    "settings"
    {
        "touch_menu_button_count"        "12"
        "touch_menu_opacity"             "100"
        "touch_menu_scale"               "120"
        "touch_menu_position_y"          "78"
        "touchmenu_button_fire_type"     "0"
    }
}
```

Wire it in the preset like any group: `"18"  "left_trackpad active"` — or as a
**modeshift target** (`active modeshift`) so the wheel only exists while a grip is held.
Settings keys observed in shipped files: `touch_menu_button_count`,
`touch_menu_opacity`, `touch_menu_scale`, `touch_menu_position_x/y`,
`touchmenu_button_fire_type` (0 = on touch release, 2 = on pad click — matches the UI's
"button fire type"), `virtualmenu_center_bound` (radial: re-center behavior).

Icons: the 3rd binding field is a png. Valve ships a stock icon set; custom pngs go in
a `TouchMenuIcons/` folder relative to the game root (Steamworks Touch Menus doc) —
for a non-Steam shortcut that's the shortcut's Start Dir, worth testing before relying
on it; stock icons + colors always work. 4th field = `#background #foreground` colors.
`touch_menu_show_labels` toggles slice labels (labels ARE the binding's label field).

**I'76 use**: weapon-select / utility wheel on the left trackpad
(machine gun / oil / mines / dropped weapon...), labels + distinct colors per slice.
Radial + "fire on release" means: touch, glance, flick, done — self-teaching.

---

## 5. Activators (per-input press semantics)

Each input has an `"activators"` block; multiple activators coexist on one input.
Types (Steamworks Activators doc): `Full_Press` (regular), `Double_Press`,
`Long_Press`, `Start_Press` (fires on down, instant release), `Release_Press` (fires
on button-up), `Chord` (only while a designated other button is held).

Settings keys observed in real vdfs, mapping to the documented UI options:

| vdf key | UI name | notes |
|---|---|---|
| `"toggle" "1"` | Toggle | press = latch on, press again = off. Free "hold-to-toggle" for cruise/lights |
| `"interruptable" "0"` | Interruptible (off) | Valve's misspelling is canonical; `0` = fire immediately even if Long/Double press also bound |
| `"delay_start"` / `"delay_end"` | Fire Start/End Delay | ms; docs range 0.0–1.0 s |
| `"hold_repeats" "1"` + `"repeat_rate"` | Hold to Repeat (Turbo) + Repeat Rate | turbo for menu scrolling / chaingun in games that don't autorepeat |
| `"long_press_time" "300"` | Long Press Time | ms (EmuDeck uses 300) |
| `"doubetap_max_duration"` | Double Tap Time | ms; **Valve's typo, verbatim** — `doubetap`, not `doubletap` |
| `"haptic_intensity" "0-3"` | Haptics | give shifted/latched bindings a buzz for feedback |
| `"cycle" "1"` | Cycle Bindings | multiple `"binding"` lines fire alternately instead of together |

**The double/long-press tax (decide per input):** an interruptible regular press on the
same input as a Double_Press or Long_Press waits out the window before firing
(Steamworks: "Any interruptable activators on the same button will not fire if a double
press is fired"; "Release Press Activators set to Interruptible will not activate until
after the Double Tap Time has elapsed"). The window is `doubetap_max_duration` /
`long_press_time` — default double-tap window on current clients is ~300 ms. So **never
stack Double/Long_Press on a latency-critical input** (fire, brake). Fine on menu keys.
`interruptable 0` on the regular press removes the delay but then the regular press
fires *in addition to* the double/long press — usable when the single-press action is
harmless alongside.

Multiple bindings under one activator fire together (see EmuDeck's LEFT_CONTROL + `1`
mount binding in the GW2 layout) — that's how you do key combos like Shift+F1.

---

## 6. Gyro — verdict for old driving sims

Community consensus (Steam Deck forums / gyro guides): for keyboard-era games use
**"Gyro to Mouse"** (not joystick emulation) when the game reads mouse; enable-on-touch
of a stick/pad as the standard activation gate.

For I'76 specifically: steering is *digital keyboard* input — gyro cannot map to
left/right key taps in any useful way, and gyro-to-vjoy does nothing in a winmm game
that ignores XInput. **Skip gyro for steering.** The one defensible use is gyro-to-mouse
for freelook/turret-style camera *if* the game path reads relative mouse (our I'76
builds drive views by keys, so: leave `"gyro"` unbound or `empty_binding`, and say so in
the layout description to preempt "is gyro broken?" reports). For ports of
analog-capable racers (NFS-era), gyro-to-joystick roll steering is a liked option —
ship it as a *second* template variant, never the default.

---

## 7. Discoverability checklist (a layout must teach itself)

What Steam actually surfaces from the vdf — use all of it:

- [ ] **`title`** — versioned, purpose-first: `Interstate 76 - Option 2 v1 (Racing:
  triggers drive)`. Shown in Browse Configs > Templates.
- [ ] **`description`** (+ english `localization` block) — the ONLY free-text a user
  sees before applying. Put the 5-line control summary here, not in repo docs. Replace
  the copied Valve WASD boilerplate in our current templates.
- [ ] **Label field on every binding** (`key_press H, Horn, ,`) — renders in the
  configurator's per-input list, in Edit Layout, and on menu slices. No label = user
  sees raw `H`.
- [ ] **Touch/radial menus for anything past ~12 actions** — on-screen labels + icons +
  colors beat memorized chords. Icons via stock set or pngs; colors field for grouping
  (weapons red, comms blue).
- [ ] **Toast on set/layer/preset switches** — give the CHANGE_PRESET / add_layer
  binding a label ("Menus", "Utility layer ON"); enable Display Action Set on Change +
  haptic beep so state changes are felt and seen.
- [ ] **`haptic_intensity`** on modeshift/toggle bindings — physical feedback for
  invisible state.
- [ ] **Consistency conventions**: hold-grips = temporary (modeshift/hold_layer),
  face-press = latched, Start long-press = set switch. Same across all our ports.
- [ ] What Steam does NOT show: vdf `//` comments, group `"name"`/`"description"`
  fields (internal organization only). Don't rely on them for users.

---

## 8. Portability: shipping layouts for non-Steam shortcuts

**Verdict: community sharing is genuinely broken for non-Steam games; shipping template
vdfs into `controller_base/templates/` is the community-standard workaround and the
most portable option. Our approach is correct — keep it.**

The facts:

- Steam keys layouts to appid. Non-Steam shortcuts get a per-user synthetic appid, so
  **you cannot publish or browse community layouts for them** ("for non-steam games you
  can't save these configs publicly" — Steam Controller forums; confirmed by the
  long-running NeoGAF manual-sharing thread existing at all).
- On disk, a non-Steam shortcut's personal layout lands in
  `~/.local/share/Steam/steamapps/common/Steam Controller Configs/<accountid>/config/
  <lowercased shortcut name>/controller_neptune.vdf` — keyed by *shortcut name*, not
  appid (verified on our own Deck: `config/emulationstation/controller_neptune.vdf`).
  Writing there works but needs the account id, exact shortcut name, and a Steam
  restart — fragile, and it silently loses to later user edits. Fine for our own
  `install-on-deck.sh`, wrong for distribution.
- `steam://controllerconfig/<appid>/<configid>` share-links only exist for configs
  saved to Valve's cloud against a real appid — unusable for non-Steam shortcuts.
- The rename-shortcut-to-an-appid trick (name the shortcut `434050` etc. to borrow a
  Steam game's community configs) works but is user-hostile and breaks art/names.
- Tools: SteamTinkerLaunch writes `controller_neptune.vdf` into the per-game config dir
  (that's how it injects its own navigation config); BoilR/NonSteamLaunchers manage
  shortcuts + art but **do not install controller layouts**. No tool beats a template.
- Precedent: **EmuDeck and RetroDECK both ship layouts exactly our way** — vdf dropped
  into `~/.steam/steam/controller_base/templates/` (EmuDeck's are visible on our Deck;
  RetroDECK docs: "extract .vdf files into .steam/steam/controller_base/templates/ and
  select them as normal from the templates").

Requirements for a template vdf to appear on the Deck: correct
`"controller_type" "controller_neptune"`, `.vdf` extension, valid `title`. It then
shows for **every** game/shortcut under Browse Configs > Templates — which is also the
apply path: **Steam button > Controller Settings > current-layout tile > Templates >
ours > X (Apply). Three-ish taps, no files, no account ids.** Name templates so they
sort together and are self-evidently ours (`Interstate 76 - ...`).

One caveat to document per-port: templates are global, so a user with many ports sees
all of them — the game-name prefix in `title` is what keeps that sane. And Desktop Mode
ignores per-game layouts for non-Steam apps (long-standing Steam bug, ValveSoftware
GitHub #8904) — always test in Game Mode.

---

## Sources — dated, for future refresh

*All sources below were accessed/verified **2026-07-11 → 2026-07-12** against Steam client
**stable channel on SteamOS 3 (Steam Deck LCD)** and its `controller_neptune` **v3 template
format**. If you're picking this up years later: (1) re-pull Valve's shipped configs off any
Deck (`~/.steam/steam/controller_base/`) and diff the syntax against §2/§4's verbatim blocks —
Valve evolves the format in place; (2) the Steamworks partner docs are versionless and silently
updated, so treat the verbatim on-Deck files as ground truth over prose; (3) the canonical typos
(`interruptable`, `doubetap_max_duration`) are load-bearing — if they stop parsing, the format
version bumped.*

Primary (files inspected directly, 2026-07-11):
- `~/.steam/steam/controller_base/basicui_neptune.vdf` (Valve, on-Deck) — mode_shift + active modeshift + multi-preset syntax
- `~/.steam/steam/controller_base/templates/emudeck_controller_steamdeck_radial_menus.vdf` (EmuDeck, on-Deck) — touch/radial menus, activator settings, CHANGE_PRESET, binding label/icon/color fields
- [GTA V Steam Controller native config](https://github.com/GoldRenard/GTAVSteamControllerNative/blob/master/controller.vdf) — v2 modeshift example
- [Guild Wars 2 Steam Deck layout](https://github.com/jsantorek/steamdeck-gw2-layout/blob/main/controller_neptune.vdf) — action_layers, hold_layer/remove_layer, touch menus with custom icons

Valve documentation (versionless pages, accessed 2026-07-11):
- [Steamworks: Mode Shifting](https://partner.steamgames.com/doc/features/steam_controller/mode_shifting)
- [Steamworks: Action Set Layers](https://partner.steamgames.com/doc/features/steam_controller/action_set_layers)
- [Steamworks: Activators](https://partner.steamgames.com/doc/features/steam_controller/activators)
- [Steamworks: Touch Menus](https://partner.steamgames.com/doc/features/steam_controller/touch_menus) / [Radial Menus](https://partner.steamgames.com/doc/features/steam_controller/radial_menus)

Community (accessed 2026-07-11):
- [Guide: Editing .vdf steam controller files](https://steamcommunity.com/sharedfiles/filedetails/?id=932405100) — vdf structure, group_source_bindings states, CHANGE_PRESET 32765
- [Steam Input Wiki: Changing Things Up](https://github.com/SteamInputWiki/SteamInputWiki/blob/main/chapter-4/changing_things_up.md) — modeshift/set/layer UI + stuck-layer workaround
- [Steam Controller 112: Introduction to Modeshift](https://steamcommunity.com/sharedfiles/filedetails/?id=1645324863)
- [Steam Falcon: Elite Dangerous Steam Controller config](https://forums.frontier.co.uk/threads/steam-controller-configuration-steam-falcon.358080/) — layered radial-menu tree pattern
- [EmuDeck: Community Creations / template install](https://emudeck.github.io/community-creations/steamos/community-creations/) and [RetroDECK controller issue #573](https://github.com/XargonWan/RetroDECK/issues/573) — controller_base/templates as distribution channel
- [ValveSoftware/steam-for-linux #8904](https://github.com/ValveSoftware/steam-for-linux/issues/8904) — Desktop Mode ignores non-Steam layouts
- [Ryvaeus: Use Steam Input's Radial Menu](https://ryvaeus.com/blog/steam-input-radial-menu/) / [ResetEra: Virtual Menus on Deck](https://www.resetera.com/threads/virtual-menus-in-steam-input-are-amazing-on-steam-deck.649086/)
- Non-Steam sharing limitations: [Steam Controller forums](https://steamcommunity.com/app/353370/discussions/0/1635237606654389025/), [NeoGAF non-Steam config sharing thread](https://www.neogaf.com/threads/steam-controller-non-steam-game-config-sharing-thread.1125840/)
- Gyro for retro/KBM games: [Steam Deck forums gyro discussions](https://steamcommunity.com/app/1675200/discussions/0/597399921281226202/)
