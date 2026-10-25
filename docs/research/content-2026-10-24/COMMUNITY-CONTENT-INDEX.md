# Community content archive: what we fetched, what is in it, how we might use it (2026-10-24)

Follows [archives-and-community.md](archives-and-community.md) s.7 ("ten to fetch first"), plus
[development-and-press.md](development-and-press.md) and [game-files-and-cast.md](game-files-and-cast.md). Downloads and
file work only: no game was started, no downloaded program was run.

- **Store:** `D:\i76-archive\community-20261024\` (`dl\` = the downloads as fetched, `x\` = each archive extracted into
  its own new folder, nested archives into `<name>.x\`, `index\` = full index incl. `files.csv` and `maps.json`).
  Nothing from it is in git.
- **Index (in git, machine-readable):** [index/](index/) - `maps-unique.csv`, `maps.csv`, `cars.csv`, `paints.csv`,
  `tools.csv`, `audio.csv`, `frc.csv`, `summary.json`, `downloads-manifest.csv` (URL, size, sha256, date per file),
  `extract-log.csv`. Author e-mail addresses found in readmes were removed from the committed copies.
- **Scripts:** [tools/content-archive/](../../../tools/content-archive/) (`fetch.py` polite sequential downloader,
  `extract.py` 7-Zip extraction, `index.py` indexer over the data track's parsers, `post.py` map grouping, `bin2iso.py`,
  `zfslist.py`). The parsers in `i76-map\data\fmt` were imported read-only.

## 1. What we now have

**760 files fetched, 2.64 GB** (sequential, 1.5-2 s apart, one retry; `interstate76.com/forums/blackhole/` never
requested). Extracted and indexed: **10,472 files, 5.0 GB** (includes the earlier `refs\route380` mirror, read in place
for de-duplication).

| source | files | MB | what |
|---|---|---|---|
| SideWinder compendium Disk 1 (archive.org, single members via `view_archive`) | 17 | 0.5 | **14 FRC force effects + I7_SFrce.dll**, BUILDER (I76EDIT.EXE + BUILDER.DOC) |
| interstate76.com `/download/` | 12 | 117 | allnitromaps.zip, DIVERmappack, builder.zip, **arsedit.zip**, ChopShop 1.9, avautils, Nitrace 5.7, Intertrace, Auto Guide, map-guide/review, audio ALL.ZIP |
| LSM (Lightfoot's Stolen Maps), I'76 + Nitro groups | 526 | 98 | every live I'76 (`i76comb1-5`, `i76race`, 227 zips) and Nitro (`exclusive*`, `combat1-3`, `racing1-2`, `ctf`, 299 zips) map; I'82 groups skipped (other engine) |
| King's Custom Rods (Wayback 2005-2026) | 35 | 3.5 | 17 car mods, 2 Nitro cars, 7 paints, hop76 v3, VCFgen, paktool, ChopShop, AVA Car Designer, hack76, jwzfs, bpatch76, Nitro patch-1 exe |
| AVA (Wayback 1999-2006) | 59 | 15.3 | 37 Paint Shop skins, utilities (addonbuilder, dizyna, PL/Price Manager, qstart/qnitro car sets, 12 small league maps, 1.06/1.081 patches) |
| Local Ditch | 30 | 45 | 18 maps (incl. `all-in-1`, `zenstuff`, dead on LSM), `i76_preview.zip`, `nitro_preview.zip`, map images, Gold DATABASE.MW2, theme, wallpapers, demo movies |
| archive.org `Interstate.76` | 1 | 110 | a played-in Nitro install with ~250 community maps + `Map Text Files` |
| archive.org `Interstate76-Soundtrack` | 1 | 597 | Game Disc (20 FLAC), OST (32 FLAC), **Bullmark Demo (24 mp3)**, 15 poems |
| archive.org `Interstate-76-Deutsch` | 5 | 843 | German retail CD1 + CD2 images |
| archive.org `score35cd` | 2 | 740 | Score #35 (Nov 1996, Czech) coverdisc |
| archive.org `Arsenal_201610`, `Interstate76_1020`, `i-76voices`, `interstate76mapimages` | 72 | 73 | Arsenal demo, I'76 demo, 507 voice wavs, 69 overhead map PNGs |

Not fetched or not usable: `crash2kill 1.0.zip` (404 live, as the catalogue said); AVA `1969.zip` and `olds_ho.zip`
(Wayback holds an HTML page, not the zip); SideWinder Disk 1/2 rars whole (only FRC/BUILDER needed; the rest is the
retail game and three unrelated Activision demos); `i76Sidewinder` (1.34 GB, same edition); Outlaws alpha, I'82
material. Eight LSM zips are corrupt on the server (7-Zip CRC/data errors, list in `extract-log.csv`: `gunfire`,
`takeoff`, `r66scen`, `trestle`, `veldt`, `orspeed`, `pgh2`, `sstream4n`); most of them have intact copies in
allnitromaps or the `Interstate.76` install.

**Defender:** `MpCmdRun -Scan -ScanType 3 -File D:\i76-archive\community-20261024` (report-only) after extraction:
**"found no threats"** (2026-10-24). InstallShield payloads (Arsenal demo `data1.cab`, avautils `_SETUP.1`, Nitrace,
Intertrace, PriceManager) were not unpacked further; self-extracting zips (avautils, qstart, qnitro, patches) were
opened with 7-Zip only.

## 2. The index

### Maps (`maps.csv` = every mission file seen, 2,360; `maps-unique.csv` = one row per map, 528)

Every mission file went through `bwd2x.decode` (the data track's byte-exact BWD2 layouts): WRLD (title, terrain
texture, sky, CD track, hour, far clip), ZONE (.ter names), ODEF (object count and labels), LDEF, RSEG, FSM action
names. Copies are matched by sha256 (`dup_group`), stock files by hash against the GOG Gold and Nitro sandboxes
(`stock` column; the stock N/M/T/P missions inside the `Interstate.76` install are flagged, not counted), and the
8-bit / 16-bit and cross-source variants of one map are grouped by `stem|terrain` (`maps-unique.csv`).

| | I'76 / Gold (.lvl) | Nitro (.cbt/.rac/.cf*) |
|---|---|---|
| unique community maps | **201** (198 melee, 2 race, 1 CTF) | **327** (184 combat, 117 race, 26 CTF) |
| static check passes for Gold `ADDON` | 189 | 207 (as melee) |
| loads in Gold but the mode's rules are Nitro-only (race checkpoints, CTF team spawns) | 3 | 104 |
| needs Nitro-only assets (Nitro .vcf / .gdf) | 0 | 15 |
| terrain file missing from every copy | 9 | 4 |
| only on LSM (no other surviving copy found) | 147 | 2 |
| with an author found in a readme | 339 of 528 overall (regex over the readmes; noisy, check by eye before crediting) | |

What the verdict means (column `gold_verdict` / `best_verdict`; **all static, nothing was played**):
- `gold-static-ok`: every .ter is in the pack or stock; every FSM action is one of the 96 Gold prototypes; at least one
  plain `spawn` label (what Gold's 8-character compare accepts, `data\notes\nitro.md` s.2).
- `gold-loads; race/ctf rules are Nitro-only`: `checkN` and `#spawnN` labels are Nitro features; in Gold those records
  are dropped (a class-1 car named `check3` fails its .vcf load), so the map is a melee arena at best.
