# Game night: Interstate '76 on the home network

*One page for James, Michael and Andrew. Built 2026-10-17; how it was built and tested:
[records/GAME-NIGHT-ROLLOUT-2026-10-17.md](records/GAME-NIGHT-ROLLOUT-2026-10-17.md).*

## Where the game is

| machine | start it with |
|---|---|
| Michael's Mac, Andrew's Mac | **Interstate 76 LAN** on the Desktop (the game lives in `~/Games/Interstate76-MP`) |
| James's Mac | **Interstate 76** in `~/Applications/Sikarugir`, after the one-line swap in the record (section 5); until then it is not the LAN pack |
| Windows PC (optional 4th player) | `PLAY-LAN.bat` in `C:\Users\james\Games\Interstate76-LAN-2026-10-17\Interstate 76` (not the daily driver) |

Every machine has the same game files (checked by md5), the same keys, stock cars, and IPX through IPXWrapper.
Everyone must be on the **home network** (same Wi-Fi or wired). Tailscale does not work for this.

## Who hosts

- **Melee:** anyone can host; the others join. The PC hosting a Mac was measured (2026-10-06). A Mac hosting a
  PC was measured in co-op (2026-10-07). Mac hosting Mac has not been tried.
- **Co-op campaign (2 players only):** the host is the story's hero; the second player is the buddy.

## Host (one machine)

**MELEE > MULTI MELEE > HOST > IPX.** Pick your car and the arena, then **BROADCAST GAME**. You go straight into
the arena (there is no lobby). The others can join while you drive.

- **Co-op Scene 1 .. Co-op Scene 17** (scroll the arena list down, after A Lot of Asphalt) = the co-op campaign:
  pick the scene to start from, then the next one loads on a win, the same one on a loss. Two players only.
- **The 15 stock arenas (The Crater too) = normal melee.**
- Pick a co-op scene and the GAME NAME may go blank or show another name: RENAME it.
- A joiner who gets *"You don't have mission coop01.lvl!"* has an old copy of the pack: update that machine.
- Leave MAX SCORE off, and leave the weapon restrictions at their defaults.

## Join (everyone else)

**MELEE > MULTI MELEE > JOIN > IPX.** The host's game appears in the GAME NAME list (for example "THE CRATER (1/4)").
Click it, then **JOIN GAME**.

## Controls (the same on every machine)

Printable sheet: [Interstate76-Controls-Quick-Reference.pdf](Interstate76-Controls-Quick-Reference.pdf).

| key | does |
|---|---|
| `W` `S` / `A` `D` | gas, brake/reverse / steer |
| `Return` or left mouse | fire the selected weapon |
| `Tab` (or `C`) / `F` | pick the next weapon / fire linked weapons |
| `1`-`5`, and `J` `K` `L` `;` | fire hardpoint 1-5 / hardpoints 1-4 on the home row |
| `Space` / `X` | handbrake / reverse direction |
| `T` / `Y` / `Q` / `U` | nearest enemy / next target / target in front / no target |
| `I` / `H` / `G` | ignition / lights / horn |
| `R` / `O` | radar range / radar camera |
| `'` / `Shift+'` | player scores / team scores |
| `Esc` | menu (quit a game from here) |

On a Mac keyboard the F-keys (camera views F1, F3...) need `fn`.

## If a machine does not see the game

1. **The host must already be in its arena.** Join after the host has pressed BROADCAST GAME.
2. **Same network.** All machines on the home Wi-Fi or wired network, not a guest network, no VPN.
3. **A permission box is waiting.** The first time, a Mac may ask whether **"wineserver" (or "wine") may accept incoming network
   connections**: click **Allow** (Michael's Mac has the firewall on, so it will ask). The first launch may also ask
   about the **microphone**: either answer is fine, but answer it, because the game waits. On the PC, the Windows
   Firewall box can open *behind* the game: Alt-Tab, tick Private networks, Allow.
4. **Still nothing:** quit the game on every machine, start the host first, BROADCAST, then the others JOIN.
5. **"vehicle rejected" or "hacked vehicle":** that machine's files do not match. Tell James (the md5 check in the
   record finds the file).

## Honest status

- **2026-10-18 (records/LAN-MATRIX-2026-10-18.md):** PC hosts / Andrew's Mac joins, Andrew hosts / PC joins and
  Andrew hosts / Steam Deck joins all worked (n 1 each), both cars seen and driven on both screens. Michael's Mac and
  James's laptop were locked during every test window and are untested. 3 players (PC + Deck + Andrew) worked.
  Michael's firewall box was answered (Allow) on 2026-10-18.

- **Two players** (one PC + one Mac) were measured over IPX on 2026-10-06 with older builds. With this pack a Mac
  hosting reached its arena, but the PC-Mac join itself is still the owner's 2-minute test (the record, section 5).
  **Three or four players have not been tested.**
- **Co-op campaign: two players only.**
- A Mac-to-Mac game has not been tested.
