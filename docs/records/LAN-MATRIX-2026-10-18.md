# LAN matrix, 2026-10-18 night: who can host, who can join

Goal (owner): network game tests across the PC, James's laptop, Michael's and Andrew's Macs and the Steam Deck,
every machine joining and hosting, with evidence, plus stable instructions (docs/MULTIPLAYER.md section 8). Tools:
`tools/lan-test/` (README). Evidence standard: both cars in both position tables (`0x54E11C`, probe `pos`), the
stationary car at the same coordinates on both ends, the far table following a car while it drives; IPXWrapper debug
logs; shell framebuffer pictures where useful. n = number of joins.

## 0. Result (updated 07:30 after the morning resume)

Rows host, columns joiner. PASS = joined, every car in every table, each machine's driving seen on the others.

| host \ joiner | PC | Andrew's Mac | Michael's Mac | laptop | Deck |
|---|---|---|---|---|---|
| **PC** | - | **PASS n 2** (cells 2, 6) | blocked: firewall box not answered | blocked: game window not frontmost | **PASS n 1** (cell 6) |
| **Andrew's Mac** | **PASS n 1** tonight (cell 3; n 2 more earlier in the night) | - | blocked (firewall) | blocked (front) | **PASS n 1** (cell 1) |
| **Michael's Mac** | blocked: its IPX start fails until the firewall box is answered | blocked | - | blocked | blocked |
| **laptop** | blocked: no click reaches the game (cell 7) | blocked | blocked | - | blocked |
| **Deck** | not run | **FAIL n 1** in The Crater (cell 5: mission files differ); melee not run | blocked | blocked | - |

