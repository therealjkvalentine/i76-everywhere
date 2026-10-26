# Playing Interstate '76 over the internet through a relay (players)

Somebody runs the relay ([README.md](README.md)) and gives you its address, e.g. `203.0.113.7:19900`. You need the **Windows Patch
Kit** built after 2026-10-25 (one with an `_ipx\relay\` folder: it carries the IPXWrapper build the relay needs), the same kit
version as the other players, and nothing else: no port forwarding, no VPN. (The kit also carries the relay itself, in
`_i76e\repo\tools\relay\`, for whoever hosts it.)

## Start

In the game folder (the one with `i76.exe`, or `nitro.exe` for the Nitro Pack), in a Command Prompt:

    PLAY.bat --relay 203.0.113.7:19900
    PLAY-Nitro.bat --relay 203.0.113.7:19900      (Nitro Pack)

(the port can be left out when it is 19900). Then **MULTI MELEE > HOST** (one of you) or **JOIN** (everyone else), exactly as on a
LAN. The relay host's window shows `player joined the relay` when your game connects (that happens when you open HOST or JOIN).

To play through the relay every time without typing it, open `SETTINGS.bat` and add under `[Multiplayer]`:

    relay = 203.0.113.7:19900

`PLAY.bat --relay off` then plays on the home network for one start; delete the line (or `relay = off`) to go back for good.

## What it does to your folder

For that launch only, `windows/PLAY-i76.ps1` checks the three IPXWrapper files in `_ipx\relay\` against their pinned SHA-256, moves your own
IPX files (`ipxwrapper.dll`, `wsock32.dll`, `mswsock.dll`, `ipxwrapper.ini`, if you have them) into `_ipx\lan-saved\`, copies the relay
set beside the exe and writes a two-line `ipxwrapper.ini`:

    dosbox server address = 203.0.113.7
    dosbox server port = 19900

When the game exits, your own files come back. If the PC was switched off mid-game, the next start puts them back (and
`UNINSTALL-i76e.bat` does too). `play-i76.log` has a `relay:` line for each step. Without `--relay` (and without a `relay =` line)
nothing changes: LAN play as before.

## Things to know

- **Every player in the session can see every other player's internet address** (the protocol carries it). Play with people you trust.
- Every player needs the same kit version (and the same community maps, if any): the relay only carries packets.
- Problems: the *Network / LAN game problem* form on GitHub, with your `mciproxy.log` and `play-i76.log`, and the host's `relay.log`.

| you see | try |
|---|---|
| a box "Internet relay: ... The game was not started" | the address is mistyped, or `_ipx\relay\` is missing / not the kit's (unzip the kit again) |
| "Unable to create an IPX connection" in HOST / JOIN | the relay is not running, its port is not forwarded, its firewall rule is missing, or your address is not in its `allow` list |
| JOIN lists nothing | the host has not pressed BROADCAST yet, or is on a different relay / port |
