# Stability lane 2026-10-24: two owner crashes

Owner's morning reports: (1) Gold, `rc-twin-20261024\PLAY.bat` (preset OWNER-2300-ALL, proxy fc6a5960 = 6b50fb9): "crashes both
times moving on to new missions"; (2) Nitro, `exp-nitro-owner\PLAY-NITRO-ALL.bat` (proxy 0c4f109c): "unhandled exception when I left
the game". Fix commit fdf07cf (main); proxy build e78aedd5 (`builds\nitro-port-20261021\stab-fdf07cf`, same bytes from the working tree
build `stab-w1`).

## 1. Gold: the crash at a mission change

**Evidence.** `rc-twin-20261024\Interstate 76\mciproxy.log` lines 86587 and 88106, two sessions: `CRASH 0xC0000005 at Strlkup.dll+0x3D3B1
reading 0x025C718C / 0x1408A18C`, frame 0, state 5, both right after the next mission's `grSstWinOpen`; the exe return 0x4039BD (the
frame hook) on the stack. `Strlkup.dll+0x48FB8` (the brief's second frame) is a stale stack slot in `trn_apply_inner`, not a caller.

**Mapping.** The RC tree `builds\rc-20261024\rc-6b50fb9-r1\src` rebuilt with `/MAP` and `/FAcs` (`builds\stability-20261024\map-6b50fb9`)
gives byte-identical fc6a5960 (the listing and the map change no code). +0x3D3B1 = `simtick_clock` + 0x931 (statics are in the map's
"Static symbols"), the inlined `wst_tick_start` leak check, simtick.c line 272:
`memcmp(g_wm[i].obj + 0x18, &g_wm[i].cur, 60)` - `mov eax, [edx]` with edx = the object's pose.

**Cause.** `g_wm` is the whole-sim tick's list of objects that moved in the last tick (raw object pointers). It was emptied only on
frames the hook sees as non-gameplay (shell, Esc menu, mission-over menu). A campaign win goes from the last gameplay frame of one
mission to the first of the next without such a frame, so the next mission's first tick read every object of the previous mission
after the game had freed them. Whether that faults depends on whether the old memory is still mapped (the bigger pools of the 2300 m
set make it likelier); Abort and Replay leave through the Esc menu and so were safe, which is why the Nitro lane's Abort / Replay
route trials (0c4f109c) passed. None of the suspects named in the brief (mirrordetail.c M16 cache / road copies, faredge, terrainmorph,
clutter alpha, shade smooth) is on the faulting path.

**Fix (simtick.c).** (1) A new mission (`[0x5a7e18] == 0`, set by simclock_Init) forgets the moving, early-pose, spawn and tracer
lists; the proxy log says `sim-tick: new mission - forgot N moving objects ...` when there was something to forget. (2) The leak check
now walks the live objects first and reads only entries still in that walk (defence for any other path that frees objects mid-mission).

## 2. Nitro: the crash when leaving the game

**Evidence.** `exp-nitro-owner\Interstate 76 Nitro Pack\mciproxy.log` line 13318 (the owner's session, `shm: default names` at 12640):
`CRASH 0xC0000005 at ntdll+0x87B71 reading 0x12310AC7`, frame 26566, state 10 (exit); exe returns 0x499B37 (HeapFree wrapper),
0x46D65A (0x46d650 free), 0x433871. The same ntdll offset and block - 1 read as the second-mission fault I76_NITRO_FONT_GUARD (04373e6)
fixed; the session's log shows that guard on (2/2 sites).

**Cause.** nitro.exe calls the font free 0x46d650 from three places, all on the mission font `[0x526a5c]`: 0x431efc and 0x433f8a (guarded)
and 0x43386c - `mov ecx, [0x526a5c]; push ecx; call 0x46d650` in WinMain's exit cleanup (0x433848: frees, then 0x46dc10(0x653b40),
0x4a1f10, 0x419b90). After a mission that pointer belongs to memory that is gone, so the exit free faults.

**Fix (nitro.c).** The guard covers the third site (`nitro-font-guard: 3/3 font free calls guarded`).

## 3. Installed (2026-10-24, no game running in each folder; the replaced DLL kept by md5)

| folder | before | now | kept as |
|---|---|---|---|
| rc-twin-20261024\Interstate 76 | fc6a5960 | e78aedd5 | STRLKUP.DLL.fc6a5960-pre-stab |
| exp-polish2\Interstate 76 | 0c4f109c | e78aedd5 | STRLKUP.DLL.0c4f109c-pre-stab |
| exp-nitro-owner\Interstate 76 Nitro Pack | 0c4f109c | e78aedd5 | strlkup.dll.0c4f109c-pre-stab |

rc-twin's PLAY.bat comment still names fc6a5960 (the RC lane's text; main coordinates the RC). The laptop bench twin was put back
to its own fc6a5960 after the runs.

## 4. Tests

