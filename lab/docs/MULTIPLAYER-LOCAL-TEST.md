# Multiplayer on one PC: two lab copies, what was measured (work in progress)

*2026-10-03, physical console, lab copies `game\` (A) and `game-alt\` (B) only. Stopped part-way on the owner's
decision to use an existing community tool instead. **Two instances did NOT reach one session.** No
`mp-two-instance.ps1` exists; `autotest\mp-explore.ps1` is the step-at-a-time helper used for everything below.
[measured] = read from the running game, a capture or a binary today; [inferred] = follows from those;
[untested] = never run. Captures: `autotest\runs\mp\explore\` (untracked).*

## 0. Verdict

| question | answer |
|---|---|
| Two copies running at once | yes, with `music-fix\Strlkup.dll` + `I76_MULTI_INSTANCE=1` (as `two-instance-probe.ps1 -Multi`) [measured] |
| Both walked to the multiplayer forms | yes: A to NET MELEE HOST EVENT FORM, B to NET MELEE ENTRY ROSTER [measured] |
| Session with 2 players | **no**. Three blockers, section 3 |
| Which transport for two copies on one PC (B4, later the same day) | **IPX through IPXWrapper** with the patched game-alt copy: both bound the same IPX socket with distinct nodes and heard each other [measured, 8.6]. The host then stopped at the vehicle anti-cheat check (ValidateVcf), so B saw no game and there was no shared mission. INTERNET: the port split fixes the bind clash, but a peer cannot stand in for the game server [measured, 8.3] |
| Windows Firewall | **prompted for `game\i76.exe`** when A opened its socket. Not clicked. Still on screen (section 4) |

## 1. The route, screen by screen (UI coordinates, 640x480; verified by the shell's button list / state after each click)

| step | click (UI) | verification read [measured] |
|---|---|---|
| intro -> main menu | keys Esc, Enter, Esc, Enter | `screen=0xC00E` |
| MELEE | 447,311 | button list becomes ids 15, 1 (MULTI MELEE, AUTO MELEE) |
| MULTI MELEE | 395,351 | list becomes ids 3, 5 (HOST, JOIN) |
| HOST / JOIN | 367,379 / 417,379 | list becomes ids 6, 7, 14, 8, 16 (MODEM, IPX, INTERNET, NULLMODEM, OTHER) |
| INTERNET | 407,406 | `screen=0xC026`, `modal != 0`: the **CONNECT TO SERVER** popup over the form |
| OTHER | 580,406 | back at the bare main menu at once; what it is meant to open is unknown |

CONNECT TO SERVER popup (fields DRIVER (greyed), NAME, IP; a scrolling list from `internet.lst`: "I'76 Net /
i76net.activision...", "I'76 Net / 206.79.5.4", "play.interstate76..."; buttons DONE, NEW, CANCEL):

| action | click / keys | result [measured] |
|---|---|---|
| CANCEL | 414,418 | back to the main menu. There is no way onto the internet form without a server entry |
| NEW | 320,418 | caret in NAME. Type the name, Enter, type the IP, Enter: the entry is added to the list (third visible row) |
| select a row | 310,355 (third row) | NAME / IP fields show the entry |
| DONE | 228,418 | popup closes (`modal=0`), the form is live, **`internet.lst` is rewritten** (md5 changes; back it up) |

Typed text goes through `keybd_event` scancodes (letters, digits, `.` = VK 0xBE); it worked first time.

Host form (after DONE): LOCAL DRIVER "UNNAMED" + RENAME, AREA OF PLAY list, GAME NAME "THE CRATER" + RENAME,
NO. DRIVERS 04, TEAM PLAY / INVITE ONLY / MAX SCORE, car panel, **BROADCAST GAME 298,461**, CANCEL 562,461.
Join form: GAME NAME list (empty), **JOIN GAME ~298,461**, CANCEL. Static reading of `EntryForm_Frame`
(i76-map shell `10028610.c` lines 407-427): BROADCAST GAME calls `Net_StartSession` and on success posts 0xC010,
i.e. the host goes **straight into the mission**; there is no host lobby [inferred, static].

Shell play modes `[0x100d217c]` (`Net_EnsureDp` 0x1002e2f0) [measured, static]: 2/6 modem host/join, 3/7 IPX,
4/8 internet, 5/9 null modem.

## 2. Transport facts (WINET.DLL, md5 6edfea77, PE stamp 0x33248ae8) [measured, static unless noted]

- `commInit` 0x100014a0: `push 0x52a5` -> one UDP socket, `SO_BROADCAST`, **bound to 0.0.0.0:21157, hardcoded, no
  fallback port**. Live: `Get-NetUDPEndpoint` shows `0.0.0.0:21157` owned by A after DONE.
- Own address is found by sending 4 bytes to 255.255.255.255:21157 and waiting up to 5 s to hear them back
  (0x100011a0); failure = init error 0x84.
- Addresses are 6 bytes, port + IPv4. `commScanAddr` 0x10001790 turns a typed name/IP into **IP : 21157 always**
  (bytes 0x52, 0xA5 written at 0x1000182b / 0x1000180d); there is no `ip:port` syntax.
- This DLL carries a hand patch (code caves 0x100092e0..0x100093a5, jumps at 0x1000136c and 0x10001409): outgoing
  packets get the sender's own address replaced by the marker `AAAA:DEADBEEF`, incoming packets get the marker
  replaced by the real source address from `recvfrom` (and `BBBB:ABADC0DA` for the destination). That looks like a
  NAT fix: a peer is known by the address its packets really come from, source port included [inferred].
- `ANETDLL.DLL` names a `dp.ini`; not looked at.
- The shell calls `dpSetGameServer` with the popup's address when the dp is created (`Net_CreateDp` 0x10036010).

## 3. What failed, with the exact text

| # | instance, action | result [measured] |
|---|---|---|
| F1 | A: HOST, INTERNET, server "LOCAL" = 127.0.0.1, DONE, then BROADCAST GAME about 4 s later | **crash, 2 of 2**: `0xC0000005` in `I76SHELL.DLL+0x3a9a9` (`Mcga_DrawRleSprite`), `mciproxy.log`: `CRASH: code 0xC0000005 at 0x030FA9A9 ... read addr 0x1384583F | ... edi 000000B3 ... frame 0 state 6`, stack `0000002B 000000B3 ...`. x = 0xB3 is the box origin of `Modal_Ok` 0x1000b660 (popup art 0x11 at 179,194), so the crash is the "server not responding" notice being drawn while the host start is in flight [inferred; the debugger attach (`mp-avcatch.ps1`) did not catch a third one] |
| F2 | A: same, but waiting longer than about 40 s before BROADCAST GAME | no crash; a shell box **"Game Server Not Responding"** with OK (`dpReceive` returned 0x10, `Net_PollMessages` 0x1002fcd8). The OK caption is drawn near y 300 but the hit rectangle is **x 298..339, y 255..268** (click 318,261 dismissed it; 320,302 did not). The loop is `Modal_Ok`'s own: mouse only, no message pump. After it, BROADCAST GAME does nothing visible and CANCEL (562,461) did not leave the form while the box was up |
| F3 | B: JOIN, INTERNET, NEW "LOCAL" 127.0.0.1, DONE, while A held 21157 | Win32 message box, caption **"Error"**, text **"Unable to create an internet connection.  Verify that you are connected to your internet service provider (ISP).  You must be connected to your ISP before attempting to play an internet game."** It opens *behind* the fullscreen window (found with EnumWindows, class `#32770`, at screen 1515,668). B owned no UDP endpoint. Cause: the second bind of 21157 [inferred from section 2; the control - B alone - was not run] |

