# camera (camera modes, cockpit, HUD, radar)

**Contract.** The camera controller at 0x4c2720 holds the current mode's per-frame function and a 0x268-byte state
block; the camera struct at 0x4c2730 goes to the renderer. The block can be pushed and popped on an 8-deep stack at
0x5dbb20. A view id (0xd..0x1b) selects a mode through the transition table 0x4c2994 (`0x4096c0`). Keys reach it
through the command-key dispatcher 0x44e030. The mode runs once per frame from WinMain (0x403e16), and on one path
from inside the player's tick (0x46391f). Script cameras are FSM actions (fsm_Cam*, `mission.md`, `framerate.md`).

Static reading of md5 9a232dcc (2026-09-27), batch `camera-map-1` (69 names), from a reviewed read-only draft (cluster I). Keys
come from the sandbox gamekey.map / KEYBOARD.MAP. Directions (front/back, left/right) are decoded from the maths,
not seen in game.

## Views

| view id | transition | per-frame | key | what | frame rate |
|---|---|---|---|---|---|
| 0xe | 0x406920 | 0x406ab0 | PRESET_VIEW_1 = F1 (gamekey.map); also the 'on' half of toggle_cmbt_view V (0x44dfa0) | camera_mode 0, cockpit seat. Eye = the vehicle's eye node entity+0x398 (object_GetTransformRelativeTo 0x458cb0) x acceleration head-sway (0x437f90) x head-look Euler from pilot_glance inputs 0x536770/78/80 (degrees). Sets 0x4c2724=1 (in-cockpit), zoom 1.0 and zoom_factor 0x5367a4=0x10000. Re-selecting while already mode 0 flips 0x654b88 (2D dash <-> 3D cockpit: 0x401cc0 draws 0x45adf0 'Ckpt3' or 0x45be20 'Ckpt2'). | dt-scaled: head-look eases x += 4*dt*(target-x) (snaps when 4*dt>0.95 or /err/<0.005); sway eases at 2*simdt. First-order neutral; targets are absolute angles, not accumulated. |
| 0xd | 0x406f30 | 0x4071a0 (binoculars) / 0x406ab0 (back to cockpit) | toggle_binoculars B (input 0x5367f0 -> input_ApplyToEntity 0x44f6c2..0x44f6e2); fsm action 0x34 also forces it off | Binocular toggle. From mode 0/2: 0x462130 toggles the binocular mask flag 0x54b67c (swaps the two overlay objects 0x54b680/0x54b684); if now on -> camera_mode 2 with 0x4071a0, else back to cockpit mode 0. 0x4071a0 = cockpit eye (eye-node chain walked up to the car root) with head-look, zoom = zoom_factor [0x5367a4]/65536 (camera_SetZoom clamps 0.5..8). | head-look eased at 2*dt (half the cockpit rate); zoom is whatever the input layer accumulated in 0x5367a4 (not traced here). |
| 0xf | 0x407ea0 | 0x4061b0 | PRESET_VIEW_2 = F2 | camera_mode 7, track/orbit camera. Orbits the car's heading frame (yaw-only quat 0x4060c0, slerped at 2*dt) at track_distance [0x53678c] clamped 1..10 x target radius (cap 150 m); pitch/yaw 0x4c2918/0x4c291c driven by track_pitch/yaw inputs 0x536794/0x53679c (1 deg per unit per call), pitch clamped [1 deg, 90 deg]. Keeps the previous orbit angles (0x4c2928=0x4c2918...). Defaults pitch 30 deg, yaw 0 (behind) from camera_ApplyViewOptions. Terrain clamp +0.6 m (0x493550). | FRAME-RATE DEPENDENT (framerate.md row 5): angle += input x 1 deg per call. Smoothing toward the target uses 2*dt. |
| 0x10 | 0x407950 | 0x407ad0 | PRESET_VIEW_3 = F3 | camera_mode 1, chase at fixed pitch 15 deg (0x3e860a92) and yaw pi (0x40490fda). Decoded rotation (0x407bf3..0x407ca0): camera at (0,0,-d) x Rx(pitch) x Ry(yaw) x heading, so yaw 0 is behind the car and yaw pi puts it in front looking back (reverse chase). Distance = track_distance 1..10 x radius (cap 150), eased 2*dt; heading slerp 2*dt; terrain clamp. | dt-scaled (2*dt easing and slerp); neutral to first order. |
| 0x11 | 0x407500 | 0x407680 | PRESET_VIEW_4 = F6 | camera_mode 1, hood/bumper camera: FOV 2pi/3 (camera_Init arg 0x40060a92), offset (0, 0.7, 3.5) in the car frame (push 0x3f333333 / 0x40600000 at 0x4078a4..0x4078af), head-look from pilot_glance inputs. camera_IsHoodView 0x407930 lets the object pass 0x457a90 skip the player's own car and keeps HUD paths on. | head-look eased at 4*dt; neutral to first order. |
| 0x12 | 0x409400 | 0x409540 | PRESET_VIEW_5 = F11 (0x44e030 also clears the binocular mask for 0x12) | camera_mode 8, missile/projectile camera. Only if weapon_GetCameraProjectile 0x4a7150 returns a projectile owned by the player (object_IsPlayer). Pushes the controller block (stack index 0x4c2988 decremented), world_ctx_cache 0x4c2908 = projectile. Camera 5 m behind, pitched 20 deg (0x4bc5e0 = 0.349 rad, 0x4bc5e8 = 5.0) in the projectile's frame. When the projectile is no longer current, lingers 1 s (0x507d0c, dt) then pops the stack and runs the restored callback. | rigid geometry; linger timer uses dt. Neutral. Note: during the 1 s linger it still reads the stale projectile's +0x18 transform (0x40959b), not the 0x507d50 copy it saved. |
| 0x13 | 0x408350 | 0x408240 | PRESET_VIEW_6 = F7 | camera_mode 1, car-mounted rigid view: Euler (0,0,0), offset (-1.5, 0, 0.2) from the target centre in the car frame = left-side camera looking forward. | stateless rigid attachment (terrain clamp only). Neutral. |
| 0x14 | 0x4084a0 | 0x408240 | PRESET_VIEW_7 = F8 | camera_mode 1, car-mounted rigid view: yaw pi, offset (-1.5, 0, -0.25) = left-side camera looking back. | stateless. Neutral. |
| 0x15 | 0x4085f0 | 0x407ad0 | PRESET_VIEW_8 = F9 | camera_mode 1, chase at pitch 15 deg, yaw 5pi/6 (0x40278d36 = 150 deg from behind: front quarter, on the car's +x side). | as chase: dt-scaled. |
| 0x16 | 0x408770 | 0x407ad0 | PRESET_VIEW_9 (no default key in gamekey.map) | camera_mode 1, chase at pitch 15 deg, yaw pi/6 (0x3f060a92 = 30 deg off behind, rear quarter). | as chase: dt-scaled. |
| 0x17 | 0x4088f0 | 0x408a10 | PRESET_VIEW_10 = F10 | camera_mode 3, overview (straight down). Height 0x4c2914 starts at 100 (0x42c80000), zoom *= 1 + 0.01*overview_zoom_delta [0x5367bc] per call, clamped to [4 x target radius, 0.85 x camera far clip 0x4c2740]; camera at (x, terrain(x,z)+height, z), rows (1,0,0),(0,0,1),(0,-1,0). The overview_x/z pan inputs are not read here. | FRAME-RATE DEPENDENT (framerate.md row 8): multiplicative zoom step per call, no dt (0x408a2b..0x408a51). |
| 0x18 | 0x408b50 | 0x408c60 | PRESET_VIEW_11 = F5 | camera_mode 4, enemy view. Needs a radar target (entity_GetRadarTarget 0x4613f0); pushes the block unless already mode 4. Each frame stores player pos 0x507d10 and target pos 0x507d28, then 0x408d90(target, player): camera 3 m above the target, 7.5 m back along target->player, tilting down up to 30 deg with distance. Target lost: lingers 3 s (0x507d0c) then pops the stack. | rigid geometry; timer uses dt. Neutral. |
| 0x19 | 0x409030 | 0x409140 | PRESET_VIEW_12 = F4 (manual: 'use the F4 view in combat') | camera_mode 4, target view: same as 0x408c60 with the arguments swapped (0x4091da/0x4091df), i.e. 3 m above and 7.5 m behind the player on the player->target line, target kept in frame. | Neutral. |
| 0x1a | 0x406e00 | 0x406ab0 | none (camera_ApplyViewOptions 0x405970 with arg 1: level start / after video-mode change) | camera_mode 0 cockpit reset: zoom 1, zoom_factor 0x10000, 0x4c2724=1; unlike 0xe it does not touch the heading quats or 0x654b88. | as cockpit. |
| 0x1b | 0x408030 | 0x408240 | automatic: entity_TickVehicle 0x463800 (0x4638f0..0x46391f) when 0x436570 says the player is inside a class-0x5c volume | camera_mode 9, interior/tunnel camera. Refused in modes 0/2/5. Pushes the block, then rigid mount behind the car: offset (0, 2, -bound radius) (entity_GetWorldBoundSphere 0x457650), track_distance forced from the radius. When the player leaves the volume 0x463800 pops the stack (camera_PopState 0x405910). 0x54b9b0 holds last tick's camera_mode for the edge test. | stateless rigid. Neutral. |
| 0xfefe | 0x409270 | 0x405b90 | automatic: WinMain network end of match (0x403bcb, 0x403d1f), which then writes track_yaw_delta 0x53679c = 8 | camera_mode 6, orbit A (same as orbit B 0x4061b0 plus a null-object check). With track_yaw_delta forced to 8 it spins around the car. | FRAME-RATE DEPENDENT: yaw += 8 deg per call (0x405c16..0x405c28) -> spins 3x faster at 60 fps than at 20. |
| (none) mode 5 | 0x49d420 | 0x48e190 (1-byte ret) | fsm action 0x34 (0x413083); fsm action 0x35 -> 0x49d470 pops | camera_mode 5, script camera: pushes the block and installs a no-op callback; the fsm camera actions (0x49d4a0, 0x49d5f0, 0x49d740, 0x49dac0, 0x49dda0 via 0x5a7ee0) drive the camera struct directly. camera_SetView refuses to switch while mode 5 or 9. | depends on the fsm camera actions (not mapped here). |

## Radar, HUD, cockpit

- **Radar visibility.** Cars with the engine off are invisible to the radar, and to AI gun emplacements.
- **Radar range.** Contacts are kept out to 600 m whatever the range key says; R only rescales the display.
- **Radar ping.** Locked on, every other blip in the wedge pings every frame (`framerate.md`; coalesced by the proxy).
  0x460c80 is the per-contact helper called by 0x45faf0, not a separate post-tick.
- **Mapped here:** gauges (0x459fa0; speedo VLOC 35, tach 36 - `engine.md`), the damage diagram, gear, specials,
  compass, target brackets and the rear mirror (off / objects / full).
- **Frame-rate dependent:** the orbit keys (1 deg per frame), the end-of-match spin (8 deg per frame), the
  overhead-map zoom, the mirror refresh.
- **Naming note:** `renderer_DisableCockpitMask` 0x4621b0 actually turns off the binoculars overlay (a better name
  is pending).

## Notes

Camera controller = 0x268-byte block at 0x4c2720 (callback, in-cockpit flag, mode, camera struct 0x4c2730, target ctx 0x4c2908, angles/offsets/quats up to 0x4c2980), stack index 0x4c2988 right after it; the stack 0x5dbb20 is 8 deep and grows down (push 0x4058b0 decrements, pop 0x405910 increments). Target cams (4), missile cam (8), tunnel (9) and script (5) push on entry; every transition pops first when leaving mode 4; the missile/target cams pop themselves after their 1 s / 3 s linger; the tunnel pops in entity_TickVehicle. Default keys from sandbox-gog gamekey.map: F1 PV1 cockpit, F2 PV2 orbit, F3 PV3 reverse chase, F4 PV12 target view, F5 PV11 enemy view, F6 PV4 hood, F7 PV6 left-front mount, F8 PV7 left-rear mount, F9 PV8 chase 150 deg, F10 PV10 overview, F11 PV5 missile cam, PV9 unbound; KEYBOARD.MAP: B binoculars, V toggle_cmbt_view, W radar_camera_toggle (weapons camera, 0x460e10), grey arrows track_*/pilot_glance, grey PgUp/PgDn zoom/track distance/overview zoom. Chase yaw convention decoded in 0x407ad0 (0x407bf3..0x407ca0; math_SinCos returns sin in eax, cos in edx): camera = (0,0,-d) x Rx x Ry x heading, so yaw 0 = behind and pi = in front looking back. 'Left' and '+x side' assume the car's local +x is its right row (physics.md row order). Confidence medium until seen live. Frame rate: dependent = orbit angles (1 deg per input per call, 0x405b90/0x4061b0), end-of-match auto-spin (track_yaw_delta = 8 per call via view 0xfefe), overview zoom (0x408a10), rear mirror refresh every 2 frames (0x445750). The dt-scaled first-order easing (4*dt cockpit/hood head-look; 2*dt chase distance, heading slerp, binoculars, orbit smoothing, cockpit sway) is near neutral but snaps at low fps (rate*dt > 0.95). Mounted, target, missile and tunnel views are stateless. Radar contacts use a 1 Hz sim-time catch-up (neutral). Radar: 0x45faf0 is the type-34 post-tick (list rebuild, lock intensity 0xff, jammer/off clears) and calls 0x460c80 per contact, so 0x460c80 is its per-contact helper, not a twin post-tick as framerate.md words it. Contacts are admitted within 600 m horizontally whatever the range toggle (+0 of the radar entity), so the R key only rescales the display (blip routine 0x460310..0x460a70: zrad.map, range_pos, led_pos radled_1/radled_2 lock LEDs, CGROWL.WAV lock growl, CRADAR.WAV ping). Engine off hides a car from radar (object_IsRadarVisible 0x466de0) and from AI emplacements (0x45f970). Mirror 0x445750: eye-node transform with the right and forward rows

## HUD drawing (static reading, md5 9a232dcc, batch `gap-hud`)

**Layout source.** `vpit_1.elt`, named by the VDFC ELT field and loaded by `elt_Load` 0x448010; the exe never parses ETBL.
Each `dst` map is a face texture on the cockpit model, found by name (`object_FindByTextureName` 0x4588b0). `dst`
labels are pixel (x, y) positions in that bitmap; `src` labels are sprite rectangles. Two sets: video-mode byte
0x654b80 < 6 selects the large set (zbk_.map, zsy_.map, zcm_.map, labels without the leading '3'); otherwise the
'3'-prefixed 320 set is used. The flag (0x4fed64 set at 0x4a4664, 0x4f67ec set in 0x459910) is added to every
label pointer, which skips the '3' (0x4a4dde).

| dst labels | src sprites | writer |
|---|---|---|
| zbk_: bracket_1..5 | housing1..5 (zwpe), random per row | `renderer_InitWeaponPanel` 0x4a481d |
| zbk_: dymo_1..5 | GDFC on/off names, weapdef+0xa8 / +0xbd | 0x4a48e2; cycle 0x4a5dbf / 0x4a5e4b; link 0x4a6391 |
| zbk_: diode_1..5 | off/green/yellow/red/drk (zdde) | `weapon_HudSetConditionDiode` 0x4a4e0a |
| zbk_: num_{thous,hunds,tens,ones}_N | top/bottom digit strip (znbe) | `weapon_HudRollAmmoDigits` 0x4a4f44 |
| zbk_: separator_N | sepbar (zbar_) | end of cycle / link / unlink (0x4a6117) |
| zsy_: engine suspen brakes rrtire rltire frtire fltire farm larm rarm barm fchas lchas rchas bchas | part_{off,grn,ylw,red,drk} (zsye) | `renderer_UpdateDamageDiagram` 0x45a628 |
| zcm_: compass_window | left / right (zcme), x-scroll | 0x459fa0 |
| zgear101: prnd; park reverse neutral drive second first | prndback; arrow | 0x45ada0 / 0x45adc0 |
| zspeedo3/6 speedneedleloc, ztach3/6 tachneedleloc | needle_N (zneedle6 / zneedle3) | 0x459fa0, 2D dash only |
| zrad: range_pos, led_pos | range_1 / range_3 (zrge); radled_1 / radled_2 (ztge) | radar painter 0x460310 |
| zbks_: sp_* | zdse | specials panel 0x4679a0, 0x467a70, 0x467b50 |

`range_2` is never drawn: the table at 0x4f7610 holds range_1, range_3, range_3.

**Weapon panel.** One row per sorted slot (`weapons.md`, Weapon groups). Panel bitmap: 182x126 (large set) or
106x59 (320 set) (0x4a4a00). `renderer_InitWeaponPanel` 0x4a45c0 runs at vehicle init (arg 1, 0x463799) and
after a video-mode change (arg 0, 0x44e3c8). For each row:
- housing k = trunc(rand()/32767 x 5) (0x4a47c2..0x4a47dc; k = 5 only at rand() = 32767, an empty name); diode forced; dymo on if selected; digits drawn from the ammo.
- The separator goes after the last row whose mount flag is front (1) or turret (4) (0x4a483d..0x4a484a), at label separator_(k+1).
- **Diode** 0x4a4d50: p = trunc(100 x hp / max) (inst+0xc over weapdef+0x64, 0x4a4d7a..0x4a4d9d). Table 0x4fe798
  {name[24], lo, hi}: off 100, green 67-99, yellow 34-66, red 1-33, drk 0 (0x4a4db0..0x4a4dbe).
  An undamaged weapon shows `off`. Redrawn only on a state change (cache rec+0x3c+4 x row, 0x4a4dc0) or when forced; called every frame (0x4a444b).
- **Ammo** 0x4a4e40: four digits, ammo mod 10 up to (ammo/1000) mod 10 (0x4a4e5f..0x4a4eb9).
  - Each shown digit (tables 0x4fec40/58/70/88) steps -1 per call, wrapping -1 -> 9, until it matches (0x4a4eda, 0x4a4eec).
  - It is drawn at digit x 0.1 of the way from `top` to `bottom` of the strip (0x4a4f04, image_BlitEltSpriteScrollY 0x4a4f44).
  - **Frame-rate dependent**: one step per frame, so a full roll takes 0.45 s at 20 fps and 0.15 s at 60. A rising count also rolls down through 9.
- Any change sets 0x5da74c, and the face texture "Weap" is invalidated (0x4a44dd..0x4a450c).

**Damage diagram** 0x45a450 (called from the gauges 0x459fa0). p = trunc(hp x 100/max + 0.5), so it is rounded
here (0x45a4a0..0x45a4ac), where weapon diodes truncate. The scales are set once per car by 0x459330 (latch
0x54a40c, 0x459fdc). Bands are the same as the diodes (tables 0x4f5f20..0x4f6448, stride 0x18, 5 per part): off
100, grn 67-99, ylw 34-66, red 1-33, drk 0 (0x45a5ef..0x45a5fd). Sources: engine +0x3c4, suspension +0x3c8, brakes +0x3cc; tyres rr +0x3b8, rl +0x3bc, fr +0x3a8, fl +0x3ac (the
mid pair is never shown); armour sides 0 front / 1 left / 2 right / 3 back = +0x138.. over +0x158..; chassis
+0x148.. over +0x168.. (0x45a8c8..0x45a997). It redraws only on a state change (caches 0x54a418 and 0x54abd0, reset to -1 by 0x459910). Entering `drk` plays
CWSTAT.WAV (0x45a630..0x45a640). Any change invalidates "Status".

**Gear** 0x45ad40. On a lever change it plays VSHIF1A.WAV, draws prndback at `prnd`, then the arrow at
park / reverse / neutral / drive / second / first [lever] (0x45ad73..0x45adc0).

**2D needles** (2D dash, 0x654b88 = 0, player only): speedo sprite needle_(9 + trunc(0.19333 x mph)), mph clamped
0..150, cap 38 (0x45a118..0x45a13c); tach needle_(trunc(0.003 x rpm + 1)), cap 25 (0x45a2c5..0x45a2e8). Gauges update only in the cockpit (0x4c2724) or with `options_ext_instruments` 0x654b8e set (0x459ff8, 0x45a001).

**Radar data** obj+0x70, 0xb8 bytes (0x45f780): +0 range index, starts at 1 = 600 m (0x45f7bd); +4 contact list;
+8 sweep state; +0xc flags (1 on, 2 target view, 4 disabled, 8 cleared, 0x10 locked); +0x54 locked contact; +0x78 owner; +0x80 face bitmap.

**Contacts** (`entity_UpdateRadarContacts` 0x45faf0). A car is admitted within 600 m horizontally (0x4f760c, 0x45fd37)
if it is class 0x5a / 0x5b or passes `object_IsActiveVehicle` (0x45fd19..0x45fd24). The list is sorted by distance. Record (0x24 bytes): +0 object; +0xc / +0x10 offset (rx, rz) rotated by the
owner's heading (0x45fc5f); +0x14 distance; +0x18 age clock; +0x1c blip palette index.
- Blip index: 0x69 for a new contact (0x46010f); +3 per whole second of sim time until >= 0x69 (0x45fce4..0x45fcf9);
  0xff every tick for the locked contact (0x45fe32).
- An active jammer on the owner (0x45fb5c) or on any admitted car (0x45fe5b) wipes the list and the lock.

**Painter** 0x460310, a texture-animation task on zrad (registered at 0x45f88f; args object, map, state). It paints only
the player's radar (0x460336). Off or disabled: bank 0 frame 30, a blank (0x460a47). Outside the cockpit it needs
`options_ext_instruments` (0x4603ae..0x4603be).

**Sweep** (no lock):
- It repaints only when sim time passes the next step time. Before stepping, prev = cur (0x4606ec).
- Every 0.2 s of game time (0x4606f9), cur = next[cur] (0x460709). The table 0x54b170 cycles 0..29 (0x45f4a5..0x45f4ba):
  30 positions, one turn in 6 s, with catch-up, so the sweep is frame-rate neutral. Frame = bank 0 frame cur (0x46072f).
- **Ping**: lo = prev x 2pi/N, hi = cur x 2pi/N with N = 29 (state+4, set at 0x45f870), both wrapped into (-pi, pi]
  (0x4607a1..0x460811). A blip that is not the locked one pings when lo <= atan2(rx, rz) <= hi: its index is set to
  0 and CRADAR.WAV plays (0x4608c7..0x4608f1).
- Quirk: the art has 30 frames per turn (the lock path uses 30/2pi), but pings use 2pi/29. Pings drift from the beam
  by up to one step (about 12 deg), and the 29 -> 0 window has zero width.

**Locked** (flag 0x10): bank 1 (0x4603e0); cur = trunc(bearing x 30/2pi), wrapped to [0, 30) (0x4603eb..0x460425).
It repaints every frame. prev stays frozen, so every other blip between the last sweep step and the target pings
every frame (the proxy coalesces these pings). Cars are drawn; other contacts only if they are the locked one
(0x46051b..0x46052a).

**Blip**: x = rx/R, z = rz/R, with R = 100 / 600 (0x4f7608 [range]). It is drawn when x^2 + z^2 <= 1
(0x46087c..0x46088d), as 2x2 pixels of palette index +0x1c at (clamp(trunc(99 + 51x), 0, w-2),
clamp(trunc(65 + 51z), 0, h-2)) (0x460902..0x46098e). The colour is the zrad palette at that index (0 = just
pinged, 0x69 = fully aged, 0xff = locked). Blips are drawn nearest first, so far blips overwrite near ones.

**Range**: range_pos gets range_1 (100 m) or range_3 (600 m) (0x46077e). The range key toggles 0/1 (0x460dd2); range reset sets 1 (0x460de0).

**LED**: led_pos gets radled_1 when the list holds any car, even outside the scope, else radled_2
(0x4609ac..0x460a13). CGROWL.WAV plays on the rising edge (latch 0x54b1fc, 0x4609d2..0x4609ee). **Correction:**
it shows radar contact, not lock.

**Target view** (flags 0x10 and 2, zradmask loaded): `renderer_DrawRadarTargetView` 0x460a70 draws instead
(0x460361..0x46039e).
