# Extra content: what can be made playable, what it costs (2026-10-25)

Owner's ask (2026-10-24): *"analysis and experimentation around which of the extra content could most easily be made
available in the game, and which would require extensive work. Level editors and stuff working would be cool. Community
maps: no more than the top 10 most acclaimed ones in any GUI."*

Inputs: [research/content-2026-10-24/COMMUNITY-CONTENT-INDEX.md](research/content-2026-10-24/COMMUNITY-CONTENT-INDEX.md)
(+ `index/*.csv`; archive `<archive>\community-20261024`), [game-files-and-cast.md](research/content-2026-10-24/game-files-and-cast.md),
[development-and-press.md](research/content-2026-10-24/development-and-press.md), <re-archive> `data\FORMATS.md`,
[MODDING-GUIDE.md](MODDING-GUIDE.md), [LEVEL-FORMAT.md](LEVEL-FORMAT.md), [records/COOP-LIST-ENTRIES-2026-10-18.md](records/COOP-LIST-ENTRIES-2026-10-18.md).
Lab copies only: `<lab>\exp-content-gold` (fresh twin of `exp-polish2`) and `exp-content-nitro` (fresh twin of
`exp-nitro-owner`). Nothing was installed in any other copy, and nothing is in any shipped list.
Tools: `tools/content-archive/arena-pack.py` (this repo); lab `tools\content-trial\` (trial scripts, editor driver, P20 stub).

## 0. Short answers

- **Easiest wins (hours each):** the 10 shortlisted community arenas (s.3), the SideWinder FRC set (a folder swap), the
  AVA league car sets (loose .vcf files), the M13 objectives fix (one WRLD field), the German voices as a private language
  pack (loose .wav in `ADDON\`).
- **Cheap with one tool we now have:** every 1997 community arena. **New finding:** 225 maps survive only in the 1997
  I76EDIT layout (WREV 8), which Gold and Nitro misread - not just the title. `arena-pack.py` converts them the way the
  official 1998 editor does (s.2). Proven by running both official editors (s.4.3). Live: the published Rage County file
  shows an empty row in Gold's arena list and the car never moves (n 3); converted, it lists as "Rage County" and drives.
- **Loaded in the lab:** Gold - 76th Precinct, Leathertown, Rage County (converted) and Twin Mesas (ARSEDIT export), 60 s
  each, 1 crash in 10 boots (proxy-side suspect, s.4.1); Nitro - Gumball Rally and Intercept and Pursuit hosted 60 s; the
  Armadillo (unused, shipped) and hop76's Limo driven as the player's car in T01; a P20 stub driven in Nitro.
- **The official editors run on this Windows 10** (s.4.3), on a private desktop, driven by window messages: ARSEDIT (the
  1998 Arsenal/Nitro builder) opened a 1997 community project and exported a WREV 9 mission; I76EDIT (1997) exported the
  old layout. **Neither can open a game .msn/.lvl** (only their own `.I76` project files), so they cannot edit our or the
  stock missions; for those, our parsers and `fsmtool` are the editor.
- **Days:** the unused Armadillo / Phantom / Howitzer as mission vehicles (data only), a P20 mission beyond the stub
  (s.4.4), unused voice lines wired into new scripts.
- **Weeks / a lane:** new missions with real scripts (P20 proper, "Interstate '77"), a car-picker for novelty cars in
  multiplayer, the German text/cutscene localisation, music beyond the 17 CD tracks.
- **P20 is not a lost 20th mission.** `p20.npt` is an earlier draft of P19 (s.4.4): same structure, "governor" where
  P19 says "CEO". The smallest runnable P20 is P19 with the P20 text.

## 1. Feasibility matrix

"Our builds" = Gold `i76.exe` 9a232dcc + i76shell + the Strlkup proxy, and Nitro `nitro.exe` 28b8ae27 + the proxy. Every
multiplayer row carries the same rule: **every machine in a LAN game needs byte-identical files** (an add-on `.lvl` is
CRC-checked by the joiner's shell only when its name is lower case, COOP-LIST-ENTRIES s.1; car and stock-file changes are
not checked at all, so a mismatch there shows up as wrong or invisible cars, not as a refusal).

| content | what it takes in our builds | effort | risk | best first step |
|---|---|---|---|---|
| **Community arenas, Gold** (201 unique I'76 maps; 189 pass the static check) | drop-in to `ADDON\` as lower-case `.lvl` + `.ter`; **the 1997 files (WREV 8) need `arena-pack.py`** (inserts the horizon name, WREV 9; s.2) | 15-30 min per map incl. a load test | WREV 8 unconverted: night, zero grip on surface 0, far clip from title bytes (s.2); MP: same files everywhere; 37 maps reference missing art, 82 drop objects | the 5 Gold maps of s.3, converted, one LAN pack |
| **Community arenas, Nitro** (327 unique; 117 race, 26 CTF) | drop-in: mission into `miss8` + `miss16`, `.ter` into `addon` (Nitro's own lists read `*.cbt/*.rac/*.cfN`); allnitromaps is already WREV 9 with titles | 10-20 min per map | Nitro exe also expects WREV 9 (same check as Gold); 15 need Nitro-only assets (Nitro-only by nature); Nitro MP = same files everywhere | the 5 Nitro maps of s.3 |
| Community maps in Gold's list from Nitro (`.cbt` renamed `.lvl`) | rename + `arena-pack.py gold` (title kept) | minutes | race checkpoints / CTF teams are Nitro-only: melee only in Gold | only where a Gold-first version does not exist |
| **Community cars** (hop76 42 novelty, King's 13 chassis swaps + specials, AVA 2 x 23 league sets) | AVA sets: loose `.vcf` in `ADDON\` (stock chassis), drop-in. hop76 / pickup_camper: new `.vdf`/`.vtf`/`.vcf` in `ADDON\` + a record in `i76car.def` (the garage list: `u32 count` + 28-byte records `{id, u32, variants, name[16]}`; hop76 ships a 58-record file). King's chassis files **replace a stock .vdf** = every car on that chassis changes | AVA: hours; one hop76 car: 1-2 h; the full hop76 set: a day (its `I76car.def` replaces ours wholesale) | hop76 was made to show cheat cars ("hoppohax") in net games; chassis swaps change handling for everyone; MP: identical `ADDON\` + `i76car.def` everywhere or other players see the stock car | s.4.2: the limo drives; next the AVA "Division" sets as a host-side car class |
| **Paint jobs** (37 AVA Paint Shop, 7 King's) | AVA: TGA sources for the AVA Paint Shop tool, not game files (n_files 1-4, no .vtf/.map) -> conversion to `.vtf` + `.map`/`.tmt` (paktool / our formats); King's: `.vtf` + textures, drop-in | AVA: days (converter); King's: hours | a `.vtf` with a stock name replaces that skin for everyone | skip AVA; King's paints only on request |
| **3 unused shipped vehicles** (Armadillo, F4D Phantom, Howitzer) | data only: everything is in Gold's `I76.ZFS` (vdf, vtf, vcf, geometry). As a mission car: an ODEF entry (class 8/9) in a mission; as the player's car: an `ADDON\` `.vcf` (s.4.2) or an `i76car.def` record (`vdillo` 1 variant) | hours per placement; a scripted Howitzer artillery role: days (FSM) | the Phantom is a plane on a car chassis model (flies? untested); artillery limit message in the exe | s.4.2: the Armadillo drives |
| **Cut mission P20** | not a cut 20th mission: `p20.npt` = an earlier draft of P19 (s.4.4). Stub = P19 + P20 text: data patch (WRLD objectives field) | stub: 1 h (done); a real "governor" mission (new placement, script): 1-2 weeks with ARSEDIT + `fsmtool` | Nitro only (P assets) unless Nitro missions are ported to Gold (NITRO-BASE) | s.4.4 |
| **Cut S08** | 3 voice clips only (`s8sgc01/02`, `s8sn201`), no .msn/.ter/.npt | a new scenario: 1-2 weeks | - | not worth it alone; fold the 3 lines into a new mission |
| **Old training (`train.npt`)** | objective text only ("race Taurus to the next gate, target practice, mock town, drone trucks"); A01's terrain and script exist | a rebuilt A01 variant: 1 week (script) | - | after P20 |
| **M13 objectives bug** | one WRLD field (`m06.npt` -> `m13.npt`) in miss8 + miss16 | 15 min + a load test | changes a stock mission file (no MP CRC for stock .msn) | quick win for the next promotion |
| **68 unplaced scenery objects** | data only: an ODEF `OBJ` with the object's name in any mission or arena (cemetery, tunnels, helipad, depot, trees) | minutes per object by script; meaningful use needs a map | an object that never shipped placed may have untested collision/LOD | use them in the first ARSEDIT map |
| **Unused voice lines** (Gold 10, Nitro 74) | FSM: add the wav to a mission's sound table and a `cb` action at the right moment (`fsmtool asm`) | an hour per line once a host script exists; days for a set | none at run time; needs listening first (n 1 listener so far) | only inside a new mission (P20 proper) |
| **German dub** (487 differing voice files in the German 1.0 ZFS; German `.npt`, LANG.TXT, 29 cutscenes) | voices: loose `.wav` in `ADDON\` (VFS container slot 0 is `addon`, FORMATS.md s.6; the official 1.06 patch shipped its fixes the same way) = drop-in; shell text: `lang.txt` belongs to STRLKUP.DLL = our proxy (code); cutscenes: `smk\` swap; `.npt`: drop-in | voices: 2 h + listening; text: days (the proxy owns STRLKUP); cutscenes: hours | disc image rights: owner's private use only; 1.0-era names (478 not in Gold) | a private "German voices" pack for the owner's own copy, if he wants it |
| **Bullmark demo tracks** (24 mp3, unreleased) | the music proxy plays `music\N.mp3` for CD tracks 1..17: replacing an N.mp3 is drop-in; new tracks 18+ need the proxy's fake TOC to answer more tracks (small code) and a mission's WRLD CD-track byte | drop-in: minutes; new tracks: a day | **licensing**: unreleased band recordings, Activision/musicians; owner's private use only | owner decision first (s.6) |
| **Official MP builder I76EDIT (builder.zip, 1997)** | runs on Windows 10 (s.4.3); opens its `.I76` projects, exports **WREV 8 `.lvl`** (the layout Gold misreads) | usable today, but every export must go through `arena-pack.py` | the tool itself warns of crashes; no undo | prefer ARSEDIT; use I76EDIT only to re-export old projects |
| **Arsenal editor ARSEDIT (arsedit.zip, 1998, "I'76 Nitro Editor v0.098b", about box "I77edit")** | runs on Windows 10 (s.4.3); opens `.I76` / `.I77` projects, exports **WREV 9 `.msn`** that Gold and Nitro read; imports `.FSM` scripts; **cannot open a game `.msn`** ("is not an Iterstate '76 Mission file!") | a new arena: 1-3 days of map work; a scripted mission: 1-2 weeks | needs the GUI at the console (the canvas did not draw under PrintWindow on a private desktop); "no commercial use" licence | a 1-day trial map with the unplaced objects, exported, round-tripped through `bwd2x` + `fsmtool`, played in the lab twin |
| hop76 / King's / AVA car tools (ChopShop, VCFgen, paktool, AVA Car Designer, Hack76, bpatch76) | not needed: `i76mod.py` writes `.vcf` byte-exact; paktool is the only one with no in-house equivalent (.pak textures) | - | bpatch76 is a warez-group NFO patcher: do not run; Hack76 edits live tables (cheat tool) | read their formats only |
| **SideWinder FRC set** (14 effects, 9 differ from GOG's) | drop-in: swap the `force\*.FRC` files (and optionally `i7_sfrce.dll`) | minutes + an A/B on the wheel | FFB only, no MP effect | hand the path to the FFB lane (already in the index plan) |

## 2. The 1997 map layout: Gold misreads every field after the 8th file name

The index said the 409 I76EDIT-1997 files "stop before the 16-byte mission title". Measured here: that is a misframing.

- Their WRLD body is **318 bytes, not 315**, and it **has** a title, the author's own (`Rage County`, `76th Precinct`,
  `Leathertown`, `Twin Mesas, TX` ...), 13 bytes earlier than Gold's (+0x12e). What the 1997 layout lacks is the **13-byte
  horizon `.hzd` name** at body +0x86 (9 file names in WREV 9, 8 in WREV 8). Byte comparison: Rage County (WREV 8) against
  Gumball Rally (WREV 9): identical up to +0x86, then the same fields shifted by 13.
- **Every 1997 exe expects WREV 8, Gold and Nitro expect 9.** The REV table at 0x500438 lists `{tag, revision}`:
  demo / 1.05 / 1.06 / 1.081 / 1.083 have `WREV 8`, Gold 9a232dcc and Nitro 28b8ae27 have `WREV 9` (read from all seven exes).
  Gold's REV handler 0x4b4610 finds the tag, compares the value and on a mismatch formats "Bad revision for %s chunk in
  file %s" through 0x42d5d0, which is a bare `ret` in the release build: **no message**.
- **Gold's WRLD loader reads fixed offsets** (0x4b8a10: hour chunk +0x9b = body +0x93, surfaces body +0x97, far clip
  `fild [ebx+0x13f]` = body +0x137) and the title peek is `lea edi,[eax+0x143]` = body +0x13b (0x4b4a10). No revision branch.
- So a raw 1997 map in Gold reads (`arena-pack.py show`):

  | map | arena-list title | horizon | hour | far clip | grip, surface 0 |
  |---|---|---|---|---|---|
  | Rage County (raw) | '' (empty) | '\t' | 0 (night) | 31092 | 0 |
  | 76th Precinct (raw) | '' | '\x0c' | 0 | 1952673385 (clamped 100000) | 0 |
  | Biggsville (raw) | '' | '\x0f' | 0 | 101 | 0 |
  | Drug Bust (raw) | '' | '\x0c' | 0 | 0 (clamped 100) | 0 |
  | Twin Mesas, TX (raw) | 'X' (the title's last letter) | '\x06' | 0 | 1411394675 | 0 |
  | Rage County (converted) | Rage County | p01.HZD | 9 | 600 | 1.9 |
  | stock M01 | (stock table) | p01.HZD | 15 | 600 | 1.9 |

  Live check of the raw control against the converted file: s.4.1.
- **The official fix is the same.** ARSEDIT's guide: "If you want to convert an old I'76 user created map so it's
  compatible with the I'76 Arsenal, simply open the map using the new editor ... re-export". Running it (s.4.3) on the
  Twin Mesas project gives WRLD 331 B, WREV 9, horizon '' (empty), title "Twin Mesas, TX", every other chunk as before.
  `arena-pack.py` produces the same layout from the `.lvl` alone (no project file needed - only 6 of the maps shipped one)
  and fills the horizon with the stock miss8 horizon of the same palette instead of an empty name (stock M15 has an empty
  one, so both load).
- Scale: of 569 non-stock map groups, **225 survive only as WREV 8**, 77 in both layouts, 266 only as WREV 9.

## 3. Top 10 community maps (5 Gold, 5 Nitro)

**How acclaim was judged, and how thin the evidence is.** No ratings survive: LSM's archive pages have a RATING column
that is empty on every row (i76comb1 page, read 2026-10-24), Local Ditch's map page has no per-map comments, and a web
search found no community ranking. What exists, in order of weight: (1) **Local Ditch's list of 19 "favorite
community-built I'76 maps from back in the day"** (the only explicit curation); (2) the map was **ported by its author or on
request** to the other game (it survives in both an `i76comb*` and a Nitro group); (3) an **LSM "exclusive"** listing;
(4) DIVER's route380 selection; (5) the AVA league set; (6) presence in interstate76.com's `allnitromaps` and the
played-in archive.org install (weak: those hold nearly everything). A clean static check, a known author and our own load
test decided between equals. Signals read from the `sources` column of `index/maps-unique.csv` (weights LD 3, each other
signal 1, a known author 0.5); the top Gold scores were all LD favourites (3.5), the top Nitro ones LD + exclusive + ported (6.5).

| # | game | map (file) | author (credit line) | why | our test |
|---|---|---|---|---|---|
| 1 | Gold melee | **Rage County** (`rageco.lvl`) | General Rage, 1997-04-20 | LD favourite; 208 objects, 2 regen, "Multi-mele tag" rules in the readme | converted: listed "Rage County", loaded, drove 60 s (s.4.1) |
| 2 | Gold melee | **76th Precinct** (`76prcnct.lvl`) v1.2 | Stingray, 1997-05-06; credit: SuperFreak and the officers of team Mod Squad | LD favourite; 10 spawn, 4 regen; v1.2 thinned for 3+ players | converted: listed, loaded, 60 s |
| 3 | Gold melee | **Leathertown** (`leather.lvl`) | Skull N. Bones ("Skull&bones"); idea: the Leather Jackets gang | LD favourite; 156 objects, 4 regen; demo-derby arena, high jump | converted: listed, loaded, 60 s |
| 4 | Gold melee | **Biggsville** (`bigville.lvl`) | Lt. Stinger (TBP), 1997-12-01; made for Officer Biggs (TBP); template by Debacle | LD favourite; 224 objects, 2 sides, 4 regen | static only (2 object types missing: `bdfrez1`, `bhtowr1`, skipped by the loader) |
| 5 | Gold melee | **Drug Bust** (`drugb.lvl`) | Captain Gram, 1997-09-17 | LD favourite; cops-and-robbers layout, 6 regen | static only |
| 6 | Nitro combat | **Gumball Rally** (`gumball.cbt`, also `.rac`) | Stingray, 1997-06-11; Nitro version 2.0 (2000-03-21, "converted by request", converter not named) | LD favourite + LSM exclusive + ported both ways | hosted: in list (index 0 of 26), loaded, 60 s (s.4.1) |
| 7 | Nitro combat | **Intercept and Pursuit** (`intercpt.cbt`) | Debacle, 1997-04-17 | LD favourite + LSM exclusive + ported | hosted: in list (index 1 of 26), loaded, 60 s |
| 8 | Nitro combat | **BorderTown, TX** (`tex.cbt`) | Debacle, 1997-07-27 | LD favourite + ported | static only |
| 9 | Nitro combat | **Offroad Terror** ("Offroad Gold", `offroad.cbt`) | General Rage, 1997-04-24 | LD favourite + LSM exclusive + ported + racing group | static only |
| 10 | Nitro race | **Great Oval** (`goval.rac`) | DIVER (D1VER); Nitro port by Lightfoot (LSM, 2002) **"without the authors expressed consent"** | LSM exclusive + route380 + ported; the only race map with curation evidence | staged; not hosted (the instrument hosts from the combat list) |

Credit line for a pack page: *"<map> by <author> (<year>), from Lightfoot's Stolen Maps / Local Ditch; included with
thanks. Original readme in the pack."* Every Gold readme above says "Please keep all files together. Do what you want with
it, as long as it is not for profit" (Rage County, Biggsville, Drug Bust); keep the readme beside the map. Note that
`arena-pack.py` *changes* the 1997 files (13 bytes), so a shared pack ships converted files: say so in the credit line.
Alternates if one fails a play-test: Twin Mesas, TX (Disco .45; tested via ARSEDIT, s.4.3), RepoTown USA (Debacle, Nitro),
All-in-One (Skull N. Bones, racing/jumping, Local Ditch only). Skull Arena 1.1 (Skull N. Bones, AVA league) scored highest
of the Gold maps (LD + AVA) but is a bare 8-object league box; it is the pick if the owner wants a pure duel arena. **Nothing goes into any list beyond these 10** (owner rule);
the lab twins hold 4 / 3 extra test files that never leave the lab.

## 4. Experiments (lab copies only)

Console runs on the PC (session `console` Active, not RDP), lab `.console-owner` taken per boot, the game muted per pid
(`I76_MUTE` + start-mute-watch), private shm suffix. Scripts: lab `tools\content-trial\` (`arena-trial.ps1`,
`arena-nav.ps1` = `tools\replay\melee-nav.ps1` + an arena-index write, `car-swap.ps1`, `nitro-trial.ps1`,
`nitro-host-trial.ps1`, `editor-session.ps1`, `p20-stub.py`); runs in `tools\content-trial\runs\`. Gold copy: `exp-content-gold`
(i76.exe 9a232dcc-family as in exp-polish2, its STRLKUP.DLL, preset OWNER-2300-ALL minus the cursor-map keys so the menu
clicks land 1:1); its own 24 add-ons (`auto*`, `coop*`) parked in `ADDON\_parked` so the test maps are indices 15-19.
"Crash lines 3" in every Gold run, the T01 control included, are three `coop-ai ... UNEXPECTED bytes - not patching` lines
of that proxy build against this exe, not crashes.

### 4.1 (a) Community arenas

**Gold, Instant Melee route** (main menu > MELEE > AUTO MELEE > INSTANT MELEE, arena index written to the form's slot
`[i76shell+0xd4474]`, ENTER AREA, then 60 s of W held 0.9 s + A/D weave every 5 s; 1 boot each):

| idx | file | the shell's list record (read from memory) | loaded (exe 0x5049f0) | WRLD far clip read | 60 s | max speed |
|---|---|---|---|---|---|---|
| 15 | `76prcnct.lvl` (converted) | '76th Precinct' | yes | - | alive | 6.3 m/s |
| 16 | `leather.lvl` (converted) | 'Leathertown' | yes | - | alive | 14.5 m/s |
| 17 | `rageco.lvl` (converted) | 'Rage County' | `rageco.lvl` | 600 | alive | 9.7 m/s |
| 18 | `ragecoraw.lvl` (**published file, unchanged**) | **'' (empty row)** | `ragecoraw.lvl` | **31092** (predicted 31092, s.2) | alive | **0.0 m/s: the car never moved** (position identical in all 12 samples) |
| 19 | `tmesas.lvl` (ARSEDIT export, s.4.3) | 'Twin Mesas, TX' | `tmesas.lvl` | 600 | alive | 3.9 m/s |

- The list count was 20 (15 stock + 5 add-ons). The arena-list screenshots do not show the add-on rows (the form does not
  redraw after a memory write); the titles above are the shell's own records, which is what it draws.
- Picture (`drive-17-2.png` vs `drive-18-2.png`): the converted map draws sky, horizon and mirror normally; the raw file
  draws the scene in a box with black above it (no horizon: its horizon name is the byte 0x09) and an empty mirror, at
  ~85-90 fps against ~95-105 for the converted map (frame counter steps per 5 s after the first: 411-443 vs 463-525; the
  far clip read from the title bytes is 31 km; n 1, the fps cap and other lanes' load not controlled). It is daylight in both: the shifted "hour" did not visibly give night.
- Low speeds in the arenas are the scripted weave in built-up spawn areas (the T01 control on a road reached 26.6 m/s).

**Repeat (01:05-01:12, same copy, alternating):** raw `ragecoraw.lvl` 2 more boots: alive, **0.0 m/s again** (n 3 of 3,
the car never moves; same spawn 1697.5 / 49372.5 each time). Converted `rageco.lvl` 2 more: one alive (3.8 m/s), **one
crash at 52 s**: `0xC0000005` at EIP 0x442C0FCC (a jump into data; ebp corrupt), return address 0x00401CAD on the stack,
in the exe function whose site 0x401CFE this proxy build reports as `coop-ai ... UNEXPECTED bytes - not patching`
(the 25/27 double-hook that main fixed in 7a7dbb6; exp-polish2's DLL predates it). Stock control (The Crater, index 0):
alive, 44.4 m/s. **Gold Instant Melee boots: 10 (9 add-on, 1 stock), 9 alive 60 s, 1 crash** (converted Rage County, 1 of 3), not attributable to the
map on this evidence: re-run the 5 maps on the current proxy (n 3 each) before the pack.

**Nitro.** Direct boot is not a route for arenas: `I76_MISSION=n01.cbt` (stock) and `gumball.cbt` / `intercpt.cbt` /
`goval.rac` all stop at nitro.exe's **"Unhandled Exception"** box with no player (the same as Gold's melee arenas, whose
players come from the shell's melee setup). So the arenas were **hosted the way a player hosts them**: nitshell's network
HOST form, arena chosen by file name, BROADCAST, the host alone, by the nitro-mp lane's instrument (`nmprun.py` + `nmpdrv`
with `NMP_POC=2` = control, stock form, nothing added) in a fresh twin `exp-content-nitro-mp` of `exp-nitro-mp` (GOG
nitro.exe 28b8ae27 + dgVoodoo; **not** our proxy, which `exp-content-nitro` carries):

| arena | combat list (26 entries) | state | player from | sim time | exit |
|---|---|---|---|---|---|
| `n01.cbt` (stock control) | index 2 | 5 (mission) | 19.2 s | 61.25 s | none (stopped by the harness) |
| `gumball.cbt` | index 0 | 5 | 19.2 s | 60.75 s | none |
| `intercpt.cbt` | index 1 | 5 | 19.2 s | 60.75 s | none |

The host car was not driven in these runs (the instrument holds). `goval.rac` sits in Nitro's race list, which this
driver does not open; it is staged but unhosted. The titles are the files' own WRLD titles (Gumball Rally, IntercptPursuit,
Great Oval; Nitro reads them with the same callback as Gold).

### 4.2 (b) A community car and an unused shipped vehicle

Route: a mission entered without the shell gives the player `vppirna1.vcf` (<re-archive> `subsystems/mission.md`), and the VFS
looks in `ADDON\` first, so `ADDON\vppirna1.vcf` decides the car (`car-swap.ps1`). Direct boot into T01, 60 s, 1 boot each:

| run | `ADDON\vppirna1.vcf` | what drove | max speed | result |
|---|---|---|---|---|
| 0 | none (control) | stock Piranha | 26.6 m/s | alive, drove 844 m |
| 1 | `vdillo1.vcf` from Gold's own `I76.ZFS` (**Armadillo**: `varmdilo.vdf`, `dillo1.vtf`, `wdilo_1a.wdf`, all shipped, never placed) | the Armadillo: no cockpit, camera at ground level (`drive-1-2.png`) | 11.0 m/s | loaded and drove; T01's script failed the mission at ~45 s ("keep up with Taurus") - too slow |
| 2 | hop76 v3 `Vlimo1.vcf` + `Vlimo.vdf` + `limo1.vtf` (**community Limo**, stock geometry, 5 x 7.62 MG) | the Limo with a full cockpit HUD (`drive-2-2.png`) | 17.7 m/s | drove 505 m, rolled, mission failed the same way |

Not tested live: the garage list. Adding a car to the melee garage is one 28-byte record in `i76car.def`
(`{id, u32, variant count, name[16]}`, 23 records stock; hop76 adds `vdillo` id 29 and `vlimo` id 32 with 1 variant).
Placing the Armadillo as a mission vehicle is an ODEF entry (class 8/9) like any other car.

### 4.3 (c) The official editors on this Windows

Copied into their own folders (`tools\content-trial\editors\arsedit`, `\builder`), Defender scan of the folder: "found no
threats". Neither imports any network API (KERNEL32, USER32, GDI32, comdlg32, COMCTL32, MSVCRT only). Both were run on a
**private desktop** (`tools\whole-sim-tick\deskrun.py`) and driven by window messages (`editor-session.ps1`: WM_COMMAND for
the menu, WM_SETTEXT into the file dialog, BM_CLICK), so the console was never touched. (A first ARSEDIT start on the
console desktop, before this was set up, came up maximised for ~10 s while another lane held the console; stopped.)

| step | ARSEDIT ("I'76 Nitro Editor rel 2/17/98 v0.098b", About "I77edit") | I76EDIT ("Interstate '76 Editor rel 3/06 v0.097a") |
|---|---|---|
| starts on Windows 10 | yes | yes |
| Open the community project `Tmesas.i76` (LSM `twnmes.zip`, 13 MB, Disco .45's Twin Mesas) | opened (title bar shows it) | opened |
| Export | `TMESAS.MSN`, 100,146 B: **WREV 9**, WRLD 331, horizon '', title "Twin Mesas, TX", ODEF 144 objects | `TMESAS.LVL`, 100,277 B: **WREV 8**, WRLD 318; same size and chunk layout as the author's 1997 `.lvl` (8,190 bytes differ, from the ZONE name's case on; not decoded) |
| Open a game mission (stock `M01.MSN` / the ARSEDIT export) | refused: *"... is not an Iterstate '76 Mission file!"* | refused (File Error) |
| the exported file in Gold | listed "Twin Mesas, TX", loaded, 60 s alive (s.4.1 idx 19) | (its output is the raw layout of idx 18) |

Not verified: the editors' map canvas (blank in PrintWindow captures on the private desktop; editing needs the real
console). ARSEDIT's file filters also offer `.I77` projects and `.FSM` import. **Conclusion:** both editors work for
building new maps and re-exporting old projects; they cannot open game missions, so they are not an editor for the stock
or our own missions. Only 6 community `.I76` projects survive in the archive (BeAsT, Creep009, thechasm, Tmesas, cprace,
ghosttwn).

### 4.4 (d) P20

- On disk (Gold and Nitro ZFS): **only `p20.npt`**. No `p20.msn`, `.ter`, `.rtm`, `load.pcx`, voice or script. nitro.exe
  builds `p%02d.msn`; the campaign stops at P19.
- **`p20.npt` is an earlier draft of P19**, not a separate mission: P19 "Assassinate the CEO! Take out his limo before it
  reaches the compound! / (HIDDEN) Get back to the airfield. Rendezvous with Hell Toupee in the chopper"; P20 "Assassinate
  the governor (he's the guy in the limo, twinkie). / (HIDDEN) Get back to the helicopter at the airport ... / (HIDDEN)
  Make sure to park next to the 'copter". The failure lines are the same six in the same order (P20 lacks P19's last one,
  "You gotta be quicker!").
- **Smallest runnable P20** (`p20-stub.py`, in `exp-content-nitro` only): P19's mission with its WRLD objectives field
  pointed at `p20.npt` and the title "P20 Governor", plus copies of P19's `.ter`/`.pcf`/`.rtm`/load screen under p20 names.
  Direct boot `I76_MISSION=p20.msn` (Nitro, our proxy): loaded, drove 328 m at up to 27.7 m/s, the car was destroyed at
  ~15 s by the mission's enemies ("You have shuffled off this mortal coil", a line both files share), game alive at 61 s.
  P19 control: the same (442 m, 27.8 m/s). n 1 each. The P20 objective line itself was not captured on screen.
- A real P20 (the governor, the airport helicopter, the "park next to the copter" objective) is a re-scripted P19:
  `fsmtool` edits of P19's script for the third objective, about a week with testing.

## 5. Licensing

- Game assets (the 3 vehicles, voices, German dub, FRC, P20 text): Activision's; using them inside the owner's own
  installs is fine, a public pack ships none of them as files.
- Community maps and cars: the authors' (handles). The Gold readmes allow free non-profit distribution with all files kept
  together; ARSEDIT's licence forbids commercial use of missions built with it. Great Oval's Nitro port says it was made
  without DIVER's consent. **Working rule unchanged: keep it private, credit every author, link rather than rehost**, and
  ask active authors (DIVER, Debacle, Skull N. Bones, Stinger) before a shared pack.
- Bullmark demo tracks: unreleased recordings; owner's private use only until rights are cleared.
- hop76 exists to make cheat cars visible online; a shared pack should not ship it wholesale.

## 6. Plan (prioritised) and decisions for the owner

1. **Gold LAN arena pack v1 = the 5 Gold maps of s.3**, converted with `arena-pack.py`, lower-case, with readmes; one play-test
   each on the test copy (spawn, regen, 2 humans), then the pack (every machine, CRC-checked). *Lane: half a day.*
2. **Nitro arena pack v1 = the 5 Nitro maps**, for the Nitro MP build; Great Oval only after DIVER is asked (or swap in
   RepoTown USA). *Half a day.*
3. **M13 objectives fix** in the next promotion (one field, both mission folders). *15 min + test.*
4. **SideWinder FRC A/B** to the FFB lane (folder swap).
5. **ARSEDIT trial map** (1 day): a small arena using the unplaced scenery (cemetery, helipad, tunnels), exported, checked
   with `bwd2x`, played; establishes the new-content pipeline.
6. **Novelty / unused cars as a host option** (needs a lane): `i76car.def` records + `ADDON\` files on every machine;
   start with the Armadillo and the AVA "Division" loadouts; a real garage test is still open (s.4.2).
7. **P20 proper** (a week, needs a lane): P19 re-scripted with the governor text and the "park by the copter" objective.
8. **German voices** as a private language pack (hours) if the owner wants it; German text needs proxy work (STRLKUP).
9. Later lanes: "Interstate '77" (weeks), extra music tracks 18+ (proxy TOC), unused voice lines inside new missions.

**Decisions needed:** (a) may the 10 maps go into the LAN pack's list as-is (private pack, credited, converted files), or
only after authors are contacted? (b) Great Oval (consent note) or RepoTown USA? (c) Bullmark tracks: private use at all?
(d) German voices pack: wanted?
