# Multiplayer: home LAN and online

*2026-10-05. Status line, measured / not measured, is in section 0. Lab records behind every claim:
`../i76-uncap-lab/docs/MULTIPLAYER-LOCAL-TEST.md` (transport, sections 8 and 9) and
`../i76-uncap-lab/docs/MULTIPLAYER-CAR-CHECK.md` (the anti-cheat car check).*

## How the community plays today, and the order to try things (research 2026-10-06)

Checked against primary sources (Peelar's netcode page, UCyborg and Lightfoot on interstate76.com via Wayback, the GOG
forum threads, Local Ditch's FAQ dated 9/28/26, Kegel's ANet master list, IPXWrapper's compatibility list):

- **The live scene plays Nitro Pack (`nitro.exe`, ANet2), not base I'76**, through community-hosted ANet lobby
  servers (`911.alink.bz911.net` resolves and answers in October 2026), with UPnP on the router (Peelar's
  `WINETS2.DLL` + `miniupnpc`), and arranges games on the UltraFunk Discord (https://discord.gg/dyJnDmSJBB, 234
  members, 40 online when checked). Direct-IP joins do not work in Nitro. Nobody uses IPX any more.
- **Base I'76 has a direct-IP route with no extra software.** GOG's `WINET.DLL` carries Peelar's NAT fix (ANet over
  UDP **21157**). Community instructions: the host adds a server entry with **its own IP** and hosts INTERNET; joiners
  add the **host's IP**. UCyborg (2019): "Direct IP connections work as far as I can tell". **Not yet tested here.** The
  lab's "a peer cannot stand in for the server" (section 1) was measured with `127.0.0.1` on one PC, which is not this
  setup, so it does not rule it out.
- **IPX through IPXWrapper** is on IPXWrapper's list as working with I'76 (0.7.2) and works here between two copies on
  one PC. It needs three DLLs per install and, on the Mac, Wine DLL overrides.

**Measured 2026-10-06, Windows 11 PC + Mac (Wine) on one home network, lab/test copies, n = 1:**

| route | result |
|---|---|
| **IPX through IPXWrapper 0.7.2, PC hosts, Mac joins** | **works.** The Mac's JOIN > IPX list showed "THE CRATER (1/4)", JOIN GAME put it in the PC's arena, and the PC's position table held both cars: the Mac's car moved ~220 m in the PC's memory while the Mac held W for 6 s |
| INTERNET, host lists its own LAN address as the server | **fails**: "Game Server Not Responding" on the host after DONE |
| INTERNET, joiner lists the host's address | **fails**: "No games found", then "Game Server Not Responding" |
| INTERNET, both through the `911.alink.bz911.net` lobby | host started (the lobby answered, BROADCAST GAME went into the arena) but the joiner's list stayed "No games found" |

Peelar's own page explains the direct-IP failure: the base-game patch was tested only below version 1.083 (GOG is
1.083) and says "make sure there are no clients on the host's own network". **So at home: IPX through IPXWrapper**
(sections 2-6). Direct IP is an internet-only route, and unverified here.

Over the internet with friends: the host forwards UDP 21157 (or uses UPnP) and friends type the host's public
address; or a virtual LAN that carries broadcast (ZeroTier, Radmin VPN) for IPX. **Tailscale is layer 3 and does not
carry broadcast**, so IPX discovery over it will not work; direct IP over 100.x addresses might (untested). To play
with the existing community, use Nitro Pack with the bz911 lobby and the Discord.

## 0. Status