- `nitro-only`: references a Nitro-only .vcf/.gdf (e.g. `gs4get.gdf`, `ggchem.gdf`, Nitro novelty cars).
- `risk: missing art X (untested)`: a WRLD texture / map-screen / horizon name that resolves nowhere (typos such as
  `zmap6moo.map`, `zmzp3m00.map`); 37 maps. What the engine does with a missing map screen is not known.
- `drops objects (...)`: object labels with no .sdf/.vcf anywhere (82 maps); the loader skips them silently.

**Correction 2026-10-25 ([CONTENT-FEASIBILITY-2026-10-25.md](../../CONTENT-FEASIBILITY-2026-10-25.md) s.2):** the WREV 8
WRLD is 318 bytes and does carry the author's title (at +0x12e); what it lacks is the 13-byte horizon name at +0x86, so
Gold/Nitro read every later field 13 bytes off (hour, surfaces, far clip, title). `tools/content-archive/arena-pack.py`
converts. The paragraph below is the original reading.

**Format finding:** 409 of the 2,360 mission files (every LSM `i76comb*` arena and the 1997 Activision bonus maps)
have **WREV 8 and a 315-byte WRLD** - the I76EDIT 1997 layout, which stops before the 16-byte mission title at +0x13b.
Gold/Nitro files are WREV 9, 331 bytes. Gold's arena list reads the title from +0x13b
([records/COOP-LIST-ENTRIES-2026-10-18.md](../../records/COOP-LIST-ENTRIES-2026-10-18.md)), so for these maps it reads
past the chunk (into the next chunk header) and will show a garbage or empty name. A pack build should rewrite WRLD to
WREV 9 with a real title (our parsers serialise WRLD byte-exactly).

