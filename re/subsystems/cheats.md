# cheats

Everything a trainer needs, from the game's own switches to direct state pokes. Static reading of md5 9a232dcc
(2026-09-27) unless marked. Tags: **[static]** read from the code, **[live]** measured in the running sandbox,
**[lab]** measured in the lab on the AiO build 60abf7bc and not yet re-checked here (same link as 9a232dcc outside
the 45 patched clusters, finding L001).

## 1. The game's own switches (safest: the game's code does the work)

**Play Options bits** - `options_play_flags` 0x654b98 (dword; saved copy 0x654bf8), read by the damage and ammo code:

| bit | effect | scope | where |
|---|---|---|---|
| 0x01 | arcade physics | | `physics_InitEntity` 0x438f06 [static] |
| 0x02 | no salvage management | | salvage_* |
| 0x04 | unlimited ammo | offline (0x452d20) | `weapon_Update` 0x4a418b copies it to 0x5da798 every call. The offline fire paths 0x4a6470 (0x4a67dc, 0x4a68c0) and 0x4a6e90 (0x4a6f37) test it; 0x4a42d3 is on the network-only branch (0x4a4257). [live: the fired weapon stopped losing ammo] |
| 0x08 | unlimited armour: damage amount zeroed before absorption | player, offline | `entity_ApplyDamage` 0x465620 [static] |
| 0x10 | unlimited chassis | player, offline | `entity_ApplyDamage` 0x465620 [static] |
| 0x20 | windshield wiper | | |

Setting any of 0x1c through the menus makes 0x495170 / 0x4970f0 / `shell_MenuDone` 0x497a00 set **0x535f78 = 1** -
a "cheats used" marker. Its one reader is WinMain at mission end (0x40412f): if the game state 0x4c2164 (`shell_SetGameState` /
`shell_GetGameState`) is 1 at mission end and the marker is set, the state becomes **0xb** (0x404137). The mission-over menu (0x497760) then turns 0xb into
0 (failed) and offers 'Turn off Cheater Options': a cheated win gives no salvage, no vehscn.vsf and no scene advance
(`mission.md`). A trainer that pokes the dword mid-mission does not set
the marker. 0x4970f0 clears it.

**Built-in cheat codes** - typed while holding Ctrl+Shift. The key path is 0x44dec0 -> handler 0x44bde0 (key word
with modifier bits 0x300). The last 15 characters are kept in 0x6092f0 and suffix-matched [static]:

| code | effect | code path |
|---|---|---|
| `wiggleburger` | toggles 0x5a6158 (read by 0x498720..0x498910; described in the community as double vision) | 0x498700 |
| `freelance` | toggles 0x4c2718 (next to the camera block; `camera_ApplyViewOptions` sets it to 1; effect to confirm) | 0x405b30 |
| `getdown` | every type-9 object gets 0x40bc40 (turned hostile), `gdsgc69.wav` plays, 0x51f5c0 = 1; the script VM 0x40a320 then treats the player's death as mission success | 0x40a050 |
| `flflat` / `frflat` / `blflat` / `brflat` | one wheel (component slots +0x3ac / +0x3a8 / +0x3bc / +0x3b8) gets 0x46da30(wheel, 0, 80) (health 0, max 80), then 0x46ddd0 (flat flag +0x44 = 1, radius +0x1c x 0.688, `tblow.wav`) | 0x46da30, 0x46ddd0 |
| `thirdnostril` | shares the flat-tyre tail (component slot +0x3b8 in the decompile); exact effect to confirm | |

**Self-destruct**: Ctrl+Alt+X sets `input_self_destruct` 0x5367f9 -> `object_Destroy` (lab cheatlib.ps1).

## 2. Player vehicle state (pokes)

Player object = [[0x54a264]] (world root; `world_GetRoot` 0x457530 returns 0x54a264); entity = object+0x70.
The entity layout below comes from `entity_ApplyDamage` 0x465620, `entity_SideHealthRatio` 0x466c20,
`entity_InitVehicle` 0x463120 and `entity_ComponentHealth` 0x466ac0 / `..MaxHealth` 0x466b70 [static]:

| entity offset | type | meaning |
|---|---|---|
| +0x138 [4] | int | armour, current, sides 0..3 (absorption copy) |
| +0x148 [4] | int | chassis, current, sides 0..3 (absorption copy) |
| +0x158 [4] | int | armour, max |
| +0x168 [4] | int | chassis, max |
| +0x178 [5] | int | armour, current (HUD copy; side 4 is a percentage, x0.01) |
| +0x18c [5] | int | chassis, current (HUD copy; side 4 a percentage) |
| +0x188, +0x19c | int | side 4 of the two HUD banks (engine / top), decremented by the side-4 path |
| +0x3a8 [24] | object* | components; wheels are type 30 in slots 0, 1, 4, 5 |
| +0x454 | uint | state flags: 0x20 dying, 0x4000 critical, 0x8000 wrecked, 0x20000 snap to ground |
| +0xac | float | speed (derived) |
| +0xbc [3] | float | world velocity (the state; tyre grip pulls it back to wheel speed within a step) |
| +0xe0 / +0xe4 / +0xe8 | float | steer / throttle / gear direction (written by input each frame) |

Offline, `entity_InitVehicle` doubles the player's armour and chassis and multiplies component health by 4 (live:
wheels 400, engine 1200; capture 012 measured armour x2).

**Component health** (component object +0x70 -> component entity), by component type [static, 0x466ac0 / 0x466b70]:

| type | health | max |
|---|---|---|
| 20, 21, 23 | +0x0 | +0x4 |
| 22 | +0x4 | +0x8 |
| 24 | +0x8 | +0xc |
| 30 (wheel) | +0x4 | +0x8 (flat flag +0x44, radius +0x1c) |
| 50 (weapon) | 0x4a4c50(obj) | 0x4a4c90(obj) |

**Repair** = for each side i: +0x138[i] = +0x178[i] = +0x158[i]; +0x148[i] = +0x18c[i] = +0x168[i]; each component
health = its max; each wheel's flat flag 0 and radius restored (the original radius is not kept by 0x46ddd0: keep a
copy from before). Side 4 of the HUD banks is a percentage (100 = full) - to confirm live.

**Transform** (teleport): object+0x18 = 3x3 rotation rows right/up/forward (floats), object+0x40/+0x48/+0x50 =
position doubles. A write during the render window is undone when `I76_RENDER_INTERP` is on (the interp restore);
write twice a frame apart.

## 3. Weapons and ammo [lab]

From `i76-uncap-lab\docs\WEAPONS-MEMORY.md` (live on 60abf7bc):
- live ammo: weapon instance table 0x5aab08, stride 0x4c, count 0x5da750 (`weapon_UnregisterVehicle` 0x4a3580).
  Ammo is at +0x20 (the lab's base 0x5AAB0C + 0x1C); 0x0FFFFFFF = unlimited. +0x08 -> an object whose +0x00 is the
  .gdf asset name ('gcmedium'). [live: reads, writes and read-back on the sandbox]
- per-vehicle weapon records: 0x5be4d8, stride 0x2c8, count 0x5da78c; `weapon_Update` 0x4a4130 runs per record;
- weapon definition table 0x5D8800, stride 0xD8, per mission (name +0x00, default ammo +0x7C): editing it changes
  defaults, not live ammo.
- The fire path: `weapon_Update` 0x4a4351..0x4a43ac jams by condition ratio and decrements ammo by int(dt x rate)
  (subsystems/framerate.md).

## 4. Safe hook points (proxy)

- `entity_ApplyDamage` 0x465620 (entity, side, record, is_player): returning early for the player = god mode
  without touching the kill roll or scripts.
- `object_Destroy` 0x4652b0: the one direct-kill entry (scripts, self-destruct, impact, fall height > 35 m).
- The Play Options dword is the least invasive switch: it is what the game checks, offline only.

## Open

- Re-verify section 3 on 9a232dcc / the sandbox 4fabc303.
- `freelance`, `thirdnostril`, `wiggleburger`: confirm effects live.
- Money / salvage state for the campaign (salvage_* 0x4b1610 / 0x4b16e0).