| claim | state |
|---|---|
| IPX between two game copies on one PC, IPXWrapper 0.7.2 | **works** (2026-10-05, n = 1): host BROADCAST GAME went into The Crater, the joiner listed "THE CRATER (1/4)", JOIN GAME, and each copy then held both cars at the same coordinates (within 0.1 m). Stock car data (Jade's Car `valepre4.vcf` de680a86) |
| IPX between two machines on 192.168.1.0/24 | **works** (2026-10-06, n = 1): Windows 11 PC host, Mac (Wine) joiner |
| The daily driver's cars pass the anti-cheat check | its `valepre4.vcf` is byte-identical to the file that passed the host and joiner checks live in row 1; the other 67 variants: static read (MULTIPLAYER-CAR-CHECK.md section 0) |
| LAN pack (2026-10-17), measured 2026-10-18 | PC host + Andrew's Mac join **works** (n 2); Andrew host + PC join (n 1, plus n 2 earlier that night); Andrew host + Deck join (n 1); PC host + Deck join (n 1); **3 players** PC + Deck + Andrew (n 1). Deck host in The Crater failed (mission files differed; since COOP-LIST-ENTRIES-2026-10-18 the co-op missions are their own arenas and The Crater is stock again). Michael's firewall box answered (09:25), his cells and the laptop's still unrun (both screens locked during the tests); 5 players not run. [records/LAN-MATRIX-2026-10-18.md](records/LAN-MATRIX-2026-10-18.md) |
| Join / leave anytime, host leaving, AI fill, co-op scaling (2026-10-20) | **works on one PC** (3 lab copies headless, n 2-3 per cell, soak in the record); not yet between machines. [records/MP-OVERNIGHT-2026-10-20.md](records/MP-OVERNIGHT-2026-10-20.md) |
| The same between machines (2026-10-20 morning) | **works** (PC host + Andrew's, Michael's Mac and the laptop): join / hard exit / re-join in Suburbia, Hope Springs (4 AI), Pretty Bus, Scene 5 (n 2 per machine per arena), AI fill counts right on the host and the parked cars where they belong on every joiner, co-op copies 1-2-3 with the joiners, 4 players, the host quitting in melee / AI arena / co-op (a Mac takes over, AI pool and scaling move with it, n 1 each), a Mac hosting with the PC joining and leaving by the Esc menu (n 2); 0 crashes. Not measured: a joiner's kill credit, the Deck (asleep). Polish (section 7, proxy cf4f81da on every reachable machine): HOST / JOIN go straight to IPX on the Macs too (n 4 launches on Andrew's Mac + smoke), and a new host after a migration leaves no stray co-op copy and counts the parked AI right (lab n 3 + 1, smoke n 1); new: the new co-op host restarts the scene. [records/LAN-MATRIX-2026-10-20.md](records/LAN-MATRIX-2026-10-20.md) |
| IPXWrapper DOSBox-server mode (internet without a VPN) | **fails** (2026-10-20, n 2): WIPX's start-up broadcast never comes back from a DOSBox server |
| Mac (Wine) running IPXWrapper | **works** (2026-10-06, n = 1): the Mac joined a Windows-hosted IPX game, see the top of this page and section 6 |

## 1. Why IPX, and what the other buttons do

The game's multiplayer menu offers MODEM, IPX, INTERNET, NULLMODEM. Only **IPX** works today:

- **INTERNET** looks for a game server from `internet.lst` (Activision's are gone). Hosting against `127.0.0.1` on one
  PC stopped at "Game Server Not Responding" (lab doc 8.2-8.3), but the community's direct-IP route (the host lists
  its own real address) was not tried; see the section above.
- **MODEM / NULLMODEM** need serial ports.
- **IPX** finds sessions by broadcast on the local network; no server. Windows 10/11 no longer ships an IPX protocol,
  so each PC gets **IPXWrapper**, which carries IPX inside UDP (port **54792**) on the ordinary LAN.

## 2. On each Windows PC

1. Download IPXWrapper 0.7.2 from its author (solemnwarning.net/ipxwrapper, GPL-2.0). We do not redistribute it.
2. Copy `ipxwrapper.dll`, `wsock32.dll`, `mswsock.dll` (the 4th file, `dpwsockx.dll`, is for DirectPlay games; I'76
   does not use DirectPlay, so it is optional) into the folder that holds `i76.exe`.
   - Do it on a **copy** of the game folder first if you want to keep the daily driver untouched: copy the whole
     `Interstate 76` folder (leave Lossless Scaling and other licensed tools out) and play LAN from the copy.
   - To undo: delete the three DLLs. Nothing else changes; IPXWrapper keeps its node number in
     `HKCU\Software\IPXWrapper` (harmless; `Remove-Item HKCU:\Software\IPXWrapper -Recurse` deletes it).
3. Network profile: the home network should be **Private** (Settings > Network > properties).
4. More than one network adapter (WSL / Hyper-V / VPN / Tailscale)? IPXWrapper uses all of them by default; on this PC
   it broadcast on 192.168.1.255, 172.30.175.255 (WSL) and 100.113.196.47 (Tailscale). That worked. If sessions do not
   show up, run `ipxconfig.exe` (in the IPXWrapper zip) and set **Primary interface** to the 192.168.1.x adapter.
5. Debug log when something fails: put an `ipxwrapper.ini` beside `i76.exe` with the line `logging = debug`; the log is
   `ipxwrapper.log` in the same folder.

## 3. Firewall (the owner clicks this, once per game folder)

The first time a game copy opens its network socket, Windows shows **"Windows Security Alert - Windows Defender
Firewall has blocked some features of this app"** for that `i76.exe`. Tick **Private networks** and click **Allow
access**. One rule per `i76.exe` path, so a new copy of the folder asks again.

