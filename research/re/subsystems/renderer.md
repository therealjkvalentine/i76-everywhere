# renderer

**Contract.** Each frame WinMain raises the process to REALTIME priority, calls `renderer_DrawFrame` 0x401c90 with the
camera 0x4c2730, then drops back to NORMAL. The software scene queues every primitive into 1 m depth buckets and
flushes them far to near (painter's algorithm) over the directly drawn sky. The hardware scene uses the same order
through D3D or a renderer plugin.

Static reading of md5 9a232dcc (2026-09-27), batch `renderer-map-1` (88 names), from a reviewed read-only draft (cluster J). The
depth cut-off 0x48fe61 and the 600 m radius 0x472499 were checked in disassembly.

## Key facts for mods and ports

- **Second draw-distance ceiling.** Depth buckets start at -300 m and anything past bucket 4096 is dropped
  (0x48fe61), so nothing beyond about 3796 m draws, even with the far-clip patch (i76-everywhere
  docs/DRAW-DISTANCE.md). Raising the far clip past about 3.8 km needs this raised too.
- **Far-vehicle radius.** The camera field read by `camera_ClassifyDistance` is 600 x zoom x sqrt(1 + tan^2(fov/2))
  (849 m at 90 deg, 0x472499). The switch to the cheap far model is at that + 25 m, independent of the far clip.
- **Object LOD is chosen by on-screen size (pixels), not distance.** With Object Detail on, LODs 1 and 2 collapse to
  0 (0x457f7f).
- **More per-frame effects** (frame-rate dependent, not yet fixed in the proxy):
  - smoke puffs live 20 frames;
  - missile smoke trails lose 4 segments per frame in their last 2 s;
  - flamer streams lose 2 per frame.

## Frame

- WinMain 0x403e47: SetPriorityClass(GetCurrentProcess(), 0x100 REALTIME) around the render call, back to 0x20 NORMAL at 0x403e71; 0x403e69 renderer_DrawFrame(camera block 0x4c2730).
- renderer_DrawFrame 0x401c90: only when shell_GetGameState()==5; 0x5dd2a8==1 (display driver kind 1 = hardware, 0x495060; see Software rasteriser) -> renderer_DrawSceneHardware 0x401fa0, else renderer_DrawSceneSoftware 0x401cc0.
- Software scene 0x401cc0 (profiler labels in quotes): weapon_AgeFlamerStreams 0x443e90; if camera_in_cockpit [0x4c2724] renderer_DrawRearMirror 0x445750 ('Mirr'); if Shadow Detail [0x654b86] renderer_ClearBitmap(0x5dcef4, 0); inline billboard yaw matrix -> 0x5dd380 (same as 0x401bd0); renderer_BeginSpanFrame 0x473630.
- Queue into depth buckets (nothing touches the screen yet): renderer_QueueTerrain 0x490a00 ('Terr'), renderer_QueueRoadsAndDecals 0x48e900 ('Road'), renderer_QueueSkidMarks 0x445060 ('Skid'), weapon_UpdateFlamerStreams 0x443fc0, renderer_QueueObjects 0x457ff0 (objects + shadows + headlight beams), renderer_QueueSmokeTrails 0x442ba0, renderer_QueueTracers 0x442480, renderer_QueueTerrainClutter 0x45c380, renderer_UpdateSmoke 0x4414a0.
- Lock the screen surface 0x5dcec0 ([0x5dd2bc] at 0x401e5d), then draw straight to it: renderer_DrawClouds 0x405200 (cloud dome), renderer_DrawHorizon 0x4016e0 (16 horizon strips) ('Sky').
- renderer_FlushDepthBuckets 0x48fac0(cam, 1): painter's order, farthest 1 m bucket first, over the sky ('Sort').
- Cockpit/HUD in the view: if in cockpit and cockpit panel shown [0x654b88]: renderer_DrawCockpit 0x45adf0 ('Ckpt3'); renderer_FlushSpans 0x473640 (software span list) ('Span'); instrument overlay 0x45be20 when (in cockpit and [0x654b88]==0) or (outside and Ext. Instrument Display [0x654b8e]) ('Ckpt2'); renderer_DrawTargetBrackets 0x45af10(cam,0); network game: renderer_DrawPlayerNameTags 0x45bb80; if shake active renderer_ApplyScreenShake 0x498730 ('Final'); unlock [0x5dd2c0].
- Hardware scene 0x401fa0: same queue order with renderer_RetryPendingFlip 0x42dd00 between passes, no shadow-buffer clear and no span flush; built-in D3D (0x504be8==0): renderer_D3DBeginScene 0x42e850 before the flush and renderer_D3DEndScene 0x42e970 after 0x45af10; name tags drawn inside their own lock/unlock; plugin DLL path (0x504be8!=0): renderer_PluginDrawEdgeStrips 0x42cd90 then renderer_fn_RenderRefresh [0x608bb4].
- Back in WinMain: lock 0x403e85, renderer_DrawMask 0x4621e0(cam) (cockpit mask), font_DrawTextWindows 0x49b430, 0x49bee0, unlock 0x403eaa, then the flip [0x5dd2e0] 0x403ed3 (or the shell overlay 0x496870).
- Rear mirror 0x445750 (options.md): level 1 = objects only via the mirror variants renderer_QueueObjectsMirror 0x457a90, renderer_QueueTracersMirror 0x4420b0, renderer_DrawSmokePuffs 0x441bb0, 0x443fc0, then 0x48fac0(cam,0); level 2 = full scene with renderer_SetBillboardYawMatrix 0x401bd0 first.

## Rules

| what | rule | site |
|---|---|---|
| camera projection | camera_Init clamps fov to [pi/4, 3pi/4] and far to [100, 100000]; zoom (cam+0x34) is clamped to [0.5, 8]. Focal scale cam+0x08 = (viewport width/2)*zoom/tan(fov/2), cam+0x0c = -aspect*that. The main view uses fov pi/2, near 1.0, far = Visibility Range ? mission far (600) : 150. | 0x472404 |
| hard-coded 600 m vehicle-detail radius | cam+0x18 = 600 * zoom * sqrt(1 + tan^2(fov/2)) (849 m at 90 deg, zoom 1). It ignores the far clip and the Visibility Range option. camera_ClassifyDistance reads it as [0x4c2748] (+25 m) for the far-vehicle physics switch. | 0x472499 |
| frustum sphere test | camera_TestSphere(cam, viewPoint, r): outside the near/far z slabs (cam+0xe8/+0xec, +0xf8/+0xfc) with radius r, or outside any of the 4 side planes (cam+0xa0.., 16-byte stride) with radius 1.1*r -> 1 (culled). Otherwise it returns -(OR of straddle bits): 0 means fully inside. Callers store (~ret & 0x100) as a 'no clipping needed' flag in draw record +0x34. | 0x472cad |
| depth-sorted draw list (painter's algorithm) | Every queued primitive gets a sort z. Terrain min z (0x6543ac) is forced to -300 and max (0x6543a4) = farthest terrain vertex + 300. Records go into 1 m buckets idx = int(z - (-300)). idx > 4096 (0x1000) is silently dropped, so nothing deeper than about 3796 m is drawn: a far-clip patch past that also needs this raised. The flush clamps the top to 4096 and walks buckets from far to near. | 0x48fe61 |
| draw record kinds (record +0x0c) and dispatch 0x4faca8 | A record with a vertex count (+0x00 in 1..31) is drawn as a polygon by 0x4260d0 (hardware) or 0x471fd0 (software), whatever its kind. Vertex-less records dispatch by kind: 3 and 11 shadows (0x48f550), 5 scenery object (0x48f500), 6 world-record object (0x48f4c0), 7 billboard object (0x48f570), 10 headlight beam (0x490640). Kinds 0-2, 4, 8, 9 are no-ops. Polygon kinds in use: 1 terrain/road/decal, 2 skid mark, 4 clutter face, 8 tracer/trail/flame quad, 9 smoke puff. Kind 12 or more, or 32 or more vertices, is skipped. | 0x48fca4 |
| object LOD selection (Object Detail) | Let s = view z / cam+0x08 (metres per pixel) and r = world record radius (+0x10); +0x30 == 0 gives LOD 0. Detail ON: find the first i in 0..2 with r > s*lod[i] (lod[] = rec +0x1c/+0x20/+0x24, pixel thresholds). If one is found -> LOD 0: the compiled code collapses 1 and 2 to 0. If none: rigid bodies (type 1/7/9) with r < 0.4*s*lod[2] -> 11 (reduced vehicle: only child parts of type 0x41..0x44 are drawn), else 3. Detail OFF: rigid bodies always 3; others 2 if r > s*lod[2], else 3. Type 0x33 objects always get LOD 0. | 0x457f7f |
| object culling | World records (table 0x542830, 0x78 B, count 0x54a25c) are transformed by their object's pose, then culled by camera_TestSphere with radius 1.1*rec radius. Records with obj flag 0x100 queue each child node separately (radius obj+0x90*1.1). When camera_in_cockpit, or the camera callback is 0x407680, the player's own record (world_ctx_cache) is skipped. There is no distance cull beyond the camera far plane. | 0x457bbd |
| object queue order and kinds | Main pass 0x457ff0: child nodes are queued as kind 5 (or 7 if obj flag 0x40) at once. Non-rigid records are queued after rigid ones (kind 6). Then, if Shadow Detail != 0 and view z < 50 m: a shadow record for each visible record, kind 11 for non-rigid and kind 3 for rigid, with LOD 3 when Shadow Detail == 1, else the object's own LOD. The player's headlight beam (entity+0x440 'hlight') is queued at night only (0x477ac0()==0), with sort z -5 so it draws last, then every visible vehicle's beam. | 0x4583d6 |
| shadows off-screen | Records that fail the frustum test also drop their merge-group slot (0x6543b4 table) so a stale group cannot draw. | 0x45818b |
| terrain quadtree LOD (Terrain Resolution) | The terrain is rebuilt each frame as a quadtree in sample units (5 m, 128x128 samples per .ter tile, 128x128 tile grid with a 24-tile border). Root: the frustum's ground footprint, snapped to 32 samples. Node of half-size h at xz distance^2 d2 from the camera: h >= 32 always splits. h < 32 and outside the footprint planes (padding 1.42h) -> culled. d2 > (2h)^2*K -> leaf, with K = /cam+8/*A/(screen width/2) (A = 6.4 / 16 / 40 for Low / Medium / High). 2*d2 < (2h)^2 -> split. Otherwise split when any of 5 midpoint height errors *2h exceeds float_exponent(d2)*E, with E = /4tan^2/*B*5*10 (B = 1/256, 1/384, 1/576.7). Leaves larger than 4 samples whose border samples carry surface types 2,3,4,6,7 (not 0,1,5) keep splitting. | 0x491341 |
| terrain resolution constants | renderer_SetTerrainResolution / 0x493080: option 0 -> A=6.4 B=0.00390625; 1 -> A=16 B=0.0026041667; 2 -> A=40 B=0.0017342. | 0x4930a5 |
| camera under the ground | If the camera is less than 0.01 m above the terrain height, no terrain is queued and the view is cleared to palette index 0xb4. | 0x492a04 |
| terrain texturing (Terrain Textures) | Vertex UV = sample coordinate * 0.125 (one texture repeat per 8 samples = 40 m). options_terrain_textures [0x654b8b] picks the emitter pair: 0 -> flat (0x48e190, 0x4922f0), 1 -> textured (0x4923f0, 0x4924b0). A hardware device forces textures on. Mode flags: hardware 0x15 (0x59c584 = 9), software 0xf4 (0xe8). | 0x490f6f |
| terrain/road/object shading | shade = min(1, clamp(0.7496 + 0.000417*viewZ, 0.75, 1) * max(0, -(N . sunDir_view)) * sunIntensity + ambient). The time-of-day table 0x4fa0b0 gives sunIntensity (+0xc) and ambient (+0x10). The sun direction is (0,0,1) rotated by the table angle. The depth term reaches 1.0 near 600 m. In hardware, terrain uses per-vertex normals (0x490fb0); in software, per-face. | 0x4910fe |
| time of day | Period index = ((hour+2) % 24 * 8) / 24; 8 periods, 0x14-byte records at 0x4fa0b0: +0 daylight flag, +4 sun/moon map (nk_1sun1 or nk_1mon1), +8 sun angle, +0xc intensity, +0x10 ambient. Periods 0 and 1 (22:00-03:59) are night, flag 0. Dynamic lights (light_CollectVisible, light_SelectForObject) and headlight beams run only when the flag is 0. | 0x4781e7 |
| dynamic lights | At night, lights whose sphere (radius*3) passes the frustum are collected. Each object takes at most the 4 strongest by attenuation 1/(k*d^2+1), with k = light+0xc. Spot lights (flag 1) are scaled by 2^(e*(1-cos)/2), e = light+8. Light positions within 25 m of the terrain are lifted 25 m before shading. | 0x47822d |
| roads | Road segments (RSEG list 0x5db988) are culled by the camera's frustum bounding sphere (cam+0x80, radius +0x98) and by segment midpoint view z <= 450 m, then by a 10 m frustum sphere and backface test. The texture is one of 10 per road type (type % 3); z < 60 m uses slot set 0 and farther uses set +10 (road texture LOD). Byte [0x654b83] = 0 draws untextured (mode 0); otherwise mode 0xf4, or 0x17 in hardware. | 0x48ead7 |
| ground clutter (Terrain Detail) | Only when options_terrain_detail [0x654b82] != 0. Each template object in list 0x54ac70 is instanced in the 3x3 block of 100 m cells around the camera's 100 m-snapped cell (offsets 0x4f7190). Instances need a surface type enabled in 0x4be070 (types 0, 1, 5; types 1 and 5 use geometry variants 1/2), terrain height within 5 m of the camera's ground, view z <= 120 m and a 2 m frustum sphere. They are oriented by the camera-facing yaw matrix 0x5dd380 (billboards). | 0x45c619 |
| skid marks | A skid strip draws until its expiry time; quads with view z < 50 m pass a 10 m sphere and a backface test, colour index 0xfe, mode 0xc0, kind 2. | 0x445127 |
| smoke puffs (frame-rate dependent) | Emitters spawn their puffs each call. Each puff lives 20 frames (age +4 < 20), not a time. Position += velocity*dt, size eases toward its target with 2*dt, and a 256-entry jitter table drifts it. Drawn as a camera-facing quad (kind 9, mode 0x8c, 20 animation frames 0x4f1728) when near <= view z <= 60 m. Width is 1.7x the base for type 3, else 0.4x. | 0x44179f |
| smoke trails / flamers (frame-rate dependent) | Missile smoke trails lose up to 4 tail segments per frame from 2 s before expiry and clear at expiry (0x442ba0). Flamer streams lose 2 tail segments per frame (0x443e90), fall at 0.65*9.8 and blend toward a target, and damage what they touch through 0x4354c0. | 0x442bd6 |
| tracers | Tracer segments pass a 10 m frustum sphere at their midpoint. Type 2 is a line from the start extended 35% toward the next point. Other types are 3 quads plus an end triangle, colours and modes from the per-type table 0x4f1c38 (0x18 B). | 0x4421b0 |
| horizon (Horizon Textures) | Only if [0x654b8f] != 0 (forced to 1 on hardware) and a horizon is loaded. Camera = the view rotation with translation zeroed, far 100000, plus a vertical offset y = -camY*(6000 - 0.8*farZ)/farZ. The 16 strip quads (0x401970, mode 0x54) use UV inset 1/128 and luma 0 (software) or 0.8 (hardware). They draw directly to the locked screen before the depth flush. | 0x4017e9 |
| clouds (Clouds option) | The cloud dome is drawn with its own camera (far 100000) straight to the screen. Clouds off, or no cloud texture: flat polygons in the texture's average colour byte (or palette 0xef), mode 1. On: textured, mode 0x16, and the UV scroll advances once per call (frame-rate dependent, framerate.md #4). | 0x405200 |
| instrument overlay gate | Gauges draw in 0x45be20 only if not (network && render_gate_flags==0x10) and camera_IsHudHidden()==0. They are skipped when the player object flag 0x200 is set. Camera mode 2 skips the gauge bitmaps but still draws the rear-mirror frame. | 0x45be3d |
| render thread priority | WinMain raises the process to REALTIME_PRIORITY_CLASS for the scene render and drops it to NORMAL afterwards, every frame. | 0x403e47 |

## Third draw-distance ceiling: int16 terrain vertex indices (2026-10-02, live)

The terrain tessellator (`renderer_SubdivideTerrainQuad` 0x4916e7 -> `renderer_SplitTerrainEdge` 0x4918f0) stores
vertex indices in 12-byte edge records as **int16** (`(short)` store of the vertex count 0x6442ec, read back with
movsx). Once a frame queues more than 32,767 terrain vertices the index wraps negative and `fld [esi+8]` at
exe+0x91919 faults (esi = vertex pool [0x5dd320] - 0xF000). Tessellation is quantised in levels (~1.4k / 4.5k /
16.9k / 65.2k vertices); the cockpit view steps a level between far 2500 and 2750 m, the hood view (120 deg) one
level higher, binoculars (zoom 8.0, the 0x472400 clamp) two. Live matrix on t01 (`i76-everywhere
docs/FARCLIP-CAMERA-CRASH.md`): 1800 and 2500 survive every view; 2750 and above crash on binoculars; 8000 crashes on
the hood view. So the safe far clip is <= 2500 m whatever the pools hold; the depth buckets (3796 m) are the next
ceiling only in principle.

## Software rasteriser (range 0x470000-0x490000, batch `range-m-1`)

Static reading of md5 9a232dcc (2026-09-27), 176 names from a reviewed read-only draft (cluster M). Only the
software path lives here. The hardware path uses the plugin / D3D layer at 0x42d0c0.. (`renderer_DDraw*`) and the
.m16 textures.

- **Pipeline.** `renderer_DrawPolySW` 0x471fd0 -> clip/project table 0x4f9538[mode & 0x1ff] -> span setup table
  0x4f8d38[mode & 0x1ff] (`renderer_SpanPoly*`). The setup carves a 0x60-byte surface from a 64 KB arena,
  scan-converts its edges into the span buffer 0x58da68 and stores screen-space gradients.
  - `renderer_FlushSpans` -> `renderer_SpanBufferFlush` resolves visibility per scanline with an active-edge list.
    The later-submitted (nearer, in painter order) surface wins, and each surface's drawer (`renderer_SpanFill*`)
    runs only on its visible spans, so opaque pixels are written once.
  - Priority key surface+0x34 = class (0 opaque, 1 darken, 2 see-through) + 4 x submission index. See-through
    surfaces bypass span occlusion and rely on submission order.
- **Draw-mode bits** (the index into both tables):

  | bit / value | meaning |
  |---|---|
  | 0x01 | Gouraud (interpolated shade row) |
  | 0x02 | UV clamp to +-32 in the projector only; the drawer twins are duplicate code (`...UvClamp`) |
  | 0x04 | textured |
  | 0x08 | already in screen space (2D clip only) |
  | 0x10 | perspective correct (a divide every 16 px, 0x4be774) |
  | 0x40 | colour key: texel 0xff is transparent |
  | 0x80 | translucent through the 256x256 table 0x60afa0 |
  | 0xc0 (flat) / 0xc4 | darken remap 0x61b1a0 (skid marks) / glow table 0x609fa0 |
  | 0xa4 / 0xb4 | translucent, but a screen pixel of index 0xff takes the texel unblended (purpose open) |
  | 0xe0 block | textured, lit by one shade row per polygon (terrain and roads use 0xf4); 0xe3 / 0xe7 wireframe |
  | 0x100 | no clipping needed (set from `camera_TestSphere`) |

- **Lighting tables.** Shade colormap 0x61b2a0 [row][colour], shade row = (1 - light) x 8064 / 256 (0x4fa48c):
  rows 0..31 are real, 32..143 repeat row 31, 144..255 repeat row 0. Keyed blend 0x62b2c0; gamma 0x6095a0 (Monitor
  Brightness 1..10, base 0x6094a0 + level x 256); nearest-colour cache 0x63b2e0. A port can rebuild all of them
  from the palette.
- **Display drivers.** A driver table is copied to display+0x3e8. Its first word is the driver kind: 0 DirectDraw
  (software, table 0x4f9dc0, `renderer_SwDDraw*`), 1 hardware (0x42d0c0..), 2 GDI window (0x4fa498, `renderer_Gdi*`).
  0x5dd2a8 is that word, so "0x5dd2a8 == 1" in the frame section means the hardware driver. The slots are init,
  shutdown, lock, unlock, palette range, palette, mode, GetDC, ReleaseDC, restore, present and clear. Video modes
  come from the table at 0x4f9e08 (7 dwords each; default mode 5). The file-name suffix per mode is at 0x4f8aaf.
- **Also here:** the .pix / .pak pack index and file cache, texture pairs (8-bit + .m16), bitmap fonts (font+0x0c
  background row, +0x10c ink row, +0x20c glyphs), time-of-day and dynamic-light setup, palette fades, road segment
  setup, and the draw-record kind handlers and pools (0x48f500..0x48f9b0). `renderer_NoOp` 0x48e190 is the shared
  empty callback. It is also the default script-camera slot the frame-rate probe waits on.
- **Open (held, low confidence):** 0x473400 (edge-segment advance), and the static initialisers 0x472de0 / 0x47caf0,
  whose globals are only ever written.

## Open

Static reading of md5 9a232dcc (2026-09-27). All 99 auto functions in the work list are named. Key findings for a port: (1) Everything 3D goes through one painter's-algorithm list of 1 m depth buckets over [-300, 3796) m; records beyond bucket 4096 are dropped, a second draw-distance ceiling after the 512 KB terrain arena. (2) Object LOD uses pixel-size thresholds (world record +0x1c..+0x24 against radius/(z/focal)). With Object Detail on, LODs 1-2 collapse to 0 (the compiled code sets any index below 3 to 0), so the 5 LOD slots are mostly unused. (3) cam+0x18 (the far-vehicle physics radius) is a hard-coded 600 m term that no far-clip patch touches. (4) Frame-rate dependencies found here (not in framerate.md): smoke puff life is 20 frames; missile smoke trails retire 4 segments per frame in their last 2 s; flamer streams retire 2 segments per frame. (5) The render call runs at REALTIME_PRIORITY_CLASS. Open: the purpose of the 0x5dcef4 bitmap cleared when shadows are on; byte 0x654b83 (road textures) has no direct menu writer (it is written as part of dword copies); shadow rasterisation 0x4bb760 and the object BSP builders 0x45cbe0/0x45da70 are not read. 0x654b88 is toggled by the cockpit camera modes (0x406920/0x406f30 xor 1) and read as 'cockpit panel shown'. Evidence sites are instruction starts from tools/disasm.py.
