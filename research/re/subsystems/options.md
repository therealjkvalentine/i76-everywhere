# options

The game's user options live in one static block. The current values start at 0x654b80 and a saved copy sits
0x60 bytes higher, at 0x654be0. Every option page (Play Options `plyopt1.map`, Graphic Detail `grxdet1.map`,
Audio Control `audcon1.map`) is a list of 0x3c-byte item records. Each record holds a label at +4 (written by
`shell_InitMenuStrings`), a handler at +8, an id at +0xc and a kind at +0x10. `tools/shell_menu_items.py` joins labels
to handlers (`foldin/shell-menu-items.tsv`). Every option handler has the same protocol, keyed on its message
argument:

| msg | action |
|---|---|
| 6 | copy the current value into the item (item+0x18) |
| 7 | write the item's value into the current byte |
| 8 | commit: copy current into the saved copy (+0x60) and apply it (e.g. 0x405970, 0x495060, 0x421ac0) |
| 9 | revert: copy saved back into current |

`shell_MenuDone` / `shell_MenuCancel` / `shell_MenuReset` drive commit, revert and defaults for a whole page.

## Layout (current block; saved copy = +0x60)

| addr | offset | name | set by |
|---|---|---|---|
| 0x654b81 | +0x01 | options_clouds | shell_GfxClouds |
| 0x654b82 | +0x02 | options_terrain_detail | shell_GfxTerrainDetail |
| 0x654b85 | +0x05 | (object detail, applied value? read by that handler's commit) | shell_GfxObjectDetail |
| 0x654b86 | +0x06 | options_shadow_detail | shell_GfxShadowDetail |
| 0x654b87 | +0x07 | options_terrain_resolution | shell_GfxTerrainResolution |
| 0x654b89 | +0x09 | options_object_detail | shell_GfxObjectDetail |
| 0x654b8a | +0x0a | options_visibility_range | shell_GfxVisibilityRange |
| 0x654b8b | +0x0b | options_terrain_textures | shell_GfxTerrainTextures |
| 0x654b8c | +0x0c | options_brightness | shell_GfxMonitorBrightness |
| 0x654b8d | +0x0d | options_rear_mirror | shell_GfxRearMirror |
| 0x654b8e | +0x0e | options_ext_instruments | shell_GfxExtInstrumentDisplay |
| 0x654b8f | +0x0f | options_horizon_textures | shell_GfxHorizonTextures |
| 0x654b90..93 | +0x10..+0x13 | options_music_level / sfx_level / voice_level / sound_channels | shell_Audio* |
| 0x654b98 | +0x18 | options_play_flags (dword: 1 arcade, 2 no salvage, 4 ammo, 8 armour, 0x10 chassis, 0x20 wiper) | shell_Option* |
| 0x654b9c | +0x1c | difficulty (byte and dword accesses) | shell_OptionDifficultyLevel |

## Object detail

`renderer_ApplyObjectDetail` 0x457870 (called on commit) sets every world object's +0x14 detail level to -1 (full)
or -21 (reduced), taking the value from 0x654b84 or 0x654b85 depending on the object's kind (0x458c10 plus a switch
on the type at +0x6c). The menu byte is 0x654b89; the two applied bytes are its per-class results.

## Visibility Range and the far clip

The camera setup 0x405970 (called when the option is committed, and from the Rear Mirror handler) computes
`far = options_visibility_range ? [0x4c271c] : 150.0` (0x4059d5..0x4059e9), then calls
`camera_Init(fov = pi/2, aspect, far, near = 1.0)`. 0x4c271c is the per-mission far distance that the mission parser
stores (docs/DRAW-DISTANCE.md in i76-everywhere). So "Near" is a fixed 150 m, and every other setting uses the
mission's own value. 0x4059de is the site the sandbox build's "far clip" patch cluster replaces.

## Rear Mirror levels

`renderer_DrawRearMirror` 0x445750 reads `options_rear_mirror` 0x654b8d. 0 draws no mirror (0x445785). At 1 it draws
objects only: 0x457a90, 0x4420b0, 0x441bb0 and 0x443fc0, then 0x48fac0(cam, 0) (0x4458a8..0x44591c). At any other
value it draws the full scene: sky/background 0x401bd0, terrain 0x490a00 / 0x48e900, the object passes, clouds
0x405200(cam, 0xef) and 0x48fac0(cam, 1). A mirror showing cars and cacti but no landscape or sky is therefore level 1,
not a bug (reported 2026-09-27 in all four frame-rate modes).