- On one PC (two copies talking over loopback) the rule is not needed; between PCs it is.
- The alert opens **behind** the full-screen game and covers the game's own OK buttons. If the game seems frozen in a
  box right after HOST or JOIN, Alt-Tab and look for the alert.
- Checking the rule exists: `Get-NetFirewallApplicationFilter | ? Program -like '*i76.exe'`.

## 4. The car rule (anti-cheat): use stock car data on every PC

Before hosting or joining, the game runs `ValidateVcf` on your car (exe 0x4b35a0):

- **Budget rule**: armour + chassis + spare points must equal 1600 x the car size, each facet at least 50 x size. A
  car that breaks it shows a **"vehicle rejected"** box and the host never opens the session. Armour mods break it
  (the lab's modded `ADDON\valepre4.vcf` adds up to 6156 of 3200).
- **Same data**: a CRC over the car's `.vdf`, its `.wdf` wheels, every weapon `.gdf` and `compnent.cdf` is sent with
  the player. The host recomputes it from **its own** files; a mismatch prints `*** <name> has tried to join with a
  hacked vehicle!` and drops the player.

So: every PC needs the **stock GOG `I76.ZFS`** (md5 6dd57b16) and **no `.vdf/.wdf/.gdf/.cdf` files in `ADDON`**. The
daily driver qualifies as it is: its `ADDON\valepre4.vcf` ("Jade's Car") is the stock file (md5 de680a86) and all 68
multiplayer car variants pass. A copy of the daily driver's folder qualifies too. The `.vcf` itself need not match
across PCs (each car is sent over the wire). Leave the host's weapon restrictions at default.

Single-player armour mods (the x2 ADDON set) and multiplayer do not mix: put the stock `.vcf` back for LAN nights, or
play LAN from a stock copy.

## 5. Starting a game

Host (one PC): **MELEE > MULTI MELEE > HOST > IPX**. The host form opens directly (no server box). Pick a car and an
area, then **BROADCAST GAME**. The host goes straight into the arena; there is no lobby.

Everyone else: **MELEE > MULTI MELEE > JOIN > IPX**. The GAME NAME list shows the host's game (default name "THE
CRATER"). Select it, **JOIN GAME**.

If the list says "No games found": the host is not in its arena yet, the firewall alert is still up on one of the PCs,
or the PCs broadcast on different adapters (section 2 step 4).

No proxy switch is needed for PCs on a LAN. (`I76_MULTI_INSTANCE=1` is only for two copies on one PC.)

## 6. The Mac (Wine)

**Works (2026-10-06, n = 1)**: the Mac test copy (`I76 IPX TEST.app`, DxWnd + OpenGLide, Wine 10) joined an IPX game
hosted by the Windows PC, with steps 1, 2 and 5 below and nothing else: step 3 was not needed (two interfaces on the
subnet did no harm), and step 4 did not come up (the macOS application firewall is off on this Mac). All three open
questions at the end of this section came out fine: WIPX init succeeded under Wine, DxWnd did not get in the way,
Tailscale did not matter. Stock car on the Mac for the run (de680a86), put back afterwards. The Mac copy was started
with `tools/mac-test-clone.sh run` (no microphone prompt).

What the survey found:
- Wine 10 (Sikarugir), wow64 x86_64 under Rosetta. The game starts through **DxWnd** (`dxwnd.exe /R:1`), which hooks
  imports and may touch winsock.
- No IPXWrapper, no DLL overrides. `I76.ZFS` is stock (6dd57b16); ADDON has no `.vdf/.wdf/.gdf/.cdf`.
- **ADDON `valepre4.vcf` is 4ed297ca, not the stock de680a86**: Jade's Car would be rejected on the Mac. Pick another
  car on the Mac, or put the stock `valepre4.vcf` (de680a86) in place for LAN play (section 4).
- Two interfaces on 192.168.1.0/24: wired en7 192.168.1.241 (default route) and Wi-Fi en0 192.168.1.115. Tailscale
  connected; NordVPN and FortiClient installed but off.

Steps, on the test clone:
1. Copy `ipxwrapper.dll`, `wsock32.dll`, `mswsock.dll` beside `i76.exe` inside the prefix.
2. Make Wine load them for the game only. Prefer the per-app registry key over `WINEDLLOVERRIDES` (DxWnd starts the
   game, so an environment variable may not reach it): in `HKCU\Software\Wine\AppDefaults\i76.exe\DllOverrides` set
   `wsock32` = `native,builtin` and `mswsock` = `native,builtin`.
3. Two interfaces on one subnet: set IPXWrapper's primary interface to the wired one (`ipxconfig.exe` in the prefix,
   or turn Wi-Fi off for the session), so each broadcast goes out once.
