# Proxy source cleanup, 2026-10-10

Owner-approved cleanup of the two proxy sources, as proposed in [CLEANUP-PLAN-2026-10-10.md](../CLEANUP-PLAN-2026-10-10.md)
sections 3 and 7.2 and [BACKLOG-2026-10-10.md](../BACKLOG-2026-10-10.md) R-07. **Source only.** The committed,
promoted binaries are unchanged: `music-fix/Strlkup.dll` is still `c11f7f7d51b1e1ddc1fcaf191a7a4675` and
`u32x/u32x_full.dll` is still `06467bd28e060b2889c9ef26b43ee152` (md5 read back after every build). No game was
started, nothing was written to a game folder, and nothing was installed.

**Before either side DLL replaces a committed binary or goes to the daily driver, it needs the 23-row gate on the lab
twin** (`..\i76-uncap-lab\autotest\gate-folder.ps1 -GameDir ..\i76-uncap-lab\game-dd-20261003`, the gate that produced
23 rows in `autotest\runs\gate\20261008-204529`). That is an owner/console item:
[OWNER-TEST-LIST.md](../OWNER-TEST-LIST.md) item 27.

## What changed

| commit | file | change |
|---|---|---|
| `d28925e` | `music-fix/strlkproxy.c`, `docs/ENHANCEMENTS.md` | **`I76_GLIDE_DIR` removed** (the 2026-10-03 subfolder-`Glide2x.dll` experiment; it did not keep the menus 4:3). Removed: the preload arm at the top of `hook_LoadLibraryA`, its `g_glide_dir` buffer, its env read and hook install in `apply_glide_refresh`, and its `g_glide_dir[0]` term in the condition that installs the `grSstWinOpen` wrapper. Kept: the hook itself and its ZGLIDE branch (cursor-map attach, `I76_ZGLIDE_TMUFIX`, `I76_TEX_CENSUS`, the wrapper for `I76_GLIDE_REFRESH` / `I76_GLIDE_GAMMA`). Read before removing: no other code reads `g_glide_dir`; the wrapper's refresh substitution keys on `g_glide_refresh_code` only (since 2026-10-07), so `GLIDE_REFRESH` is untouched |
| `2182e8a` | `u32x/u32x_full.c`, `u32x/README.md` | **`I76_U32X_VPTR*` removed** (8 switches: `VPTR`, `_MAP`, `_CURSOR`, `_CURSOR_SHELL`, `_HIDEOS`, `_WIDEN`, `_CURSOR_ALWAYS`, `_WINDOW`). Removed: the mapping (`vptr_shell_box`, `vptr_box_to_ui`, `vptr_ui_to_box`, `vptr_try_widen`, `vptr_shell_getpos`, `vptr_note_shell`), the WINDOW experiment, `vptr_tick`, and their branches in `My_GetCursorPos`, `My_SetCursorPos` and `My_PeekMessageA`. Kept: the cursor window (`VptrWndProc`, `vptr_paint`, `vptr_show`, `vptr_hide`, the `g_vp_*` state), which `I76_U32X_MODAL_PTR` draws with, and `caller_is_shell`. The separation was clean: with `I76_U32X_VPTR` unset, every removed branch was already a no-op (each started with `sw_vptr()`), and the modal pointer's only VPTR dependencies were its own "VPTR owns the window" stand-down and `vptr_show`'s `I76_U32X_VPTR_HIDEOS` test. That test became its default (hide the OS arrow once while ours is up): **the one behaviour change**, and only for someone who set `I76_U32X_VPTR_HIDEOS=0` with the modal pointer |
| `095c45e` | `music-fix/strlkproxy.c`, `music-fix/cursormap.c` | **One env helper**, 76 sites converted (below) |
| `9426190` | `music-fix/README.md` | **20 switch rows added** (below); `I76_GLIDE_DIR` removal noted in History |

Before the removal, `I76_GLIDE_DIR` was checked against every launch path: `presets\*.psd1` (none), the lab
(`..\i76-uncap-lab`: `.psd1 .ps1 .bat .cmd .txt .md`; only three docs name it: `TERRAIN-WHITE-FLASH.md`,
`TEXTURE-DELIVERY.md`, `WIDESCREEN-2D.md`), and the daily driver's `.psd1 .ps1 .bat .txt` (none; read only). It was
documented as abandoned in ENHANCEMENTS row "Glide wrapper from a subfolder", STATUS-2026-10-02 and BACKLOG-2026-10-10
G-02 / item 8. The `I76_U32X_VPTR` family is in no preset; the lab's `autotest\vptr-test.ps1` and its run folders
use it (CLEANUP-PLAN section 3), and they will now find the switches absent: a rebuilt `u32x_full.dll` ignores them.

