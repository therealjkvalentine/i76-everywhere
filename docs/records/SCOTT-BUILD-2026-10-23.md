# Scott build 2026-10-23: the tester zip over a GOG copy

Lane: Scott-build (owner 2026-10-23: "a build that Scott can run ... the latest stable copy so he can give feedback. Make sure
the repository is buildable off of the copy of the game he'll have ... which may not be ultrawide ... explain the home-row
keyboard controls"; coordinator: the zips go on GitHub, so NOTHING of GOG's inside, a draft pre-release, a patcher for the
user's own files). Repo commits `6bdba60`, `e85585f`, `98d96e1`, `4b28e82` (main); lab `builds\scott-20261023\`.

## 0. Deliverables

| what | where |
|---|---|
| the zip | `C:\Users\james\i76-uncap-lab\downloads\scott\Interstate76-i76-everywhere-scott-20261023.zip` - **2,881,558 B, 83 files, md5 `41a1b508`** (repo ce8ffc5; `<zip>.MD5SUMS` beside it). The gate ran on the zip packed from 4b28e82 (md5 c62e73d4); the final zip differs from it only in README-SCOTT.md, VERSION.txt and MD5SUMS text - every binary, script, preset and conf is byte-identical (the binaries' md5s are in s.1) |
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

### 6.3 Second run 15:58-16:34 (lab `builds\scott-20261023\gate-20261023-155827`, autotest runs 155828 / 160045 / 160526 / 160710 / 161741 / 162711)

One console take per row group, 30 s between takes, nothing else queued at the time. Every launch here carries the shipped preset
(LAB_GAME_ENV for the harness boots, PLAY.bat for the launcher rows), proxy 9bab51fe, exe 9a232dcc, i76shell 64923d95, u32x 06467bd2,
conf dccd379a.

| row | result | n | detail |
|---|---|---|---|
| 1 conf accepted | **PASS** | 1 | client 3440x1440 ACCEPTED with the global `%APPDATA%` conf hidden; conf put back (dccd379a); watermark capture taken (`runs\gate\20261023-155828\1-conf-watermark.png`, by eye) |
| 2 bookmark route (TRIP -> LOAD BOOKMARK -> TURRET TEST -> LOAD -> ACCEPT SALVAGE -> DONE -> mission, by memory) | **PASS** | 3 of 3 | leg-b b1 through B1.10; scene 7 up each time |
| 3 trip route through PLAY.bat | **VOID** | 0 of 2 | `option6-trip-test.ps1` line 77 takes the first `i76`/`nitro` process on the PC as "the game the launcher started": the orphaned `nitro.exe` pid 48740 (exp-nitro-mp, 1 thread in a kernel wait, unkillable until a reboot; coordinator 2026-10-23) wins every time -> "NOT in -GameDir ... killed, nothing clicked". Not a verdict on the launcher: the launcher's own game did start each time (its sessions are in mciproxy.log) and was stopped by my watchdog afterwards |
| 4 save screen | **VOID** | - | watchdog at 10 min right after "scratch installed" (`garage-ui.ps1` waits on a game process the same way) |
| 5 Esc-menu Exit, 6 melee by menus | **VOID** | - | watchdog at 9 min at "=== 5 ===" (proxy-run's launch, same cause) |
| 7 input.map | **PASS** | - | lint OK, md5 a66a37f7 unchanged |
| 8 force feedback | no verdict | - | needs row 3's mission |
| 9 T05 route fps (direct boot into t05.msn through the launcher's preset, the owner's route driven by keys) | **PASS** | 1 | **hill leg median 120.0 fps over 2604 m, 1 % low 96.9**; ridge 120.0 / 1 % low 108.7 (the RC's AiO-exe gate: 91 / 83 / 98 on three launchers, n 3). `t05-route-fps.ps1` filters by path + start time, so the zombie did not touch it |
| S player state | **PASS** | 4 of 4 groups that ended | byte-identical to the backup after every finished group; the two killed groups' state was put back by hand from `runs\gate\20261023-160710\saves-before` (md5) and the scratch `save003.cmp` removed; `--check` 13 records 784 B |
| D folder drift | **PASS** | 4 of 4 | only mciproxy.log written |

The two display tests (PLAY.bat `--display 1920x1080 --no-supersample` and `--display 2560x1440 --no-supersample`, s.4): the conf
and the four presets were rewritten as designed (`[Glide] Resolution = 1920x1080` / `2560x1440`, `I76_ASPECT = '1920x1080'` /
`'2560x1440'`, menu aspect the same), the game's own session read **`aspect: D 1.778, 20/20 sites; fov 90 -> 106.3 deg, hood 120 ->
133.2 deg ... present at 1.778:1`** and `hud-squeeze ... x 1/1.333` both times, and the T05 captures (`display-<WxH>\t05-cockpit.png`,
`t05-hood.png`, F6) show a 16:9 picture with side bars on the 21:9 panel, nothing stretched (the far ridge, the road and the car
look as they do at 21:9, narrower field). So the camera, the HUD and dgVoodoo's target agree on a 16:9 monitor's shape. Two
corrections to s.4's expectation: dgVoodoo kept the borderless window at the full desktop (3440x1440 at 0,0) and fitted the
16:9 target into it (stretched_ar), rather than making a 1920x1080 window - on a real 16:9 monitor both are the same thing; and the
pointer-map half of the proof (the trip route by clicks) is VOID for the same zombie reason as row 3. The proxy's cursor map was
up (`cursor-map: aw picture aspect 1680:1050`, `u32x.dll 5/5`), but a click landing on the drawn button was not observed.

**Verdict so far:** the stable launcher boots the GOG 2.1.0.17 exe with every switch of the shipped preset applied (s.6.2), the
bookmark route by memory and the T05 route at 120 fps PASS on it, the folder and the player state come through untouched, and the
display derivation gives a correct 16:9 picture. **Not yet shown on this exe: the menu pointer under the cursor map (rows 3-6).**
The RC's gate showed exactly that on the AiO exe with the same conf / preset / u32x / cursor map, and the proxy log shows the same
cursor-map lines here, but it is an inference until rows 3-6 are re-run after the owner's reboot:
`builds\scott-20261023\run-gate.ps1 -Groups '3,7,8','4','5,6'` (then the two display tests), one take per group, watchdogs on.

## 7. Open risks

- **Non-ultrawide on real hardware: untested.** Only this PC's 3440x1440 panel exists here; 1920x1080 and 2560x1440 were run as
  16:9 settings on it (s.6.3: camera, HUD and target agree, picture 16:9 with bars), which exercises the same conf and camera numbers
  but not a different GPU / driver / DPI scaling, and not the menu pointer at that size (void, zombie). A 4:3 monitor was dry-run
  only (`Make-Wide-Conf -AllowNarrow`).
- **The menu pointer on 9a232dcc under the shipped cursor map is inferred, not observed** (s.6.3 rows 3-6 void): re-run after the
  reboot. If it fails there, the fallback is the RC's conf / map pair as it is (the proxy lines match the AiO run), or `PLAY-16x10.bat`.
- **GOG exe layout.** The stable preset on 9a232dcc: s.6.2 - everything applied except the LAN-only `coop-ai` tick site and the pad /
  wheel early tick (no WINMM import). The AiO-exe path (60abf7bc) is what the RC runs and was not re-gated here; its shell chain was
  checked offline (s.3).
- **Shared harness vs the zombie:** `option6-trip-test.ps1` (line 77), `garage-ui.ps1` and `proxy-run.ps1` take any `i76`/`nitro`
  process as the game; a single-thread orphan blocks every launcher row of every lane until the reboot. Not changed here (other
  lanes' infrastructure); my runner ignores a single-thread nitro.exe for its own busy check only.
- **The orphaned proxy build vs HEAD:** the DLL is a clean build of `8cb3da2`; `0e01d3c` / `3d89698` (off-by-default lab switches) came
  later. A re-pack from a newer commit needs its own gate.
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

## 8. Evening 2026-10-23: the ALL preview, rebuilt on main, re-gated on GOG's exe (zip 20261023b, still a DRAFT)

Lane brief (owner 18:xx: "push the ALL version to github and draft scott an email ... make sure we tested everything we ask him to do");
coordinator: do not publish, the owner decides. Same tag `scott-20261023`, new asset name `...-scott-20261023b.zip` (the old asset deleted).

### 8.1 What changed

| item | value |
|---|---|
| proxy | `Strlkup.dll` **6208d3ad** (742,912 B), clean build of main **9fe3510** (`tools\build-proxy.ps1 -Ref 9fe3510`, new in the repo, reproduces it byte for byte; lab `builds\nitro-port-20261021\scott-9fe3510`) |
| PLAY-PREVIEW*.bat | preset `scott-preview` = lab `exp-polish2\...\presets\OWNER-2300-ALL.psd1` as of 18:16 (md5 09dd0cd3), only `Name` changed; labelled "EXPERIMENTAL GRAPHICS PREVIEW" in the .bat header and README |
| PLAY.bat | unchanged: tick19-42 (f7e589ef) |
| zip | `downloads\scott\Interstate76-i76-everywhere-scott-20261023b.zip` **2,886,744 B, 84 files, md5 28d99ecd6266601305bd794f68e6004e, sha256 15f82e92955b6f7e9c4a5e17fe4024d3e380e73cd8ad934665228aaf3e8e9bc8**, VERSION `scott-20261023b a8f694a`. Name guard + an independent check: 0 entries match the game-file pattern, 0 files content-identical to any of GOG's 371 |
| GitHub | asset replaced on the **draft** pre-release `scott-20261023` (body = README-SCOTT.md); `gh release download` sha256 = the local zip. Not published (coordinator); anonymous `curl -I` therefore not possible yet |
| fixes found by the tests | (a) **UNINSTALL-i76e.bat failed at its first step** (PS 5.1 `-File` leaves `$PSScriptRoot` empty in deploy-u32x's param default; i76e-prepare's `Stop` preference turned the child's stderr into a terminating error) - fixed 0818caa; (b) a zip extracted **without Unblock** tags 135 files and Copy-Item carries the tag to the deployed AutoHotkeyU32.exe / dgVoodoo DLLs - i76e-prepare now clears it every run (4d2e47b; lab `game-scott-motw`: setup OK while tagged, 135 -> 0); (c) **GOG's default options put the rear mirror at its middle level** (`I76PLYR.DEF` +0x4A / +0x4D / +0x4E = 1 / 1 / 0: cars on a flat sky colour, no road or terrain - seen on stable and preview alike, drives 21:21 / 21:26); at the RC's 2 / 2 / 1 the mirror shows road, terrain and clouds (drive 21:38, manual 22:16). The first-run setup now sets those three bytes only when they are GOG's defaults, keeps `I76PLYR.DEF.pre-i76e`, the uninstall puts it back (73cfd8d) |

### 8.2 Every preview key on GOG's exe 9a232dcc (PLAY-PREVIEW-T05.bat as Scott starts it, game-scott-b, 20:2x; then n 3 drives)

| key(s) | apply line in mciproxy.log |
|---|---|
| I76_SHADE_SMOOTH 1 | `shade-smooth: on (vertex shade -> ZGLIDE intensity through a 256-entry table ...)`, table built at mission load |
| I76_TERRAIN_MORPH 0.25 + STATELESS + SHADE 3 + BIG 2 | `terrain-morph: on, STATELESS ... band 0.25 x the ring distance ... height and shade, shade band x3.00 ... 64+ levels shade only; every pass` (the same line as the owner's exp-polish2 log) |
| I76_SKY_MIRROR 0 | `sky-mirror: ON - the rear-view mirror's sky draw does not scroll the clouds (2/2 mirror call sites)` |
| I76_MIRROR_FAR 1000 | `mirror-far: mirror camera far clip 100 -> 1000 m` |
| I76_MIRROR_LOD / EVERY / M16 / M16_SKY 0 / TEX 2 / PAL | `mirror-detail: on ...`, `mirror-every: ... every 2-th frame (stock layout Galaxy: every 2nd frame)`, `mirror-m16: ... (sky: the stock 8-bit cloud art ...)`, `mirror-tex: ...`, `mirror-pal: ... (25 palette pairs compiled in)`, `mirror-lod: ... x1.00 ...; the main view keeps x24.00` |
| I76_JUMP_NOSE 0.91 | `jump-nose: factor 0.91, site 0x43a7f5 patched`; fired on the drive: `first airborne step, pitch rate -0.9234 -> -0.8403 rad/s (x 0.91)` |
| I76_CLUTTER_DENSITY 0.5 / FADE 450 / DIST 2300 | `clutter-dist: on, 8/8 sites; view z 120 -> 2300 m ... fade: full density to 450 m ... density x 0.50` |
| I76_GLIDE_FOG 0.75,hzd + _ALPHA 1 | `glide-fog: on - fog table clear to 0.75 x far ...`, `glide-fog alpha: FADE TO TRANSPARENT ...`, `grFogMode ok, grFogColorValue ok, grFogTable ok`, `grDrawTriangle hooked`, `grAlphaBlendFunction hooked, grAlphaCombine hooked, grChromakeyMode hooked` |
| far clip / roads 2300, terrain LOD 24, TERRAIN_TEX / OBJECT_LOD / SHADOW_DIST / ROAD_TEX | `far-clip: on (2300 m, pools x16, 6/6 sites)`, `road-dist: 450 -> 2300 m`, `terrain-lod: x24.00, 6/6`, `terrain-tex: x8.00`, `object-lod: x8.00`, `shadow-dist: 50 -> 200 m`, `road-tex: 60 -> 480 m` |
| not applied (expected, as for the stable preset s.6.2) | `coop-ai: ai_FrameTick ... UNEXPECTED bytes` + 2 trigger/damage sites (LAN co-op only), `joy-routing ... NOT HOOKED (no WINMM import)` |

Nothing dropped: every preview key applies on 9a232dcc. No `CRASH` line in any session except the documented frame-0 PIT probe (exe+0x99997).
Preview T05 drives (row 9 route, cockpit): hill median **116.0 / 115.3 / 115.6 fps, 1 % low 73.3 / 69.3 / 71.5**, ridge 121.2 / 117.0 / 121.0
(n 3; stable on the same folder 120.0 / 1 % 88.0 and 120.0 / 86.8). Captures (`drive-PLAY-PREVIEW-20261023-213817\mirrors.png`, `boot-PLAY-PREVIEW-T05\*.png`):
bushes render as bushes (no black squares), the far edge fades, the mirror shows road / terrain / clouds once the options are at 2 / 2 / 1;
one of four mirror frames had a large white block (a near object or a PAL remap edge case; not chased).

### 8.3 Gate on the stable PLAY.bat (lab game-scott-b = pristine 9a232dcc + the zip + its own first run; runner `run-gate.ps1`, lab bd81811 ff.)

| row | result | n |
|---|---|---|
| 1 conf accepted (global conf hidden) | PASS | 1 |
| 2 bookmark route TRIP -> ... -> mission (by memory) | PASS | 3 of 3 |
| 3 trip route through PLAY.bat by pointer clicks, 120 fps | **PASS** (the row that was void at 15:58) | 2 of 2 |
| 4 save screen (gate-folder) | harness hang after the garage is reached (n 2; B1.7 garage each time) -> replaced by `manual-save-esc.ps1`: SAVE BOOKMARK, typed SCOTT, SAVE x2 -> `save018.cmp` + savegame.dir written, `--check` OK, files put back | manual 1 |
| 5 Esc-menu Exit (gate-folder) | harness hang after the menu opened (n 3; the menu capture is fine) -> manual: Esc (skips the opening), Esc (Spanner's Cafe menu up), click Exit at the drawn place -> menu closed | manual 1 |
| 6 melee by menus | not run (README does not ask it) | - |
| 7 input.map lint + unchanged | PASS | 1 |
| 8 force feedback | INFO: no FF device plugged in | - |
| 9 T05 route fps | PASS 120.0 / 1 % 88.0 (and 120.0 / 86.8 in the capture drive) | 2 |
| launcher boots (group P: PLAY-PREVIEW-T05, PLAY-T05, PLAY-PREVIEW, PLAY-16x10, PLAY-balanced, PLAY-stock, PLAY-i76) | all 7 start, window 3440x1440, AHK layer up, 0 crash lines, 0 unapplied sites but coop-ai | 1 each |
| display tests 1920x1080 / 2560x1440 `--no-supersample`, **both** launchers | conf `[Glide] Resolution` = the size, presets rewritten, `aspect: D 1.778, 20/20 sites`, 16:9 picture with bars; **pointer**: TRIP -> LOAD BOOKMARK -> row -> LOAD -> ACCEPT SALVAGE -> DONE all clicked through (7 step shots each) | 4 |
| uninstall on a copy | all 371 GOG files md5-identical to pristine afterwards | 3 (each zip iteration; final on game-scott-c) |

The row 4 / 5 hang: my own `manual-save-esc.ps1` hung the same way when it read garage-ui.ps1 through a pipe (the game leg-b starts inherits
the pipe's write end); with output to a file it ran. gate-folder's rows were not changed (shared harness). Run-gate's display tests passed
`--display` without its value until 21:09 (Start-Process joins an argument array unquoted) - the two `cmd.exe ... PLAY.bat --display`
processes from 16:31 / 16:33 are that bug's leftovers (not stopped: not started by this session); the 20:29 pair was mine and was stopped.

### 8.4 README-SCOTT instruction -> run that covers it

| README asks | covered by |
|---|---|
| unzip into the GOG folder, Unblock | every gate folder = pristine + Expand-Archive; MOTW folder with every file tagged (8.1 b) |
| double-click PLAY.bat: one-time setup, the yellow "NOT the GOG 2019 build" line | `PLAY.bat --setup` on game-scott-b / -c (log `setup-game-scott-*.txt`), row 3 through PLAY.bat |
| PLEASE STAND BY, Esc skips the intro | rows 2 / 3 / display tests (intro skipped by Esc, step01 shot) |
| PLAY-PREVIEW.bat, PLAY-T05.bat, PLAY-PREVIEW-T05.bat | group P boots; row 9 on PLAY.bat and PLAY-PREVIEW.bat presets; display tests on PLAY-PREVIEW.bat |
| PLAY-16x10 / balanced / stock / i76 | group P boots |
| `--no-supersample`, `--display WxH` | display tests (4) |
| `--setup` | the setup runs above |
| keys: W/S/A/D, I, F6, F1, Esc | row 9 drives (W / A / D keys), captures with F6 / F1, the Esc menu check; the whole table = input.map lint against the exe (row 7) and docs\CONTROLS.md (generated from the same map) |
| menus by mouse; SAVE BOOKMARK; TRIP -> LOAD BOOKMARK | rows 2 / 3, display tests (pointer), manual save check |
| popups Enter / Space, overwrite Y / N | **not exercised here** (the shell key patch bytes are the RC's chain, s.3; the overwrite prompt was not reached: the manual check wrote a new bookmark) |
| music in missions (GOG's shim on this exe) | not by ear (all runs muted); the log notes "no WINMM import" as documented |
| pad / wheel | AHK layer starts (group P); no controller connected: row 8 INFO |
| mciproxy.log written | every session |
| delete the global dgVoodoo.conf if the picture is wrong | row 1 runs with it hidden |
| UNINSTALL-i76e.bat | 8.3 last row |

### 8.5 Open

- Overwrite prompt Y / N and the popup Enter / Space keys on 9a232dcc: not run in this pass.
- Rows 4 / 5 through gate-folder.ps1 on this folder: the pipe-inheritance hypothesis is untested there.
- Real 16:9 hardware: still computed + windowed tests only.

## 9. 2026-10-24: both packages rebuilt with the two Windows 11 fixes, verified on the laptop (26100.9711), release still a DRAFT

Packaging lane (Sonnet). Repo commit `0467282` (package-scott.ps1: new `-DgVoodooFallbackDir`; scott-preview.psd1 = current exp-polish2 OWNER-2300-ALL, md5 375425b7, only `Name` changed; README-SCOTT.md and i76e-prepare.ps1 say 2.87.5 + the swap-back line).

| item | value |
|---|---|
| A: overlay zip | `downloads\scott\Interstate76-i76-everywhere-scott-20261024.zip` **4,187,803 B, 95 files, md5 04983fdefc577ff59c8fff8a08d22deb, sha256 4370190dffd338454826b8dcf7d61022d9e296f811f61b33dffa120c3fbb9782**, VERSION `scott-20261024 0467282`. Proxy inside = **53944fb2** (main 3ef108d), `_i76e\dgVoodoo` = 2.87.5 (six files, md5s checked by the packager; DDraw.dll c70a0ee6), `_i76e\dgVoodoo-2.87.3` = the fallback (DDraw ab19386d) with its README line, PLAY-PREVIEW preset = OWNER-2300-ALL as of 2026-10-24. Name guard passed (no GOG file; no i76.exe / i76shell / ZFS in the zip) |
| B: private full zip | `downloads\scott-full\Interstate76-i76e-ALL-20261024b.zip` **442,940,921 B, 570 entries, md5 e34c19f6b16dde1b16a07eadc53c8417**, root folder `Interstate76-i76e-ALL-20261024` (base = last night's 20261024.zip = exp-polish2 at 23:05 + `_fit` launcher + README.txt; older zips kept). STRLKUP.DLL = 53944fb2, OWNER-2300-ALL.psd1 md5 375425b7, the eight dgVoodoo files = 2.87.5 (md5s per DGVOODOO-UPDATE s.5, all matched), the 2.87.3 files in `Interstate 76\_dgvoodoo-2.87.3`; no mciproxy.log / ipxwrapper.log / display.txt were present; README.txt got the "built 2026-10-24 ..." line. Written with Windows tar (forward-slash entries) |
| GitHub | draft pre-release `scott-20261023` (still draft; tag untagged-98cb8fd6bc87ee730ea7), asset replaced: `...-scott-20261024.zip`, old 20261023b asset deleted, body = README-SCOTT.md; downloaded asset sha256 = the local zip |

Laptop (LAPTOP-HPK11OMS, Windows 11 26100.9711, 1920x1080), runner `laptop-run.ps1 -Script wmr-scott.ps1`, muted, lock held per group. A = fresh copy of the pristine GOG game (`i76-map\sandbox-gog\main\app`, i76.exe 9a232dcc) at `C:\i76-bench\scott-a\game` + the zip + `PLAY-T05.bat --setup`; B = fresh Expand-Archive of the zip at `C:\i76-bench\scott-b`. Hold 20 s per boot.

| launcher | n | reached t05 | alive at 20 s | CRASH lines | winmm-heapfix | dgVoodoo | aspect |
|---|---|---|---|---|---|---|---|
| A: PLAY-T05.bat | 5 | 5 | 5 | 5 of 5 boots = the one frame-0 probe `0xC0000096 at exe+0x99997`, nothing else | applied at DllMain (SHLWAPI split, 3 slots -> the layer's) | DDraw c70a0ee6 | D 1.778, 20/20 sites |
| A: PLAY-PREVIEW-T05.bat | 5 | 5 | 5 | same (probe only) | applied | c70a0ee6 | D 1.778; `shade-smooth: on` present (the preview preset is live) |
| B: PLAY-T05.bat (fresh unzip, display fit run on the first start) | 3 | 3 | 3 | **0** | applied | c70a0ee6 | `_fit\display.txt` = 1920x1080 x2, aspect D 1.778, 20/20 sites |

Raw logs on the laptop: `C:\i76-bench\runs\wmr\scott-{a,b}-*`. Not measured: music by ear (muted), anything past 20 s in the mission, a real 16:9 monitor beyond the laptop's panel.

## 10. Release renamed (2026-10-24 18:36, then again 18:4x: v0.7.3)

The owner named the public tester release **v1.3.0-alpha.1** (not "scott"). The draft `scott-20261023` was published, then
replaced: new tag `v1.3.0-alpha.1` (gh created it at main's HEAD), release title "v1.3.0-alpha.1 - tester build (over
your GOG copy)", body = README-SCOTT.md with the new heading, asset renamed
`Interstate76-i76-everywhere-v1.3.0-alpha.1.zip` (byte-identical to the 20261024 zip, md5 04983fde, 4,187,803 B);
anonymous download checked (HTTP 200, same length). The `scott-20261023` release and tag were deleted.
URL: https://github.com/therealjkvalentine/i76-everywhere/releases/tag/v1.3.0-alpha.1
Final name (owner, 18:4x): **v0.7.3** - tag v0.7.3 at the same commit, asset Interstate76-i76-everywhere-v0.7.3.zip (same bytes), v1.3.0-alpha.1 deleted. URL: https://github.com/therealjkvalentine/i76-everywhere/releases/tag/v0.7.3
Final (owner, 18:5x): release title "Interstate '76 Patch Kit (i76-everywhere) v0.7.3", asset Interstate76-Patch-Kit-i76-everywhere-v0.7.3-d4b765a.zip (d4b765a = the v0.7.3 tag commit; same bytes, md5 04983fde); the v1.0.0 "Vacation Build" release was deleted (its git tag kept). Only v0.7.3 is listed.

## 11. Renamed to "Patch Kit" (2026-10-24 evening; tag commit f5d5ac0)

Owner: user-facing text names neither the first tester nor the developer. Packaging lane (Sonnet), commits `e73ec66` + `f5d5ac0`.

Rename map: `tools/scott/` -> `tools/patch-kit/`; `tools/scott/README-SCOTT.md` -> `tools/patch-kit/README.md` (shipped in the zip as `README-PATCH-KIT.md`, so it cannot clobber a game-folder README); `tools/package-scott.ps1` -> `tools/package-patch-kit.ps1` (new `-Version`, default 0.7.3; zip `Interstate76-Patch-Kit-i76-everywhere-v<Version>-<sha>.zip`); preset `presets/scott-preview.psd1` -> `presets/preview.psd1` (`Name = 'preview'`); references fixed in Build-From-GOG.ps1, setup-windows.ps1, i76e-prepare.ps1, Apply-Shell-Keys.ps1, OPEN-FEATURES, OWNER-TEST-LIST, RC-20261024, research/game-files-and-cast. The README says "the developer" for James and ends feedback with "send it to whoever gave you this kit". Launcher names unchanged. Lab output dir is now `downloads\patch-kit\`.

New zip `downloads\patch-kit\Interstate76-Patch-Kit-i76-everywhere-v0.7.3-f5d5ac0.zip`: 4,187,799 B, 95 files, md5 84b977c5e5ed69a06390d2a0af41b5be, sha256 365fdd2ab74438fc525954ef6afc3574f2998b90bb083b68a3c22e525054ee5f. Inputs as s.9 (proxy 53944fb2 from wmr-3ef108d, dgVoodoo 2.87.5 + 2.87.3 fallback, AHK 1.1.37.02; the dgVoodoo/AHK dirs were taken from the d4b765a zip, md5-checked by the packer). Versus the d4b765a zip: 95 vs 95 entries; every binary md5-identical; differing: the 4 renamed files (README, preset, Apply-Shell-Keys.ps1, shell-keys-patch.json paths), and re-texted setup-windows.ps1, i76e-prepare.ps1, the four PLAY*.bat (preset name), VERSION.txt, MD5SUMS, two README-dgVoodoo.txt (date stamp).

Laptop (Windows 11 26100, 1920x1080), `wmr-scott.ps1`, fresh pristine GOG copy (371 files, i76.exe 9a232dcc) + the new zip at `C:\i76-bench\kit-a\game`, setup via `PLAY-T05.bat --setup`; hold 20 s:

| launcher | n | reached t05 | alive | CRASH lines | heap fix | DDraw |
|---|---|---|---|---|---|---|
| PLAY-T05.bat | 5 | 5 | 5 | only the frame-0 probe `exe+0x99997` (5 of 5) | applied (SHLWAPI split, 3 slots) | c70a0ee6 |
| PLAY-PREVIEW-T05.bat | 5 | 5 | 5 | same | applied | c70a0ee6 |

(i76.exe after setup 64165126, proxy 53944fb2.) Raw logs on the laptop `C:\i76-bench\runs\wmr\scott-kita-*`, `scott-kitap-*`.

GitHub: tag v0.7.3 moved d4b765a -> f5d5ac0, asset `Interstate76-Patch-Kit-i76-everywhere-v0.7.3-f5d5ac0.zip` uploaded (anonymous download HTTP 200, sha256 = local zip), old d4b765a asset deleted, body = tools/patch-kit/README.md, title unchanged. https://github.com/therealjkvalentine/i76-everywhere/releases/tag/v0.7.3