- **3 players: PASS n 1** (cell 6: PC host, Deck and Andrew's Mac join, all three drove, all three tables agree).
- **5 players: not run** - Michael's Mac and the laptop could not join (below).
- **Clicks the owner still has to do:**
  1. **Michael's Mac:** the box *Do you want the application "wine" to accept incoming network connections?* is on his
     screen now (UserNotificationCenter window, 260x282 at 626,189, up since 07:15). Click **Allow**. Until then the
     game's IPX start fails (Wine "Error" box; IPXWrapper log "Router thread didn't exit"). It cannot be pressed
     remotely: osascript / System Events needs Accessibility for sshd and only hung (killed after 12 s; a second box
     appeared meanwhile and was gone by 07:25 - if a box asks to let "sshd-keygen-wrapper" control "System Events",
     click **Don't Allow**). No microphone box appeared in his launch (07:15, window list checked).
  2. **James's laptop:** Terminal is the front app, and macOS 26 refuses to bring wine forward from SSH
     (`NSRunningApplication.activate` returned true, the front app stayed Terminal; a restart via `open` the same).
     While wine is not frontmost the game's pointer stays frozen (mouse object 2,240 whatever the pointer does), so no
     click lands. Click once into the I76 MP GATE window, then the laptop cells can run.
- Crashes: none (n 7 sessions). Host handover: section 4.

## 1. Builds on each machine (md5, read 2026-10-18 00:40-01:05)

| machine | i76.exe | STRLKUP | i76shell | ipxwrapper | notes |
|---|---|---|---|---|---|
| PC LAN copy | 6319abf7 | 33211f11 | a300db63 | 06a01d0f | `PLAY-LAN.bat`, best-wide + co-op switches, u32x 06467bd2 |
| Andrew's Mac | 6319abf7 | 33211f11 | a300db63 | 06a01d0f | the pack (rollout record), firewall off, unlocked (Minecraft holds the display awake) |
| Michael's Mac | 6319abf7 | 33211f11 | a300db63 | 06a01d0f | the pack, firewall **on**, no wine entry in `socketfilterfw --listapps`, screen **locked** all night |
| laptop gate clone | 6319abf7 | 33211f11 | a300db63 | 06a01d0f | `I76 MP GATE.app`, firewall off, screen **locked**, displays asleep |
| Steam Deck | f92b8a7e | 8bc52939 | 8960fa16 | 06a01d0f | its own pack (not the LAN pack): GE-Proton10-12, `WINEDLLOVERRIDES` wsock32/mswsock native, `I76_CURSOR_MAP=1`, `I76_PAD_MENU=1`; own `ADDON\valepre4.vcf` 4ed297ca (not stock) |

All on 192.168.1.0/24. Network both ways was proven earlier in the night (pktmon, UDP listeners, both IPXWrapper logs).

## 2. Cells

Times CDT. Positions are the probe's `pos` (position table 0x54E11C) unless marked "player table" (car +0x40/+0x50).

**Cell 1 - Andrew's Mac hosts Suburbia (m04), the Deck joins. PASS, n 1.** Andrew: nav + BROADCAST (session renamed
"zqxandrew"), net 1, me = host = 3. Deck: JOIN > IPX, row, JOIN GAME: net 1, me 6, host 3. At rest (01:11:3x) both
tables: host car 4732.48, 120.94, 49317.50 on both ends (identical), Deck car 4172.52, 120.73, 49552.50 on both ends.
Deck drove 60 s (W + steer pulses, 01:12:00-01:12:57): Andrew's table followed it 4384 -> 5032 -> 4507 (x) in step with
the Deck's own samples. Andrew drove 40 s (01:13:53-01:14:30): the Deck's table followed 4542 -> 4008 -> 4007 (x),
matching Andrew's own 4498 -> 4007. The Deck's car crept by +-10 m while "parked" on both ends alike (the Deck's own pad
layer / stick drift; not chased).

**Cell 2 - the PC hosts Suburbia ("pchost"), Andrew's Mac joins. PASS, n 1.** PC LAN copy (PLAY-LAN.bat, console lock
01:51-02:02). Andrew on JOIN > IPX: `find pchost` hit the session record (0x01f22328) before the click; `joingo` with the
real pointer warped onto the row and JOIN GAME: net 1, me 6, host 3 on the first try. At rest (01:53:3x) the two tables
were identical: PC car 4272.52, 120.94, 49437.50 and Mac car 4862.48, 120.94, 49542.50 on both ends (n 3 samples).
Mac drove 60 s (01:53:49-01:54:47): the PC's table followed 4691 -> 4358 -> 4519 / 49661 in step. PC drove 40 s
(01:55:05-01:55:40): Andrew's table followed 4395 -> 4382 / 49707. Final pair a second apart: 4380.66 / 4380.59 and
4499.04 / 4498.59 (cars still rolling).

**Cell 3 - Andrew's Mac hosts Suburbia ("andrewhost"), the PC joins. PASS, n 1** (the direction proven twice earlier
in the night). PC: net 1, me 6, host 3; at rest both tables: host car 4272.52, 120.94, 49327.50, PC car 4172.52, 120.94,
49437.50 on both ends. PC drove 30 s, Andrew's table followed (4351 -> 4927 -> 4830). Andrew drove 30 s: the PC's
**position table** stopped updating Andrew's car at 02:00:16 (4399.06, 49148.96 frozen) while Andrew's car went on to
4400.4, 49054.2; the PC's **player table** had it right (4400.4, 49054.2 on both ends at 02:01). So the position table is
not authoritative for a far car (it was ~600 m away by then) [inferred: a draw-side table]; use `state` (player table)
for remote cars. Andrew kept receiving the PC car the whole time.

**Cell 4 - the Deck (migrated host of "zqxandrew") hosts, Andrew's Mac joins. Partial.** List filled on the Mac
(session record and the framebuffer picture, section 3); with the real pointer on JOIN GAME the Mac sent the join
(17 + 54 bytes) and the Deck answered (91 ... 255 bytes) at 01:27; the Deck then suspended, so arena entry was not
measured here (it was in cell 2).