## The env helper (strlkproxy.c, after the globals)

```c
static DWORD env_str(const char *name, char *buf, DWORD cap);   /* 0 = unset, empty or too long for buf (buf[0] = 0) */
static int   env_present(const char *name);                       /* GetEnvironmentVariableA(name, NULL, 0) > 0 */
static int   env_flag(const char *name, DWORD cap, int dflt);     /* '1' -> 1, '0' -> 0, otherwise dflt */
static int   env_int(const char *name, DWORD cap, int dflt);      /* atoi, or dflt */
```

`cap` is the buffer size each site always used, kept so that a value too long for it is still rejected exactly as
before (a 4-byte site and an 8-byte site differ for 4..7-character values). Each conversion is one of four identities:
`k = GetEnvironmentVariableA(X, v, sizeof v); k && k < sizeof v` -> `env_str(X, v, sizeof v)` (returns k when it
fits, else 0); `k && k < cap && v[0] == '1'` -> `env_flag(X, cap, 0) == 1`; `k && k < cap && v[0] == '0'` ->
`env_flag(X, cap, 1) == 0`; `GetEnvironmentVariableA(X, NULL, 0) == 0` -> `!env_present(X)`. Where a site parses more
than the first character (`=2`, `ar`, `exe`, `1997`, numbers, lists), it keeps its own parse on the `env_str` buffer.
The flag sites that read "any value except `0` enables" (`AI_BACKAWAY_GRID`, `NO_MINIMIZE`, `SW_RES`, `CURSOR_MAP`,
`MIRROR_RATE`) use `env_str` + their own test, because `env_flag` would read `2` as the default.

**Converted (76):** 13 presence sites (`SKIP_MOVIES`, `HIRES_CLOCK`, `ENGINE_DT_FIX`, `FAR_ENGINE_DT`,
`FRAMERATE_FIXES`, `AI_FIXES`, `FIX_LABEL_TABLE`, `LABEL_TEST`, `INPUT_LATCH`, `COLL_WINDOW` (presence), `RENDER_INTERP`,
`MULTI_INSTANCE`, `I76MUSIC_LOG`), 4 in cursormap.c, the `env_is_1` helper, and every other guarded read.

**Not converted (8)**, each an unguarded read where the value is used without the `k < sizeof(v)` test. For a value
too long for the buffer, Windows leaves the buffer unwritten, so these test an uninitialised byte (or, for
`FPS_PROF`, the first character of the `I76_FPS_LOG` value already in the shared buffer). `env_str` would read that
case as unset. That is a change (a fix) for over-long values, not an identity, so it was left for a decision:

| site | read |
|---|---|
| `I76_MUSIC_THREAD` | `n && v[0] == '1'` |
| `I76_MUSIC_RESUME` | `!(n && v[0] == '0')` |
| `I76_MUSIC_GUARD` | `!(n && v[0] == '0')` |
| `I76_FPS_PROF` | `GetEnvironmentVariableA(...) && v[0] == '1'`, buffer shared with `I76_FPS_LOG` |
| `I76_CRASH_LOG` | `GetEnvironmentVariableA(...) && v[0] == '0'` disables |
| `I76_CD_LOG` / `I76_CD_FAKE` | `!n \|\| v[0] == '0'` / `n > 0 && v[0] == '1'` |
| `I76_FIX_HEALTH_PCT` | presence enables (any length), `n < sizeof(v) && v[0] == '2'` picks the mode: needs two reads to express |

## README rows (BACKLOG R-07)

