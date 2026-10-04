# Weapons in memory — trainer / modding reference

*Measured live against GOG Gold `i76.exe` (MD5 `60ABF7BC…`, base `0x400000`, no ASLR).
Confidence: **[live]** verified in the running game · **[dump]** read from a memory dump ·
**[open]** not yet established.*

## The weapon definition table — `0x005D8800`, stride `0xD8` (216 bytes) **[live]**

The runtime form of the game's `.gdf` weapon definitions. Populated per mission with the
weapons that mission loads, so the contents change between missions — the *table address* is
static, its *contents* are not.

```
record (0xD8 bytes):
  +0x00  char[]   name, NUL-terminated   ("30cal MG", "Oil Slick", ".45 Handgun", ...)
  +0x5C  u32      type/class             (2 for 30cal MG)
  +0x60  u32      15
  +0x64  u32      200
  +0x68  float    3.3333
  +0x70  float    10.0
  +0x74  float    150.0                  (range? plausible for an MG in metres)
  +0x78  u32      1
  +0x7C  u32      DEFAULT AMMO           (2000 for 30cal MG - matches the HUD's initial value)
  +0x80  u32      1
  +0x84  float    0.2
  +0x88  char[]   muzzle-flash sprite    ("X1_MUZF1")
  +0x94  char[]   fire sound             ("wlmgun.wav")
  +0xA0  u32      1
  +0xA4  u32      240
  +0xA8  char[]   loop-start sound name  ("330cal_mg_on")
  +0xBD  char[]   loop-stop sound name   ("330cal_mg_off")
```

Live read of the table in an Instant Melee (ABX Leprechaun):

| idx | VA | name | `+0x7C` |
|---|---|---|---|
| 1 | `0x5D88D8` | `30cal MG` | 2000 |
| 2 | `0x5D89B0` | `Oil Slick` | 2000 |
| 3 | `0x5D8A88` | `.45 Handgun` | 268435455 (`0x0FFFFFFF` = unlimited) |
| 4 | `0x5D8B60` | `.45 Handgun` | 268435455 |
| 5 | `0x5D8C38` | `20mm Cannon` | 350 |
| 6 | `0x5D8D10` | `BloxDropper` | 10 |

(The same slot held `7.62mm MG` in an earlier mission — confirming the table is per-mission.)

**This is a definition table, not live state.** Writing `+0x7C` does not change the HUD, and
firing does not decrement it. It is the right place to read weapon *stats* and to mod defaults;
it is the wrong place to build an infinite-ammo trainer.

## Other weapon data in memory **[dump]**

| region | what |
|---|---|
| `0x0310xxxx` | large per-weapon records, stride `0x8C4`; names repeat at that interval |
| `0x03178xxx` | packed name list — `Aim-Nein`, `Mortar`, `FlameThrower`, `FireRite Rkt` appear here even when not loaded on the car |
| `0x005D88xx` | the definition table above |

Weapon names seen: `30cal MG`, `50cal MG`, `7.62mm MG`, `20mm Cannon`, `Oil Slick`,
`FireRite Rkt`, `FlameThrower`, `BloxDropper`, `Landmine`, `Aim-Nein Msl`, `Mortar`,
`.45 Handgun`, plus specials `NitrousOxide`, `Radar`.

## Live ammo + weapon slots — **[live] SOLVED**

A single **static** array. No pointer chase, no ASLR — ideal for a trainer.

```
base    0x005AAB0C          stride 0x4C (76 bytes)      16 slots (10 used in a melee)

  +0x00  ptr -> weapon object; ITS +0x00 is the GDF asset name  ("gmlight", "goilslck", ...)
  +0x04  ptr -> second weapon object (paired; role not yet established)
  +0x08  int   (168 / 180 / 400 ...)   per-weapon stat
  +0x0C  int   (15 / 60 / 30 ...)      per-weapon stat
  +0x10  int   (200 / 400 ...)         per-weapon stat
  +0x14  ptr   shared per-class object (same value across several slots)
  +0x1C  int   ***LIVE AMMO***         0x0FFFFFFF = unlimited
```

```
slot N ammo address = 0x005AAB0C + N*0x4C + 0x1C  =  0x005AAB28 + N*0x4C
```

**Verified by writing, not just by watching.** Writing `1234` to `0x005AAB28` made the HUD read
`30CAL MG 1234`; writing `7777` / `4242` to slots 0 and 1 made it read `30CAL MG 7777` and
`OIL SLICK 4242`. That is the test the previous attempt skipped.

**Re-confirmed in a guided session on a second install**: 50cal MG set to `3333` and Landmines
to `55`, both confirmed on screen by the player. Use `tools/vehicle/ammo-lock.py`
(`--set N [--hold SECONDS]`).

