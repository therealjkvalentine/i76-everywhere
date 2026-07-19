# Interstate '76 / MechWarrior 2 engine — vehicle, weapon/ammo, and armor/damage data structures

Research compiled 2026-07-18 for the GOG `i76.exe` memory-scan effort. Goal:
find where **live ammo counts, armor-per-facet, and component health** live, and
how they are **encoded**, so we can locate them in a running process.

The short answer up front is in the last section ("Bottom line for the memory
scan"). Everything above it is the evidence.

---

## 0. What each source can and cannot tell us

| Source | What it authoritatively gives | Limits |
|--------|-------------------------------|--------|
| **That Tony**'s format docs (hackingonspace.blogspot) | The on-disk **file formats** (VCF/VDF/GDF/SDF). Field order = struct shape. | Blog now behind a Blogger login redirect; content survives via the Open76 parsers that implement it. Disk layout, not RAM layout. |
| **Open76** (r1sc + rob518183 forks), C#/Unity | The actual **parsers** (`GdfParser`, `VcfParser`, `VdfParser`) — exact field order, types, sizes — plus a **runtime model** (`Car`, `Weapon`, `WeaponsController`) showing how ammo/armor behave frame-to-frame. | It is a *reimplementation*: field values come from the real files, but the runtime container shape is their design, not the original engine's RAM struct. Two constants (hull/core HP) are hardcoded with `// TODO: figure out where this is stored`. |
| **Roanish/i76** "Vigilante '76" (Ghidra C rewrite of Nitro Pack), `docs/REVERSING.md` | Confirmed **engine-level** facts: the entity store is a 2029-bucket hash of heap-allocated object structs; the fixed-timestep sim loop; a handful of object-struct offsets. | RE has reached the **boot/asset/mesh/mission-load** layer only. It has **not** yet reversed the vehicle *combat* fields (ammo/armor/HP offsets are unknown in public RE). |
| **Shane Peelar** (inbetweennames.net) | The **20 fps physics coupling** and the fast-rsqrt find; netcode. | No struct layouts published. |

Nobody has published the exact RAM offsets of ammo/armor inside the live vehicle
entity. But the file formats + the reimplementation's runtime model together
pin down the **encoding and shape** tightly, which is what the scan needs.

---

## 1. GDF — weapon definition = the shape of a weapon's static data

`GdfParser.cs` (Open76) reads the `GDFC` chunk in this exact order. Offsets below
are **bytes from the start of the GDFC payload** (each field consumes its size).
This is the disk layout; the live weapon-instance almost certainly carries the
same scalar fields (plus a mutable ammo/health counter).

| GDFC off | Type | Open76 field | Notes |
|----------|------|--------------|-------|
| 0  | char[16] | Name | e.g. "Landmines" |
| 16 | int32 | (unk1) | |
| 20 | int32 | (unk2) | |
| 24 | float ×4 | (unk3..6) | 24,28,32,36 |
| 40 | 4 bytes | (skipped) | |
| 44 | **int32 Damage** | per-projectile damage | |
| 48 | **int32 Health** | weapon's own hit points (That Tony/renscreations called this "fireproofing", value 200) |
| 52 | float | WeaponMass | |
| 56 | char[12] | (unk7) | |
| 68 | uint16 | (unk8) | |
| 70 | float | (unk9) | |
| 74 | float | BurstRate | stored as 1/x |
| 78 | float | FiringRate | stored as 1/x |
| 82 | **int32 FireAmount** | shots per burst (value 1 = single) |
| 86 | float | BulletVelocity | |
| 90 | **int32 WeaponGroup** | fire-group id |
| 94 | **int32 AmmoCount** | **ammo capacity** — landmine = 25 |
| 98 | float | (unk10) | |
| 102 | char[13] | FireSpriteName | |
| 115 | char[13] | SoundName | |
| (rev 8 only) 128 | int32 + char[16] ×2 | enabled/disabled sprite | |

**Cross-confirmed:** renscreations' independent GDF dump lists "Ammo Count" as an
Int32 at GDFC offset **94** with value 25 for landmines — byte-identical to
Open76's `AmmoCount`. Damage=int32, Health=int32, AmmoCount=int32, FireAmount=int32.
**No fixed-point anywhere in the combat scalars** — counts and damage are plain
32-bit ints; only physical quantities (mass, velocity, rates) are floats.

## 2. How ammo behaves at runtime (Open76's model = best available proxy)

`Weapon.cs`:
```
public int Ammo;              // mutable, per weapon INSTANCE
public int Health;            // weapon's own HP
...
Ammo   = gdf.AmmoCount;       // initialised from the GDF capacity
Health = gdf.Health;
```
`WeaponsController.FireWeapon()`:
```
--weapon.Ammo;                                    // plain decrement, one per shot
_panel.SetWeaponAmmoCount(weapon.Index, weapon.Ammo);   // HUD reads it directly
```
Empty check: `if (weapon.Ammo == 0) play "cammo.gpw" (out-of-ammo click)`.

So in the reimplementation ammo is:
- a **per-weapon-instance signed int** (not per weapon *type*),
- initialised to the GDF capacity,
- a **countdown** (decrement per shot), and
- **the exact value the HUD prints** — the HUD does not compute or scale it.

Containment: **Vehicle (VCF) → list of weapon instances → each has its own Ammo
int.** `WeaponsController` holds `Weapon[] _weapons`; each `Weapon` owns `Ammo`,
`Health`, a `WeaponGroupOffset`, and a back-pointer to its `Gdf`. Weapons are
grouped by fire-group (`WeaponGroup`, +100 for rear-facing) for the fire button.

## 3. VCF — vehicle config = the shape of armor/chassis

`VcfParser.cs` reads the `VCFC` chunk. Offsets from VCFC payload start:

| VCFC off | Type | Field |
|----------|------|-------|
| 0  | char[16] | VariantName |
| 16 | char[13] | VdfFilename |
| 29 | char[13] | VtfFilename |
| 42 | uint32 | EngineType |
| 46 | uint32 | SuspensionType |
| 50 | uint32 | BrakesType |
| 54 | char[13]×3 | Wdf front/mid/back (54,67,80) |
| **93**  | uint32 | **ArmorFront** |
| **97**  | uint32 | **ArmorLeft** |
| **101** | uint32 | **ArmorRight** |
| **105** | uint32 | **ArmorRear** |
| **109** | uint32 | **ChassisFront** |
| **113** | uint32 | **ChassisLeft** |
| **117** | uint32 | **ChassisRight** |
| **121** | uint32 | **ChassisRear** |
| 125 | uint32 | ArmorOrChassisLeftToAdd |

Then `SPEC` chunks (specials) and a `WEPN` chunk listing `{int32 MountPoint,
char[13] GdfFilename}` per weapon — this is the **vehicle→weapon list** on disk.

**Armor model = 8 contiguous uint32s: 4 armor facets + 4 chassis facets**, in
face order Front/Left/Right/Rear. Armor = the outer layer that eats projectile
damage; chassis = the structural layer underneath. Both are plain **uint32**.

## 4. Runtime damage/health model (Open76 `Car.cs`)

Health is one flat `int[]` indexed by a `SystemType` enum (17 slots):

```
Vehicle, Engine, Brakes, Suspension,          // core
FrontArmor, LeftArmor, RightArmor, BackArmor, // 4 armor facets
FrontChassis, LeftChassis, RightChassis, BackChassis, // 4 chassis facets
TireFL, TireFR, TireBL, TireBR,               // 4 tires
TotalSystems
```

Initialisation:
```
Vehicle    = 550   (VehicleStartHealth)  // hardcoded, "// TODO: where is this stored?"
Engine/Brakes/Suspension = 250 each (CoreStartHealth)  // hardcoded TODO
Tires      = 100 each (TireStartHealth)  // hardcoded TODO
FrontArmor = Vcf.ArmorFront   ... (all 4 armor facets from VCF uint32)
FrontChassis = Vcf.ChassisFront ... (all 4 chassis facets from VCF uint32)
```

Damage flow (`ApplyDamage` → `SetComponentHealth`):
- Projectile hits pick an **armor** facet by impact angle; force/collision hits
  pick a **chassis** facet.
- `hp[system] -= damage` (plain integer subtract).
- **Overflow passes through:** if a facet drops below 0, the negative remainder
  is added to a randomly chosen surviving core system (Vehicle/Engine/Brakes/
  Suspension). When `Vehicle` hp ≤ 0 → `Explode()`.
- The HUD panel shows only a **5-step colour group** (off/grn/ylw/red/drk)
  computed from `current/start` — it does **not** print the raw armor int.

Two important caveats for us:
- The 550/250/100 core constants are **guesses** — the reimplementers could not
  find them in the files, so they may differ in the real exe (they are strong
  candidates for a memory search: look for 550 and 250 near the player entity).
- Armor *facet* start values come straight from the VCF uint32s, so in the real
  save/entity the current armor is almost certainly the **same integer scale**
  as the VCF value (see the "tenths" note in §7).

## 5. Engine-level facts from the Roanish Ghidra decompile

`docs/REVERSING.md` + `world.h` (confirmed):

- **Entity store = a 2029-bucket hash of heap-allocated object structs**
  (`g_obj_buckets`, described as "the original's 2029-bucket entity store").
  Objects are allocated on the game object heap, **not** at fixed addresses.
- **Entity creation path:** mission load → `FUN_004b3660` (per-OBJ reader) →
  type-code switch at **object `+0x64`** → `FUN_004b3e20` allocates the object
  struct → `FUN_00453d50(entity, transform, …)` is "the entity-store insert"
  (fatal string "I'76 Nitro Pack cannot create entity"). So **the player car is
  a heap object created at mission start** — its base address is stable within a
  mission but changes across load/mission.
- **Object-struct offsets known so far:** `+0x5c` cached mesh ptr, `+0x64` type
  code, `+0x84..+0xab` a transform/orientation block. The **combat fields
  (ammo/armor/HP) have not yet been located** by public RE — this is exactly the
  gap our scan fills.
- **Fixed-timestep deterministic sim** (`world_tick(in, dt)` called 0..N times
  per rendered frame; render interpolates with an alpha). Matches Shane Peelar's
  finding that I'76 physics/AI are **hard-coupled to ~20 fps** — the sim advances
  in fixed ticks, so ammo/HP mutate on tick boundaries, not render frames. When
  scanning "what changed after I fired", step by ticks, not frames.

## 5b. MechWarrior 2 (the shared engine ancestor) — corroboration

I'76 is built on a modified MW2 engine, so MW2's data model is a useful cross-check.
The MW2 **MEK** (mech config) format, documented by the MechVM RE effort
(`DEFMEK.H`, mech2.org forums), lays out a mech as:

- header **DWORD tonnage**, then counts: walking MP, jumpjets, heatsinks,
  **number of weapons, ammo count**;
- then per **section** (torso/arms/legs): **front armor, rear armor, internal
  structure**, plus a word-array of critical slots.

The parallels to I'76's VCF are exact in kind: **armor is a per-section integer,
split into an outer armor layer and an inner "internal structure" layer** — which
is precisely I'76's *armor facet* + *chassis facet* pair. Ammo is a **count**
carried alongside the weapon list, not a float. This independently supports the
"combat scalars are plain integers, armor is a two-layer per-facet integer,
weapons carry an ammo count" model above.

## 6. Shane Peelar (inbetweennames.net)

- Confirms the **20 fps coupling**: "I'76 is really dependent on its framerate for
  the physics simulations to work properly and other parts of game logic (like
  AI)… 20 was about as high as you could go before negative effects set in."
- Documents Activision's **fast reciprocal square root** in the 1997 build (Quake
  III–style) — relevant only in that the engine leans on float math for physics,
  but **not** for the integer combat counters.
