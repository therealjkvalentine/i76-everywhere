# Additional content for I'76 expansions: archives and community sources (swept 2026-10-24)

Scope: every surviving source of content beyond the stock games (missions, arenas, cars, paint jobs, voices, music,
textures, tools) for Interstate '76 / Gold / Nitro Pack / Arsenal. This extends
[COMMUNITY-RESOURCES.md](../../COMMUNITY-RESOURCES.md) and [COMMUNITY-SITEMAP.md](../../COMMUNITY-SITEMAP.md) (2026-08-09)
and [records/COOP-LIST-ENTRIES-2026-10-18.md](../../records/COOP-LIST-ENTRIES-2026-10-18.md) s.4 (where "Lightfoot's
Stolen Maps" was "a frameset, list not readable"). Nothing large was downloaded; every "live" claim below is an HTTP
HEAD or 1-byte range request made on 2026-10-24, every archive.org file list comes from the item's metadata API or
its `view_archive` listing. Companion data file: [lsm-map-files.tsv](lsm-map-files.tsv) (639 map zips, URL and size
or ERR).

**Licence, all sources:** none of the fan sites or archive.org items states a licence (the one exception is an
unrelated CC-BY road-sign model). Game assets are Activision's; fan maps, cars and skins belong to their authors, most
of whom are known only by handle. Working rule for this public repo: **link, do not mirror**; fetch into git-ignored
`refs/` for study; anything shipped in a pack needs the author's handle credited and, for the big archives, the
owner's ruling. archive.org copies of the retail discs are not redistributable by us at all.

## 1. Grand Funk Highway (GFH) - what actually survives

- Real URL: `grandfunkhighway.com` (also `www.`). An Interstate '76 **gang** (clan), founded 24 May 1997 by
  "Airbuddha" with Wolfe; leader later The Wraith. Closed as an I'76 gang 13 March 1999 and turned into a Starsiege
  Tribes clan; the domain lapsed to a parking page by 2002.
- Wayback: 70 unique URLs, captures 1998-12-02 .. 2006. **No downloads were ever captured** (no zip/exe/lvl in the
  CDX; every capture is html/gif). The 1998 front page is a NetObjects frameset whose body frame (`body_index.html`)
  was never crawled.
  - root, last I'76 statement: http://web.archive.org/web/19990428020625/http://www.grandfunkhighway.com/
    ("The Interstate 76 GFH gang has officially closed it's doors ... May 24, 1997 - March 13, 1999")
  - history: http://web.archive.org/web/20010107195800/http://grandfunkhighway.com/html/about.html
  - roster (handles, ICQ, join dates): http://web.archive.org/web/20001027184848/http://grandfunkhighway.com/html/members.html
- Expansion value: **none in content** (lore / community history only). Don't spend more time here.

## 2. interstate76.com (Lightfoot) - the live hub, and its map archive is now enumerated

Everything below answered 200 on 2026-10-24. **Do not fetch `/forums/blackhole/`** (the footer link is a bot trap
that bans the client). Forums block bots; use Wayback (see COMMUNITY-RESOURCES s.3a).

### 2a. "Lightfoot's Stolen Maps" (LSM) - http://www.interstate76.com/lsm/index.htm
Frameset; the real index is `lsm/links.htm`, which links 19 archive pages. Crawled all of them: **639 map zips, 626
live (131 MB total)**, full list in [lsm-map-files.tsv](lsm-map-files.tsv).

| group | pages | zips | dead | size | engine |
|---|---|---|---|---|---|
| Nitro (`exclusive*`, `combat1-4/no3comb*`, `racing1-2/no3race*`, `ctf`) | 10 | 300 | 2 | 70.8 MB | **Nitro** (`.cbt/.rac/.cf*` + `.ter`) |
| I'76 (`i76comb1-5`, `i76race`) | 6 | 235 | 7 | 26.7 MB | **I'76 / Gold** (`.lvl` + `.ter`) |
| I'82 (`i82comb1-3`) | 3 | 104 | 3 | 33.9 MB | I'82 only - different engine, no value to us |

Dead links (404 live and 404 in Wayback 2007): `i76comb1/{all-in-1,bobypind,cruzcnty,nukewntr,river}.zip`,
`i76comb3/2tracks.zip`, `i76comb5/crash2kill 1.0.zip`, `i76race/zenstuff.zip`, `combat1/clonecyn.zip`. Two have
other copies: `all-in-1.zip` and `zenstuff.zip` on Local Ditch (s.5); `racing1/hillclim.zip` has a Wayback copy
(20070701122857). The Activision bonus maps are here too: `i76comb2/miner.zip` (= Activision's `miners_ridge.zip`,
~100 KB) and `i76comb4/elim1b.zip`.
Expansion value: **highest single source of arenas** (combat, race, CTF) for both engines; authors in each readme.

### 2b. Downloads - http://www.interstate76.com/download/ (sizes = live Content-Length)

| file | size | what | value |
|---|---|---|---|
| `allnitromaps.zip` | 58.6 MB | "All Nitro maps" collection (Wayback copy 2016-12-23 also resolves) | arenas, Nitro |
| `DIVERmappack.zip` | 1.07 MB | DIVER's Nitro map pack | arenas |
| `builder.zip` | 114 KB | **Interstate '76 Map Editor** (official MP mission builder `I76EDIT.EXE` + `BUILDER.DOC`, same as Activision's `multi/TOOL.ZIP` 116 KB) | tool |
| `arsedit.zip` | 204 KB | Interstate Arsenal Pack Editor (Nitro mission builder; = route380 `NITRO.ZIP`?) | tool |
| `ChopShop19.zip` | 160 KB | El Gato's AVA Chop Shop 1.9 beta - car modification | cars |
| `avautils.exe` | 3.36 MB | AVA Car Dizyna + Hacker Tracker (16-bit self-installer) | cars, MP rules |
| `nitrace57.zip`, `nitrace.zip`, `intertrace1_1b.zip` | 2.1 / 1.8 / 1.7 MB | Nitrace / Intertrace (AVA cheat-detection / car-file audit) | tool, car formats |
| `AntiCrashv10.zip` | 2.05 MB | Anti-Crash v1.0 (I'76 + Nitro) | fix |
| `nitropatchI..IV.zip`, `nitroexe.zip` | 0.7-2.9 MB | historic Nitro patches; Nitro.exe 30 fps update | exe reference |
| `asset.zip` | 8.5 KB | Asset Bible (already mirrored) | - |
| `i76autoguide.zip` | 2.1 MB | Rude Dog's I'76 Auto Guide (car guide) | docs |
| `map-guide.doc`, `map-review.xls` | 15 KB | LSM map review guide / template | curation |
| `i76.exe`, `i76demo.exe`, `i82demo.exe` | 21 / 31.8 / 29 MB | I'76 demo, Arsenal demo, I'82 demo | pre-release builds |
| `audio/ALL.ZIP` | 47.8 MB | I'76 game-disc music (from `i76audio.htm`) | music |
| `Outlaws-0.1.1a-linux.tar.gz`, `IOSetup-0.1.0.exe` | 53.7 / 58.1 MB | "Interstate Outlaws" open-source fan game alpha (~2007) | assets/ideas, probably own art |
| `I76.wmv`, `i76full.wmv` | - | The Great Santini's I'76 music video | - |
| `i82tool.zip` | 17.8 MB | I'82 Terraformer | I'82 only |

`/skins/` (408 zips in the 2007 Wayback crawl) is **I'82 skins** - wrong engine. `/the-ava/` = restored AVA site
(rules, ladders); `/sss/` = SuiCyco's Speed Shop (strategy, no files); `/resources/` = frames to the Asset Bible.

## 3. AVA, King's Custom Rods and the official Activision server (Wayback)

- **the-ava.net** (Auto Vigilante Association, 1999-2006): Wayback holds real files. Verified: `camaro.ZIP`,
  `addonbuilder.exe` resolve.
  - **Paint Shop user skins, ~42 zips (2001-2003):** `http://web.archive.org/web/20010718162411/http://the-ava.net:80/paintshop/user_zips/camaro.ZIP`
    and siblings (`'70elky`, `Americana`, `beemers`, `Blackend_Manta`, `camperfect`, `CRAP_POLICE_CAR`, `Crap_taxi`,
    `cusfire`, `GENERAL_LEE_ON_EL_PASEO!!!`, `Mustang`, `palflm`, `palglw`, `porsche`, `Powder_Blue`, `RaceYellow`,
    `Racing_Wagon`, `Target`, `Tim_Hortons`, `van`, `viper`, `VW_Bus`, `WOOdy` ...; 20-370 KB). I'76 paint jobs.
  - **utilities/** (1999-2001): `addonbuilder.exe`, `dizyna.exe`, `PLManager.zip` (1.47 MB), `qnitro.exe`, plus
    small maps `4pit`, `auto`, `avma`, `ber`, `elim1b`, `isa`, `oval`, `pmrw` and `Nitrace/Nitrace60f.zip`.
    Example: http://web.archive.org/web/20010727111807/http://www.the-ava.net:80/utilities/addonbuilder.exe
  - 2002 front page: https://web.archive.org/web/20020930070859/https://www.the-ava.net
- **kingmercury.tripod.com** (King's Custom Rods): **DNS does not resolve today** (both curl and WebFetch,
  2026-10-24) but Wayback captured the files on **2026-04-11** and they resolve:
  - **17 custom cars** `files/i76/cars/`: `clydelowrider`, `crewcabpickup`, `kingsconvertible`, `kingslowcavera`,
    `kingslowchevelle`, `kingslowjefferson`, `kingslowroyale`, `lowcop`, `lowcuda`, `lowjeff`, `lowpalamino`,
    `lowrabbit`, `lowvolvo`, `pickup_camper`, `salt_flat_spec`, `striderfunnycar`, `swamper` (27-163 KB each);
    Nitro cars `haci_proto`, `KingM_soccer_ball`.
    e.g. http://web.archive.org/web/20260411065144/https://kingmercury.tripod.com/files/i76/cars/swamper.zip
  - paints: `Charger1.8`, `Interceptor`, `General_Lee`, `ferrari_f376`, `camoclyde`, `blackngreenranha`, `jeffersonpaint`.
  - **tools:** `files/nitro/programs/VCFgen10.zip` (VCF generator), `paktool10.zip` (PAK tool), `bpatch76.zip`,
    `AVA_Car_Designer_by_KingM.zip`, `Nitro_patch1_fixed-exe.zip`, `ChopShop19.zip`; `files/i76/hop76_Ver3.ZIP`,
    `files/i76/programs/hack76.67b.zip`; `jwzfs.zip` (ZFS tool; the 2026-01 capture is a 502, look for an older one).
  - Wayback root: http://web.archive.org/web/20020125081645/http://kingmercury.tripod.com/
- **download.activision.com/activision/i76/** (official, Apache index captured 2001-05-05):
  `multi/` = `CRATER.ZIP` 177 KB, `TOOL.ZIP` 116 KB, `elim1b.zip`, `miners_ridge.zip`, `race1a.zip` (all
  1997-04-16). Only CRATER.ZIP was captured (http://web.archive.org/web/20031105074648/http://download.activision.com:80/activision/i76/multi/CRATER.ZIP,
  resolves); the others survive via LSM/AVA (s.2a, s.3). `stuff/` wallpapers + theme, `video/` (gameplay.zip, 3
  AVIs), `patch/` (1.05-1.083), `demo/` (split demo). Value: provenance for the first official bonus melee maps.
- Other archived fan pages (from Local Ditch links, not re-verified for files): Kowalski's page (real-vehicle chart),
  Deli Kingz, Magnificent Bastards (gangs), Vigilante's Paradise (1997 news, allgames.com/I76), Cater's page, Jeff
  Wofford's poems, GameSpot strategy guide 2008 capture.

## 4. archive.org items (identifier - size - content)

Content-bearing (expansion value):

| identifier | size | what | value |
|---|---|---|---|
| `Interstate.76` | 110 MB (`Interstate 76.7z`) | **a played-in Nitro install** (GOG-era nitro.exe, miniupnpc) with **~250 community maps** across `addon/` (428 files) `miss8/` `miss16/` (481 each) plus `Map Text Files/` (271 readmes incl. `divermappack`, `diverandfriendspack`, `zenguide`) | arenas + author credits; best pre-sorted install-ready set |
| `Interstate76-Soundtrack` | 597 MB zip | lossless **Game Disc** rip (20 tracks), **OST** (15+ tracks, with "In the Junkyard", "Roswell" ... not on the game disc), **Bullmark Demo** (24 mp3, arionsalazar.com, unreleased demo tracks), poems wav | music |
| `4_20200504_202005` | 43 MB | 16 mp3 of the game music | music (lossy dup) |
| `i-76voices` | 15 MB rar | 507 wav voice lines extracted from GOG I'76 | voices (dup of our own data, handy index) |
| `Interstate-76-Deutsch`, `interstate-76-deutsch_202308` | 843 / 865 MB | **German retail** (CD images, manual 24 MB PDF, reference card) | alternate (German) voice + text set |
| `1976-auto-vigilante-compendium` | 551 MB (2 rar + manual) | the **SideWinder Force Feedback Pro pack-in** edition. Disk 1 lists `BUILDER/I76EDIT.EXE`+`BUILDER.DOC`, `FRC/*.FRC` force effects + `I7_SFrce.dll`, `DEMO/{HYPER,MERCS,TIME}`; Disk 2 = missions M01-M15/A01, cutscenes | FFB effects (FFB lane), builder doc |
| `i76Sidewinder` | 1.34 GB | another SideWinder FF edition dump | same |
| `Arsenal_201610` | 36.5 MB | **Arsenal demo (pre-release, Feb 1998)**: `Nitro.exe` 1998-02-04, `NITRO.ZFS` 19.6 MB, missions `p09` (1998-01-22) and `t03` (1997-10-23) in Miss16 | cut content / dev-intent diff vs retail |
| `Interstate76_1020` | 20.8 MB | I'76 demo (pre-patch, 1997) | pre-release diff |
| `Interstate82Demo` | 29 MB | I'82 demo | - |
| `I76PATCH`, `I76V106` | 1.9 / 2.0 MB | 1.05, 1.06 patches | exe reference |
| `interstate76mapimages` | 1.65 MB | PNG maps of every I'76 + Nitro level (69 files: instant melee, scenarios, trip 01-17, Nitro instant/campaign) | map art for a level select / pack page |
| `interstate-76-arsenal-reference-card` | 8 MB | 300 dpi Arsenal keycard scans | docs |
| `the-interstate-76-arsenal-for-modern-systems` | 2.47 GB | "Enhanced Edition" repack: `76.7z`, `76 Nitro Pack.7z`, A3D-Live, compat-shim .reg, complete savegame, manual, box scans; also I'82 and Vigilante 8 | install reference; no new content |
| `choci76`, `winampskin_interstate_76`, `winampskins_Interstate_76` | <1 MB | Win95 theme by Gaetan Guine ("Choc"; probably the GFH member of that handle), Winamp skins | branding |
| `INTERSTATE_76` | 1 MB | the manual PDF | docs |

Full games / disc images (reference only, not redistributable): `i-76-cd-2`, `interstate-76-activision-1997`,
`interstate-76-usa-oem` (redump-verified, 2026-09), `Interstate_76_Accelerated_Gold_Edition_-_Win95_Eng` (+ Gold
patch16 exe), `Interstate_76_STB_Velocity_128_Pack-In_Activision_CD1/CD2`, `nitro-pack-for-interstate-76` (Diamond
Monster 3D II pack-in), `nitropack-for-interstate-76` (Argentine retail, 1200 dpi scans), `Interstate_76_Nitro_Pack_Eng`,
`interstate-76-nitro-riders`, `rootifera-interstate-76-nitro-riders-1998`, `interstate-76-nitro-pack` and
`interstate-76_202606` (GOG 2.1.0.17 rars), `interstate-76-arsenal-gog.com-version`, `interstate-82`, `i-82_20261003`,
`20250315_20250315_0400` (Activision PC image collection, 290 GB). Pack-in editions (STB, Diamond, SideWinder) are
worth a file-level diff only if a build difference is suspected.

Magazine coverdiscs carrying the I'76 / Arsenal demos (not opened; same demo builds): `Computer_Gaming_World_CD_Battlecruiser_3000_and_Interstate_76_Number_156_JULCGROM_July_1997`
(586 MB), `pcgamer-disc-3.3-june-1997`, `demo-2-flav-1` (PC Gamer 7/97), `pcgamer-disc-3.14-may-1998`, `cdrom-pcgamer-314`,
`PCUJUN97`, `pcwjul97`, `wpcjul-97`, `connect-1`, `score42cd`/`score52cd`, `czlevel29cd`/`czlevel32cd`, `LEVEL0998R`.
Value: only if a coverdisc carries a demo build different from `Interstate76_1020` / `Arsenal_201610`.

## 5. Other community sources

| source | URL | content | status | value |
|---|---|---|---|---|
| Local Ditch maps | https://www.localditch.com/interstate-76/maps.html | 19 I'76 maps (authors: Stingray, Debacle, Skull N. Bones, General Rage ...) incl. `all-in-1.zip`, `zenstuff.zip` missing from LSM | live | arenas (mostly overlap LSM) |
| Local Ditch downloads | https://www.localditch.com/interstate-76/downloads.html | `avautils.zip`, `hack76.67b.zip`, `i76_maps.zip` (845 KB, Kalle Siukola map images), Gold 1.2 upgrade ARJ parts (official), `i76_music_for_ogg-winmm.zip`, demo movies, `i76_preview.zip` (pre-release AVI from MW2 Mercenaries disc), wallpapers, theme | live | tools, music, pre-release footage |
| route380 Terrarium | https://route380.stars.ne.jp/i76/resource_i76/ | already mirrored (40 maps, Bible, builders) | `i76/` root 403 today | done |
| GitHub `Lexx2k/I76_Viewer` | https://github.com/Lexx2k/I76_Viewer | browser (three.js) map + mission viewer: ZFS/LZO, VQM/CBK/ACT, BWD2, TER/GEO/SDF, VCF/VDF/VTF/WDF/GDF (2026-10-16, no licence) | live | viewer for vetting maps; preview images |
| GitHub `Roanish/i76` | https://github.com/Roanish/i76 | MIT C/Vulkan Nitro rewrite; `zfs_dump`, `asset_browser`, `smk_dump`, mesh viewer; `docs/REVERSING.md` (ZFS, GEO/OEG, mission object chain, PIX/PAK, fonts) | live (2026-10-16) | tools, format docs |
| GitHub `chasseyblue/i76-geo-importer` | https://github.com/chasseyblue/i76-geo-importer | Blender importer for `.geo` | live | car/prop authoring path |
| GitHub `CahootsMalone/interstate-76-stuff` | https://github.com/CahootsMalone/interstate-76-stuff | UNZFS, special-vehicles list mod, vehicle-list format, Nitro VCF list, **`interstate-76-poems-wave-files.zip`** | live | special vehicles, poems audio |
| GitHub `r1sc/Open76`, `jpcy/piranha76`, `greg-kennedy/i76render`, `vahokif/I26` (editor writes original formats) | - | engines / RE / renderer | live | known |
| GitHub `rickymagal/i76_patch`, `r4lix/interstate76-nx` | - | ddraw FPS cap; Switch port | live | none for content |
| GOG forum | https://www.gog.com/forum/interstate_series | threads: special vehicles (`how_to_add_special_vehicles_to_the_vehicle_selection_menu`), `addon_maps_not_being_found_by_interstate_76_original` (2010, "~250 user maps"), `extract_dialogue_files_of_i76_and_nitro_pack` | live | how-tos |
| VOGONS | https://www.vogons.org/viewtopic.php?p=288754 (AiO patch), p=774356 | AiO patch, RReady Verite wrapper | live | fixes, not content |
| PCGamingWiki file 1349 | https://community.pcgamingwiki.com/files/file/1349-interstate-76-nitro-pack-aio-patch/ | AiO patch download | live | fix |
| GamePressure | https://www.gamepressure.com/games/interstate-76/mods-trainers/z3187c | 25 fps fix, Nitro 30 fps patch, 1.06 | live | none |
| MyAbandonware | https://www.myabandonware.com/game/interstate-76-3zz | manual only; comment asks for DIVER's road texture fix (we have it, route380 `patch_8bit_roads.zip`) | live | none |
| ModDB `interstate-76-mod` | https://www.moddb.com/mods/interstate-76-mod | archived **Battlefield-style total conversion** inspired by I'76 (not for the I'76 engine); 403 to bots | archived | none |
| Interstate '76 Wiki (Fandom) | https://interstate76.fandom.com/wiki/Tricks | small wiki (Tricks: T.R.I.P. custom car via ADDON .vcf copy, UNZFS / Dragon UnPACKer notes); 402 to bots | live | how-tos |
| Reddit r/interstate76 | - | could not verify: reddit blocks this client and web search returned no I'76 threads | unknown | - |
| Discord | I'76 community 623625237891907618; UltraFunk https://discord.gg/dyJnDmSJBB | I26 testing; online Nitro games | live (known) | ask for private map/car stashes |
| Sketchfab xetura collection | (in COMMUNITY-RESOURCES s.1b) | 3D car models | known | reference |

## 6. Gotchas found this sweep

- `interstate76.com/lsm/index.htm` and `/resources/` are framesets; the real lists are `lsm/links.htm` ->
  `lsm/<group>/<page>.htm`. A plain WebFetch of the index returns nothing.
- archive.org lists the contents of a zip/rar/7z without downloading: `https://archive.org/download/<id>/<file>/`
  (302 to `view_archive.php`); rows are `<tr><td>name<td><td>date<td id="size">bytes`.
- Wayback raw files: insert `id_` after the timestamp (`/web/20010718162411id_/http://...`).
- The Wayback CDX API went "Temporarily Offline" / 502 several times this session; retry later rather than
  concluding a site has no captures.
- tripod.com: DNS failure from this host today, yet Wayback captured it in April 2026 - treat as "reach via Wayback".
- GFH exists but is a dead end for files (s.1).

## 7. Ten to fetch first (into git-ignored `refs/`, never committed)

1. `interstate76.com/download/allnitromaps.zip` (58.6 MB) - the Nitro map collection, live.
2. archive.org `Interstate.76` -> `Interstate 76.7z` (110 MB) - ~250 install-ready community maps with 271 readmes;
   diff its `addon/miss16` names against #1 and LSM to get a de-duplicated catalogue with authors.
3. LSM I'76 / Gold archives: the 228 live zips in `i76comb1-5` + `i76race` (26.7 MB, list in `lsm-map-files.tsv`) -
   the only large arena set for the Gold exe we ship.
4. `interstate76.com/download/builder.zip` + `arsedit.zip` + `DIVERmappack.zip` (1.4 MB total) - the official I'76
   MP mission builder with its doc, the Arsenal editor, DIVER's pack.
5. King's Custom Rods via Wayback: the 17 `files/i76/cars/*.zip`, 2 Nitro cars, `VCFgen10.zip`, `paktool10.zip`,
   `hop76_Ver3.ZIP` (~1.5 MB) - the only new **cars** found, plus car/PAK tooling.
6. AVA Paint Shop skins via Wayback (~42 zips, ~3.5 MB) + AVA `utilities/` (`addonbuilder.exe`, `dizyna.exe`,
   `PLManager.zip`, small maps) - paint jobs and the AVA car tools.
7. `Interstate76-Soundtrack` zip (597 MB; or just its OST + Bullmark Demo folders) - lossless music and 24
   unreleased demo tracks for a music expansion; `interstate76.com/download/audio/ALL.ZIP` (47.8 MB) as the
   smaller game-disc set.
8. `Arsenal_201610` (36.5 MB) and `Interstate76_1020` (20.8 MB) - pre-release builds; diff `p09` / `t03` and the ZFS
   against retail for cut content and dev intent.
9. `1976-auto-vigilante-compendium` Disk 1 rar, or just its `FRC/` + `BUILDER/` entries (can be pulled singly via
   `view_archive` links) - SideWinder force-effect files for the FFB lane, official builder doc.
10. `interstate76mapimages` (1.65 MB) - PNG overhead maps of every stock I'76 and Nitro level, for a mission-select or
    pack page.

Second tier: German retail (`interstate-76-deutsch_202308`, alternate voices), Local Ditch `all-in-1.zip` /
`zenstuff.zip` (missing from LSM), ChopShop19 / avautils / Nitrace (car-format knowledge), CahootsMalone poems wav,
Interstate Outlaws alpha (check its licence before looking at any asset).
