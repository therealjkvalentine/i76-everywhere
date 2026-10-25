# Mac converge 2026-10-20: one app per Mac, sound, AI cars, the Esc menu

Owner (verbatim, 2026-10-20 evening): *"there's no sound on i76 MP Gate on my laptop, no ai cars spawn when i enter multi
melee, and the mouse and keyboard don't work on the game pause menu correctly. i'd like to clean up all the other/old
versions on the mac: we'll converge towards one where everything works, and i don't need to protect a daily driver besides
the windows one for now. multiplayer menu simplification looks great now though."*

Machines: The developer's laptop (the family Mac over ssh), the M2 tester Mac (the family Mac over ssh), the M4 Max tester Mac
(the family Mac over ssh), all through the laptop hop. Times CDT. n = launches / clicks / boots as stated per row.
Evidence: lab `captures\mac-converge-20261020\<machine>\` (manifest-before / manifest-after: path, size, md5 of every
STRLKUP.DLL / i76.exe / i76shell.dll / u32x.dll / launcher / user.reg / dxwnd.ini; the laptop GATE app's registry, DxWnd profile
and proxy log as the owner left them; Esc-menu page dumps; host-form pictures), PC check `captures\mac-converge-20261020\pc*\`.
Lab tools: `tools\mac-converge\` (manifest.sh, build-final.sh, build-lab-at.sh, pccheck.py). Pack delta: lab
`builds\mp-pack-20261020-macconv\` (= `mp-pack-20261020-polish` with `STRLKUP.DLL` cf4f81da -> **0ce90a90**).

## 0. Result

| symptom | cause | fix | evidence |
|---|---|---|---|
| no sound in `I76 MP GATE.app` (laptop) | the gate clone was made with Wine's audio driver switched off (`[Software\Wine\Drivers] "Audio"=""` in its `user.reg`; GAME-NIGHT-ROLLOUT-2026-10-17 s.1: "Gate clone ... (null audio)"). The proxy's mute probe in that app: `mute: no default render endpoint for role 0/1 (hr 0x80070490)`, 35 / 36 times | the GATE app is gone; the pack now runs in the owner's own `Interstate 76.app`, whose prefix has CoreAudio (no `Audio` override; DirectSound "MacBook Pro Speakers" enumerated) | converged app, muted launch: `mute: session muted = 1 (... 2/2 endpoint role(s) read back muted)` (n 1); unmuted launch: coreaudiod's `BuiltInSpeakerDevice` IO assertion appears with the game (none before it), menu music `PLAY track 13` (n 1). The M2 tester's / the M4 Max tester's: 2/2 endpoints (n 1 each) |
| no AI cars in MULTI MELEE | the owner hosted **stock** arenas: the GATE log's last session hosted `m01.msn` (The Crater) then `m08.msn` (Creeper Canyon, `user.mel`), 1 player, `mission cars alive 0`. Stock arenas have no AI by design; the AI fill is only in **Hope Springs (2 / 4 / 6 AI)** (`ai_*.lvl`). The launch switches were present (`I76_COOP_AI=1`, `I76_COOP_CHAIN=1`, `I76_MP_MENU` default 1) | none needed; the owner's sheet says which arenas have AI (OWNER-TEST-LIST) | hosting Hope Springs (4 AI): `mpfill: ... host, ai_hs4.lvl, humans 1, tagged 4: in play 4` + `aimelee: ... 4/4 alive`, every AI targeting the host (`->0`) - laptop n 1 (converged app), the M2 tester's n 1 |
| Esc menu: mouse | **measured**: under DxWnd the click position that reaches the menu's hit-test (0x4972d0) stops at about window x 800 / y 560-600. Its lParam leaves the exe's u32x `PeekMessageA` already clamped to (639, 479) and DxWnd's window layer then scales it again ((639,479) -> (354,318) on a 1440x900 window). Rows lower than UI y ~320 or right of x ~355 cannot be hit, Cancel / Back never (the M2 tester Mac 0 of 61 clicks, laptop 0 of 3), and a click below the last reachable row lands on that row instead | proxy **I76_MENU_PTR** (`music-fix/escmenu.c`, ae48dd8): the two calls into 0x4972d0 take the exe's own GetCursorPos read (u32x, the read the shell's working pointer uses) instead of the lParam; on only when `dxwnd.dll` is in the game | section 3: The M2 tester Mac Cancel 4 / 4, Play Options rows 4-6 where drawn, row edges exact (n 11 + 5); laptop and the M4 Max tester's: `2 / 2 call sites repointed, read back OK` (n 1 each). Laptop clicks after the fix: **not measured** (screen locked) |
| Esc menu: keyboard | not reproduced: Up / Down (plain and extended, as a real arrow key sends), Tab, Enter, Esc move and pick rows on the M2 tester Mac (n 14) and the laptop (n 3, locked screen, keys reach the game). The menu ignores keys while a mouse press is "armed" on a row (0x654b1c, cleared by the button-up) and its starting row is the last one used (stock) | - | the owner's real keyboard is the open check |
| one app per Mac | laptop: 7 I'76 apps (GATE, IPX TEST, SETUP TEST, TEST, Software-renderer backup, the owner's own, Nitro + DxWnd Settings launchers); the boys: 4 old game folders inside the app | section 4 | after-manifests |

## 1. Diagnosis on the laptop (17:15-17:35)

- The owner was playing when the lane started: `I76 MP GATE.app` (17:07), then his own `Interstate 76.app` (17:20-17:45); the
  lane only read files until he stopped.
- **Sound.** GATE's `user.reg`: `[Software\\Wine\\Drivers] "Audio"=""` (Wine's null driver) and no DirectSound devices
  under `ActiveMovie\devenum`; the owner's own app: no override, DirectSound "MacBook Pro Speakers" / "Microsoft Teams Audio".
  The env blocks of the two prefixes are identical except `I76_SKIP_MOVIES=1` in GATE (a lane switch). DxWnd profiles
  identical (444770ce).
- **AI.** The proxy log's mission per session: sessions 17-22 joined other hosts' `ai_hs4.lvl` / `coop05.lvl` / `auto04.lvl`
  with AI on screen; the owner's own session 24 hosted `m01.msn` and `m08.msn` alone.
- **Esc menu, before the fix (proxy cf4f81da), the M2 tester Mac** (1440x900 window = the screen, unlocked; game hosting
  Suburbia alone): page `mainmn1.map` at 172..468 x 27..452, items: four rows x 193..468 (y 111-135, 157-181, 180-204,
  203-227) and Cancel 401..461 x 434..453 (`captures\...\m2\escmenu-pages.txt` has all four pages). A click selects /
  activates a row only in a window band x >= 436 (= UI 193, the stretched map) and y 214..250 (row 0: UI 114-133); clicks at
  x 1050..1439 still hit the rows (UI up to 640 would miss the page: the x is clamped); Play Options rows probed with a
  button-down only (no setting changed): window y 560, 650, 740, 800, 840 all selected row 4. The first build's log
  (`I76_MENU_PTR_LOG=1`) gave the reason: `msg 0x201 lParam (639,479) -> ...; real pointer 555,560, client 800x600 as the game
  sees it` for a click at window (1000, 840). Keys: plain and extended Down / Up / Tab / Enter / Esc all move or pick (n 14).
- The cursor map / u32x menu map / pad menu of the brief's hypothesis: the Macs never set `I76_CURSOR_MAP` / `I76_PAD_MENU`
  (their `[Environment]` has neither), and the pack's exe imports `u32x.dll`, whose slots DxWnd leaves alone (the exe's
  `PeekMessageA` / `GetCursorPos` slots were still u32x's at the shell). So nothing there failed to attach; the clamp is in the
  message path itself.

## 2. Build and PC check

- Source: i76-everywhere **ae48dd8** (`music-fix/escmenu.c` + two lines in `strlkproxy.c`; probe `xkey` / `pmsg`). The Mac pack
  proxy is the deployed source plus only this: commit object 87ba566 = d249380 + those two files' changes (not on a branch;
  the archived source is `builds\mac-converge-20261020\final\wt`). MSVC x86 /MT /O2 /Brepro, built twice byte-identical
  (`final\b1|b2`): **0ce90a90**. Lab twin (+ I76_LAB_SHELLCLICK, for the headless PC check only): 1c8119a0.
- **PC path unchanged** (`tools\mac-converge\pccheck.py`, lab copy `exp-mac` = the PC LAN copy, private desktop, I76_MUTE=1 +
  per-pid mute watcher, I76_SHM_SUFFIX=exp-mac; each boot waited for the foreign games of other lanes to end):
  run 1 (`pc\`, the pack build 0ce90a90 itself): in 3 of 3 boots the two 0x4972d0 call sites read their stock bytes (`e8 7f 27 09 00` at 0x404b4c, `e8 42 27 09 00` at 0x404b89), `mp-menu: skip ... patched, read back OK` through the LoadLibraryA hook (the PC route), 0 crash lines, persisted mute not set. A headless pack build cannot leave the intro (it has no lab click path), so the thread's `menu-ptr: auto - no DxWnd in this game: off` line (written once the shell is up) was not reached; run 3 (`pc3\`, the lab twin 1c8119a0, which can reach the main menu) reached the main menu in 3 of 3 boots and logged `menu-ptr: auto - no DxWnd in this game: off (the PC path)` each time, call sites stock, mp-menu patched through the hook, 0 crash lines (19:06). Order, honestly: the Macs got 0ce90a90 between 18:40 and 19:05, after run 1's call-site result and before run 3's log-line result; run 3 then passed. The PC LAN copy itself was not changed.

## 3. The Esc-menu fix, measured

| check (the M2 tester Mac, test build 6760d485 = the same escmenu.c on HEAD) | result | n |
|---|---|---|
| attach | `menu-ptr: Esc-menu clicks take the pointer from i76.exe's GetCursorPos slot (u32x.dll 79FF1270): 2 / 2 call sites repointed, read back OK` | 2 boots |
| Cancel clicked where drawn (window 1000,840 / 950,830 / 1030,820 / 920,845) | menu closes, mode 0x10 -> 0x1 | 4 / 4 |
| just outside Cancel (UI y 433 above, 464 below) | no action | 2 / 2 |
| Play Options, button-down only, window y 230 / 400 / 470 / 560 / 650 / 740 / 800 | rows 0 / 2 / 3 / 4 / 5 / 6 / 6 (6 = 387-411, 800 = UI 426 is in its value box) | 7 |
| row x edges at window y 650: x 300 / 440 / 1050 / 1200 (UI 133 / 195 / 466 / 533) | miss / hit / hit / miss | 4 |
| keys after the fix: extended Down x2, Up, Tab, Enter, Esc | rows 0-1-0-1, Enter opens Play Options, Esc closes | 6 |
| laptop (converged app, 0ce90a90) | attach line as above; keys move the rows (screen locked: n 3); clicks not measurable while locked | 1 boot |
| The M4 Max tester Mac (0ce90a90) | attach line as above (screen locked) | 1 boot |