> **Do not hardcode a slot index.** A regen respawn rebuilds the car and *shifts which slots the
> player occupies* — observed moving from slots 0–3 to 5–8, and later the 50cal sitting at slot
> 6 with Landmines at slot 8. Identify the weapon by the car's **loadout signature** instead
> (e.g. `[~300, ~2000, 700, 25]` = 25mm / 50cal / Gas Launcher / Landmines), which is what
> `ammo-lock.py` does. Because the array itself is static, it is the reliable **anchor for
> finding things that move** — see [ARMOR-INVESTIGATION.md](ARMOR-INVESTIGATION.md).

A live melee (ABX Leprechaun, 3 AI cars), `tools/vehicle/dump-ammo-table.py`:

| slot | ammo | id (`[+0x00]+0x00`) | weapon |
|---|---|---|---|
| 0 | 2000 | `gmlight` | 30cal MG — **player** |
| 1 | 2000 | `goilslck` | Oil Slick — **player** |
| 2, 3 | `0x0FFFFFFF` | *(null)* | .45 Handgun (unlimited) |
| 4 | — | `gcmedium` | 25mm Cannon |
| 5 | — | *(unreadable)* | |
| 6 | 569 | `gfmedium` | Gas Launcher |
| 7 | 20 | `glandmin` | Landmines |
| 8, 9 | `0x0FFFFFFF` | *(null)* | |
| 10-15 | 0 | null pointers | unused |

**The weapon ID is the GDF asset name** (`gmlight` = `gmlight.gdf`), reached as
`[[slot+0x00]+0x00]`. That is the stable name-to-memory mapping; the numeric index into the
definition table at `0x5D8800` is *not* stable because that table is repopulated per mission.

**[open]** The array holds **every vehicle's** weapons, not just the player's — 10 slots for a
4-car melee. Slots 0/1 were the player's here, but slot-to-vehicle assignment (spawn order?) is
not established. Read `+0x00`'s GDF name to identify a slot rather than assuming an index.

### The old "not ammo" retraction was itself half wrong

An earlier note withdrew `0x005AAC58` / `0x005AACA4` as "some other decreasing counter". They
are in fact **slots 4 and 5 of this very array** — `0x5AAB28 + 4*0x4C` and `+ 5*0x4C` land
exactly on them. They were real ammo all along, just for weapons that were not on the *player's*
HUD, which is why writing to them appeared to do nothing.

Both the original claim and the retraction failed the same way: identifying a field by *where the
number moved* without ever establishing *whose* number it was.

### How it was found — the discriminator that worked

`tools/vehicle/find-ammo.py`. A free-running counter can imitate ammo across a single before/after
diff; it cannot survive **idle → FIRE → idle → FIRE**, because real ammo is *exactly constant*
across the idle windows. That collapsed ~3800 candidates to 35, and the winner
(`0x005AAB28`, −31 rounds in each of two 3 s bursts) was unmistakable.

> **GOTCHA — fire is `Enter`, not `Space`.** `input.map`'s comment header says "Space fire" and
> it is **wrong**; the `weapon_fire` block binds keyboard `Enter` and mouse `LeftBtn`. A first
> run fired Space, nothing happened, the HUD still read 2000, and every one of the 471
> "candidates" was noise. Read the binding block, not the comment.

## Car component / weapon slots — **[open]**

The vehicle-logic object is `[player_entity + 0x108]`, but the older `+0xa71c` /`+0xa738`
weapon-array offsets did **not** resolve on this build (the pointer scan found none). The
16-record, stride-`0x90` component array (armor/engine/tyres, integer tenths) is documented in
the main engine reference; per-field offsets inside a record still need a watchpoint.

## Equipping weapons from the UI — **[live]**, and it works

**Retracted:** an earlier note here said *"`CONFIGURE CHASSIS` is disabled in Instant Melee"*.
It is not. It opens fine from the AUTO MELEE • DRIVER ENTRY FORM and is the way to change
weapons. (The old note also described the slot control as *cycling* through weapons; on this
form it opens a scrollable picker instead.)

All coordinates below are **UI units = OS cursor coordinates**, read straight off a `Capture-UI`
screenshot. See [CONFIG-OPTIONS.md](CONFIG-OPTIONS.md) §3 — do not sweep for these.

### Route

`MELEE > AUTO MELEE > INSTANT MELEE` → **DRIVER ENTRY FORM** → `CONFIGURE CHASSIS` (536, 429)
→ **CHASSIS CONFIGURATION FORM**.

| control | UI coord | notes |
|---|---|---|
| `CONFIGURE CHASSIS` | (536, 429) | on the driver entry form |
| weapon slot `#1 Top` arrow | (258, 174) | opens the weapons picker |
| weapon slot `#1 Dropper` arrow | (258, 190) | rows are ~16.8 units apart |
| `Hand` slot arrow | (258, 258) | |
| picker: scroll up / down | (261, 124) / (261, 349) | **one row per click** |
| picker: first list row | (300, 161) | rows ~16.8 apart, 11 visible |
| picker: `CANCEL` | (359, 357) | |
| `PARTS CATALOG` / `DONE` / `CANCEL` | (238,460) / (400,460) / (563,460) | |
| `RENAME` (variant) | (340, 27) | toggle — see the gate below |
| A.I. DRIVERS `[-]` / `[+]` | (159, 295) / (206, 295) | driver entry form |
| AREA list rows | x≈80, y = 157/174/190/207/225/242 | Crater…Tombstone |
| `ENTER AREA` | (299, 461) | |