**Cell 5 - the Deck hosts, Andrew's Mac joins (07:20). FAIL n 1, cause found.** The Deck's host form row at y 208
started **The Crater (m01)**, not Suburbia (its arena list differs). Andrew joined (net 1, me 6, host 3) but his own car
never spawned: player table `nan,nan` on both ends; Andrew's proxy log "coop-ai: role joiner ... mission m01.msn ...
mission cars alive 5". The LAN pack's `miss8\M01.MSN` is the co-op T01 mission (000869bb); the Deck runs its own pack
with the stock m01, so host and joiner loaded different missions. Fix: give the Deck the LAN pack (common part), or
never pick The Crater when the Deck is in the game. A Deck-hosted melee was not run.

**Cell 6 - 3 players: the PC hosts Suburbia ("pchost"), the Deck and Andrew's Mac join (07:22-07:27). PASS n 1.**
Deck: net 1, me 6; Andrew: net 1, me 8; the PC's table lists ids 3, 6, 8. At rest all three player tables identical:
3 at 4272.5, 49437.5; 6 at 4862.5, 49542.5; 8 at 4172.5, 49327.5. All three drove 25 s at once; afterwards the three
tables agreed within the motion between the sequential samples (id 6: 3981.5 / 3982.8 / 3984.3; 15 s later
4011.8 / 4012.6 / 4012.6, cars still coasting).

**Cell 7 - the laptop (unlocked) as host.** Started, main menu reached by Esc; every click missed (main menu, n 9
tries; calib2 read the mouse object frozen at 2,240). Front app: Terminal. Section 0, click 2.

**Cell 8 - Michael's Mac (unlocked) as host.** Started 07:15 (audio muted first, restored to unmuted after), main menu,
calib2 worked (map 2.364 1.4 2.041 4.1), MELEE > MULTI MELEE > HOST > IPX reached; the firewall box appeared at once
and the game showed a Wine "Error" box (IPX could not start). Section 0, click 1.

## 3. Why the Mac joins "failed" earlier in the night: the automation, not the game

Earlier tonight every Mac join stopped on the ENTRY ROSTER: net stayed 0 and the Mac sent no join request. Measured:

1. **The join list fills on the Mac.** With the Deck hosting (session "zqxandrew"), Andrew's IPXWrapper delivered the
   host's 85-byte broadcast every second, the session record sat in the shell's list (`[shell+0xf21a0]`: count 1,
   record 0x01f22328 "zqxandrew", host node B7:CE:7C:20:E4:2C, players 1 of 4), and the shell's back buffer
   (`fbshot.sh`) showed "zqxandrew (1/4)" in the GAME NAME list, selected.
2. **JOIN GAME was pressed somewhere else.** The entry forms (EntryForm_Frame 0x10028610) hit-test the shell mouse
   object `[[0x100cc514]+0x2c/+0x30]` (decompiled frame, lines 51-63). On the Mac that object followed the **real
   macOS pointer**: it read 402,240 and then 300,240 while the probe "clicked" all over the form, and moved to
   exactly the warped point after `cur` (`CGWarpMouseCursorPosition`) - 200,100 -> UI 67,53 and 1200,700 -> 527,373
   (client offsets), i.e. `UI x = (client x - 54.3) / 2.174`, `UI y = client y / 1.875`. The probe, started over SSH,
   has no Mac driver, so its SendInput moves only Wine's server cursor. CANCEL did nothing until a raw client click
   happened to put the real pointer on it.
3. **With the real pointer on JOIN GAME, the Mac joined at the protocol level.** Warp to (735,857) = UI 300,457,
   buttons only: Andrew's IPXWrapper log shows the join request (17 + 54 bytes to the host) at 2012946.01 and the
   host's answers (91, 105, 53, 41, 29, 18, 255 bytes), the same sequence the Deck sent as a working joiner
   (17 / 54 / 4 ... at 2710.56). The host then disappeared (the Deck suspended, section 4), so the arena entry is
   measured in the PC cell below, not here.
4. The press itself was seen by the game every time: during a held press `[mouse+0x34]` = 1 and `[mouse+0x10]` = 2.

So "the Mac sends only two 4-byte packets and never a join request" was a measurement artifact of remote clicking.
A player with a real mouse is not affected (the real pointer is where they click). Not tested here: the macOS
firewall and microphone prompts on Michael's Mac (locked screen all night).

