# Nitro as the base? What the GOG Nitro Pack holds of the original game (2026-10-21)

Lane `nitro-base`. Owner question (verbatim): "can you play everything in the original on nitro version or no?", scope cut
the same morning (verbatim): "i don't need a big test just tell me if nitro claims to have original and expanded content
and if the files are there is fine, and give me a version of it i can play to check". Background: NITRO-VS-RETAIL-2026-10-20
(Nitro = Gold's engine relinked, same file formats).

## Answer

**No: the GOG Nitro Pack is the expansion only.** It does not claim the original game and it does not ship it.
- **The claim.** Nothing in the install calls itself more than "Interstate '76 Nitro Pack" (`splash\PRODUCT.INI`
  `I'76: Nitro Pack`, `STRINGS.TXT`, `goggame-1207661023.info`). Activision sold it as an add-on: 20 new missions, 30
  multiplayer maps, CTF and racing, novelty cars, new weapons (Arsenal page, I76-VERSIONS s.1). GOG sells the original as
  a separate product (I'76 = Gold), the pair as *Arsenal*.
- **The files.** None of the original 40 mission files (T01-T17 campaign, M01-M15 arenas, A01, S01-S07) is in the
  install, nor 27 of the 29 movies. What Nitro does carry: every car, texture and model of the original, byte-identical,
  inside `nitro.zfs`; its own campaign (19 P-missions + training B01, 4 characters); 54 multiplayer maps (24 combat .CBT, 17 CTF, 13 race), of which
  N51-N65 are the 15 original arenas re-laid on the same terrain.
- **Its shell has no original campaign flow.** Strings only in Gold's `i76shell.dll`, absent from `nitshell.dll`: `Trip`,
  `t%2.2d.msn`, `savegame.dir`, `save%3.3d.cmp`, `Load Bookmark` / `Save Bookmark`, `Scene %d.`, `Leave without taking
  salvage?`, `m01.msn`..`m15.msn`, `addon\*.lvl`. Nitro's single-player menu reads `addon\SCENARIO.DAT` (a mission list
  per character); its arena list reads `*.cbt / *.rac / *.cf2-4`. So even with the original files added, there is no
  trip (scene chain, garage and salvage between scenes, bookmarks); a mission can at most be listed one by one.

## Inventory: original content in the GOG Nitro install

By name against the golden copy (`Games\I76\golden\Interstate 76`); md5 where the same name exists. Tool: lab
`tools\nitro-base\inventory.py`, output `captures\nitro-base-20261021\inventory.txt`.

| original content | files (golden) | in Nitro | note |
|---|---|---|---|
| campaign scenes T01-T17 (.MSN / .TER / _16.PCF) | 51 in miss16, 34 in miss8 | **absent** | Nitro's campaign is P01-P19 + B01 |
| melee arenas M01-M15 (.MSN / .TER) | 30 + 30 | **absent** by name | N51-N65 .CBT = the same arenas re-laid, terrain byte-identical (NITRO-VS-RETAIL s.3) |
| A01, S01-S07 | 23 + 16 | **absent** | |
| scene movies INT01-16, OUT01-17, ANG05/06/16 F01.SMK | 27 | **absent** | |
| INTROF01.SMK, CREDF01.SMK | 2 | present, **different md5** | Nitro's own intro / credits |
| music 2-11.mp3 | 10 | present, **different md5** (not listened to) | |
| music 12-17.mp3 | 6 | **absent** | |
| ADDON fullres.lst, i2ayj_13.map, vmxmarx3.vcf | 3 | present, same md5 | |
| ADDON loadgame.pcx, loadscr.pcx | 2 | present, different md5 | Nitro's loading screens |
| cars, chassis, wheels, weapons, textures, models (I76.ZFS members) | 5,624 shared names | **present, all byte-identical** in nitro.zfs | plus 88 new .vcf, 7 .gdf, 985 .wav |
| original radio voices (I76.ZFS .wav) | 492 | **absent** | campaign / training speech; Nitro mounts only nitro.zfs |
| saves and the original shell's files (savegame.dir, save*.cmp, I76PLYR.DEF, i76car.def, multicar.def, trip4.spc) | - | absent | Nitro uses nitplyr.def / nitcar.def / nitmcar.def; no save files |

## Two copies to play-check

| folder | what | start |
|---|---|---|
| `<games>\I76\nitro` | the GOG Nitro Pack as shipped: `nitro-full\app` copied unmodified (520 files, md5-compared to the extraction); nitro.exe 28b8ae27, GOG's OpenGLide renderer, no proxy, no patch | `PLAY.bat` = `nitro.exe -glide` (how GOG's shortcut runs it; FINDINGS-2026-07-WINDOWS-AND-TEXTURES) |
| `<games>\I76\nitro-plus-original` | the same + the original content copied beside it from the golden copy (list with md5: `NITRO-BASE-STAGED.tsv` in the folder; summary in its `VERSION.md`): 184 mission files, M01-M15 also as `.CBT` (30), 27 movies, music 12-17, 22 save / setup files, 5 ADDON files; one Nitro file changed: `addon\SCENARIO.DAT` gets a 5th character **Groove** = "Original Mission 1-17" (t01-t17; stock kept in `_nitro-originals\`) | `PLAY.bat` |

What to click in `nitro-plus-original`: the single-player menu, character **Groove**, any "Original Mission N" (does a
T-scene load and play?); multiplayer / host alone, the arena list (do M01-M15 appear beside N51-N65 and load?). Expect
the radio voices to be missing in the T-scenes (they live in `I76.ZFS`, which Nitro does not open). The SCENARIO.DAT
columns after the file name were copied from Nitro's first Taurus line (their meaning is not decoded).

**Boot check (headless, private desktop, muted, game state read from memory; this session is Remote Desktop):**
- `nitro` (stock): **"Unhandled Exception" message box**, state never reached the menu (n 1, 200 s;
  `captures\nitro-base-20261021\owner-nitro-boot1.json`). `nitro-plus-original`: the same box (n 1, 60 s).
- Where: a stock copy with only the lab file-log added (`exp-nitro-stockgl`) stops right after `ZGLIDE.DLL` loads, i.e.
  in GOG's OpenGLide `glide2x.dll` start-up, before the first data file is read (n 1, `stockgl-r1.log`). The same exe with
  dgVoodoo's Glide in place of OpenGLide (lab `exp-nitro-base`) reads its files and reaches Nitro's main menu, state 6
  (n 1, `shell-r2.log`, intro movie skipped; with the movie playing it sat in the movie for 45 s, n 1).
- So **not confirmed playable on this PC from here**: OpenGL under a Remote Desktop session / an off-screen desktop is the
  likely cause (AGENTS.md: launch results over RDP do not count), not proven. If `PLAY.bat` shows the same box at the
  monitor, the known fix is the one our installer applies to Nitro (setup-windows.ps1 -Exe nitro.exe: dgVoodoo's Glide);
  it was not put in these folders because they are meant to be as GOG ships them.

## What it would take to make Nitro the base (rough size, from NITRO-VS-RETAIL and the shell strings)

1. The original campaign: port Gold's trip flow into Nitro's shell (scene chain, garage + salvage, bookmarks / savegame,
   the trip FMV and briefing screens), or run Gold's `i76shell.dll` against nitro.exe (shell ABI not compared). Large.
2. The original radio voices: a loose-file or second-ZFS path for the 492 base .wav. Small to medium.
3. Every proxy feature (tick, music, cursor, multiplayer fill, telemetry...) re-addressed: our proxy hard-codes Gold
   addresses; Nitro moved code and globals (examples measured today: state 0x4c2164 -> 0x4f30cc, mission buffer 0x5049f0
   -> 0x526758, player root 0x54a264 -> 0x5530c4, entity fields >= +0x444 shift by 4). 90.8 % of functions are matched,
   so mostly table work. Large but mechanical.
4. The frame limiter / PIT fix (AiO or i76fix equivalent) for nitro.exe. Small.
5. Our LAN multiplayer: Nitro's ANet 2 does not talk to Gold's ANet 1; the pack would move to Nitro's stack. Medium.

The cheaper direction stays the one in NITRO-VS-RETAIL s.7a: keep the Gold exe and load Nitro's missions and arenas into it
as add-on files (measured: P01 boots in our exe).

## Files

- Repo: this record; pointer in NITRO-VS-RETAIL-2026-10-20.md; OWNER-TEST-LIST row "base: Gold or Nitro".
- Lab `tools\nitro-base\`: `inventory.py`, `stage_retail.py` (makes nitro-plus-original and the lab copy), `nbrun.py`
  (headless boot + Nitro memory probe), `xmap.py` / `gmap.py` (Gold -> Nitro address mapping through exe_diff_map.json),
  `nbdrv\` (a lab-only nitro.exe instrument, Strlkup.dll: mission boot, file log, input; used only in the lab copy).
- Lab copy `exp-nitro-base\` (Nitro + original content + dgVoodoo + nbdrv) and `captures\nitro-base-20261021\`.
- The first plan (a full campaign / arena / car / feel measurement) was stopped by the owner's scope cut; nothing of it is
  claimed here. PrintWindow screenshots of the private desktop came back black, as AGENTS.md predicts.