Verified live: selecting **Napalm Hose** into `#1 Top` changed the slot text from `30cal MG`,
redrew the chassis diagram's top mount, and moved total weight 2002 → 2072 LBS.

### The 28 weapons offered for a top mount (ABX Leprechaun)

In picker order. They come in **turret / fixed pairs**, with the mortars unpaired:

| # | name | # | name | # | name | # | name |
|---|---|---|---|---|---|---|---|
| 1 | 30mm Turret | 8 | Napalm Hose | 15 | Gas Lnch Trt | 22 | 30cal Turret |
| 2 | 30mm Cannon | 9 | 25mm Turret | 16 | Gas Launcher | 23 | 30cal MG |
| 3 | 7.62 Turret | 10 | 25mm Cannon | 17 | EZK Mortar | 24 | FireRite Trt |
| 4 | 7.62mm MG | 11 | 50cal Turret | 18 | Cluster-Bomb | 25 | FireRite Rkt |
| 5 | DrRadar Trt | 12 | 50cal MG | 19 | WP Mortar | 26 | Flame Turret |
| 6 | DrRadar Msl | 13 | Aim-Nein Trt | 20 | 20mm Turret | 27 | FlameThrower |
| 7 | Napalm Trt | 14 | Aim-Nein Msl | 21 | 20mm Cannon | 28 | HE Mortar |

Enumerate again with `autotest/setup/enum-weapon-picker.ps1` (pages the list and saves a capture per
page). Other slots (dropper, rear, hand) offer different subsets — not yet enumerated.

### **BLOCKER: saving a modified loadout needs typing, and typing cannot be injected**

Clicking `DONE` after any change raises a modal **"RENAME VARIANT TO SAVE"** — the game refuses
to leave the form with a modified *stock* variant. Confirmed hard-gated: dismissing the dialog
and clicking `DONE` again re-raises it.

The rename state machine, measured:

1. `RENAME` (340,27) is a **toggle**. Armed → a caret appears (`Econo_`) and the drawn cursor
   **freezes** (the game stops tracking the mouse while waiting for keys).
2. **Any click cancels the edit**, including clicking the field itself.
3. The VARIANT field is **not** directly clickable — hovering it shows a *prohibited* cursor.
4. **No injected keystroke reaches it.** Tried and failed: `keybd_event` with virtual-key codes,
   `keybd_event` with `KEYEVENTF_SCANCODE` (the path that works for driving), and posted
   `WM_CHAR`. Modifiers were verified not stuck (`GetAsyncKeyState` clear for ALT/CTRL/SHIFT).

This is consistent with the long-standing observation that the 2D shell ignores injected keys.

**SOLVED — go around the UI instead.** The loadout is a file: `ADDON/*.vcf`. Overwriting one
sets weapons and armor with no menu interaction at all, verified live. See
[CAR-CONFIG.md](CAR-CONFIG.md) for the format and `autotest/setup/make-test-variant.py`.

> **Retracted:** an earlier version of this section said the AUTO MELEE MAKE/MODEL (613,407)
> and VARIANT (443,427) arrows "do not cycle — the car is fixed". Wrong on both counts. The
> VARIANT arrow opens a **picker list** (Econo / GT / GTA / Jade's Car), and the car is not
> fixed. The clicks that produced that conclusion were being swallowed by a foreground popup.

### GOTCHA — modal dialogs hang `Force-Foreground`

While the game sits in one of its own modal dialogs the main window stops pumping, and
`ShowWindow` / `BringWindowToTop` / `SetForegroundWindow` / `AttachThreadInput` all block with
no timeout. That cost a 120 s harness timeout, and worse, **the clicks queued behind it never
fired** — so the dialog looked unclickable when nothing had actually clicked it.
`focuslib.ps1` now returns early if the window is already foreground and probes with
`SendMessageTimeout(WM_NULL, SMTO_ABORTIFHUNG)` before touching the blocking calls.
`SetCursorPos` + `mouse_event` keep working throughout — click modal dialogs directly.

## Cursor positioning — solved

The OS cursor position **is** the engine's 640x480 UI coordinate, 1:1; the earlier "standing
obstacle" framing and its two fitted calibrations were wrong. Workflow is now
`Capture-UI` → read the coordinate off the image → `Click-UI` it. Full derivation and the
reason the old measurements failed: [CONFIG-OPTIONS.md](CONFIG-OPTIONS.md) §3.
