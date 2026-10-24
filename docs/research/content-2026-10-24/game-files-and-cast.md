# What else is in the game files, and who voiced it (2026-10-24)

Research lane: extra content in I'76's own files (GOG Gold and GOG Nitro), unused/cut assets, and a check of an AI
summary's claims about the voice cast and "hidden developer outtakes". Read only; nothing in a game folder was touched.

## 0. Short answers

- **Voice cast: the AI summary is right.** Groove Champion = Andrew Heckler, Taurus = Greg Eagles, Skeeter = Tom Kane.
  The game itself says so: the credits roll inside `DATABASE.MW2` (item 0x53) and the GOG `Manual.pdf` (p. 46,
  "Credits 61"). They also credit Antonio Malochio = John de Lancie and Jade Champion = Lisa Picotte. Nitro's credits
  (`database.tvf`) add **Skeeter / Natty Dread = Tom Kane**, keep Taurus = Greg Eagles and Jade = Lisa Picotte, and
  list no Groove.
- **"Hidden developer outtakes, bloopers and unused recording-session dialogue": not supported.** No clip on disk
  behaves like a blooper: no long clips, and no clip without a mission-numbered name. What the files do hold:
  - Gold: 10 voice clips no script plays (about 26 s in all, each 1 to 7.5 s, named like normal mission lines).
  - Nitro: 74 more.
  - One editor region label, `04SRK02b.wav`, inside `04srk02.wav`. It shows that a "b" take existed in the
    session. The take itself is not on disk.
  - Gold's line numbering skips 441 slots. Those lines were cut before the game shipped and are not in the files.
  So there is a small amount of unused dialogue, but no outtake reel. I found no source online that documents
  outtakes. The Cutting Room Floor page had no usable content.
- **Cut content that is really there, ranked by how useful it is for an expansion:** three complete vehicles never
  placed in any mission (Armadillo, F4D Phantom II jet, Howitzer), the objective text of a cut Nitro mission P20
  ("assassinate the governor"), remnants of a cut scenario S08 (3 voice lines), an earlier training-mission design
  (`train.npt`), M13's own objective text (the mission points at M06's file by mistake), 68 scenery objects no mission
  places (a whole cemetery set, tunnels, a gas depot, Joshua/scrub trees, an armadillo, a helipad), road manifests
  for cut arenas N04 and N08, and 13 Nitro-only car chassis that already sit in Gold's I76.ZFS.

## 1. What was already done (not redone)

- `i76-map\data\FORMATS.md`: every format parses byte-exact, 6,368 files, 0 diffs. Tools in `data\fmt`
  (bwd2x, fsm, mw2tool, nitro_corpus). `data\out\mw2db` holds the extracted shell database, including the credits
  text.
- `data\notes\nitro.md` and `docs\records\NITRO-BASE-2026-10-21.md`: Nitro's ZFS shares 5,624 byte-identical payloads
  with Gold. It adds 1,080 (985 .wav, 88 .vcf, 7 .gdf) and lacks 492 Gold .wav. All 88 Nitro .vcf resolve their
  chassis in Gold's ZFS.
- `data\notes\fsm-actions.md`: 18 FSM actions no mission uses (`playScene` aborts the game).
- `docs\records\FRESH-START-2026-09-04.md`: the debug-key names (`MONO_DEBUG_*`, `FSM_DEBUGGER`, `DAMAGE_DEBUG_*`,
  `DEBUG_CRITICAL_HITS_0..9`). `gamekey.map` labels them "Don't function in release build".
- `docs\ASSET-BIBLE.md` (DIVER 2000), `docs\PARTS-REFERENCE.md`, `docs\WEAPON-STATS.md`. The Cherub Missile is a real
  shipped weapon (`gscherub.gdf`), not cut content.
- **What was missing:** a reachability census, meaning which files anything actually names. That is new here.

## 2. Method (new tools, read only)

