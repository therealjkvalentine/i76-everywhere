# Render scale and antialiasing as graphics keys (2026-10-25, render-keys lane)

Owner, 2026-10-25: *"Supersampling and AA probably need to be in the graphics setting options."* Until now the 2x2 supersample
and the 4x MSAA lived only in `dgVoodoo.wide.conf` (and the kit's `--no-supersample` flag); every other graphics setting is a
preset key that `presets\local.psd1` overrides. Now these two are keys too.

## 1. The keys

| key | values | default | read by | applied as |
|---|---|---|---|---|
| `I76_RENDER_SCALE` | 1, 1.5, 2 | 2 (= the 6880x2880 played since 2026-10-12 on 3440x1440) | PLAY-i76.ps1 (not the proxy) | `[Glide] Resolution` = scale x the display per axis, each side capped at 8192, even |
| `I76_AA` | 0, 2, 4, 8 (also `off`, `4x`) | 4 | PLAY-i76.ps1 | `[Glide] Antialiasing` = off / 2x / 4x / 8x |
| `I76_RENDER_WIDTH` | - | - | nobody (reserved) | the Mac has no render-size key yet (section 3); PLAY-i76.ps1 drops it from the game's environment |

Sources, highest first: `PLAY-i76.ps1 -RenderScale` (the kit's `--no-supersample`), `presets\local.psd1`, the launcher's preset,
the shell environment, the default. Values outside the list: a `render:` warning line and the default. Both keys are removed from
the environment handed to the game.

## 2. Where they are applied (PLAY-i76.ps1, "render scale + antialiasing", after the local.psd1 merge)

- Only when `dgVoodoo.conf` is byte-equal to `dgVoodoo.wide.conf`, i.e. the launcher copied the wide conf (PLAY.bat, PLAY-T05,
  PLAY-STABLE, PLAY-TICK*, the kit's PLAY.bat). PLAY-VANILLA's 16:10 conf is never touched; with keys set the log says
  `render keys NOT applied ... this launcher uses another conf`.
- Neither key set and never changed before: nothing is written. Log: `render: 2x (6880x2880), AA 4x (default: no I76_RENDER_SCALE /
  I76_AA set, dgVoodoo.wide.conf as installed; display 3440x1440 from the primary monitor)`.
- Otherwise the wanted `[Glide] Resolution` / `Antialiasing` are compared with the conf's own lines (no separate stamp: the conf is
  the stamp, so a conf another tool rewrote is noticed). Different -> the installed conf is kept once as
  `dgVoodoo.wide.conf.pre-render-keys`, `tools\Make-Wide-Conf.ps1 -Template <that> -SourceConf <that> -Scale S -Antialiasing A
  -NoPreset` rewrites `dgVoodoo.wide.conf` (only the Resolution digits and the Antialiasing value may differ from the template; the
  script dies otherwise), it is read back, then copied to `dgVoodoo.conf` (md5 compared). Back to 2 / 4 with the kept file still
  matching the display: the kept file is put back byte for byte and removed. A failed rewrite puts the kept file back and launches
  on it. Log: `render: 1x (3440x1440), AA 4x (from local / default; display 3440x1440 from the primary monitor; dgVoodoo.wide.conf
  rewritten (installed copy kept as dgVoodoo.wide.conf.pre-render-keys))`.
- Display: `<game>\_i76e\display.txt` (the kit's display stamp, so `--display WxH` is honoured) if present, else the primary
  monitor (the same source Make-Wide-Conf.ps1 and i76e-prepare.ps1 use).
- Make-Wide-Conf.ps1 is found beside PLAY-i76.ps1 (`tools\`, the repo), in `<game>\_tools\` (installed; setup-windows.ps1 now
  copies it there) or `<game>\_i76e\repo\tools\` (the kit).
- `-Windowed` now sizes its per-launch `[Glide] Resolution` with the same scale (it was a fixed 2).
- `-RenderOnly`: apply the step, print the line, exit 0 (5 if the step failed); starts nothing. Used by the tests below.

Make-Wide-Conf.ps1 gained `-Antialiasing` ('' = the template's value; 0 / off, 2, 4, 8, 16). The "same bytes but the digits" guard
now also masks the Antialiasing value and allows at most 3 changed lines.

## 3. The Mac: no equivalent key yet (finding)

The brief assumed the Mac's render size is `OpenGLid.INI Resolution=` (1488 on the MacBook). It is not, in the Gold app as installed:
the prefix's `user.reg [Environment]` has `OGL_OUTPUT=parent` and `OGL_VIEWPORT`, and OpenGLide-HD patch 0005
(`InitialiseOpenGLWindow`) then replaces the INI's window size with the parent client area and renders at `OGL_VIEWPORT`. The
MacBook's own `OpenGLid.log` (Gold.app and the GFX LAB clone, read 2026-10-25 over SSH, nothing changed):
`OGL_OUTPUT: parent client area 3440x1440` / `OGL_VIEWPORT: rendering at 2228x1440`, while the INI says `Resolution=1488`.
`OGL_VIEWPORT` is computed by the installed stub (`i76-launch-stub.swift` `setGlideViewport`) from the display at every start, and it
must equal the real drawable (a different value draws into a corner of the window: MAC-BUILD.md s.10, the "hall of mirrors"). So
writing `Resolution=` would be a write that never lands, and there is no knob today that renders the Mac's 3D smaller or larger than
its window. (A stub `setRenderWidth` that wrote `Resolution=` from `user.reg` `I76_RENDER_WIDTH` was written, compiled and exercised
on copies in `/tmp` on the MacBook - 1200 written with the CR kept, 1488 back to the original md5, unset = untouched - and then taken
out again before commit 2 for that reason. No Mac app was rebuilt or changed.)

Where a Mac render-size key would go:
1. OpenGLide-HD, a new patch 0007 in `platform/windows/output.cpp`: render the Glide frame into an FBO of `OGL_RENDER_SCALE x` the
   `OGL_VIEWPORT` size and scale it to the drawable at swap. `OutputPostProcess` already resolves the frame with `glBlitFramebufferEXT`
   into a single-sampled FBO for the gamma pass (patch 0004), so the blit-scale fits there; the LFB paths (menus, binocular mask)
   composite at the Glide resolution and would need the same scale.
2. `i76-launch-stub.swift`, next to `setGlideViewport` (same hook: it reads and writes `user.reg [Environment]` before Wine starts):
   read `I76_RENDER_WIDTH` (or a scale) and write `OGL_RENDER_SCALE` into `[Environment]`. Takes effect on the next stub rebuild +
   install (the apps' stub is 565c4bd9 from 2026-10-04).
3. Mac antialiasing already is a key: `OGL_MSAA` (4) in the same `[Environment]` (patch 0004).

The Mac tier files say this in their header comment; `I76_RENDER_WIDTH` is reserved for it.

## 4. Presets

| file | I76_RENDER_SCALE | I76_AA | note |
|---|---|---|---|
| graphics-balanced | 2 | 4 | = today |
| graphics-high | 2 | 8 | UNTESTED (8x MSAA on 6880x2880) |
| graphics-mid (new) | 1 | 4 | balanced's keys at the display's own size. **TODO**: set from docs/records/SUPERSAMPLE-COST-2026-10-25.md when that lane lands (not measured here) |
| graphics-mac / -mac-fast | - | - | header documents section 3 |

The launcher presets (OWNER-2300-ALL, tick19-42, ...) do not set the keys: the defaults are today's behaviour, and nothing is touched.

## 5. Patch kit

- `PLAY.bat --no-supersample` = `I76_RENDER_SCALE 1` for that launch: i76e-prepare.ps1 still writes its 1x conf (display stamp
  `display.txt` unchanged), and the .bat now also passes `PLAY-i76.ps1 -RenderScale 1` (package-patch-kit.ps1, `%PLAYARGS%`), so
  the render step sees a matching conf and changes nothing. Without the flag a local.psd1 key works as on the RC.
- README-PATCH-KIT.md: a "Graphics settings" section (every key a user may put in `presets\local.psd1`, one line each); the same
  section is in the RC's VERSION.md.
- The next kit build picks all of this up (package-patch-kit.ps1 ships PLAY-i76.ps1, Make-Wide-Conf.ps1, presets, README); the
  published zip was not rebuilt.

## 6. Tests

### Offline, a scratch copy of the RC's confs + presets (lab `builds\render-keys-20261025\scratch`), PLAY-i76.ps1 -RenderOnly

Display 3440x1440 (primary monitor). Each row = launcher copy (wide -> dgVoodoo.conf) then PLAY-i76.ps1 -RenderOnly, preset OWNER-2300-ALL.

| row | local.psd1 | log line | dgVoodoo.conf md5 | [Glide] Resolution / Antialiasing |
|---|---|---|---|---|
| A | none | `render: 2x (6880x2880), AA 4x (default: ... as installed ...)` | dccd379a (= installed, unchanged) | 6880x2880 / 4x |
| B | RENDER_SCALE 1 | `render: 1x (3440x1440), AA 4x (from local / default; ... rewritten ...)` | 0eb52fd6 | 3440x1440 / 4x |
| C | RENDER_SCALE 1, AA 0 | `render: 1x (3440x1440), AA off (from local; ...)` | 9edde827 | 3440x1440 / off |
| D | AA 0 | `render: 2x (6880x2880), AA off (from default / local; ...)` | 59d369f8 | 6880x2880 / off |
| E | 1.5 / 8 | `render: 1.5x (5160x2160), AA 8x (from local; ...)` | 1473ef62 | 5160x2160 / 8x |
| F | removed | `render: 2x (6880x2880), AA 4x (from default; ... the installed dgVoodoo.wide.conf put back)` | dccd379a, .pre-render-keys gone | 6880x2880 / 4x |
| G | none | as A | dccd379a | |

Also: the installed layout (PLAY-i76.ps1 in the game folder, Make-Wide-Conf.ps1 in `_tools\`): same lines; the 1x/AA-off conf differs
from the installed one in exactly 2 lines (`Resolution = 3440x1440`, `Antialiasing = off`). `-RenderScale 2` over local 1 -> 2x (from
-RenderScale). Bad values `3` / `6` -> two warning lines, 2x / 4x. 16:10 conf in place -> `render keys NOT applied`, conf untouched
(299a6811). `-DryRun`: the render line with "DRY RUN: would rewrite", nothing written, and the game environment carries neither key.

`tests/test_render_keys.py` (4 tests, same checks on the repo template with `_i76e\display.txt` = 3440x1440, so it does not depend on
the monitor) + `tests/test_presets.py`: 32 passed.

### Live boots (dev-gold, desktop console)

PENDING - see the addendum below.

## 7. Deployed (md5 first 8; every replaced file kept beside itself as `<name>.<md5>-pre-render-keys`, state in `_rollback\render-keys-20261025\state.txt`; lab `builds\render-keys-20261025\deploy.ps1 -Target <dir> [-Rollback]`)

No game ran from any target while deploying (checked by the script). Read back by a second run ("already").

| file (in `Interstate 76\`) | Gold (= release-candidate) / test-gold / RC stage before | dev-gold before | after (all four) |
|---|---|---|---|
| PLAY-i76.ps1 | 6abf5833 | 15b9862e | 5d9f9143 |
| _tools\Make-Wide-Conf.ps1 | - | - | eb53635b |
| presets\graphics-balanced.psd1 | 76f115d8 | - | a67d3aec |
| presets\graphics-high.psd1 | 10a4ee18 | - | 6dc7c7c9 |
| presets\graphics-mac.psd1 | 95b9a1af | - | 8be5c9fc |
| presets\graphics-mac-fast.psd1 | a31824f9 | - | b74428e0 |
| presets\graphics-mid.psd1 | - | - | 6d7fd271 |
| VERSION.md (top level; "Graphics settings" section) | 83634a5d | dbbbcb7b | 4ce0deca (dev-gold df13a1d1) |

The confs were not changed anywhere (dgVoodoo.wide.conf / dgVoodoo.conf dccd379a in Gold, test-gold, dev-gold). The RC stage: the
replaced files' originals are in lab `builds\rc-20261024\_renderkeys-stage-pre-20261025\` (not in the stage, so install-rc.ps1 does not
copy them), MD5SUMS refreshed (backup `MD5SUMS.pre-renderkeys-20261025`), 67 entries 0 bad. PLAY-i76.ps1 5d9f9143 = repo main
(working copy, CRLF) after commit 2; it also carries the kit's portable-opentrack fallback (4ec088e) that the RC's 6abf5833 lacked
(inert without `_tools\opentrack\`).

## 8. Commits

- 4447685 the keys, Make-Wide-Conf -Antialiasing, presets, kit, setup-windows, tests (and a Mac stub function, taken out again in 2).
- commit 2: this record, the Mac stub function removed (section 3), the Mac tier comments, the README row.
