# Nitro on the home network: the weekend how-to

*For the developer, the M4 Max tester and the M2 tester. Interstate '76 **Nitro** (the GOG Nitro Pack with our add-ons), PC + Macs on the home
network. Written 2026-10-24 early morning; how it was built and tested:
[records/NITRO-MP-DESIGN-2026-10-21.md](records/NITRO-MP-DESIGN-2026-10-21.md) section 0.5.20. The **Gold** game night
([GAME-NIGHT.md](GAME-NIGHT.md)) is separate and unchanged. If Nitro gives trouble, play Gold.*

## Who hosts, and where the game is

**The PC hosts** (the developer). The Macs join. That is the combination that was tested.

| machine | start it with |
|---|---|
| Windows PC (host) | **`PLAY-NITRO-ALL.bat`** in the one Nitro folder (`Games\I76\Interstate 76 Nitro`, the former `exp-nitro-owner`; it does single player and LAN, the IPXWrapper DLLs are in it). `nitro-lan` is retired. |
| The M4 Max tester Mac, the M2 tester Mac | **Interstate 76 Nitro** in `Games` > `Interstate76-MP` (the folder in your home folder) |
| The developer's MacBook | **Interstate 76 Nitro** in `Applications` > `Sikarugir` |

Everyone must be on the **home network** (same Wi-Fi or wired). Not Tailscale.

**Update 2026-10-25 02:30:** all three Macs (the developer's MacBook, the M4 Max tester's, the M2 tester's) now have the final Nitro proxy `Strlkup.dll` **3f27c797** (main 4e40261) and the patched `nitshell.dll` a32ffba6, launcher e61e4e57 and the no-3D-menus setting. **The M2 tester Mac is updated** (it had proxy ad904941 and launcher 384a0f8e; backup `app-backup-20261025-020752` in `~/i76-nitro-mp-lab` there). The M4 Max tester's backup is `app-backup-20261025-020751`, the MacBook's `app-backup-20261025-020736`. The M4 Max tester Mac still needs the Local Network Allow click (his join stalled again in the final check).

**Update 2026-10-25 09:45: Nitro on the Macs is no longer held at 24 fps.** The three Mac Nitro apps had a 24 fps cap left over from 10-21. They now run the PC's simulation tick (`I76_SIM_TICK_MS=41.667`, `I76_SIM_TICK_INPUT=1`) under the Mac Gold apps' 120 fps cap. The game still steps 41.7 ms (24 per second), the same as the PC host. Measured in P01: MacBook 71.5 fps, M2 tester 55.2, M4 Max tester about 112 (before: 24.0 on each). A Mac-to-Mac LAN join at the new setting worked 2 of 2. Only the Environment values in each app's user.reg changed; the backup is `_rollback-uncap-20261025/user.reg` in each Nitro game folder. Details and undo: [records/NITRO-MAC-UNCAP-2026-10-25.md](records/NITRO-MAC-UNCAP-2026-10-25.md).

Tested overnight, with nobody at the Macs: the PC hosting and the developer's MacBook joining every game type, 2 of 2 each, no
crashes. The M4 Max tester Mac could not join until someone clicks Allow there (next section). The M2 tester Mac was asleep, and three
players at once was not tried.

## Before the first game: say Allow (once per machine)

- **Every Mac, the first time:** macOS asks whether *Interstate 76 Nitro* may **find and connect to devices on your local
  network**. Click **Allow**. Without it the PC's game shows up in the JOIN list, but JOIN GAME does nothing. (This is
  what stopped the joins in tonight's tests on the M4 Max tester Mac.) If someone clicked *Don't Allow*: System Settings >
  Privacy & Security > **Local Network** > switch *Interstate 76 Nitro* on, then quit and reopen the game.
- **The M4 Max tester Mac, also:** macOS may ask *"Do you want the application wine to accept incoming network connections?"*
  Click **Allow**. (His Mac has the firewall on.)
- **The PC, the first time it hosts:** Windows may ask whether `nitro.exe` may use the network. Tick **Private
  networks** and click **Allow**. Do not cancel it: cancelling makes Windows block it.

## Host (the PC)

**MELEE > MULTIPLAYER > HOST > IPX.** On the host form:

1. **GAME TYPE** (the arrow at the top left). Pick one:
   - **Combat**: plain Nitro melee, the way it always was. Only the people in the game.
   - **Arena Drop-In + AI**: computer cars fill every empty seat. Set **NO. DRIVERS** (for example 6); with 3 people
     you get 3 computer cars. People can join and leave at any time. A leaving player's seat goes back to a computer car.
   - **Co-Op**: Nitro's own campaign missions as co-op. Everyone plays the mission together, and the host is the hero.
2. Pick the arena (Combat and Arena Drop-In) or the mission (Co-Op) in the list.
3. **BROADCAST GAME.** You go straight in. The others can join while you drive.

## Join (the Macs)

**MELEE > MULTIPLAYER > JOIN > IPX.** Within a few seconds the PC's game is in the list: *Evening Stroll (1/6)* for
Combat, *[AI Drop-In] Evening Stroll (1/6)* for Arena Drop-In + AI, *[Co-Op] P01 (1/6)* for Co-Op (a PC or Mac still on
the older proxy 3f27c797 shows these as *ARENA+ [AI Drop-In] ...*; a newer joiner shows an older host's game as
*[Drop-In] Evening Stroll*). Click it, then **JOIN GAME**. You are in the arena about
5 seconds later.

## Keys

Nitro uses its **own** keys, and they are the same on every machine: the GOG Nitro Pack's defaults (Nitro's Options >
Controls shows them). The Gold printable sheet does not apply to Nitro.

