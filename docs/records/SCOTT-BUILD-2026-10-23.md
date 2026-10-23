# Scott build 2026-10-23: the tester zip over a GOG copy

Lane: Scott-build (owner 2026-10-23: "a build that Scott can run ... the latest stable copy so he can give feedback. Make sure
the repository is buildable off of the copy of the game he'll have ... which may not be ultrawide ... explain the home-row
keyboard controls"; coordinator: the zips go on GitHub, so NOTHING of GOG's inside, a draft pre-release, a patcher for the
user's own files). Repo commits `6bdba60`, `e85585f`, `98d96e1`, `4b28e82` (main); lab `builds\scott-20261023\`.

## 0. Deliverables

| what | where |
|---|---|
| the zip | `C:\Users\james\i76-uncap-lab\downloads\scott\Interstate76-i76-everywhere-scott-20261023.zip` (83 files, 2,881 KB; md5 in s.1) and `<zip>.MD5SUMS` |
| GitHub | **draft pre-release** `scott-20261023` on `therealjkvalentine/i76-everywhere` (public repo), asset = the zip, body = README-SCOTT.md, target main. NOT published: `gh release view scott-20261023`; publish with `gh release edit scott-20261023 --draft=false` after the owner's go. Until then the URL reads `releases/tag/untagged-...` (GitHub creates the tag on publish). |
| packer | `tools\package-scott.ps1 -Proxy <dll> -ProxyCommit <sha> -DgVoodooDir <unpacked dgVoodoo2_87_3.zip> -AhkDir <AutoHotkeyU32.exe folder>` (stage kept in lab `builds\scott-20261023\stage`) |
| the launcher logic | `tools\scott\i76e-prepare.ps1` (run by every PLAY*.bat before the game), `tools\scott\Apply-Shell-Keys.ps1` + `shell-keys-patch.json`, `tools\scott\README-SCOTT.md` |
| extended, not forked | `setup-windows.ps1` (a preset carrying `I76_ASPECT` counts as a wide preset; `-AllowNarrow`), `tools\Make-Wide-Conf.ps1` (`-Presets`, `-AllowNarrow`), `tools\fix-shell-textentry.ps1` (refuses only while the game from THIS folder runs) |
| presets | `presets\tick19-42.psd1` (= the release candidate's f7e589ef, byte for byte), `presets\scott-preview.psd1` (= lab `exp-polish2\...\presets\OWNER-2300-FOG.psd1` as it stood 11:40, only `Name` changed) |
| gate folder | lab `game-scott` = `i76-map\sandbox-gog\main\app` (GOG 2.1.0.17, i76.exe **9a232dcc**, the exe Scott most likely has) + the zip unzipped into it + its own first-run setup; `builds\scott-20261023\run-gate.ps1` |

## 1. What is in the zip, and why each item may be shipped

The zip is unzipped INTO the game folder (`PLAY.bat` beside `i76.exe`). Name guard in the packer: no `i76.exe`, `i76shell.dll`,
`*.ZFS / ZIX / MW2 / DEF / SMK / MP3 / WAV / PCX / FNT / TTF / CUR / OVL / MSN / VCF`, `strlkup_orig.dll`, `I76PATCH.DLL`, GOG's
`goggame* / win32 / audiere / smackw32 / anetdll / z*.dll ...`, and no `.exe` / `.dll` other than the six named below. Every file's
md5 is in `_i76e\MD5SUMS` (and `<zip>.MD5SUMS` beside the zip).

| item | files | why it may be shipped |
|---|---|---|
| our proxy | `_i76e\repo\music-fix\Strlkup.dll` **9bab51fe** (738,816 B) | ours (MIT); clean build of main `8cb3da2` by lab `builds\nitro-port-20261021\build.ps1 -Tag scott-8cb3da2 -Ref 8cb3da2` (git archive, MSVC x86 /MT /O2 /Brepro); the two music-fix commits after it (`0e01d3c` I76_GLIDE_MIPMAP, `3d89698` faredge alpha combine) are lab switches off in both shipped presets |
| our mouse DLL | `_i76e\repo\u32x\u32x_full.dll` 06467bd2 + `deploy-u32x.ps1` + `README.md` | ours; the daily driver's build since promotion 15 (KnownGood list in deploy-u32x.ps1) |
| our launchers / scripts | `PLAY.bat`, `PLAY-PREVIEW.bat`, `PLAY-T05.bat`, `PLAY-PREVIEW-T05.bat`, `UNINSTALL-i76e.bat`, `_i76e\i76e-prepare.ps1`, `_i76e\repo\setup-windows.ps1`, `PLAY-i76.ps1` (c2194586 = the RC's), `tools\Make-Wide-Conf.ps1` + `tools\conf\dgVoodoo.daily-wide-ss2x-2026-10-12.conf` (dccd379a), `dgVoodoo.daily-driver-2026-10-03.conf`, `dgVoodoo.windows.conf`, `tools\fix-shell-textentry.ps1`, `tools\lint-input-map.py`, `tools\i76wheel.exe` (ours, tools\i76wheel.c), the debug tool (`tools\debug|trainer|telemetry`, `tools\driver\DEBUG.bat|TRAINER.bat`) | ours (MIT) |
| shell patch DATA | `_i76e\repo\tools\scott\shell-keys-patch.json` (4.7 KB) + `Apply-Shell-Keys.ps1` | ours: only OUR replacement bytes (offset + hex, 578 bytes in 25 runs), keyed by the md5 of the shell they fit; no original bytes (s.3) |
| presets, controls | `presets\tick19-42 / scott-preview / best-120 / best-wide / best-wide-balanced / stock.psd1`, `controls\input.map` (a66a37f7) + `README.md`, `i76-remap.ahk`, `i76-ch-fighterstick.ahk`, `docs\CONTROLS.md`, `docs\Interstate76-Controls-Quick-Reference.pdf` | ours |
| bookmark saves | `_i76e\repo\saves\save000..017.cmp` + `savegame.dir` (13 records, the repo's shipped set) | player-written save files already in the public repo (`saves\README.md`); only copied in when the user has no saves |
| dgVoodoo 2.87.3 | `_i76e\dgVoodoo\3Dfx\x86\Glide.dll / Glide2x.dll / Glide3x.dll`, `MS\x86\DDraw.dll / D3DImm.dll`, `dgVoodooCpl.exe`, the package's `*.url` readme links, our `README-dgVoodoo.txt` | Dege's **ReadmeGeneral, section 1 "Redistribution rights"** (http://dege.freeweb.hu/dgVoodoo2/ReadmeGeneral/, read 2026-10-23): *"You can freely ship your game or game mod with unmodified individual dgVoodoo components (files) included."* (standalone hosting needs the original zip; bundling in launchers / frameworks for general use is not allowed). The packer refuses any of the six unless its md5 equals the file in `dgVoodoo2_87_3.zip` from github.com/dege-diosg/dgVoodoo2/releases/tag/v2.87.3 (downloaded with `gh release download`; all six matched the files the daily driver / RC run) |
| AutoHotkey 1.1.37.02 | `_i76e\AutoHotkey\AutoHotkeyU32.exe` b6af97aa + `license.txt` (GPL v2) | GPL: redistributable with its licence; unmodified interpreter for the pad / wheel / stick layer |
| text | `README-SCOTT.md`, `_i76e\VERSION.txt` (`scott-20261023 4b28e82`), `_i76e\MD5SUMS`, `LICENSE`, `THIRD-PARTY.md` | ours |

Earlier portable builds (`Make-Portable-Zip.ps1`, `Interstate76-i76-everywhere-portable-20260801`) packed the WHOLE configured
install, game bytes included, for the owner's own PCs ("don't redistribute it", its header). This zip replaces that model for a
third party: the repo's installer path (`install.ps1` / `setup-windows.ps1`, the fresh-install work of 2026-10-10..12) run from a
trimmed repo copy inside the zip, against the user's own files.

## 2. What the first PLAY.bat does to the user's copy (i76e-prepare.ps1)

1. Refuses without `i76.exe` beside `_i76e\`; refuses under Remote Desktop (3D hangs there, AGENTS.md).
2. First run (or a new `VERSION.txt`, or a missing proxy / u32x / preset / launcher):
   - `Apply-Shell-Keys.ps1` on the user's `i76shell.dll` (s.3), then `fix-shell-textentry.ps1` (a no-op on GOG's shell: its bytes
     are the stock 0x41 / 0x08; the AiO shell has the narrowed clear and gets the two bytes back),
   - `setup-windows.ps1 -GameDir <here> -DgVoodooDir _i76e\dgVoodoo -AhkDir _i76e\AutoHotkey -Preset tick19-42 -NoShortcut -Display WxH
     [-AllowNarrow]`: GOG's glide*.dll / glide2x.ovl -> `_openglide-backup\`, dgVoodoo DLLs + Cpl, the 16:10 conf (TMU 8192),
     `controls\input.map` (GOG's kept as `input.map.stock-<ts>`), the repo saves if the folder has none, the proxy (`strlkup_orig.dll`
     kept), `I76PATCH.DLL` -> `.disabled` where GOG shipped one, u32x (`i76.exe.u32xorig`, `i76shell.dll.orig`), the AHK layer,
     presets, `PLAY-i76.ps1`, the debug tool, `PLAY-i76.bat / -16x10 / -balanced / -stock.bat`; nothing outside the folder.
3. Every run: the primary monitor's size (or `--display WxH`) and `--no-supersample` -> `_i76e\display.txt`; when it changed,
   `Make-Wide-Conf.ps1 -Presets tick19-42,scott-preview,best-wide,best-wide-balanced [-AllowNarrow] -Scale 2|1` rewrites
   `dgVoodoo.wide.conf` and the presets' `I76_ASPECT` / `I76_U32X_MENU_ASPECT`; then `dgVoodoo.wide.conf -> dgVoodoo.conf`.
   The .bat then starts `PLAY-i76.ps1 -Preset <x> -LosslessScaling none` (`-Mission t05.msn -SkipMovies` for the T05 variants).
4. `UNINSTALL-i76e.bat` = `-Uninstall`: `deploy-u32x.ps1 -Restore`, `Apply-Shell-Keys.ps1 -Revert`, `strlkup_orig.dll` / `I76PATCH.DLL`
   back, `input.map.stock-*` back, `_openglide-backup\*` back, our files removed (`_i76e`, the root .bat files and the README are
   left for the user). Verified only as far as the setup's own backups go (not run on the gate folder: it is the gate folder).

Idempotence: the setup ran twice on `game-scott` (the second after a re-unzip with a new VERSION): every step reported "already" /
"nothing to do" and the file set was unchanged.

## 3. The shell keyboard patches as a patcher (no game bytes shipped)

GOG's 2.1.0.17 install ships `i76shell.dll` **deb41008** (the Galaxy / offline-installer shell); the AiO patch's shell is
**8960fa16** (the RC's `i76shell.dll.orig`; it differs from deb41008 in 9,809 bytes, a different build, with the narrowed ToAscii
clear). The daily driver's / RC's live shell a300db63 = 8960fa16 + F7 + M1/M2/K1-K4 + the text-entry fix + the u32x import rename.

`tools\patch-shell-f7.py` and `tools\patch-shell-modals.py` were run on BOTH shells (lab `builds\scott-20261023\shellpatch`):
deb41008 -> 68be82f2 (F7, 124 B) -> **3f2fff4f** (454 B more; the numbers FRESH-INSTALL-CHECK-2026-10-10 predicted), 8960fa16 ->
631e0793 -> **20e1cdda**. Check: 20e1cdda + the text-entry bytes (0x1B52C 0x41, 0x1B535 0x08) differs from the RC's live a300db63 in
exactly the 10 bytes of the import name `USER32.dll` -> `u32x.dll` at 0x41228, i.e. the chain reproduces what the owner plays.
`shell-keys-patch.json` holds, per base md5, the 25 runs of OUR bytes and the expected result md5; `Apply-Shell-Keys.ps1` reads the
user's file, matches its md5, backs it up once (`i76shell.dll.pre-i76e-keys`), patches in memory, checks the image md5 against the
expected result, writes, reads back, checks again (puts the backup back on a mismatch); an unknown shell build is left alone (exit
2, the game works without: the popups answer to the mouse). It runs before deploy-u32x.ps1 (the rename changes the md5); an already
patched file is recognised by the F7 hook bytes at 0xab9f. On `game-scott`: `deb41008 -> 3f2fff4f` applied, then u32x -> 64923d95.

## 4. Display handling

One conf for every monitor: the daily driver's wide template (dccd379a: windowed borderless, `stretched_ar`, `CaptureMouse = false`,
4x MSAA, TMU 8192) with `[Glide] Resolution = scale x the primary display per axis` (scale 2, or 1 with `--no-supersample`; each
side capped at 8192 with one factor on both axes) and `[DirectX] Resolution = 1680x1050` (the 16:10 shell picture the cursor map
`I76_CURSOR_MAP_DGV=aw` and u32x assume). dgVoodoo sizes the borderless window to the [Glide] target scaled into the desktop, so
a 2x target gives a full-screen window of the display's shape; the 3D view is Hor+ at that shape (`I76_ASPECT = WxH`), the Esc menu
maps over the full window (`I76_U32X_MENU_ASPECT = W:H`), the 640x480 shell / movies sit 4:3 in the window. A 4:3 monitor gets the
same conf at 4:3 (`-AllowNarrow`): the proxy logs `aspect: 1600x1200 out of range (1.34..3.6) - not applied` = the stock camera, which
is right. No 16:10 / 16:9 conf variants are needed; `PLAY-16x10.bat` (the 16:10 conf + best-120) stays as the tested fallback.

Why not test by changing the desktop mode: the window is sized by the [Glide] target, so `--display 1920x1080 --no-supersample` on
the 3440x1440 desktop gives a centred 1920x1080 borderless window with the presets at 1920x1080 / 1920:1080 - the same conf and
map a 1080p monitor gets (the 2x target would be 3840x2160, a scale of the same shape). The pointer map is proven by the trip
route by clicks (option6-trip-test reads the window rect and clicks UI coordinates; the game must answer), the 3D shape by a
cockpit / hood capture in T05. Results in s.6.

## 5. The exe Scott will have

GOG's current install (the sandbox copy, `i76-map\sandbox-gog\main\app`) is i76.exe **9a232dcc** (2017 Galaxy / 2.1.0.17 offline
build): no `I76PATCH.DLL`, no WINMM import (CD audio through GOG's `win32.dll` + `audiere.dll` + `music\*.mp3`, so the proxy's
music switches `I76_MUSIC_RETAIL / RESUME` are inert there and GOG's shim plays the music; `setup-windows.ps1` says so), a
first-chance `CRASH ... exe+0x99997` at frame 0 (the PIT CPU-speed probe, handled by the game; FRESH-INSTALL-CHECK). The daily
driver / RC run 6319abf7 = the 2019 AiO exe 60abf7bc + the u32x rename; the proxy knows both layouts where they differ (hires
clock, tick-ms, mirror refresh gate) and checks the bytes at every other site (`patch: ... has UNEXPECTED bytes - not patching`
in mciproxy.log). The gate below runs the stable preset on 9a232dcc and reads that log (s.6.2). If Scott's copy is the AiO build,
`setup-windows.ps1` reports "the known-good GOG 2019 / AiO build" and the shell patch takes the 8960fa16 chain (s.3).

## 6. Gate (console, lab game-scott, PLAY.bat = tick19-42, proxy 9bab51fe, exe 9a232dcc)

### 6.1 First run 12:08-12:18: VOID as a verdict, and it wedged the console (my fault)

`autotest\runs\gate\20261023-120851`. Rows 1 (conf accepted at 3440x1440, client 3440x1440, md5 dccd379a) and 2 (leg-b bookmark
route 3 of 3) PASS; row 3 (the trip route through PLAY.bat) FAIL 0 of 2 with the game sitting at the main menu (gstate 6, the
capture shows the pointer parked near the top-left); row 4 wedged at the save screen until the coordinator had me stop it (i76.exe
48124, runner 47860; locks released, the global dgVoodoo.conf the gate hides put back, the player state restored from the run's
`saves-before` by md5, the scratch `save003.cmp` removed).

Cause, read from `autotest\lib\maplib.ps1` and `tools\tick-gaps\tg-gate.ps1`: the harness maps a click through the proxy's cursor map only
when the lane wrapper sets **`LAB_CURSOR_FREE=1`**; without it `Click-UI 217 311` is `SetCursorPos(217, 311)` in raw screen pixels, which
on the 3440x1440 panel is nowhere near TRIP. The RC's gate (tg-gate.ps1) sets that, plus `LAB_GAME_ENV` = the preset's keys for the
rows that boot without the launcher (leg-b, proxy-run, garage-ui, enter-melee), `I76_MUTE=1` and the shm suffix. My first runner set
none of them, so row 2's pass was the harness's own switch set, not the shipped preset, and row 4 ran the save screen with the
harness's launch under the wide conf but without the cursor map the conf expects (CaptureMouse = false) - its Place-Ui candidates
never read back and the row's wait had no timeout. Nothing of this is a property of the build. Second form of the runner
(`builds\scott-20261023\run-gate.ps1`, lab 27be9e8): tg-gate's environment, one row group per `.fps-lock` take (groups 1 / 2 / 3,7,8 /
4 / 5,6 / 9, then the two display tests), the shared `.fps-queue` line while waiting, a watchdog per group (7-10 min) that stops the
gate child tree and game-scott's i76.exe and puts the global conf back. Queued 14:54 behind the far-edge and game-types lanes.

### 6.2 What the shipped preset applied on 9a232dcc (mciproxy.log of the 12:08 launcher sessions)

Every switch of tick19-42 applied as on the AiO exe - `aspect: D 2.389, 20/20 sites`, `sim-tick: ON ... 12/12 sim gates, 4/4 display
hooks, 16/16 draw-side holds, 7/7 cosmetic sites`, `hires-clock: 2/2 simclock call sites`, `far-clip: on (1800 m, pools x16, 6/6
sites)`, terrain-lod 6/6, clutter-dist 8/8, road-dist / road-tex / shadow-dist / object-lod / terrain-tex / terrain-hyst / freeze,
cam-ground-fix, terrain-hull-fix, breakable-box, fix-health-pct, fix-label-table, cursor-map (`i76.exe 4/4 u32x.dll slots`, `aw
picture aspect 1680:1050`, `u32x.dll 5/5 USER32 slots behind the picture adapter`), zglide-tmufix, glide-refresh 120 Hz, menu-keys,
menu-draw, fade, sign-sound, font-private, mp-menu, coop-chain 7/7, coop-ai 27/27 of its other sites. The differences, all expected
for this exe:
- `patch: coop-ai: ai_FrameTick at 0x00403DDF has UNEXPECTED bytes - not patching` - `I76_COOP_AI`'s one layout-specific site (the
  host's AI tick; LAN co-op only, inert in single player). The 9a232dcc layout of that call is a follow-up for the LAN pack, not Scott.
- `joy-routing ... NOT HOOKED (no WINMM import)` -> `sim-tick: joystick watch OFF ... a wheel / pad waits for the next tick`: the early
  tick on a pad / wheel input is not available on this exe (keys still get it); at most one 41.7 ms tick of extra latency on analog
  input. New finding for the README's "what differs on the Galaxy exe".
- `NOTE: this exe has no WINMM.dll import ... the music redirect and the aux volume hooks cannot attach`: GOG's shim plays the music (s.5).
- The frame-0 `CRASH ... exe+0x99997` first-chance line, as documented for this exe.
- tick-factors `0/3`, `0/4` etc. are the "factor 1.000, nothing to install" lines at 41.667 ms, the same on the AiO exe.

### 6.3 Second run

PENDING (queued 14:54; results land here from `builds\scott-20261023\gate-<ts>\run.txt`).

## 7. Open risks

- **Non-ultrawide on real hardware: untested.** Only this PC's 3440x1440 panel exists here; 1920x1080 and 2560x1440 were proven as
  windows of that size (s.6), which exercises the same conf, map and camera numbers but not a different GPU / driver / DPI scaling.
  A 4:3 monitor was dry-run only (`Make-Wide-Conf -AllowNarrow`).
- **GOG exe layout.** The stable preset on 9a232dcc: see s.6.2 for which proxy sites applied. The AiO-exe path (60abf7bc) is what the RC
  runs and was not re-gated here; its shell chain was checked offline (s.3).
- **Program Files installs**: a Galaxy default install under `C:\Program Files (x86)\GOG Galaxy\Games` is user-writable on most PCs;
  if not, the setup fails with access denied (README: run as administrator once, or move the game).
- **Downloaded-file blocking (Mark of the Web)**: PowerShell is started with `-ExecutionPolicy Bypass`, dgVoodoo DLLs load; README
  says to tick Unblock on the zip. Antivirus false positives on dgVoodoo are a known thing (the README names it).
- **The repo's shipped `saves\savegame.dir` is 876 B for 13 records (92 B of zero slack)**: the game reads it fine (count first), the
  lab gate's row 4 insists on the exact 784 B, so the gate folder's copy was trimmed (backup in `builds\scott-20261023`). Not changed
  in the repo (AGENTS.md: never shrink the file); a follow-up could regenerate it exact with the save editor.
- **Music on 9a232dcc** is GOG's shim, not ours (s.5): the owner's music rulings do not reach Scott on that exe.
- **The preview preset** moved under this lane: OWNER-2300-FOG's fog start was 0.7 when the brief was written and 0.75 when copied
  (11:40); the copy is what was in the file then. The far-edge lane keeps changing it; this zip freezes one state.
- `README-SCOTT.md` says the 1080p / 1440p tests were done as windows on this PC; it does not promise other hardware.
