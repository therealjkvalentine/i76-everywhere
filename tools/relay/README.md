# Interstate '76 internet relay (host side)

Internet play for Interstate '76 Gold and the Nitro Pack without a VPN: one PC runs this **relay**, every player's game sends its
IPX packets to it over UDP, and the relay forwards them to the others. To the games it looks like one LAN, so HOST / JOIN > IPX work
as at home. Owner ruling on issue #113: the relay runs on the developer's desktop at home ("A"). Record:
[docs/records/RELAY-DESKTOP-2026-10-25.md](../../docs/records/RELAY-DESKTOP-2026-10-25.md); the protocol and the spike that proved it:
[docs/records/INTERNET-RELAY-SPIKE-2026-10-25.md](../../docs/records/INTERNET-RELAY-SPIKE-2026-10-25.md). Players: [JOIN-RELAY.md](JOIN-RELAY.md).

| file | what it is |
|---|---|
| `RUN-RELAY.bat` | starts the relay in a console window; prints the port, this PC's home-network address and the public address to hand out. Close the window (or Ctrl+C) to stop it. |
| `RELAY-FIREWALL.bat` | once per PC (asks for administrator rights): removes the inbound **Block** rules Windows made for the relay's Python and adds one inbound **Allow** rule, UDP 19900 only, for that Python only, private + public networks. `--check` shows what it would do and changes nothing. The undo line is in its header. |
| `relay.ini` | port (19900), listen address, optional allowlist, idle timeout, log level, log file, which Python |
| `pyrelay.py` | the relay itself: Python 3, standard library only, ~200 lines. Speaks the DOSBox IPX server protocol (as `ipxnet startserver` and ipxbox). |
| `relay-tool.ps1` | what the two .bat files run |

## Set up the desktop (once)

1. **Python 3** (python.org, "Add python.exe to PATH"; a Microsoft Store Python works too, but run `RELAY-FIREWALL.bat` again after
   each of its updates: its program folder changes).
2. **`RELAY-FIREWALL.bat`**: double-click, answer Yes. It lists the rules it removed and the one it added.
3. **Router**: in your router's admin page, port forwarding: forward **UDP 19900** to this PC (the "this PC on the home network"
   address `RUN-RELAY.bat` prints). Nothing else; players need no forwarding (everything they receive is a reply to what they sent).
4. A VPN app on this PC changes the public address and can drop forwarded packets: turn it off while hosting.

## Every session

1. `RUN-RELAY.bat`. It prints `players start: PLAY.bat --relay <public address>:19900`; send that line to the players.
2. Start the game yourself the same way (`PLAY.bat --relay <public address>:19900`, or `127.0.0.1:19900` on this PC), HOST > IPX.
3. The window shows `player joined the relay: <address>` for each game that connects, and a traffic line every 10 s.

Logs: `relay.log` beside these files (`log file` in relay.ini). Attach it with the players' `mciproxy.log` to a multiplayer issue.

## What to know

- **Every player in a session can see every other player's internet address.** Under the DOSBox protocol a player's IPX node *is* his
  public IP:port, and every packet carries it. The relay does not hide them. Invite people you would give your address to.
- Anyone who has the address and port can join while the relay runs. `allow = ` in relay.ini limits it to listed addresses / ranges.
- One relay = one network: everybody connected sees every game hosted through it.
- Traffic is small: ~1 KB/s up per player; ~60 KB/s out of the relay for 8 players.
- A game that is closed stays listed for `idle timeout` (600 s) and is then dropped; that costs a little upload, nothing else.
- The relay identifies a player by the address his packets come from, not by what the packet claims (DOSBox trusts the packet); packets
  from addresses that never registered are dropped.
