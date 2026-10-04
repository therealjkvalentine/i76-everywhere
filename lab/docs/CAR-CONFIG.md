# Car configuration — the `.VCF` format

**The whole car setup — which chassis, which skin, armor, and the weapon loadout — is a small
readable file, not heap state.** Editing one changes what the game loads. This is the practical
route for loadout testing, and it sidesteps the menu's rename gate entirely.

*Verified live against GOG Gold. Confidence: **[live]** confirmed in the running game.*

## Where they live

| path | what |
|---|---|
| `ADDON/vehscn.vcf` | **the player's current car** — the game rewrites this when a melee starts |
| `ADDON/valepre4.vcf` | a saved variant ("Jade's Car", Picard Piranha) |
| `ADDON/vmxmarx3.vcf` | another saved variant |
| `NVCL/nvcl0.vcf` | rewritten alongside `vehscn.vcf` |
| `I76.ZFS` | the stock variants (Econo / GT / GTA …) live in the archive |

## Format **[live]**

Chunked. Every chunk is a 4-byte tag (NUL-padded) + `u32 size`, and **size includes the 8-byte
header**.

```
BWD2                       file magic (size 8)
REV \0   u32 revision      = 3
VCFC     the vehicle:
   +0x00  char[16]  variant name           "Econo"
   +0x10  cstr      chassis model .vdf     "valeprec.vdf"   <- WHICH CAR
   ...    cstr      texture .vtf           "leprecn1.vtf"   <- WHICH SKIN
   ...    u32 x3    0, 1, 1
   ...    cstr      front wheel .wdf / "null" / rear wheel .wdf
   ...    u32 x8    ARMOR - integer TENTHS
SPEC     a special slot (empty slots are still written)
WEPN     u32 hardpoint, then cstr gdf name  ("gmlight.gdf")
EXIT     terminator
```

### Armor — 8 × `u32`, integer tenths **[live]**

Immediately after the last wheel `.wdf` string (file offset `0x79` in every file seen so far):

```
[ FRONT, RIGHT, LEFT, REAR ,  FRONT, RIGHT, LEFT, REAR ]
  <------ armor ------>       <----- chassis ----->
```

`200` = 20.0 on the form. The armor/chassis split is not a guess — Jade's Car ships
`[400,400,400,400, 360,360,360,360]` and the form shows armor 40.0 / chassis 36.0.

**Confirmed by writing:** setting all eight to `900` made the CHASSIS CONFIGURATION FORM read
`90.0` on every face, and total weight rose 4301 LBS. This also settles the long-open
"armor is integer tenths" note in the engine reference, which had never been checked against a
live value.

### Weapons — one `WEPN` chunk per mounted weapon **[live]**

`u32` hardpoint index, then the GDF asset name. Hardpoints on the Piranha:

| index | form slot | example |
|---|---|---|
| 0 | `#1 Dropper` | `glandmin.gdf` → LANDMINES |
| 1 | `#1 Rear` | `gfmedium.gdf` → GAS LAUNCHER |
| 2 | `#1 Top` | `gmmedium.gdf` → 50cal MG |
| 3 | `#2 Top` | `gcmedium.gdf` → 25mm CANNON |

Hardpoints can be fired individually with the **number keys**, so index ↔ number key is the
handle for testing one weapon at a time. (The `.45` handgun is special: it only fires when you
are looking out of the window, using the generic weapon-fire input.)

**GDF naming is systematic** — `g` + class + size:

| name | weapon | | name | weapon |
|---|---|---|---|---|
| `gmlight` | 30cal MG | | `gcmedium` | 25mm Cannon |
| `gmmedium` | 50cal MG | | `gfmedium` | Gas Launcher |
| `goilslck` | Oil Slick | | `glandmin` | Landmines |

These are the same strings the live weapon objects carry in memory, so a `.vcf` loadout maps
straight onto the in-memory slots — see [WEAPONS-MEMORY.md](WEAPONS-MEMORY.md).

### Which car is which **[live]**

The `.vdf` is the identity; the `.vtf` is only the skin.

| `.vdf` | `.vtf` | car |
|---|---|---|
| `valeprec.vdf` | `leprecn1.vtf` | ABX Leprechaun |
| `vppirnha.vdf` | `piranha1.vtf` | Picard Piranha |

## Editing a variant — the rename-gate bypass **[live]**

The chassis form refuses to save a modified stock variant until you rename it, and the rename
field **cannot be driven by injected keystrokes** (see WEAPONS-MEMORY.md). Editing the file
instead works and needs no UI at all:

```powershell
python autotest/setup/make-test-variant.py ADDON/valepre4.vcf.bak ADDON/valepre4.vcf --armor 900
python tools/vehicle/vcf.py dump ADDON/valepre4.vcf          # verify before launching
```

Relaunch, pick the variant, and the form shows the new values.

> **You must OVERWRITE an existing variant — adding a file does not register a new one.**
> Dropping a new `.vcf` into `ADDON/` (tried as both `valetst1.vcf` and `valepre5.vcf`, matching
> the existing naming) left the VARIANT list unchanged at Econo / GT / GTA / Jade's Car. The
> list is not built by scanning the directory; the stock variants come from `I76.ZFS` and an
> ADDON file acts as an override for one that already exists. Where the list itself is
> enumerated is **[open]**.

## Real-time (damageable) armor — **[LOCATED 2026-08-10]**

The `.vcf` value is the *configured* armor. The live, damageable copy is now located **inside the
player entity** at `+0x138..+0x154` (current) / `+0x158..+0x174` (max), integer tenths, in the
same 8-component `[ARMOR ×4, CHASSIS ×4]` layout as this file's block. It survives the repair
reallocation because it is reached by the stable entity chain `[[[0x54A264]]+0x70]`. Full method,
structure and the remaining authority write-test: **[ARMOR-INVESTIGATION.md](ARMOR-INVESTIGATION.md)**.
The historical dead-ends below are kept because they explain why the *live-scanning* route failed
and why the offline snapshot-diff route was needed instead.

### The fingerprint technique (use this, it works)

Because the config is editable, plant a unique value per face instead of searching for the
stock 200 (which is everywhere and defeated two earlier attempts):

```powershell
python autotest/setup/make-test-variant.py ADDON/valepre4.orig ADDON/valepre4.vcf `
    --armor-list 711,722,733,744,755,766,777,788
```

That instantly pins every copy of the armor block and reveals something the file cannot:
**memory order is FRONT, LEFT, RIGHT, REAR — not the file's FRONT, RIGHT, LEFT, REAR.**

### What the copies are

| address (that session) | stride | write behaviour | verdict |
|---|---|---|---|
| `0x0310899C`, `0x03184CA4` | 4 | sticks | config copy — HUD does **not** react |
| `0x072F9B1C`, `0x07309B1C` | `0x2C` | **restored within 300 ms** | derived copy, refreshed every frame |
| `0x072F7C70` | `0xB0` | sticks | no HUD reaction |
| `0x0CCC6480` | `0x18C` | sticks | no HUD reaction (see false positive below) |
| `0x6D0…` many | `0x84` | — | mapped-DLL resource copies |

**The live value is not stored in any form of the configured number.** Searches for int `711`,
float `711.0`, and float `71.1` all fail to find a copy that behaves like live armor, so the
engine evidently converts to some other unit or normalisation at load.

### Two traps that cost real time here

- **The HUD damage panel is a bad oracle while AI cars are shooting.** It changes on its own
  between a "before" and "after" capture. Writing 30 to `0x0CCC6480` moved 0.12 % of panel
  pixels and looked like a hit — but writing `1`, a far more extreme value, moved **0 %**.
  Incidental damage, not causation. Always run a null capture pair to measure the baseline, or
  set AI drivers to 0.
- **"Wait and let the AI shoot you" is not a reliable stimulus.** A 35 s window produced no
  armor change at all. Driving at full throttle into scenery does damage the car (confirmed on
  the panel), so use that.

### The next step that should actually work

`0x07309B1C` (stride `0x2C`, all eight faces in order) is **rewritten every frame**, so whatever
writes it is reading the true live armor. Put a **hardware write breakpoint** on it with
`src/find-reads.c` and follow the writer back to its source. That is the tool this situation was
built for, and it beats any further value scanning.

## Menu notes **[live]**

- The **VARIANT** arrow at UI `(443, 427)` opens a **picker list**, it does not cycle. An
  earlier note here claimed the AUTO MELEE make/model and variant arrows "do not cycle" — that
  was wrong, and it was wrong because a foreground popup was swallowing the clicks at the time.
- MAKE/MODEL arrow is at UI `(613, 407)`; `CONFIGURE CHASSIS` at `(536, 429)`.
- Coordinates are OS cursor units — see [CONFIG-OPTIONS.md](CONFIG-OPTIONS.md) §3.
