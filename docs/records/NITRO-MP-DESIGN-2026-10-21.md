# Our multiplayer on Nitro, behind one separate menu entry (design, 2026-10-21)

Lane `nitro-mp-design`. Owner ruling, 2026-10-21 (verbatim): *"from a multiplayer perspective we'd want nitro to be the
basis instead of gold so we'll have some rebuilding to do there. let's try to do it nondestructively, so that community
play of nitro multiplayer is unperturbed. perhaps it's a new menu item we'd add separately but not sure what we'd call it
ai drop in coop something"*. Plan: [ARSENAL-PLAN-2026-10-21.md](../ARSENAL-PLAN-2026-10-21.md) section 2.

**Everything here is static** (Ghidra decompilation and capstone on the pristine GOG files; no game was started). RE notes
with every address: `C:\Users\james\i76-map\nitro-net\README.md` (new track; headless exports of nitshell, WIPX2, WINETS2;
tools `callers.py`, `ndis.py`, `sitemap.py`). Hook-list skeleton: `music-fix/nitro_mp.c` (not built, not included).

Files: `nitro.exe` 28b8ae27, `nitshell.dll` f804f50d, `anet2.dll` a21c2baa, `dll\WIPX2.DLL` 70f35031, `dll\WINETS2.DLL`
b91eccee (all from `i76-map\sandbox-gog\nitro-full\app`).

## Answer in six lines

1. **Receive path:** Nitro's pump `0x448d80` calls `dpReceive` through the import slot **ANET2.DLL!dpReceive 0x4c13cc** with
   the same six arguments as Gold, and **drops any packet type it does not know** after updating "last heard". Our Gold
   method (hook the import, read our 2-letter packets after the real call) carries over unchanged. No packet types are
   registered anywhere; ANet 2 only adds the system packet 'd9' (session lost).
2. **Menu insertion:** Nitro's main menu is one button table (ids 0..0x12, layout `0x10009610`) with one click dispatch,
   `cmp esi, 0x12; ja default` at `0x1000887b`. A new button **id 0x13** in the melee group, routed by changing only that
   `ja` target to a stub, adds the entry without moving any stock button.
3. **Isolation:** the shell hosts and lists sessions of ANet **sessionType 604** (`[0x10046cb0]`, = anet.inf). In our
   entry the proxy swaps that one word for our own value, so **our sessions never appear in a stock JOIN list and stock
   sessions never appear in ours**. Belt and braces: our host reports version "6.04+" so a stray stock joiner gets the
   stock "version does not match" box.
4. **Stock sessions stay stock:** with the entry unused, the proxy keeps every multiplayer switch off; a stock joiner of
   a patched host passes the host's vehicle check (`0x446120`, re-runs the car CRC from the host's own files) and its own
   version / mission-CRC check, as long as the host's car and mission files are stock (they are: we change none).