4. macOS asks once whether the Wine process may accept incoming connections: allow.
5. Debug log as on Windows (`ipxwrapper.ini` with `logging = debug`).

Open questions before the run (all fine, see the top of this section): whether Wine's `ws2_32` loopback-delivers the subnet broadcast that WIPX must hear back within 5 s
(otherwise IPX init fails, error 0x84), whether DxWnd's winsock hooks get in IPXWrapper's way, and whether Tailscale
changes which interface the broadcast leaves on.

## 7. Two players on ONE PC

See `../i76-uncap-lab/nucleus-coop/README.md` (Nucleus Co-op handler) and the lab doc section 9. That route needs two
game copies, a patched second `ipxwrapper.dll` (its own mutex and registry key), `I76_MULTI_INSTANCE=1`, and for pads,
the proxy's `I76_JOY_MAP` (each copy binds `joystick1`; the switch routes it to that copy's pad).

Joystick slots, measured 2026-10-05 with a synthetic pad (lab doc section 9): the engine opens `joystick1` and
`joystick2` normally, but opens every higher slot with winmm id 1's caps and first poll, so `joystick3`+ work only
while a device sits at winmm id 1. `I76_JOY_MAP=0=<id>` with `joystick1` in input.map avoids that for any pad id.

## 8. Family game night (stable setup, 2026-10-18)

Measured results behind this section: [records/LAN-MATRIX-2026-10-18.md](records/LAN-MATRIX-2026-10-18.md). One-page
sheet for the players: [GAME-NIGHT.md](GAME-NIGHT.md). Re-run the matrix from the PC: `tools/lan-test/README.md`.

### Which app on which machine (never a new copy)

