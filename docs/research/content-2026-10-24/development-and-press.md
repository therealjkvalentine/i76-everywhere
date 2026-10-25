# Interstate '76: development history, press previews and cut content

Swept 2026-10-24 for future expansion work. This extends
[COMMUNITY-RESOURCES.md](../../COMMUNITY-RESOURCES.md) §5 ("Background / preservation"). Every source below
was fetched during the sweep unless it is marked **not fetched**. Treat all of it as third-party data.

Reliability scale:
- **A**: a primary source, either a named developer on the record or a period trade article.
- **B**: a period magazine preview, written from a pre-release build and developer briefings.
- **C**: a fan site or wiki summary of something primary.
- **D**: a single unverified mention.

Magazine page references are archive.org **leaf** indexes, in the form `https://archive.org/details/<id>/page/n<leaf>`.
A leaf index is not the printed page number. Where a scan shows the printed page, it is given too.

How the scans were searched: the archive.org "search inside" API was run over every scanned issue of these
magazines:
- CGW 141-163;
- Next Generation 1996-05 to 1999-08;
- PC Zone 1996-1999;
- the few PC Gamer issues on archive.org.

Hits were then extracted page by page from each scan's `_djvu.xml`. The helper scripts are
`<home>\i76press-tools\inside.py`, `page.py`, `find.py` and `meta.py`. They sit outside the repo; copy
them in if they are needed again. **US PC Gamer 1996-97 is not on archive.org as scans.** Local Ditch's April 1997
PC Gamer image is the only PC Gamer pre-release material found.

---

## 1. Who made it: names verified

| person | role on I'76 | source |
|---|---|---|
| **Zack (Zachary) Norman** | lead designer and writer: script, core cast, several of Taurus's poems | Next Generation #23 (Nov 1996), leaf 148-151; Ernest Adams, *Designer's Notebook* (1999); Gamezilla interview |
| **Sean Vesce** | director | Adams 1999; NG #23 |
| **Scott Krager** | producer; interviewed by OGR (1997) and Gamezilla (1996) | Local Ditch mirrors |
| Scott Lahman | Activision Director of Creative Affairs; championed the pitch | Adams 1999 |
| Rick Glenn | art lead | Adams 1999 |
| **Dan Stanfill** | programming lead; vehicle physics | Adams 1999; Julio Jerez via Dev Game Club |
| **Julio Jerez** | graphics programmer; his rasterizer replaced MW2's renderer as the "Darkside engine"; tyre-suspension filter | Dev Game Club ep. 424 (2025), Discord reply read on air |
| Kelly W. Rogers | Activision music director; executive producer of the music | OGR, Gamezilla, manual p.61 |
| Jason Slater (producer), Eric Valentine (engineer) | music production | Wikipedia citing WeFunkRadio |
| Lars Batista | voice of Oktoberfest; designed many TRIP missions | Local Ditch trivia (C) |
| Mondo Media | pre-rendered cutscenes (the "M" in Mondo Burger) | Local Ditch trivia (C); Gamezilla says "an external art house" |

The team was about 23 core staff in four groups: roughly 6 artists, 6 designers/mission builders, 7
programmers, 3 production staff, plus Vesce (Adams 1999). Gamezilla gives the timeline: production began
September 1995 and ran 15 months.

**"Zipper": not verified.** No source links Zipper Interactive to I'76, Nitro or I'82. Zipper made MechWarrior 3
(MicroProse, 1999), which may be the source of the confusion.