So, on one PC with the stock files:

1. **One port.** Both copies need UDP 21157 on the same address; the second cannot open the transport (F3).
2. **A game server is mandatory on the INTERNET transport.** The popup cannot be skipped, and an address that does
   not answer as a server gives F2 (or F1 if the host is started first). 127.0.0.1 from the host is the host itself.
   Activision's servers in `internet.lst` are dead.
3. IPX, MODEM, NULLMODEM were **not tried** (no IPX protocol on Windows 10, no COM pair on this PC) [untested].

## 4. Windows Firewall prompt (owner action)

When A bound its socket, **"Windows Security Alert - Windows Defender Firewall has blocked some features of this
app"** appeared for `C:\Users\james\i76-uncap-lab\game\i76.exe` (process `rundll32`, capture `a9.png`). It was not
clicked and was still open when work stopped; the owner decides. No prompt for `game-alt\i76.exe` was seen (B never
got a socket). Loopback traffic does not need the rule; LAN play would. The prompt sits over the centre of the game
(about UI 232..408 x 175..302); the helper refuses any click whose screen point is not over the chosen game window
and sends keys only when that game is the foreground window.

## 5. Two stacked fullscreen windows: what it took

No conf change was needed; `dgVoodoo.conf` was not touched. Input goes to the foreground instance
(`Force-Foreground`), memory reads pick the process by folder (`$I76GameDirInUse`, `shellstate.ps1 -ProcessId`).
One trap [measured]: with a second instance alive in the background (and the firewall prompt up) the OS cursor
clip **alternates** between `0,0-640,480` (about 1.25 s) and the full screen (about 0.75 s); with one instance it
stays 640x480. A click sent in the released phase is read by the shell as a translated point (447,311 -> 0,103)
and misses; chains of clicks failed that way. `mp-explore.ps1`'s `Safe-Click` waits for the clip to go
released -> confined and clicks inside that window; every click after that change landed (about 25 of 25). Earlier
in the same sitting, before the prompt existed, about 15 clicks landed without that wait; which of the two
(prompt, start order) causes the alternation was not separated.