Biggest I'76 arenas with an author in the readme (objects / spawn / regen): `foose3` Fookill [Brian Foose] 266/1/0,
`joad` Thomas Grob 253/9/2, `thrill1` Groove [DEG-L] 250/8/2, `bigville` Lt. Stinger (TBP) 224/9/4, `rageco` General
Rage 208/8/2, `h_n_s` WeaponX 206/8/2, `loswypro` Stinger 203/9/23, `all-in-1` Skull N. Bones 194/8/0 (Local Ditch only),
`doomvlly` Evicerator 177/10/2, `snake` "Snake Rally" Debacle 153/6/1, `oak` The Hunter, `tmesas` Disco .45, `dderby`
WeaponX, `76prcnct` Stingray, `rallyv` Mad Dog. Nitro: `overkill`, `city` "Regen City", `ghost_pk`, `judge`, `p_valley`
(raven), `pipe`, `gold`, `plant`, `blind`, `sparkle` (ATOMIC MONKEY), `test` "Biggsville" (Captain Stinger), `repo`
"RepoTown USA" (Debacle), `pheaven` (Skull N. Bones), `mofo`, `cmvalley`, `mojave`, `blachs`, `grumpy`.

### Cars (`cars.csv` 116 .vcf, 109 non-stock; `paints.csv` per pack)

- **hop76 v3** (King's Custom Rods): 42 drivable novelty and hidden vehicles - UFO, phone booth ("Bill & Ted"), cactus,
  do-nut, hut, shack, rocket, limo, monster truck, three dragsters, armed armadillo, armed tractor, pole turret,
  **Howitzer** - with their own .vdf/.geo/.tmt/.gdf and a replacement `I76car.def`. All chassis parse; several use
  texture set `NULL` (untextured models).
- **King's lowriders and specials:** 13 zips are chassis replacements only (`.vdf`: lowered Clydesdale, Courchelle,
  Cavera, Royale, Jefferson, cop, Cuda, Palomino, Rabbit, Volvo/Vikea, crew-cab dually, salt-flat coupe, convertible
  Royale + .vtf). A replaced stock .vdf changes every car on that chassis and is part of the MP join CRC.
- **pickup_camper:** Plow Truck, Armydozer, Bulldozer, "Farmer John" tractor (new .vdf + .pak).
- **AVA league sets** (`qstart.exe`, `qnitro.exe`): 2 x 23 balanced loadouts by division (5 .. 30 = $5k .. $30k
  budgets) - ready-made MP car classes. Two reference Nitro weapons (`gs4get.gdf`, `ggchem.gdf`).
- **Paint jobs:** 37 AVA Paint Shop skins (camaro, General Lee, police / taxi / VW bus, Tim Hortons, Target ...) and 7
  King's paints (Charger 1.8 "General Lee", Interceptor / Black Mad Max, Ferrari F376, camo Clydesdale ...).

### Tools (`tools.csv`, 19 entries)

The finds that matter: **ARSEDIT, the official Arsenal Mission Builder** (`arsedit.zip`: exe + a 3.2 MB *Editor
Guide*, `objects.xls`, `mission info.xls`). The guide documents terrain painting, surface types, roads, **AI paths**,
labelled objects and vehicles "useful when referencing it in AI scripting", **.FSM import**, race checkpoints
(`check1..N`, "place about six pixel squares in front"), CTF bases (`BHWTOWR2-5` towers, `A1FLAG1-4` flags, Red and
Green first), and the 8-bit/16-bit double export with `.MSN -> .CBT/.RAC/.CF2-4` renames. Its readme allows free
distribution of missions and forbids commercial use. I76EDIT 1997 is identical across builder.zip, the SideWinder disc
and GOG Gold; its BUILDER.DOC differs by one day between builder.zip and the SideWinder disc.

### Audio (`audio.csv`, 1,192 files with durations)

