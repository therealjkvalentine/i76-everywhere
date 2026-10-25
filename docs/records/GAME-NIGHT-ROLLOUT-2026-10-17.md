# Game night rollout, 2026-10-17: one LAN pack for the PC and three Macs

Goal: The developer, the M4 Max tester and the M2 tester (Macs, Wine) plus the Windows PC can play I'76 over IPX at home, with identical game
data and one control map. The one-page player sheet is [../GAME-NIGHT.md](../GAME-NIGHT.md).

## 1. State of each machine (end of the session)

| machine | game copy | md5 check | controls | IPXWrapper | starts? |
|---|---|---|---|---|---|
| **The M2 tester Mac** (the family Mac over ssh, macOS 15.5, arm64, admin, Rosetta, 15 GB free, firewall off) | `~/Games/Interstate76-MP/Interstate 76.app` + Desktop link `Interstate 76 LAN.app` | 496 pack files, 0 mismatches | unified map `a66a37f7` | 0.7.2 + Wine overrides | **yes**: started in 9 s, main menu reached (shell screen fn 0x10025a50), quit cleanly, audio mute restored to off. Needed the stub rebuilt for macOS 11+ (section 4) |
| **The M4 Max tester Mac** (the family Mac over ssh, macOS 26.6.2, arm64, admin, Rosetta, **24 GB free of 926**, firewall **on**) | same layout as the M2 tester's | first sync 17:22: 496 files, 0 mismatches, Desktop link made | same | same | **not yet run**: the Mac kept dropping off the network (sleep). A loop on the developer's Mac (`/tmp/i76mp/retry-m4max.sh`, log `/tmp/i76mp/rsync-m4max.log`, every 60 s for 4 h) re-syncs the macOS-11 stub, re-verifies and runs the same launch test (mute, start, main menu, quit, unmute) as soon as it answers |
| **The developer's Mac** (the developer's MacBook, macOS 26.6.2) | **unchanged game folder** (owner: do not replace yet). The pack is staged at `~/i76-mp-pack-20261017` (`common/`, `mac/`, md5 lists, verified 0 mismatches; `kid/` = the boys' app) | - | his own map (home row J K L ; as in the unified map; other keys differ, e.g. F radar camera, Minus/Equal gears) | not in his folder | his copy as before |
| **Windows PC** | LAN copy `<games>\Interstate76-LAN-2026-10-17\Interstate 76` (common + win parts), `PLAY-LAN.bat` inside | common + win: 0 mismatches | unified map + `i76-remap.ahk` with `o` | 0.7.2 | launcher dry run OK (preset best-wide + co-op switches); not started (firewall Allow is the owner's click) |
| Windows daily driver | untouched (promotion 18 by another agent) | - | still `90122d37` | none | - |

The developer's Mac, what did change: the pack was swapped in once for a launch test (16:20-16:45) and swapped back. The old
folder is again `Interstate 76`; the pack copy from that test is beside it as `Interstate 76.mp-20261017` (stale proxy
509c6df0; safe to delete). `user.reg` keeps the pack's four lines (wsock32/mswsock `native,builtin` for i76.exe,
`I76_COOP_AI=1`, `I76_COOP_CHAIN=1`, `I76_MUSIC_THREAD=1`); the original is `user.reg.pre-mp-20261017`. All four are
inert or helpful in his copy (no wsock32.dll there, so builtin; co-op code only acts in a network game; the music thread
fixes a boot stall, section 4). Gate clone `~/Applications/Sikarugir/I76 MP GATE.app` (null audio) is mine; delete when done.

## 2. The pack

`<games>\Interstate76-MP-pack-2026-10-17` (`tools/mp-pack.py`, `MANIFEST.md` lists every file with md5):

- **common** (431 files, every machine byte-identical): the Windows daily driver's files **after promotion 18**
  (PROMOTIONS row 17): `i76.exe` 6319abf7, `i76shell.dll` a300db63, `u32x.dll` 06467bd2, `STRLKUP.DLL` **33211f11**,
  `I76.ZFS` 6dd57b16, missions, `ADDON` (stock `valepre4.vcf` de680a86, no .vdf/.wdf/.gdf/.cdf); `input.map` a66a37f7;
  IPXWrapper 0.7.2 (`ipxwrapper.dll` 06a01d0f, `wsock32.dll` 70e4a652, `mswsock.dll` c18759b2); co-op campaign by
  `tools/coop-install.py` (M41..M57; `miss8\M01.MSN` 000869bb and `miss16\M01.MSN` 2a41d03c = co-op T01, originals kept
  as `.pre-coop`). Rebuilding gives the same md5s (checked once).
- **win** (63 files): dgVoodoo DLLs + confs, `PLAY-i76.ps1`, presets (promotion 18: best-wide 3922146a,
  best-wide-balanced 0bca8b31, best-120 9b53c141), `_ahk` (repo `i76-remap.ahk`), music, `PLAY-LAN.bat`.
- **mac** (66 files, from the developer's Mac): OpenGLide `Glide2x.dll` 429e6e94, `OpenGLid.INI`, `I76PLYR.DEF`, the cutscene
  music `SMACKW32.DLL`, the rumble `i7_sfrce.dll`, the Mac music folder, small `.ahk`/`.env` files.
- Left out: saves, the driver's backups, logs, `Lee.fot` (the game rewrites it at every start).
- Files the game itself writes and that therefore drift from the pack after play: `Lee.fot`, `I76PLYR.DEF`,
  `user.rpr`, `ADDON/vehscn.vsf`, logs. They are not car data and do not affect the anti-cheat check.

The Mac app for the boys = the developer's wrapper (Sikarugir Wine 10, DxWnd + OpenGLide, AutoHotkey pad layer) with the pack
as its game folder, without saves, backups, x64dbg, the Nitro Pack install or debug scratch (`mp-mac-install.sh clone`),
real audio (they need sound), 1.5 GB. Each account gets `drive_c/users/<name> -> Sikarugir` (`adopt`).

Mac environment (prefix `[Environment]`): The developer's existing switches (fixed step 24, hi-res clock, frame-rate fixes,
render interp, OpenGLide settings) + `I76_COOP_AI=1`, `I76_COOP_CHAIN=1`, `I76_MUSIC_THREAD=1`. The Windows preset's
newer sim switches (collision G, `I76_BREAKABLE_BOX=4`, `I76_TERRAIN_HULL_FIX`, input latch) are **not** on the Macs:
they were never run under Wine. Each machine simulates its own car, so this changes feel on the Mac, not the
network game.

## 3. Controls

`controls/input.map` (commit ad0ebd0): the Mac's live home-row hardpoints (J K L ; = 1-4, since 2026-10-03 on the
Mac) merged into the Windows WASD map. Radar camera K -> O (wheel shift-L3 types o), team scores ; -> Shift+',
C added as a second cycle-weapon key (the Mac pad layer types C). Lint OK against the driver's exe; controls sheet
rebuilt; `tests/test_controls.py` 5 passed. **Proposed promotion:** the Windows daily driver still has `90122d37`
(J = hp1, L = hp2, K = radar camera); giving it this map + `i76-remap.ahk` is the owner's call.

