# Co-op missions as their own multiplayer arenas (2026-10-18)

Owner, 2026-10-18: *"Instead of taking the place of one of the existing/known melee missions, the coop missions should
be named as themselves in the list menu and added separately yes? Also are there popular maps that people like to play
online in the community we should add? Don't make a mess just like the 3-5 most popular if there are any serious
ones."*

Why: the LAN pack put the co-op T01 in place of The Crater (`miss8\M01.MSN`, `miss16\M01.MSN`). On 2026-10-18 the
Steam Deck (its own files, stock M01) hosted The Crater and Andrew's Mac (the pack's co-op M01) joined: different
missions, the joiner's car never spawned, no message (LAN-MATRIX-2026-10-18.md cell 5).

## 1. How the shell builds the arena list (static, i76shell.dll a300db63; addresses = i76-map export)

The game already has an add-on arena route. It is the one the 1997 builder documents (`BUILDER\BUILDER.DOC`: "Copy
the .LVL and .TER files into the ADDON directory ... Your mission will be listed in addition to the ones included with
the game"):

| what | where | detail |
|---|---|---|
| stock arenas | table at `0x1004b510`, 15 records of 0x2d bytes: title[32] + file[13] | "The Crater" m01.msn .. "A Lot of Asphalt" m15.msn; count `DAT_1004b2f8` = 0xf |
| add-on arenas | `FUN_10027c80` (host form init): `findfirst("addon\*.lvl")` (string `0x1004c0a4`) | per file a 0x2d record: file name at +0x20, title read by exe callback `[0x10058198]+0x58` (the WRLD mission title, body +0x13b, 16 bytes) into +0; list `DAT_100f2194`; count += n |
| drawing | `EntryForm_DrawArenaList` 0x1002b350 | index < 15 from the table, else `list[index - 15]`; 6 rows visible, scrolled by `DAT_100f21b0` |
| no fixed width | the add-on list is a growable list (`FUN_10027870(0x100)` / `FUN_10027970`) | 17 add-ons need no change |
| file to load | host form, `10028610` line 254: index < 15 -> `0x1004b530 + i*0x2d` ("m01.msn"), else the record's +0x20 | copied to the setup block +0x5d; WinMain copies it to `0x5049f0` (0x403419); `bwd2_LoadMissionFile` 0x4b42b0 appends `.msn` only when there is no extension and opens the name through the VFS (ADDON first) |

### What goes over the wire

- The host's join reply ('JO', `net_SendJoinAccept` exe 0x455fa0, 0x50 bytes) carries the **mission file name**
  (`0x5049f0`, at +0x32) and `[0x504a04]` (at +0x44). So the joiner loads the file the HOST names. That is the Deck
  failure: the name "m01.msn" was the same on both, the contents were not.
- For an **add-on** arena the host's shell (`FUN_1002f368`, at session start) opens `addon\<file>` and puts its CRC-32
  (`Crc32_File` 0x10022bc0: poly 0x04C11DB7, MSB first, init and final xor ~0) in its setup +0x6c; the exe copies it to
  `0x504a04` once (0x40253e). The joiner's shell (`FUN_1002fcd8`, the 'JO' handler) sees the `.lvl` extension
  (`0x1004c7dc`), opens `addon\<file>` and:
  - missing: *"You don't have mission %s! Check Activision's web page for additional missions!"* (`0x1004c7f0`),
    join cancelled;
  - CRC differs: *"Your mission file %s does not match the host's"* (`0x1004c848`), join cancelled.
- For a **stock** `.msn` neither check runs. A stock name can never be safe for a changed mission.

- **The extension test is case-sensitive** (5-byte compare with ".lvl", host `0x1004c6ec`, joiner `0x1004c7dc`), and
  the add-on file name is whatever `findfirst` returns. Measured: with `COOP01.LVL` the host's slot `0x504a04` was 0
  and a join went through with no file or CRC check at all; with `coop01.lvl` the slot was `e1dcaa33`, exactly the
  CRC-32 computed offline over the file (coop05: `ca8b4bae`, also equal). So the files must be lower case.

So the least invasive form needs **no code at all** for the list: the co-op missions go into ADDON as lower-case `.lvl`
files with their own names and titles. Nothing in the exe or the shell is patched.

### Side effect seen in the code (cosmetic)

When the host has not typed a game name, picking an arena copies `0x1004b510 + index*0x2d` as the default name
(`10028610` ~line 735) for every index, also >= 15; for add-ons that reads past the stock table (index 16 lands on
"Oil Well Well", the scenario table at `0x1004b7e0`). The arena itself is right; only the suggested session name is
wrong. GAME-NIGHT already says to RENAME the game.

## 2. What changed

| file | change |
|---|---|
| `tools/coop-install.py` | builds `ADDON\coop01.lvl .. coop17.lvl` (lower case, above) from `miss16\T01..T17.MSN`, titles "Co-op Scene 1" .. "Co-op Scene 17" (the game's own name for the trip missions is "Scene N"); removes the old layout (M41..M57 in miss8/miss16, the co-op M01) and puts the stock M01 back (md5 f00bad90 / abb41681 = the pristine GOG files) |
| `tools/coop-mission.py` | `--title` sets the WRLD title |
| proxy `I76_COOP_CHAIN` | chain keyed on `coopNN.lvl`: coop01 -> coop02 ... coop17 = normal end; any other network mission (every melee) is left alone; on a host chain reload `0x504a04` gets the next file's CRC (only when it holds the current file's), else a late joiner would be refused by the check above |
| proxy, all co-op sends | **crash fix**, section 3.3: every buffer given to ANet's `dpSend` keeps 16 spare bytes |
| `tools/mp-pack.py` | docstring and PLAY-LAN.bat comment |

miss16, not miss8: the two folders differ only in the WRLD palette / sky / horizon names (8-bit vs 16-bit art). The
pack machines run hardware renderers (dgVoodoo Glide on the PC, OpenGlide on the Macs); a `.lvl` in ADDON is used in
either mode. Not checked: which art the Deck's Proton build uses (it is not on the pack yet).

## 3. Tests on the PC (2026-10-18 09:40-10:24, console lock held in three stretches)

Copies: `i76-uncap-lab\game-cooplist` (A) = a copy of the LAN copy `Interstate76-LAN-2026-10-17` (i76.exe 6319abf7,
i76shell a300db63) with `coop-install.py` run on it (old layout removed, stock M01 back, 17 add-ons);
`game-cooplist-b` (B) = a copy of A with the instance-B `ipxwrapper.dll` (fad787e8, own mutex and registry key,
lab MULTIPLAYER-LOCAL-TEST.md section 9). Both started directly (`i76.exe -glide`, the folder's wide dgVoodoo conf)
with `I76_COOP_AI=1 I76_COOP_CHAIN=1 I76_MULTI_INSTANCE=1 I76_NO_MINIMIZE=1`, driven by a copy of
`tools/lan-test/pcnav.sh` (i76probe). Proxy: this branch (final build `ba2b45c1`). Evidence files:
`i76-uncap-lab\captures\coop-list-20261018\`.

### 3.1 The list

HOST > IPX: the arena list holds **32 entries** (shell count `DAT_1004b2f8` = 0x20 = 15 + 17). Scrolled to 12 it reads
Dodge, Jorczak's Peak, A Lot of Asphalt, **Co-op Scene 1, Co-op Scene 2, Co-op Scene 3** (`a-list12.png`); the first
15 rows are the stock arenas in their stock order (The Crater .. A Lot of Asphalt). Selecting Co-op Scene 1 shows it in
the AREA OF PLAY box (`a-sel1.png`), arena index 15. The suggested GAME NAME went blank (the out-of-table read of
section 1); typed a name.

### 3.2 What loads (probe: `0x5049f0` mission name, `0x504a04` join CRC, player table, proxy log)

| arena picked (index) | file loaded | evidence | n |
|---|---|---|---|
| Co-op Scene 1 (15) | `coop01.lvl` | the host adopts the T01 player object `vppirna4` (proxy), host car 3337.5, 35872.5, Taurus `t01js01` and the tractor `vxktrac1` in the mission car table, CRC slot e1dcaa33 | 1 (+5 boots with the upper-case `COOP01.LVL`, same mission, slot 0) |
| Co-op Scene 5 (19) | `coop05.lvl` | T05 player object adopted, CRC slot ca8b4bae | 1 |
| The Crater (0) | `m01.msn` (stock, md5 = pristine) | host spawn 2092.5, 101.0, 49752.5; no mission player object (a melee) | 1 |
| Suburbia (3) | `m04.msn` | host spawn 4732.5, 120.9, 49427.5 (= the LAN-matrix Suburbia spawn) | 1 |

### 3.3 Two copies on the PC (IPX through IPXWrapper on loopback)

1. **Join with the file:** B (JOIN > IPX) listed "coophost (1/4)", JOIN GAME: B net 1, me 6, host 3, mission
   `coop01.lvl`, both cars in both tables; B's proxy: role joiner, 156 'AT' packets in, 4 objectives applied, mission
   cars mirrored (Taurus `t01js01` and the tractor in B's table). n 2 (upper-case name, no check; lower-case name,
   CRC checked and equal).
2. **Join without the file** (B's `coop01.lvl` hidden): the join stopped with the game's own box *"You don't have
   mission coop01.lvl! Check Activision's web page for additional missions!"* (text read from the box, Win32), B
   stayed on the roster. n 1. This is the Deck failure turned into a message. Not run: the CRC-mismatch box (static
   only, `0x1004c848`).
3. **A host crash at every co-op reload, found and fixed.** Sitting still, the T01 script fails the mission after ~75 s;
   the chain then reloads it ("host lost 'coop01.lvl' -> loading 'coop01.lvl'") and the host process died with
   0xC0000409 (stack cookie) in Strlkup.dll, every time:

   | proxy | layout | n | result |
   |---|---|---|---|
   | this branch, first build (and its map build for the dump) | add-ons | 4 (1 with a joiner) | host crash at the reload |
   | the build before this branch (a3befe1) | add-ons | 1 | host crash |
   | the build before this branch | **old layout, M01 = co-op T01** | 1 | host crash |
   | **the LAN pack's deployed proxy 33211f11** | **old layout** | 1 | host crash |
   | this branch, fixed (`ba2b45c1`) | add-ons, host + joiner | 1 | **both reloaded coop01 and played on** (host and joiner tables agree: host car 3698.2 / 3698.3) |

   Cause, from a full dump (procdump) of the crash: `coop_chain_at_end` (with `coop_chain_send` inlined) had its
   cookie overwritten by `03 00 04 00`, the 4 bytes right after the 20-byte 'AM' packet: ANet's `dpSend` writes the
   from / to ids (3, group 4) after the payload it is given. The packet was the last local before the cookie. So the
   **game-night LAN pack as deployed crashes the host whenever the co-op chain reloads** (a loss, or a win to the next
   mission); a joiner is not affected (the session migrates to it, as seen). Why the 2026-10-07 runs (16/16 reloads)
   did not crash is not measured [inferred: that build's frame put other locals, not the cookie, after the packet].
   Fix: every buffer handed to `dpSend` keeps 16 spare
   bytes (the 'AM' and 'AO' packets on the stack, the 'AC' queue); the 'AT' buffer (512 for at most 208) already had
   room. The win path (next mission) was not run here; it sends the same packet.

### 3.4 What the LAN agent still has to check across machines

1. Rebuild the pack with this `coop-install.py` and the fixed proxy, and put it on every machine (the Deck too:
   without `coop01.lvl` it now gets the "You don't have mission" box instead of a wrong mission).
2. On each Mac and on the Deck: the 17 files arrive as **lower-case** `ADDON/coop01.lvl ..` (a copy that upper-cases
   them disables the check), the host form lists Co-op Scene 1..17 after A Lot of Asphalt.
3. A co-op host on a Mac (Wine's `findfirst` order and case) and a PC joiner, and the reverse: joined, mission
   `coop01.lvl` on both, the probe's CRC slot `0x504a04` = e1dcaa33 on the host.
4. A loss (sit still ~75 s in Scene 1) and a win (next mission) with a joiner on another machine: both reload, no
   crash (the fix above), both in `coop02.lvl` after a win.
5. A late joiner after a win (host in coop02): it must join (the proxy puts coop02's CRC in the slot, log line
   `coop-chain: join CRC ... -> ...`); not measured here.
6. A machine without the files (the Deck before its update): the box, no join.
7. Stock melee still as before (Suburbia; The Crater is now the stock Crater again on every machine).

## 4. Community melee maps: none added

Criteria (owner's "only serious ones"): still downloadable from a traceable source, made for melee / multiplayer,
named by more than one source as played or popular today, redistribution acceptable with a known author.

What exists (web search 2026-10-18, a sonnet research pass plus two searches of my own, and the repo's own crawl
`docs/COMMUNITY-SITEMAP.md` of 2026-08-09):

- **DIVER's I'76 Terrarium** (route380.stars.ne.jp): 40 fan maps, all already mirrored in `refs/route380/maps/`
  (the Dojo, GunsOnly, Nowhere N.M., Suburbs, Ruins, races and drag strips ...), Gold install rule `.cbt`/`.rac` ->
  `.lvl` into ADDON.
- **Local Ditch** (localditch.com/interstate-76/maps): 19 zips with authors, 10 "Combat" (76th Precinct by Stingray,
  Biggsville by Lt. Stinger, Bordertown TX / Burger Run / Intercept Pursuit by Debacle, Drug Bust by Captain Gram,
  Leather Town by Skull N. Bones, Modland 4 by Funky Speed, New Haven 1.1, Rage County by General Rage), 2 AVA arenas.
- **interstate76.com/download**: `allnitromaps.zip`, `DIVERmappack.zip`; "Lightfoot's Stolen Maps" (a frameset, list
  not readable; a 2010 GOG thread speaks of ~250 user maps).
- Online play today: no source names a map anyone plays. Local Ditch says online play is "basically non-existent now";
  the active remnant uses Nitro Pack with an ANet2 lobby (inbetweennames.net/projects/interstate76anet), a Facebook
  group, and (2010) Tunngle. No Discord or ModDB scene with map lists was found.

Verdict: **no map meets the "played / popular, more than one source" criterion**, so none is added. The archives are
real and authored, but nothing separates three to five of them from the other ~60 except guesswork. If the owner
wants to try some anyway, the route is the same as the co-op entries (lower-case `.lvl` + `.ter` in ADDON on every
machine), and the Combat maps above are the natural shortlist.

Sources: https://www.localditch.com/interstate-76/maps/ ,
https://route380.stars.ne.jp/i76/resource_i76/ , http://interstate76.com/download/ , http://interstate76.com/lsm/index.htm ,
https://www.gog.com/forum/interstate_series/addon_maps_not_being_found_by_interstate_76_original ,
https://inbetweennames.net/projects/interstate76anet/ , https://www.moddb.com/mods/interstate-76-mod (archived, no maps).

## 5. Follow-up (14:00): auto-respawn only in co-op missions

Owner's playtest (laptop host + Michael joiner, Suburbia, pack proxy ba2b45c1): after a death the joiner came back 5 s
later, the host stayed in the death view. Cause: the joiner auto-respawn (08ba553) ran in every network game with
`I76_COOP_CHAIN`, melee included; the host never had one. Fix (commit f2598f0): the auto-respawn runs only when the
loaded mission is a `coopNN.lvl`. Stock melee is stock for both.

The host stays stock in co-op on purpose: it drives the story's player object, the scripts watch that object, so the
host's death fails the mission and the chain reloads it for both (measured below, back alive ~10-15 s later). A host
auto-respawn would race that teardown and adds nothing.

PC, two lab copies, build 5035857f (/Brepro; two builds md5-identical), CTRL+ALT+X self-destruct, dead bit = entity
+0x454 & 0x20:

| case | result | n |
|---|---|---|
| melee (Suburbia, The Crater), host dies | still dead 25 s later, no respawn line: stock | 2 |
| melee, joiner dies | still dead 25 s later, no respawn line: stock | 2 |
| Co-op Scene 1, joiner dies | "joiner dead - respawn requested", new car alive at +14 s | 2 |
| Co-op Scene 1, host dies | "host lost 'coop01.lvl'" -> both reload coop01, both alive at +15 s, no crash | 2 |

Build note: 5035857f was compiled from f2598f0's strlkproxy.c with a simtick.c that another session was editing at the
time (its committed parent does not compile). HEAD f2598f0 (clean tree, simtick.c of 0614391, a lab experiment off by
default) builds deterministically to **ac44e2c2**; it differs only in that file and has not been run in game. Both are
in `i76-uncap-lab\builds\coop-list-20261018\`.

## 6. Owner's questions for tonight (static, from the files and the code)

**3 on 3 against the computer?** Not in stock multiplayer. The net host form has driver, arena, game name, number of
drivers, TEAM PLAY, INVITE ONLY and MAX SCORE, and no computer-player setting; the stock arenas carry no AI cars
(the proxy's mission-car count in Suburbia: 0). TEAM PLAY is real (exe strings "Team %s has reached the maximum
score", `show_team_scores`, team rows in the standings 0x1003fb40), but the teams are humans. The computer opponents
are in the single-player scenarios (S01-S07, "Oil Well Well" etc., table 0x1004b7e0), which the net host list does not
offer. The closest is a co-op scene: the humans together against the mission's AI cars (`I76_COOP_AI`, every AI
behaviour aimed at a human retargets to the nearest human, any of 16 player slots).

**How many humans in a co-op scene?** Measured: 2. In the code nothing is limited to 2 (the 'AT' / 'AM' / 'AC' / 'AO'
packets go to the whole session group, the joiner role is per machine, retargeting scans 16 slots). Each co-op file has
2 spawn points beside the hero, and the host takes the mission's own player object, not a spawn point (host at the
player start 3337.5, 35872.5; joiner at +30 m x = spawn 1), so a third human would take spawn 2 [inferred, 3 players
never run]. A 4th would need `coop-mission.py --count 3`.

**Are the scenarios multiplayer?** The "Co-op Scene N" entries are the 17 campaign trip missions (T01-T17), playable
by host + joiners as above. The single-player melee scenarios S01-S07 are not in the multiplayer list.

**Which scene for 3 humans, daylight, hills, ~3 enemies?** From the mission files (WRLD hour, mission .ter height
spread, non-player vehicle objects; which of them are hostile is decided by the script and was not read):

| scene | hour | terrain height spread (sd / range m) | non-player vehicles |
|---|---|---|---|
| 1 | 15 | 16.6 / 0-100 (flat) | 5 (Taurus is an ally, one parked tractor) |
| 9 | 15 | 17.2 / 0-100 | 2 |
| 17 | 15 | 33.3 / 0-120 | 4 (2 are trailers: t17cm01, t17mx01 + vfratlr2/3) |
| 13 | 15 | 34.4 / 0-135 | 10 |
| 8 | 15 | 28.7 / 1-110 | 8 |
| 4 | 6 (dawn) | 21.6 / 0-409 (canyon) | 3 |

Best fit to "daylight, curves and hills, about 3 enemies": **Co-op Scene 17** (afternoon, hilly, two cars plus two
trailers), but it is the story's last mission; **Scene 8** if more cars are wanted. Untested with 3 humans.

## 7. 2026-10-19: MULTI MELEE goes straight to IPX

Owner: *"perhaps would be nice to limit the non-working multi-melee modes on the menu, or just launch the right one when
use clicks before showing modem ipx whatever."*

**How the shell builds the choice (static, i76shell a300db63; this code is byte-identical to the pristine deb41008).**
Not a DirectPlay enumeration: a fixed row of five main-menu buttons, laid out by MainMenu_Layout (`Button_Init` sites
0x10027334 .. 0x100273cf) and swapped into the menu list by the HOST / JOIN handlers of the main-menu dispatch (jump table
0x1002655c):

| button | record | id | handler | effect |
|---|---|---|---|---|
| HOST | 0x100d3be0 | 3 | 0x10025dee | `[0x100d3a54]` = 1, HOST / JOIN out, MODEM IPX INTERNET NULLMODEM added, `jmp 0x10025f39` (JOIN's tail adds OTHER, shows all five) |
| JOIN | 0x100d3e80 | 5 | 0x10025e97 | `[0x100d3a54]` = 0, same; the tail ends at 0x10025f82 `jmp 0x10026515` (dispatch exit) |
| MODEM | 0x100d3f60 | 6 | 0x100260a0 | provider `[0x100d217c]` = host 2 / join 6 |
| IPX | 0x100d3dd8 | 7 | 0x100260b2 | provider = host 3 / join 7, `call 0x10027c80` (form init, arena list), message 0xc026 (network entry form) |
| INTERNET | 0x100d3eb8 | 14 | 0x100260d7 | provider 4 / 8 |
| NULLMODEM | 0x100d3da0 | 8 | 0x100260ff | provider 5 / 9 |
| OTHER | 0x100d3c50 | 16 | 0x10026127 | a 0x1000b800 popup |

**Change** (proxy `music-fix/mpmenu.c`, its own file, attached when the exe loads i76shell; every site is checked against
the stock bytes and read back):

| switch | what it does |
|---|---|
| `I76_MP_MENU=1` (**default**) | "skip": 0x10025f82 `jmp 0x10026515` -> `jmp 0x100260b2`. HOST and JOIN run their own code (the same state as stock) and fall into the IPX handler in the same click, as if IPX had been clicked next. One 5-byte relative jump |
| `I76_MP_MENU=2` | "hide": the 11 list-add / show calls of MODEM, INTERNET, NULLMODEM, OTHER in the HOST / JOIN code become 5-byte NOPs; the row shows IPX only |
| `I76_MP_MENU=0` | stock |
| `I76_ARENA_FIT` (default 1) | section 8.2 |

The default is on in the proxy itself, so every machine on the pack proxy (PC and Macs) gets it without a launcher
change; `PLAY-LAN.bat` also sets `I76_MP_MENU=1`. The Deck runs its own proxy and keeps the stock row.

**Measured** (PC, two lab copies `i76-uncap-lab\game-mpmenu` (A) and `game-mpmenu-b` (B) = copies of game-cooplist /
-b, proxy 77ad2aca = commit efa108d built with `cl /Brepro`, started `i76.exe -glide` with I76_COOP_AI=1
I76_COOP_CHAIN=1 I76_MULTI_INSTANCE=1 I76_NO_MINIMIZE=1, driven by `i76-uncap-lab\tools\mpmenu\mpnav.sh` (a copy of
`tools/lan-test/pcnav.sh` keyed on the folder) and i76probe; console lock held 08:54-09:20 and 09:41-09:45; evidence in
`i76-uncap-lab\captures\mp-menu-20261019\`):

| check | result | n |
|---|---|---|
| MELEE > MULTI MELEE > HOST | lands on NET MELEE HOST EVENT FORM: shell screen 0xc026, frame fn 0x10028610, provider `[0x100d217c]` = 3 (`a-host1-ui.png`) | 9 |
| MELEE > MULTI MELEE > JOIN | lands on NET MELEE ENTRY ROSTER listing the host's game "coop1 (1/4)", provider 7 (`b-join1-ui.png`) | 4 |
| host A, join B | joined (B: net 1, me 6, host 3, same mission) | 3 (Oil Well Well, Pretty Bus, Scene 1 (Co-op)) |
| host B, join A | Suburbia; both copies hold both cars at the same coordinates | 1 |
| `I76_MP_MENU=2` | HOST shows the row with IPX only (`a-hide-ui.png`, menu list = button 7); IPX opens the host form, provider 3 | 1 |
| proxy log | "skip ... patched, read back OK" at every start | 14 |

## 8. 2026-10-19: the single-player scenarios in the list, new titles

Owner: *"would like to see the solo auto melee missions added to the list of options including coop multiplayer missions
(both labeled accordingly)"*; on the names: *"start with the actual name then (Scenario) please i think the name is most
important"* (same rule for the co-op entries: name, then " (Co-op)").

### 8.1 The list as it reads now (host form, 39 entries; shell count `0x1004b2f8` = 0x27, measured)

| index | title | file |
|---|---|---|
| 0-14 | The Crater .. A Lot of Asphalt (stock, unchanged) | m01.msn .. m15.msn |
| 15 | Oil Well Well (Scenario) | auto01.lvl = S03 |
| 16 | Mondo Burger (Scenario) | auto02.lvl = S02 |
| 17 | Seminole (Scenario) | auto03.lvl = S04 |
| 18 | Pretty Bus (Scenario) | auto04.lvl = S05 |
| 19 | Race No Shoot (Scenario) | auto05.lvl = S06 |
| 20 | Trailer Pk. Madness (Scenario) | auto06.lvl = S01 |
| 21 | Milk Toast (Scenario) | auto07.lvl = S07 |
| 22-38 | Scene 1 (Co-op) .. Scene 17 (Co-op) | coop01.lvl .. coop17.lvl (names unchanged) |

Order: the scenarios follow the game's own AUTO MELEE > SCENARIO table (0x1004b7e0); the files are named `autoNN` so
that `findfirst` (alphabetical on NTFS) lists them before `coopNN`. On a Mac (Wine) or the Deck the directory order is
the host file system's and was not checked. The trip missions have no title of their own (the WRLD title is empty in
all 17; the game calls them "Scene N" in the bookmarks), so the co-op entries read "Scene N (Co-op)".

**Title length.** The WRLD title field is the last 16 bytes of the WRLD body (15 characters). The arena list reads it with
a strcpy from the chunk (exe 0x4b4a10, chunk +0x143 = body +0x13b) and the shell keeps 31 characters (strncpy 0x20,
0x10027ea0), so `coop-mission.py --title` now grows the body by 16 bytes for a longer title; the mission loader reads
WRLD by fixed offsets up to body +0x137 (0x4b8a10), and every grown file loaded (8.4).

### 8.2 The box is narrower than the titles: I76_ARENA_FIT

The list box holds about 178 pixels of the handwriting font (~19 characters). "Oil Well Well (Scenario)" ran over the
right border, and because the list clears only its box (0x10038fd0, x 11 w 206) the overflow stayed on screen as smeared
glyphs (`a-list-strip.png`). The proxy (mpmenu.c, `I76_ARENA_FIT`, default on) repoints the two text calls of
EntryForm_DrawArenaList (0x1002b3af the chosen arena, 0x1002b421 the rows) to a stub that measures the title with the
shell's own glyph width (0x1003e42c) and, when it is too wide, shortens the **name** with a "." and keeps the kind
suffix whole. As drawn (`b-list-strip.png`): Oil Well. (Scenario), Mondo Bu. (Scenario), Seminole (Scenario), Pretty Bu.
(Scenario), Race No S. (Scenario), Trailer P. (Scenario), Milk Toas. (Scenario); Scene 1 (Co-op) .. Scene 17 (Co-op)
fit whole.

The files keep the full titles. **Open question for the owner:** at this width "(Scenario)" takes about half the line;
the full names would fit with a shorter kind tag (e.g. "Oil Well Well (S)"), which the 2026-10-19 rule ("never abbreviate
the suffix") excludes. It is one constant (`SCEN_TITLE` in coop-install.py) if he prefers that. A machine without the
pack proxy (the Deck) draws the full titles with the overflow.

### 8.3 What a scenario needs, and the respawn rule

Static read of S01-S07 (FSM scripts, `i76-map\data\out\fsm\s0N.fsm`; helpers and an edit set in
`i76-uncap-lab\tools\mpmenu\fsmwork\`):

| scenario | objective (script) | AI vehicles (measured on the host: mission cars no human drives) |
|---|---|---|
| Oil Well Well (S03) | kill 5 enemies, do not lose more than 17 of 20 wells | 8 |
| Mondo Burger (S02) | beat Taurus to the finish, then kill > 5 gang cars with Mondo intact | 7 |
| Seminole (S04) | kill 5 enemies, protect the post office | 10 |
| Pretty Bus (S05) | escort the bus, kill 5, be within 40 m of the bus at the end | 8 |
| Race No Shoot (S06) | reach the finish line (cops, choppers, turrets) | 9 |
| Trailer Pk. Madness (S01) | destroy 10 trailers, kill 5, do not let "hate" escape | 10 |
| Milk Toast (S07) | destroy the milk truck before it reaches the garage, kill 5 | 10 |

What a scenario needs beyond a co-op scene: its own AI cars (already in the file; the proxy's `I76_COOP_AI` runs them on
the host and mirrors them to joiners in any network mission, no change needed); spawn points for joiners
(`coop-mission.py --count 3`: 4 humans = the host form's default NO. DRIVERS); no movies to strip (the S files have none).

**Respawn rule chosen: joiners respawn by themselves (melee-style); the host's death is the scenario's loss, and any
loss reloads the same scenario for everybody; a win ends the game normally; no chain to another file.** Why not melee
respawn for the host too: every script ends the scenario on `isDead(user)` (the host's car, resolved once at load by its
ODEF label), and removing that loss is not enough. After a respawn the old car is torn down (0x4513c0 -> 0x45ed70), the
script's "user" entity becomes NULL (0x45f0f0), and `isWithinSqNav` (0x40b940), polled every frame by the exit watchers
of S01, S03, S04, S05 and S07, reads the position with no NULL check (a likely host crash; static reading); the wins of
S02, S05 and S06 need the host's original car. A host melee respawn would need the proxy to point the "user" entity at
the new car (entity record +0x58, reference 0x45ed00) plus a one-byte script edit per death check (jz -> jmp; the edit
set is in `fsmwork\make_edits.py`, round-trip checked, not applied). Not done; a follow-up if the owner wants it.

Proxy (commit efa108d): the joiner auto-respawn and the chain's loss / win handling also key on `autoNN.lvl`
(`coop_scen_num`); a won scenario ends normally (nothing follows it).

### 8.4 Tests (same copies and build as section 7)

| check | result | n |
|---|---|---|
| list order and labels | 39 entries in the order of 8.1; screenshots at scroll 12 / 15 / 18 / 24 / 30 / 33 (`a-list*-ui.png` full titles without the fit, `b-list*-ui.png` with it) | 1 |
| each scenario loads for the host | all 7: mission `autoNN.lvl`, state 5, the host drives the scenario's own car (proxy "drives the mission's player object"), AI cars 8 / 7 / 10 / 8 / 9 / 10 / 10 (auto01..07) | 1 each |
| join CRC | the host's slot 0x504a04 = 4790f803 = the shell's CRC-32 (MSB first) of auto01.lvl | 1 |
| Oil Well Well with a joiner | joined; 8 AI cars on both, same positions | 1 |
| Pretty Bus with a joiner | joined; 8 AI cars on both | 1 |
| Pretty Bus lost (the bus died, nobody defending) | host "lost 'auto04.lvl' -> loading 'auto04.lvl'", the joiner reloaded too, 8 AI on both after | 1 |
| joiner dies (CTRL+ALT+X) in Pretty Bus | "joiner dead - respawn requested", back at the start a few seconds later | 1 |
| host dies (CTRL+ALT+X) in Pretty Bus | both reloaded auto04.lvl, 8 AI on both, no crash | 1 |
| co-op unchanged: Scene 1 (Co-op), host + joiner | coop01.lvl on both, the host adopts the T01 player object, Taurus, the tractor and 3 more on both (5 = 5) | 1 |

Not run: a scenario win; 3 or 4 humans in a scenario; scenarios 2, 3, 5, 6, 7 with a joiner; the Macs and the Deck.

### 8.5 Rollout notes (for the main session; nothing was deployed)

- The co-op files change (title only, file names unchanged), so their CRCs change: every machine must get the new
  `ADDON\coop*.lvl` and `auto*.lvl` together, or joins between old and new machines stop with "Your mission file
  coop01.lvl does not match the host's".
- Pack: `i76-uncap-lab\builds\mp-pack-20261019\` (tools/mp-pack.py with `--proxy ...\builds\mp-menu-20261019\STRLKUP-77ad2aca.dll`,
  the mac part copied unchanged from the 2026-10-18 pack). Against the 2026-10-18 pack: common gains `ADDON\auto01..07.lvl`
  (+ markers), the 17 `coopNN.lvl` change, STRLKUP.DLL ba2b45c1 -> 77ad2aca; win: PLAY-LAN.bat (I76_MP_MENU=1); mac: same.
- A saved arena index now points at another entry (index 15 was "Co-op Scene 1", is now "Oil Well Well (Scenario)"):
  the host just picks again.
