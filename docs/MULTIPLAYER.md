# Multiplayer over the home LAN (IPX through IPXWrapper)

*2026-10-05. Status line, measured / not measured, is in section 0. Lab records behind every claim:
`../i76-uncap-lab/docs/MULTIPLAYER-LOCAL-TEST.md` (transport, sections 8 and 9) and
`../i76-uncap-lab/docs/MULTIPLAYER-CAR-CHECK.md` (the anti-cheat car check).*

## 0. Status

| claim | state |
|---|---|
| IPX between two game copies on one PC, IPXWrapper 0.7.2 | **works** (2026-10-05, n = 1): host BROADCAST GAME went into The Crater, the joiner listed "THE CRATER (1/4)", JOIN GAME, and each copy then held both cars at the same coordinates (within 0.1 m). Stock car data (Jade's Car `valepre4.vcf` de680a86) |
| IPX between two PCs on 192.168.1.0/24 | **not run yet** (same mechanism: IPXWrapper broadcasts UDP on every LAN interface) |
| The daily driver's cars pass the anti-cheat check | its `valepre4.vcf` is byte-identical to the file that passed the host and joiner checks live in row 1; the other 67 variants: static read (MULTIPLAYER-CAR-CHECK.md section 0) |
| Mac (Wine) running IPXWrapper | **unknown**, see section 6 |

## 1. Why IPX, and what the other buttons do

The game's multiplayer menu offers MODEM, IPX, INTERNET, NULLMODEM. Only **IPX** works today:

- **INTERNET** needs an Activision game server (`internet.lst`). Those are gone. Hosting stops at "Game Server Not
  Responding" and a peer cannot stand in for the server (lab doc 8.2-8.3).
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

Not run yet. The Mac session surveyed the MacBook read-only on 2026-10-05; nothing there was changed, and trying
IPXWrapper is for a **test clone** of the prefix, after the owner says yes in that session.

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

Open questions: whether Wine's `ws2_32` loopback-delivers the subnet broadcast that WIPX must hear back within 5 s
(otherwise IPX init fails, error 0x84), whether DxWnd's winsock hooks get in IPXWrapper's way, and whether Tailscale
changes which interface the broadcast leaves on.

## 7. Two players on ONE PC

See `../i76-uncap-lab/nucleus-coop/README.md` (Nucleus Co-op handler) and the lab doc section 9. That route needs two
game copies, a patched second `ipxwrapper.dll` (its own mutex and registry key), `I76_MULTI_INSTANCE=1`, and for pads,
the proxy's `I76_JOY_MAP` (each copy binds `joystick1`; the switch routes it to that copy's pad).

Joystick slots, measured 2026-10-05 with a synthetic pad (lab doc section 9): the engine opens `joystick1` and
`joystick2` normally, but opens every higher slot with winmm id 1's caps and first poll, so `joystick3`+ work only
while a device sits at winmm id 1. `I76_JOY_MAP=0=<id>` with `joystick1` in input.map avoids that for any pad id.