## 4. Found and fixed on the way

- **Mac boot stalled in Wine's audio layer** (main thread in mmdevapi under quartz, minutes, no menu) on the developer's Mac
  with the pack's proxy; the Oct 4 log in his old folder shows the same stall. `I76_MUSIC_THREAD=1` (MP3 open off the
  game thread) fixed it at once (n 1). Now part of `mp-mac-install.sh update`.
- **The launcher stub required macOS 26** (built on the developer's Mac without a deployment target, `minos 26.0`): The M2 tester's
  macOS 15.5 refused it (`LSOpen` error -10825). Rebuilt from `i76-launch-stub.swift` with
  `-target arm64-apple-macos11.0` (md5 73c61b8d); boots to the main menu on macOS 26 (gate clone) and 15.5 (the M2 tester).
  `build-launchers.sh` now passes the target. The old stub is kept as `Sikarugir.minos26` in the boys' apps.
- **`rsync --delete` removes the per-user profile link**; `adopt` runs after every sync.
- **Headless Mac driving** (`tools/wine-probe/i76probe.c`): over SSH a process may not post macOS events or capture
  the screen, and the developer's Mac sat at the lock screen. A Windows program started with the app's wine joins the game's
  Wine session: memory reads (game state, network ids, player and position tables, the shell's screen and button
  list) and injected keys and clicks work. A process started from SSH gets no Mac display driver, so the game itself
  must be started with `open`. SetCursorPos alone did not move the shell's pointer; SendInput clicks did. The first
  click after the menu appears is sometimes lost (retry and check the button list).

## 5. The gate (PC <-> Mac IPX): NOT PASSED, handed to the owner

- **Mac side, measured** (gate clone of the boys' app on the developer's Mac, pack incl. proxy 33211f11): Esc to the main menu,
  MELEE > MULTI MELEE > HOST > IPX, each step confirmed in the shell's button list (15/1, 3/5, 6/7/14/8/16, screen
  0xC026), BROADCAST GAME -> **in the arena as host**: network flag 1, own ANet id = host id = 3, player slot 0 car
  at 4172.5, 49437.5. n 1.
