# controls/: the control map this project installs

`input.map` here is the map `setup-windows.ps1` writes into a Windows game folder by default
(`-Controls i76e`). It is the owner's daily-driver map, copied byte for byte on 2026-10-03 from
`C:\Users\james\Games\Interstate76-2026-10-03\Interstate 76\input.map`
(md5 `a937f36dba46644d2b0f421097aede2f`). It is a WASD layout, **not** the 1997 key layout; how to keep
the original keys is at the top of [docs/CONTROLS.md](../docs/CONTROLS.md).

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

Two things in the file that read oddly, left as they are because the file is installed unchanged:

- Its header comment (dated 2026-07-04) says `Space fire` and `C handbrake`. The bindings below it say
  otherwise and are what the game reads: `Space` is the handbrake, `Enter` and the left mouse button fire,
  `C` is not bound.
- `hardpoint1_fire` has no binding at all (stock has it on `1`). The `1` key does nothing on this map.

`docs/input.map.reference` is a different file: the map the Mac installer copies (2026-09-06). The Mac
layout has not been compared with this one; converging the two is open work (docs/README.md, section 4).