## 4. Convergence

**Laptop.** The pack went into the owner's own `~/Applications/Sikarugir/Interstate 76.app` (MULTIPLAYER.md section 8 and
GAME-NIGHT-ROLLOUT-2026-10-17 s.5 planned this; it keeps the app's CoreAudio prefix, its wine binary and the macOS answers
tied to it, his saves, and the `Interstate 76 Nitro (DxWnd).app` and `Interstate 76 - DxWnd Settings.app` launchers, both of
which point into this app's prefix): his game folder was moved aside, GATE's verified pack folder cloned in (`cp -c`), his
`savegame.dir` and 18 `saveNNN.cmp` carried over, the pack's `input.map` / `I76PLYR.DEF` kept (the ones he played MP with),
472 pack files verified (0 mismatches after `histogram.txt` was put back), then 0ce90a90 applied (408 common files, 0
mismatches). The prefix's `user.reg` already had every pack line (2026-10-17: wsock32 / mswsock overrides, I76_COOP_AI,
I76_COOP_CHAIN, I76_MUSIC_THREAD).

| | before | after |
|---|---|---|
| I'76 apps | `I76 MP GATE.app` (pack, cf4f81da, null audio), `Interstate 76.app` (own lineage: i76.exe f92b8a7e, i76shell 8960fa16, STRLKUP ae866ec5; + `Interstate 76.mp-20261017` 509c6df0, + Nitro Pack), `I76 IPX TEST.app` (834ce774), `I76 SETUP TEST.app` (482563b9), `Interstate 76 TEST.app` (ae866ec5), `Interstate 76 - Software-renderer backup 2026-10-04.app` (e5951e0f), Nitro + DxWnd Settings launchers | **`Interstate 76.app`**: i76.exe 6319abf7, i76shell a300db63, u32x 06467bd2, **STRLKUP 0ce90a90**, launcher 565c4bd9 (his own), dxwnd.ini 444770ce; Nitro Pack folder kept in its prefix; Nitro + DxWnd Settings launchers kept |
| deleted | | GATE, IPX TEST, SETUP TEST, TEST, Software-renderer backup apps; `Interstate 76.mp-20261017` and his old game folder (in the tarball); `~/i76-mp-pack-20261017`; `~/i76-overnight-20261020` except `deck-polish/` (the Deck lane's `deck-stop-loop.sh` still runs from it, pid 61885, not this lane's) |
| kept | | `~/i76-archive-20261020/Interstate76-app-before-converge-20261020.tgz` (1.21 GB, md5 d2ea5790; the owner's app before the swap, without the stale `.mp-20261017` folder), `STRLKUP-cf4f81da.dll`; evidence copy of GATE's user.reg / dxwnd.ini / logs in lab captures |

**The M2 tester Mac** and **The M4 Max tester Mac** (`~/Games/Interstate76-MP/Interstate 76.app`, Desktop link `Interstate 76 LAN` -> that
app, unchanged): the old folders inside the app (`Interstate 76-pre-20261020` 533ab67c lineage, `-pre-teams-20261020`,
`-pre-polish-20261020`, `lan-pack-pre-20261018`), the M2 tester's `~/Games/Interstate76-MP/pointer-fix-pre-20261018` and empty
`~/i76-everywhere`, and `~/i76-overnight-20261020` deleted; the 2026-10-17 pack tools beside the app (`common.md5`, `mac.md5`,
`mp-mac-install.sh`) moved to `~/i76-archive-20261020/old-pack-tools/`. One tarball each: `~/i76-archive-20261020/Interstate76-app-before-converge-20261020.tgz`
(the app without the old folders; the M2 tester 847 MB md5 10db8c97, the M4 Max tester 846 MB md5 a08aefe9), plus `STRLKUP-cf4f81da.dll`.

| machine | STRLKUP before | after | i76.exe / i76shell / u32x | pack verify |
|---|---|---|---|---|
| laptop | GATE cf4f81da / own ae866ec5 | 0ce90a90 | 6319abf7 / a300db63 / 06467bd2 | 408 common files, 0 mismatches |
| The M2 tester Mac | cf4f81da | 0ce90a90 (attach line n 1 at 19:05; the M2 tester was using the Mac again, so the game was stopped after the boot) | 6319abf7 / a300db63 / 06467bd2 | 408 common files, 0 mismatches |
| The M4 Max tester Mac | cf4f81da | 0ce90a90 | 6319abf7 / a300db63 / 06467bd2 | 408 common files, 0 mismatches |
| PC LAN copy | cf4f81da | cf4f81da (unchanged; 0ce90a90 behaves the same without DxWnd, section 2) | | |

Rollback on a Mac: `cp ~/i76-archive-20261020/STRLKUP-cf4f81da.dll "<game folder>/STRLKUP.DLL"` (proxy only), or extract
the tarball in place of the app (`tar -xzf ~/i76-archive-20261020/Interstate76-app-before-converge-20261020.tgz` in the app's
parent folder, game closed).

## 5. Open

- **The laptop's Esc menu with the owner's mouse** after the fix (the screen locked at ~18:40, so no click reached the game),
  and his keyboard there: OWNER-TEST-LIST "Mac converge" item 1.
- **Hosting with AI on the laptop: n 1 of the 2 asked** (the second launch came after the lock); the M4 Max tester's host census: not
  measurable (locked all evening; clicks do not reach a locked Mac).
- **Cross-machine join with the PC LAN copy hosting**: not run (the M2 tester Mac asleep from ~18:58, the M4 Max tester's and the laptop
  locked; a Mac joiner needs clicks).
- Stock arenas have no AI cars. Whether MULTI MELEE should offer AI in every arena is the owner's call.
- The PC LAN copy keeps cf4f81da (the pack's other files are identical); it can take 0ce90a90 at the next PC rollout.
- `~/i76-overnight-20261020/deck-polish/` on the laptop: delete once the Deck lane's loop has ended (14 h from 16:20).
- Lab copy `exp-mac` deleted after its logs went to `captures\mac-converge-20261020\pc-expmac\`, except `Lee_____.ttf`
  (held open by Windows since the game registered the font; delete the folder after the next sign-out).