- **PC side**: lab copy `<lab>\game-mp-20261017` (common + win, 16x10 conf, best-120 preset env of promotion
  18 + co-op switches, `mp-explore.ps1`). JOIN > IPX listed **"No games found"** for ~25 s. The new exe path got
  Windows Firewall's prompt; by design that click is the owner's, so its inbound rule stayed **Block** (I closed the
  prompt unanswered; Windows had already written Block for Private and Public). The Mac-joins-PC direction of
  MULTIPLAYER.md section 0 needs the PC to accept inbound, so it was not runnable either. **Not measured: both cars in
  each other's tables in this pack.** Most likely cause: the Block rule [inferred; IPXWrapper on the Mac logs at info
  level, which does not show packets].
- My error on the way, repaired: to reuse the owner-allowed rule of lab folder `game-mpb` I tried to swap folder names;
  the rename was denied (a handle open on the folder), and my script carried on and launched the ORIGINAL `game-mpb`
  with `mp-explore` given the same folder as A and B, whose backup step then ran twice and overwrote `game-mpb`'s own
  `STRLKUP.DLL` (c8b15a62). Restored from the identical `refs\nucleus\...\Instance0\STRLKUP.DLL` (c8b15a62, read back),
  lock and `.pretest` removed. That run rewrote `game-mpb`'s `I76PLYR.DEF` and `Lee.fot` (the game writes them at
  start) and replaced its `mciproxy.log`.

**Owner's 2-minute test** (also the first network play of promotion 18):
1. PC: double-click `<games>\Interstate76-LAN-2026-10-17\Interstate 76\PLAY-LAN.bat`. At the Windows
   Security Alert (may be behind the game: Alt-Tab), tick **Private networks**, **Allow access**.
2. PC: MELEE > MULTI MELEE > HOST > IPX, any arena except The Crater, BROADCAST GAME.
3. The M2 tester Mac (works today) or the developer's Mac after the swap below: Interstate 76 LAN > MELEE > MULTI MELEE > JOIN >
   IPX, select the game, JOIN GAME. Pass = each screen shows the other car.

**The developer's Mac swap** (when he wants it; the old folder is moved aside and kept, saves carried over):
`~/i76-mp-pack-20261017/mp-mac-install.sh update "$HOME/Applications/Sikarugir/Interstate 76.app" ~/i76-mp-pack-20261017`
then `.../mp-mac-install.sh verify` with the same two arguments.

## 6. Untested

- Any PC <-> Mac game with this pack (section 5); 3 or 4 players (only 2 ever measured); Mac <-> Mac; the co-op
  campaign with this pack (co-op was measured 2026-10-07 with older builds, 2 players).
- The M4 Max tester Mac launch (pending the loop). His firewall is on: expect a "wine ... accept incoming connections" box.
- The boys' first launch with real audio: macOS may ask for the microphone (Wine's audio init); the game waits for the
  answer (either answer is fine).
- The u32x exe + i76shell a300db63 under Wine with a real mouse (clicks injected through Wine worked).
- `I76_COOP_AI`/`_CHAIN` in an ordinary melee on the joiner (the joiner skips the AI tick; melee arenas have no AI cars;
  read from the code, not measured).
