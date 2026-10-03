# controls/: the control map this project installs

`input.map` here is the map `setup-windows.ps1` writes into a Windows game folder by default
(`-Controls i76e`). It is the owner's daily-driver map, copied on 2026-10-03 from
`C:\Users\james\Games\Interstate76-2026-10-03\Interstate 76\input.map`, plus the three keys below. It is a
WASD layout, **not** the 1997 key layout; how to keep the original keys is at the top of
[docs/CONTROLS.md](../docs/CONTROLS.md).

**It is no longer byte-identical to the daily driver's map** (since 2026-10-03, owner ruling the same day):

| File | md5 |
|---|---|
| `controls/input.map` (this repo) | `90122d370333b545d27070f3f94b1265` |
| the daily driver's `input.map` | `a937f36dba46644d2b0f421097aede2f` |

The difference is three added bindings and a corrected header comment; nothing was removed or moved:

- `1` = `hardpoint1_fire` (it had no binding at all; stock has it on `1`, and the pad layer's LB + RT types `1`);
- `J` = `hardpoint1_fire` and `L` = `hardpoint2_fire`, right-hand home-row fire keys, as second blocks
  (alternatives, not chords) beside `1` and `2`;
- the header comment now says `Enter fire` and `Space handbrake`, which is what the bindings always were.

The daily driver gets this map **by promotion after a pad test** (`tools\Promote-To-Driver.ps1`), together with
the changed `i76-remap.ahk`. Until then the driver has the old map and the old pad layer.

**Hardpoint 2 is on `L`, not `K`: the owner can flip it.** The owner said "maybe K" for hardpoint 2. `K` is the
radar camera in his map, and the wheel layer types `K` for it (L3 with shift, `gWheelAlt` 11 in `i76-remap.ahk`);
`L` was unbound. So `L` fires hardpoint 2 and `K` stays the radar camera. The alternative, in one line: change the
second `hardpoint2_fire` block to `K` and `RADAR_CAMERA_TOGGLE` to `L`, change `11: "k"` to `11: "l"` in
`gWheelAlt`, then run `tools\controls-sheet\build.ps1`.

- **Printable sheet:** [docs/Interstate76-Controls-Quick-Reference.pdf](../docs/Interstate76-Controls-Quick-Reference.pdf),
  generated from this file by [tools/controls-sheet](../tools/controls-sheet/README.md).
- **To change a binding:** edit `input.map` here, then run `tools\controls-sheet\build.ps1`. It lints the
  map, checks it against the AutoHotkey layers, and regenerates the sheet, or lists what is inconsistent.
- **The file is stored without line-ending conversion** (`.gitattributes`): it has mixed endings, as in the
  owner's game folder, and the sheet prints its md5.

What is specific to the owner's machine, checked 2026-10-03:

- `steer` and `throttle` read `joystick1` (`Left/Right`, `Down/Up`). That is the first winmm joystick on
  any PC: the wheel on the owner's, an Xbox pad's left stick on a pad-only PC.
- There are **no native `joystick1` button or hat bindings**. They were removed on 2026-08-08 because the
  AutoHotkey wheel layer types keys for every button and a native binding beside it fires twice
  ([docs/WHEEL-T300.md](../docs/WHEEL-T300.md)). For a gamepad this means the buttons work only through
  the AutoHotkey layer (`i76-remap.ahk`), which the installer deploys.
- No paths, device names or other machine data are in the file.

`C` is not bound. The pad layer's B button typed `C` for "cycle weapon" until 2026-10-03; it types `Tab` now.

`docs/input.map.reference` is a different file: the map the Mac installer copies (2026-09-06). The Mac
layout has not been compared with this one; converging the two is open work (docs/README.md, section 4).