| machine | open this | game folder (updated in place) |
|---|---|---|
| Michael's Mac | Desktop: **Interstate 76 LAN** (a link to `~/Games/Interstate76-MP/Interstate 76.app`) | inside that app |
| Andrew's Mac | Desktop: **Interstate 76 LAN** (same layout) | inside that app |
| James's laptop | `~/Applications/Sikarugir/Interstate 76.app` (his own app; the pack swapped in 2026-10-20 evening, [records/MAC-CONVERGE-2026-10-20.md](records/MAC-CONVERGE-2026-10-20.md); `I76 MP GATE.app` and the test apps are gone) | inside that app |
| Steam Deck | Steam (Game Mode) > **Interstate 76** (non-Steam shortcut). **For LAN games since 2026-10-20** its launch options must name the new LAN launcher: `"/home/deck/Games/Interstate76/i76-deck-launch-mp.sh" %command% -glide` (proxy cf4f81da as on every machine + `I76_COOP_AI` / `I76_COOP_CHAIN` / `I76_MP_MENU` on top of the Deck's own `i76-env.sh`; the old `i76-deck-launch.sh` still works but has no LAN switches). Jade's Car is refused (the Deck's own `valepre4.vcf`): pick another car. Installed and booted (n 1), a cross-machine join on the new pack not yet measured: [records/LAN-MATRIX-2026-10-20.md](records/LAN-MATRIX-2026-10-20.md) section 8 | `~/Games/Interstate76/game` |
| Windows PC | `C:\Users\james\Games\Interstate76-LAN-2026-10-17\Interstate 76\PLAY-LAN.bat` (not the daily driver) | that folder |

Keep **one app bundle per Mac** and update only its game folder (`tools/mp-mac-install.sh update` touches
`drive_c/GOG Games/Interstate 76` and `user.reg`, never `Contents/SharedSupport/wine`). macOS ties the firewall and
microphone answers to the app's `wine` binary (ad-hoc signed, `org.winehq.wine`); a new copy or a rebuilt wine asks
again, the same bundle never does.

### One-time approvals (a person at each machine, once)

1. **Michael's Mac (firewall on):** the first time the game opens its network socket (HOST > IPX or JOIN > IPX),
   macOS asks *Do you want the application "wineserver" to accept incoming network connections?* (the record of
   2026-10-18: the allowed entry is `.../Interstate 76.app/Contents/SharedSupport/wine/bin/wineserver`). Click **Allow**. Checked
   2026-10-18: `socketfilterfw --listapps` has no wine entry yet, so this box is still to come. It cannot be clicked
   remotely (no sudo, no Accessibility), so Michael (or James) clicks it on game night, before the first join.
   Andrew's Mac and James's laptop have the firewall off: no box.
   **Michael's Mac: answered 2026-10-18 (wineserver: Allow, seen 09:25).** Before that his IPX start failed with an
   "Error" box.
2. **Microphone (each Mac, first real-audio launch):** *"wine" would like to access the microphone*. Either answer
   is fine; answer it, because the game waits behind it. Andrew's Mac reached the main menu in all 4 launches on
   2026-10-18 (no box in the way); Michael's has not been launched with the screen unlocked yet.
3. **Windows PC:** the Windows Defender Firewall box for the LAN copy's `i76.exe` is already answered (inbound Allow
   rules exist, Private profile).
4. **Deck:** nothing (Linux, no firewall prompt).

### Order on the night

1. Everyone on the home Wi-Fi / wired network (not guest, no VPN). Macs **unlocked and awake**: plug them in.
2. One host (any machine; a Mac host and a PC host are both measured): MELEE > MULTI MELEE > HOST (with the pack of
   2026-10-19 HOST goes straight to the IPX host form; on an older pack or the Deck click IPX after HOST), pick an
   arena, RENAME the game to something recognisable, **BROADCAST GAME**. The host drives straight into the arena.
   The list (pack of 2026-10-19; records/COOP-LIST-ENTRIES-2026-10-18.md sections 7-8):
   - the 15 stock arenas (The Crater .. A Lot of Asphalt): normal melee;
   - **Hope Springs (2 AI), Hope Springs (4 AI), Hope Springs (6 AI)**: melee against 2 / 4 / 6 computer cars that the
     host runs and that attack the nearest human; a human who kills one scores for it on every screen ("Torque Daisy
     was destroyed by ..."); everybody respawns by himself; when every computer car is dead the arena reloads with
     them back and the scores kept (records/AI-MELEE-M1-2026-10-19.md);
   - **Oil Well Well, Mondo Burger, Seminole, Pretty Bus, Race No Shoot, Trailer Pk. Madness, Milk Toast (Scenario)**:
     the single-player auto-melee scenarios with their computer cars, humans together against them; a joiner who dies
     comes back by itself, the host's death (or the scenario's own loss) restarts the scenario for everybody, a win
     ends the game; the list is drawn in a smaller handwriting so the names fit (only "Trailer Pk. Madn. (Scenario)"
     is shortened);
   - **Scene 1 .. Scene 17 (Co-op)**: the co-op campaign (was "Co-op Scene N").
3. The others: MELEE > MULTI MELEE > JOIN (straight to the game list with the 2026-10-19 pack; otherwise JOIN > IPX), click the game's row, **JOIN GAME**. Joining while the host drives
   is fine.
4. How to tell it worked: each screen shows the other cars (radar / view); a joiner that stays on the ENTRY ROSTER
   after JOIN GAME did not join.

### Known failures and their fix

| symptom | cause | fix |
|---|---|---|
| list says "No games found" | host not in the arena yet / firewall box waiting / different network | host first; answer the box; same network |
| the host quits and the game carries on | ANet hands the session to another player (seen 2026-10-18: Andrew left, the Deck became host 6) | normal; the new host keeps it alive |
| a Mac joiner sits on ENTRY ROSTER after JOIN GAME | seen only with remote automation (2026-10-17/18): the forms act where the **real** pointer is, and the SSH probe moved only Wine's. With the pointer on the button the Mac joined (PC host, n 1). A player clicking with the mouse is not affected | click JOIN GAME again with the mouse |
| Deck drops out mid-game | Game Mode suspends after ~10 min without touching the Deck | touch it now and then, or plug it in and raise the suspend timeout in Steam settings |
| Deck hosts The Crater: the joiner's car never appears (2026-10-18, before the fix) | the pack's m01 was the co-op T01, the Deck's the stock one | fixed in the tools (not yet on the machines): rebuild the pack, the co-op missions are then `ADDON\coop01..17.lvl` ("Co-op Scene N"), The Crater is stock everywhere |
| "You don't have mission coop01.lvl!" when joining | that machine lacks the pack's co-op files (or has them upper-cased) | update it from the pack; the game's own check, by name and CRC-32 |
| a co-op host's game closes when the mission is lost or won | the proxy's chain packet overflow (ANet writes 4 bytes past it), in the pack's proxy 33211f11 | fixed in the proxy source (COOP-LIST-ENTRIES-2026-10-18 section 3.3); until the pack carries a rebuilt proxy, a lost or won co-op mission ends the host's game |
| clicks do nothing on a Mac while another app is in front (laptop, 2026-10-18) | the game reads the pointer only while its window is frontmost | click once into the game window |
| "vehicle rejected" | that machine's car file is not stock (the Deck's own `ADDON\valepre4.vcf` is 4ed297ca, not de680a86) | pick another car, or use the LAN pack's stock files |