`grep '"I76…"'` over strlkproxy.c and cursormap.c gives 86 quoted names. 20 had no mention anywhere in
music-fix/README.md; they now have rows: `I76_MISSION`, `I76_SKIP_MOVIES` (noted: a no-op without `I76_MISSION`,
BACKLOG R-13), `I76_PHYS_RATE` (measured superseded experiment, i76-map `captures/014-framerate`), `I76_FPS_LOG`,
`I76_FPS_PROF`, `I76_GLIDE_REFRESH_CODE`, `I76_SW_RES`, `I76_JOY_MAP`, `I76_JOY_SYNTH`, and the eleven `I76_COOP_*`
(`AI`, `CHAIN`, `DAMAGE`, `ADOPT`, `HOSTMODEL`, `CB`, `SHIMLOCK`, `HEAPGUARD`, `HEAPWATCH`, `HEAPLOCK`, `AI_DIAG`).
After the edit every quoted name appears in the README. What each row says it does is read from the code. Its status
comes from `git log -S` and the docs it names. **`I76_COOP_HEAPLOCK`: no doc or run record names it; whether it was
ever run live is unknown.** `I76_CD2` is not a switch (a CD volume label inside a comment). Names that are mentioned
in the README only inside another switch's row, not as a row of their own, were left so: `AI_DODGE_HOLD`,
`AI_FIRE_CACHE`, `AI_ROLL_HOLD`, `ASPECT_COCKPIT_FOV`, `FLASH_ROWS`, `INTERP_SMOOTH`, `LABEL_TEST`, and
`I76MUSIC_LOG` (Diagnostics).

## Side builds (MSVC, Visual Studio 2019 Build Tools x86)

| DLL | path (git-ignored) | bytes | md5 | how |
|---|---|---|---|---|
| proxy | `music-fix\out\Strlkup.dll` | 281,088 | `8b904e53875de470f071e0f6e2380595` | `music-fix\out\b.cmd`: the `cl` line of `build.ps1 -Msvc` (`/LD /MT /O2 /W3 /D_CRT_SECURE_NO_WARNINGS ... user32.lib`), output kept in `out\` (**`build.ps1` / `build-msvc.ps1` were not used: they move the result over the committed `Strlkup.dll`**). No warnings at /W3 |
| u32x | `u32x\u32x_full.build.dll` | 112,128 | `188e0c078786aac92f547e1f499e778a` | `u32x\build-full.ps1` (non-destructive by design). Only LNK4070, which the script expects |

A rebuild has another md5 each time (MSVC stamps the link time), so these md5s name these two files, not the source.

**Toolchain control.** The pre-cleanup u32x source (`d28925e`) built with the same command reproduces the committed
`u32x_full.dll` `06467bd2`, apart from 6 bytes, all in the PE header and debug-directory time stamps. So the u32x
side DLL differs from the promoted binary only by the source change. For the proxy, the committed `c11f7f7d` is
already 3 source commits behind (BACKLOG "State of the binaries"). Its control is a build of the pre-cleanup source
(`012d31f`, `music-fix\out\ctrl\Strlkup.ctrl.dll`, 281,088 B, `8da01aa2003ad268446a448c28f280eb`).

**Strings, new vs control** (all printable runs of 4 or more characters, both directions):

- proxy: the only meaningful strings lost are `I76_GLIDE_DIR`, `  glide-dir: %s %s`, `  glide-dir: %s, LoadLibraryA %s`,
  `%s\%s\Glide2x.dll`, `loaded before ZGLIDE` and `FAILED to load - the game folder's Glide2x.dll will be used`. None
  were gained (the rest of the difference is code bytes). All 85 quoted switch names of the new source are in the
  binary (the 86th, `I76_CD2`, is a comment). All 244 `mlog` format literals of the new source are present verbatim.
- u32x: lost the 8 `I76_U32X_VPTR*` names and the `AdjustWindowRectEx` import (only the WINDOW experiment used it).
  All 15 `I76_U32X_*` names of the new source are present, `I76_U32X_MODAL_PTR` among them, and so is the cursor
  window's class name `u32xVptr`. The `VPTR cursor ...` log lines stay in the source but exist only in the
  `/DU32X_LOG` build, as before.

## Tests (offline)

- `python -m pytest tests`: 220 passed, 5 skipped.
- `tools\haptics\haptics.ps1 test` (with `I76_REAL_DRIVES` = the main checkout's `tools\ffb`): golden 352 passed,
  0 failed, 1 skipped; C# tests exit 0, Python tests exit 0.

Neither touches the proxies' runtime behaviour, which only the gate (item 27) checks.

## Not done

- No live run of either side DLL, and no gate (item 27 is for the console).
- The 8 unguarded env reads above: converting them would also fix what an over-long value does. That needs a decision.
- The optional folds from CLEANUP-PLAN section 3 (`I76_VOLUME_TEST`, `I76_LABEL_TEST`) were not part of this pass.
- Lab `autotest\vptr-test.ps1` was not touched (lab repo). After a rebuilt `u32x_full.dll` is promoted, it tests
  switches that no longer exist.
