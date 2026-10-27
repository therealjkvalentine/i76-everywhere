# Draw distance: cracked, patched, and proven in the sandbox

> **2026-10-02: a third ceiling, and a crash.** Terrain edge records hold vertex indices as `int16`; wide views (F6 hood at 120 deg, B binoculars at 8x) push a frame past 32,767 terrain vertices between **2500 and 2750 m** and the game faults in `renderer_SplitTerrainEdge`. Keep the far clip at **2500 m or below**. The sandbox's file patch sat at 8000 m and crashed on F6/B every time; it was set to 1800 m on 2026-10-02, which is safe. Details: [FARCLIP-CAMERA-CRASH.md](../records/FARCLIP-CAMERA-CRASH.md). The proxy's `I76_FAR_CLIP` refuses values above 2500.

**SOLVED 2026-08-16 (unattended session).** The "landscapes pop in late" improvement is a
one-global engine value with a fixed-size render pool as its crash ceiling — both found, both
patched, verified live at 3× and 8.3× stock with screenshots, arena telemetry, and FPS
measurements. **Deployed to the sandbox only; the portable install is untouched.** The console
eyeball test happened on 2026-10-02 at 1800 m (F6 hood view and B binoculars good); deploying to the
portable is a separate, announced step (corrected 2026-10-02: this said "pending the console eyeball test").

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
crash, `Responding=True` throughout. Screenshots: `<lab>/captures/farclip/`
(`stock-run1/2.png`, `far1800-run1.png`, `far5000-run1.png` — run1 vs run2 is the control
pair; their delta is negligible, so the patched delta is real).

## Deploy / rollback

```
<lab>\tools\framerate\patch-farclip.ps1 -GameDir <dir> -FarMeters 1800
<lab>\tools\framerate\patch-farclip.ps1 -GameDir <dir> -Restore
<lab>\tools\framerate\patch-farclip.ps1 -GameDir <dir> -Status
```

Keeps `i76.exe.farorig`. Composes with the camera-rate patch (different bytes, own backup).
**Sandbox is at 1800 m with enlarged pools** (corrected 2026-10-02: this line said 5000; the sandbox was
in fact at 8000 m / 128x until the F6/B crash and was set to 1800 on 2026-10-02). Recommended dose for the
portable: **1800**. Anything above 2500 m crashes the wide views ([FARCLIP-CAMERA-CRASH.md](../records/FARCLIP-CAMERA-CRASH.md)),
so 5000 is no longer an option; the proxy's `I76_FAR_CLIP` refuses it.

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
experiment, see [HD-TEXTURES-RESEARCH.md](../research/HD-TEXTURES-RESEARCH.md)). Deferred.

## Prior art (none of it went this far)

- **CahootsMalone** raised the *level-file* value 600→1000 and showed terrain extends
  (github.com/CahootsMalone/interstate-76-stuff, `terrain-texture-info.md`) — per-mission
  hex edit, no exe patch, no crash-ceiling fix.
- **MechWarrior 2 "FarPatcher"** (mech2.org) patches the same engine family's per-world
  VIEW records — same design, same "some missions crash above certain values" wall we
  removed here.
- **No published I'76 draw-distance mod exists** (PCGamingWiki, VOGONS, ModDB, GOG forums
  swept 2026-08-16). This appears to be a first.

## 2026-09-27: a second ceiling at about 3.8 km (static)

Found while mapping the renderer (<re-archive> `subsystems/renderer.md`): the software scene sorts every primitive into 1 m
depth buckets that start at -300 m. A bucket index above 4096 is silently dropped (`cmp edi, 0x1000` at 0x48fe61), so
nothing deeper than about 3796 m in view space is drawn, whatever the far clip says. A far-clip patch that aims past
about 3.8 km also has to raise this limit (and the flush clamp that walks at most 4096 buckets). Not yet tested live.

## 2026-10-19: terrain pop-in on the T05 canyon ridge - the split distance, not the LOD factor or the vertex guard (lab lod-sweep lane, interim)