The main-menu logo is animated (it zooms); two captures of the same screen differ. Do not read that as a layout change.

## 6. Unfinished / unknown

- **Port-split experiment, prepared and never run.** Idea: A keeps 21157 and types addresses as :21158 (one byte,
  `WINET.DLL` file offset 0xC10, A5 -> A6); B binds 21158 (file offset 0x8CB, A5 -> A6) and types :21157. Each
  copy's "server" would then be the other copy on 127.0.0.1. The bytes were written to the two lab copies, the
  stop came before any launch, and both files were put back (md5 6edfea77 again). Whether a plain peer answers as a
  "game server" at all is the open question it was meant to settle [untested].
- Whether the host works when the server answers; what the joiner's roster shows; any player-count or session
  field to read from memory; the exe's `*** %s has joined the game` line: none reached.
- F3's control (B alone, port free) and F1's exact call stack.
- The OTHER button; `dp.ini`; LAN address instead of 127.0.0.1; IPX / null-modem routes.

## 7. Helper and state

```powershell
cd C:\Users\james\i76-uncap-lab\autotest
.\mp-explore.ps1 -Start                              # locks, state backup to runs\mp\bak, proxy in, A then B
.\mp-explore.ps1 -Inst A -Key "ESC,ENTER,ESC,ENTER"
.\mp-explore.ps1 -Inst A -Click "447,311" -Buttons   # one click, then read the state it prints
.\mp-explore.ps1 -Inst A -Shot name [-Full]
.\mp-explore.ps1 -Close                              # kill both, STRLKUP.DLL back, locks off, changed state files put back
```

`mp-avcatch.ps1 -TargetPid N -Out file` attaches as a debugger and dumps the WOW64 context and stack on the first
access violation (it changes the timing: F1 did not recur under it).

Folders at stop [measured]: no `i76` process; both `STRLKUP.DLL` md5 54f2de9d; no `.console-test.lock`, no
`.pretest` files; `DLL\WINET.DLL` 6edfea77 in both; `internet.lst` 38474c4d in both (A's had gained the LOCAL entry
and was put back); `savegame.dir`, `save*.cmp`, `*.def`, `*.spc`, `input.map` byte-identical to the copies taken
before the first launch (21 files per folder, 0 differ); `dgVoodoo.conf` and `u32x.dll` untouched.

## 8. Transport study (B4, 2026-10-03 afternoon): static reading + one live INTERNET run

Tools: python pefile + capstone on the lab copies' DLLs (md5 below); IPXWrapper 0.7.2 binary + source and the
LGPL anet source downloaded to `refs\ipxwrapper` (GPL-2.0) and `refs\anet` (github Nielk1/anet, LGPL; the
2001 "v2" code, newer than this 1997 ANETDLL, so read as a guide only).

