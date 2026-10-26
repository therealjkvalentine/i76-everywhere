# The ShellMain interface from both sides: 13 arguments and 27 callbacks

DLL: pristine `i76shell.dll` deb41008…; exe: `i76.exe` 9a232dcc…. The exe half (what each callback does) is in
`work\exe-callbacks.md`, written by a read-only helper agent against the main export and checked here where it
touches the DLL. The DLL half (who calls what, with what) is `tools\cbsites.py`: a capstone linear sweep of the
DLL `.text` that pairs every `mov R,[0x10058198]` with the following `call [R+4n]` (92 table loads, all paired).

## ShellMain (export 0x1001e260) — `int __stdcall ShellMain(13 args)`, `ret 0x34` at 0x1001ec1e

Stack layout at 0x1001e2aa: return address at esp+0x50, so arg k = [esp+0x50+4k]. Each arg is listed with its DLL store and its exe source (call at 0x4023xx in 0x4022e0).

| # | exe passes | DLL stores to | DLL use |
|---|---|---|---|
| 1 | HMODULE of I76SHELL.DLL (0x5dd2f8) | `0x100f7020` (0x1001e37f) | instance for LoadCursor etc. |
| 2 | 0 | — (not read) | — |
| 3 | command-line copy | read at 0x1001e3b9: `[arg3]==0` clears the CD drive letter `0x10047774` ("A:\") | CD path |
| 4 | 1 | — | — |
| 5 | main HWND 0x5dcf7c | `0x100f702c` (0x1001e385) | GetClientRect 0x1001e415, PostMessageA target, ScreenToClient 0x1001fca3 |
| 6 | DirectDraw block 0x643920 or 0 (`-gdi`) | `0x100f6368` (0x1001e2bd) | chooses DDraw vs GDI blit in `LoadScreenBackground` 0x10038804 |
| 7 | &0x4c2160 (exe-persistent dword) | `0x100d2180` (0x1001e2d3) | **the current trip scene/mission number**: `*arg7==0x11` routes 0xC008 (0x1001e5c5); incremented after a won mission (0x1001eafc–0x1001eaff); "Scene %d." label (0x100147d5); file `t%2.2d.msn` (0x1001eb3d); dir record +0 (0x10014870) |
| 8 | &0x5dcea4 (result block) | not stored; read at 0x1001e511 | passed as arg 1 of `PlayerDef_Load` 0x10016f70, which reads only its arg 2 (the copy target `[esp+0x84]` at 0x10016fdf sits after 0x70+2 pushes plus the unpopped `fclose` push, so it is arg 2 = 0x100c5ae0). **No DLL use of arg 8 was found**: `sdis.py` shows no other read of `[esp+0x70]` in ShellMain. Where 0x5dcea9 (the mission name the exe copies) gets written is open. |
| 9 | callback table | `0x10058198` (0x1001e2e3) | every callback |
| 10 | 0x230-byte setup/net block | `0x100d2170` (0x1001e2f4) = ebx; bit 5 of `[arg10]` → `0x100d218c` (0x1001e2fc–0x1001e307) | `+0x5d` holds a mission name: `_stricmp(arg10+0x5d,"a01.msn")` 0x1001e500; `t%2.2d.msn` is written there at 0x1001eb43 when a trip mission starts; `+4` → `0x100d217c` (0x1001e6f5) |
| 11 | the exe's previous game_state | its **address** is stored in `0x100d2164` (0x1001e2ee) | `==5` → main menu (0x1001e4ed); `==2` / `==8` / `==1` pick the post-mission flow (0x1001e538, 0x1001e585, 0x1001e5b5); `*arg11==1` at 0x1001eaf0 advances the scene after a won mission; saved into dir records (+0x34) |
| 12 | &0x5dce80 (0x40-byte player block) | `0x100c5ad8` (0x1001e2e8) | `+0x20` = play mode (1/2; 2 = trip in progress: Options shows Save/Exit Trip, 0x1000e64f; set to 2 on start, 0x1001eb5e), `+0x38` = current vehicle index into the 0x8c4 garage array (0x100329fc). The exe reads 0x5dcea0 = arg12+0x20 as the result code (helper report (a)). |
| 13 | &0x4f9e08 (video-mode table) | `0x100f6364` (0x1001e2c6) | Graphic Detail menu |

**Result (settled 2026-09-26, naming batch C, spot-checked).** Two channels:
- ShellMain's **return value** is 3 = play (0x1001eb61, loop ended by `WM_QUIT` 0xC001) or 0xff = quit (0x1001eb68).
- The **play mode** is `[[0x100c5ad8]+0x20]` = exe 0x5dcea0, which the exe switches on:
  - **2 = trip** — ShellMain 0x1001eb5e, `Screen_LoadBookmark` 0x10013408, `Inventory_Open` 0x10018b07
  - **3 = auto melee** — `EntryForm_Open` 0x10027f64; `EntryForm_Frame` 0x100289bf on GO
  - **4 = scenario** — `EntryForm_Open` 0x100280e0 (form mode 1); `EntryForm_Frame` 0x10028aed
  - **5 = network** — `EntryForm_Frame` 0x10028662 (msg 0xC004, modes 6–9) and 0x10028c31 (after the join succeeds)

**Correction to `work\exe-callbacks.md`:** the string at arg12+0x29 (exe **0x5dcea9**) is **always the player's
car file** ("vehscn.vcf"), never a mission file. Writes: 0x100289ce, 0x10028afd, 0x1000515e, 0x10016b23, 0x10016c2a,
0x1001f5a7, 0x100248b3, 0x100248ec, 0x10024a58. The **mission file** goes into the arg-10 setup block at **+0x5d**:
`t%2.2d.msn` for a trip (0x1001eb43), the arena table 0x1004b530 ("m01.msn"…) for melee (0x10028a23–0x10028a4b),
the scenario table 0x1004b800 ("s03.msn"…) for a scenario (0x10028b31). Setup +0xe holds the player name (0x10028a58)
and +0x2e the car name (0x10028a9d). So the exe copies 0x5dcea9 into 0x5dd370 for results 2/3/4 as the **car to
load**. The mission comes from the WinMain setup struct. That is consistent with direct-mission-entry.md's
`startup_mission_name` path.

## The 27 callbacks

`slot | exe fn | exe-side meaning (helper) | DLL call sites (containing DLL function) | DLL-side context`

| slot | exe | meaning | DLL call sites | context |
|---|---|---|---|---|
| 00 | 0x4b4c10 | BuildPartsCatalogue(PartRec*) → count | 14: 0x10001aa4 (0x10001a90), 0x100027e1 (enter-Reconfig 0x10002750), 0x10013475 (load bookmark 0x10013380), 0x10016a8d, 0x10016bbd (new trip 0x10016b50), 0x1001f56c (mission grid 0x1001f480), 0x10023ea7 (car select 0x10023c20), 0x1002408b (post-mission 0x10023fc0), 0x100247c3 / 0x1002487a / 0x10024a20 (0x100246e0), 0x1002a8d9 (0x1002a3b0), 0x10001e84, 0x10024396 | every garage entry rebuilds the part catalogue into `0x100c6288` (the `&0x100c6288` push next to each site, e.g. 0x100027be) |
| 01 | 0x4b4b80 | LoadStockVehicles | **none** | dead in Gold (no caller on either side) |
| 02 | 0x4b2b30 | RegisterFile(file, dir) | 11: 0x10001d17 / 0x10001d9d (0x10001a90), 0x10017ecc (0x10017e90), 0x100358ab / 0x100358d7 (0x10035250), 0x10035ea7 / 0x10035ed3 (0x10035930), 0x1000204c, 0x10017ae0, 0x1001847b, 0x10018491 | after writing a `.vcf` or state file, so the exe's file index sees it |
| 03 | 0x4b6850 | SaveGarageVehicleAsVcf | 0x10001d87 (0x10001a90), 0x10017aca | chassis/variant save |
| 04 | 0x4b73a0 | UpdateVehStateFile | **none** | dead |
| 05 | 0x4b58a0 | LoadVcfIntoGarage(GarageRec*, vcf, idx) → nWeapons | 28 sites; the heaviest callers are 0x10002750 (×4, Reconfig), 0x100246e0 (×3), 0x10028610 (×3, melee forms), 0x1002a3b0 (×3) | loads cars into the 0x8c4-stride garage at `0x100581a0` (`&0x100581a0` at 0x10002868) |
| 06 | 0x4b7190 | ReadVehStateFile | 0x10002989 (0x10002750) | Reconfig reads the car's damage/state file |
| 07 | 0x4b72b0 | CreateVehStateFile | 0x10001d01 (0x10001a90), 0x10002037 | new state file |
| 08 | 0x4b0bd0 | WriteVcf | 0x1003588e (0x10035250) | |
| 09 | 0x4b0b00 | WriteVehStateFile | 0x10035e8a (0x10035930) | |
| 10 | 0x421400 | SoundUpdate(commit) | 0x1000bd40 (**Modal_YesNo** 0x1000bc40 loop), 0x1000bfba (0x1000bdd0, the one-button modal), 0x1001e9c2 (ShellMain main loop, arg 0), 0x10036692 (0x10036660) | per-frame sound service: the only exe code that runs while a modal loops |
| 11 | 0x421d50 | SoundCreateKeyed | 0x1003664f (0x10036640), 0x10036672 (0x10036660) | the shell's `Sound` wrapper (ctor 0x10036610 takes a DB WAV item; 0x10036640 = play) |
| 12 | 0x421e90 | SoundStopKeyed | 0x100366b9 (0x100366b0) | `Sound` stop |
| 13 | 0x421f50 | SoundQueryKeyed → flag bit 0 | 0x10036680 / 0x100366a0 (0x10036660), 0x100366c9 | 0x10036660 polls it (restart when done). So bit 0 means **playing**: proposed. |
| 14 | 0x423520 | SetMusicVolume | 0x1000d3ba (0x1000d3a0), 0x1000dc23 (Audio menu frame 0x1000db90) | Audio Control "Music Level" |
| 15 | 0x423540 | SetSfxVolumePreview | 0x1000d3ea (0x1000d3d0) | "Sfx Level" |
| 16 | 0x4235a0 | SetVoiceVolumePreview | 0x1000d41a (0x1000d400) | "Voice Level" |
| 17 | 0x470f90 | RequireCD2(prompt) | 0x1001e0fe, 0x1001e118 (ShellWindowProc, message 0xC010 = go) | CD check before a mission. `0x1000bad0` in between is the retry prompt. On failure, 0xC00E is posted with 0xC010 (0x1001e139). |
| 18 | 0x499ba0 | GetDefaultDetailPreset(u8[16]) | 0x10012ea9 (Graphic Detail frame 0x10012db0), 0x10016f7f (player-def loader 0x10016f70, before reading `I76PLYR.DEF`) | defaults, then the file overrides |
| 19 | 0x433de0 | returns 0 | 0x10012e79 (0x10012db0) | Graphic Detail: the "restore defaults?" gate always sees 0 |
| 20 | 0x423330 | PlayCdTrack(track, force) | 0x10007b01 / 0x10007bc4 (Credits 0x10007930 / 0x10007b20), 0x1001e4b9 (ShellMain start: track 0xd, force 1) | shell music |
| 21 | 0x4233d0 | StopCdMusic | 0x10007af4, 0x10007b77, 0x10007bb8 (Credits), 0x1001e4ac (ShellMain start) | |
| 22 | 0x4b4a80 | GetMissionWorldName | 0x10027eba (0x10027c80) | mission/world names for the forms |
| 23 | 0x499920 | SetLocaleFontField | **none** | dead |
| 24 | 0x499410 | TextFitWidth | **none** | dead |
| 25 | 0x4b3570 | SetWeaponWhitelist | 0x1002f390 (0x1002f368), 0x100301e1 (0x1002fcd8, called every frame at 0x1001ea67) | network rules |
| 26 | 0x4b35a0 | ValidateVcf (anti-cheat CRC) | 0x1002e6f5 (0x1002e487), 0x1002f3d6 (0x1002f368) | netgame join |

Counts: 23 of 27 slots are called by the DLL (92 sites). Slots 01, 04, 23 and 24 have no caller on either side, the
exe side checked through callgraph.json by the helper agent.

## Notes and checks

- **Slot 10 is the only thing modal loops call into the exe.** `Modal_YesNo` (0x1000bc40) polls only its own mouse
  object and slot 10. It does no message pump and no key read, which is the root of the 2026-08-10 "not responding" freeze
  (FIXES.md F3).
- The helper's claim that "0x4c2160 is DLL-persistent state" is refined here: it is the **trip scene counter**,
  arg 7 → `0x100d2180`. Evidence: the increment at 0x1001eaff, `t%2.2d.msn` at 0x1001eb3d, and the Scene label.
- Slot 17's `-1` (MCI error) return: the loop at 0x1001e104–0x1001e120 treats any nonzero as "CD present".