## If something goes wrong

| what you see | do this |
|---|---|
| The game is in the JOIN list, you click **JOIN GAME**, and nothing happens (you stay on the list) | That Mac has no Local Network permission: see "Say Allow" above. Then quit the game and open it again. |
| The Mac's game crashes or freezes **while starting**, before the menu, or sits on a black screen | Quit it (Dock > right-click > Quit, or Cmd-Q) and open it again. A start crash is now rare (0 in 34 test starts; it was about 1 in 6 before). About 1 start in 10 can still stop before the menu; a second start works. |
| The game is **not** in the JOIN list | Check the PC really pressed BROADCAST GAME and is in the arena. Check the Mac is on the home Wi-Fi. On the M4 Max tester Mac, see the firewall note above. |
| *"Mission file ... not found"* on a Mac | That Mac missed the update. Tell the developer. |
| A Mac game quits by itself after 2-3 minutes | That Mac missed the update (the old launcher did this). Tell the developer. |
| After **Exit** in the game the screen stays black | Press Cmd-Q. |
| Anything else | Play Gold instead ([GAME-NIGHT.md](GAME-NIGHT.md)). |

## What was changed on each Mac, and how to undo it

Each Mac's **Interstate 76 Nitro** got three changes. Nothing else changed, and the Gold app was not touched:

1. the add-on file `Strlkup.dll`: new build `6208d3ad`, with the GAME TYPE choices;
2. the launcher inside the app: `e61e4e57`. It no longer closes the game after 2-3 minutes, quitting one game no longer
   closes another, and it keeps the old launcher's identity so the Local Network permission stays;
3. one Wine setting: `nitro.exe` draws its menus without 3D, which stops the crash at start.

A copy of the old files was kept on each Mac. To go back, close the game, then in Terminal on that Mac:

    bash ~/i76-nitro-mp-lab/apply-update.sh "<the app>" --restore ~/i76-nitro-mp-lab/<backup folder>

| Mac | the app | backup of the state before tonight |
|---|---|---|
| The developer's MacBook | `~/Applications/Sikarugir/Interstate 76 Nitro.app` | `app-backup-20261023-212851` |
| The M4 Max tester's | `~/Games/Interstate76-MP/Interstate 76 Nitro.app` | `app-backup-20261023-222906` |
| The M2 tester's | `~/Games/Interstate76-MP/Interstate 76 Nitro.app` | his Mac was asleep all night. See below |

**The M2 tester Mac** was asleep, so it still has the old app. That app closes the game after 2-3 minutes and does not have
the GAME TYPE choices. With his Mac awake, run this on the developer's MacBook in Terminal:
`bash ~/i76-nitro-mp-lab/update-m2.sh`. It makes the backup itself and prints the undo line. (A watcher on the PC
tries this every 10 minutes until 09:00 on 2026-10-24, once his Mac has been idle 10 minutes with no game running. Its
log, `<lab>\builds\nitro-weekend-20261023\m2-poll.out`, says whether it ran.)

The PC's `Games\I76\nitro-lan` is a new folder, and deleting it undoes it. The PC's other installs were not changed.

## Gold apps on the Macs (2026-10-25)

Deployed to all Macs (untested PC<->Mac join - the morning family game is the first test; rollback = `_rollback-final-20261025` inside each
Gold app's game folder): proxy 5d6f9828 + the six new `auto*.lvl`, `ai_hs2/4/6` removed, on the MacBook, the M4 Max tester's and the M2 tester's Gold apps.
Details: [records/LAN-FIXES-2026-10-24.md](records/LAN-FIXES-2026-10-24.md) s.12.

**Steam Deck (2026-10-25):** the same Gold set: proxy 5d6f9828 + the six `auto*.lvl`, `ai_hs*` removed (rollback
`game/_rollback-final-20261025`), plus the free graphics keys (no fps loss, n 2) and the rumble shim. The LAN switches are now in
the Deck's main `i76-env.sh`, so the existing library entry (launch options unchanged: `"/home/deck/Games/Interstate76/i76-deck-launch.sh"
%command% -glide`) goes straight to the IPX screens. **A Deck join on this set is not yet measured** (the lab host's IPX instance is
isolated from the LAN; the owner's console was then in use). Keep the Deck awake during a game. Record:
[records/DECK-2026-10-25.md](records/DECK-2026-10-25.md).