- No published struct layouts; his focus is the renderer/Vulkan and ANet netcode.

## 7. The "ammo = 3721 / armor tenths" puzzle — interpretation

**Ammo (3721):** Every source that touches ammo treats it as a **plain 32-bit
integer count**, initialised from the GDF `AmmoCount` (int32) and **decremented
per shot**. 3721 is a perfectly ordinary int (some MG/rapid weapons ship with
thousands of rounds). Interpreting 3721 as fixed-point fails: as 16.16 its
integer part is 0, as a float it is a tiny value — neither matches a HUD reading
of 3721. **Conclusion: ammo is a plain int; the reason it "moves" is that it
lives at a fixed *offset inside the heap-allocated vehicle/weapon struct*, whose
*base* relocates** (§5) — not because it is encoded oddly. It is very likely a
**countdown** (current rounds remaining), matching the reimplementation, rather
than a shots-fired counter — but both are ints and both are trivial to confirm:
fire one shot and watch for a ±1 delta.

**Armor "tenths":** the VCF stores armor as **uint32** and the reimplementation
carries it at that same integer scale. If the save shows values ~10× the HUD
number (the "tenths" you saw), the most likely explanation is that the engine
keeps armor/HP in **tenths (fixed ×10 integer)** internally and the HUD divides
by 10 for display — this is an *integer* scaling, still not floating fixed-point.
That would also explain the hardcoded 550/250 core constants (55.0 / 25.0 shown).
This is the one encoding detail worth explicitly testing: read a facet's raw
value, compare to the HUD, and check for a ×10 relationship.

