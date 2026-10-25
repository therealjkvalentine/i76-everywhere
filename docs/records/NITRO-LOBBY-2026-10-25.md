# Nitro on the community lobby (INTERNET button), naming, and stock compatibility, 2026-10-25 (nitro-lobby lane)

Owner (2026-10-25): approves **live lobby tests** and "reverse compatibility tests/fixes"; asks whether "ARENA+" would read
better as "AI Drop-In". Brief: rename every user-visible ARENA+; find the community's INTERNET route; try it with our build;
stock GOG Nitro against our build both ways; note what the lobby exposes for later hole punching.

Lab: `i76-uncap-lab\builds\nitro-lobby-20261025` (runner `lobby.py` for the PC, `lap2.py` + `laptop\lrun.py` / `lstart.ps1`
for the laptop, instrument `drv3`), captures `i76-uncap-lab\captures\nitro-lobby-20261025` (laptop runs) and
`captures\nitro-mp-20261021` (PC runs). Laptop copies `C:\i76-bench\lobby\{nitro,nitro2,stock}`; PC copies
`i76-uncap-lab\exp-nitro-lobby-ours` (twin of main Nitro) and `exp-nitro-lobby-stock` (pristine GOG). Main Nitro was only
read. Every test session was named **"i76e test - ignore"** and held 150 s or less. Times CDT.

## Answer in eight lines

1. **Naming:** the JOIN list now shows **"[AI] Evening Str (1/4)"** and **"[Co-Op] P01 (1/4)"**: the host names its session,
   fitted to the list ("[AI Drop-In] Evening Stroll" ran through the count and out of the box, so the long tag is used only
   when it fits). The GAME TYPE rows stay "Arena Drop-In + AI" / "Co-Op". No user-visible "ARENA+" is left (main dfb6ef1,
   0599b36; proxy **58df7e36**).
2. **The community route** is: Nitro + the **interstate76.com "Grab it and Go" `nitro.zip`** set (`anet2.dll` 23160234,
   `dll\WINETS2.DLL` e0009893, `miniupnpc.dll` 510453fa) + a lobby (`911.alink.bz911.net`, `play.interstate76.com`,
   `battlezone1.com`) on UDP 21157 + **UPnP on the host's router**. Peelar's own download host is gone (NXDOMAIN).
3. **Our build on the lobby works as a client:** it reaches bz911, hosts a stock Combat session that a second client lists
   through the lobby, and lists sessions (6 of 6 valid pairs, both DLL sets, both directions with a stock client).
4. **No join through the lobby succeeded here, for reasons outside our build:** GOG's own ANet DLLs publish the host as
   `128.127.50.1:7` (a placeholder the lobby passes on unchanged: "Cannot get info on this game", n 2); the community
   WINETS2 has an **off-by-one that drops the last character of the public address** it reads from ipinfo.io (published
   `x.x.x.25` for `x.x.x.253`, 4 of 4 starts), and our router offers **no UPnP gateway**, so a host at home is unreachable
   from outside anyway. Both clients were behind the same NAT; a phone hotspot is needed for the real cross-NAT case.
5. **Stock compatibility (IPX):** joins work both ways on one machine (5 of 5) and stock-joins-ours across machines (n 1);
   **open: a stock host on the PC never counted our laptop joiner (n 2) while a stock laptop joiner was counted (n 2)**
   (section 5a). No proxy fix was made for it yet.
6. **Fixes:** the INTERNET host form keeps the 5 stock GAME TYPE rows (an Arena / Co-Op session would register species
   7676 on a public server and be listed to nobody); the Nitro Alt-Tab crash that broke every two-window test was found to
   be the proxy's keep-on-blur call (fixed meanwhile by 788554a, proxy d738caac).
