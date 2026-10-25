# Internet play through a DOSBox-protocol IPX relay: spike (c), 2026-10-25

Owner, 2026-10-25: *"Sure, you can start (1)."* = option (c) of
[../research/INTERNET-PLAY-SPIKE-2026-10-25.md](../research/INTERNET-PLAY-SPIKE-2026-10-25.md): IPXWrapper from upstream master
(the loopback fix e7e9883) in DOSBox mode, every player pointed at one DOSBox-protocol relay.

Everything below was measured today unless marked. n = sessions per cell. Lab: `<lab>\tools\relay-spike\` (lab commit
7e4c113 and later), evidence `<lab>\captures\relay-spike-20261025\<tag>\`.

## Verdict

**The 2026-10-20 failure is fixed by IPXWrapper master, and the relay shape works for Gold and Nitro, Windows and Mac (Wine).**

- With master, WIPX's start-up self-echo is delivered (`Delivering 4 byte payload ... relaying to local port` in every IPXWrapper log), HOST
  reaches the host form, BROADCAST opens the session, and a joiner on another machine lists it and joins.
- Same laptop, same copy, same relay, **0.7.2 DLLs swapped in: HOST never reaches the host form** (the 2026-10-20 symptom, n 1). Master: n 4.
- Gold: laptop host + MacBook joiner, **3 of 3 sessions joined**, both copies hold both cars at the same coordinates (0.0 m, 46 pairs parked).
- Nitro: laptop host + MacBook joiner, **2 of 2 joined** (state 5, net 1, 2 players, held 145 s, 0 CRASH).
- **Every row here is LAN-only**: the relay ran on the MacBook on the home LAN, every peer on <LAN subnet>. No NAT was crossed. The phone-hotspot
  test needs the owner (section 6).
- The exact desktop cell (two lab copies + DOSBox Staging on this PC) was **not run**: it sat in the desktop `.fps-queue` from 05:53 to 07:25
  behind six lanes, and the coordinator moved the peers to the laptop and the MacBook. The desktop's lab `dosbox.exe` also carries an inbound
  **Block** rule (the 2026-10-20 firewall prompt was dismissed), so a remote peer could not have reached a relay there anyway (section 4).

## 1. Build: IPXWrapper master

- Fresh clone of github.com/solemnwarning/ipxwrapper, HEAD **dbe9a81** ("respond to ping"). It contains **e7e9883** ("Fix delivery of
  loopback packets", 2026-08-01; the commit exists and its diff is as the spike doc described) and 3 later commits. 8 commits past the 0.7.2 tag.
- Review of `git diff ipxwrapper-0.7.2..dbe9a81` outside the tests (the clone was treated as untrusted source and read before building):
  - `winsock.c`: in DOSBox mode a packet to our own net/node, and a copy of every successful broadcast, is delivered locally
    (`deliver_packet`). This is the fix for our 2026-10-20 failure.
  - `router.c`: remembers the private UDP port and drops packets that come back from our own port on a local address (no double delivery
    in plain UDP mode); answers a DOSBox server's ping (echo socket, broadcast node) with an ack (ipxbox pings).
  - `interface.c`: `ipv4_address_is_local`. Makefile: version "git", CFLAGS from the environment, ipxconfig C++ -> C (the GUI tool only).
  - No new network endpoints, no process creation, no new file writes. Nothing suspicious.
- Toolchain: the lab's w64devkit (i686 gcc 16.2.0, make, windres) plus **NASM 2.16.03** (official zip; the stub DLLs need it; w64devkit has
  no nasm). Warnings only. The 0.7.2 tag no longer builds with this gcc (`select` signature; master's 3e5d2cb fixes it), so there is no
  same-toolchain 0.7.2 control; the control is the 2026-10-20 run with the released 0.7.2 binaries.
- Outputs (sha256; full table, instance-letter variants and build line in lab `builds\ipxwrapper-master-20261025\README.md`):

| file | sha256 | md5 (8) |
|---|---|---|
| ipxwrapper.dll | 1f88a7975d044f8bab40fc5ff02b0a249fdd7e55b72bd92f6995834e454edd63 | 42d83f38 |
| wsock32.dll | 508f9c23155887f961649a8db2f6f3202f2d1de1cbcf1ed1552befaa16691b53 | f7d5ee0f |
| mswsock.dll | ac4606209c7d9961161efea67d6bd7ba47fa697079c4d73d1b23623e6f49706c | 0f8c7d61 |

- Two copies on one PC still need their own IPXWrapper instance (the socket mutex `ipxwrapper_socket_%hu` is session-wide): the same
  2-byte patch as lab MULTIPLAYER-LOCAL-TEST 8.4, new letters R / S (Gold twins) and T / U (Nitro twins), used by no other copy (census of
  every ipxwrapper.dll in the lab, <archive> and Games\I76). The Mac and the laptop run the unpatched master DLL.
- The whole player-side change is three DLLs plus a three-line `ipxwrapper.ini` beside the exe:

```
dosbox server address = <relay host>
dosbox server port = 19900
logging = debug          (spike only)
```

## 2. The relay used

- **pyrelay.py** (lab `tools\relay-spike\`, Python standard library, ~100 lines), written for this spike because no ipxbox build exists here
  (Go is not installed on any machine; ipxbox ships no binaries). It speaks the DOSBox protocol as dosbox-x `ipxserver.cpp` does:
  registration = a packet to socket 2 with destination host 0, the node is the client's IP:port, broadcast goes to everyone except the sender,
  unicast by node. Differences: the sender is identified by its UDP source address (DOSBox trusts the header's src field), packets from
  unregistered addresses are dropped, an optional CIDR allowlist, an idle timeout, and a stats line every 10 s.
- Checked against DOSBox Staging 0.82.2 `ipxnet startserver 19900` on this PC with a protocol probe (`ping.py`: register, then echo to our
  own node through the server): both answer the same way (20 of 20 echoes; 0.31 ms Staging, 0.21 ms pyrelay on loopback).
- Where it ran: **the MacBook** (<LAN-IP>, macOS firewall off), a third box like a VPS would be. The desktop was not used as the relay
  host: no console slot, and the inbound Block rule above.
- The 2026-10-20 launch line for Staging was also broken as written in the harness (`-c ipxnet startserver 19900` unquoted splits into
  three arguments; Staging then never opens the port). The record of that day still holds: IPXWrapper logged `Connected to DOSBox server`.

## 3. Cells (all on the home LAN)

Peers: the laptop (the laptop bench, <LAN-IP> on Wi-Fi, console locked for the Nitro rows and unlocked for Gold, its `.fps-lock`
taken per boot) and the MacBook (nobody at it, null audio, its own app clones). Every boot: movies skipped (`I76_SKIP_MOVIES` /
`NB_SKIP_MOVIES`), no FFB interposer (direct boot, `I76_FFB_OFF=1` on Gold), muted (`I76_MUTE` + the pid watcher on Windows, null
audio on the Mac). Only processes these scripts started were stopped.

| cell | host | joiner | relay | result | n | evidence (`captures\relay-spike-20261025\`) |
|---|---|---|---|---|---|---|
| Nitro host alone, DOSBox mode under Wine | MacBook Nitro clone | - | MacBook, loopback | **pass**: `Connected to DOSBox server`, self-echo delivered, BROADCAST, `dpOpen species 025c 'Gumball Rally'`, hosting 75 s | 1 | `m0-mac-host` |
| Nitro, Windows host, Mac joiner | laptop `relay-nitro` (nitro-b twin, dgVoodoo 2.87.5) | MacBook Nitro clone | MacBook | **pass**: joiner listed `'Evening Stroll' species 025c players 1/6`, joined, both sides state 5 net 1 players 2 for 145 s, 0 CRASH | 2 | `x0-r2`, `x0-r3` |
| Nitro, allowlist refuses the host | laptop | - | MacBook, `--allow 127.0.0.0/8` | **refused cleanly**: 4 registrations refused, IPXWrapper never connects, the game shows "Unable to create an IPX connection..." | 1 | `x0-deny` |
| Gold host alone | laptop `relay-gold` | - | MacBook | **pass**: host form, BROADCAST, in mission (net 1, me = host) | 1 | `laptop-gl1` |
| Gold, Windows host, Mac joiner | laptop `relay-gold` | MacBook Gold clone | MacBook | **pass**: JOIN GAME on the first try, both tables hold ids 3 + 6 at identical coordinates, held 110-170 s, 0 CRASH | 3 | `g-r1`, `g-d1`, `g-t1` |
| **control: Gold host with IPXWrapper 0.7.2** | laptop, same copy, 0.7.2 DLLs (06a01d0f) | - | MacBook | **fails** like 2026-10-20: `Connected to DOSBox server`, then no self-echo delivery (no `Delivering 4 byte` line), host form never reached | 1 | `laptop-g072` |
| control: Gold on plain IPXWrapper UDP (LAN mode, no relay) | laptop | MacBook Gold clone | - | **inconclusive**: the Mac heard the laptop (49 packets received) but JOIN GAME did not get in (state 6, net 0). Not isolated: the clone's new bundle id may need macOS Local Network permission, or the stock port 54792 listed another LAN session first | 1 | `g-lan-t1` |

Builds on the peers: Gold `relay-gold` = the desktop twin `relay-f-20261025` (= game-mpo-d: LAN exe 6319abf7, i76shell a300db63, lab proxy
4519db95 with `I76_LAB_SHELLCLICK`) + dgVoodoo 2.87.5 + IPXWrapper master; the Mac Gold clone = the Mac's own Gold app (same exe and shell)
with the same lab proxy. Nitro = nitro.exe 28b8ae27, nitshell f804f50d, instrument nmpdrv 8d298467 chained to the final proxy 3f27c797
(the nitro-rel settings), stock Combat session, n01.

## 4. What a hosted relay needs

- **Ports**: one UDP port on the relay host (19900 here; DOSBox's default is 213), reachable from the internet. At home that means a router
  port forward to the relay box (not done; router settings untouched). On a VPS: open that one UDP port in its firewall. Players need no
  forwarding: every packet is a reply on the flow they opened (the desktop's own blocked inbound rule did not stop replies to its outbound
  probe). On Windows a relay host also needs an inbound allow rule for the relay program; the desktop's lab `dosbox.exe` and Python both carry
  inbound UDP **Block** rules today, so neither could serve a remote player without the owner changing them.
- **Player side**: three DLLs (`ipxwrapper.dll`, `wsock32.dll`, `mswsock.dll`) from master and a two-line `ipxwrapper.ini`
  (`dosbox server address`, `dosbox server port`). HOST > IPX / JOIN > IPX unchanged in both games. Two copies on one PC still need two
  instance letters.
- **Traffic** (pyrelay stats): 2 players, ~10 packets/s and ~1.0 KB/s up per player (Gold host 1420 packets / 142 KB in 140 s; Nitro host 1814 /
  181 KB in 201 s); each player receives about (players - 1) x that. Relay forwarding cost 0.1 ms per packet in Python on the MacBook.
  Eight players would be ~8 KB/s down per player and ~60 KB/s out of the relay. Any VPS or home uplink carries it.
- **Auth = the address**: the invite is `relay host:port`. ipxbox (read from its source today): **no client authentication or allowlist**; the
  only password is `--uplink_password` for server-to-server uplinks (challenge-response); NetBIOS forwarding is off by default;
  `--client_timeout` 10 min; syslog logging for public servers; keepalive pings for NAT (IPXWrapper master answers them, commit dbe9a81).
  DOSBox Staging / dosbox-x: none of those. pyrelay: a CIDR allowlist (measured above) and source-address binding.
- **Correction to the research doc ("players see only the server's IP")**: under the DOSBox protocol a player's IPX node *is* his public
  IP:port as the relay saw it (`node c0:a8:01:8d:...` = <LAN-IP>), and every packet carries the sender's node. Every player in a session
  can read every other player's address. Hiding it needs a relay that rewrites nodes (pyrelay could assign opaque nodes; not done).
- **Trust gaps of the stock protocol**: no auth, and dosbox-x routes by the header's source field, so any registered client can spoof
  another's node. Anyone with the address can join the IPX LAN; one game per relay port.

## 5. Latency

| measure | value | n |
|---|---|---|
| relay round trip, PC -> MacBook relay -> PC (wired -> Wi-Fi) | median 2.60 ms (2.32-3.83) | 50 |
| relay round trip, laptop -> MacBook relay -> laptop (Wi-Fi both) | median 4.53 ms (3.99-6.51) | 50 |
| parked position agreement, laptop host vs Mac joiner (both cars) | **0.0 m** (max over 46 pairs) | 1 session |
| same, LAN run of 2026-10-20 (one PC, IPXWrapper UDP) | 0.0 m (MP-OVERNIGHT s.2) | 3 |
| host teleported 40 m (trainer TELEPORT), first Mac sample showing the new position | upper bound median 78 ms after the ack, range -29..178 ms | 8 |

Notes on the last row: the Mac samples the player table with the wine probe every 176 ms (median) and stamps the sample when the probe
starts, so a single value carries up to +176 ms of uncertainty (hence the negative ones); clocks were aligned with a UDP time echo (laptop vs
MacBook -115 to -130 ms, the desktop vs MacBook +1304 ms: the desktop's clock is 1.3 s off). So: the joiner shows the host's move within
roughly one network send interval (~100 ms at 10 packets/s) plus the relay hop, and no worse than ~0.35 s. Driving was not measurable this
way: writing the input block (0x5367CC throttle, 0x5367D0 throttle-up) moved the host car only 2 m in 8 s from the bench session, so no
moving-car comparison was made. A LAN baseline for the step test was not obtained (the LAN control cell did not join).

## 6. Next steps

1. **True NAT (needs the owner)**: put the laptop on a phone hotspot. Then either (a) the relay on this desktop with a router port forward
   (UDP 19900 -> <LAN-IP>) and an allow rule for the relay program, both owner decisions; or (b) the relay on a small VPS (one UDP port).
   (b) avoids touching the home router. With the hotspot alone and the relay still on the MacBook, a forward to the MacBook would be needed.
2. Run the exact desktop cell (two lab twins + DOSBox Staging, n 2) when the desktop console is free for ~10 min, to close the 2026-10-20
   row on the machine where it failed; the twins are ready (`relay-e/f-20261025`, `exp-relay-nitro-a/b-20261025`, lab `relay.py gold` /
   `relay.py nitro`). It is no longer needed to answer the question.
3. Decide the relay: ipxbox (maintained, keepalives, syslog; needs a Go build, no auth) or pyrelay grown into the real thing (allowlist,
   per-room ports, opaque nodes so players cannot see each other's IPs, an invite token in the registration packet would need an IPXWrapper
   change). Option (d)'s loopback shim is the same code on the player's side.
4. Pack: ship the master DLLs (GPL-2.0: point at upstream dbe9a81, no local changes except instance letters for lab twins) and an
   `ipxwrapper.ini` written by the launcher from a "relay address" setting; keep stock IPXWrapper UDP as the LAN default.
5. 3-4 players through the relay, a Mac host, Nitro ARENA+ / co-op session types, a late join, host migration: not measured.
6. The LAN control (plain IPXWrapper, laptop + Mac clone) should be repeated with an isolated port before it is used as a baseline.

## 7. Where things are

- Lab (local repo, commits 7e4c113, 460fe01): `builds\ipxwrapper-master-20261025\` (README with sha256, build log; `src\` = the upstream
  clone, `out\` = the DLLs), `refs\nasm\`, `tools\relay-spike\` (pyrelay.py, ping.py, timesrv/timecli.py, relay.py + with-lock.ps1 for the
  desktop cell, npair.py, gcell.sh, x0.sh, gnav.ps1 + gnavg.py (laptop), gnav.sh + rj.sh (MacBook)), `captures\relay-spike-20261025\`.
- Twins (delete when the lane ends): desktop `relay-e-20261025`, `relay-f-20261025`, `exp-relay-nitro-a-20261025`, `exp-relay-nitro-b-20261025`;
  laptop `<bench>\relay-gold`, `relay-nitro`, `relay-in`; MacBook `~/i76-relay-lab` (two app clones, `Interstate 76 Gold Relay Lab.app`,
  `Interstate 76 Nitro Relay Lab.app`, bundle ids `com.i76everywhere.test.interstate.76.*.relay.lab`).
- No router, firewall or main-copy change was made.
