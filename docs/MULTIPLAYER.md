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
| James's laptop | `~/Applications/Sikarugir/I76 MP GATE.app` until the pack is swapped into his own `Interstate 76.app` (rollout record section 5) | inside that app |
| Steam Deck | Steam (Game Mode) > **Interstate 76** (non-Steam shortcut, launches `~/Games/Interstate76/i76-deck-launch.sh`) | `~/Games/Interstate76/game` |
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
2. One host (any machine; a Mac host and a PC host are both measured): MELEE > MULTI MELEE > HOST > IPX, pick an
   arena (the 15 stock arenas are normal melee; **Co-op Scene 1..17**, after A Lot of Asphalt, are the 2-player co-op
   campaign, records/COOP-LIST-ENTRIES-2026-10-18.md), RENAME the game to something
   recognisable, **BROADCAST GAME**. The host drives straight into the arena.
3. The others: MELEE > MULTI MELEE > JOIN > IPX, click the game's row, **JOIN GAME**. Joining while the host drives
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