| set | tracks | minutes | note |
|---|---|---|---|
| OST CD (FLAC, AccurateRip log) | 32 | 51.0 | 18 titles not on the game disc ("In the Junkyard", "Roswell", "Helicopter Fuzz", "Stampede", "Macadamia Medley" ...) |
| Game Disc (FLAC) | 20 | 47.1 | = the game's CD audio |
| **Bullmark Demo (mp3)** | 24 | 48.2 | unreleased session/demo tracks: "DESTRON Super Jam" 3:36, "Tossed Salad" 3:30, "Can You Feel My Spacium Ray Tonight" 3:19, "The Crab Style" 3:08, "Spam Jammies" 2:48, "Henshin V3!" 2:54 ... (nine are "Track N" untitled) |
| poems (wav) | 15 | 5.1 | Taurus's poems |
| interstate76.com ALL.ZIP | 32 | 51.0 | mp3 of the OST (lossy duplicate) |
| i-76voices | 507 | 41.3 | GOG voice lines (duplicate of our own data) |
| **German retail voices** (from the German I76.ZFS) | 538 | 46.2 | 495 share a name with Gold's ZFS, **487 of those differ** = the German dub; plus German `.npt` objectives and a 43 KB `LANG.TXT` (shell strings, English -> German) |

### FRC force effects (`frc.csv`) - for the FFB lane