5. **Lists:** Nitro builds its arena list from files only (`*.cbt` in the game's files, then `addon\*.cbt`), no fixed
   table. The 15 original arenas are already there (N51-N65, terrain byte-identical); our AI fill works on every combat
   arena by memory injection (no new files). The 17 co-op scenes and 7 scenarios need the Gold mission files, placed in a
   folder only our entry's list reads.
6. **Estimate:** about **15 lane-days** in 8 pieces, the shell entry and the ANet 2 layer first.

## 1. ANet 2 map (nitro.exe + nitshell.dll)

### 1.1 Session create / join / list, lobby vs direct IPX

| step | where | what (decompiled; addresses in the RE notes) |
|---|---|---|
| provider | nitshell main menu ids 13..16 -> `[0x1004701c]` (host 2..5, join 6..9), `0x1002e4c0` | same numbering as Gold's shell (2 modem, 3 IPX, 4 internet, 5 null modem; +4 to join) |
| game server (lobby) | `0x10038610`: `dpCreate`, `dpEnumApp`, reads `internet.lst` / `lobby.dat`; `dpSetGameServer` at `0x1002e620`, `0x1002f2d0`, `0x10038610` | INTERNET only. IPX has no server: broadcast enumeration through WIPX2 |
| host | `0x1002f3c0`: `dpOpen(dp, &session, 0, 0)`, session record 0x5f bytes, **+0xd sessionType = 604**, +0x11 max players, +0x15 flags 0x41, +0x17 name; `dpCreatePlayer`; player data keys **1** team pick, **2** session name, **3** car block 0x198, **4** car CRC, **5** host form 0xe4; `dpCreateGroup("SIM")`; the setup block for the exe (0x324 B) | |
| list | `0x1002dfb0`: `dpEnumSessions(dp, {sessionType 604}, 0, 2000 ms, cb 0x1002e060)` | **the list asks for species 604 only** |
| join | `0x100307a0` (dpOpen of the picked session, dpCreatePlayer, keys); 'RE' resent every 500 ms with the password; 'JO' / 'JD' handled in `0x1002ffd0` | 'JO' checks: version "6.04" (`0x10045810`) and the mission file's CRC for `.cbt .rac .cf2-4 .lvl` (case-insensitive; Gold tested `.lvl` case-sensitively) |
| exe takes over | WinMain `0x431760` -> net init `0x448640` (dp `0x53f258`, me `0x53f25c`, net flag `0x53f264`), session options `0x4486d0` (flags word -> `0x53f228`, limits, password) | |

### 1.2 Receive path (the dpReceive we hook on Gold)

`net_Pump 0x448d80` (Gold 0x4532c0), called once per frame from WinMain at `0x432884`:

```c
while (DAT_006522ac == 0) {                       // pump-exit flag
  do { size = 0x200;
       r = dpReceive(DAT_0053f258, &from, &to, 0, &pkt, &size);   // IAT 0x4c13cc
  } while (r == 2 && ++tries < 3);
  if (r != 0) break;
  if ((short)from == 0) {                         // ANet system packets
    'd2' 0x3264 delete player / me -> pump exit;  'd1' 0x3164 add player;  'd5' 0x3564 added to group;
    'd9' 0x3964 "*** SESSION LOST - GAME OVER ***" (new in Nitro)
  } else if ((pkt.type & 0x8000) == 0) {
    FUN_00446bb0(from);                           // last heard
    switch (pkt.type) { 'RE','SC','SH','CH','BO','FL','SR','SP','ST','XX','YY' -> handlers }
    // any other type: nothing - read and dropped
  }
}
```

Other dpReceive callers: the join handshake `0x448950` (same as Gold 0x452f20), `0x446270` (wait for group + enum
players at load), `0x449400` (shutdown). The shell has its own receive loops (`0x1002ffd0`, `0x1002e620`, `0x1002f2d0`)
before the exe takes over.

**Consequence:** `patch_iat(exe, "anet2.dll", "dpReceive", hook)` (the import descriptor reads `ANET2.DLL`; patch_iat
compares with `lstrcmpiA`) gives the same position as Gold's hook: after the real call, before the pump's switch.
Sends go through `[0x4c13c0]` (dpSend). Every stock send uses flag 0 (unreliable), as on Gold.

### 1.3 Packet types, player table, slot flags

| item | Gold | Nitro |
|---|---|---|
| registration | none (2-letter app tags, `dppt_MAKE` order) | none; same tags + **'FL'** (flag) and system 'd9' |
| player table | 0x541070, 16 x 0x48 | **0x53ed08, 16 x 0x50**; new +0x44 float (init 1.0) and **+0x48 team int**; count 0x53ed00 |
| slot flags +0x1c | bit 0 joining, 1 team read, bits 16..18 team | same, plus bit 2 "team member announced", bit 3 "car team set" (`0x446390`) |
| team play | bool 0x541010 | **no bool**: team game = flags 0x53f228 & 0x40 (CTF) or & 0x2000 (TEAM PLAY), `0x4487e0` |
| host / group | 0x541064 / 0x541060 | 0x53ecfc / 0x53ecf8 |
| entity owner / dead bit | +0x480 / +0x454 & 0x20 | **+0x484 / +0x458 & 0x20** |

**Note for the port lane:** `sites_nitro.h` maps Gold 0x541010 -> 0x53f228 by vote. The address is right but the meaning
is not: 0x53f228 is a flag word (bit 0x8 is always set), so `aim_team_rule`'s `*(int *)0x541010 != 0` would read "team
play on" in every Nitro session. And Gold 0x452d9f (scoreboard create) is mapped to 0x4486b3, which calls 0x449730; the
scoreboard is `push 0; call 0x449ef0` at **0x4486ab** (Nitro passes an argument).

### 1.4 The 'ST' score path, host migration, the flag packet

- **Scores ride in 'ST'** as on Gold: the mirror `0x463a20` ends with `net_SetPlayerScore 0x447050` at **0x464409**
  (Gold 0x465267, unmapped in the port table). Kill credit 0x447140, death 0x4472e0.
- **Host migration** is the game's, not ANet's, and has Gold's shape: lowest id wins the handshake; a host change runs
  `0x446ea0` ("You are now the host!" / "%s is now the host!"), and the new host **republishes player data keys 2, 3, 5**
  (session name, car block, host form) under its own id (`0x4476c0`). CTF re-sends the flag state.
- **'FL'** `0x4451d0`: per team a state 0..5 (home, returned, dropped + x,y,z, captured by team, carried by player,
  carrier lost), messages "flag has been taken / returned / Team %s has captured %s's flag!", capture credit. CTF only;
  not touched by this design.

### 1.5 Vehicle validation: what a stock joiner of a patched host meets

On the **host**, `0x446120` runs from 'SR' (`0x445b99`) and from the first 'ST' of an unknown car (`0x445e13`):

```c
if (!hacks /*0x526a68, -hacks*/) if (dpGetPlayerData(dp, id, 4, &claimed_crc, &4, 0)) return 0;
v = parse_vcf(bytes, size);                       // key 0: the joiner's .vcf
if (!hacks && v) { ok = ValidateVcf(file_of(v), budget, &crc);   // 0x4b7bf0, the host's OWN .vdf/.wdf/.gdf/.cdf
                   if (!ok || crc != claimed_crc) { send 'BO' reason 1; "*** %s has tried to join with a hacked vehicle!";
                                                    dpDestroyPlayer(); } }
```

On the **joiner**, the shell checks the host's version string ("6.04") and the mission file CRC. Nothing checks the
host's exe or proxy. So a stock player joins a patched host's stock session exactly when the host's **car files and
mission files are stock** - which they are: this design changes no file the stock list or the car check reads (our
extra missions live in their own folder, our AI is injected in memory).

### 1.6 How races / CTF pick their mode

Not from the extension in the exe. The shell's game-type selector `[0x10045860]` (1 combat, 2 race, 3..5 CTF 2..4 teams)
picks **which files** the arena list reads (`*.cbt`, `*.rac`, `*.cf2..4`, each also from `addon\`), and the host form
sets the session flags the exe reads: 0x10 combat, 0x20 race (`0x448810`), 0x40 CTF (`0x448800`), 0x2000 team play,
0x100 / 0x200 / 0x400 / 0x800 / 0x1000 limit kinds. Bits 0x4000 / 0x8000 are never set and never tested (byte search of
every reference to 0x53f228 and the bit tests of its whole-word getter's 23 callers). This closes the open item in
`i76-map\data\notes\nitro.md` ("which setup bit the exe reads ... not traced").

### 1.7 anet2.dll itself: a loader stub (not reached)

`anet2.dll`'s `.text` has 0xa00 file bytes for 0x15a00 in memory: an entry stub (`.dllent`) maps the real code from a
75 KB overlay. Ghidra sees the stub only. A 32-bit LoadLibrary-and-dump tool (`i76-map\nitro-net\tools\anetdump`) gets
error 1114 outside the game (n 3). ANet 2's internals (species filter on a game server, reliable send, its packet size
limit) are therefore **not read**; the design takes them from the exe / shell side and from Gold's measurements (2 'AT'
records = 208 B per packet arrive, 508 B did not). First item for the nitro-mp lane's first lab boot: dump the mapped
anet2 image from a running lab nitro.exe.

## 2. Nitro shell: the menu, the lists, where the entry goes

| piece | finding |
|---|---|
| screens | window messages (as Gold): 0xc00e main menu `0x10008690`, 0xc021 `0x1002a610` (single-player melee form, also `*.cbt`), 0xc024 single player (`addon\scenario.dat`), **0xc026 network entry form** `0x100318e0` |
| main menu | 19 buttons `Button_Init 0x1000e410(id, record, x, y, sprites, w, h, sprite, parent)` in `0x10009610`; sprites, no text strings. By layout and handlers [inferred, not seen on screen]: id 1 opens the melee group (ids 9 and 0xc at y 0x154), **id 9 = multiplayer melee** (shows HOST 10 / JOIN 11 at y 0x170), id 0xc = the single-player melee form (0xc021), ids 13..16 the providers at y 0x18b (each: provider := n, arena list, 0xc026), id 17 setup |
| click dispatch | `0x10008770`: `cmp esi, 0x12; ja 0x100092e6; jmp [0x1000933c + esi*4]` at `0x1000887b` |
| arena list | `0x10031320`, by game type; records title[32] + file[20] in a growable list; title = the WRLD title through exe callback +0x58 |
| what the entry passes to the exe | nothing has to cross: shell and exe are one process with one `Strlkup.dll`, so the proxy's own flag `g_nmp_mode` is read by both halves. (A setup-block bit would also be safe - 0x4000 is never tested - but is not needed.) |

**Insertion without moving stock buttons:**
1. A new widget record with **id 0x13** (proxy memory), built with `0x1000e410` in the melee group, in the free slot
   beside / under id 0xc (x 0x1d7, y 0x170 [inferred free]); shown and hidden with the group (`0x10009610` / the
   redraw `0x10009c10` get one extra call through a wrapper).
2. Click: only the `ja 0x100092e6` target at `0x1000887b` changes, to a stub: id 0x13 -> `g_nmp_mode = 1`, then the
   id-9 path (HOST / JOIN, providers, the 0xc026 form) runs unchanged; any other id -> the stock default.
3. While `g_nmp_mode = 1`: sessionType word `[0x10046cb0]` = ours, the 'JO' version = "6.04+", the arena list also reads
   our folder. Back to the main menu (0xc00e), session end or `dpClose` -> mode 0, all three restored.
4. Label: the shell has no text buttons; either draw the label with the shell's text call (as I76_ARENA_FIT draws titles
   on Gold) over an empty plate, or add one sprite to the shell's image set. The first needs no data file.

## 3. Design

### 3.1 What carries over, what needs ANet 2 work

| feature (Gold source) | netcode-independent? | Nitro work |
|---|---|---|
| injected AI pool records (`aim_odef`) | yes | site `0x4bd4bf` (ODEF handler `0x4bd4b0` -> `0x4b3630`, Gold 0x4b45bf); only combat `.cbt` arenas in our entry |
| parked / teleport pool (`mpfill.c`) | yes | **per-team spawn tables** in Nitro ("no spawn points for team %d"): trace their layout (Gold: one table 0x53fd88, count 0x540d98) |
| aimelee host tick, skill, cap (`aimelee.c` 1) | yes | `0x4079a2`; fsm_SetSkill / SetMaxAttackers / SetBehaviour matched "same" (`0x418400`, `0x418710`, `0x415490`) |
| teams | mostly | team = slot +0x48 and flags bits 16..18; team game from 0x53f228 & 0x2040 (not a bool) |
| difficulty skill (`difficulty.c`) | yes | re-address only |
| respawn (humans: `0x44caf0` = Gold 0x451570; AI: spawner `0x44c930` = Gold 0x4513c0) | yes | spawner "changed" (per-team spawn) |
| score rows (AI rows in the player table) | yes, but layout | **0x50 stride; fill +0x44 = 1.0f and +0x48 = team**; ids 0x7E00+n never reach ANet (rows are local, as on Gold) |
| 'AT' AI state sync, fire mask, damage block | needs the ANet 2 hook | packet unchanged (`net_PackVehicleState 0x463660` = Gold 0x4644d0 "same", 0x60-byte record) |
| 'AK' kill credit | ANet 2 hook | unchanged |
| 'AM' reload / next scene (co-op chain) | ANet 2 hook + WinMain sites | `0x433165`, `0x433717`; join CRC slot `0x52676c` |
| 'AC' / 'AO' (CB lines, objectives) | ANet 2 hook | CB voices: Nitro does not open I76.ZFS (NITRO-BASE): the original radio voices are missing until the nitro-base lane adds a voice path |
| slot settle (team read, 1.5 s / 3 s holds) | ANet 2 player data | same keys (1 = team pick) |
| host migration reconcile | ANet 2 | Nitro elects like Gold; add an **'AH' hello** from the new host so joiners confirm the pool / rows before the new host acts |

### 3.2 Packet design on ANet 2: piggyback, not a registered type

There is nothing to register: ANet 2 hands every app packet to the pump, the pump dispatches by its 2-letter tag and
drops the rest (section 1.2). So **keep the Gold scheme**: our tags 'AT' 'AK' 'AM' 'AC' 'AO' 'AV' plus one new 'AH'
(hello: protocol version, flags, pool CRC; sent by the host on each join and after a migration), read in the dpReceive
hook after the real call. Rules: sent **only while `g_nmp_mode = 1`** (and only to our species' sessions, which stock
games cannot join); payload <= 2 records (208 B) until the anet2 dump shows the real limit; 16 spare bytes after every
send buffer (ANet 1 wrote 4 past the payload; ANet 2 unchecked); 'AK' / 'AM' keep 3 copies + sequence numbers (ANet 2
probably has a reliable flag, unread). Even if one leaked, a stock Nitro pump drops it (decomp above) - but none may.

### 3.3 The non-destructive guarantee

A player who never opens our entry plays stock Nitro; a stock Nitro player can join a stock session hosted by a
patched game; a stock player never sees or joins one of ours. Concretely:

1. **Mode 0 at every boot**; mode 1 only from the button; back to 0 on the main menu, session end, `dpClose`.
2. **Forced off in mode 0** (whatever the environment says): `I76_COOP_AI`, `I76_COOP_CHAIN`, `I76_COOP_DAMAGE`,
   `I76_COOP_SCALE` (+ `_MAX`, `_TEST`), `I76_COOP_CB`, `I76_COOP_ADOPT`, `I76_COOP_HOSTMODEL`, `I76_AIMELEE` and every
   `I76_AIMELEE_*` (`_FILL`, `_FILL_TEAM`, `_RESPAWN`, `_RESPAWN_AI`, `_SCORE_ROWS`, `_TEAMS`, `_WAVE`, `_ARENAS`,
   `_BOX_LINES`, `_SKILL`, `_CAP`, all `_TEST*`), `I76_DIFFICULTY_AI` in network games, `I76_MPF_LOG` (harmless, but
   off). `I76_MP_MENU` / `I76_ARENA_FIT` are Gold-shell patches and never attach to nitshell. Lab-only `I76_LAB_*` never
   ship.
3. **Not touched in mode 0:** the dpReceive hook passes through (returns the real result, reads nothing), no extra
   sends, no AI injection, no score rows, sessionType 604, version "6.04", the stock arena list.
4. **Files:** nothing in `addon\` that the stock list reads (`addon\*.cbt|*.rac|*.cf2..4`) and no `.vdf/.wdf/.gdf/.cdf`
   override; our missions in `addon\nmp\` (a mission name "nmp\coop01.cbt" fits the 20-byte record; that the exe's VFS and
   the joiner's `addon\%s` CRC path accept a sub-folder is **to be checked**, fallback: the proxy maps the name).
5. **Local-only proxy features stay on** in stock sessions (far clip, terrain, music, cursor, telemetry): they change
   nothing another machine sees. **Own-car physics changes** (whole-sim tick) are the open question: they change only
   the patched player's car, but a community game should get the same car as everyone else; recommendation: in network
   games outside our entry, the tick runs at the setting measured equal to retail (gold-standard rule), never a
   handling change.
6. **Gate (before anything ships):** two lab copies, IPX: (a) patched host, stock Nitro joiner, every game type
   (combat, race, CTF 2) - join, play, leave, migrate; (b) stock host, patched joiner; (c) our entry hosting while a
   stock copy lists: not listed; (d) the same over the bz911 lobby with our species (risk R3); n 3 per cell.

### 3.4 List entries under the new entry

| group | count | source | how |
|---|---|---|---|
| Nitro combat arenas with AI fill | every `*.cbt` the stock list shows (data track: 24 `.cbt` in the corpus, incl. N51-N65) | stock files | memory injection of 7 parked AI at load (Gold's AI-MELEE-RESPAWN phase 2), fill = NO. DRIVERS - humans |
| the 15 original arenas | 15 | **already in Nitro as N51-N65** (same terrain) | as above; nothing to add. (The owner's `nitro-plus-original` copy also has M01-M15 as `.CBT`: in our entry they would duplicate N51-N65; leave them out) |
| co-op scenes 1-17 | 17 | Gold T01-T17 (`coop-install.py` output, owner's Gold install) | `addon\nmp\coopNN.cbt`, combat type, title "Co-op Scene N"; voices missing until a voice path exists |
| scenarios S01-S07 | 7 | Gold S01-S07 (`autoNN`) | `addon\nmp\autoNN.cbt` |
| races / CTF with AI | - | - | out of scope (AI would need race / flag logic) |

The brief's "Nitro's 36 arenas" did not match a count here (the corpus has 24 `.cbt`, 17 `.cf2-4`, 13 `.rac`); the rule
"every combat arena of the stock list" covers whatever the install holds.

## 4. Names for the entry (owner picks)

Each name with the one-line description the shell would show beside it (on the button's hover / the form title).

| # | name | description line |
|---|---|---|
| 1 | **AI DROP-IN** | Melee with computer drivers in every empty seat; friends drop in or out any time. |
| 2 | **CO-OP / AI MELEE** | Team up against computer cars: every arena, the '76 scenes and scenarios. |
| 3 | **ARENA+** | Every arena plus the original '76 missions, with AI filling the open slots. |
| 4 | **CONVOY** | Roll out together: co-op scenes and AI-filled arenas, join whenever you like. |
| 5 | **NET AUTO MELEE** | Auto Melee over the network: AI drivers fight beside and against your friends. |

Width: the plate beside "auto melee" holds about 106 px (the id 0xc button); every name fits in the shell's 12-px hand
font (CO-OP / AI MELEE is the longest, about 100 px [estimated from Gold's font measurement in mpmenu.c]).

## 5. Estimate and order (lane-days, one lane)

| # | piece | days | risk | why |
|---|---|---|---|---|
| 0 | prerequisite: the nitro-port lane's foundations (exe detection, site table, logging, cursor / shell map) | - | - | not counted here |
| 1 | anet2 dump from a lab boot + read species filtering, reliable flag, size limit | 0.5 | low | one boot, one dump, one export |
| 2 | shell entry: button id 0x13, click stub, text label, mode flag, species / version / list swaps, reset paths | 2.5 | **medium** | widget internals (show / hide with the group) only read statically |
| 3 | ANet 2 layer: dpReceive hook, sends, role / host / group, 'AT' sync + fire + damage block + score skip, re-addressed globals (0x50 rows, +0x484 / +0x458) | 2 | low-medium | same pump shape, packets unchanged |
| 4 | AI melee on Nitro: host tick, kill credit, skill, respawn, score rows (0x50 layout), pool injection at 0x4bd4bf, per-team spawn tables, teams on the flags word | 4 | **medium** | per-team spawns and the new row fields are new ground |
| 5 | co-op scenes + scenarios: chain sites, 'AM' / 'AC' / 'AO', `addon\nmp\` list + VFS sub-folder check, files from Gold | 3 | **high** | Gold missions on Nitro measured for P01 only in our exe, never in nitro.exe; radio voices missing |
| 6 | host migration: 'AH' hello, reconcile pool / rows on the new host, co-op restart | 1 | medium | as on Gold, but new packet |
| 7 | non-destructive gate (3.3 item 6), incl. the lobby with our species | 1.5 | medium (R3) | needs two lab copies and the lobby |
| 8 | cross-machine pass (PC + a Mac) and pack | 1 | medium | Wine + Nitro never run here |
| | **total** | **15.5** | | |

Order: 1 -> 2 -> 3 -> 7(a-c) early (prove the entry is invisible to stock before any AI work) -> 4 -> 6 -> 5 -> 7(d) -> 8.

**Risks.** R1 anet2 internals unread (piece 1 retires it). R2 the shell's button / group code is read, not run. R3 a
lobby server may refuse or hide an unknown species: our entry would then be IPX / LAN only until a species the lobby
lists is agreed with the community (the bz911 operators); stock play is unaffected either way. R4 Gold co-op missions in
nitro.exe (scripts, FMV hooks, missing voices) - the nitro-base lane's owner check answers part of it. R5 the port lane's
two mapping slips in section 1.3 must be fixed before any team / scoreboard code runs on Nitro.

## 6. What was not done

- No game was started (no stock Nitro menu or IPX session observed): the button meanings in section 2 are inferred from
  the layout and the handlers. First lab boot should confirm them (screenshot of the main menu with the melee group open).
- anet2.dll internals (section 1.7).
- Nitro's per-team spawn table layout, the VFS sub-folder question (3.3 item 4).