### 8.1 WIPX.DLL (md5 9b044781, stamp 0x3329c2c9) [measured, static]
- Imports only WSOCK32 (`socket, bind, setsockopt, sendto, recvfrom, ioctlsocket, htons, WSAStartup/Cleanup`).
  No NWLink/Novell API. `IPXWIN_Create` 0x10001910: `socket(AF_IPX=6, SOCK_DGRAM, NSPROTO_IPX=1000)`,
  `setsockopt(SOL_SOCKET, SO_BROADCAST)`, `bind` net 0 / node 0 / **socket 0x52A3 (hard-coded, pushed at
  0x10001068)**, FIONBIO. Broadcast address = node FF:FF:FF:FF:FF:FF, same socket.
- Own address: sends 4 bytes to the broadcast address and waits up to 5 s to receive them back (0x10001ab0),
  the same trick as WINET. No echo = init error 0x84.
- Addresses are printed as `net,node` (`%u.%u.%u.%u,%X.%X.%X.%X.%X.%X`); the socket is implicit, so every
  peer must use the same IPX socket number. **No server**: sessions are found on the wire.
- Shell: `Net_CreateDp` 0x10036010 calls `dpSetGameServer` only when a server name is set (0x1003624d..0x1003628b),
  i.e. only on the INTERNET route.

### 8.2 ANETDLL.DLL (md5 785171b6, stamp 0x3339eb58, March 1997) [measured, static]
- `dpOpen` 0x10004240: if a game server handle is set (not -4/-3) and `dpio` state of that handle (0x10007080)
  is not 7 (ESTABLISHED), return **0x10** -> the shell's "Game Server Not Responding". So hosting on INTERNET
  needs a *connected* server.
- `dpSetGameServer` 0x10001ff0 resolves the name with the driver and opens a dpio handle to it at once (SYN).
- `dpEnumSessions` 0x100020a0 sends a `dE` request to the server handle. Any node that is master of a session
  (`[dp+0xc]=1`, set by `dpOpen` with the create flag at 0x100043ac) answers `dE` with its session (`dS`,
  0x100029d0), opening a handle for an unknown sender first (0x1000370b..0x10003728). So a host can answer session
  enumeration, but the connected-server check in `dpOpen` comes first.
- dpio reaches ESTABLISHED only after both ends have sent a SYN (anet `dpio.h`: "Sent syn, got syn ack and SYN").
  The 1997 change log says packets from an unknown sender (PLAYER_NONE) are dropped, SYN included.

### 8.3 Live: INTERNET with the port split (console held 12:42-13:04, B4) [measured]
`autotest\winet-portsplit.ps1 -Apply`: A (`game`) file 0xC10 A5->A6 (typed addresses go to :21158), B
(`game-alt`) file 0x8CB A5->A6 (binds 21158). Each byte was read back. Both copies: server entry "LOCAL" = 127.0.0.1,
so each names the other.
- **The bind clash is solved**: `Get-NetUDPEndpoint` showed `0.0.0.0:21157` owned by A and `0.0.0.0:21158` owned
  by B at the same time, with no "Unable to create an internet connection" box (F3 does not recur).
- **The server step still fails.** Run 1 was confounded (B was suspended for about 60 s after its DONE). Run 2:
  B DONE, then A DONE at 13:02:56, both processes running and responding, nothing suspended. A showed "GAME
  SERVER NOT RESPONDING" between 30 and 36 s after its DONE (window stopped responding = `Modal_Ok` loop;
  capture `runs\mp\explore\run2-60s.png`). B showed no box and its list read "No games found". n = 1 clean run.
  Not separated: whether the SYNs arrived and were ignored (8.2), or did not arrive. B's SYNs went to a closed
  port for about 3 min before A bound; that is a possible confound. The likelier reading: a plain peer does not
  answer as a game server.
- The **firewall prompt for `game-alt\i76.exe`** appeared when B bound its socket (rundll32 pid 27372,
  "Windows Security Alert"). It was **not clicked** and is still on screen. The first one (for `game\i76.exe`) was
  no longer showing. The prompt sits over the box's OK hit rectangle (318,261), so A could not be released
  either time and was killed.
- Restored afterwards: both WINET.DLL md5 6edfea77 (stock); STRLKUP 54f2de9d in both; internet.lst put back
  (changed, restored); 0 of the backed-up state files differ; no i76 process, no `.console-test.lock`, no `.pretest`.

