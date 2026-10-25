# Internet play for people off our LAN and off Tailscale: research spike, 2026-10-25

Owner's question: *"How would we play Interstate '76 / Nitro with people on the internet who are not on our LAN or
Tailscale, or not generally trusted? Before solutions: what does the stock Nitro Pack do, what do modern games do, and
what exists in the open-source community?"*

Research only, no code. Every claim is either (R) read in this repo / the lab records, (S) read in source we hold
locally (ANet 0.10, IPXWrapper 0.7.2, I26 0.6.0 decompiled, analysis only), (W) read on the web today with the URL
given, or **unverified** (marked). Nothing here was measured today.

## Answer in six lines

1. **The stock game already shipped the right idea.** ANet 2 (Nitro, 1998) was designed for "clients behind firewalls
   (but not servers)": 6-byte IP+port addresses, the game server tells a client its external address, peers ping both
   addresses. The community keeps that alive (bz911 lobby + Peelar's UPnP patch). Base I'76 (ANet 1, March 1997) has
   only the retro-fitted NAT patch in GOG's `WINET.DLL` and a direct-IP route on UDP 21157 that nobody here has tested.
2. **Our measured route (IPX through IPXWrapper) is LAN-only by construction**: IPXWrapper has no unicast / direct-IP
   mode at all; its only internet mode is "DOSBox encapsulation", which failed here because the DOSBox server never
   echoes a broadcast to its sender and `WIPX.DLL` needs that echo. **IPXWrapper master (unreleased, commit e7e9883,
   2026-08-02) fixes exactly that**: "Fix delivery of locally-generated packets to the same process when using
   IPXWrapper UDP or DOSBox encapsulation". That makes (c) below a one-evening spike instead of a project.
3. Virtual LANs that carry broadcast (ZeroTier, Radmin VPN, Hamachi) make IPXWrapper work unchanged; Tailscale does
   not carry broadcast, so IPX discovery over it cannot work (direct IP over 100.x might; untested).
4. Modern games answer NAT with hole punching (82 % of UDP NATs in the 2005 study) plus a relay fallback, and answer
   trust with a server that owns the rules, passwords / invite codes, and data checks. I26 (vahokif) already does the
   hole punch *through the stock ANet lobby* (`I26P` probes, 10 s, both addresses): the lobby is the signalling server.
5. Our proxy already has the hooks (dpOpen / dpReceive / list, species 0x7676, IPXWrapper instance N) and the data
   checks (car rule, mission CRC), so the missing pieces are transport and identity, not game code.
6. **Recommended order:** (c) IPX-over-UDP relay with IPXWrapper master (spike now; one hosted port, works for Gold,
   Nitro and the Macs' IPXWrapper-under-Wine), (b) Gold direct IP as a two-household owner test, (a) ZeroTier for
   friends we trust now, (d) only when there is a community to serve, (e) watch I26.

## 0. What the project already knows (not re-derived)

| fact | where |
|---|---|
| IPX through IPXWrapper 0.7.2 is what works (one PC, LAN, PC + Mac + Deck, 4 players, host migration); the LAN pack | [../MULTIPLAYER.md](../MULTIPLAYER.md) s.0, 2-8 |
| INTERNET on Gold fails on one LAN ("Game Server Not Responding" / "No games found"), both with the host's own address and with the bz911 lobby; Peelar's page explains it (tested only < 1.083, "no clients on the host's own network") | MULTIPLAYER.md top table, 2026-10-06 |
| "Internet / direct-IP play: untested"; ZeroTier / Radmin carry broadcast, Tailscale does not; IPXWrapper DOSBox-server mode **fails** (n 2): WIPX's 4-byte start-up broadcast never comes back from a DOSBox server | MULTIPLAYER.md s.0 last rows; [../records/MP-OVERNIGHT-2026-10-20.md](../records/MP-OVERNIGHT-2026-10-20.md) s.5; lab MULTIPLAYER-LOCAL-TEST s.8.4 (predicted from dosbox-x `ipxserver.cpp`) |
| `WINET.DLL` (GOG): one UDP socket bound to **0.0.0.0:21157, hard-coded**; own address found by hearing its own broadcast back within 5 s (else error 0x84); typed addresses always become IP:21157; the DLL carries a hand patch replacing the sender's address by `AAAA:DEADBEEF` / `BBBB:ABADC0DA` markers that the receiver fills from `recvfrom` (= Peelar's NAT fix) | lab MULTIPLAYER-LOCAL-TEST.md s.2, 8.1-8.3 |
| `WIPX.DLL`: `AF_IPX` socket 0x52A3 hard-coded, broadcast enumeration, no server; `ANETDLL.DLL` (March 1997): `dpOpen` returns 0x10 unless the game-server handle is ESTABLISHED | lab MULTIPLAYER-LOCAL-TEST.md s.8.1-8.2 |
| Nitro: `dpOpen(session species 604)`, `dpEnumSessions` asks for 604 only, INTERNET reads `internet.lst` / `lobby.dat` and calls `dpSetGameServer`; our ARENA+ hosts register species 0x7676; a patched client would subscribe a second session table on the lobby; `nmp_lobby_subscribe()` is a stub; "ARENA+ is IPX / LAN only until a species is agreed with the community" and any live-lobby test is owner-approved | [../records/NITRO-MP-DESIGN-2026-10-21.md](../records/NITRO-MP-DESIGN-2026-10-21.md) s.1.1, 0.5.8 |
| The bz911 lobby serves a custom species (I26 uses 18726), so the lobby needs no server change; anet 0.10 is LGPL 2.1 and public | NITRO-MP-DESIGN s.0.5.8; [../PRIOR-ART-I26-2026-10-21.md](../PRIOR-ART-I26-2026-10-21.md) s.8 |
| The PC's Tailscale subnet route (`RouteAll`) sent LAN unicasts through Tailscale and broke a Nitro join until `--accept-routes=false` | NITRO-MP-DESIGN s.0.5.15-16 |
| I26: own UDP netcode (LiteNetLib, port 7676, protocol 13 at 0.6.0), dedicated `i26-server`, "internet play through community servers with UDP hole punching", passwords, invite-only, host migration as saved state, deterministic sim | PRIOR-ART-I26 s.1, 2, 8 |
| Open feature row: "Internet / off-LAN play: direct IP (UDP 21157) untested; ZeroTier / Radmin carry broadcast; IPXWrapper DOSBox mode does not work" | [../OPEN-FEATURES-2026-10-24.md](../OPEN-FEATURES-2026-10-24.md) s.5.1 |
| Community routes index: Peelar's patches, anet master list, UltraFunk Discord, Lightfoot's Nitro guide, UCyborg on NAT, GOG forum (Tunngle era), IPXWrapper issue #22; "GameRanger: no Interstate title. Kali and Tunngle: dead or unused for I'76 since about 2011" | [../COMMUNITY-RESOURCES.md](../COMMUNITY-RESOURCES.md) s.3a |
| The car rule: `ValidateVcf` budget check + CRC over `.vdf/.wdf/.gdf/.cdf` recomputed by the host; mission file name + CRC-32 checked on join | MULTIPLAYER.md s.4, s.8 |

## 1. STOCK: what Interstate '76 and the Nitro Pack shipped

### 1.1 Transports

Both games load a transport DLL per menu button (MODEM, IPX, INTERNET, NULLMODEM): Gold `DLL\WINET / WIPX / WMODEM /
WSERIAL`, Nitro `dll\WINETS2 / WIPX2 / WMODEM2 / WSERIAL2` (all different binaries) plus `dkupddll.dll`, an updater
("This upgrade is required to play in multiplayer mode") (R: records/NITRO-VS-RETAIL-2026-10-20.md). The ANet 0.10
source has the same five Windows drivers in `src/win/`: `winets` (Winsock TCP/UDP, "Multiport Winsock TCP Protocol",
with `winets2` and `wudplan` build variants), `wipx`, `wloop` (loopback), `wmodem`, `wserial`; Mac `minet / minets /
mipx / mmodem / mserial` (S: `i76-uncap-lab\refs\anet\anet-master\src\win`). The box copy promised "eight-player LAN,
hood-to-hood modem and Internet combat" (W: [elisoftware.org listing](https://elisoftware.org/wiki/Interstate_%2776_(PC,_CD-ROM)_Activision_-_1997_USA,_Canada_Release)).
Nitro's listing adds "through a LAN connection, the Internet, modem or link cable" (W: [MobyGames](https://www.mobygames.com/game/interstate-76-nitro-pack)).

The MODEM and NULLMODEM transports need serial ports and are out of scope. No DirectPlay anywhere: `WIPX.DLL` imports
only WSOCK32 and opens `AF_IPX` sockets itself (R: lab s.8.1), which is why IPXWrapper's `dpwsockx.dll` is optional.

### 1.2 ANet ("Activenet", "Activlink"): the library, its licence, how internet play was meant to work

- **What and licence.** "Anet is a peer-to-peer networking system; it also supports a central chat server", built at
  Activision from 1995 and used in "twenty-odd multiplayer games for MS-DOS, Macintosh, Windows 95, and Linux" between
  1995 and 2001; Activision released it under the **GNU Lesser General Public License** (W: [kegel.com/anet](https://kegel.com/anet/)).
  The public mirror is [github.com/Nielk1/anet](https://github.com/Nielk1/anet), **LGPL-2.1**, README dated
  2001-09-04, "builds on Linux and Windows 95 and higher" (W). Version 0.10 is the only release (anet-0.10.tar.gz).
  The lab holds a copy (`i76-uncap-lab\refs\anet`). The server README names the games: "Dark Reign, Battlezone, Heavy
  Gear, Zork, Shanghai, and other games" (S: `src/linux/server/README2.txt`, 1998-10-05); the architecture doc names
  "a game such as Interstate '76" as a game client (S: `src/doc/arch.htm`).
- **Architecture** (S: `src/doc/arch.htm`, "Last updated: 10 Aug 1998"): sessions are **peer-to-peer**; the **game
  server** "tells game clients and web browsers about current games and chat areas", publishes a SESSIONS table (dptab,
  "transmits only changes in tables") keyed by the game's 16-bit `sessionType` (our "species"; 604 Nitro, 666 Dark
  Reign); a **master server** keeps the list of game servers, downloaded by the library when a client connects
  (today: [kegel.com/anet/master/servers.txt](http://www.kegel.com/anet/master/servers.txt) = `911.alink.bz911.net`,
  `battlezone1.net`, `play.interstate76.com`, W). The server is a Linux program "distributed free of charge to Internet
  Service Providers", "acts mostly as a player-matching service", sized for "about 250 very active users" on a Pentium
  200 behind a T1 (S: `doc/server.htm`, `README2.txt`). **It does not relay game traffic**: nothing in `server.c` or
  `dp2.c` forwards session packets; game data goes peer to peer.
- **The 1998 firewall strategy, verbatim** (S: `arch.htm`, "Firewall Strategy"): "To accomodate port mapping
  firewalls, the address used on IP has been extended to six bytes to include the port number; clients no longer always
  open a particular port. [...] clients which are behind a firewall will ask the game server what IP address and port
  number they appear to be using, and will use that when constructing ID's. Client machine records will contain both the
  external IP adr/port number and the internal IP adr/port number. When a client opens a connection to another client,
  it checks to see if it might be behind the same firewall; if so, it pings the other client at both addresses, and uses
  the address/port number of the first reply". Design goal: "Able to work with clients behind firewalls (but not
  servers)". That is STUN-plus-dual-address-ping, written in 1998, and `winets` implements the 6-byte address
  ("Bytes 4 and 5 are the port number in network order", "commInit now chooses a random port number by default",
  S: `src/win/winets/wstcpdll.c`). **Base I'76's ANETDLL.DLL (March 1997) and WINET.DLL predate all of it**
  (4-byte addresses, hard-coded port 21157, R: lab s.2); Nitro's ANet 2 has it. Why the community still needs patches
  is in 1.4.

### 1.3 How people played online in 1997-98

- **Activision's own ANet game servers.** The stock `internet.lst` of Gold lists "I'76 Net / i76net.activision.com",
  "I'76 Net / 206.79.5.4" and "play.interstate76.com" (R: lab MULTIPLAYER-LOCAL-TEST s.1; S: the lab copies'
  `internet.lst`). Local Ditch: "Originally, I '76 came set up to use Activision's Anet (Alink, Activelink, Activenet)
  servers", since shut down (W: [Local Ditch FAQ](https://www.localditch.com/interstate-76/faq.html), "Last update
  10/18/26"). Peelar: the base game's ANet is "too old to use with the Activision Game Servers, so only direct
  connections work", while Nitro "can connect to Activision Game Servers to get game lists" (W: [Peelar's RE blog](https://inbetweennames.net/blog/2021-05-04-interstate-76-reverse-engineering-efforts-the-story-so-far/)).
  *Reading:* in 1997 base I'76 hosted through the lobby with public IPs on both ends; the servers are gone and nothing
  in the base game's ANet 1 speaks today's ANet 2 server protocol. (The "too old" sentence is Peelar's; **unverified**
  whether a 2026 ANet 2 lobby rejects an ANet 1 login or whether it is the address format that breaks.)
- **Mplayer / Heat.net / TEN.** No source found that lists Interstate '76 on any of them (W: searches of game lists,
  forum recollections name MechWarrior 3 and others, not I'76). Treat "I'76 was on Mplayer" as **unverified /
  probably false**; the game had its own lobby network.
- **Kali.** An "IPX network emulator for MS-DOS and Windows" from spring 1995: "all the machines on the VSN appear to
  be normal IPX network nodes sitting on a single subnet. The application has no idea that it is really being played
  over a TCP/IP network" (W: [Kali, Wikipedia](https://en.wikipedia.org/wiki/Kali_(software)); [1995 kali.doc](https://discmaster.textfiles.com/view/10593/Netware%20Super%20Library.iso/inet_tcp/kali10wb/kali.doc)).
  "Today, Kali's network is still operational but development has largely ceased"; registration is free (W: Wikipedia;
  Local Ditch FAQ: "Kali.net is also still running and can be used"). One 2011 GOG poster claimed Kali "perfectly work
  with nitro pack and original"; the thread never confirmed it (W: [GOG thread](https://www.gog.com/forum/interstate_series/help_us_with_the_multiplayer_gog)).
  **Unverified for I'76 on Windows 10/11.** Kali's Windows client needs an IPX stack the OS no longer has; whether it
  runs over IPXWrapper is unknown.

### 1.4 What the INTERNET button does today, and whether any of it can still function

**Gold (base game, GOG 1.083):**
- HOST > INTERNET opens CONNECT TO SERVER (list from `internet.lst`, NEW adds an entry); DONE calls `dpSetGameServer`,
  `dpOpen` then needs the dpio handle to that server ESTABLISHED or the shell prints "Game Server Not Responding"
  (R: lab s.8.2-8.3). Activision's entries are dead; `play.interstate76.com` is in the anet master list but Peelar's
  blog says the base game cannot use ANet 2 servers.
- **Direct IP.** GOG's `WINET.DLL` is Peelar's 2011 patch (with Rob Roddy): addresses "stored in the DLL as 6 bytes
  instead of 4, to accomodate the 2 byte port number", sentinel addresses filled in transparently (W: [Peelar's
  project page](https://inbetweennames.net/projects/interstate76anet/); the lab read the same code caves, R). Procedure
  from that page: host "Forward port 21157 on your router to your computer. [...] Just make sure there are no clients
  on the host's own network"; joiners "Get the host's external IP address. Open the 'Join Game/Internet' screen and
  enter that address. The game should list the host." Caveats, verbatim: "Only Vanilla I76 below 1.083 was tested by
  the author", "largely untested", "1v1 games working without problems"; the LAN-client problem "The author plans to
  fix this with a modified ANet matchmaking server, which hasn't been written yet". UCyborg (2019): "Direct IP
  connections work as far as I can tell" (R: COMMUNITY-RESOURCES; the Wayback copy could not be fetched today).
  Because `commScanAddr` always appends :21157 (R: lab s.2), **only one host per public IP** and the host's port
  cannot be changed without a byte patch (the lab's `winet-portsplit.ps1` did exactly that, R: lab s.8.3).
  Our 2026-10-06 failure was measured with host and joiner **on the same LAN**, the one case Peelar excludes, so it
  does not rule the route out (R: MULTIPLAYER.md).
- Password: the Gold host form has no password field that we know of; **unverified**. Anyone who knows IP:21157 and
  passes the car check can join.

**Nitro (ANet 2):**
- HOST / JOIN > INTERNET reads `internet.lst` / `lobby.dat`, logs in to the chosen ANet 2 server, lists species 604
  (R: NITRO-MP-DESIGN s.1.1). `911.alink.bz911.net` answers in October 2026 (R: MULTIPLAYER.md). Peelar: "You must use an
  ANet2 server. The page recommends battlezone1.net"; the patch collections on interstate76.com point at
  interstate76.com's server (W: Peelar's page and blog). The stock Nitro can list games today; what fails is the
  peer connection through NAT.
- **Why NAT still breaks stock Nitro although ANet 2 was designed for it.** The 1998 design assumed the *host* is
  reachable ("clients behind firewalls (but not servers)") and the lobby gives the host's address as the host sees
  itself; with both ends behind home routers nobody can open the first packet. UCyborg's thread 1508 explains the
  server-side part (R: COMMUNITY-RESOURCES; not re-read today). Peelar's fix ("completed early 2014"): `WINETS2.DLL`
  rebuilt from the ANet source with **miniupnpc**, so the host's router forwards the port at session start; "The only
  caveat is that your NAT needs to support UPnP"; install by replacing `anet2.dll` and `winets2.dll` (W: Peelar).
  Direct IP on Nitro: "guaranteed to not work for the time being" (W: Peelar). So Nitro's internet route is
  **lobby + UPnP on the host**, and that is what the UltraFunk Discord players use (R: MULTIPLAYER.md).
- The PCGamingWiki "Interstate '76 + Nitro Pack AiO Patch" bundles "Shane's netcode patches to be able to play
  normally over the internet when behind NAT"; "If you're patching Interstate '76, you must install Gold Patch first"
  (W: [search excerpt](https://community.pcgamingwiki.com/files/file/1349-interstate-76-nitro-pack-aio-patch/); the
  page itself returned 403 today).

**Can it still function?** Nitro INTERNET: yes, with Peelar's DLLs, a UPnP router and bz911 or interstate76.com's
server; this is the live community's route. Gold INTERNET: only as direct IP with forwarding, one host per public IP,
no LAN joiner beside the host, untested by us. Neither needs Activision.

## 2. How the community plays old IPX / DirectPlay games today

### 2.1 IPXWrapper (what we ship)

- Version 0.7.2 (2025-08-08), GPL-2.0, "emulates IPX support while tunneling the packets over UDP"; Interstate '76 on
  its reported-working list (W: [solemnwarning.net/ipxwrapper](https://www.solemnwarning.net/ipxwrapper/); [GitHub](https://github.com/solemnwarning/ipxwrapper)).
- **Three encapsulations, no unicast / direct-IP mode.** (1) Default: IPX in UDP on the LAN, broadcasts to port
  54792 on every interface, "Each instance of IPXWrapper binds to a random UDP port for sending and receiving packets.
  The 'normal' port is shared only for receiving broadcasts" (W: [changes.txt](https://raw.githubusercontent.com/solemnwarning/ipxwrapper/master/changes.txt), 0.4.0); a "Primary interface" can be set.
  (2) **"DOSBox UDP encapsulation"**: "select the 'DOSBox UDP encapsulation' option in ipxconfig and enter the
  address/port of your DOSBox server", meant for internet play or Windows-to-DOS; "SPX connections are not supported"
  (W: README). Added in 0.7.0 ("Added support for DOSBox IPX servers"). (3) "Real IPX encapsulation" via WinPcap
  (0.6.0). The whole `ipxwrapper.ini` vocabulary is: `dosbox server address`, `dosbox server port`, `coalesce
  packets`, `send packet limit`, `send byte limit`, `firewall exception`, `logging` (W: [ipxwrapper.ini.example](https://raw.githubusercontent.com/solemnwarning/ipxwrapper/master/ipxwrapper.ini.example)).
  **So "IPXWrapper unicast + port forwarding" (option b of the brief) does not exist as a feature**; the only
  non-LAN route is a DOSBox-protocol server. There are no "internet" instructions in README or changelog; the
  closest items are a 0.3.2 "workaround for Hamachi bug" and a 0.4.1 "workaround for point-to-point links" (W).
- **The DOSBox-mode failure we measured has a fix in master.** Commit e7e9883 (2026-08-02) "Fix delivery of loopback
  packets. Fix delivery of locally-generated packets to the same process when using IPXWrapper UDP or DOSBox
  encapsulation": `ipx_send_packet()` now calls `deliver_packet()` locally for a destination matching the local
  DOSBox net/node and after successful broadcasts, and the UDP receive path drops the copy that loops back through
  the socket; tests `30-dosbox-ipx.t` / `30-ip-ipx.t` add an "ipx loopback packet delivery" case (W: [commit](https://github.com/solemnwarning/ipxwrapper/commit/e7e9883551bbb582336a7650791b9473a2dec0a8);
  changelog entry "UNRELEASED"). WIPX's init is exactly "send 4 bytes to the broadcast address and wait up to 5 s to
  receive them back" (R: lab s.8.1), which the DOSBox server never does (2.2). **Unverified** that the fix is
  sufficient for WIPX (the self-echo may not be the only thing; the session handshake then runs through the server).
  Later master commits (to 2026-09-15) are build fixes and "respond to ping" (W: [commits](https://github.com/solemnwarning/ipxwrapper/commits/master)).
  The lab has `w64devkit` and the 0.7.2 source in `refs\`, so a master build is local work.
- Issue #22 is a 48-work / 19-fail list of games under DOSBox encapsulation compiled by NukemNet's author, who "spawns
  IPXBox for the host, copies the IPXWrapper DLLs into the game directory, and sets the registry entries with the host
  IP and port" (W: [issue #22](https://github.com/solemnwarning/ipxwrapper/issues/22)). I'76 is not on that list.

### 2.2 DOSBox-protocol IPX servers (the relay that IPXWrapper can talk to)

- Protocol: client-server, IPX in UDP, default UDP **213**; "If the server sits behind a router, the chosen UDP port
  has to be forwarded. Clients don't need their own port forwarding" (W: [DOSBox wiki IPX](https://dosbox.com/wiki/IPX),
  [DOSBox Staging manual](https://www.dosbox-staging.org/0.83/manual/networking/ipx/)). Registration is a packet to
  socket 2 with destination host 0; the server answers with the client's assigned address.
- **Broadcast is sent to every client except the sender** (the cause of our failure), dosbox-x `ipxserver.cpp`:
  `if(connBuffer[i].connected && ((ipconnguest[i].host != srchost)||(ipconnguest[i].port!=srcport)))` (W: [source](https://raw.githubusercontent.com/joncampbell123/dosbox-x/master/src/hardware/ipxserver.cpp)).
- **ipxbox** (fragglet, Go, GPL-2.0): "a standalone DOSBox IPX server", with keepalive pings "so NAT-behind users
  aren't timed out", syslog "when running a public server", a built-in PPTP server for Windows 9x, TUN/TAP / libpcap
  bridging to a physical network and "Uplink functionality for bridging a network to a remote ipxbox server"
  (W: [github.com/fragglet/ipxbox](https://github.com/fragglet/ipxbox)). No authentication is mentioned (**unverified**:
  the HOWTO returned 503 today). Docker images exist (unraid listing, W). This is the natural hosted relay for (c).
- NukemNet: "A multiplayer launcher for retro games", 167 games, Windows / Linux / macOS and a browser "Web Arena";
  I'76 is not listed (W: [nukemnet.com](https://nukemnet.com/)). Its mechanism (issue #22) is the (c) shape: a hosted
  IPXBox plus IPXWrapper in DOSBox mode, registry set per player.

### 2.3 Virtual LANs

| tool | what it is | broadcast (needed for IPX discovery) | limits / trust | source |
|---|---|---|---|---|
| **ZeroTier** | layer-2 virtual Ethernet switch over UDP with its own NAT traversal and root relays | default L2 filter "allows only IPv4, IPv6, and ARP traffic" (fine: IPXWrapper's packets are IPv4 UDP); `ipx_a` / `ipx_b` ethertypes exist for rules; broadcast support claimed by secondary sources only, **unverified** against official docs today | free tier; flow rules can restrict a network to UDP 54792 and the game ports; everyone on the network is a LAN neighbour otherwise; libzt SDK is BSL-1.1, the client is open | W: [docs.zerotier.com/rules](https://docs.zerotier.com/rules); searches |
| **Radmin VPN** | "create virtual local networks ... Play your favourite LAN games with your friends over the Internet", Windows 11/10/8/7 only, free, "does not limit the number of gamers" | layer 2 (secondary source), not stated officially | Windows only, closed source, central servers | W: [radmin-vpn.com](https://www.radmin-vpn.com/) |
| **Hamachi** | LogMeIn hosted VPN | IPXWrapper has a 0.3.2 "workaround for Hamachi bug", so it was used this way | free tier 5 members per network | W: GoTo support table |
| **Tailscale** | WireGuard mesh, layer 3 | **none**: "no support for broadcast or multicast due to the point-to-point nature of the connections" (Tailscale forum); IPX discovery cannot work, direct IP over 100.x untested | node sharing exists: an invite shares one machine with a user on another tailnet, "A shared machine can receive incoming connections [...] but cannot start connections", recipient must be Owner/Admin/IT admin of their own tailnet; **Funnel is TCP/TLS only on ports 443/8443/10000**, so it cannot carry a UDP game; peer relays are tailnet-internal and "experimental" | W: [forum](https://forum.tailscale.com/t/broadcast-multicast-support/156), [sharing](https://tailscale.com/kb/1084/sharing), [Funnel](https://tailscale.com/kb/1223/funnel), [peer relay](https://tailscale.com/docs/features/peer-relay.md) |

Our own data agrees: IPX worked with Tailscale merely present (R: MULTIPLAYER.md s.6), and broke when Tailscale
*routed* the LAN (R: NITRO-MP-DESIGN s.0.5.15). The GOG forum of 2010-11 is the Tunngle era: "Use tunngle! It's faster
than hamachi", five players over Tunngle on Gold, and "We could not get Nitro Pack working using ANY method, but we
were able to play I'76 Gold" (W: [GOG thread](https://www.gog.com/forum/interstate_series/help_us_with_the_multiplayer_gog)).
Tunngle and Evolve are shut down (W: Steam discussion via search). The VOGONS I'76 thread offers only "Hamachi ...
go LAN like they were next to each other" and a poster who gave up over connection quality (W: [VOGONS](https://www.vogons.org/viewtopic.php?p=146895)).

### 2.4 Lobbies and launchers

GameRanger: no Interstate title (R: COMMUNITY-RESOURCES 2026-10-06; the site's certificate had expired today, not
re-checked). Kali: alive, free, I'76 status **unverified** (1.3). NukemNet: no I'76 (2.2). The live I'76 scene is Nitro
+ bz911 / interstate76.com's ANet servers + Peelar's UPnP DLLs, arranged on the UltraFunk Discord; "I '76 games rarely
run" (Local Ditch FAQ, W). I26 (0.4.0, 2026-10-11) lists its own games on the same ANet servers: "Internet games
without port forwarding: games are listed on the community anet servers and joined through them (UDP hole punching; a
strict symmetric NAT still needs a forwarded port)"; 0.8.0 (2026-10-24, protocol 16) adds "interstate76.com's anet
servers (Glenrio and Interstate76.com), beside BZ911 and Iondriver" to its address book (W: [I26 releases](https://github.com/vahokif/I26/releases)).

## 3. MODERN: how current indie / retro multiplayer handles NAT and trust

### 3.1 NAT

- **Hole punching**: both peers send UDP to each other's public address at once after a rendezvous server exchanged
  the addresses; measured success "82% (310 of 380 data points)" for UDP, 64 % for TCP (W: Ford, Srisuresh, Kegel,
  ["Peer-to-Peer Communication Across Network Address Translators"](https://www.usenix.org/event/usenix05/tech/general/full_papers/ford/ford_html/), USENIX 2005; the third author is ANet's Dan Kegel).
  Fails on symmetric NATs and carrier-grade NAT; hence every production system keeps a **relay (TURN) fallback**.
- **ICE / STUN / TURN** as a library: **libjuice** (C, no dependencies, MPL-2.0, STUN RFC 8489 + TURN RFC 8656 client
  and a lightweight server, UDP only, one component per session) (W: [libjuice](https://github.com/paullouisageneau/libjuice)).
- **Relay networks.** *Steam Datagram Relay*: "Valve's virtual private gaming network", "IP addresses are never
  revealed", "authenticated, encrypted, and rate-limited"; requires the game to ship on Steam, a game coordinator and an
  AppID; "the opensource code does not support accessing the relay network" (W: [SDR docs](https://partner.steamgames.com/doc/features/multiplayer/steamdatagramrelay)).
  *GameNetworkingSockets* (BSD-3): reliable/unreliable messages, AES-GCM-256, "NAT traversal through Google WebRTC's
  ICE implementation" with "Plug in your own signaling service" (W: [GNS](https://github.com/ValveSoftware/GameNetworkingSockets)).
  *Epic Online Services P2P*: "EOS will first attempt a NAT punch-through and then automatically fall back to relayed
  communication"; free relays; each player needs an EOS identity; distant relays possible (W: [Edgegap analysis](https://edgegap.com/blog/can-epic-online-services-eos-relays-allow-for-dedicated-server-or-authoritative-server), [coherence docs](https://docs.coherence.io/hosting/client-hosting/implementing-client-hosting/epic-online-services-eos-relay); Epic's own doc page returned empty today, **secondary sources**).
  *Photon Cloud*: free tier "20 Connected Users at the Same Time", "For Development Only"; 100 CCU $95 once (W: [pricing](https://www.photonengine.com/realtime/pricing)).
  *Tailscale peer relays / Funnel*: see 2.3; not a public-game relay.
- **What I26 does, concretely** (S: `I76.Net.Anet\HolePunch.cs`, `AnetHost.cs`, `AnetJoiner.cs`, 0.6.0 decompiled,
  analysis only): the host registers its session on the ANet lobby (species 18726) with its *reported* private address;
  the joiner sends the lobby a REQUEST_OPEN; the lobby relays it to the host with the joiner's address as the server
  *seen* it (public) and as *reported* (private); the host bursts 11-byte `I26P` HostProbe packets at both for 10 s
  every 0.2 s (`Targets(seen, reported)`), the joiner sends JoinerProbe to the session master's address(es) for 10 s
  (`PunchTime`), the first probe to land answers and the game connection follows. **The 1998 ANet lobby is the
  signalling server**; no extra service. "punch failed" names "whose router stopped it" (0.5.0, W).

### 3.2 Simulation models

- **State replication, host-authoritative** (most shooters): clients send inputs, the server owns the world. ANet
  games are peer-to-peer: I'76 mirrors cars with 'AT' records (2 cars per 208 B packet) and the host owns kills / AI
  (R: NITRO-MP-DESIGN s.1.3, our AI pool). Cheating = lying about your own car; the host cannot verify positions.
- **Deterministic lockstep** sends only inputs and needs a bit-identical simulation on every machine; **rollback**
  (GGPO, MIT: "input prediction and speculative execution", W: [GGPO](https://github.com/pond3r/ggpo)) predicts remote
  inputs and resimulates. Both need determinism, which "took longer than expected" in every case study (W: search).
  I26 is deterministic (`StateHash`, saved-state host migration) but still "Hits and damage are still the server's"
  with client-side prediction of your own car (W: I26 0.5.0 notes). **The original exe is not deterministic across
  machines in any way we have measured** (R: nothing in our records tests it), so rollback is not on our table; our
  model is the stock one.

### 3.3 Trust for a small community

- **Server authority** where lying pays: "ask whether a player could gain an advantage by lying. If so, that logic
  belongs on the server" (W: [AccelByte](https://accelbyte.io/blog/server-authoritative-logic-to-prevent-cheating));
  "anti-cheat can make cheating harder, but it cannot prevent it entirely" (W: [Photon FAQ](https://doc.photonengine.com/bolt/current/troubleshooting/authoritative-server-faq)).
  In I'76 the host already recomputes the car CRC from its own files and drops mismatches ("has tried to join with a
  hacked vehicle!"), validates the budget rule, and checks mission name + CRC-32 (R: MULTIPLAYER.md s.4, s.8). I26
  kept "The original's strict car checks" and has `--restrict`, `--password`, `--invite-only`, kick (W). Positions,
  hits and damage in the stock game are reported by the shooter / victim and cannot be verified without a rewrite;
  accept that for a friends-of-friends community.
- **Identity**: passwords on the session (Nitro has 'RE' with password, R: NITRO-MP-DESIGN s.1.1; Gold **unverified**),
  invite codes = a secret room id on the relay, friend lists need an account service (Nakama, Apache-2, "matchmaking,
  leaderboards, chat, and social features", self-hosted on Postgres/CockroachDB, W: [Nakama](https://github.com/heroiclabs/nakama)).
- **IP exposure**: any P2P or direct-IP game shows every player every other player's address; a relay hides them
  (SDR's selling point). For strangers that matters more than cheating.
- **Build identity**: every I26 release prints its protocol number and "everyone in a game needs this version" (W);
  our packs should show a pack id on the host form (R: PRIOR-ART-I26 s.3.4, still open).

### 3.4 Open-source building blocks (licences as read today)

| block | what | licence | source |
|---|---|---|---|
| anet 0.10 | the game's own library + lobby server + master server | LGPL-2.1 | [Nielk1/anet](https://github.com/Nielk1/anet) |
| IPXWrapper | IPX over UDP for Win32, DOSBox encapsulation | GPL-2.0 | [solemnwarning/ipxwrapper](https://github.com/solemnwarning/ipxwrapper) |
| ipxbox | hosted DOSBox-protocol IPX server, bridging, PPTP, keepalives | GPL-2.0 | [fragglet/ipxbox](https://github.com/fragglet/ipxbox) |
| DOSBox-X / Staging `ipxnet` | the same server inside the emulator | GPL-2.0 | dosbox-x.com |
| GameNetworkingSockets | reliable UDP, encryption, ICE P2P with your signalling | BSD-3 | ValveSoftware |
| libjuice | ICE/STUN/TURN client + small server, C, no deps | MPL-2.0 | paullouisageneau |
| ENet | reliable UDP, small C | MIT | [lsalzman/enet](https://github.com/lsalzman/enet) |
| yojimbo | client/server UDP, connect tokens, encryption, "100 players or less" | BSD-3 | [mas-bandwidth/yojimbo](https://github.com/mas-bandwidth/yojimbo) |
| GGPO | rollback SDK | MIT | pond3r/ggpo |
| Nakama | accounts, friends, matchmaking, chat backend | Apache-2 | heroiclabs |
| libzt (ZeroTier SDK) | embed a ZeroTier node in an app | **BSL-1.1** (not OSI; free for non-commercial) | zerotier/libzt |
| Tailscale | mesh VPN, node sharing | client BSD-3; coordination server proprietary (Headscale exists) | tailscale.com |
| I26 | Godot/C# reimplementation incl. anet lobby client + punch | **no licence stated; source not public** (0.8.0, 2026-10-24) | vahokif/I26 |

## 4. FOR US: the option space

Context the options share: the proxy sits between the shell / exe and ANet (dpOpen / dpReceive / list hooks, its own
species, host-side AI and co-op state) and between the game and IPXWrapper (instance letters, `I76_IPX_PIN`); every
machine runs IPXWrapper (Windows native; Macs under Wine, measured; the Deck under Proton). Effort: **S** an evening,
**M** days, **L** weeks of lane time. "Trust" = who can get into a game and what they learn.

### (a) VPN + invite: works now, trusted people only

- **What**: a layer-2 virtual LAN that carries IPv4 broadcast (ZeroTier network, or Radmin VPN on Windows-only
  groups); nothing in the game or pack changes; HOST > IPX, JOIN > IPX as on the LAN.
- **NAT**: handled by the VPN (its own traversal + relays). **Trust**: a member is a LAN neighbour of every other
  member's PC; ZeroTier flow rules can cut that down to UDP 54792 + the per-process ports (IPXWrapper's random source
  ports make an exact rule hard; **unverified**), Radmin cannot. Tailscale is not an option for IPX (no broadcast); a
  Tailscale node share + Gold direct IP over 100.x is conceivable and untested.
- **Effort S**, risk low; the known-unknown is latency through a VPN relay when direct traversal fails.
- **Experiment**: one ZeroTier network; PC on the home LAN + the laptop on a phone hotspot (a real second NAT);
  IPXWrapper primary interface = the ZeroTier adapter on both; host The Crater, join, hold W 6 s, read the host's
  position table (the 2026-10-06 method). Then the same with a Mac under Wine. n 2 each. Record RTT (`zerotier-cli
  peers`) beside the join result.

### (b) Direct IP on Gold (UDP 21157 + port forwarding)

- **What**: the stock INTERNET route with GOG's patched `WINET.DLL`: host adds a server entry with **its own public
  IP**, hosts INTERNET; joiners add the **host's public IP**. Host forwards **UDP 21157** (Gold's WINET has no UPnP;
  that is Nitro's `WINETS2`). Nitro: not available ("guaranteed to not work", Peelar).
- **Limits** (all from WINET's code, R: lab s.2): one host per public IP; no joiner on the host's LAN; port fixed; the
  host's "own address" discovery needs its LAN broadcast echoed back (fine on a normal LAN). Peelar tested < 1.083,
  GOG is 1.083 (R). **Trust**: anybody with IP:21157 who passes the car check is in; no password known; every player
  sees the host's IP and the host sees theirs. Fine for a named friend, not for strangers.
- **Effort S** (an owner test with one remote friend), risk: it may just not work on 1.083, which is itself the answer.
- **Experiment**: PC hosts (router forwards UDP 21157 to the PC; confirm with `Get-NetUDPEndpoint`), the laptop joins
  from a phone hotspot (not from the LAN: Peelar's exclusion). Expect: the joiner's list shows the host within the
  2 s enumeration; then join, position table. n 2, then swap roles once (laptop hosting through the hotspot's NAT
  will likely fail: that is the NAT finding, not a bug).

### (c) IPX-over-UDP relay (a hosted DOSBox-protocol server) + IPXWrapper master

- **What**: run **ipxbox** (or dosbox-x `ipxnet startserver`) on a small VPS or on the PC with one forwarded UDP port;
  every player's `ipxwrapper.ini` gets `dosbox server address` / `dosbox server port` (two lines, per game folder; the
  pack can ship it); IPXWrapper rebuilt from master (e7e9883) so WIPX hears its own start-up broadcast. The game then
  sees one virtual IPX LAN: HOST > IPX / JOIN > IPX unchanged, Gold **and** Nitro, ARENA+ included, Macs through the
  same DLLs under Wine (DOSBox mode under Wine **untested**).
- **NAT**: only the server port is forwarded; players need nothing (DOSBox protocol; ipxbox keepalives hold the NAT
  mapping). No hole punching needed because everything is relayed; cost = one extra hop of latency and the server's
  upload (ANet traffic is small: 208 B packets; **unmeasured** per player per second).
- **Trust**: the server address + port is the invite; ipxbox has no password (**unverified**), so rotate the port per
  game night or front it with a firewall allowlist / WireGuard for regulars; everyone on the server shares one IPX
  LAN (one game at a time per server, or one server per room); players see only the server's IP, not each other's
  (the relay hides addresses). Car and mission checks apply as today.
- **Effort S for the spike, M to productise** (build + ship a patched `ipxwrapper.dll` in the pack = GPL-2 obligations:
  source and patch published, which the repo already does for its own GPL dependencies; a VPS to run). Risk: the
  master fix may not be the only thing WIPX needs; IPXWrapper's DOSBox node assignment per process (lab s.8.4 hoped it
  "would give each its own node") is a bonus for two copies on one PC.
- **Experiment (first)**: build IPXWrapper master with the lab's w64devkit; on the PC run dosbox-x
  `ipxnet startserver 19900` as on 2026-10-20 and repeat the exact failed cell with the two lab copies and the two-line
  ini (n 2). Pass = HOST reaches the host form and the joiner lists the session. Then: the server on a VPS (or the PC
  with the port forwarded), the laptop joins from a phone hotspot; then a Mac. Keep `ipxwrapper.log` (debug) from
  every side.

### (d) A proper relay with hole punching, invite codes and checks

- **What**: our own small service, in two possible shapes. **D1 (I26's shape, Nitro)**: the proxy's `nmp_lobby_subscribe`
  written against anet 0.10 so ARENA+ hosts list on bz911 under species 0x7676, plus a punch under the proxy's control
  (REQUEST_OPEN gives the host the joiner's public and private address; probes both ways for 10 s; the stock ANet 2
  socket then talks directly); the lobby is the signalling server, no server of ours. Needs the owner-approved live-lobby
  step and a transport that is UDP/IP (`WINETS2`), i.e. Nitro INTERNET, not IPX. **D2 (transport shim, Gold + Nitro)**:
  a local daemon that presents a DOSBox-protocol server on 127.0.0.1 to IPXWrapper and upstream does rendezvous +
  punch + relay fallback (libjuice or GNS-ICE; our own tiny signalling service with invite codes); the game and
  IPXWrapper stay untouched. Invite code = room; the daemon can enforce pack id, car-file hashes and a kick list before
  any packet reaches the game.
- **NAT**: punch for most pairs, relay for the rest. **Trust**: invite codes, per-room allowlists, hidden IPs when
  relayed; the game-level checks stay the game's.
- **Effort L** (D2: daemon + signalling server + Wine/Deck testing + ops; D1: anet client in the proxy + owner-approved
  lobby test + punch). Risk: we become a service operator; D1 depends on a lobby we do not run.
- **Experiment**: D1: a one-day read of anet 0.10's `dptab` subscription and REQUEST_OPEN against the proxy's
  `nmp_lobby_subscribe` stub, output = a sequence diagram and a go / no-go. D2: a 200-line prototype that fakes a DOSBox
  server on loopback and forwards to a remote ipxbox: if IPXWrapper master is happy with a loopback DOSBox server, D2's
  hard part is only the punch.

### (e) Joining I26's netcode later

- I26's protocol is its own (LiteNetLib, protocol 16 at 0.8.0, changes weekly); the original exe cannot speak it, so
  "joining" means playing I26 instead of the original, or offering I26's `i26-server` our content (co-op scenes exist
  there since 0.8.0: `i26-server --coop MISSION`). Source still not public, no licence (W: releases). **Effort 0 for
  now**; action: watch releases, and offer vahokif the tick measurements as PRIOR-ART-I26 s.7 drafts. Not a route for
  *our* exe.

### Summary table

| option | works for | NAT work for players | trust | effort | risk | state |
|---|---|---|---|---|---|---|
| (a) ZeroTier / Radmin virtual LAN + IPXWrapper | Gold, Nitro, ARENA+, Macs | none (VPN does it) | members = LAN neighbours; friends only | S | low; VPN relay latency | ZeroTier/Radmin **untested** here; Tailscale ruled out for IPX |
| (b) Gold direct IP, UDP 21157 | Gold only | host forwards 21157; one host per IP; no LAN joiner | IP known = in; IPs visible | S | may fail on 1.083 | **untested**; our LAN test was the excluded case |
| (c) DOSBox-protocol relay + IPXWrapper master | Gold, Nitro, ARENA+, Macs (Wine untested) | none; server forwards one port | server:port = invite; IPs hidden by relay; no password | S spike / M ship | master fix may not suffice | failed on 0.7.2 (n 2); **fix exists in master** |
| (d) relay + punch + invite codes (D1 lobby / D2 shim) | D1 Nitro INTERNET; D2 all | none | codes, allowlists, hidden IPs, pre-game checks | L | we run a service; D1 lobby not ours | design only |
| (e) I26 netcode | I26, not our exe | none | theirs | 0 | not our game | watch |
| stock Nitro INTERNET (community route) | Nitro, species 604 (ARENA+ hidden until lobby step) | host's router UPnP (Peelar DLLs) | lobby password; IPs visible | 0 | ARENA+ species invisible to stock | works for the community; our ARENA+ lobby test owner-approved only |

### Recommendation

1. **Spike (c) first**, this week: build IPXWrapper master, rerun the 2026-10-20 DOSBox cell. It is the cheapest
   possible unlock (two ini lines per player, one hosted port, no game change), covers Gold, Nitro and ARENA+ at once,
   and its failure mode is already understood. If it passes on one PC, put ipxbox on a VPS and bring the laptop in
   over a hotspot. If it fails, read `ipxwrapper.log` for which packet WIPX is still missing before anything else.
2. **(b) as an owner test** with one remote friend who has Gold: zero engineering, and it settles a four-week-old
   "untested" row either way. Gold only.
3. **(a) for the people we already trust**: a ZeroTier network for the family's laptops away from home; measure once.
4. **(d) only if (c) proves the relay shape and a community shows up**: start with D2 (the loopback DOSBox shim), because
   it keeps the game and IPXWrapper untouched and turns the relay into an invite-code service; D1 waits on the
   owner-approved lobby step and on writing the anet client.
5. **(e)**: watch, contribute measurements, do not build toward it.

## 5. Unverified claims collected

- Peelar's "too old to use with the Activision Game Servers" for base I'76: not reproduced; may be address format
  rather than protocol version.
- Kali with I'76 on Windows 10/11; Kali over IPXWrapper.
- Whether Gold's host form has any password; what a stock Gold joiner shows when a session is full / password-protected.
- ZeroTier broadcast behaviour (official doc not fetched; secondary sources say supported) and whether flow rules can
  confine IPXWrapper's random source ports.
- IPXWrapper master's loopback fix is *sufficient* for WIPX in DOSBox mode (the self-echo was the first failure, not
  necessarily the last); DOSBox mode under Wine.
- ipxbox has no authentication (HOWTO not fetched, 503).
- EOS P2P details are from secondary sources (Epic's page returned empty).
- GameRanger "no Interstate title" was checked 2026-10-06, not today (certificate expired).
- UCyborg's thread 1508 and Lightfoot's thread 1443 quoted from COMMUNITY-RESOURCES / MULTIPLAYER.md; Wayback could
  not be fetched today and forums.interstate76.com did not resolve.
- Bandwidth per player of an ANet session (needed to size a relay); never measured.

## 6. Sources

Project: `docs/MULTIPLAYER.md`, `docs/records/NITRO-MP-DESIGN-2026-10-21.md` (s.0.5.3, 0.5.8, 0.5.15-16, 1.1-1.3),
`docs/records/MP-OVERNIGHT-2026-10-20.md` s.5, `docs/OPEN-FEATURES-2026-10-24.md` s.5, `docs/PRIOR-ART-I26-2026-10-21.md`,
`docs/COMMUNITY-RESOURCES.md` s.3a, `docs/records/NITRO-VS-RETAIL-2026-10-20.md`; lab `docs/MULTIPLAYER-LOCAL-TEST.md`
s.2, 8.1-8.4; local source `i76-uncap-lab\refs\anet\anet-master` (`src/doc/arch.htm`, `doc/server.htm`,
`src/linux/server/README2.txt`, `src/win/winets/wstcpdll.c`), `i76-uncap-lab\refs\ipxwrapper`,
`Downloads\i26-0.6.0\decompiled\I76.Net\I76.Net.Anet\{HolePunch,AnetHost,AnetJoiner}.cs` (analysis only, nothing copied).

Web (read 2026-10-25):
[kegel.com/anet](https://kegel.com/anet/) · [Nielk1/anet](https://github.com/Nielk1/anet) · [anet master list](http://www.kegel.com/anet/master/servers.txt) ·
[Peelar: netcode patches](https://inbetweennames.net/projects/interstate76anet/) · [Peelar: RE blog 2021](https://inbetweennames.net/blog/2021-05-04-interstate-76-reverse-engineering-efforts-the-story-so-far/) ·
[Local Ditch FAQ](https://www.localditch.com/interstate-76/faq.html) · [GOG forum: help us with the multiplayer](https://www.gog.com/forum/interstate_series/help_us_with_the_multiplayer_gog) ·
[VOGONS I'76 online thread](https://www.vogons.org/viewtopic.php?p=146895) · [PCGamingWiki AiO patch](https://community.pcgamingwiki.com/files/file/1349-interstate-76-nitro-pack-aio-patch/) ·
[Kali (Wikipedia)](https://en.wikipedia.org/wiki/Kali_(software)) · [kali.doc 1995](https://discmaster.textfiles.com/view/10593/Netware%20Super%20Library.iso/inet_tcp/kali10wb/kali.doc) ·
[IPXWrapper site](https://www.solemnwarning.net/ipxwrapper/) · [IPXWrapper repo](https://github.com/solemnwarning/ipxwrapper) · [changes.txt](https://raw.githubusercontent.com/solemnwarning/ipxwrapper/master/changes.txt) ·
[ipxwrapper.ini.example](https://raw.githubusercontent.com/solemnwarning/ipxwrapper/master/ipxwrapper.ini.example) · [commit e7e9883](https://github.com/solemnwarning/ipxwrapper/commit/e7e9883551bbb582336a7650791b9473a2dec0a8) ·
[issue #22](https://github.com/solemnwarning/ipxwrapper/issues/22) · [DOSBox wiki IPX](https://dosbox.com/wiki/IPX) · [DOSBox Staging IPX](https://www.dosbox-staging.org/0.83/manual/networking/ipx/) ·
[dosbox-x ipxserver.cpp](https://raw.githubusercontent.com/joncampbell123/dosbox-x/master/src/hardware/ipxserver.cpp) · [fragglet/ipxbox](https://github.com/fragglet/ipxbox) · [NukemNet](https://nukemnet.com/) ·
[ZeroTier rules](https://docs.zerotier.com/rules) · [Radmin VPN](https://www.radmin-vpn.com/) · [Tailscale broadcast forum](https://forum.tailscale.com/t/broadcast-multicast-support/156) ·
[Tailscale sharing](https://tailscale.com/kb/1084/sharing) · [Tailscale Funnel](https://tailscale.com/kb/1223/funnel) · [Tailscale peer relays](https://tailscale.com/docs/features/peer-relay.md) ·
[Ford/Srisuresh/Kegel 2005](https://www.usenix.org/event/usenix05/tech/general/full_papers/ford/ford_html/) · [libjuice](https://github.com/paullouisageneau/libjuice) ·
[Steam Datagram Relay](https://partner.steamgames.com/doc/features/multiplayer/steamdatagramrelay) · [GameNetworkingSockets](https://github.com/ValveSoftware/GameNetworkingSockets) ·
[Edgegap on EOS relays](https://edgegap.com/blog/can-epic-online-services-eos-relays-allow-for-dedicated-server-or-authoritative-server) · [Photon pricing](https://www.photonengine.com/realtime/pricing) ·
[Nakama](https://github.com/heroiclabs/nakama) · [ENet](https://github.com/lsalzman/enet) · [yojimbo](https://github.com/mas-bandwidth/yojimbo) · [GGPO](https://github.com/pond3r/ggpo) ·
[AccelByte: server-authoritative logic](https://accelbyte.io/blog/server-authoritative-logic-to-prevent-cheating) · [Photon: authoritative server FAQ](https://doc.photonengine.com/bolt/current/troubleshooting/authoritative-server-faq) ·
[I26 releases](https://github.com/vahokif/I26/releases) · [I26 v0.4.0](https://github.com/vahokif/I26/releases/tag/v0.4.0) · [I26 v0.5.0](https://github.com/vahokif/I26/releases/tag/v0.5.0).
