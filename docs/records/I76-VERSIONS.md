# Interstate '76: every released version, what each changed, and what we have (2026-10-17)

Lane `versions-catalogue`. Static work, plus downloads of period patches. Nothing was installed or run: no game and no VM.
Every downloaded file sits in its own folder under lab `emu\images\versions\`, hashed in `SOURCES.txt` there. The exes
and readmes extracted from them are in `emu\images\versions\extracted\`, so other lanes can diff them.

**Evidence classes used below.**
- **[doc]**: Activision's own text (readmes, patch notes, installer strings, product pages).
- **[press]**: period magazines and boards.
- **[lore]**: community sites, 2010-2026.
- **[ours]**: our measurement on the bytes: md5, PE link date, function-level diff, data-file diff.

Scripts: `tools/versions-catalogue/` (`fp.py` PE fingerprint, `iso.py` ISO 9660 reader, `funcmatch.py` +
`cmpf.py` / `pairlit.py` / `showdiff.py` / `region.py` normalized function matching, `vdfcmp.py` / `chunkdiff.py` /
`fielddiff.py` vehicle and weapon data diff, `strdiff.py`, `rtnames.py`). They ran from a scratch folder that held
the extracted media, and the paths inside them are that folder's.

## Short answer

1. **Original-team releases.** There were six exe builds after the March 1997 disc:
   - patches 1.05, 1.06, 1.08b, 1.081 and 1.083;
   - Gold Edition 1.2 (February 1998).

   We now hold four of the 1997 patches byte for byte (1.05, 1.06, 1.081, 1.083), plus the March 1997 demo. Only
   1.08b, the first D3D beta of July 1997, is still missing. For Gold 1.2 we hold the official upgrade patch (an
   RTPatch binary diff, 1.0 -> 1.2), but no Gold disc.
2. **The important bug-fix patch was 1.05 (with 1.06).** It came out two days after launch: exe link 1997-03-28.
   - It fixed about a dozen multiplayer bugs, the Mission 12 save crash and the 320x200 cockpit art. It also added
     one physics-side guard: the vehicle step now stops when a landing bounce has just wrecked the car (section 3.2).
   - 1.06 (exe 1997-04-11) added the host's "boot player" command and a chat toggle.
   - **No 1997 patch changed driving physics.** In 1.0, 1.05, 1.06, 1.081, 1.083 and the demo, every physics function
     carries the same float constants and the same struct offsets [ours, section 3]. The car, weapon and wheel data
     (mass, drag, damage, fire rate, ordnance speed and gravity) are also identical through 1.083.
3. **Gold 1.2 is the big change.** It is a full rebuild with a new compiler (VC4.2 -> VC5), with:
   - plugin renderers: D3D (DX5), Glide, Rendition, PowerVR and software;
   - 16-bit art;
   - **difficulty levels**;
   - multiplayer hack prevention;
   - retuned data: several cars' armour and loadouts, the Gas blast 500 -> 100, and the bus mass 9,000 -> 12,730.

   Our earlier work already showed that Gold's physics step is the same algorithm as 1.0's (RETAIL-HANDLING-DIFF).

   **New today:** the difficulty damage multiplier (x2.0 / x1.0 / x0.75) exists only in Gold and Nitro. It is absent
   from 1.0 through 1.083 [ours, section 4.3]. Retail 1.0 therefore has no difficulty scaling at all. That matters for
   any damage-rate comparison against the gold standard.
4. **GOG.**
   - GOG has sold *The Interstate '76 Arsenal* since 2010-02-18: two products, I'76 (Gold) and Nitro Pack.
   - The current GOG offline installer (2.1.0.17, which we hold) ships exe `9a232dcc`. That is the Gold exe, linked
     1998-02-19, with GOG's `WIN32.dll` music shim swapped in for `WINMM.dll`.
   - **It does not contain the 2019 AiO patch.** No `I76PATCH.DLL`, and the exe is unpatched.
   - The community claim that "the AiO patch is incorporated into GOG as of 2019" is not supported:
     - GOG DB has recorded the same 395.3 MB installer since 2018;
     - it lists only one Galaxy build (2015-04-21);
     - our extraction of the installer finds no `I76PATCH.DLL`.

     Our daily driver's AiO exe (`60abf7bc`) came from somewhere else. Section 2.8.
5. **Steam: none.** Steam's store search returns 0 results for "interstate 76" (queried 2026-10-17).
6. **Localized builds.**
   - MobyGames lists Brazil (localized by Brasoft), the UK and Germany (Bomico) for 1997, and Nitro Riders for
     Germany, Italy and Spain in 1998.
   - **No Japanese release was found** (English and Japanese searches, MobyGames, Wikipedia).
   - The string-lookup localisation layer (`STRLKUP.DLL`, `lang.txt`) first appears in 1.081.
7. **For the gold standard and the port.**
   - The physics of every original-team build is one algorithm.
   - What differs between 1.0 and Gold is data, difficulty scaling, renderers and the frame rate each reaches.
   - Section 5 lists what this means for the rebuild question. That decision belongs to other lanes and the owner.

## 1. The catalogue

`have` = we hold the bytes locally (path given). Link date = PE TimeDateStamp (UTC).

| version | date | exe (size, link date, md5) | renderers | what changed (source) | have |
|---|---|---|---|---|---|
| **Demo** | posted ~late March 1997 | `I76.EXE` 1,018,880 B, 1997-03-24, `e633e84b`; shell = retail's `7013d6ef` | software (DirectDraw) | 2 missions (T03, T14), product `I76DW95` [doc] | yes: `versions\demo-1997\i76.exe` (Local Ditch mirror) |
| **1.0 retail** | 1997-03-26/28 (US), 1997-04-04 (UK) | `I76.EXE` 1,019,392 B, 1997-03-16 06:30, `6cc509ad` (VC4.2); shell `7013d6ef` | software only, 320x200 / 320x240 / 480x360 / 640x480 | the game; product `I76W95` 1.0 | yes: `Downloads\I76_CD1.ISO` (archive.org, md5 `8fcd930d`), lab `emu\images\cd-rip\I76_CD2` |
| **1.05** | ~1997-04-01 (installer 04-01) | `I76.EXE` 1,019,904 B, 1997-03-28 01:27, `a7ba1eae`; shell `c6f95fd6` (03-31) | software | the fix list in section 2.2 [doc: archive.org item text = Local Ditch list]; CGW #156 (July 1997): "More than a dozen fixes ... the host no longer gets double kills" [press] | yes: `versions\patch-i76v105\I76PATCH.EXE` (archive.org `I76PATCH`, md5 `3a61a42f`) |
| **1.06** | ~1997-04-21 (installer) | `i76.exe` 1,022,976 B, 1997-04-11 23:50, `c1753568`; shell `d6ed4db4` | software | host can eject players (CTRL-S, CTRL-#); "minor internal optimization"; includes 1.05; 32 vehicle .vdf + 24 .tmt + MARX3.VTF in `ADDON`, merged into I76.ZFS by `FIX106.BAT`/`ZFSADD` [doc] | yes: `versions\patch-i76v106\i76v106.exe` (md5 `c387bba7`) |
| **1.08b** (D3D beta) | ~early July 1997 | not found | D3D beta | "1.08b patch" on the Activision board 1997-07-03..05; no transparency, no mip-mapping [press: WHAT-IS-STOCK rows 24] | **no** |
| **1.081** (D3D beta) | cab 1997-08-12 | `I76.EXE` 1,150,464 B, 1997-08-02 03:52, `99930c85`; + `I76D3D.EXE` 30,720 B launcher; shell `d523756c` (1997-07-22) | software + Direct3D (built into the exe; readme: "ONLY ... 3Dfx, RENDITION VERITE, and STB NITRO") | "bilinear filtering, MIP mapping, hardware acceleration"; applies to 1.0/1.05/1.06; **removes force feedback** (I-Force) [doc]; `ADDON\D3D.ZFS` 1,208 entries (power-of-two textures etc.) | yes: `versions\patch-i76v1081\i76v1081.exe` (md5 `43d5978f`) |
| **1.083** (FF) | ~Oct 1997 | `I76.EXE` 1,122,304 B, 1997-10-03 02:16, `3d8a568d`; same shell `d523756c`; same D3D.ZFS | as 1.081 | "adds force feed-back ... ups the version number to 1.083" (MS SideWinder Force Feedback via `i7_SFRCE.DLL`) [doc] | yes: `versions\patch-i76v1083\i76v1083.exe` (md5 `30ec5cdc`) |
| **Gold Edition 1.2** | Feb 1998 (in *Arsenal*; free upgrade download; also on the Nitro CD) | Gold `I76.EXE`: we hold it only as GOG's copy, `9a232dcc` 1,050,624 B, 1998-02-19 22:21 (VC5, LINK 5.10), shell `deb41008` (1998-02-19) | software, D3D (DX5, `ZDX5DRAW`), Glide (`ZGLIDE`), Rendition (`ZREDLINE`), PowerVR (`zpowervr`, NEC, "Released 2/14/98") | "16-bit 3D hardware acceleration, optimized engine, new terrain, horizon and sky textures, difficulty levels, hack prevention" [doc: Activision Arsenal page]; upgrade = "Interstate '76 Accelerated Gold Patch - Version 1.0 -> 1.2" [doc: patch exe] | upgrade: `versions\gold-v12-upgrade-{hardware,software}` (RTPatch, 1998-02-27); exe: GOG copy only (section 2.6) |
| **Nitro Pack** | 1998-02-28 (IGN via Wikipedia); US Activision store | GOG `nitro.exe` 1,070,080 B, 1998-03-27 22:14, `28b8ae27`; Arsenal-demo `Nitro.exe` 1998-02-04 `b73f852d` | as Gold | 20 missions, 30 MP maps, CTF / racing, novelty cars, new weapons; "Hack prevention: vehicles are validated" [doc: Arsenal Nitro page] | GOG installer `Downloads\setup_interstate76_nitro_pack_2.1.0.17.exe`; demo `versions\arsenal-demo-1998` |
| **Nitro Riders** | 1998 (Europe) | not held | as Nitro | European stand-alone name of Nitro Pack; Activision's page: the store's Gold upgrade "does NOT apply to ... the 'NITRO RIDERS' version" [doc] | no |
| **Arsenal** | Feb 1998 | = Gold 1.2 + Nitro Pack | | box asks for DirectX 5; "P133 or higher for 3-D acceleration" (WHAT-IS-STOCK, box photo) | no disc; GOG sells it |
| **GOG** | 2010-02-18 (Wikipedia, citing 1UP) | `i76.exe` = `9a232dcc` (Gold exe, `WINMM.dll` import renamed `WIN32.dll`); `nitro.exe` `28b8ae27`; GOG adds `win32.dll` (mp3 music via audiere), OpenGLide `glide2x.dll`, `I76SHELL_1083.DLL` (the 1.081/1.083 shell, unused by default) | as Gold, Glide through OpenGLide | Galaxy build 9141 dated 2015-04-21 (GOG DB); installer unchanged in size since 2018 | yes: `Downloads\setup_interstate76_2.1.0.17.exe`, pristine extraction `i76-map\sandbox-gog\main\app` |
| **AiO (community)** | 2019-08-01..09-01 | `60abf7bc` 1,051,648 B (same 1998-02-19 link + 45 code clusters) + `I76PATCH.DLL` (2019-09-01, 20 fps limiter) | as Gold | UCyborg: 20 fps cap, buffer-overrun fixes, CPU-check skip, NT windowed mode, netcode [lore: VOGONS t=68384] | yes: driver `i76.exe.u32xorig`, portable zip |
| **Steam** | - | - | - | none: store search for "interstate 76" returns `{"total":0}` (2026-10-17) | - |
| **Japan** | - | - | - | none found | - |

What is not on this list:
- the 1996 E3 and preview builds;
- a PlayStation port (Wikipedia files the game under "Cancelled PlayStation games" with no text);
- *Interstate '82* (1999, a different game).

Nitro Pack Patches I-IV are listed on the community download index (interstate76.com, captured in i76-map recon
`web-sweep\i76forum\download.txt`). Their origin was not established and they were not fetched.

## 2. Per-version notes

### 2.1 Retail 1.0 and the demo

- **Disc 1** (`I76_CD1.ISO`, 373,813,248 B) holds:
  - `I76.EXE` (dated 1997-03-15 on the disc);
  - `I76.ZFS` (63.8 MB, 1997-03-13), `I76MAX.ZIX` / `I76MIN.ZIX`;
  - `README.TXT` (1997-03-15): three notes on multiplayer drop-outs, Matrox Millennium black screens and "partial
    death";
  - the help files, the 16-bit InstallShield setup, and `PRODUCT.INI` (`I76W95` 1.0).
- **Disc 2** is the play disc: missions and the CD audio tracks.
- **The demo.** Its exe is linked eight days after retail (1997-03-24) and ships retail's exact shell DLL.
  - 1,784 of retail's 1,898 functions are byte-identical after address normalisation.
  - **Every physics function is identical:** `physics_StepVehicle` 0x472360, CheckImpact, the collision block, the
    tyre solver and its parts, the lateral function, the attitude solver, the terrain damage, `simclock_Update` and
    `StepperBegin` [ours].

### 2.2 Patch 1.05 (exe 1997-03-28)

The fix list below is Activision's: the text of the archive.org item and Local Ditch's 1.06 page, which repeats it.

- **Multi-Melee:**
  - the host info and game name blinked on the setup screen;
  - the host got double kills and double score;
  - turreted weapons kept their target locks after 'y' or jamming (they hit players while appearing to fire forward
    in the host's view);
  - shift characters could not be typed on the number line in the modem setup;
  - "partial death": the camera kept spinning around the hulk;
  - in IPX, a host who quit and rejoined showed only its own info.
- **TRIP:** a crash after Mission 12 when switching from a 'no salvage' to a 'salvage' saved game.
- **General:**
  - Dr. Radar turret missiles showed as Cherubs, and Aim Nein turret missiles as Fire Rites, in 320x200;
  - Fire Rite turret missiles corrupted the g-pit labels in 320x200;
  - the limited Moth Truck's explosion lacked the `mx11pp_3` texture.

Contents: `I76.EXE`, `I76SHELL.DLL`, `ANETDLL.DLL` and `ADDON\MARX3.VTF`.

Code [ours]:
- 1,702 of retail's 1,898 functions are identical.
- Six physics-module functions differ in bytes. Five of them differ only by operand order and register allocation
  (identical literal and offset sets).
- The one semantic change is in section 3.2.

### 2.3 Patch 1.06 (exe 1997-04-11)

**New strings.**
- "Boot %s from the game? (CTRL-Y / CTRL-N)";
- "Chat display is ON/OFF";
- `dpDestroyPlayer`.
- Removed: "This program must be launched from i76.exe".

**Vehicle data.** It ships 32 vehicle `.vdf`, 24 Marx `.tmt` and `MARX3.VTF`. `FIX106.BAT` merges them into
`I76.ZFS` with `ZFSADD`.

**Per-chunk diff against the disc's ZFS [ours]:**
- **ETBL** is the cockpit element table (`zdue320.map`, the 320x200 g-pit). Its turret-weapon icon indices are
  shifted by one, and a missing `3pyro_trt_on` entry is added (+32 B). This is the 320x200 turret-label fix.
- **WLOC:** the 3-5 bytes that differ are in unused wheel slots, which hold uninitialised garbage (FORMATS-tables
  WLOC). The two **COLP** differences are in turret emplacements, where COLP is ignored for class 8.
- **Mass, drag, class, size, LOD, geometry and wheel positions: identical.**

### 2.4 Patches 1.08b, 1.081, 1.083 (summer and autumn 1997)

- **The readme.** 1.081 and 1.083 carry the same `README.TXT`, headed "INTERSTATE 76 BETA PATCH v.1.0.8b (D3D
  Enhanced)". It is signed by the "I76: D3D team":
  - Dave Georgeson (producer), Paul Trowe (associate producer), Julio Jerez (lead programmer);
  - Qing Yuan (programmer), Marc Turndorf (senior QA lead), Rick Omori (lead QA tester).

  So the D3D patches were a separate small team. The readme lists three known issues: blank screens on 3Dfx
  pass-through boards with S3 or Tseng cards, an Oil Well Well replay crash, and repeated save names.
- **Direct3D is compiled into the exe.** About 500 new strings: DirectDraw and D3D error texts and the caps dump.
  - `ADDON\D3D.ZFS` adds 1,208 entries: pak, pix, map, vqm, cbk, plus 34 vdf, 30 vcf, 29 gdf, 13 xdf and 79 vtf.
    Krager had admitted every texture needed re-sizing to a power of two (WHAT-IS-STOCK row 22).
  - Field diff of its vdf / vcf / gdf / xdf against 1.0 + 1.06 [ours]: mass, drag, weapon damage, fire rate,
    lifetime, ammo, spread and ordnance head are identical. Only geometry and garbage bytes differ.
- **Force feedback.**
  - Retail 1.0 names `iforce.dll` (Immersion I-Force).
  - 1.081 drops it (the readme: you "lose all Force Feedback").
  - 1.083 adds `i7_SFRCE.DLL` / SWForce (Microsoft SideWinder Force Feedback). That DLL is the one Gold ships
    (1997-12-01 build).
- **Localisation.** The `STRLKUP.DLL` string lookup and the "English" locale string first appear in 1.081.
- **The shell.** 1.081 and 1.083 share shell `d523756c` (1997-07-22). **GOG ships this exact DLL as
  `I76SHELL_1083.DLL`.** VOGONS t=25721 uses it to avoid Gold's Mission 12->13 shell crash.
- **Code.** 1.081 is a heavier rebuild: 45 % of retail's functions are identical, against 62 % in 1.083.
  - In 1.083, every physics function has the same float-constant set as 1.0.
  - The remaining literal differences are x87 stack indices (`st(n)`).
  - The vehicle step keeps the 1.05 wreck guard.

### 2.5 The 1.08b gap

The first D3D beta was named on the Activision board on 1997-07-03..05, with the 3Dfx and Rendition card lists on the
archived Activision downloads page [doc]. No copy was found: Local Ditch, archive.org, the Activision CDX (11,881
captures from 1997-2000, none an I'76 patch file) and the interstate76.com index all came up empty. The 1.081 readme
calls itself "v.1.0.8b". 1.081 may be its re-release under a new name; that is unverified.

### 2.6 Gold Edition 1.2 (February 1998)

- **The patch.** The free upgrade is `I76GPAT16.EXE` (hardware, 84.7 MB) or `I76GPAT8.EXE` (software, 72.6 MB).
  - Exe link date 1998-02-27; distributed as 4 ARJ volumes plus `unpack16/8.exe`.
  - It is a **Pocket Soft RTPatch 4.10** update titled "Interstate '76 Accelerated Gold Patch - Version 1.0 -> 1.2".
  - Its file table names, among others: `i76.exe`, `i76shell.dll`, `i76.zfs`, `i76.zix`, `zdx5draw.dll`,
    `zglide.dll`, `zredline.dll`, `zpowervr.dll`, `i7_sfrce.dll`, `strlkup.dll`, `d3d.zfs`, `fullres.lst`, and the
    help files.
  - It refuses partly patched installs: "You should apply this patch to a clean install".
  - It names `i76v108.exe` and `i76d3d.exe`, so it knows about the 1.08x installs.
- **Gold = 1.2.** Activision's own patch title gives the number.
- **GOG's exe is the Gold build.** Every check fits:
  - product `I76GLDW95`;
  - exe linked 1998-02-19 and ZFS dated 1998-02-16, eight days before the patch exe;
  - the DLL set matches the patch's file table.

  **It is not byte-verified against an applied 1.2 patch.** The patch is a binary diff against 1.0 and has to be
  applied, which this lane's rules forbid. Next step 1 does it inside a VM.
- **"Gold CD exe" `e1dca993`.** The lab's `I76GOLD.ISO` is built from the GOG files, with the 2-byte import rename
  undone. It is not a 1998 pressing.
- **Data changes 1.0 + 1.06 -> Gold [ours, field diff of the two ZFS files].**
  - **Cars (VDFC):**
    - mass, drag, class and size are identical for 25 of 26 cars;
    - **bus `vxbus` mass 9,000 -> 12,730**;
    - LOD distance 1 is 35 -> 45 on 22 cars, and the "never" LOD changes from FLT_MAX to 100,000;
    - hardpoint count changes on 2 (van 5 -> 4, tractor 0 -> 1);
    - the cockpit ETBL moved out of the vdf into `.elt` files (`vpit_1.elt`).
  - **Loadouts (VCF):**
    - armour and chassis retuned on a few variants (e.g. `vavikea1` armour 400 -> 300 per side, `vazamz1` chassis
      400 -> 380);
    - weapons swapped on 19 configs;
    - `engine_id` set on 38 turrets / emplacements;
    - one brake and one suspension id changed;
    - 56 configs point at a different `.vdf` (new Gold variants such as Moth for Marx).
  - **Weapons (GDFC):** damage, hp, mass, lifetime, fire rate, burst, ammo and spread are **identical** for all 43.
    Turret sub-ids are renumbered (+90, now >= 100 = turret variant).
  - **Ordnance (ORDF):** the first 16 bytes (id, muzzle speed, gravity scale, damage mask) are identical for all 43.
    Gold inserts a 4-byte tracer field.
  - **Explosions (XDF):** **Gas `xgasx1` blast damage 500 -> 100.** The other 22 are identical.
  - **Engines (`compnent.cdf`, power, brakes, suspension):** byte-identical.
  - **Wheels (WDF):** only LOD and geometry float noise.
- **Difficulty levels are new in Gold** (section 4.3).

### 2.7 Nitro Pack, Nitro Riders, Arsenal

- Nitro is the same engine family (Roanish's map; i76-map nitro-vs-i76). It has the difficulty branch too (section
  4.3).
- GOG's `nitro.exe` is linked 1998-03-27, a month after the 02-28 release date. The *Arsenal* demo's is 1998-02-04.
  So GOG ships a later Nitro build than the earliest one. Nitro's installer also carries an Activision auto-updater
  (`dkupddll.dll`: "This upgrade is required to play in multiplayer mode") [doc]. Official Nitro patches therefore
  existed. Their notes were not found.
- The Arsenal demo (archive.org `Arsenal_201610`, 1998-02-26) holds one Gold mission and one Nitro mission, run
  through `Nitro.exe` [doc].
- **Full difference map against retail 1.0: [NITRO-VS-RETAIL-2026-10-20](NITRO-VS-RETAIL-2026-10-20.md)** [ours].
  In short:
  - **Engine:** Gold's engine, relinked. 1,781 of 1,997 Gold-matched functions are identical; about 60 % of Nitro's
    functions have a located retail counterpart.
  - **Physics:** the same physics code and car data as Gold. That is retail's algorithm plus Gold's two
    grounded-only guards; no handling constant differs.
  - **Combat:** Gold's changes (difficulty x2.0 at the GOG default, health %, turrets, heat cone), plus Nitro's own:
    the dropper cadence, the specials Dashboard Mary and Tire Covers, and 7 weapons.
  - **Data:** the same file formats and FSM. Race and CTF are ODEF label conventions handled in exe code.
  - **Network:** ANet 2.
  - Our exe `6319abf7` is the Gold build (section 2.8). It boots Nitro's single-player mission P01 from add-on files
    (lab exp-nitro, 4 of 6 boots).

### 2.8 GOG and the AiO exe in our driver

**What GOG ships.**
- GOG installer 2.1.0.17 (395,232,528 B), extracted with innoextract: `app\i76.exe` = `9a232dcc`.
- It has no `I76PATCH.DLL`.
- It ships GOG's `win32.dll` (2009; forwards to winmm and plays `music\N.mp3` through audiere), OpenGLide, and
  `I76SHELL_1083.DLL`.

**Our driver's exe** (`i76.exe.u32xorig` `60abf7bc`) and the portable zip's are the AiO 2019-09-01 final.
- MAC-BUILD.md found it byte-identical to UCyborg's AiO final.
- The `i76.exe` we run (`6319abf7`) is this AiO file plus a 10-byte import rename, `USER32.dll` -> `u32x.dll` (file
  offset 0xbff84). All three files (`9a232dcc`, `60abf7bc`, `6319abf7`) carry the Gold link stamp 1998-02-19
  22:21:32. Byte-compared 2026-10-20 in NITRO-VS-RETAIL section 7a.
- The driver folder also carries `goggame.dll` and `gfw_high.ico`, which the 2.1.0.17 installer does not have
  (FRESH-INSTALL-CHECK-2026-10-10).
- Where that copy came from is not recorded. Two candidates: an older GOG package, or an AiO applied by hand.

**Doc correction proposed:** the label "GOG 2019 build" in MODERN-SETUP.md, FIX-INVENTORY-2026-10-17.md and others
should read "GOG Gold exe + UCyborg AiO 2019".

## 3. Code differences that touch the simulation (1.0 -> 1.05/1.06 -> 1.083 -> Gold)

### 3.1 Method

1. Function starts are E8 call targets. Each body is normalised:
   - branch and call targets are masked;
   - absolute addresses are masked;
   - every x87 memory operand is replaced by the **value** of its constant, so a changed constant shows up.
2. Bodies are hashed and matched across builds.
3. For a non-identical pair, the multiset of literals (struct offsets, immediates, float constants) is compared.
   Equal literal sets plus the same instruction counts mean a pure code-generation change.

Retail addresses are from lab `emu\tools\memtrace\addrmap-retail.md`.

Identical function bodies, out of retail's 1,898 [ours]:

| build | identical | physics functions changed in meaning |
|---|---|---|
| demo 1997-03-24 | 1,784 | none |
| 1.05 | 1,702 | the wreck guard (3.2) |
| 1.06 | 1,533 | the wreck guard (as 1.05) |
| 1.081 | 858 (rebuild) | not checked function by function (low match rate) |
| 1.083 | 1,178 | the wreck guard; otherwise the same literal sets, including every float constant |
| Gold 1.2 | different compiler | same algorithm (RETAIL-HANDLING-DIFF, line by line for the lateral function) |

`simclock_StepperBegin` and `StepperInit` are byte-identical in 1.0, 1.05, 1.06, 1.081 and 1.083. **The substep rule
`count = floor(sim_dt x 20) + 1` has never changed**, and Gold has the same rule (EMU-MEMTRACE).

### 3.2 The one physics-side change: the landing-wreck guard (1.05)

| build | `test [x+0x454], 0x8020` occurrences |
|---|---|
| 1.0 and the demo | 2 |
| 1.05, 1.06, 1.083 | 4 |
| Gold | 4, plus 4 `test eax,0x8020` |

In 1.06, at 0x473049 and 0x4730bf, two new checks sit in the airborne/landing branch of the vehicle step:
1. after the landing-bounce sound (`push 4; call 0x468e10`);
2. after `ApplyCollisionDamage` (call 0x45dc10).

If the car's flags now carry 0x8020 (wrecked or destroyed), the rest of the step is skipped. In 1.0 a car destroyed
by its own landing finishes the wheel, surface and terrain-damage update of that substep.

This changes nothing for a car that survives its landing. It plausibly relates to the 1.05 "partial death" fix, but
that link is an inference, not a measurement. It does not explain Gold's higher T05 wreck rate (3 of 7 against 0 of
7, EMU-T05-CLEAN). The guard acts only after a car is already wrecked.

### 3.3 Arcade physics

`TOGGLE_ARCADE_MODE CTRL+A` is in both the 1.0 and the Gold `GAMEKEY.DEF`, and the "Arcade Phys." option string is in
both shells. The yaw cap that arcade switches (C = grip limit A instead of 7.84 x wheels in contact) sits inside the
lateral function. That function has identical literal sets from 1.0 through 1.083 and the same algorithm in Gold. So
**arcade behaves the same in every build** [ours, static; RETAIL-HANDLING-DIFF for Gold].

## 4. Behaviour by version: what is established and what is not

### 4.1 Renderers

| build | renderers |
|---|---|
| 1.0 / 1.05 / 1.06 | software rasteriser on DirectDraw only (DirectX 3) |
| 1.08b / 1.081 / 1.083 | adds Direct3D: DX3-era execute buffers, 3Dfx / Rendition / STB Nitro listed |
| Gold / Nitro | separate renderer plugins chosen at start-up (`-glide -d3d -redline -powervr`, or software): `ZDX5DRAW` (DX5 D3D), `ZGLIDE` (Glide 2.x), `ZREDLINE` (Rendition RRedline), `zpowervr` (NEC SGL) |

**Local Ditch [lore] on texture quality:** Glide and Rendition use the good 16-bit textures, D3D uses lower-quality
ones, and software uses 8-bit.

Frame rate by renderer and CPU is the other lanes' measurement (ERA-ENVELOPE, EMU-MEMTRACE, GOLD-STANDARD-FINGERPRINT).
Within one build, the renderer changes the simulation only through frame time. Section 3.1 explains why: one physics
step per frame below 50 ms, and the step is that frame's time.

### 4.2 Hardware: P133 and P166

No build contains a CPU-specific physics path. Gold's start-up does measure the CPU speed: the privileged-instruction
check that AiO and i76fix skip (WHAT-IS-STOCK rows 28-29). What it feeds was not traced in this lane.

The box line "P133 or higher for 3-D acceleration" is Arsenal's (Gold era). The 1997 retail spec is P90 minimum, P133
recommended. Any P133/P166 behaviour difference therefore has to come through frame time (step length). That is the
ERA-ENVELOPE / emulator lanes' measurement.

### 4.3 Difficulty and damage balance: new in Gold

Gold's offline damage site multiplies by 1.0 when `[esi] == 0x12`. Otherwise it reads the difficulty byte
`[0x654b9c]`: 0 gives **x2.0**, 1 gives x1.0, 2 gives x0.75 (constants at 0x4beb54..5c = 1.0 / 0.75 / 2.0;
FIX-INVENTORY item 9 for the meaning).

Scan for the same construct (`cmp dword [reg], 0x12` followed by an `fld`) [ours]:

| build | hits |
|---|---|
| 1.0, 1.06, 1.083 | 0 |
| Gold | 1 (0x4a76da) |
| GOG Nitro | 1 (0x4ade6a) |

**Retail 1.0 has no difficulty branch, as Activision's "Difficulty levels!" (new in Gold) says.** The factor retail
applies at its equivalent site was not traced; it is most likely a fixed 1.0. GOG's default `I76PLYR.DEF` holds byte 0
(x2.0).

**Consequence: a damage-rate or AI-difficulty comparison between Gold at default and retail 1.0 compares x2.0 against
no multiplier**, unless the Gold runs set the difficulty byte to 1. Which object x2.0 applies to (the player's weapons,
or damage taken) is FIX-INVENTORY's reading, "the player's offline weapon damage"; re-reading it is next step 3.

### 4.4 Data-driven behaviour, 1.0 -> Gold

From section 2.6:
- weapon numbers and ordnance ballistics are unchanged;
- engines, brakes and suspension (`compnent.cdf`) are unchanged;
- some loadouts and armour are retuned;
- the Gas blast is 1/5;
- the bus is 41 % heavier;
- LOD distances are longer.

The T05 and flat-road comparisons that used the retail and Gold player cars should check that both runs used the same
`.vcf`. Most player-car vcfs differ between the two ZFS files: armour, loadout, sometimes the vdf they point at.
GOLD-STANDARD-FINGERPRINT already suspects "car / save" for the lab's 34 % acceleration gap.

## 5. What this means for the open questions

- **"Were there important post-1.0 bug-fix releases from the original team?"** Yes. In order:
  1. **1.05**, two days after ship: multiplayer score and sync fixes, the turret lock, a TRIP save crash, 320x200 art,
     and the wreck guard;
  2. **1.06**: the host kick;
  3. **1.08x**: D3D and force feedback, betas only;
  4. **Gold 1.2**: renderers, 16-bit art, difficulty levels, hack prevention, data retune.

  None of them changed the handling model.
- **For the gold standard** (retail 1.0, P166, software, lowest detail):
  - The disc exe is unpatched 1.0. A period player on the internet would have run 1.05/1.06 within weeks.
  - **1.06 + software renderer is the "as played in April 1997" build.** Its physics equals 1.0 except for the wreck
    guard, and its data is the same.
  - Either 1.0 or 1.06 is defensible as the reference. We now hold 1.06, so it can be A/B'd against 1.0 on the same
    emulator rig (next step 2).
- **Rebuild on 1.0 instead of GOG?** This lane does not decide it; inputs only:
  - Gold and 1.0 run the same physics code.
  - The differences the owner can feel come from four places:
    1. data (the car and save used);
    2. difficulty scaling (x2.0 at Gold's default);
    3. renderers (1.0 has software only, so no Glide and no 16-bit art);
    4. frame rate and step length.
  - A 1.0 base would lose the renderers and art. A Gold base with difficulty byte 1, arcade off and 1.0-equivalent
    car files would match 1.0's simulation inputs. That is a configuration choice, not a code port, except for the
    landing-wreck guard, which is harmless.

## 6. Sources

**Local media (hashes in lab `emu\images\versions\SOURCES.txt` and above):**
- `Downloads\I76_CD1.ISO`;
- `emu\images\cd-rip\I76_CD2`;
- `Downloads\setup_interstate76_2.1.0.17.exe`, `setup_interstate76_nitro_pack_2.1.0.17.exe`;
- `i76-map\sandbox-gog\main\app`.

**Downloads, 2026-10-17 (not run):**
- https://www.localditch.com/interstate-76/downloads/ : `i76v106.exe`, `i76v1081.exe`, `i76v1083.exe`,
  `goldhardware/*`, `I76GPAT8.zip`, `I76GPAT16.zip`, `i76.exe` (the demo). The page text is the source of the 1.05,
  1.06, 1.081, 1.083 and Gold upgrade notes.
- https://archive.org/details/I76PATCH : v1.05, `I76PATCH.EXE` md5 `3a61a42f`.
- https://archive.org/details/Arsenal_201610 : the Arsenal demo.

**Activision pages (Wayback):**
- http://web.archive.org/web/20191224170624/http://www.interstate76.com/activision/arsenal/gold/main.html (the Gold
  feature list);
- http://web.archive.org/web/20190613061820/http://www.interstate76.com/activision/arsenal/nitro/main.html (Nitro,
  Nitro Riders exclusion);
- http://web.archive.org/web/20160826214246/http://www.interstate76.com/activision/i76/downloads.html (1.06, the D3D
  beta card list, the FF patch).

**Release data:**
- https://en.wikipedia.org/wiki/Interstate_%2776 (US 1997-03-26 citing OGR; UK 1997-04-04; Nitro 1998-02-28 citing
  IGN; GOG 2010-02-18 citing 1UP);
- MobyGames release info via Wayback,
  http://web.archive.org/web/20220514134607/https://www.mobygames.com/game/windows/interstate-76/release-info and
  http://web.archive.org/web/20160413222753/http://www.mobygames.com/game/windows/interstate-76-nitro-riders/release-info
  (Brazil, Brasoft localisation; UK; Germany, Bomico; Nitro Riders DE/IT/ES 1998; Brazil 2001 covermount);
- https://computinghistory.org.uk/det/71846/Interstate-76-Nitro-Riders/ (Nitro Riders);
- https://www.gogdb.org/product/1207661003 and https://www.gogdb.org/product/1207661023 (GOG builds and installers);
- Steam store search API, `https://store.steampowered.com/api/storesearch/?term=interstate%2076` ->
  `{"total":0,"items":[]}`.

**Earlier records:** WHAT-IS-STOCK (period press and board quotes), RETAIL-HANDLING-DIFF, EMU-MEMTRACE,
FIX-INVENTORY-2026-10-17, i76-map recon `pe-fingerprint`, `nitro-vs-i76`, `web-sweep`.

## 7. Next steps (not done here)

1. **Byte-verify Gold 1.2 = GOG `9a232dcc`.**
   - Apply `I76GPAT8.EXE` inside a disposable 86Box snapshot that holds a retail 1.0 install. Use a new snapshot copy,
     never `w95pb-hdd.img`.
   - md5 the resulting `I76.EXE`, `I76SHELL.DLL` and `I76.ZFS`.
   - This lane did not run the patch, per its brief.
2. **A/B 1.06 against 1.0** on the gold-standard rig. Both are software-only with the same data, so the only expected
   difference is the wreck guard: an A/A-sized null is the prediction.
   - The 1.06 exe needs its 32 vdf merged into `I76.ZFS`. `ZFSADD` does it in the VM, or `data\mod\zfspatch.py` does
     it offline.
3. **Trace retail's damage site** (the 1.0 counterpart of Gold 0x4a76a0), and confirm which side the difficulty x2.0
   applies to. Then set the difficulty byte in every Gold gold-standard comparison run, and record it.
4. **Diff the player-car `.vcf` / `.vdf`** that the retail and Gold T05 / T06 runs actually loaded. Per car, per
   field: armour, loadout, mass.
5. **Find 1.08b and the official Nitro patches.** Leads: interstate76.com `nitropatchI-IV.zip`, the Activision FTP
   mirrors on Usenet `comp.sys.ibm.pc.games.action` 1997-07, and the PC Zone coverdisc D3D patch.