**Driving trick [measured]:** `NtSuspendProcess` on the other instance stops the cursor-clip alternation (section 5).
With B suspended, 10 of 10 clicks on A landed at the first try (`sawFree=False stable=True`). With both
running, MELEE took 25 attempts and failed to stick. Suspend only before an instance's DONE: a suspended peer
looks like a dead server to the other one. (A `Force-Foreground` on an instance stuck in `Modal_Ok` hangs
`mp-explore.ps1`. Use a background job, or read state with `shellstate.ps1` and take the capture without focusing.)

### 8.4 IPX on one PC with IPXWrapper 0.7.2 [static: source and binary read; not run]
IPXWrapper replaces wsock32 in the game folder (`ipxwrapper.dll`, `wsock32.dll`, `mswsock.dll`; the folder's own
`ipxwrapper.ini` overrides the registry). It carries IPX inside UDP (port 54792 shared via SO_REUSEADDR for
broadcasts, a random private port per process). Two clashes for two processes on one PC:
1. **Bind**: `_complete_bind` takes the named mutex `ipxwrapper_socket_<n>`, which is shared by the whole session.
   A second bind of 0x52A3 fails with WSAEADDRINUSE unless that socket set SO_REUSEADDR. WIPX sets only SO_BROADCAST,
   and IPXWrapper's default "w95 bug" emulation drops broadcasts to sockets without SO_BROADCAST, so
   that option cannot simply be swapped for SO_REUSEADDR.
2. **Node**: the wildcard interface's node is random but **stored once in HKCU\Software\IPXWrapper**, so both
   processes get the same net/node/socket and the peers could not tell each other apart. The ini file cannot set a
   node. DOSBox-server mode would give each its own node, but the DOSBox server never sends a broadcast back to
   its sender (dosbox-x `ipxserver.cpp`), which would break WIPX's 5 s self-echo.
**Fix chosen**: `autotest\ipx-setup.ps1 -Install` gives game-alt a copy of ipxwrapper.dll with two bytes changed,
"ipxwrapper_socket_%hu" -> "ipxwrapper**B**socket_%hu" (file 0x1BEAC) and "Software\IPXWrapper" ->
"Software\IPXWrappe**B**" (file 0x1CB7C). B then has its own mutex namespace and its own registry key, so it gets
its own random node. A keeps the stock file. `-Remove` deletes exactly the installed files. Open points:
whether a process hears its own UDP broadcast in plain mode (WIPX needs that; Windows usually loops directed
broadcasts back), and whether the shell's IPX button goes straight to the form.

### 8.5 Next step (exact)
1. Take the console (CONSOLE-LOCK.md). `autotest\ipx-setup.ps1 -Install` (lab copies only). `mp-explore.ps1 -Start`.
2. Suspend B. Walk A: MELEE, MULTI MELEE, HOST, **IPX 343,406**, then BROADCAST GAME. Resume B and suspend A only
   while B's menu clicks are made: MELEE, MULTI MELEE, JOIN, IPX. Then resume A and leave both running. Read B's
   GAME NAME list. If "THE CRATER" shows, JOIN GAME.
3. If WIPX init fails (box), set `logging = debug` in a per-folder `ipxwrapper.ini` and read `ipxwrapper.log`.
4. Close: `mp-explore.ps1 -Close`, `ipx-setup.ps1 -Remove`, md5 check. The HKCU keys IPXWrapper / IPXWrappeB
   stay (only node numbers).
5. Owner: answer or dismiss the Windows Firewall prompt for `game-alt\i76.exe`. Loopback does not need the rule,
   but while the prompt is up it covers the centre of both games.

### 8.6 Live: IPX with IPXWrapper (console held 13:36-13:50, B4) [measured unless marked]
`ipx-setup.ps1 -Install` (A stock ipxwrapper.dll md5 06a01d0f; B patched copy fad787e8, read back as
`ipxwrapperBsocket_%hu` / `Software\IPXWrappeB`; a per-folder `ipxwrapper.ini` with `logging = debug`).
Logs: `autotest\runs\mp\ipx\game-ipxwrapper-134955.log`, `game-alt-ipxwrapper-134955.log`. Captures:
`runs\mp\explore\ipx-*.png`. n = 1 attempt.

