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