7. **Hole punching:** the lobby's SYN reply carries the client's **public address and port as the lobby sees it**
   (dpio SYN, version 5, "destination address"); the NAT kept the local UDP port (21193 -> 21193, 4 of 4). That is the
   STUN half; the session record carries only one address (the host's own claim), so a punch needs our own exchange.
8. **For the owner:** a phone-hotspot test (laptop off the home NAT), and whether to log in to the AT&T gateway
   (192.168.1.254, device access code) to look at its UPnP setting. No router setting was changed.

## 1. Naming (part A)

Owner's question: "ARENA+" or "AI Drop-In"? **Recommendation: the type keeps its full name "Arena Drop-In + AI" on the host
form, and the JOIN list shows a short bracket tag, "[AI Drop-In]" / "[Co-Op]".** "ARENA+" said nothing about what a joiner
gets; "AI Drop-In" says both halves (AI fill, join any time). The bracket keeps the arena or scene name readable after it.

| where | before | now (main dfb6ef1) |
|---|---|---|
| JOIN list name of a hosted Arena Drop-In + AI session | `ARENA+ Evening Stroll` (prefixed by the JOINER) | `[AI] Evening Str` (named by the HOST at dpOpen; `[AI Drop-In] <name>` when that fits) |
| JOIN list name of a hosted Co-Op session | `ARENA+ Evening Stroll` (the name box's arena title, wrong for a scene) | `[Co-Op] P01` (the scene of the selected list row) |
| a session from an older host (3f27c797 and before) seen by a new joiner | - | fitted the same way (`[AI] Evening Str`) |
| a new host's session seen by an older joiner (the Macs on 3f27c797 until they update) | - | `ARENA+ [AI] Evening Str` |
| box-mode labels (`I76_NITRO_GAMETYPES=0`, kept for one release) | `ARENA+`, `[ ] ARENA+` | `AI DROP-IN`, `[ ] AI DROP-IN` |
| docs/NITRO-LAN-WEEKEND.md, music-fix/README.md | `ARENA+ Evening Stroll` | the new names; records stay historical |

Code: `nitro_mp.c` (`nmp_open` calls `nf_session_name` for a 7676 session; the enum callback fits only names that do not
start with `[`), `nitro_form.c` (`nf_session_name` / `nf_fit_name` / `nf_text_px`: host form only, the record's 32-byte field
at +0x17, the scene from the selected record's file `pNN.msn`, the width summed from the shell's own glyph table
`0x10017e50` = `[font + [font + 0x10 + c*4]]`, budget 144 px). **The list width:** the JOIN list draws "name (n/m)" in one
string clipped by its box; the first cut (lapN-a1 / c1, "[AI Drop-In] Evening Stroll", ~240 px) ran through the count and
out of the box, the second (budget 182, lapN-a4) still overlapped; at 144 px "[AI] Evening Str (1/4)" sits inside
(lapN-a6, screenshot `lapN-a6-list.png`). The old "ARENA+ Evening Stroll" was over the width too. Stock 604 sessions are never renamed on either side. The
internal log tag stays `ARENA+` (lab parsers read it).

Host boots, one per type (laptop, IPX instance N, proxy wt1 54f15652 = dfb6ef1's tree, read from the proxy log):

| cell | GAME TYPE row | proxy log |
|---|---|---|
| lapA-a1 | 5 Arena Drop-In + AI | `session name 'Evening Stroll' -> '[AI Drop-In] Evening Stroll'`, `dpOpen species 7676 '[AI Drop-In] Evening Stroll' -> 0` |
| lapA-c1 | 6 Co-Op (P01) | `session name 'i76e test - ignore' -> '[Co-Op] P01'` (the name box held a typed name from an earlier run: a typed name is replaced for co-op), `dpOpen species 7676 '[Co-Op] P01' -> 0` |
| lapA-s1 | 0 Combat | `dpOpen species 025c 'Evening Stroll' -> 0 (stock)`, no rename |
| lapN-a6 (proxy 9aadc2f6 = 0599b36's code) | 5, joiner lists | `'Evening Stroll' -> '[AI] Evening Str' (141 px of 144)`; the joiner's list row `[AI] Evening Str` 7676 1/4 |
| lapN-a5 (budget 182) | 5, typed name "i76e test - ignore WWWW" | `-> '[AI] i76e test - igno'` (the cut works on any typed name) |
| lapN-c4 | 6 Co-Op | `-> '[Co-Op] P01' (95 px)`, listed `[Co-Op] P01` 7676 1/4 |

## 2. The community route (part B1)

- **Where the files are now.** Peelar's page (inbetweennames.net/projects/interstate76anet) links
  `peelar.myweb.cs.uwindsor.ca/winets2_v3.zip`: that host is **NXDOMAIN** (8.8.8.8 too), `cs.uwindsor.ca/~peelar` has an
  expired certificate and redirects to the dead host, and the Wayback Machine never archived the zip (CDX: only the index
  page). The page itself recommends "the patch bundles from interstate76.com". interstate76.com's front page ("Grab it and
  Go - Direct download!") serves **`https://interstate76.com/download/nitro.zip`** (146,735,090 B, Last-Modified 2024-10-06),
  a complete community Nitro install with the network set.
- **Downloaded as untrusted** to `D:\i76-archive\lobby-dl-20261025\interstate76com\nitro.zip`, sha256
  `25a2fee91b35e5feedae7b19389a3404f32566edafcedad5d58c0f9a3793d324`; **Defender custom scan of the folder: no threats**.
  Only the network files were extracted (`netset\`), nothing was run on the PC. The same anet2 / WINETS2 / miniupnpc md5s are
  in the archive.org "Interstate 76.7z" already held in `D:\i76-archive\community-20261024`.

| file (nitro.zip `nitro/I76Nitro/`) | md5 | sha256 | GOG Nitro has |
|---|---|---|---|
| `anet2.dll` (259,072 B, unpacked ANet 2 with "DUAL ADDRESSES") | 23160234 | f84075c12e4b9a1543cf8b2698fdfcd5dd2f55524cf2bbadc6a038fc58c2842a | a21c2baa (84,852 B, packed stub, 1998-03-05) |
| `dll\WINETS2.DLL` (13,312 B; imports WS2_32; loads `miniupnpc.dll` itself; HTTP `GET /ip` to ipinfo.io) | e0009893 | 01c3b12a11e2c4d03761269f2af194933199d13a0d2ac3ff56bb90d697a36478 | b91eccee (WSOCK32) |
| `miniupnpc.dll` | 510453fa | 8948b8fd1eb4c63b33f7cec2294d0b0541ac7f525cb44d05ebd317ab80dd440e | - |
| `internet.lst` (3 servers: "BattleZone One" battlezone1.com, "BattleZone 911" bz911.net, "Play Interstate" play.interstate76.com) | 22775af3 | e3bfab1bf6ad09c5c9d745ce49d95dfc3df9cf7981f6338a7df20f8aa9800443 | 5 dead Activision entries (australia1 / california3 / california12 / newjersey1.activision.com, stockholm.alink.fragzone.se) |
| `servers.dat`, `nitpatch.dll` a9a1898e..., `nitro.exe` 91d2a23d, `nitshell.dll` cba1839a | | | the community exe / shell are NOT GOG's (28b8ae27 / f804f50d); the shell's version string is the same "6.04" |
| Gold side: `Interstate76\DLL\WINET.DLL` | 6edfea77 | fce15ceae82b8863097fd35aeb4ee9524ee28a681cd407f2ab1aa4c7a7b0c50c | (Gold, not tested here) |

- **The lobby on GOG Nitro.** INTERNET (HOST or JOIN) opens **CONNECT TO SERVER**: NAME / IP fields, the `internet.lst`
  list, NEW / DONE / DELETE / CANCEL (screenshot `lapE-10-inet0.png`). GOG's list is Activision's dead servers, so a player
  adds one with NEW. The record format is `u32 count` + 0x60-byte records `{char name[32]; char host[64]}`; the lab copies got
  `BZ911 / 911.alink.bz911.net`, `Interstate76.com / play.interstate76.com`, `Glenrio / glenrio.interstate76.com`
  (`mklst.py`). DONE sets the server (`nitshell [0x1017a114]`, logged `'911.alink.bz911.net' use 1`). The servers live:
  bz911 = 52.116.46.118 UDP 21157 (the anet master list `kegel.com/anet/master/servers.txt` still names
  50.97.149.218, stale); play.interstate76.com and glenrio.interstate76.com serve the stock ANet `/anet2/` status page
  (per-game players / games / 24 h), empty today; bz911 has no status page.
- **UPnP.** The community WINETS2 asks the router for a UDP port mapping (miniupnpc `UPNP_AddPortMapping`). This network's
  gateway (AT&T BGW, 192.168.1.254) **does not answer SSDP for an InternetGatewayDevice** (multicast M-SEARCH from the PC and
  from the laptop, unicast to .254: NAS, TV tuner, Roku and a camera answered; the gateway did not), and its firewall pages
  that would show UPnP need the device access code (not used). So the DLL could not map anything; **no router setting was
  changed**. What hosting from home would need: UPnP on in the gateway, or a manual UDP forward of the host's ANet port.

## 3. Our build on the lobby (part B2)

All on the laptop bench (Windows 11, `C:\i76-bench\lobby`, console session, muted, FFB key set), two copies of main Nitro
(`nitro`, `nitro2`: GOG 28b8ae27 + nitshell a32ffba6 + dgVoodoo 2.87.5 + proxy as `strlkprx.dll` under the instrument drv3;
proxy wt1 54f15652 for the early cells, **d738caac** = main 061c313 from lapR-*7 on). The PC console was not used (the lab
queue held it for hours; the coordinator moved this lane to the laptop). Instrument: `drv3` = drv2 + INTERNET navigation
(`NMP_LAB_SRV` clicks on CONNECT TO SERVER), `NMP_LAB_NAME` (GAME NAME box 0x1017a04c), `NMP_LAB_JOINNAME` (joins only when
every listed session carries the test name: a public lobby lists other people's games), a MessageBoxA logger, and `NMP_NETLOG`
(this process's own UDP through WINETS2's socket imports, plus the hex of the first 64 bytes).

**Lobby cells** (host and joiner on the laptop, both behind the home NAT; the joiner starts 3 s after the host; the host
picks BZ911 > DONE, GAME TYPE Combat, GAME NAME "i76e test - ignore", BROADCAST; the joiner picks BZ911 > DONE, reads the
list, joins only our test session):

| cell | DLL set (both sides) | host on bz911 (state 5, net 1) | joiner lists the session through the lobby | join | why not |
|---|---|---|---|---|---|
| lapH-2 (host only) | GOG | yes, 60 s | - | - | - |
| lapP-oo1 | GOG | crashed at the joiner's start (Alt-Tab crash, section 6) | 0 sessions (host gone) | - | void |
| lapP-oo2, oo3 | GOG | yes | 0 sessions: the joiner was on the HOST form (instrument bug: `ijoinplay` routed to HOST; fixed) | - | void |
| lapP-oo4 | GOG | yes | **yes**: 'i76e test - ignore' 604, 1/4 | no: `dpOpen -> 16` (dp_RES_HOST_NOT_RESPONDING), "Cannot get info on this game"; no packet ever went to the host | the session record names the host `128.127.50.1:7` |
| lapP-cc1, cc3 | community | yes | **yes** | no: 10 SYNs to the host's published address in 35 s, no reply, "Cannot open connection to game" | the host published `<public>.25` instead of `.253` (WINETS2 off-by-one) |
| lapP-cf3 | community + the one-byte fix (lab, `NMP_LAB_FIXIP=1`) | yes; publishes the right `<public>.253:21131` | **yes** | no: 10 SYNs to `<public>.253:21131`, none arrived at the host | the home gateway does not loop a packet to its own public address back in (no hairpin for this mapping) |
| lapS-os1 | ours hosts (GOG set), stock GOG lists | yes | **yes**, the stock client lists ours (20 of 20 reads) | not tried (same NAT) | - |
| lapS-so1 | stock hosts, ours lists | stock host yes | **yes**, ours lists the stock session (20 of 20 reads) | not tried | - |

So: **our build is a working lobby client** (hosts registered on bz911 in every cell, listed by the other client in 6 of 6
valid pairs, both DLL sets, in both stock / ours directions). No pair joined, and every failure is explained by the address in the
lobby's session record or by the shared NAT, none by our proxy (a stock client fails the same way: lapS cells list only;
the GOG-set cells fail before any packet is sent).

**Not done: the cross-NAT join** (the laptop on a phone hotspot, the PC at home). With the GOG DLLs it cannot work
(`128.127.50.1:7`); with the community DLLs it needs a host whose router maps the port (UPnP or a manual forward) and, today,
the one-byte WINETS2 fix. **Needs the owner** (a hotspot), section 8.

## 4. The community WINETS2 drops the last character of the host's public address

Measured: every community-set client claimed `<public>.25` while the lobby saw it at `<public>.253` (4 of 4 starts:
lapP-cc1 / cc1-B / cc3 / cc3-B). Static: `WINETS2.DLL` e0009893 sends `GET /ip HTTP/1.1` / `Host: ipinfo.io`, takes ONE
`recv` of up to 0x200 bytes into `[ebp-0x2ac]`, terminates it with `mov byte [ebp+eax-0x2ad], 0` (+0x1b45, bytes
`c6 84 05 53 fd ff ff 00`) = `buf[n-1] = 0`, then `inet_addr(strrchr(buf, '\n') + 1)`. ipinfo.io's body has no trailing
newline, so the last digit goes: an address ending in a one-digit octet even fails `inet_addr`. With the displacement made
`-0x2ac` (`buf[n] = 0`; one byte, +0x1b48 `53 -> 54`) the host published the right address (lapP-cf3, n 1). Joiners take
the lobby's corrected view of their OWN address (anet2's "Overwriting myAdr" path), but the host's session record keeps the
claim, so this bug breaks hosting for every community player whose public address ends in two or three digits.
**Not changed in the proxy**: the owner's install uses GOG's DLLs; a proxy fix (byte-checked, only when the module is
e0009893) is a few lines if we ever ship the community set. Upstream: Peelar's source zip is gone; the interstate76.com
maintainers would be the ones to rebuild it.

## 5. Stock compatibility (part B3)

Through the lobby nothing joins on one network (section 3), so the reverse-compatibility joins ran over **IPX on the
laptop**, the route the family uses: stock = pristine GOG Nitro (`i76-map\sandbox-gog\nitro-full\app`, nitro.exe 28b8ae27,
nitshell f804f50d, anet2 a21c2baa, no proxy, no dgVoodoo) plus only IPXWrapper (b8464944's DLLs, instance M), behind the
lab instrument; ours = the main-Nitro twin with proxy **d738caac** (main 061c313) on instance L. Two IPXWrapper processes of
one instance on one machine collide ("Unable to create an IPX connection", lapR-os1 / so1), and two instances with the same
node never see each other (lapR-so3): L and M got their own keys (`HKCU\Software\IPXWrappeL / M`, port 54830, nodes
02:4c:00:00:76:11 / 02:4d:00:00:76:12; `laptop\ipxlm.ps1`, `-Remove` undoes).

| cell | host | joiner | listed | joined (state 5, net 1) | players host / joiner | car / version / mission complaints |
|---|---|---|---|---|---|---|
| lapR-so7 | stock | ours | yes | **yes** (t+5 s) | host 2 to t+145 s; joiner 2 to t+80 s, then 1 | none |
| lapR-so8 | stock | ours | yes | **yes** (t+5 s) | host 2 to t+145 s; joiner 2 to t+85 s, then 1 | none |
| lapR-os9 | ours | stock | yes (listed twice) | **yes** (t+3 s) | 2 / 2 to the end (host t+145, joiner t+95) | none |
| lapR-os12 | ours | stock | yes | **yes** | host 2 from t+15 to t+55 s, then 1; joiner 2 to the end | none |
| lapR-os13 | ours | stock | yes | **yes after one retry** (the first JOIN stalled 20 s; CANCEL + JOIN again, as a player would) | host 2 from t+65 to t+105 s, then 1; joiner 2 to the end | none |
| lapR-os11 | ours | stock | yes | stalled (JOIN clicked 1 s after the host's dpOpen, on a 0/4 record; no retry in that cell) | - | none |
| lapR-os7, os8 | ours | stock | yes | not tried: the instrument's first guard refused a list with the session twice | - | - |
| lapR-os1..3, so1..3 | - | - | - | void: one IPXWrapper instance for both processes, then equal nodes; and the Alt-Tab crash (os2, os3) | - | - |

**Joins: 5 of 5 valid cells joined** (stock host / ours joiner n 2, ours host / stock joiner n 3, one after a retry).
The version check ("6.04"), the mission CRC and the host's car check passed every time, and the proxy sends nothing of its own
in a 604 session (no 'AH' hello: `nitro-mp` acts only on species 7676).

**Open: the peer count drops on one side after 40-80 s in 4 of 5 joined cells, in both directions** (with a stock host too:
so7 / so8, where our build is only the joiner), never with an error box. All of these ran two games on ONE desktop, where one
window is always in the background; the family's PC <-> Mac Combat cells of s.0.5.22 (w55-s1 / s2) held 2 / 2 for 145 s on
two machines. Cross-machine cells (laptop <-> PC over the home LAN) to settle it: section 5a.

### 5a. Cross-machine (laptop <-> PC, IPXWrapper instance N on the home LAN, UDP 54792)

PC side: the nitro-mp-design lane's copy `exp-nitro-mp` borrowed (GOG unmodified + dgVoodoo + the stock strlkup as
strlkorg + the instrument, no proxy; it has the Private-network firewall rules a new folder lacks; the pristine
`exp-nitro-lobby-stock` also needed dgVoodoo on a private desktop: OpenGLide faulted at boot, lapX-5); instrument and
IPXWrapper N swapped in by `lobby.py` and put back (b577183c / 1ca45be0 read back). Laptop side: `lobby\nitro` (ours,
proxy f308f8f2 = the fit code with budget 182) or `lobby\stock` on instance N. The PC lock was taken first and the laptop
side ran inside it (`xcell.sh`, `lobby.py --pre / --post`). Session "i76e test - ignore", Combat, about 3 minutes each.

| cell | host | joiner | listed | joined | host's player count / joiner's |
|---|---|---|---|---|---|
| lapX-10 | laptop, OURS | PC, stock | yes | **yes** | 2 from t+25 s to the end / 2 to the end |
| lapX-7 | PC, stock | laptop, OURS | yes | joiner in the arena (state 5, net 1) | **1 for 200 s** / 2 |
| lapX-9 | PC, stock | laptop, OURS | yes | joiner in the arena | **1 for 200 s** / 2 |
| lapX-11 (control) | PC, stock | laptop, STOCK | yes | **yes** | 2 from t+25 to t+170 s / 2 |
| lapX-12 (control) | PC, stock | laptop, STOCK | yes | **yes** (after one retry) | 2 from t+75 s / 2 |
| lapX-6, X-8, X-13, X-14 | | | void: the joiner listed 0 sessions (X-6 / X-8 laptop host; X-13 / X-14 with the PC host's instrument net layer on, `NMP_NET=1`, which also showed only the host's own row) | | |

**Open finding (n 2, control n 2): a stock GOG host on another machine does not take our build in as a player** (its count
stays 1 while our joiner sits in the arena counting 2), where a stock joiner from the same laptop is taken in (2 of 2).
The other direction works (stock joiner of our host: X-10, and os9 / os12 / os13 on one machine). On one machine a stock
host did count our joiner (so7 / so8), so the cause is not settled: candidates are the host's car check on the joiner's
spawn ('SR' -> 0x446120, the "hacked vehicle" path; our copy is main Nitro's twin with its own `addon\` content and the
proxy's 604-session behaviour) or our joiner's spawn timing. Next cell: the stock PC host with an instrument that logs the
host's car-check result and the incoming 'SR' / 'ST' packets (not the net layer that hid the session in X-13 / X-14), and
the same join with the proxy unloaded on our side (`I76_NITRO_MP=0`, then no proxy) to split car data from proxy code.

Stock Combat sessions from our build are byte-compatible with the stock client in both directions: the version check
("6.04"), the mission CRC and the host's car check all passed, and the proxy sends nothing of its own in a 604 session
(no 'AH' hello: `nitro-mp` acts only on species 7676). **No proxy fix was needed.**

## 6. Fixes and side findings

- **INTERNET host form: stock rows only** (main dfb6ef1, `nitro_form.c` `nft_popup` / `nft_sync`). The GAME TYPE popup shows
  "Arena Drop-In + AI" / "Co-Op" on the IPX host form only; on INTERNET it keeps the 5 stock rows (read back: lapH-2 and every
  lobby host cell, `rows 5 of 5`) and the species stays 604. Reason: a lobby client subscribes to anet.inf's species only
  (ANet 0.10 `dpSetGameServer` -> `dpGetAppVersion`), so a 7676 session would sit on bz911 listed to nobody, as an unknown
  species on a community server. The OPEN-FEATURES row "LAN only until a session ID the lobby accepts is agreed" stands; the
  form now enforces it.
- **The Nitro Alt-Tab crash** (`exe+0x433C6B` call -> an address just below the proxy, the moment another window takes the
  focus in a mission) killed lapP-oo1 and lapR-os2 / os3 and the 2.87.3 control lapE-8. It is the proxy's keep-on-blur call
  re-aimed twice; the clean-install lane fixed it in **788554a** while these runs were going (the read-back now checks the call
  lands in `ffr_on_blur`). From lapR-*7 on the copies ran d738caac (061c313) and no focus change crashed (two windows on one
  desktop in every cell). The owner's main Nitro still runs 3f27c797, which has the bug (that lane's install).
- **Laptop bench**: a private desktop works there only with dgVoodoo 2.87.5 (`nitro-a` still carries 2.87.3, the copy here
  took nitro-b's set); the console-desktop route (`lrun.py`, scheduled `/IT` task) is what ran every cell.
- **Instrument bugs found on the way** (lab only): `ijoinplay` navigated to HOST; the joiner guard refused a list that showed
  the same session twice; netlog now re-hooks WINETS2 on every reload and covers WS2_32 as well as WSOCK32.

## 7. What the lobby exposes for hole punching (part B4)

Read-only, from this process's own UDP traffic (the instrument hooks WINETS2's `sendto` / `recvfrom`; the first 64 bytes of
each datagram; other players' records only as the client normally receives them, not reproduced here). Public addresses
below are the household's and are not written out.

- **The lobby tells every client its public address and port.** The dpio SYN (`'dY'`, version 5, 6-byte addresses = IPv4 +
  port, big-endian) from the server carries `{server address, destination address, capabilities, server address 2}`: the
  destination is the client as the server saw it. ANet 0.10 `dpio.c` documents the field ("destination's adr, added
  10/23/97") and the "Overwriting myAdr!" / "Exchanging addresses" logic that uses it. Measured on bz911:

  | client | its own claim in its SYN | the lobby's view (SYN reply) |
  |---|---|---|
  | GOG anet2 / WINETS2, 13 starts (10 with the lobby's reply logged) | `128.127.50.1:7` every time (never corrected; also the address its session record carries) | `<public>.253 : 52254..63552` (an ephemeral port per start) |
  | community set, 4 starts | `<public>.25 : 21131..21207` (ipinfo.io, last digit dropped) | `<public>.253 :` **the same port** (21193 -> 21193, 21177 -> 21177, 21140, 21207: the NAT kept the local port, 4 of 4) |
- **The session record carries one address**, the host's own claim (`'dT'` table packet: `... 5c 02` species 604, name,
  `adrMaster` 6 bytes); the lobby passes it on unchanged (GOG: `128.127.50.1:7` arrives at the joiner as sent). So the lobby is
  a STUN-like reflector for each client, but it does **not** publish the reflected address of the host; a hole punch needs our
  own exchange of the reflected addresses (I26's way: REQUEST_OPEN through the lobby, then probes both ways).
- **The AT&T gateway**: port-preserving (4 of 4) and no hairpin to its own public address (lapP-cf3). Port preservation is the
  friendly case for punching; filtering behaviour toward an unsolicited peer was not testable without a second NAT.
- **Other traffic the community anet2 sends on its own**: two 19-byte `'dB'` packets with species 604 to 50.250.167.13
  (play.interstate76.com) and 54.244.133.27, answered with `'dC'` (server pings / app checks); the WINETS2 HTTP call to
  ipinfo.io (TCP, not in the UDP log; from the strings).
- **The table the lobby sends after login** holds other games' sessions too (about 40 records with many species values, e.g.
  Battlezone maps); the client filters by species. Our session came back to its host as a 604 record.

## 8. For the owner / the coordinator

- **QA (owner):** a hotspot pass. The laptop on a phone hotspot, the PC at home. With the GOG DLLs no join can work
  (`128.127.50.1:7`); worth one try with the community set + the one-byte fix on the laptop as HOST is pointless without a
  mapping on the hotspot side, so the useful cell is PC hosting at home **with a UDP forward or UPnP on the AT&T gateway**
  (owner's call; nothing was changed) and the laptop joining from the hotspot. Without that, internet play stays option (c)
  of INTERNET-PLAY-SPIKE (a relay) rather than the lobby.
- **Decide:** whether to read the AT&T gateway's UPnP setting (192.168.1.254 > Firewall > NAT/Gaming, device access code).
- **Installed:** nothing in main Nitro (still proxy 3f27c797, nitshell a32ffba6). The naming is in main from dfb6ef1 + 0599b36;
  the current main proxy build is **58df7e36** (0599b36, built twice, identical); it reaches the owner's copy, the Macs and
  the kit with the next Nitro proxy rollout, which also brings 788554a's Alt-Tab fix. Not installed by this lane because that
  build carries every lane's work since 4e40261 with no Nitro multiplayer pass, and section 5a's open finding should be
  read first. Until the Macs update,
  a Mac joiner of a new PC host reads `ARENA+ [AI Drop-In] Evening St`; a new joiner of an old host reads `[Drop-In] ...`.
- **Lab state left behind:** laptop `C:\i76-bench\lobby\` (copies nitro / nitro2 / stock, runs\), keys
  `HKCU\Software\IPXWrappeL / M` on the laptop (`ipxlm.ps1 -Remove` deletes them), PC lab copies `exp-nitro-lobby-ours` /
  `exp-nitro-lobby-stock` (the twin was not booted; the stock one got dgVoodoo, its OpenGLide kept in `_gog-renderer\`),
  archive `D:\i76-archive\lobby-dl-20261025\`. Laptop `C:\i76-bench\lobby\nitro` is on IPXWrapper L, `stock` on M.