**What IPX did (network layer: works)**
- The IPX button **opens the form directly**; there is no server popup.
- A: `bind(..., /21155)` gave address `00:00:00:01/92:DA:A4:AC:05:7A/21155` (UDP private port 61965). Its
  4-byte self-echo broadcast went out on 192.168.1.255, 172.30.175.255 and 100.113.196.47 (:54792) and came
  back 3 times, so WIPX init succeeded (no 0x84).
- B: the **same IPX socket 21155 bound with no WSAEADDRINUSE** (separate mutex), with its **own node**
  `2F:E4:D6:9F:90:93` (separate HKCU key). Its self-echo also came back.
- **Cross-process delivery works**: A's log shows B's broadcast arriving from 2F:E4:D6:9F:90:93 and being relayed to
  A's socket.
- Firewall: no new prompt appeared. The old prompt for `game-alt\i76.exe` (pid 27372) was still up and was not touched.

**What stopped it (game layer, not network)**
- A, HOST > IPX > BROADCAST GAME: A **stopped responding inside a shell modal** (box at UI 179..461 x 194..287,
  text hidden behind the firewall prompt). After its init echo, A's IPXWrapper log shows **no packet at all**, so
  the session never opened.
- The box is `Modal_VehicleRejected` 0x1000b980 [inferred, strong]:
  - its art rectangle (0xB3,0xC2, 0x11A x 0x5D) matches the box;
  - Net_HostSession calls it when exe callback slot 26 **ValidateVcf (0x4b35a0, anti-cheat CRC on the car .vcf)**
    returns 0, before `dpOpen` (0x1002f3d6 < 0x1002f4ad);
  - every `dpOpen` failure uses a Win32 MessageBox, and A owned no `#32770` window;
  - no traffic followed, which is what a stop before `dpOpen` looks like.
  - Its OK hit rectangle (UI 298..340 x 255..269) is under the firewall prompt, so it could not be dismissed.
- B (launched after A), JOIN > IPX: the form opened, and the list read **"No games found"**. That is expected,
  since A never opened a session.
- A's default car was PICARD PIRANHA / JADE'S CAR. The lab copy carries modded vehicle/ADDON data (memory:
  sandbox carries user mods), and that is the likely reason the CRC fails [inferred].

**Answer to "did B see A's game / did both reach one mission": no and no.** IPX now works between two copies on
one PC at the transport level. The run stopped one step earlier, at the host's vehicle anti-cheat check.

**Driving notes**
- Starting A alone (`mp-explore.ps1 -Start -OnlyA`), walking it, and only then launching B was reliable: every
  click landed.
- Suspending B straight after launch, while it still covered the screen, left A's window parked at -32000,-32000.
  That parked state survived `ShowWindow`/`SetWindowPos`, and every click went nowhere.

**Restored** at 13:50:
- `ipx-setup.ps1 -Remove` removed 3 files per folder; ini removed; logs moved.
- DLL\WINET/WIPX/WMODEM/WSERIAL, ANETDLL and STRLKUP match the stock md5s in both folders.
- 0 state files differ from the backup; no i76 process; no lock or `.pretest` files; `.console-owner` released.
- **Left in place, delete later if wanted**: `HKCU\Software\IPXWrapper\00:00:00:00:00:00` and
  `HKCU\Software\IPXWrappeB\00:00:00:00:00:00` (values net, node, enabled). Delete with
  `Remove-Item HKCU:\Software\IPXWrapper, HKCU:\Software\IPXWrappeB -Recurse`.

### 8.7 Next step (exact)
1. Make the host's car pass ValidateVcf. First, check which files the CRC covers: exe 0x4b35a0, i76-map
   `shell\CALLBACKS.md` row 26. Then either use stock vehicle data from the pristine control
   (`i76-map\sandbox-gog\main\app`) in both lab copies for the test, or pick a stock car in the host form.
   If the lab has to keep modded data, a lab-only proxy switch could make slot 26 return 1. Both copies must
   carry identical car data, because the joiner runs the same check (0x1002e6f5).
2. Rerun 8.5 with these changes: start A alone, walk it to BROADCAST GAME, then launch B and JOIN > IPX.
3. Owner: dismiss or answer the firewall prompt first. It hides the shell's modal boxes and their OK buttons.