**Norman on I'82.** Norman was director and writer of I'82 (Wikipedia infobox; NG #47). NG #47 calls him "director
on both I-76 and I-82", but on I'76 he was the lead designer; Vesce directed.

## 2. Engine lineage

The engine line runs from MechWarrior 2 to I'76, then to Battlezone (1998), then to I'82.
- **MW2 → I'76.** Activision reused the MW2 engine to win project approval (Adams 1999). Vesce called MW2's engine
  "held together with super glue and bubble gum" (NG #23, cited by Wikipedia).
  - Gamezilla quotes the team: "we rewrote virtually all of the Mech engine and created a new engine."
  - Jerez gives the finer picture. The renderer and the tyre suspension were replaced, but the main game logic and
    the core vehicle physics stayed MW2-derived. "Many of the technical people did not want to modify the main game
    logic."
  - The green turret view is a MW2 leftover (Local Ditch Q&A).
- **I'76 → Battlezone (1998).** CGW #160 (Nov 1997) says so in two places: leaf 88 ("a much-enhanced version of
  the Interstate 76 engine") and leaf 164.
- **I'82** is on a new hardware-only engine: "Dark Side", the Heavy Gear II engine line. Sources are PC Zone #66 (Aug
  1998) leaf 65, which says "Kneel to the power of the Dark Side", and Local Ditch's I'82 page. The I'82 levels are
  "Large Driveable Mesh" levels built in Softimage (NG #47 leaf 74). **For us:** I'82 shares no engine code with I'76,
  so the I'82 data formats are not a shortcut.
- **Frame rate.** Jerez says the game "was designed to run at 15 frames per second". The suspension is a
  second-order filter tuned to resonate at 15 Hz and usable from about 10 to 30 Hz. This is already folded into the
  physics-rate work.

## 3. What the press saw before release, against what shipped

### 3.1 Next Generation #23, Nov 1996, "NG Alphas: Interstate '76" (B, with direct developer quotes)

Archive.org id `NextGeneration23Nov1996_2400`, leaf 148-151 (printed pp. 147-150). It is also the source
Wikipedia cites.
- **Release date "November" 1996.** The game shipped on 26 March 1997. Games Domain (Feb 1997) gives the reason for
  the slip: "we realized we couldn't build the game as originally envisioned in the given timeframe".
- **Plot as previewed:** Malochio "has been hired by OPEC to detonate a nuclear warhead over the U.S.'s one
  remaining oil field (he also killed your sister, Jade...)". In the shipped game he targets the Strategic Oil Reserve
  and there is no nuclear device. A nuke plot is a ready-made expansion beat.
- **"Some 25 different types of cars"**, each "customized with any of three different paint jobs per car." CGW #153
  also says 25 vehicles and 20 weapons.
- **Timed rescue mission:** "if you can't reach the diner in time, for example, it will be gutted by the time you get
  there." This is a time-pressure objective that degrades the map state.
- **AI that protects damaged sides:** "if a vehicle is damaged on its right side, it will know to keep itself to the
  left side of the player."
- **"Pit stops at 7-11s"** are pictured, and the preview calls the world "a place where you can walk into a 7-11 and
  buy both ammunition and a quart of milk."
- Norman says they were "experimenting with blending palettes from the cut scenes and the game". Cutscene cars use
  the in-game models.
- **The handgun** fired from inside the car: "be sure that you have enough money for a new windshield".

### 3.2 Computer Gaming World

| issue | leaf | what it says | differs from retail? |
|---|---|---|---|
| `Computer_Gaming_World_Issue_145` (Aug 1996) | 106 | E3 listing: "stop the enemy from destroying the US strategic oil reserve" | no; the final plot was already set |
| `Computer_Gaming_World_Issue_153` (Apr 1997), preview "Groovy Wheels", Elliott Chin | 49 | TRIP = "Totally Realistic Interactive Project", "over a dozen missions"; 25 vehicles, 20 weapons; "non-essential items that simply add to the atmosphere (such as cup holders)"; Multi-Melee "in over a dozen arenas"; **melee scoring "awards more points to those skillful few who record kills with less powerful weapons"**; Internet play still only "hoped" | weapon-weighted melee scoring did not ship as described; an expansion could add it as a game mode |
| `Computer_Gaming_World_Issue_155` (Jun 1997) | 133-136 | review; the host can drop out without ending the game | - |
| `Computer_Gaming_World_Issue_158` (Sep 1997) | 103 | **"Interstate '77", "an epilogue" to I'76**: player is Taurus; "a Vietnam vet named The General is pushing to instigate World War III by using Mexico's illegal oil smuggling as an excuse"; promises faster frame rate, **"incremental saves (to allow you to save at any time)"**, Direct3D, new cars and weapons, all-racing MP maps; ETA Fall '97 | yes: it became the Nitro Pack, a *prequel* with no running plot; The General is not in Nitro |
| `Computer_Gaming_World_Issue_161` (Dec 1997) | 50 | Nitro Pack: The Vigilante Files announced: play as Taurus, Jade, Skeeter in about 20 missions; **"bonus missions that can be played once all of the main character missions have been completed"**; 25 new MP maps with CTF and racing | the bonus-mission tier needs checking against the GOG Nitro data |
| `Computer_Gaming_World_Issue_163` (Feb 1998) | 38 | Nitro is a "pseudo-prequel... no campaign or running story"; nine new cars including an Army Jeep, limousine, ice cream truck, hearse | matches retail |

### 3.3 PC Zone (UK)

| issue | leaf | what it says |
|---|---|---|
| `PCZone041` (Aug 1996) | 11 | earliest UK preview: "team up with auto-vigilante Taurus... with only their revolvers, eight-tracks and attitudes"; "equip his car with even cooler weapons and other unique power-ups, until he's strong enough to be crowned **'King of the Road'**" |
| `PC_Zone_Issue_066_1998-08_Dennis_Publishing_GB` (Aug 1998) | 65 | **early I'82 premise:** "As Taurus, your main task will be to rescue your partner, who's been kidnapped by vicious highwaymen and held ransom in the depths of a run-down Las Vegas"; ETA Nov '98 (shipped Nov 1999); calls I'76 "Interstate '77" |
| `PC_Zone_Issue_069_1998-11_...` | 49 | I'82 preview |
| `PC_Zone_Issue_084_1999_..._christmas_edition` | 51-52 | I'82 review: on-foot car swapping; Groove's story continues |

### 3.4 Next Generation, other issues

| issue | leaf | what it says |
|---|---|---|
| `NextGeneration36Dec1997` | 107-109 | **Vigilante 8 preview.** Developer Luxoflux, three people; "borrows several locations, characters, and vehicles from I'76" and is a prequel set in 1975, with Malochio and the Creepers on one side and Convoy's vigilantes on the other. Focus testing showed "gamers didn't want a mission-based game". The car-select caption: "fans of I-76 will immediately recognize these Vigilante characters and their unique muscle cars". Local Ditch trivia says Taurus and Jade were playable in early V8 builds and cites this issue (C; the OCR does not name them) |
| `NextGeneration37Jan1998` | 5 (contents) | lists an "Interstate '76 Nitro Pack" preview. **The page was not found by OCR search**; read the scan by eye |
| `NextGeneration47Nov1998` | 74 | I'82: Norman: "I described I-76 as Road Warrior meets Shaft, I'm describing I-82 as the Road Warrior meets Miami Vice"; every weapon has a countermeasure; exit-vehicle "Multivehicle Combat" |
| `NextGeneration48Dec1998` | 81 | I'82 preview |

### 3.5 Developer interviews: mirrors on Local Ditch (A, as transcribed)

- **OGR, Scott Krager (1997)**, <https://www.localditch.com/interstate-76/articles/ogr.html>:
  - Norman's line: "The future is boring";
  - the handgun was in the design from the start;
  - follow-ups were "not set in stone yet... the I '76 gang will return";
  - the band's core tracks were recorded at Royaltone, Los Angeles.
- **Gamezilla, 1996**, <https://www.localditch.com/interstate-76/articles/gamezilla.html>:
  - "over 30 missions created", 25+ minutes of cutscenes, "several hours of voice-over", about 70 minutes of music
    by a six-piece band;
  - Groove was written with a feature film in mind ("an actor like Brad Pitt"); Taurus drew on Samuel L. Jackson's
    Jules.
  - Retail has 17 TRIP missions. The other 13 or so of the "30 missions" are presumably training, the S-scenarios and
    the melee maps; the exact split is unknown.
- **Games Domain, Feb 1997 (Edward Fielding)**, <https://www.localditch.com/interstate-76/articles/gamesdomain.html>:
  - the reference films the team watched: *Starsky & Hutch*, *Dukes of Hazzard*, *Shaft*, *The Mack*, *Bullet*
    [sic, probably *Bullitt*], and *Pulp Fiction*;
  - the slip from November 1996, explained above.
- **Ernest Adams, "Designer's Notebook: Interstate '76 and the Principles of Harmony" (Gamasutra, 15 Jan 1999)**,
  <https://www.gamedeveloper.com/design/designer-s-notebook-i-interstate-76-i-and-the-principles-of-harmony>,
  interviewing Vesce:
  - the cinematics were planned in real time and became pre-rendered;
  - the cars are fictional so they can carry weapons;
  - the menus live in the fiction (order pad, receipts, paper-bag maps, label maker).
  - **Vesce's hindsight list:** easier controls, clearer objectives, more frequent rewards, a simpler repair screen,
    splitting long missions (especially the first), save-anywhere, MP anti-cheat, more balancing time.
- **Zack Norman, Interstate '82 Initiative forum post (undated, c. 1999)**, mirrored at
  <https://www.localditch.com/interstate-76/articles/interstate-82-initiative.html>. The original was on netbabbler
  forum 4388 and was **not fetched**.
  - Norman calls I'76's damage system "too detailed to be very useful".
  - I'82 merges armour with chassis reinforcement, drops facings, adds an internal damage value and five-level part
    malfunctions.
- **Dev Game Club ep. 424 (2 Apr 2025)**, <https://www.devgameclub.com/blog/2025/4/2/dgc-ep-424-interstate-76-part-three>,
  with the Jerez text at <https://www.localditch.com/interstate-76/articles/devgameclub.html>.

### 3.6 Pre-release images and unused files (C: Local Ditch, <https://www.localditch.com/interstate-76/pre-release.html>, updated through 2026-10-07)

- Early Piranha: one hood stripe, different rear and dash, roof weapons; PC Gamer Apr 1997.
- Taurus's junkyard car with front-mounted guns.
- An early radar-only HUD with no Mr. Damage readout (Score, Czech, Nov 1996).
- **An unused junkyard scene, "Zack's Auto Wrecking"**, intended for the intro, never shipped.
- A cutscene not in I'76 that was later reused in the Nitro credits.
- **Unused multi-melee entry form and an unused level-select screen inside `DATABASE.MW2`.** We hold this file:
  the retail and demo copies. An offline look at its unused screens costs nothing and would show what the shell
  was meant to offer.
- **Interstate '77 material:**
  - Taurus's partner was "Jenny" before being replaced by Jade;
  - a mock-up of a possible I'77 cover;
  - a 1997 E3 clip of Krager and Norman, from the *Infinite MHz* show.
- Trivia (C) on the cut handhelds. Krager: "The original design called for a variety of handhelds, but we had to cut
  because of time". The cut list is a sawed-off shotgun, a grenade launcher and a **Molotov slingshot**, and the
  **parts catalog still lists them**.
- More trivia (C):
  - running out of gas was in the original design documents;
  - `freelance` was an artist tool for rotating through buildings;
  - Activision's I'76 site cut its multiplayer section first.
- Trivia (C): an **early I'76 preview video ships in the `avi` directory of MechWarrior 2: Mercenaries**, with the
  older 'Ranha paint.
  - It can be checked on archive.org `MechWarrior2MercenariesUSA` (651 MB zip, **not downloaded**).

### 3.7 Demos and betas

- **The March 1997 demo** (`Interstate76_1020`; T03 and T14, `SMK\PREVIEW.SMK`, its own `DATABASE.MW2`) was linked
  eight days *after* retail and shares retail's shell. It is not a pre-release build. Already covered in
  [records/I76-VERSIONS.md](../../records/I76-VERSIONS.md) §2.1.
- **The Arsenal demo** (`Arsenal_201610`, Feb 1998) holds one Gold mission and one Nitro mission. Also in
  I76-VERSIONS.
- **Beta builds.** Reviewers got cassette-style "Gold Master" copies (Local Ditch). Games Domain's writer had "an
  early beta... not all together playable". A former Activision "Visioneer" says they beta-tested Nitro (Local Ditch
  Q&A). **No pre-release build of I'76 has surfaced publicly**; none was found on archive.org.
  - The "1996 E3 and preview builds" stay on the "not held" list.
- The **Score 35 CD (Nov 1996)** (`score35cd`, 740 MB bin, **not downloaded**) is the coverdisc of the issue that
  carried the earliest HUD screenshots. It may hold a preview video or screenshots from the pre-release build. This
  is the most promising unfetched lead for pre-release material.

### 3.8 Source code, SDK, editors

- **No official SDK or mission editor was ever released, and no leak of the game source was found.** Krager's 1997
  answer on host controls was "Stay tuned...". Local Ditch Q&A: weapon values were "discovered with a little bit of
  hex editing".
- Community tools (already indexed in COMMUNITY-RESOURCES §1a/§3):
  - Hack76 and the AVA utilities;
  - I76edit;
  - the Nitro mission builder;
  - route380's tools;
  - I26's 3D map editor.
- Only ANet, the network library, is open (LGPL).

## 4. Nitro Pack, Interstate '77 and Interstate '82

- **The chain.** The first plan was Interstate '77, a Fall '97 *epilogue* with Taurus against The General and a
  Mexico oil-smuggling war (CGW #158). It became **Nitro Pack: The Vigilante Files**, a Feb 1998 *prequel* anthology
  (CGW #161 and #163).
  - The trivia says the early Nitro story had Taurus escorting gasoline runs for the Mexican government.
  - Nitro shipped as about 20 missions dated Jan 1974 to Jul 1976, "like a syndicated TV series" with no fixed order
    except "Two Days Before" (Local Ditch Nitro story).
  - It is called *Nitro Riders* in Europe.
- **The Interstate '77 story was never used.** The General / WWIII-via-Mexico plot appears in neither Nitro nor
  I'82. It is the best documented "lost sequel" story.
- **I'82** (Nov 1999):
  - Taurus is the protagonist; Las Vegas; the Reagan era;
  - music by Josh Mancell plus unreleased Devo songs;
  - Dark Side engine, out-of-car play;
  - about 17 linear levels (PC Gamer Argentina/Spain, Nov 1999, `pc-juegos-pc-gamer-13-noviembre-1999` leaf 23-24).
  - The Aug 1998 premise was Taurus rescuing a kidnapped partner from highwaymen in Las Vegas (PC Zone #66).
  - Cut or broken in I'82 (Local Ditch): an in-car cockpit HUD (performance problems, and water drew over it), and a
    handgun that cannot kill drivers.
  - Its filtered dialogue is installed but disabled.
  - **No I'82 content is reusable in the I'76 engine as is**, but its characters and its 1982 coda are canon.
- **Vigilante 8** (PS1, 1998, Luxoflux) began as a PlayStation port of I'76. Focus testing turned it into a
  1975-set arena prequel. The I'76 PlayStation version itself was cancelled (MobyGames, Wikipedia category). V8
  arenas are listed in NG #36: oil fields, a ski resort, Hoover Dam, a secret military base.

## 5. Soundtrack and poetry

- **The band is "Bullmark", not "Bullet".** Members per Local Ditch music page and Wikipedia citing WeFunkRadio:
  - Arion Salazar (bass, writing; later Third Eye Blind);
  - Tom Coster (keys, Santana);
  - Bryan "Brain" Mantia (drums, Primus);
  - David Shul (guitar), Les Harris (horns), John Bendich (percussion).
  - Production: Jason Slater, with Eric Valentine engineering. Executive producer: Kelly W. Rogers.
  - "Bullet" in the brief probably comes from the film *Bullitt* that Games Domain lists.
- **Official soundtrack CD (Activision, 1997):** 32 tracks per Local Ditch: game cues, dialogue, and **unreleased
  Bullmark tracks from the sessions**.
  - Some game edits differ in length: "Malochio Down" runs 1:02 in game and 1:46 on the CD; "Skeeter Gettin'
    Medieval" 2:07 in game and 1:13 on the CD.
  - The label and catalog number were not verified; only eBay listings were found, and eBay blocks fetches.
- **The "Bullmark demo"** has 24 tracks, formerly on arionsalazar.com. Titles include "DESTRON Super Jam", "Twamp
  Sack" and "Kanegon". It is archived with the CD rip and a game-disc rip in archive.org `Interstate76-Soundtrack`
  (597 MB zip, lossless except the demo; **not downloaded**).
  - Local Ditch lacks one demo track, "Ma... Something Like This" (Q&A 2014).
- Nitro has an 11-track listing, partly reused. I'82 is by Josh Mancell and Devo.
- **Poetry.** There are 15 Taurus poems, recited on the CB with "C" in a fixed order, voiced by Greg Eagles.
  - Norman wrote at least several of them, drawing on Delaware, Edinburgh and Boston ("This window above the
    Charles", "Copley brought me to a monument").
  - No unused poems are documented. The `freelance` code is not a poetry code (see §3.6).
  - A rip of the voice lines is at archive.org `i-76voices`, taken from GOG WAVs.

## 6. Film and TV

- **Film rights went to 20th Century Fox and Davis Entertainment (John Davis), reported 6 March 1998** (Hollywood
  Reporter, Josh Chetwynd, "Fox, Davis win '76' film rights"). Verified from the archived HighBeam abstract:
  <https://web.archive.org/web/20171107023304/https://business.highbeam.com/2012/article-1G1-55819524/fox-davis-win-76-film-rights>.
  - The pitch line was "'The Road Warrior' meets 'Mod Squad'... a team of young vigilantes fighting a repressive
    system."
  - Nothing came of it (Wikipedia). No writer was ever attached in any source found.
- **No TV adaptation was found.** The Nitro Pack's own design brief was TV-shaped: episodes dated out of order,
  "like a syndicated TV series".
- Gamezilla (1996): Groove was written with a film in mind (Brad Pitt type).

## 7. What this suggests for an expansion, ranked by how well it is sourced

1. **"Interstate '77": The General.** Taurus, a post-1976 epilogue, a Vietnam vet using Mexican oil smuggling to
   start WWIII, and a Mexico border setting. *Source:* CGW #158 leaf 103 (B), Local Ditch trivia and pre-release (C).
   - It is officially planned and never used, it is canon-adjacent, and the original cast is available.
   - It slots after the 1976 ending and before the 1982 sequel.
   - It also fits the E3 1997 clip. Find the *Infinite MHz* footage before writing the story.
2. **The cut handhelds as player weapons:** sawed-off shotgun, grenade launcher, Molotov slingshot. They are already
   named in the parts catalog. *Source:* Krager via Local Ditch trivia (C).
   - Check the shipped catalog strings and the weapon table for stub entries first. If stubs exist, the slot is
     already allocated.
3. **A fuel mechanic** ("running out of gas was in the original design documents"), with 7-11 / gas-station pit
   stops as the refuel points. *Source:* trivia (C); NG #23 caption (B).
   - It fits the setting's whole premise.
4. **Time-pressure objectives that degrade the map,** as in the diner that is "gutted by the time you get there".
   *Source:* NG #23 (B).
   - The FSM mission scripting can already express timers; this needs mission design, not engine work.
5. **The cut nuke plot.** Malochio is "hired by OPEC to detonate a nuclear warhead". *Source:* NG #23 (B).
   - It can serve as an alternate-history mission or the climax of a "what if" TRIP.
6. **Weapon-weighted melee scoring:** more points for kills made with weaker weapons. *Source:* CGW #153 (B).
   - It is a server-side scoring rule. It fits the Nitro-MP work and is cheap.
7. **Nitro-style episodic mission packs** in an out-of-order "syndicated TV" format. Two candidate unlock tiers:
   - the **post-campaign bonus missions** CGW #161 promised;
   - a New Game+ (Local Ditch "A Look Forward", 2026).
8. **Music:** the unreleased Bullmark session tracks and the 24-track demo are real period funk by the same band.
   - Using them as new-mission cues is the most authentic music expansion possible.
   - The rights belong to Activision and the musicians. This is for the owner's own use unless cleared.
9. **Story beats from the unused art:**
   - "Zack's Auto Wrecking" junkyard intro;
   - Taurus's gun-nosed junkyard car;
   - "Jenny" as the original partner.
   They are small, but they supply set dressing and a character with documented origins.
10. **"King of the Road"** (PC Zone #41): the early progression goal, a title after full upgrades. It could name a
    melee ladder or an end-of-pack reward.

## 8. Open leads (not fetched)

- **NG #37 (Jan 1998) Nitro preview.** It is in the contents but was not located by OCR; read the scan by eye.
- **Score 35 CD (Nov 1996)**, archive.org `score35cd`: likely pre-release I'76 media.
- **MW2 Mercenaries `avi` directory:** the early I'76 preview video.
- **The *Infinite MHz* E3 1997 Krager/Norman clip:** the Interstate '77 pitch on camera.
- **The original 1996-97 Activision I'76 site and its removed Multi-Melee guide.** interstate76.com/activision
  returns 403 to fetchers; use Wayback in a browser.
- **The netbabbler I'82 Initiative forum (id 4388):** more Norman design posts.
- **`DATABASE.MW2` unused screens:** we hold this file, so this is a local job.
- **The parts catalog's cut-weapon names:** check the shipped strings.
