# Internet relay on the desktop: `tools/relay/` + `PLAY.bat --relay`, 2026-10-25

Owner ruling on #113: *"A [the desktop at home] would be more portable and better even though there's some config that's needed."*
This lane builds what A needs and tests it on one PC; the router and firewall steps are the owner's (#122), the real NAT test is #123.
Before: [INTERNET-RELAY-SPIKE-2026-10-25.md](INTERNET-RELAY-SPIKE-2026-10-25.md) (IPXWrapper master fixes the DOSBox-mode start-up; the
relay shape works for Gold and Nitro on one LAN). Everything below was measured today; n = sessions.

## Verdict

- **Built**: `tools/relay/` (relay + host scripts), `PLAY-i76.ps1 -Relay <address>:<port>` / `-CheckRelay` / `-RelayRestore`, the
  settings-file line `relay = <address>:<port>`, `PLAY.bat` / `PLAY-Nitro.bat --relay` in the Patch Kit, IPXWrapper master shipped in
  the kit's `_ipx\relay\` (sha256-pinned, GPL-2.0 with licence and source zip). Without `--relay` nothing changes.
- **Gold, two copies on this PC, host + join through the repo's `pyrelay.py`, both started by `PLAY-i76.ps1 -Relay`: 3 of 3 joined**
  (relay on 127.0.0.1 n 2, on this PC's LAN address n 1), both tables hold both cars at the same coordinates (0.0 m), held 30 s,
  **0 CRASH**, and after each game was stopped the launcher had put the folder's own IPX files back (6 of 6 copies).
- **Nitro, launcher only**: `PLAY-i76.ps1 -Exe nitro.exe -Relay` swaps the files in, nitro.exe runs 45 s, the LAN files come back
  (n 2). No Nitro session was driven through the relay here (no menu driver for Nitro in this harness); the spike's Nitro sessions
  (2 of 2) used the same three DLLs with a hand-written ini, which is what the launcher now writes.
- **Not measured**: anything across a NAT (#123), the firewall rule (`RELAY-FIREWALL.bat` was not run: it changes this PC's
  security settings; only `--check` was), the router forward (#122), a kit unzipped into a GOG folder and started by double-click.

## 1. What was built

| piece | what it does |
|---|---|
| `tools/relay/pyrelay.py` | the spike's relay cleaned up: Python 3 stdlib, reads `relay.ini` then the command line; DOSBox protocol (registration = socket 2 / host 0; broadcast to all but the sender; unicast by node); sender = UDP source address, unregistered senders dropped; `allow` CIDR list; idle timeout; `log level` quiet / info / debug; stats line every 10 s; `log file` (empty = console only) |
| `tools/relay/relay.ini` | port 19900, bind 0.0.0.0, allow (empty = anyone with the address), idle timeout 600, log level info, stats every 10, log file relay.log, python (empty = `py -3`, else `python`) |
| `tools/relay/RUN-RELAY.bat` | `relay-tool.ps1 -Run`: prints the port, this PC's home-network addresses (where the port forward points), the public address (asked of OpenDNS by DNS; else the router-page hint) and the `PLAY.bat --relay <public>:19900` line to hand out, then runs the relay in that window |
| `tools/relay/RELAY-FIREWALL.bat` | self-elevating like `tools/patch-kit/FIREWALL.bat`; `relay-tool.ps1 -Firewall`: finds the REAL program file of the relay's Python (a Store Python's `python.exe` is an alias; the process is `C:\Program Files\WindowsApps\...\python3.x.exe`, read by `QueryFullProcessImageNameW` on itself), removes every inbound **Block** rule on that program, adds one inbound **Allow** rule "Interstate 76 relay (i76-everywhere)", UDP 19900, that program, private + public. `--check` lists and changes nothing. Undo line in the header |
| `PLAY-i76.ps1 -Relay` | checks the address (`host[:port]`, port default 19900; `off`), checks `_ipx\relay\{ipxwrapper,wsock32,mswsock}.dll` against the pins, moves the folder's own `ipxwrapper.dll / wsock32.dll / mswsock.dll / ipxwrapper.ini` into `_ipx\lan-saved\` (marker `_ipx\relay-active.txt`), copies the relay set in (read back by sha256), writes the two-line ini (read back), logs it; after the game exits (or did not start) puts the LAN files back. A start without a relay undoes a relay launch that did not finish. A refusal exits 7 with a message box (the kit runs the launcher hidden; no box when output is redirected) |
| `-CheckRelay` | the address + pins check only, before anything is written; `PLAY.bat --relay` runs it in its visible window first |
| `-RelayRestore` | the undo by hand; `UNINSTALL-i76e.bat` runs it when the marker is there |
| `i76-settings.txt` `relay =` | Multiplayer group, kind `relay`; `PLAY.bat --relay off` wins over it for one start |
| kit (`tools/package-patch-kit.ps1`) | `_ipx\relay\`: the three DLLs (refused unless their sha256 are the pins), upstream `license.txt` as `LICENSE-IPXWrapper-GPL-2.0.txt`, `readme-IPXWrapper.txt`, `ipxwrapper-source-dbe9a81.zip` (`git archive` of the built commit), `README-relay-IPXWrapper.txt` (sha256, build line); the binary guard allows those three names only in that folder; `tools/relay/` in `_i76e\repo\`; VERSION.txt line; `--relay` in PLAY.bat and PLAY-Nitro.bat |
| docs | `tools/relay/README.md` (host), `tools/relay/JOIN-RELAY.md` (players), kit README "Internet games", THIRD-PARTY.md IPXWrapper row, MULTIPLAYER.md row |
| tests | `tests/test_relay.py` (9: relay forwarding / broadcast / drop / allowlist / ini; launcher address checks, pin refusal, swap + restore, unfinished-launch undo, settings line, `--relay off`) |

Pins (PLAY-i76.ps1 `$relayPins`, the spike's build, lab `builds\ipxwrapper-master-20261025\README.md`): ipxwrapper.dll `1f88a797...`,
wsock32.dll `508f9c23...`, mswsock.dll `ac460620...`; the launcher also accepts the instance-letter variants R / S / T / U of
ipxwrapper.dll (the same build with the 2-byte mutex / registry letter; two copies on one PC). The kit ships only the plain build.

## 2. Found on the way

1. **Every option of the kit's `PLAY.bat` / `PLAY-Nitro.bat` broke the launch when the .bat was not started from the game folder**:
   `shift` also shifts `%0`, so `%~dp0` after the first option is the folder of the option text (= the current directory). Measured:
   the generated PLAY.bat started from another directory with `--no-supersample` ran no `i76e-prepare.ps1` (`-File` path did not exist).
   Fix: `set "HERE=%~dp0"` before the options, `%HERE%` after (both templates). Double-click (no options) and a Command Prompt in the
   game folder worked before and still do.
2. **The desktop's Python Block rules are Public-profile only**: `netsh ... show rule` lists, for the Store Python 3.13 the relay would
   use, Block on Public (TCP + UDP) and Allow on Private (TCP + UDP); this PC's Ethernet is Private. So a relay here may already be
   reachable from the home LAN; whether forwarded internet packets pass depends on the profile of the interface they arrive on
   (the Ethernet, Private here), not on the internet being "public". The rule `RELAY-FIREWALL.bat` adds covers both profiles anyway.
   The Store Python's program folder carries its version (`..._3.13.3824.0_...`): an update moves it and the rule stops matching
   (the bats say to run it again; `relay.ini python =` pins a python.org install instead).
3. **A VPN adapter is up on this PC**: with a VPN connected, the public address `RUN-RELAY.bat` finds
   is the VPN's and forwarded packets may not arrive. `RUN-RELAY.bat` and #122 say to turn it off while hosting.
4. `relay.ini`'s `log file =` (empty) fell back to relay.log (the test found it); fixed: empty = no file.
5. Stale registrations: a game that is killed stays registered until the idle timeout (600 s); the relay keeps broadcasting to it
   (run 2 of r127 showed 4 registered, 2 of them run 1's). Harmless upload; a shorter `idle timeout` trims it.
6. The relay's own PC must use `127.0.0.1` (or its LAN address), not its public address: the home router was found without hairpin NAT
   (NITRO-LOBBY-2026-10-25), and the spike's Mac joiner on 127.0.0.1 joined a remote host through the same relay.

## 3. Cells

Harness (lab, not in the repo): `<lab>\tools\relay-desktop\rdt.py` (Gold host + join; mpo.Inst menus through the lab proxy's
`I76_LAB_SHELLCLICK`), `rdt_nitro.py` (Nitro launcher smoke), `with-lock.ps1` (the `.fps-queue` / `.fps-lock` / `.console-owner`
rules), `batgen.ps1` (writes the kit's PLAY.bat / PLAY-Nitro.bat from the packager's AST, for the bat checks). Every boot: the repo's
`PLAY-i76.ps1 ... -NoFfb -FfbOff -NoHeadTrack -NoStick -NoMusic -SkipCutscenes -NoSettings -NoLocal -Relay <addr>:<port>` on its own private
desktop (deskrun.py runs the launcher; the game inherits it), `I76_SKIP_MOVIES` + `I76_SKIP_CUTSCENES` + `I76_FFB_OFF`, `I76_MUTE` +
start-mute-watch per pid, `I76_SHM_SUFFIX` per twin; only processes the harness started were stopped. Twins: `relay2-a-20261025`
(IPXWrapper master instance R in `_ipx\relay\`) and `relay2-b-20261025` (S), copies of game-mpo-d (i76.exe / shell / lab proxy 197c0351)
without `_ahk` and `i76wheel.exe` (no helper processes); `relay2-nitro-20261025` (copy of exp-nitro-mp, plain master build). Relay =
the repo's `tools/relay/pyrelay.py`. Evidence `<lab>\captures\relay-desktop-20261025\<tag>\`.

| cell | result | n | evidence |
|---|---|---|---|
| Gold host + join, relay 127.0.0.1:19900 | **pass**: relay files in place on both (sha256 + ini read back, marker), HOST BROADCAST in Suburbia (m04), JOIN GAME first try, both tables ids 3 + 6, parked agreement 0.0 m / 0.0 m, held 30 s, 0 CRASH; relay: 2 joined, ~900 packets / 150 KB in from the host per run; after stop both folders' own ipxwrapper.dll (94e1039f) / mswsock (c18759b2) back, no ini, no marker | 2 | `r127` |
| the same, relay on this PC's LAN address | **pass** (same checks; host in 820 pkt / 136 KB, joiner 365 / 33 KB in 50 s; 56 us per packet in the relay) | 1 | `rlan` |
| first run (harness counted the AI pool's two empty slots as players) | joined, positions agreed; the join check failed on the count (fixed: people = ids below 0x7000); not counted above | 1 | `dev1` |
| Nitro launcher: `-Exe nitro.exe -Relay 127.0.0.1:19901` | files in (1f88a797 / 508f9c23 / ac460620, ini, marker), nitro.exe alive 45 s, LAN files back (ipxwrapper 1ca45be0, mswsock c18759b2); relay saw no registration (IPXWrapper registers at HOST / JOIN, not at start); CRASH 0 of a near-empty proxy log (that copy's proxy logs little): weak | 2 | `nitro1` |
| kit `PLAY.bat` from another directory: `--relay 127.0.0.1:19900` / `--relay bad:host:1` / missing DLL | after the `%HERE%` fix: check line printed, hidden launch swapped and restored (play-i76.log); bad address and missing DLL refused with the reason and `pause`, folder untouched | 1 each | `%TEMP%` scratch folder, play-i76.log |
| test pack `-Version 0.8.2-test` (lab `builds\relay-desktop-kit-test`) | packed, 130 files, `_ipx\relay\` = 3 DLLs (md5 42d83f38 / f7d5ee0f / 0f8c7d61) + licence + readmes + source zip; guard passed; not released | 1 | stage + zip there |
| `RELAY-FIREWALL.bat --check` on this PC | lists 4 inbound rules on the Store python3.13.exe (2 Block Public, 2 Allow Private), would remove 2 and add 1; nothing changed | 1 | - |
| pytest `tests/test_relay.py` + test_settings_file + test_render_keys + test_presets + test_controls | 9 + 8 + 37 passed | 1 | - |

## 4. Open

- #122 (owner): `RELAY-FIREWALL.bat`, the router's UDP 19900 forward, `RUN-RELAY.bat` lists the port.
- #123 (owner): laptop on a phone hotspot joins the desktop's host through the relay; both mciproxy.log + relay.log.
- Both need a kit with `_ipx\relay\` on the PCs that play: the next kit pack (not packed for release by this lane; the test pack above
  shows the packer works). The developer's own copies get it by copying a kit's `_ipx\relay\` folder in.
- Nitro session through `--relay` (the menus driven) not run here; 3+ players, a Mac through `--relay` (the Mac Kit has no launcher
  option yet: its prefix needs the same three DLLs + ini by hand, as the spike did), opaque nodes (players cannot hide their addresses).
- Lab twins `relay2-a/b/nitro-20261025` to delete when #123 is done.