---

## Bottom line for the memory scan

1. **Ammo is a plain signed 32-bit int**, one per **weapon instance**, almost
   certainly a **current-rounds countdown** initialised from the GDF `AmmoCount`
   (int32 at GDFC+94). Not fixed-point, not a float. It appears to "wander" only
   because it sits at a fixed **offset within a heap-allocated weapon sub-struct**
   hung off the vehicle entity, and the entity is created on the object heap at
   mission load (base relocates). Scan technique: don't chase an absolute address
   — fire one shot, diff for a `-1` int change, then treat that address as
   `entity_base + weapon_index*stride + ammo_off` and re-derive it each mission
   via a pointer chain from the player-entity pointer.

2. **Armor is per-facet plain integers: 8 of them (4 armor + 4 chassis),
   contiguous, face order Front/Left/Right/Rear**, seeded from the VCF uint32s.
   Component health (engine/brakes/suspension/tires, and the hull "Vehicle" pool
   ~550) are the same integer kind. Damage is integer subtraction with
   pass-through to a core pool on facet depletion.

3. **Most likely non-obvious wrinkle: the stored values are integers in *tenths*
   (×10 of the HUD number).** Test this first — it reconciles the "tenths in
   saves" observation and the 550/250 constants without invoking floating-point.
   If tenths is confirmed, every combat scalar (ammo may or may not share it —
   test separately) is `displayed = stored / 10`.