**Path: `D:\i76-archive\community-20261024\dl\compendium-disk1\FRC\`** (14 `.FRC` + `I7_SFrce.dll`, 1997-05/08 dates).
All are DirectInput `RIFF`/`FORC` files, one effect each ("UserDefined1" custom-force samples). Against the GOG set
(`<install>\force\*.FRC`, identical in GOG Gold, GOG Nitro, the golden copy and the archive.org Nitro install):

| same bytes | differ (same size) |
|---|---|
| EXPLOSN, MISSIL45, WPNCYCLE, WPNLINK, WPNUNLNK | CANNON1-4, ENGSTART, MISSILE2, MISSILE5, TIREBLWL, TIREBLWR |

The differences are small (mostly +-1 in the custom-force sample table, a few header parameters) - an earlier tuning
pass, SideWinder pack-in vs the shipped set. The two `I7_SFrce.dll` differ too (compendium 508fa2de..., GOG a7e876b2...).

### Pre-release and other finds

- **Score #35 (Nov 1996, Czech) coverdisc:** 15 I'76 screenshots `CD\DI\INTE7600-7614.PCX` (dated 1996-10-12) and a
  Czech preview text. The shots are pre-release: an in-car view with a large green radar disc on the dash and no damage
  readout (the "radar-only HUD"), an in-car shot of a hand firing a pistol out of the side window (the cut handheld
  weapons), a big rig on a Route 66 road, a junkyard of stacked cars, cutscene-style renders of Groove, Taurus and
  Skeeter (Taurus with a baseball bat). Extracted to `x\ia\score35cd\i76-files` (PNG copies in `png\`).
- **`i76_preview.zip` (Local Ditch): `I76.AVI` dated 1996-07-31**, 9.8 MB, CRAM video - the earliest pre-release footage
  we hold (MechWarrior 2 Mercenaries disc). `nitro_preview.zip` (1997-09-23) is the Nitro trailer.
- **German retail:** CD1 is a 1.0-era build (I76.ZFS 3,875 entries vs Gold's 6,116; 478 names not in Gold, mostly
  voice lines), CD2 holds 29 German cutscenes and the MISSIONS folder.
- **Arsenal demo:** its data sits in InstallShield 5 cabs that 7-Zip cannot open; it is already covered in
  [records/I76-VERSIONS.md](../../records/I76-VERSIONS.md).
- `interstate76mapimages` (69 PNG) and Local Ditch `i76_maps.zip` / `nitro_maps.zip`: overhead maps of every stock level.

## 3. Licence notes

No archive states a licence (ARSEDIT's readme is the only rule text: free to pass missions on, no commercial use). Game
assets are Activision's; maps, cars and skins belong to their authors, mostly known by handle. Working rule, unchanged:
**keep the archive private, credit authors, link rather than rehost**; ship nothing third-party in a public pack
without the owner's ruling, and prefer packs built from our own work plus links to the originals. Disc images (German
retail, Score #35) are reference only.

## 4. How we might use it

**Arena packs for the Gold LAN.** Gold lists `addon\*.lvl` and reads each title from WRLD +0x13b; the 189 I'76 maps
that pass the static check are the candidates. Build steps a pack needs: lower-case file names (the Mac/Deck rule from
the co-op pack), WRLD rewritten to WREV 9 with a title for the 409 WREV-8 files, the .ter (and .npt) beside the .lvl,
identical files on every machine (the join check rejects mismatched mission files). Nitro combat maps (`.cbt`) can join
the same list renamed to `.lvl` (the route380 rule) when they pass; Nitro race and CTF maps are melee-only in Gold.

**Nitro MP.** The 327 Nitro maps are native: `.cbt/.rac/.cf2-4` in `miss8` + `miss16`, `.ter` in `addon`
(`nitshell.dll` also reads `addon\*.cbt|*.rac`). allnitromaps.zip and the archive.org install are already laid out
that way; 15 need Nitro-only assets and are only for the Nitro build.

**Custom cars.** hop76's novelty vehicles and the AVA division sets are the quickest wins: the AVA sets are balanced
MP classes (a host could offer "Division 10" etc.), hop76 gives fun one-offs. Every .vcf already parses with our
`i76mod.py`; chassis (`.vdf`) replacements need care because they change all cars on the chassis and the join CRC.

**New missions.** ARSEDIT plus our FSM assembler (`data\fmt\fsmtool.py`) is a full mission pipeline: ARSEDIT for
terrain, roads, AI paths and placement; `fsmtool asm` for the script. Candidates: the cut Nitro mission **P20**
("assassinate the governor", text survives in `p20.npt`), and the **"Interstate '77"** epilogue (Taurus vs The
General, Mexican oil smuggling; CGW #158) as a short campaign on existing terrains, using the never-placed vehicles
(Armadillo, Howitzer - hop76 has drivable versions to study).

**FFB.** Two effect sets now exist for A/B: the shipped GOG set and the SideWinder pack-in set (9 of 14 differ). The
FRC files give the authored shape of each effect (cannon recoil, tyre blow-out, engine start, missile launch) for the
FFB lane's mixer.

**Music.** The 24 Bullmark demo tracks and the 18 OST-only cues are period funk by the same band; they could score new
missions through the music proxy (CD-track substitution). Licensing is the blocker: private use only until the owner
decides.

**Cut content.** Score #35 shots and the 1996 preview AVI show the pre-release HUD and handheld weapons; the German
build is a second 1.0-era data set to diff against our retail 1.0 reference.

## 5. Plan (prioritised)

1. **Hand the FRC path to the FFB lane** and A/B the SideWinder vs GOG effect sets on the wheel (test copy only).
2. **Gold LAN arena pack v1:** pick 10-15 of the 189 statically-OK I'76 arenas with credited authors (start with the
   list in s.2), rewrite WREV 8 -> 9 with titles, lower-case names, then play-test each in the test copy (load, spawn,
   regen) before the pack goes to the machines.
3. **Nitro arena pack v1** from allnitromaps / the archive.org install: 20 combat + 10 race + 5 CTF maps, credited, for
   the Nitro MP build.
4. **ARSEDIT trial:** read the Editor Guide, export one small arena and one scripted test mission, round-trip both
   through `bwd2x` and `fsmtool`; confirm ARSEDIT output loads in Gold and Nitro.
5. **P20 "Assassinate the governor"** as the first new mission (existing Nitro terrain + `p20.npt` text + a new FSM).
6. **AVA division car classes** as an MP host option (the 23 qstart loadouts), and a hop76 novelty-car side pack
   (test copy first; it replaces `I76car.def`).
7. **"Interstate '77" outline:** 3-5 missions on stock terrains, The General's convoy, the cut vehicles; Bullmark demo
   tracks as score (private until licensing is ruled on).
8. **Pre-release study:** frame-grab `I76.AVI` (1996) and compare the Score #35 shots with the shipped HUD and weapons;
   add findings to development-and-press.md.
9. **German data set:** diff the German 1.0 ZFS/missions against our retail 1.0 reference; offer German voices as an
   optional language pack for the owner's own installs.
10. **Ask the community** (I'76 Discord, UltraFunk) about the 13 maps whose terrain is lost and the 8 corrupt LSM zips,
    and about permission from active authors (raven, ATOMIC MONKEY, Debacle, Skull N. Bones, Stinger) to include maps
    in a shared pack.