## 4. What blocked the other cells

- **Locked Macs (Michael's, the laptop):** keys reach the game (Esc opens and closes the Esc menu), clicks do not:
  SendInput (n 30+ on a grid across the main menu row), posted WM_LBUTTONDOWN, a real-pointer warp plus buttons, and
  holding the mouse object at the target (rewritten every ~1 ms) all left the main menu unchanged. The game window
  is Wine's foreground window; the laptop's displays reported asleep, both screens locked (`IOConsoleLocked` true).
  Nothing that can be done over SSH without a password unlocks them. These cells need a person to unlock the Mac.
- **Steam Deck:** suspended about 20 minutes after its game started (it still answered the Mac's join at 01:27; ping and SSH dead from ~01:29;
  host migration to the Deck seen at ~01:16). Game Mode suspends on its own after a stretch without physical input;
  our input goes into Wine, not into Steam. It cannot be woken over the network.
- **Host migration** (the "handover" seen on 2026-10-17): when the host quits, ANet hands the session to a remaining
  player. Measured: Andrew (host 3) quit; the Deck's table then read `host 6` (itself), still in Suburbia, and kept
  broadcasting the session (85-byte packets, name "zqxandrew" carried over). Later, after the Deck vanished, Andrew
  (by then a joiner of that session) began sending the 85-byte broadcasts himself. So a handover is ANet's normal
  host migration, triggered by the host leaving; tonight's cause was our own restart / the Deck's suspend.

## 5. Changes made and undone

- Deck: `ADDON\valepre4.vcf` swapped to stock de680a86 for the test (original 4ed297ca kept in
  `~/Games/Interstate76/lan-test-20261018/`), a debug `ipxwrapper.ini` added; both reverted at the end (section 6).
- Andrew's Mac: game restarted 3 times (ours), probe + helper scripts in `/tmp/i76mp` only.
- Laptop: gate clone started (ours), `cur`, `wake`, helper scripts in `/tmp/i76mp`.
- Michael's Mac: `/tmp/i76mp` (probe, scripts, `cur`) only; game never started.

## 6. Cleanup (02:02-02:10)

- PC: LAN copy stopped (our pid 5896 only); debug `ipxwrapper.ini` removed from the LAN copy (its `ipxwrapper.log`,
  3.9 MB, left beside it); console lock released 02:02 (held 01:51-02:02). PC audio stayed muted.
- Andrew's Mac: game stopped (`wineserver -k`, his app's prefix only), debug `ipxwrapper.ini` removed, audio unmuted
  (`output muted` = false, as before we muted it). Our logs copied to `/tmp/i76mp` there.
- Laptop: gate clone stopped (`wineserver -k`, gate prefix). `/tmp/i76mp` keeps the tools.
- Michael's Mac: nothing was started; `/tmp/i76mp` only.
- Deck: suspended with our game, the stock `valepre4.vcf` and the debug `ipxwrapper.ini` in place. A loop on the
  laptop (`/tmp/i76mp/deck-revert-loop.sh`, every 60 s for 14 h, log `/tmp/i76mp/deck-revert.log`) runs
  `tools/lan-test/deck-revert.sh` on the Deck as soon as it answers: stops our game, restores its own valepre4.vcf
  (4ed297ca), removes the ini and the test folder. If the log has no DONE line, run that script on the Deck by hand.


Morning resume (07:13-07:30): the Deck revert loop had run at 07:12 (log DONE: valepre4 4ed297ca back, ini removed).
For cells 5-6 the Deck's valepre4.vcf was swapped to stock again and reverted at 07:27 with `deck-revert.sh` (game
stopped, 4ed297ca back, test folder removed; Deck audio was muted before and stays muted). `caffeinate -d -i -u` on the
three Macs (ours, stopped); `systemd-inhibit` on the Deck was refused (block mode needs authorisation). Games we started
on the PC, Andrew's, Michael's and the laptop stopped (`wineserver -k` per prefix; our PC pid only); Andrew's and
Michael's audio back to unmuted (their prior state). PC console lock 07:22-07:27, released.
