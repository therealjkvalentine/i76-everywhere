# I'76 level format — chunks, objects, and where the repair spots are

Decoded live from `b01dojo.cbt` (route380 community map). Applies to `.LVL`, `.CBT` and `.RAC`
— they are the same container, and the Gold install instructions ("rename `.cbt`/`.rac` to
`.lvl`") reflect that.

Parser: **`tools/level-objects.py`**.

## Container

The same chunk scheme as `.VCF` (see
[`i76-uncap-lab/docs/CAR-CONFIG.md`](../../i76-uncap-lab/docs/CAR-CONFIG.md)): a 4-character
tag, then a `u32` size **which includes the 8-byte header**.

```
BWD2            magic
REV             revision
WDEF            world defs      (dojo: 367 bytes)
TDEF            terrain defs    (6,467)
RDEF            roads           (27,860)
ODEF            objects         (8,992)   <- everything placed in the level
LDEF            (28)
ADEF            (64)
EXIT
```

## `ODEF` — one `OBJ` chunk per placed object, 0x6C bytes

```
+0x00  char[8]   class name        "REGEN", "AARAMP2", "BHBARN2", "VCROYAL1"
+0x08  float[9]  3x3 rotation matrix
+0x2C  float     X
+0x30  float     Y      (height)
+0x34  float     Z
```

Class names are the Asset Bible's — see [ASSET-BIBLE.md](ASSET-BIBLE.md) and
[asset-bible/](asset-bible/INDEX.md). Coordinates are world units on the same scale the game
reports live: dojo's first `REGEN` is at `(1782.5, 24.0, 50267.5)` and in-mission player
positions read around `(4688, 120, 49082)`.

> **GOTCHA — bit 7 of a name character is a FLAG, not part of the name.**
> Read raw, the class list fills with phantoms: `BCSTRAK2` and `BCSTRAK6` alongside
> `BCSTRÁK6` (`0xC1` vs `0x41`) and `AKWRECË2`. These look like a corrupt file or a drifting
> parser and are neither — they are the same objects with the high bit set. Mask to 7 bits.
> Every name then matches the Asset Bible exactly.

## `regen` — the repair spot, with coordinates

`regen` is the **"healing building"**: a placeable object that repairs a damaged car, listed in
the Asset Bible's vehicle codes alongside `spawn` and `check1..N`. It is ordinary map data, not
special scripting.

**This is the key to live armor.** A repair is the only stimulus that moves armor *upward* on
demand — damage has proved unreliable in every form tried (AI fire produced no change in 35 s,
wall-grinding does nothing, own landmines were inconclusive). Knowing a map *has* one is
useless without knowing *where*; that is what this parser gives.

Across the 40 mirrored community maps: **138 regen objects in 54 level files**
(`refs/route380/regen-scan.txt`).

### Best targets

Melee-usable combat maps (`.cbt` → rename to `.lvl` for Gold, with the `.ter`):

| map | file | regen at (X, Y, Z) |
|---|---|---|
| **the Dojo** | `dojo/b01dojo.cbt` | `1782.5, 24.0, 50267.5` · `717.5, 37.0, 50442.5` · `1132.5, 30.0, 49477.5` |
| GunsOnly | `GunsOnlyfixed/N00.cbt` | `1542.5, 0.1, 49372.5` |
| Nowhere N.M. | `nowhere/nowhere.cbt` | `2817.5, 0.8, 50032.5` |
| Texas v1.03 | `p15texas/p15Texas.cbt` | `1702.5, 2.0, 49367.5` · `1892.5, 44.0, 49597.5` |

**Biggest target of all:** `b01skyd1/for_i76/Sd.LVL` has **15 regen spots** packed around
`(247.5, 120.0, 51100)` — a repair *zone* roughly 20 × 75 units, far easier to drive into than
a single point.

### Also useful: known ramp heights in the same maps

The Asset Bible encodes launch height in the ramp name, and dojo contains `AARAMP2` (11 m) and
`AARAMP3` (2 m). That gives a **known launch height** for 20 Hz vs 60 Hz jump comparison in a
map we control, instead of hunting the Mission 5 canyon.

## How to use this

```powershell
python tools\level-objects.py <level>                # every object + class histogram
python tools\level-objects.py <level> --only regen   # just the repair spots
python tools\level-objects.py <dir>  --scan regen    # sweep a directory of maps
```

Install a community map into **Gold**: rename `.cbt`/`.rac` → `.lvl`, put it with its `.ter`
into `ADDON`. (Classic I'76: `.lvl`/`.ter`/`.npt` into `ADDON`. NitroPack: mission into `miss8`
*and* `miss16`, terrain into `ADDON`.)

Source of the maps and the install rules: [COMMUNITY-SITEMAP.md](COMMUNITY-SITEMAP.md) §1.