### Pack status (2026-10-18 11:00)

The co-op pack of 2026-10-18 (co-op missions as arenas "Co-op Scene 1..17" = `ADDON/coop01..17.lvl`, lower case; stock
The Crater back; proxy ba2b45c1 with the co-op reload crash fixed) is on the PC LAN copy, Michael's Mac and the laptop
gate clone (in place, verified). **Andrew's Mac and the Deck still carry the old pack** (unreachable / asleep during the
update): bring them up and run `tools/lan-test/apply-pack-delta.sh` (Macs) or copy the 34 `ADDON/coop*` files (Deck)
before a co-op night. No co-op cell has been run across machines yet (records/LAN-MATRIX-2026-10-18.md section 7).

### Update 2026-10-18 14:10

- Mac to Mac works both ways (Michael <-> laptop, melee and Co-op Scene 1, n 1 each); a co-op loss reloads on both
  without a crash (n 2); a machine without `coop01.lvl` gets "You don't have mission coop01.lvl!" (n 1). Not yet: a
  co-op win / late join, the PC-hosted cells of the new pack, 5 players.
- **After a death in melee the host stays in the death view, joiners respawn by themselves** (our co-op switch
  `I76_COOP_CHAIN` gives only joiners an automatic respawn). The host respawns from the replay. Fix pending.
- **Menu pointer off on Andrew's Mac** (~14 px left): his window is narrower than the screen (DxWnd size made on a
  1728x1117 laptop). Fix staged: DxWnd size and OGL_VIEWPORT = his screen, 1440x900.

### Update 2026-10-18 14:50

- **4 players measured** (laptop host + Michael + Deck + Andrew, n 1). The host form's **NO. DRIVERS defaults to 4**: a
  5th player gets "Game full!". For 5, the host raises NO. DRIVERS (the + beside it) before BROADCAST GAME.
- With several games on the network, pick the row by its name (the first row is not always yours).
- Proxy **ac44e2c2** (melee respawn stock for host and joiner; automatic respawn only in Co-op Scenes) on the PC LAN copy,
  the laptop copy, Michael's and Andrew's Macs. The Deck keeps its own pack (+ the co-op files, no co-op switches).
- Andrew's pointer fixed (window = his 1440x900 screen).
- Daylight arenas with hills and roads: Hope Springs, Vigilantes' Paradise, Tombstone (records/LAN-MATRIX section 9).

### Update 2026-10-19 (built, not deployed)

- **The menu:** MULTI MELEE > HOST and > JOIN go straight to the IPX screens (proxy `I76_MP_MENU=1`, default; `=2` shows
  only the IPX button, `=0` the stock MODEM / IPX / INTERNET / NULLMODEM row). PC, two lab copies: HOST n 9, JOIN n 4,
  host and join both ways (n 3 and n 1).
- **The list** now reads: 15 stock arenas, the 7 scenarios "<name> (Scenario)" (`ADDON\auto01..07.lvl`), then
  "Scene 1 .. 17 (Co-op)" (`coop01..17.lvl`, file names unchanged, titles changed). All 7 scenarios load for a host
  with their computer cars (n 1 each); Oil Well Well and Pretty Bus with a joiner, computer cars on both (n 1 each);
  Scene 1 (Co-op) unchanged (n 1). Records: COOP-LIST-ENTRIES-2026-10-18.md sections 7-8.
- **Every machine needs the new ADDON files at once:** the co-op files' CRCs changed with their titles, so an old and a new
  machine refuse each other's co-op games ("does not match the host's").
