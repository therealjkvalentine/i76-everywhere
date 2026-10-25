# One launcher for the release candidate (2026-10-24, launchers lane)

Owner, 2026-10-24: *"Why separate launchers for the Gold RC? Ideally the main one launches everything - story, LAN and
everything else. Fine to include a vanilla / play-stock-networking option or others WITHOUT features. No dependency on
opentrack: if it's not set up or running, just skip it every time instead of the current wait."* Later the same evening
(coordinator): the family LAN pack merges into the RC, so PLAY-LAN.bat goes too; PLAY-STABLE / PLAY-VANILLA keep the stock FFB;
a per-machine graphics override (`presets\local.psd1`) and three tier files.

## 1. What changed

### PLAY-i76.ps1 (repo root = the source; commits 319d4b8, 4813d2f and this record's commit)

| | before | now |
|---|---|---|
| head look | opt-in `-HeadTrack`; with game detection unavailable a bounded 20 s wait for `FT_SharedMem` | **opt-out**: on when opentrack is installed (`$OpenTrack` exists) and the folder has `_ahk\i76-opentrack-headlook.ahk`; opentrack started unless running, game detection + the UIA autostart helper in the background; **never waited for** (the layer's `OpenFT()` retries `FT_SharedMem` on every 8 ms tick, read in the RC copy: it does not block). Not installed / no layer / fails to start: one log line, launch goes on. `-NoHeadTrack` disables. `-HeadTrack` still accepted (adds "although -HeadTrack was given" when opentrack is missing) |
| custom FFB | opt-in `-Ffb` | **auto**: after the game process starts, `Ffb-Probe` (new in `tools\ffb\FfbCore.ps1`: DirectInput8 `EnumDevices(GAMECTRL, ATTACHEDONLY \| FORCEFEEDBACK)` only - nothing created or acquired, the game must find the wheel free) looks for a wheel (DI type 0x16 "driving", or a wheel-like product name). Found -> `ffb-interposer.ps1` starts (own window = its panel). `-NoFfb` = the game's own FFB. `-Ffb` forces the interposer. An older FfbCore without `Ffb-Probe` -> the game's own, said in the log |
| per-machine override | - | `<GameDir>\presets\local.psd1` (an `Env` hashtable) merged over the preset: keys replace, `''` removes (stock). Every key logged. Not applied to preset `stock` or with `-NoLocal`. gitignored, never shipped. The preset guard runs on the merged set |
| launcher log | console only (the .bat files run it hidden) | `<GameDir>\play-i76.log` (last 400 lines): the launch line, local-override keys, head look status, game start (pid, preset, mission), FFB status, game exit code, each with seconds since the script started |
| exit cleanup | FFB zeroing dot-sourced `tools\ffb\FfbCore.ps1` only (absent in a game folder) | finds it in `_ffb` too |

Probe cost: `Ffb-Probe` in a fresh PowerShell 0.62 / 0.55 s including the PowerShell start (n 2, desktop, T300 found:
`Thrustmaster T300RS Racing Wheel type=0x16`). It runs after the game has started, so it adds nothing to the time to the game.

### The RC launcher set (lab `builds\rc-20261024\stage`, generator `launchers-20261024\make-launchers.ps1`)

| launcher | preset | head look | FFB | notes |
|---|---|---|---|---|
| `PLAY.bat` | OWNER-2300-ALL (story + the LAN switches I76_COOP_AI / COOP_CHAIN / MP_MENU) | auto (opentrack installed) | interposer when a wheel is attached | through the menus; hosts / joins LAN |
| `PLAY-T05.bat` | OWNER-2300-ALL | auto | auto | = `PLAY.bat --mission t05` |
| `PLAY-VANILLA.bat` | stock (no I76_* switch), `dgVoodoo.16x10.conf` (as the driver's PLAY-stock.bat) | off | the game's own | comparison and plain networking with stock copies; ignores local.psd1 |
| `PLAY-STABLE.bat` | tick19-42 (no new graphics) | auto | **the game's own** (`-NoFfb` default) | the fallback; the stock FFB focus-loss fix is another lane's |
| retired | `PLAY-WITH-HEADLOOK.bat`, `PLAY-WITH-FFB.bat`, `PLAY-LAN.bat` | | | in `_superseded-20261024\` with a note on line 2 (`PLAY-LAN-lanpack.bat`: the old `_superseded-20261024\PLAY-LAN.bat` already used that name); removed from the top level by `REMOVE.txt`, the originals go to the install's rollback folder |

Options on every one (any order): `--no-headtrack`, `--no-ffb`, `--mission <name>` (no menus, no movies),
`--legacy-multiplayer`, `--ai-skill N`. Same spellings as PowerShell switches also accepted (`-NoHeadTrack`, `-NoFfb`).

Tier files (repo `presets\`, staged into `Interstate 76\presets\`), revised per the per-Mac sweep (MAC-GRAPHICS-TUNE-2026-10-24.md:
1800 m alone = 27 fps on an M5 Pro, 17 on an M2; LOD 24 another 22-26 fps): `graphics-mac.psd1` (far clip / roads / bushes /
terrain LOD / mirror / fog / sky key removed = stock; terrain morph + smooth shade + detail x2), `graphics-mac-fast.psd1` (M5 Pro
class: detail x8 + roads 1800 m, the rest stock), both checked over OWNER-2300-ALL with `-DryRun` (no guard refusal),
`graphics-balanced.psd1` (= OWNER-2300-ALL's graphics keys), `graphics-high.psd1` (LOD x32, texture x24, 2300 m, 120 Hz;
**UNTESTED**, past the measured far-clip edge at LOD 24). VERSION.md: "to tune this machine, copy a tier file to
presets\local.psd1 and edit"; LAN is in PLAY.bat and every machine in a LAN game must run the same proxy md5.

## 2. Tests

### Desktop (DESKTOP-AUR3UBC, opentrack installed, T300 attached), lab twin rc-twin-20261024

Runner: lab `builds\rc-20261024\launchers-20261024\desk-run.ps1` (CONSOLE-LOCK.md: `.fps-lock` + `.console-owner`, queue line, no
game running anywhere, console active / not RDP, idle 120 s) calling the same `launcher-job.ps1`; muted per pid, shm suffix
`rc-twin-20261024`. The console was shared with the lanfix / nitro / ffb-panel lanes all evening: the first batch waited 65 min, the
second 73 min. Proxy 53944fb2 (the RC's). No opentrack instance was running before any boot (the owner's was not touched); every
opentrack / head-look / interposer process a boot started was gone 6 s after the game.

| bat | n | bat -> i76.exe | bat -> in mission | head look (log) | FFB (log) / [0x52bbe4] | CRASH | alive |
|---|---|---|---|---|---|---|---|
| PLAY-T05.bat + one Alt-Tab cycle | 2 | 2.56 / 2.01 s | 9.2 / 7.5 s | ON, opentrack started (+0.64 / +0.44 s) | interposer ran; pointer 0 before, while away and after | 0 / 0 | yes |
| PLAY.bat --mission t05 (opentrack) | 2 | 2.05 / 2.15 s | 7.6 / 7.3 s | ON (+0.45 s) | interposer ran; pointer 0 | 0 / 0 | yes |
| PLAY.bat --mission t05 --no-headtrack | 2 | 1.82 / 1.83 s | 6.8 / 6.9 s | OFF (+0.31 s) | interposer ran; pointer 0 | 0 / 0 | yes |
| PLAY-VANILLA.bat --mission t05 | 2 | 1.79 / 1.78 s | 7.0 / 6.5 s | OFF | the game's own (-NoFfb); pointer live | 0 / 0 | yes |
| PLAY-STABLE.bat --mission t05 | 2 | 2.14 / 2.12 s | 7.4 / 7.7 s | ON (+0.44 / +0.46 s) | the game's own (-NoFfb); pointer live | 0 / 0 | yes |
| PLAY.bat (menus, 100 s) | 2 | 2.02 / 2.10 s | - | ON | "custom interposer ON - wheel found: Thrustmaster T300RS Racing Wheel"; pointer live in the menus (the interposer waits for a mission before it takes the wheel) | 0 / 0 | yes |

**Head look with / without opentrack (PLAY.bat --mission t05, n 2 each):** bat -> game process 2.05 / 2.15 s with opentrack
started vs 1.82 / 1.83 s with `--no-headtrack` (+0.28 s: the registry write and `Start-Process opentrack`); bat -> in mission
7.6 / 7.3 vs 6.8 / 6.9 s (+0.6 s, opentrack's own start competing for the CPU while the mission loads). No multi-second wait in
either case (the old path's bounded wait was up to 20 s). Laptop (opentrack absent): the decision costs nothing measurable.

**Stock FFB vs the interposer (coordinator point 1).** With a wheel found, the interposer acquires the wheel only once a mission
is loaded (it waits for the player entity), then zeroes the engine's I7FF_SIM_Effect pointer `0x52bbe4`, so no stock effect call
reaches I7_SFRCE.DLL while it holds the wheel: read back 0 in all 6 desktop mission boots, including during and after the Alt-Tab.
In the menus (before any mission) the pointer is live and the interposer holds nothing: the stock driver owns the wheel there and
the two never hold it at the same time. Restored on the interposer's exit. PLAY-STABLE / PLAY-VANILLA: pointer live, no interposer
(the stock path the focus-loss lane is fixing, untouched).

**Alt-Tab (point 3), n 2:** focus to the taskbar for 4 s and back for 6 s with the interposer running: game alive, interposer
alive, pointer still 0; the panel (screenshot `desk\launch-t05-b-*.interposer.png`) read `LIVE - Thrustmaster T300RS Racing Wheel`,
`engine FFB call bypassed (0x52bbe4 = 0) - firing safe`, loop 38.6 Hz, and an empty events list: no `DEVICE LOST`, so no reacquire
was needed (it acquires DISCL_EXCLUSIVE | DISCL_BACKGROUND; `Ffb-Reacquire` stays the path if another app takes it).

**Bug found and fixed on the way (9f6e04f):** `$ffb` is the same variable as the `-Ffb` switch (PowerShell names are case-insensitive).
`$ffb = $null` reset the switch, so **since f7e784f (2026-08-02) `PLAY-i76.ps1 -Ffb`, i.e. PLAY-WITH-FFB.bat, never started the
interposer**; and `$ffb = <Process>` cannot be stored in a switch, so the first desktop boots logged "the interposer did not start"
while it ran, and the launcher could not stop it or zero the wheel at exit (the interposer's own exit-with-the-game covered it). Now
`$ffbProc`; the 23:28 / 23:31 menu boots logged the interposer correctly. The owner's 2026-10-24 "PLAY-WITH-FFB felt good" drive
(FFB-WHEEL-2026-10-24.md) therefore most likely had the stock force feedback unless the interposer was started by hand
(`FFB-PANEL.bat`): worth asking him before tuning on that impression.


### Laptop bench (LAPTOP-HPK11OMS, opentrack NOT installed, no wheel)

Bench twin `C:\i76-bench\rc-twin` brought to the RC's runtime first: it still had dgVoodoo 2.87.3 (crashed at frame 0 in
`DDRAW.dll+0x4AB0A`, the laptop's known 2.87.3 fault, 1 boot) and proxy fc6a5960 (one boot crashed in `winmmbase.dll+0x5AB3`
at frame 0, the fault 53944fb2's winmm heap fix is for). Both replaced with the RC's files (2.87.5 set; STRLKUP.DLL 53944fb2 via
`laptop-run.ps1 -SyncDll`, md5 read back); the 2.87.3 set parked in `_dgvoodoo-2.87.3`, the old launchers in `_pre-launchers-20261024`.
Runner: lab `laptop-bench\bench\launcher-job.ps1` via `laptop-run.ps1` (the bat through `cmd /c call`, muted per pid, shm suffix
`i76bench`; "in mission" = the player entity `[[[0x54A264]]+0x70]` non-zero).

| bat | n | bat -> i76.exe | bat -> in mission | head look (log) | FFB (log) | CRASH lines | alive |
|---|---|---|---|---|---|---|---|
| PLAY-T05.bat | 2 | 1.47 / 1.48 s | 4.4 / 4.2 s | skipped - opentrack not installed (+0.22 s) | the game's own - no wheel | 0 / 0 | yes |
| PLAY.bat --mission t05 | 2 | 1.48 / 1.46 s | 4.4 / 4.3 s | skipped (+0.22 s) | no wheel | 0 / 0 | yes |
| PLAY-VANILLA.bat --mission t05 | 2 | 1.46 / 1.45 s | 4.2 / 4.2 s | OFF (-NoHeadTrack) | the game's own (-NoFfb) | 0 / 0 | yes |
| PLAY-STABLE.bat --mission t05 | 2 | 1.46 / 1.46 s | 4.2 / 4.2 s | skipped (+0.21 s) | the game's own (-NoFfb) | 0 / 0 | yes |
| PLAY.bat (menus, held 30 s) | 2 | 1.46 / 1.48 s | - | skipped | no wheel | 0 / 0 | yes, 100 s |
| PLAY.bat --mission t05 + local.psd1 `I76_MIRROR_EVERY='3'` | 2 | 1.51 / 1.48 s | 4.3 / 4.2 s | skipped | no wheel | 0 / 0 | yes |

The head-look decision is logged 0.21-0.23 s after the script starts; the game is started at +1.12-1.16 s (of which 0.8 s is the
existing "let the AHK layers finish their device probe" sleep). Opentrack absent costs nothing measurable. The override run's log
line: `local override: I76_MIRROR_EVERY=3 (preset 2)`, and the proxy read it back (`mirror-every: the rear mirror redraws every
3-th frame`, both boots); local.psd1 removed afterwards. No helper processes were left after any boot.

## 3. Where the files are

- RC stage: lab `builds\rc-20261024\stage` (MD5SUMS / REMOVE.txt refreshed; `.pre-launchers-20261024` copies of both), the
  stage's old launchers in `launchers-20261024\stage-before\`. Twin `rc-twin-20261024`: `install-rc.ps1 -Target` applied (rollback
  folders `_rollback\rc20261024-20261024-2051*`, `-205504`, `-211539`).
- `exp-polish2\Interstate 76\PLAY-i76.ps1` replaced (old kept as `PLAY-i76.ps1.d2059e2d-pre-launchers`); it has no `_ffb`, so FFB
  there is "the game's own - the interposer is not in this folder".
- Patch kit: `tools\package-patch-kit.ps1` ships the repo's `PLAY-i76.ps1` (not `_ffb`, not the head-look layer), so the next kit
  picks the change up as is: head look skips itself (no layer), FFB says "not in this folder". The public zip was not rebuilt.
  The kit's preset list does not include the tier files; add them when the kit is next built if wanted.

## 4. Installed in the release candidate (2026-10-24 23:54)

The stage also holds the Gold-LAN lane's work in progress (proxy a7acc44b with `STRLKUP.DLL.53944fb2-pre-lan`, six `ADDON\auto0*.lvl`),
so `install-rc.ps1` (which applies the whole stage) was NOT used on the RC or, after 22:20, on the twin. Instead
`launchers-20261024\install-launchers.ps1` copies only this lane's 14 files and removes the 3 retired launchers, keeping every replaced
or removed file with a `state.txt` of md5s in `release-candidate\_rollback\launchers-20261024-20261024-235400`
(`install-launchers.ps1 -Rollback <that dir>` undoes it). Read back: a second run says "already applied". The RC's proxy stays 53944fb2.

| file | before | after |
|---|---|---|
| `PLAY.bat` | 8b2a25ac | bcac588b |
| `PLAY-T05.bat` | 09e52511 | 53e4936a |
| `PLAY-VANILLA.bat` | - | 0f19209a |
| `PLAY-STABLE.bat` | 8e2f3755 | a82f3f22 |
| `VERSION.md` | c315f6d6 | 6be4bf59 |
| `Interstate 76\PLAY-i76.ps1` | d2059e2d | 15b9862e |
| `Interstate 76\_ffb\FfbCore.ps1` | 6ba7c66b | 881e6a57 |
| `Interstate 76\presets\graphics-mac.psd1` / `-mac-fast` / `-balanced` / `-high` | - | 95b9a1af / a31824f9 / 76f115d8 / 10a4ee18 |
| `_superseded-20261024\PLAY-WITH-FFB.bat` / `PLAY-WITH-HEADLOOK.bat` / `PLAY-LAN-lanpack.bat` | - | ad9eff0e / afda549b / 9d934036 |
| `PLAY-WITH-FFB.bat` / `PLAY-WITH-HEADLOOK.bat` / `PLAY-LAN.bat` | 7953dcf4 / d6735d25 / 1cdf1e9e | removed (in the rollback folder) |

Note: the RC's other launchers (`PLAY-TICK*.bat`, `PLAY-P18-BALANCED.bat`) call the same PLAY-i76.ps1 without `-NoFfb` /
`-NoHeadTrack`, so they now also get head look and the interposer when the hardware is there.