4. **Containment for pointer chains:** player vehicle entity (heap object in the
   2029-bucket store) → armor/chassis facet ints (contiguous block) + a weapons
   array → each weapon's {current ammo int, weapon HP int, group id}. Find the
   player-entity pointer once (it is passed to `FUN_00453d50` at spawn and is the
   thing the HUD renders from), then all combat values are fixed offsets off it.

5. **The sim is fixed-tick (~20 fps).** Combat ints mutate on tick boundaries;
   pause/step by ticks when correlating a shot to a memory delta.

---

## Sources

- Shane Peelar, "Interstate '76 Reverse Engineering — the story so far" and
  "Fast reciprocal square root… in 1997?!", inbetweennames.net.
- Roanish/i76 "Vigilante '76", `docs/REVERSING.md`, `src/engine/world.h`,
  `src/engine/gamestate.h` (Ghidra decompile of the Nitro Pack binary).
- r1sc/Open76 and rob518183/Open76 (Unity reimplementation), files:
  `Assets/Scripts/System/Fileparsers/GdfParser.cs`, `VcfParser.cs`, `VdfParser.cs`;
  `Assets/Scripts/CarSystems/Components/Weapon.cs`, `WeaponsController.cs`;
  `Assets/Scripts/Entities/Car.cs`; `Assets/Scripts/CarSystems/Ui/SystemsPanel.cs`.
- renscreations.com, "More Open76 — Looking Into GDF Files" (independent GDF
  byte-offset dump; confirms AmmoCount int32 @ GDFC+94).
- "That Tony", hackingonspace.blogspot.com (original format RE; now login-gated,
  survives via the Open76 parsers that implement it).
- localditch.com "I '76 Hacks", GOG forum threads (VCF/VDF hex-edit lore).
- MechWarrior 2 shared engine: mech2.org forums (MEK format, "Open MW2 Engine"),
  MechVM / `DEFMEK.H`, sarna.net "MechVM" — MEK = tonnage DWORD + weapon/ammo
  counts + per-section {front armor, rear armor, internal structure}.