- Pack: `i76-uncap-lab\builds\mp-pack-20261019\` (proxy 3125197a). Not yet on any machine. Host melee respawn in scenarios
  is an owner option, not built (records/COOP-LIST-ENTRIES-2026-10-18.md 8.3).

### Update 2026-10-19: AI melee arenas (built, not deployed)

- **New list entries** after A Lot of Asphalt: "Hope Springs (2 AI)", "(4 AI)", "(6 AI)" = `ADDON\ai_hs2/4/6.lvl`
  (`tools/aimelee-mission.py`, installed by `coop-install.py` and so by `mp-pack.py`). Proxy `I76_AIMELEE` (on with
  `I76_COOP_AI`, PLAY-LAN.bat sets it): the host sends every computer car after the nearest human, credits a human's kill
  of one to that human on every machine, reloads the arena with the cars back when all are dead (scores kept), and dead
  humans respawn by themselves.
- **Measured on the PC, two lab copies** (records/AI-MELEE-M1-2026-10-19.md): 4 AI present and moving for the host (n 3),
  the joiner sees them at the same places (median 0.2-0.4 m, n 5), the AI hit and kill both humans, the host's kills
  score on both screens (7 kills, n 2), two wave reloads with both players through and scores kept (n 2), the host's
  death does not end the game (n 5). **Not measured:** a joiner's kill of an AI (the scripted joiner never finished one),
  any run between two machines. The 15 stock arenas and Scene 1 (Co-op) load as before (n 1 each).
- Every machine needs the three `ai_hs*.lvl` files (the joiner's shell checks name and CRC). Pack:
  `i76-uncap-lab\builds\mp-pack-aimelee-20261019\` (proxy 8e262bcf = main e9d3e0b). Not on any machine.

### Update 2026-10-19 (afternoon): the lab tick copy plays LAN (lan-merge lane)

Owner: *"would like to see network funcitonalities merged into the lab version"*. The owner's tick play copy
`i76-uncap-lab\game-tick` (PLAY-TICK.bat / PLAY-TICK-66.bat, proxy tick19e a08577c4, which already holds every co-op, AI-melee
and menu commit) now hosts and joins family games from those two launchers, no PLAY-LAN.bat needed:

- **Keys** (in `presets\tick19-33.psd1` / `tick19-66.psd1`, generated by lab `tools\tick-finish\make-presets.ps1 -OwnerBest`):
  `I76_COOP_AI=1`, `I76_COOP_CHAIN=1`, `I76_MP_MENU=1`, the three PLAY-LAN.bat sets. They act only in network games.
- **Files** added to `game-tick\Interstate 76`, the same as the LAN pack adds to a plain install (checked against the PC LAN copy by
  md5): `ipxwrapper.dll` 06a01d0f, `wsock32.dll` 70e4a652, `mswsock.dll` c18759b2 (IPXWrapper 0.7.2, byte-identical to the LAN
  copy's; no `ipxwrapper.ini`, which is only the debug-log switch) and the 27 arenas of `tools/coop-install.py` at a05a6e4:
  `ADDON\ai_hs2/4/6.lvl`, `auto01..07.lvl`, `coop01..17.lvl` plus their `.aimelee` / `.coop` markers. Everything else the PC LAN
  copy has over the driver is game-written (NVCL, user.mel, nscr.dat, ipxwrapper.log) or not network (`_ahk\i76-remap.ahk`).
- **Tested on the PC** (game-tick through PLAY-TICK.bat + lab copy `game-lanmerge-b`, ADDON byte-identical; IPX on loopback with
  I76_MULTI_INSTANCE / I76_NO_MINIMIZE for two copies on one PC): game-tick hosts Hope Springs (2 AI), the other copy joins, both
  hold the same 4 cars and the 2 AI cars move the same on both (n 2); the reverse, game-tick joining (n 1); game-tick hosts
  Scene 1 (Co-op), joined, 7 cars at the same places on both (n 1). Single player unchanged: gate rows 2-3 through PLAY-TICK 6 PASS
  0 FAIL. Record: records/TICK-FINISH-2026-10-18.md section 15.
- **With the family machines today:** they run the 2026-10-18 pack (older `coop*.lvl`, no `auto*` / `ai_*`), so game-tick plays
  the 15 stock arenas with them but its co-op, scenario and AI arenas are refused ("does not match the host's"; from the CRC rule of COOP-LIST-ENTRIES 8.5, not tested here) until they get the
  next pack from `tools/mp-pack.py` on main HEAD (same coop-install.py, same files).
- The promotion-19 candidate (`i76-uncap-lab\builds\tick-finish-20261018\promotion-19-candidate`) carries the same presets and files.

### Update 2026-10-20 (overnight lane): join / leave anytime, AI fill, more co-op enemies per joiner

Record: [records/MP-OVERNIGHT-2026-10-20.md](records/MP-OVERNIGHT-2026-10-20.md) (all measured on the PC with 3 lab copies,
headless; nothing between machines yet). Pack `i76-uncap-lab\builds\mp-pack-20261020-overnight\` (proxy 533ab67c = e3934e3);
which machines run it: the record's section 8.

- **Join and leave anytime** (stock; nothing needed fixing): a late join into a running melee or co-op scene, a joiner leaving,
  the same player re-joining, a joiner's game dying (his slot goes after ~47 s), re-joining after that: all pass (n 2-3 each).
  **When the host leaves, the game goes on**: ANet makes a joiner the host at once (n 2).
- **Open slots filled by AI** (`I76_AIMELEE_FILL`, default on, AI arenas only): "Hope Springs (4 AI)" keeps 5 combatants:
  alone 4 AI, 2 humans 3, 3 humans 2, ...; a joiner retires one AI (parked far away, no score), a leaver brings one back
  (n 3 per step).
- **Co-op scenes get more enemies per joiner** (`I76_COOP_SCALE`, default on): every enemy car of a scene has 3 parked copies
  in the file; when it attacks, one copy per joiner (up to 3) comes in beside it and fights. Alone you play the stock scene
  (n 3). The co-op scenes also get a 3rd joiner start point (4 humans).
- **Internet without Tailscale through IPXWrapper's DOSBox-server mode: does not work** (the game's IPX start-up check never
  hears its own broadcast back from a DOSBox server, n 2). Direct IP (UDP 21157, unverified) or ZeroTier / Radmin VPN stay
  the answers above.

### Update 2026-10-20 morning: the overnight features between real machines

Record: [records/LAN-MATRIX-2026-10-20.md](records/LAN-MATRIX-2026-10-20.md). PC hosts, Andrew's Mac, Michael's Mac and the
laptop join (one at a time, then all four together); also Andrew hosts and the PC joins.

- **Everything passed, 0 crashes**: 29 joins, 12 hard exits (the slot goes after 39-43 s), 3 host quits (the game goes on, a
  Mac becomes host; in Hope Springs (4 AI) and Scene 5 its proxy takes over the AI pool / the co-op copies).
- ~~On a Mac, MULTI MELEE > HOST / JOIN shows MODEM / IPX / INTERNET / NULLMODEM: click IPX~~ **Fixed 2026-10-20 (proxy cf4f81da,
  pack `mp-pack-20261020-polish`)**: HOST / JOIN go straight to IPX on the Macs too (DxWnd held the proxy's LoadLibraryA slot; a
  watch thread now patches the shell), and the arena titles are shortened there as well. Record section 7.
- **Leaving from the game**: Esc > Abort Mission > Abort Mission > "Are you gonna leave me, Sweetheart?" Yes. The menu lights the
  row under the mouse.
- ~~After a host change in a co-op scene, one co-op copy of the old host can stay as a stray car on the map~~ **Fixed (cf4f81da)**:
  the new host re-parks the copies it has no joiner for and keeps the others; in AI arenas it counts the cars the old host had
  parked as parked. New, not fixed: when the co-op host leaves, the new host restarts the scene ("host lost", record section 7.2).
- **Steam Deck: not reached all morning** (asleep): it still has the 2026-10-18 files; stock arenas only with the others until
  its one-command step runs. **Afternoon:** arena files (15:10, main) and proxy cf4f81da + a new LAN launcher
  `i76-deck-launch-mp.sh` (15:25, record section 8) installed, rollback tested; the Deck boots through it with every MP hook in
  place (n 1), then went to sleep before its join could be measured.
- **Teams pack deployed (07:47)**: proxy **31efcf7a** (teams lane, TEAM PLAY with the AI on Men In Black, a returning AI takes the
  leaver's team) on the PC LAN copy, the laptop, Andrew's and Michael's Macs; pack `i76-uncap-lab\builds\mp-pack-20261020-teams\`,
  old folders kept, rollback per machine in the record's section 6. Measured across machines: AI t7 on both screens, the
  returning AI on the leaver's team (n 2), teams off unchanged (n 1). The Deck: not reached (own proxy, 2026-10-18 files).

### Update 2026-10-20 evening: one app per Mac (Mac converge lane)

Record: [records/MAC-CONVERGE-2026-10-20.md](records/MAC-CONVERGE-2026-10-20.md). Every Mac now has ONE I'76 app with the pack:
the laptop `~/Applications/Sikarugir/Interstate 76.app` (the pack in the owner's own app: CoreAudio, his saves, the Nitro and
DxWnd Settings launchers keep working), Andrew's and Michael's `~/Games/Interstate76-MP/Interstate 76.app` (Desktop link
**Interstate 76 LAN**). Old folders, test apps and helper folders deleted; one tarball of each app as it was before, in
`~/i76-archive-20261020/`. Proxy **0ce90a90** on the Macs (pack `i76-uncap-lab\builds\mp-pack-20261020-macconv\`: the polish
pack + `I76_MENU_PTR`, which makes the in-mission **Esc menu clickable on a Mac**: its lower rows, Cancel and Back could not be
clicked under DxWnd). The PC LAN copy keeps cf4f81da (same behaviour on Windows).

- **No sound on the laptop** was the GATE clone's switched-off Wine audio driver; the converged app has sound.
- **AI cars only come in the AI arenas**: host **Hope Springs (2 AI) / (4 AI) / (6 AI)** (or a Scenario / Co-op scene). The
  15 stock arenas (The Crater, Creeper Canyon, ...) are human-only.