Owner: "maybe lod isn't the right variable? ... i can see the terrain changing at the high part behind the t05 intro cutscene road."
Method (lab copy game-lod = game-tick, preset tick19-33, real renderer, 120 fps cap, tools\lod-sweep\ridge-run.ps1): T05 at the
mission start (x 8490, z 44520, heading +x, the canyon road), the car held still 12 s with the handbrake, then driven slowly (W) 24 s;
a PNG every 2 s, the frame's terrain vertices (ridge_sampler.py, 50 ms), fps from I76_FRAME_LOG (display frames; the telemetry dt is the
33.3 ms tick under the tick preset), vertex-guard refusals from the proxy log. n 1 per setting except the baseline (n 3: 112.0 / 115.5 / 113.9 fps,
so the fps spread is about +-2). Raw: lab tools\lod-sweep\ridge\<id>\ (PNGs s00..s17, verts.csv, frames.csv, summary.txt), ridge-results.txt.

| setting (far clip 1200) | terrain vertices mean / peak | fps mean | p1 | guard refusals | ridge cliff face |
|---|---|---|---|---|---|
| LOD 24 (driver) | 2767 / 3281 | 112.0, 115.5, 113.9 | 81 | 0 | missing (smooth slope) |
| LOD 48 | 3679 / 4445 | 115.0 | 82 | 0 | |
| LOD 96 | 5291 / 6614 | 102.8, 106.2 | 73, 78 | 0 | |
| LOD 256 | 8412 / 10848 | 94.8 | 65 | 0 | resolved |
| LOD 96, VLIMIT 31000 | 5125 / 6629 | 104.1 | 71 | 0 | same as 96 |
| LOD 256, VLIMIT 31000 | 8539 / 10867 | 96.3 | 64 | 0 | same as 256 |
| A 96, B 24 (distance only) | 3907 / 4738 | 112.6 | 80 | 0 | resolved (near x256) |
| A 256, B 24 | 4496 / 5529 | 110.0 | 80 | 0 | resolved |
| A 24, B 96 (height error only) | 3450 / 4097 | 113.2 | 82 | 0 | missing, as LOD 24 |
| A 24, B 256 | 4004 / 4856 | 109.0 | 79 | 0 | missing, as LOD 24 |
| A 1, B 256 | 1379 / 1473 | 117.7 | 81 | 0 | coarse everywhere |

- **The vertex guard is not involved**: peak 10.9k vertices at x256, the guard (28000, or 31000) never refused a split in this view.
  VLIMIT 31000 changed nothing (verts and fps within noise); it would also leave only 1.8k under the 32,767 int16 ceiling while the leaf
  edges add about 1.9k past the limit, so it is a risk with no gain here. Keep 28000.
- **The ridge is the split distance (A)**: A 256 / B 24 and A 96 / B 24 show the canyon wall's terraced cliff face from the start;
  A 24 / B 256 does not (identical to x24). The height-error constant B costs vertices (x96 -> +1.5k) without showing here. New lab switches
  `I76_TERRAIN_LOD_A` / `I76_TERRAIN_LOD_B` (strlkproxy.c; side proxy lab builds\lod-split-20261019, source 6efb646 + the change) split them.
  Same fps cost class as the driver (n 1) at A 96 / B 24, against about 10 fps for x96 and 17 fps for x256.
- **Vertex budget by distance at LOD 24** (far clip 150 / 300 / 600 / 1200 / 1800 m = terrain vertices mean 661 / 1197 / 1653 / 2767 / 5619, n 1):
  the ground within 150 m takes 24 % of the 1200 m budget, within 300 m 43 %, within 600 m 60 %; the ridge shell beyond 600 m about 40 %
  and the 1200-1800 m shell as much again. These are all terrain in a radius, not flat vs rugged (the quadtree gives no per-node count
  from outside); a relief-weighted split would take the distance constant per node from the height error the B test already computes at
  the same decision point as the vertex guard (0x4912f6).
- Baseline p1 is 81 fps at LOD 24 itself (frame-log wall periods under the tick), so no LOD can meet p1 >= 110 on this view; the earlier
  p1 97-100 figures were per-frame telemetry dt under a per-frame preset.
