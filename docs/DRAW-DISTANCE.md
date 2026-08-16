# Draw distance: cracked, patched, and proven in the sandbox

**SOLVED 2026-08-16 (unattended session).** The "landscapes pop in late" improvement is a
one-global engine value with a fixed-size render pool as its crash ceiling — both found, both
patched, verified live at 3× and 8.3× stock with screenshots, arena telemetry, and FPS
measurements. **Deployed to the sandbox only; the portable install is untouched pending the
console eyeball test** ([READY-TO-TEST.md](READY-TO-TEST.md)).

## The chain, end to end

1. **The mission file carries it.** Every `.MSN`'s `WDEF` chunk nests a `WRLD` record; at
   `WRLD+0x13F` sits a u32 far-clip distance. **All 40 GOG missions say 600** (meters). The
   official mission-builder manual (`BUILDER\BUILDER.DOC` in the install!) even documents it:
   *"Typically the far clip distance is set to 600, which is the recommended distance.
   Adjusting it may cause problems… Experiment at your own risk."*
2. **The parser stores it in ONE global.** The chunk dispatch table at `0x500328`
   (`{tag, handler, flags}` × BWD2/REV/WDEF/TDEF/RDEF/ODEF/LDEF/ADEF/EXIT) routes `WDEF` →
   nested table `0x500CA0` → `WRLD` handler `0x4B8A10`, which ends:
   `fild [WRLD+0x13F]` / `fstp [0x4C271C]` — far clip as float, 600.0 in-game.
3. **ONE reader builds the camera.** Projection setup at `0x4059DE`:
   `mov eax,[0x4C271C]` when in-mission (flag byte `0x654B8A`), else 150.0 for menus, then
   camera-create `0x472220(fov=π/2, aspect, far, near=1.0)`. The constructor clamps far to
   **[100 … 100000]** — the engine itself accepts 100 km.
4. **The patch is byte-for-byte.** `mov eax,[0x4C271C]` (A1 1C 27 4C 00) →
   `mov eax,imm32` (B8 + float) at file offset 0x4DDE. Mission files untouched, menu path
   untouched, every mission covered at once.

## The crash ceiling (why "experiment at your own risk" was real)

At far=5000 the game died with 0xc0000005 at `i76.exe+0x91A11` — every time, same offset.
That code is a **12-byte-record bump allocator with no bounds check** (cursor `[0x654380]`,
count `[0x59C568]`), drawing from a **fixed 512 KB pool** `[0x5DD324]` allocated once at
renderer init (`0x402F98..0x402FD9`), alongside a sibling vertex buffer `[0x5DD320]`
(0x1A5E0 bytes, split at +0xD2F0).

Live telemetry proved it: a sampler read the pool at the moment of death — **peak 585,736
bytes used against 524,288**, record count 44,237 ≈ the pool's exact 43,690-record capacity.
(The killer scene was the menu's attract/demo render, which is why it could crash "at the
menu" before any mission.)

**Fix: enlarge both pools 16×** (arena 512 KB → 8 MB). All five size constants live in one
init sequence and appear nowhere else (verified unique). `patch-farclip.ps1` applies far +
pools atomically — never one without the other.

## Measured results (training mission, same spot ±30 cm, sandbox, 60 fps cap)

| far | terrain view | arena use | FPS |
|---|---|---|---|
| 600 (stock) | mesas are fog-clipped stubs; haze band above the ground | 20,720 B (4% of stock pool) | 60.0 |
| 1800 | full mesas, mountain silhouettes complete | 53,704 B | 60.0 |
| 5000 | entire mountain ranges to the horizon; vehicles render in the rearview that were beyond the clip | 648–676 KB (**would crash stock pool**; 8% of new pool) | 60.0 |

Note the **sub-linear** growth (3× far → 2.6× records): the terrain LOD/decimation does its
job, which is why 8.3× distance costs nothing measurable on a modern machine.

Soaks at 5000: mission entry, 60 s continuous driving (~730 m), 3-minute menu idle — no
crash, `Responding=True` throughout. Screenshots: `i76-uncap-lab/captures/farclip/`
(`stock-run1/2.png`, `far1800-run1.png`, `far5000-run1.png` — run1 vs run2 is the control
pair; their delta is negligible, so the patched delta is real).

## Deploy / rollback

```
i76-uncap-lab\tools\framerate\patch-farclip.ps1 -GameDir <dir> -FarMeters 1800
i76-uncap-lab\tools\framerate\patch-farclip.ps1 -GameDir <dir> -Restore
i76-uncap-lab\tools\framerate\patch-farclip.ps1 -GameDir <dir> -Status
```

Keeps `i76.exe.farorig`. Composes with the camera-rate patch (different bytes, own backup).
**Sandbox is currently at 5000 with enlarged pools.** Recommended first deploy to the
portable after the eyeball test: **1800** (dramatic, conservative) or 5000 (maximal).

## Caveats for the console test

- **Object/road pop.** Community work (CahootsMalone) reports objects and road segments cull
  at their own, shorter distance — terrain now reaches 5 km but buildings/roads may still
  appear at their old radius. If it bothers, that culling is a separate future hunt.
- **Design assumptions.** Missions were authored assuming a 600 m veil: distant enemy
  spawns/despawns may now be visible (the rearview truck at 5000 is exactly that). Fog/haze
  atmosphere is thinner at distance too — check whether the desert still "feels" right.
- **Only the training desert was soaked.** Dense scenes (canyons, cities) will use more
  arena; the 16× pool has ~13× headroom over the worst measured frame, so the margin is
  huge, but a campaign playthrough is the real test.

## The texture-LOD half (deferred, path known)

Terrain *textures* at distance are **hand-authored mip tiers inside `tpXXm6.pak`**
(256/64/64/32/16 px), selected by engine distance logic — not Glide mipmapping, so **no
wrapper setting can push the sharp tier further out** (dgVoodoo has no LOD-bias key; its
author explicitly declined — engine-side LOD). The proven path is data-side: swap larger
images into the far mip slots of the pak (same skill set as the retired HD-textures
experiment, see [HD-TEXTURES-RESEARCH.md](HD-TEXTURES-RESEARCH.md)). Deferred.

## Prior art (none of it went this far)

- **CahootsMalone** raised the *level-file* value 600→1000 and showed terrain extends
  (github.com/CahootsMalone/interstate-76-stuff, `terrain-texture-info.md`) — per-mission
  hex edit, no exe patch, no crash-ceiling fix.
- **MechWarrior 2 "FarPatcher"** (mech2.org) patches the same engine family's per-world
  VIEW records — same design, same "some missions crash above certain values" wall we
  removed here.
- **No published I'76 draw-distance mod exists** (PCGamingWiki, VOGONS, ModDB, GOG forums
  swept 2026-08-16). This appears to be a first.
