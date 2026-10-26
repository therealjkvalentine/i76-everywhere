# mission (game states, loading, persistence)

**Contract.** WinMain runs the frame loop while the game state 0x4c2164 is 5. The play mode 0x4fe534 separately
gates the sim and the HUD within a mission. A mission file is walked chunk by chunk into the world, terrain, roads,
objects and script. At mission end the exe hands the outcome, the trip-scene counter and ADDONehscn.vsf (car
state and salvage) to the shell DLL, which writes .cmp and savegame.dir.

Static reading of md5 9a232dcc (2026-09-27), batch `mission-map-1` (24 names), from a reviewed read-only draft (cluster K).

## States

| var | value | meaning | set at | handled at |
|---|---|---|---|---|
| 0x4c2164 | 0 | mission failed (FSM failAll/failAllObj). Also what a cheated win becomes when the mission-over menu opens | 0x41370f (FSM failAll: 0x5244e4=0, applied by fsm_RunMachines at 0x414a0e once the clock passes 0x5244e0); 0x41373f (FSM failAllObj); 0x4977d3 (mission-over menu 0x497760 turns 0xb into 0) | 0x404326/0x4043ef: WinMain opens the mission-over menu 0x497760 (Replay / Reconfigure / Abort Mission / Exit Game) and loops at 0x404417..0x4044ab, pumping messages while the state stays 0. If the menu cannot open, the state becomes 2 (0x4044b3) |
| 0x4c2164 | 1 | mission success | 0x4136e3 (FSM successAll: 0x5244e4=1, applied at 0x414a0e after the delay); 0x40a1e6 then 0x40a14f (melee: ai_MeleeFrameTick sets 0x51f5fc=1 when bit 0x200 of the player object's +0x10 is set, and applies it after the 0x5095a8 deadline) | 0x404123..0x404142: becomes 0xb if the cheats marker 0x535f78 is set. On a plain success other than t04: 0x5dd2f0 = (mission is t12) at 0x404181, salvage_LoadMissionFsi at 0x404186, bwd2_WriteVehicleStateVsf('addon','vehscn.vsf') at 0x4041b3, shell_cb_02 RegisterFile at 0x4041c8. Then the WRLD outro movie (0x5dd310) plays through 0x49a070 (0x404265). Control returns to the shell, which gets 1 as ShellMain arg 11 and advances the trip scene (DLL 0x1001eaf0) |
| 0x4c2164 | 2 | mission aborted (Abort Mission, the abort key, or the window was closed) | 0x496837 (Abort Mission confirm page 0x496830, reached from the menu item shell_MenuReplayPageAbortMission 0x495b40); 0x44e088 (command key 0x34 in 0x44e030); 0x44e059 (network game with no world root: key 0x34 or 0x35); 0x404a19 (WndProc WM_CLOSE); 0x4044b3 (WinMain, when the mission-over menu fails to open) | 0x40432e: generic end path (graphics re-init 0x404397..0x4043ad, network 0x4524e0), then teardown from 0x404542 and back to the shell with arg11=2 (the DLL picks the post-mission flow on ==2) |
| 0x4c2164 | 3 | network game over, 10 s after the network end condition | 0x403d7c (network game: [esp+0x14] holds the time 0x453ab0 first reported the end, stored at 0x403a8a; the state becomes 3 when simclock_GetTime minus that time is at least 10.0 (0x4bc490)) | same generic end path as 2 (0x40432e); network teardown 0x4524e0 at 0x4043e5 |
| 0x4c2164 | 5 | mission running (the frame loop's condition); also the initial data value | data init 0x4c2164 = 5; 0x40318b (before the first shell); 0x404755 (Replay: reload without the shell); 0x404843 (WndProc on message 0x432, which ShellMain sends on exit: DLL 0x1001ea7a SendMessageA) | 0x40397a (the loop is entered only in state 5) and 0x4040bd (cmp [0x4c2164],5; je 0x40398d closes the loop). Any other value leaves the loop for the end-of-mission code at 0x4040cc |
| 0x4c2164 | 6 | shell running | 0x40243b (shell_RunAndGetChoice 0x4022e0, just before ShellMain; the previous value goes to ShellMain as arg 11) | WndProc 0x404bf3: while the state is 6, every message except 0x432 goes to ShellWindowProc [0x504bec] (0x404c10) |
| 0x4c2164 | 7 | replay the mission | 0x495ad6 (shell_MenuReplay, offline) | 0x404542: shell_cb_21 / shell_cb_20(-1) (CD music), then teardown. On t17 it becomes 8 (0x4046a6). Otherwise 0x4046eb..0x404769 copies the car name 0x5dcea9 to 0x5dd370 for play modes 2/3/4, sets the state to 5 and jumps to 0x40320b, reloading the same mission without the shell (also when the skip-shell dword 0x504c10 is set) |
| 0x4c2164 | 8 | reconfigure (back to the shell's garage) | 0x495af9 (shell_MenuReconfigure); 0x4046ab (Replay chosen on t17 becomes 8) | 0x4046b1: with skip-shell 0, goes to shell_RunAndGetChoice (jmp 0x4031f5, arg11=8); the DLL tests ==8 at 0x1001e585 |
| 0x4c2164 | 9 | load bookmark | 0x495949 (shell_MenuLoadBookmark) | generic end path, then the shell with arg11=9 |
| 0x4c2164 | 0xa | exit the game | 0x496817 (Exit Game confirm page 0x496810, reached from the menu item shell_MenuExitGame 0x495b10) | 0x4046bf / 0x404772 set [esp+0x18]=0xff (0x40477b), and the check at 0x40320b jumps to shutdown at 0x404788. With the skip-shell dword 0x504c10 set, every end state except 7 also exits this way |
| 0x4c2164 | 0xb | success while the cheats marker 0x535f78 is set (Play Options bits 0x1c chosen from the menu) | 0x40413c (WinMain, from 1) | 0x40432e -> 0x4043ef: handled like 0 (the mission-over menu). 0x497760 sets the state to 0 and adds a 'Turn off Cheater Options' item (handler 0x4976a0 clears bits 0x1c, rewrites I76PLYR.DEF and clears 0x535f78). A cheated win therefore gets no .fsi salvage, no vehscn.vsf and no scene advance |
| 0x4fe534 | 1 | play mode: normal driving (the sim runs and the HUD is drawn) | 0x49cdca (0x49cdc0, called at 0x403201 after every shell return; also sets the return mode 0x4fe538=1); 0x49cddb (0x49cdd0 toggles back to 1); 0x49ce5a (leaving the map); 0x49d080 / 0x49d17d (unpause) | 0x4039ec: a sim frame runs only when the app is active (0x504c1c) and mode&0x3e==0 (offline). 0x403e78: the HUD / renderer_DrawMask is drawn only in mode 1 |
| 0x4fe534 | 2 | paused (offline only); 0x4fe538 holds the mode to return to | 0x49d1bd (the 0x49d140 toggle: from fsm_IsKeypress 0x44dea0, command key 0x33 at 0x44e0ed, and WndProc key code 0x1ff at 0x40488d); 0x49d0d2 (0x49d000, command 0x33 in mode 2) | 0x4039ec -> 0x40402f: no sim; only the mode key handler 0x49d000 and the message pump run |
| 0x4fe534 | 4 | map screen (map image named by the mission at 0x5a7ec8; plays cmap2.wav / gdsgc26.wav) | 0x49cfef (the 0x49cdf0 toggle, from input_ApplyToEntity 0x44f64e and 0x49d0f5) | 0x403e3d: test 0xc skips the 3D world draw; the sim is frozen offline as for 2 |
| 0x4fe534 | 8 | notepad / objectives screen ('cnote.wav', 'ZNPD%1d01.map') | 0x45e762 (0x45e2b0 toggles 8 through 0x49cdd0; called from input_ApplyToEntity 0x44f665 and 0x49d112) | 0x403e3d, as for 4 |
| 0x4fe534 | 0x10 | in-game menu (the options menu or the mission-over menu) | 0x49515a (0x495070 opens the options menu; command 0x22 at 0x44e0c8); 0x497897 (mission-over menu 0x497760) | 0x403ebf: 0x496870 draws the menu. 0x49d020: in mode 0x10, 0x49d000 runs the menu frame 0x496e10. 0x495170 closes the menu (0x4952a4 sets mode 1) |
| 0x4fe534 | 0x20 | in-mission cutscene movie (cutscene\*.smk through smackw32) | 0x49a42c (0x49a070, e.g. the WRLD intro movie 0x5dd300 at 0x40371c and the outro 0x5dd310 at 0x404265) | 0x403758 / 0x403f05 / 0x40403c / 0x40429b / 0x404429: in mode 0x20 WinMain calls 0x49a670 (the movie frame) instead of shell_cb_10. WndProc 0x4048b7: Esc (0x1b) calls 0x49a9f0 to end the movie (mode 1 at 0x49aa2a) |

## Load order

- WinMain 0x4034da: world_ParseMissionCode(0x5049f0). At 0x4034c5/0x4034cf, 0x5dd2f4 = 1 for t01/t13/t17 (training missions get the 5-item mission-over menu)
- 0x4034f4 bwd2_LoadMissionFile(0x5049f0): 0x4b42b9 calls object_InstallShadowReleaseHook 0x4b84e0 (re-registered every mission; 0x457100 cleared the hook arrays at 0x403256). Mission number 0x6562c0 and type 0x6562c4 come from the name (m/n 1, t 2 trip, s/p 3). 0x4b43ea calls vfs_ResolveFilePath 0x4b2d50, then 0x46ffc0 loads the file
- pass 1, table 0x500328 (2 entries): BWD2 -> 0x4b8960 (no-op), REV -> 0x4b4610 (revision check, msn = 2)
- pass 2, table 0x500348 (7 entries, flags 0x2006). Chunks are handled in file order; the stock order is REV WDEF TDEF RDEF ODEF LDEF ADEF EXIT:
- WDEF 0x4b4550 -> bwd2_ParseWdef 0x4b89e0 (table 0x500ca0): WREV 0x4b4610; WRLD bwd2_h_WRLD_4b8a10 (movies, palette, sky, map, objectives .npt, hour, surfaces, far clip); EXIT 0x4b4290
- TDEF 0x4b4570 -> bwd2_ParseTdef 0x493910 (table 0x4fae18): first clears the 80x80 zone grid 0x5a4768 to -1 and zeroes 0x5a4628[0x50]. TREV; ZMAP bwd2_h_ZMAP_493960 (zone count 0x5a4620, grid copy, index check); ZONE bwd2_h_ZONE_4939d0 (.ter, addon\ first); EXIT bwd2_h_EXIT_493bd0 = 0x493080(1, options_terrain_resolution 0x654b87, 5.0), which builds the terrain
- RDEF 0x4b4590 -> bwd2_ParseRdef 0x4b8750 (table 0x500cd0): RREV; RSEG bwd2_h_RSEG_4b8780; ISEG/TSEG 0x4b8960 (ignored); EXIT
- ODEF 0x4b45b0 -> bwd2_ParseOdef 0x4b7a90 (table 0x500ae8): OREV, then OBJ bwd2_h_OBJ_4b7ac0 per object. Class 1 'spawn'/'regen' -> 0x450f90 (network spawn/regen point, no object). Class 1/8/9 -> 0x4b8230 builds the object and 0x4ad6f0 loads its .vcf. Scenery classes 2/3/4/7/0xa/0xb/0xc/0x50/0x52/0x53 -> 0x4b8230 plus bwd2_LoadDef(.sdf, table 0x500b18). Then, except for 0x50/0x52/0x53, 0x4572b0 registers the entity (running the register hooks at 0x54a188) and 0x457610 inserts the 8-byte label -> object into the table 0x54a178 (the FSM entity key). Classes 0x50/0x52/0x53 are merged into the parent's transform instead
- LDEF 0x4b45d0 -> bwd2_ParseLdef 0x4b8f40 (table 0x500d80): LREV; OBJ bwd2_h_OBJ_4b8f70 (fence and tyre strings); EXIT
- ADEF 0x4b45f0 -> bwd2_ParseAdef 0x4b89b0 (table 0x500d20): AREV; FSM bwd2_h_FSM_409740 (the script; its labels resolve through 0x54a178); EXIT
- top-level EXIT 0x4b4790: reports an error if 0x401320() == 0 and world_GetRoot() == 0 (no player object); returns 1
- back in WinMain: 0x4034fc 0x45dea0, 0x403501 0x45f520, 0x403506 object_RunPendingInits 0x461b80, 0x403510 entity_AddUnregisterHook(0x4093e0), the sound tables, 0x403598 0x48e1a0(mission name), the intro movie at 0x40371c, graphics init, camera_ApplyViewOptions at 0x403955, then the frame loop at 0x40398f while 0x4c2164 == 5

## Persistence (exe side)

- player_SaveDef 0x497290 writes 0x60 bytes from 0x654b40 to I76PLYR.DEF (fopen 0x49729b, fwrite 0x4972b4). This is the OPTIONS block, not campaign progress: 0x654b80 video mode, 0x654b81..0x654b93 detail and sound options, 0x654b98 options_play_flags, 0x654b9c difficulty (symbols/globals.tsv). It is called at mission end (0x4040f7) and after the graphics-mode cycle key (0x44e3a1). 0x4970f0 reads the file back after every shell return (0x403206) and clears the cheats marker 0x535f78 (0x49724a). The 'Turn off Cheater Options' handler 0x4976a0 writes the same file inline (0x4976c6 / 0x4976e1)
- player_LookupById 0x4547c0 is not persistence. It searches the 16-entry network player table 0x541070 (stride 0x48) for a u16 id at +0 and returns the dword at +0x28 (the player's object; 'No vehicle sent for player %d' is logged at 0x4511cf just before the call at 0x4511dd), or 0
- Salvage list 0x5dabc4: singly linked category nodes (0xc bytes: +0 next, +4 part list, +8 category: 0 wheel/.wdf, 1 weapon/.gdf, 2 eng, 3 sus, 4 bra, 5 spc) and part nodes (0x1c bytes: +0 next, +4 name[16], +0x14 amount, +0x18 source flag). Filled during the mission by salvage_CollectFromWreck 0x4b1610 (amount = the record count, flag 0) and fsm_Salvage 0x40c040 (amount -1, flag 1), and at success by salvage_LoadMissionFsi 0x4b1a20 (amount -1, flag 1). Play Options bit 2 (no salvage management) turns all of it off. salvage_FreeAll 0x4b19d0 frees the list at teardown (0x40457d)
- What a destroyed car yields: entity_DamageAndKill (0x464109), 0x464890 (at 0x464bbd) and entity_Wreck (0x4664c2) call salvage_CollectFromWreck(object) right after setting the wrecked flags 0x80008000 in entity+0x454, unless object_IsPlayer. It exports the car with entity_ExportVehicleRecords 0x4b10e0 into 64 records of 0x60 bytes. Every record with count > 0 whose 8-byte name at +0x18 is not 'null' becomes a part: records 0-5 as .wdf wheels, 10-16 as .gdf weapons, the others with no extension (eng/sus/bra/spc by name prefix)
- Tier gating: salvage_AddPart 0x4b16e0 passes each part through salvage_ClampPartTier 0x4b1cb0, using the per-category tier tables at 0x4ffc28 (rows of 0x1c bytes: name, trip minimum +0x10, scenario minimum +0x14, always-available +0x18). A part above what mission 0x6562c0+1 allows is replaced by the highest allowed lower tier (tier 1 is always available). Names not in a table are dropped. Wheels are renamed 'wauto_0' plus the tier letter
- Mission end, success only (not t04, not a cheated win): salvage_LoadMissionFsi adds the parts listed in <mission>.fsi. Then bwd2_WriteVehicleStateVsf 0x4b06b0('addon','vehscn.vsf'), for trip missions only (0x6562c4 == 2), runs salvage_PruneRandom 0x4b1b90 (per category it keeps 4 wheels, 1 special, and 1-3 of the rest at random) and writes the BWD2 file ADDON\vehscn.vsf: header (bwd2_WriteHeader 0x4b4840, rev 2), VCST (0x4c bytes, holds 'vehscn.vcf'), WLST (0x18), WPST (12 bytes per fitted slot, from entity_ExportVehicleRecords on the player), SALV (0x18 per salvage part: name[16], amount, flag), and EXIT with an 8-byte body. SALV and EXIT are skipped when 0x5dd2f0 (mission t12) is set. shell_cb_02 RegisterFile (0x4041c8) then adds the file to the exe's file index
- What the exe hands the DLL: ShellMain arg 11 = the old 0x4c2164 (the outcome; the DLL advances the trip scene only when it is 1, 0x1001eaf0); arg 7 = &0x4c2160 (the trip scene number, data init 1, incremented by the DLL at 0x1001eafc and used for t%2.2d.msn); arg 10 = the WinMain setup block at esp+0x25c (+0x5d mission file, copied to 0x5049f0 at 0x403419); the player block 0x5dce80 (+0x20 = 0x5dcea0 play mode, +0x29 = 0x5dcea9 car file); and the file ADDON\vehscn.vsf. The .cmp files and savegame.dir are written by i76shell.dll

## Notes

Code outside functions.tsv (functions must be created before rows can land): the main WndProc 0x404830 (msg 0x432 -> state 5 at 0x404843; WM_CLOSE -> state 2 at 0x404a19; in state 6 it forwards to ShellWindowProc; pause and Esc keys), and the in-game menu pages 0x496810 (Exit Game confirm, state 0xa), 0x496830 (Abort Mission confirm, state 2) and 0x4976a0 (Turn off Cheater Options). Because they are not functions, the callgraph misses them as callers of shell_SetGameState. Death has no state of its own. The player's death reaches the outcome through the mission script (failAll/failAllObj; the getdown cheat makes it a success) or, in melee, through ai_MeleeFrameTick (object+0x10 bit 0x200 -> outcome 1). 0xb is not a variant of success. WinMain routes it to the mission-over menu, which turns it into 0 and offers 'Turn off Cheater Options'. A cheated win earns no .fsi salvage, writes no vehscn.vsf, and does not advance the scene (the DLL advances only on arg11 == 1). The exe keeps no campaign progress file of its own: I76PLYR.DEF is the options block, player_LookupById is a network lookup, and the scene number 0x4c2160 lives in exe memory while the DLL saves it. Provisional prefix: the play-mode helpers (0x49cdc0, 0x49cdd0, 0x49d140, 0x49d000, 0x49cdf0) use 'startup' (WinMain scope) because VOCABULARY.md has no mode/game prefix; rename them if a row is added. 0x497760 uses shell_ because the other in-exe menu handlers (shell_MenuReplay etc.) already carry it. Not verified live: the tier-gating semantics (the table values look right: tier 1 always available, rising minimums) and the contents of WLST/VCST. Housekeeping: temporary scratch files (callers.py, winmain.asm, winmain_n.asm, wndproc.asm) were written during analysis and deleted afterwards; if a callers.py existed in the scratchpad before this run, it was overwritten.

## Found in wave 5 (static, 2026-09-27)

- **Object-label table bug.** `entity_LabelMapInsert` 0x4ad450 (via `entity_AddLabel` 0x457610; record 0x54a178 =
  heap, table, count, capacity; start capacity 0x800 from `heap_Create` 0x4ad410) grows the table on a path where
  everything is wrong:
  - it sizes the block with the CRT's `_msize` on a private-heap block;
  - a successful HeapReAlloc returns 0 and drops the new pointer, so the table may dangle;
  - a failed one zeroes the table pointer and writes through it.
  Stock T01 registers 88 labels, far below 2048. The opt-in proxy fix `I76_FIX_LABEL_TABLE` is verified with the
  start capacity forced to 16: it grew to 272 and kept all 88.
- **Cheat-confirm dialog.** Turning on a Play Options cheat asks "I'm a cheater" / "I'm a swinger" (menu page
  0x4fd018, plyopt1.map, Esc disabled). The exit dialog is 0x4fcec0 (extgme1.map). The code number on menu pages is
  (level + 900) x 1000 + rand() % 992, rerolled per level (0x496870).
- **Campaign act** 0x4fe520 (1..5) comes from the mission code through the table 0x4fe430 (letter, number, act).
- **Multi-car melee** reads MULTICAR.def (match_*, range-s-1). Melee kill score = victim mass / player mass x 1000.

## Player car in scripted missions (static, md5 9a232dcc, 2026-09-27, gap sound-mission)

- **Car name** 0x5dd370. WinMain seeds 'vppirna1' (0x402d25 / 0x402d45). After each shell return,
  `shell_RunAndGetChoice` 0x4022e0 switches on the shell play mode 0x5dcea0 (0x4024de):
  - 5 network: sprintf("%s%s", setup+0x4e, ".vcf") (0x402509);
  - 2 trip / 4 scenario: a copy of 0x5dcea9 (0x402552..0x402566 / 0x402583..0x402597);
  - 3 auto melee: `match_SetMultiMelee(1)` (0x40257b), then the copy;
  - anything else keeps the previous car. A mission entered without the shell therefore drives vppirna1.

  Replay (state 7) repeats the copy for modes 2/3/4 (0x40470e..0x40473f). The shell's 0x5dcea9 is the player's car file,
  'vehscn.vcf' in a trip (shell/CALLBACKS.md).
- **ODEF.** `bwd2_h_OBJ` 0x4b7ac0 builds each class 1/8/9 object (0x4b7b9d), copies objFlags (ODEF +0x60) to
  object+0x10 (0x4b82c0 / 0x4b82cb), then calls `bwd2_LoadVcfForObject` 0x4ad6f0 (0x4b7bdc) with the mission's
  '<name>.vcf'.
- **Substitution** (0x4ad6f0):
  - If `object_IsPlayer` (objFlags bit 0x10, 0x4ad71e) and the override 0x5dabc0 is 0 (0x4ad730), the file is
    basename(0x5dd370) + '.vcf' (0x4ad755..0x4ad76a), and the object's 8-byte name becomes that basename
    (strncpy 0x4ad764).
  - So the player's ODEF entry gives only position, orientation and flags; its vcf is never loaded.
  - FSM labels come from the ODEF record (0x457610 in bwd2_h_OBJ), so scripts keep the mission label.
  - The one reference to 0x5dabc0 in .text is that read, so stock code never uses the mission's car for the player.
    Every other vehicle uses the mission's vcf.
- **State file.** After the VCFC load (0x4ad7cd), and only in trip missions (0x6562c4 == 2, 0x4ad7dd), '<basename>.vsf' is
  loaded if it exists (0x4ad864), with the table 0x4ff330 (0x4ad87d): VCST 0x4b0350, WLST 0x4b0540, WPST 0x4b0610, SALV (no
  handler), EXIT.
  - The test runs for every vehicle in a trip; in practice only vehscn has a .vsf.
  - Scenario, melee and network cars load fresh.
- **Carried over** (VCST body offsets):
  - The name is checked against the object (0x4b03a7). A mismatch only logs 'State file %s calls for %s...' (0x4b03cc)
    and applies the state anyway.
  - armour[4] body+0xd -> entity+0x138 and +0x158 (0x4b0414 / 0x4b0434).
  - chassis[4] body+0x1d -> +0x148 and +0x168 (0x4b0457 / 0x4b0475).
  - Engine hp body+0x3d, brakes hp body+0x41 (brake+4), suspension hp body+0x45 (0x4b04a0 / 0x4b04a9).
  - Velocity body+0x2d -> +0xbc, with |v| -> +0xac (0x4b04b4 / 0x4b04fc); body+0x39 -> object+0x48 (height, 0x4b050e).
  - WLST: the hp of the six wheels (0x4b054e..0x4b05c1).
  - WPST: `weapon_RestoreMountState`(obj, slot, rec+8, rec+4) (0x4b0627). The weapon field at 0x5aab14 gets rec+4, and
    0x5aab28 gets rec+8 unless it is -1.
- **Not carried by the exe:**
  - salvage: SALV has no load handler; the shell owns it;
  - the fit (weapons and parts): it comes from the vcf the shell writes;
  - export records 17-19: written to VCST +0x49..+0x4b (0x4b08b2..0x4b08ca) and never read.
- **Writer quirks** (`bwd2_WriteVehicleStateVsf` 0x4b06b0):
  - VCST is zero-filled (0x4b06ec), then fed from the export records through a jump table (0x4b084b):
    - 0-5: WLST;
    - 7 / 8 / 9: body+0x3d / +0x45 / +0x41;
    - 10-16: WPST (skipped when named 'null' with count 0);
    - 64 and 80: through two pointers that both start at body+0xd (0x4b082b / 0x4b082f).
  - Nothing writes velocity, body+0x39 or chassis. A car reloaded from an exe-written file would get v = 0, height 0.0
    and chassis 0 unless the shell rewrites the file (open).