**Harness.** Lab `builds\stability-20261024\tools\`: `stab-run.ps1` (a copy of tools\nitro-owner\no-run.ps1: one boot on a PRIVATE
desktop, .fps-queue / .fps-lock, I76_MUTE + the per-pid mute watcher, I76_SHM_SUFFIX = the copy's folder, restores the copy's DLL;
output `captures\stability-20261024\<tag>.*`) and `stab_side.py` (writes the game state from a gameplay frame, the way the game's
own code ends a mission: 1 won, 2 aborted, 7 replay, 0xa exit; logs state / frame / mission at 4 Hz). Copies: `stab-gold-20261024`
(rc-twin-20261024 without its superseded folders; preset OWNER-2300-ALL; dgVoodoo.wide.conf as PLAY.bat copies it) and
`stab-nitro-20261024` (exp-nitro-owner; preset OWNER-NITRO-ALL). Neither owner folder was booted.

**Which route reproduces the Gold crash headlessly.** A forced win in a direct mission boot (I76_MISSION) ends the session (no next
mission to load: the game exits cleanly, n 1), so the campaign's win -> next mission cannot be driven without the shell. Replay
written from a gameplay frame takes the same path as that win: the mission loop ends with no Esc-menu frame through the hook and the
next mission loads in the same session. The Esc menu's own Replay / Abort pass through menu frames, which already emptied the list
(why they never crashed, and why the Nitro lane's route trials passed).

| run | build | route | transitions | result |
|---|---|---|---|---|
| gold-before-win-2 | fc6a5960 (RC) | t01, win from gameplay | 1 | session ends (direct boot), no CRASH |
| gold-before-replay-1 | fc6a5960 (RC) | t01, replay from gameplay x3 | 3 | **CRASH at the 3rd: Strlkup+0x3D3B1 reading 0x0EB42F84, frame 0 state 5** - the owner's signature |
| gold-after-replay-1 | e78aedd5 (fdf07cf) | t01, replay from gameplay x5 | 5 | 0 CRASH; each load logs `sim-tick: new mission - forgot 7 moving objects` (the 7 pointers the old code would have read) |
| gold-after-replay-5 | e78aedd5 | the same, second session | 5 | 0 CRASH, 5 x `forgot 7` |
| laptop mc-gold-after-replay | e78aedd5 | the same on the laptop bench (C:\i76-benchc-twin-dgv2875, dgVoodoo 2.87.5; `laptop-benchench\mc-job.ps1`) | 5 | 0 CRASH, 5 x `forgot 7` |
| laptop mc-gold-before-replay | fc6a5960 | the same | 1 | **CRASH at the 1st: Strlkup+0x3D3B1 reading 0x14E42F84, frame 0 state 5**, exit 0xC0000005 |
| nitro-before-exit-1 | 0c4f109c | p01, exit (0xa) from gameplay | 1 | **CRASH ntdll+0x87B71 reading 0x0D1705B7, state 10, 0x433871 on the stack** - the owner's signature; the game sits in its exception box |
| nitro-before-abort-1 | 0c4f109c | p01, abort (2) from gameplay (direct boot: the session ends) | 1 | **the same CRASH** |
| nitro-after-exit-1..3 | e78aedd5 | p01, exit from gameplay | 3 boots | 0 CRASH; process gone 1 s after the write; `nitro-font-guard: 3/3`, one stale font skipped per boot |
| nitro-after-abort-1..3 | e78aedd5 | p01, abort from gameplay | 3 boots | 0 CRASH, same |
| nitro-after-replay-1 | e78aedd5 | p01, replay x3 then exit | 4 | 0 CRASH; 3 x `forgot 7 moving objects`, 4 font skips |
| nitro-after-shellexit-2 | e78aedd5 | shell (state 6), state 0xa written | - | not a route: the shell loop does not read the state (no exit, no crash). Exit Game from the shell's menu was not driven (it needs console clicks); it ends in the same WinMain exit cleanup 0x433848 as the mission routes (the loop's `cmp ebx, 0xa` at 0x43382e), so the guarded site is the one it reaches |

**Gold totals:** before (fc6a5960) 2 sessions, both crashed (at the 3rd and the 1st replay: 2 crashes in 4 transitions), the owner's
signature each time; after (e78aedd5) 3 sessions (2 desktop, 1 laptop), 15 of 15 transitions, 0 CRASH. **Nitro totals:** before
(0c4f109c) 2 of 2 exits crash; after 7 boots (3 exit, 3 abort, 1 replay x3 + exit), 0 CRASH.

Interference seen (not this lane's code): four Gold boots in `stab-gold-20261024` (gold-*-replay-2/3/4, gold-diag-1) ended 16-37 s
into the load with exit code 0xFFFFFFFF (terminated) and no CRASH record, each just before the dgv-compat lane's gate (gate-dgv.ps1 ->
gate-folder.ps1 on rc-twin-20261024, `.console-owner`) booted its next row. That gate holds the console by `.console-owner`, which
stab-run.ps1 did not honour (it took `.fps-lock` only); after it waited on both, its boots ran to the end. What terminated them was
not found (the row scripts read stop only their own folder's game). Not counted. The dgv gate rows from 10:23 ran on rc-twin with
e78aedd5 installed.

Not run: the campaign's real win -> next mission and Abort -> another mission through the menus (console routes; the owner may be at
the console, and other lanes held it). Mute: both test exes read `not muted` in Windows' per-exe store after the runs
(tools\unmute-persisted.ps1 -List; the watcher cleared each one at exit).