- `i76-map\data\fmt\content_census.py [gold|nitro|both]` writes `data\out\census\{gold,nitro}.json` and
  `unused-both.json`.
  - **Nodes:** loose files, ZFS payloads and every .pak member, taken from its .pix. Gold has 29,933 nodes and
    Nitro 30,673.
  - **Edges:** a file name, or a stem of at least 4 characters, appearing in another node's bytes. This includes
    names stuck inside full fixed-width fields. Mission ODEF labels and ZONE names come from the parser.
  - **Rules from the loaders:** the exe/shell printf patterns (`t%2.2d.msn`, `vppt%2.2d.vcf`, `nvcl%1x.vcf`,
    `%s%d.vcf`, `ZHL45%1d01.tmt`, ...); `<msn>.ter/_16.pcf/.rtm/.fsi/.tab/load.pcx` (0x48e1a0, 0x4b1a20, 0x42da44;
    Nitro's exe has `load.pcx`); and the tyre grades b/c/d next to every `_Na.wdf`. The tyre-grade rule is
    **inferred**: the garage picks the grade.
  - **Roots:** the exe, the shell, the fixed-name manifests and every loose mission. Gold's shell names all 40
    missions: `t%2.2d`, `s01..s07`, `m01..m15`, `a01`. Nitro's globs `*.cbt/*.rac/*.cfN` and uses `p%02d.msn`.
  - A file BFS never reaches is a **candidate**.
- `i76-map\data\fmt\voice_audit.py` writes `data\out\census\voice-audit.json`. For every mission it compares the FSM
  sound table with what the scripts can play. It counts literals before cb/cbPrior/cbFromPrior/cbFrom/playMovie/
  salvage, S-kind machine parameters, and every pushed literal in a script with a sound action. That last rule
  covers the random-banter arrays (A01 ip 1474..1513 pushes indices 65..82 and plays `BP[rand]`). It also finds
  exact PCM duplicates and screens for alternate takes: the normalised cross-correlation of 20 ms log-energy
  envelopes against the same speaker code.
- `data\out\census\unused-audio.m3u` is a playlist of every unreferenced clip (96 entries), so you can listen.
- **Caveats:**
  - The census leans towards "used". Stem matching on words in text and on random binary substrings creates false
    links. Known cases: `train.npt` (linked by the word "train" in a01.npt), and `gback.wav`/`gpage.wav` (found in
    mission bytes). I corrected all three by hand below.
  - The unused lists are therefore lower bounds. The other direction (a file loaded by a naming rule I did not
    model) was checked by hand for every family in the table: grep of the exe/shell strings, plus the loader
    notes.
- **Inputs:**
  - Gold: `i76-map\sandbox-gog\main\app` (i76.exe 9a232dcc), plus the 6,116 I76.ZFS payloads in
    `recon-2026-09-04\recon\formats\zfs_out`.
  - `game-scott` has the same I76.ZFS (md5 6dd57b16) but a different i76.exe (64165126, the patched patch-kit build).
    The data is identical.
  - Nitro: `sandbox-gog\nitro-full\app` (nitro.exe 28b8ae27, the same files as `Games\I76\nitro`) and its 6,704
    ZFS payloads.

## 3. Inventory

| | Gold | Nitro |
|---|---|---|
| missions | 40 (T01-T17 trip, S01-S07 scenario, M01-M15 melee, A01 training); every one reachable from the shell | 19 P (story) + 1 B01 + 54 N arenas (.cbt 24 / .cf2-4 17 / .rac 13) |
| cutscenes (.smk) | 29, all referenced (WRLD intro/outro or FSM `playMovie`); T14's WRLD names an outro `preview.smk` that is **not on disk** | 2 (intro, credits) |
| voice clips | 494 (≈41 min): 364 mission CB lines (≈29 min), 87 `gd*` generic (3.5 min), 28 `tm*` (3.7 min), 15 `posta*` (5.1 min; a hard-coded list in i76.exe, **inferred** to be the Taurus poetry key) | 988 (≈76 min): 765 mission, 143 `gd*`, 60 `tm*`, 20 `rl*` (hard-coded in nitro.exe) |
| SFX | 123 .gpw + the exe's named .wav | same 123 .gpw |
| shell UI | 11 sounds in DATABASE.MW2 + 12 loose `g*.wav` in the ZFS (see s.4) | same 12 `g*.wav` |
| object .sdf | 371 | 371 (identical) |
| car .vcf / chassis .vdf | 295 / 48 | 382 / 48 |
| textures .map/.vqm/.m16 (incl. pak members) | 480 / 6,101 / 5,644 | same |

**Speaker codes** (from the credits; the file-code mapping is **inferred**):
- Gold uses `s` + two letters: gc Groove, ta Taurus, sk Skeeter, jc Jade, am Antonio Malochio, plus the minor CB
  voices (in, sn, ok, ...).
- Nitro uses three letters: tau, jad, ske, nat (Natty Dread, Tom Kane), whi, sna, rad (radio), ...
- The leading number is the recording script's scene, not the mission. For example, T01's sound table holds
  `12sgc08` and `14ssk04`.

## 4. Unused-content table (unreferenced in Gold and in Nitro unless noted)

| family | count | names | what it is / evidence |
|---|---|---|---|
| **vehicles, complete** | 3 | `varmdilo.vdf` "Armadillo" + `dillo1.vtf` + `vdillo1.vcf` + `varmdlog.pak`; `vuphantm.vdf` "F4D Phantom II" + `phantom1.vtf` + `vuphant1.vcf` + `vuphantg.pak` (textures `phantm16/1m` are shared, `phantm1t` unused); `vxhowitz.vdf` "Howitzer" + `howitzr1.vtf` + `vxhowit1.vcf` + `vxhowitg.pak` | chassis, skin, loadout and geometry all present; no mission in either build places them (i76.exe has the message "More then %d artillery guns in the mission", so artillery was a mission feature) |
| car loadouts (.vcf) | 44 more | mission casts never placed: `t11al01 t11al02 t11cc01 t11cm01 t11cr01 t11dl01 t11fp01 t11fr01 t11va01` (a cut T11 convoy), `t02js01 t05fy01 t13fr01 t14cp02 t17fr02 t17fr03`, `s01ds01 s02vfy01 s03vas01 s03vc02 s04vas01 s04vc03 s04vfy01 s05vc01 s05vfp01 s06vc03 s06vu02 s07go01`, Nitro `p02wc01 p06al01 p06jso1 p07az01 p08al01 p09cc01 p14js01 p18uc01`; specials `c1turr sp2turr` (turrets), `norbus norlepr norpony norroyl` ("nor" set, low-armour civilians, **inferred**), `vugcobr1 vxbus1no vxsndbg2` | leftovers from mission revisions; every one resolves to a shipped chassis |
| **mission text (.npt)** | 3 | `p20.npt`: "Assassinate the governor (he's the guy in the limo, twinkie)... Get back to the helicopter at the airport", failures incl. "You have been abducted by aliens. Bummer."; `train.npt`: an older training design ("Race Taurus to the next gate ... target practice, take out the mock town ... blow up the drone trucks"; the shipped A01 is "Listen to Jade's tape"); `m13.npt`: "Pyrite Mining Corp. closed this years ago... That first step is a doosy" | P20 = a cut 20th Nitro mission (the P missions stop at P19); **M13's WRLD names `m06.npt` (miss16 and miss8)**, so M13 shows M06's text and its own text is never shown |
| cut-mission remnants | 5 | `s8sgc01.wav` 2.2 s, `s8sgc02.wav` 2.8 s, `s8sn201.wav` 7.5 s (a scenario S08; the shell lists S01-S07); `n04.rtm`, `n08.rtm` (road texture sets for arenas N04 / N08; Nitro ships N01-N35 without N04, N07 or N08) | the files alone; no .msn or .ter |
| voice, Gold | 10 (+1) | `02sgc20` 3.2 s, `02sgc21` 1.0, `07som01` 4.1, `gdsgc21` 2.0, `gdsgc22` 1.1, `gdsgc23` 1.4, `gdsgc24` 1.2, plus the 3 `s8*` above; `gdsgc29` sits in a sound table but no instruction pushes its index | no table names them. The alternate-take screen scores 0.20-0.79 against the closest same-speaker clip; used clips score median 0.50, p90 0.69 (n 60). Only `gdsgc21~13sgc09` (0.78, 1.99 / 1.96 s) and `gdsgc22~s2sgc04` (0.79) reach the top decile: worth a listen, not evidence |
| voice, Nitro | 74 | 16 numbered (`05jad08 06jad22 06jad23 06tau17 06tau21 06tau26 08jad06 08ske01 08ske02 10ske04 11tau04 14sna04 17tau08 17tau16 17whi19`; `tmjad20`) and 58 `gd*` (jad 20, tau 20, ske 10, nat 8) | 8 of the `gd*` are **byte-identical PCM** to `rl*` race lines that nitro.exe plays (`gdtau22/30/43/44`, `gdjad31/41`, `gdnat17`, `gdske14`): the same take under a second name. Above the control p90: `gdjad34~tmjad21` 0.89, `gdnat12~rlnat02` 0.88, `gdnat18~gdnat25` 0.83 (both 2.029 s), `gdtau01~08tau11` 0.80, `gdjad23~tmjad14` 0.80: possible alternate takes of the same line; listen to confirm |
| recording-session trace | 1 | `04srk02.wav` carries a RIFF `cue`/`adtl` region labelled `04SRK02b.wav` | the editor's region name for take "b"; the only session metadata among 1,753 clips (others: a Cool Edit 96 tag in `fdmg1.gpw`, dates 1996-08-16 / 1996-12-19 on 3 SFX) |
| old shell UI sounds | 12 | `gadv gback gic gpage gpencil gquit grp gsml gsms gsr gsws gtext.wav` | only in I76.ZIX's listing; the shipped shell plays its own 11 sounds from DATABASE.MW2 (no PCM matches). Likely an earlier shell (back/page/pencil/quit/text) |
| SFX | 6 | `vlanding wgl whsm xcar xsv1 xsv2.gpw` | named by nothing |
| scenery .sdf | 68 | cemetery `bhyceme1-6` (gate, walls, graves); tunnels `betunnl2/3`; `bfdepot1` gas depot; `a3pline1` pipeline; `aaramp6` "bridge a..." / `aaramp8` "broken s..."; trees `ntree1-4` (scrub, Joshua), `npinetr2`; `nadillo1` armadillo; `axlot1` parking lot, `axlot2` helipad; street lights `agstlgt1 bczlite2`; Industrial Park `bcaik1/3/5/7`, `bcaik_s2/5/6/7`, `bcaikwl6`; props `abarrel1 actrash1 afence1/2`; 14 intersections; 19 signs (`sj13l/r sj21l/r sj38l/r` junction, `sh38e/w_2 sh82e/w_2` night routes, `swbrn swrop swwht` welcome, `swfed swarn sedon scros smcar sl55x_2`) | every one has its geometry pak; ready for new missions. Gold alone leaves another 74 unused, but Nitro places them (CTF flags `a1flag1-4`, planes, church, Foxy's, a Gila station) |
| explosions .xdf | 4 | `xcarx2 xcont1 xfire2 xsmbk1` (+ `xfire2.pak`, `xsmbk1.pak`) | alternate blast / fire / smoke effects |
| weapon | 1 | `tsball.gdf` "Ball O'Flame trt" | Nitro-only file; Gold's shell names it, but no Nitro car mounts it |
| palettes / sky | 17 | `superpal.act`; `m02/m03/m04/s06.act` + `.lum` + `.tbl` (those missions use other missions' palettes); `b01/t16.hzd`, `t06/12/14_16.hzd`; `nk_1mon2.map` (second moon sky) | per-mission looks that were replaced |
| textures | 75 .map + ~440 pak members | `tn10*` (a whole terrain texture set: `tn10m/m6/16m.pak`, `tn101-106md_`), `i2ang_11-13` + paks, `ax_1lt_1/2`, `mchades`, `zmiro101`, `zbinc`, `zsle`, `zhpd*` (8, HUD-style names); `tt0NN2-6sd_`, `tm15[2-6]as_` look like the levels of a used texture (**probably loaded by a naming rule I did not model; not claimed as cut**) | |
| codebooks | 4 | `roadmap4-6.cbk`, `tvfmap3.cbk` | 1-3 are used, which suggests levels |
| Nitro mission support in Gold | 13 chassis + ~150 files | `vagrappl vchacnda vdrampag vjdrednt vleopard vrmarshl vuballon vwclown vwfwolfv vxamblnc vxhearse vxsandbg vxufo.vdf` with skins and geometry; `p01-19load.pcx`, `p*.npt/hzd/act/lum/tab/rtm`, `b01.*`, `n*.tab/rtm`, `mbalfire/mcaltrop.geo`, caltrop/chemical/Ball O'Flame sounds | unreachable in Gold (Gold's exe does not even build `<msn>load.pcx`), used by Nitro. Gold's ZFS was built from the Nitro data set |
| not game data | 49 + 14 + 1 | `SP256\*.bmp` (autorun launcher art), `force\*.frc` (FFB effects; i7_sfrce.dll), `BUILDER\BUILDER.DOC` (editor manual) | outside the engine |

**No orphan missions or terrains** in either build. Every .msn/.ter on disk is reachable.

## 5. Voice cast: verdict and sources

| character | AI summary | game credits | verdict |
|---|---|---|---|
| Groove Champion | Andrew Heckler | Andrew Heckler | **true** |
| Taurus | Greg Eagles | Greg Eagles (also Additional Voices; Taurus again in Nitro) | **true** |
| Skeeter | Tom Kane | Tom Kane (Nitro: "Skeeter / Natty Dread") | **true** |
| Antonio Malochio | - | John DeLancie | (not claimed) |
| Jade Champion | - | Lisa Picotte (also Nitro) | (not claimed) |
| "hidden developer outtakes, bloopers, unused recording-session dialogue in the audio files" | claimed | - | **false as stated.** There are no bloopers or outtake reel. There is a small set of unused lines (Gold 10 clips ≈ 26 s, Nitro 74 ≈ 3 min, 8 of those Nitro clips duplicates of used lines) and one take-"b" label. |

**Sources:**
- On disk: `DATABASE.MW2` item 0x53 (`i76-map\data\out\mw2db\083_0x53_credits.txt`); `Manual.pdf` page 46;
  Nitro `database.tvf` at offset 9,375,382 ("Voices").
- On the web, consistent with the disk credits: an archived Wikipedia article on the game (Heckler, Eagles, Kane,
  de Lancie, Picotte):
  <https://wikipedia2006.classicistranieri.com/en/i/n/t/Interstate_%2776.html>
- John de Lancie's Wikipedia page ("voiced Antonio Malochio"): <https://en.wikipedia.org/wiki/John_de_Lancie>
- The fan wiki: <https://interstate76.fandom.com/wiki/Characters>
- MobyGames and Behind The Voice Actors refused automated fetches (HTTP 403). The current English Wikipedia article
  lists no voice cast.
- No web source documents I'76 outtakes or bloopers. A search on "Interstate '76 outtakes bloopers unused dialogue"
  returned nothing specific to the game, and `tcrf.net/Interstate_'76` gave no usable content.

## 6. The finds most useful for an expansion

1. **Three ready vehicles:** Armadillo, F4D Phantom II, Howitzer. Each has a vdf, vtf, vcf and geometry, so they can
   be dropped into a mission (ODEF class 8/9) with no new art. The Phantom gives an airfield flyover; the Howitzer
   gives artillery.
2. **Cut-mission seeds with authored text:** P20 "assassinate the governor" (objectives and failure lines, with an
   airport-helicopter escape); the earlier training design (`train.npt`); the S08 voice lines. These are briefs
   that can be rebuilt as missions.
3. **The M13 text fix.** One WRLD field (`objective_text` m06.npt -> m13.npt, in both miss16 and miss8) restores the
   mission's own description. Our mod CLI can make this one-byte-class edit.
4. **68 unplaced scenery objects**, including a complete cemetery kit, tunnels, a helipad, a gas depot, desert
   trees, an armadillo and 20 signs. That widens the level-editor palette at no art cost.
5. **Nitro content already in Gold's ZFS:** 13 novelty chassis plus the P/N mission support files. Gold needs only
   Nitro's 88 .vcf and the missions, as NITRO-BASE already found. The census confirms it at file level.
6. **Unused voice for new missions:** 84 clean lines in-character (Groove, Taurus, Skeeter, Jade, Natty Dread). They
   fit new CB triggers. Audition list: `i76-map\data\out\census\unused-audio.m3u`.

**Open / next:**
- Listen to the 5 above-p90 Nitro pairs and the 2 Gold ones to settle "alternate take or not". n = 1 listener; no
  speech-to-text is installed. Whisper would turn the 84 clips into a transcript table.
- Model the texture-level naming (`tt0NN2-6`, `roadmap4-6`) before calling any of those cut.
- Find T14's `preview.smk` in a retail CD image; it is absent from GOG Gold.
