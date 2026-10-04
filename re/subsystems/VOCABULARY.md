# Naming vocabulary (PILOT-1 changes 1, 2 and 8; method doc section 6, G4 amendment 2026-09-05)

Function names are `prefix_CamelCase`: one lower-case prefix from the table below, an underscore, then
CamelCase words that say what the function does and no more than the evidence supports. Global names are
`prefix_lower_snake` (existing rows: `input_weapon_fire`, `gamekey_key_queue`, `ds3d_listener`). Types are
spelled as in `types\i76.h` (`uint32_t`, `uint8_t`, `FILE *`); param identifiers are not part of the G4 key
(index + type are), so spell them freely.

G4 accepts two names that are equal after lower-casing and dropping separators (spelling), and two names whose
part after the prefix is equal that way (prefix): the merge then takes the prefix that both views' prefixes
resolve to in this table, or the one the reviewer names in `reconcile: {name: <one of the two spellings>}`;
otherwise the key requeues with reason `G4 prefix`. Two names with different words after the prefix still
requeue: the words are the independent part of the consensus. Amendment 2026-09-26: when both names describe the
same behaviour (synonyms), the reviewer may pick exactly one of the two with `reconcile: {name: X, synonyms: true}`
(prefixes must fold together; never a third name) - requeued synonym pairs came back swapped instead of converging.

| canonical prefix (= subsystem) | aliases the merge folds into it | scope |
|---|---|---|
| bwd2 | | BWD2 container walker and records |
| shell | i76shell, menu | the MW2 shell DLL boundary and its 27 callbacks |
| heap | heapPool, heappool | the private-heap wrappers 0x5a7cc0 etc. |
| pool | | pool_Reserve 0x498940 / 0x499ce0 carve pools |
| ai | | computer drivers: throttle/steer controllers writing entity+0xe4 / +0xe0 (0x40f9c0, 0x40fd20, 0x40fe80, 0x41b6e0 ...) |
| salvage | | parts taken from destroyed vehicles into the player's salvage (0x4b1610 / 0x4b16e0; off with Play Options 'No Salv. Manag.') |
| fsm | | 0x412ce0 / 0x414670 / 0x410a10 state machines |
| profiler | prof | |
| simclock | clock, tick | GetTickCount clock in 0x49c920, dt 0x4fe428 |
| lzo | | LZO1X / LZO1Y 0x4ba980-0x4baed5 |
| crt | | CRT-shaped helpers not matched as library |
| ffb | | force feedback loader 0x446020 and descriptor writer |
| entity | | world/entity chain [0x54a264] |
| zfs | | ZFS archive 0x4b9800 / 0x4b9bd0 / 0x4b9fc0 |
| renderer | videolog, d3d, ddraw, ddsurface, glide, video | renderer plugin loader 0x426900, caps logging, surfaces, screenshots |
| input | mouse, cursor, joystick, gamekey, keyboard | input block 0x5367cc.., gamekey queue 0x608e60, mouse_Poll 0x44b8c0 |
| camera | cam | |
| physics | phys | |
| player | plyrdef, player_def, plyr | player definition save/load |
| world | | |
| math | calc, geom, Geom | rsqrt 0x495000 and friends |
| startup | install, cmdline, winmain | WinMain 0x402b30, install checks 0x4b2220, cmdline 0x49d1d0 |
| vfs | FileMap, filemap, file | file mapping / path helpers |
| image | pcx, smk, bmp, tga | image and video file readers/writers |
| sound | wav, wavlist, ds3d, dsound, audio | DirectSound, wav tables 0x49c400, listener 0x5fcdc0 |
| net | anet, dp, netgame | ANet / dp* networking |
| font | fnt, text | font resources |
| debug | dbg | |
| roadwar | | |
| match | | |
| object | obj | scene objects: node links (+0x60/+0x64/+0x68), transform +0x18, class type +0x6c, entity +0x70, class table 0x4f76e0 dispatch |
| light | | dynamic light table 0x58db84 (light_SetEnabled 0x477e80, light_Remove 0x477e10) |
| weapon | gdf | weapon records 0x5be4d8, instances 0x5aab08, weapon_Update 0x4a4130 |

Adding a prefix: append a row here in the same commit as the first merged row that uses it (single writer).
