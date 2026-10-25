# Clean-install test on the Win11 laptop, 2026-10-25

Owner's ask: wipe the Windows 11 laptop's bench and rerun the install as a user would. Lane: clean-install (Sonnet). Laptop
LAPTOP-HPK11OMS (192.168.1.77, Win11 26100.9711, 1920x1080, console unlocked after 06:40). Kit: GitHub release **v0.7.3** (the only
one; no v0.7.4 draft), `Interstate76-Patch-Kit-i76-everywhere-v0.7.3-f5d5ac0.zip`, md5 84b977c5, 4,187,799 B. Evidence (screenshots,
logs, scripts): lab `i76-uncap-lab\clean-install\` (`out\`). An earlier pass of this record stopped at 05:5x because the console was on the
lock screen; this is the full run.

## Verdict

**Gold passes as a user would run it**: fresh GOG folder, unblock, unzip, first `PLAY.bat`, PLAY-PREVIEW, PLAY-T05, PLAY-PREVIEW-T05,
`--no-supersample`, `--display`, uninstall (371 of 371 files back), and reinstall + first run, all on Windows 11 24H2 with 2.87.5, and no
`CRASH` line other than the known frame-0 probe (`exe+0x99997`). **Nitro works only after three things a user cannot do or does not
know**: `Build-From-GOG.ps1` has a download bug, needs MSVC and a repo clone, and there is no Nitro kit. Details below.

## Step table

| # | step | verdict | notes |
|---|---|---|---|
| 1 | wipe `C:\i76-bench\` | done, one deviation | deleted controls, kit-a, rc-twin, rc-twin-dgv2875, scott-a/b/gog, scott-b.zip, wmr, wmr-twin, old job/probe scripts, `runs\` of 10-24 (list: lab `wipe-list.txt`). **Kept** the live Nitro-lane items (`nitro-a/b/gog`, `parity-nitro`, `dgv`, `dlls`, `tools`, bench scripts, lock). 45.9 GB free. |
| 2 | pristine GOG Gold (2.1.0.17, i76.exe 9a232dcc) | PASS | copied from `i76-map\sandbox-gog\main\app` to `C:\i76-bench\clean\GOG Games\Interstate 76`: 371 files, md5 list from the same source, 0 bad. (No separate recorded md5 list exists, only the count.) |
| 3a | download v0.7.3 | PASS (deviation) | `gh release download` on the PC, scp, Zone.Identifier ZoneId=3 added by hand (no browser). |
| 3b | Unblock + extract into the game folder | PASS | `Unblock-File` + `Expand-Archive` 1.1 s, +95 files, 0 GOG files changed, 0 files with the download mark. Zip README = repo README. |
| 3c | `PLAY.bat` first run | **PASS** | setup + start: game process up 4.6 s after the double-click (setup 3.3 s), display read as 1920x1080, `[Glide] 3840x2160`. 15 s: intro text; 45 s: intro movie (car); after Esc at 80 s: main menu (OPTIONS / EXIT / TRIP / MELEE, pointer drawn) at 100 s and 140-160 s. `aspect: D 1.778 20/20 sites`. Log: 1 `CRASH` event (4 lines) = the frame-0 probe `exe+0x99997`, plus `coop-ai: ai_FrameTick UNEXPECTED bytes` (LAN-only, expected). Shots: `out\gold-play1.shot*.png`. Alive at the end of 160 s. |
| 3d | `PLAY-PREVIEW.bat` | PASS | same: alive, menu after Esc (shot125), 1 probe event, `view z 120 -> 2300 m`, coop-ai x3 UNEXPECTED (LAN-only). |
| 3e | `PLAY-T05.bat` | PASS | straight into mission 5 at 2.1 s, hood/cockpit view with HUD and mirror, picture correct (shot100), alive 110 s, 1 probe event. Frame log: median frame 16.8 ms (60 fps, idle at the start spot, laptop GPU, 2x supersample), p99 24.8 ms. |
| 3f | `PLAY-PREVIEW-T05.bat` | PASS | alive, median 17.9 ms (56 fps), p99 24.9 ms, 1 probe event. |
| 3g | `--no-supersample` (`PLAY-T05.bat --no-supersample`) | PASS | setup message "render target x1", `[Glide] 1920x1080`; alive; median 12.6 ms (80 fps), p99 16.6 ms. No probe CRASH line was logged in this run (3 lines of other matches only). |
| 3h | `--display 1280x720` | PASS | message "display: 1280x720 (--display), render target x2", `[Glide] 2560x1440`; alive, picture fills the 1080p screen correctly (16:9 either way, so this does not test a different shape); median 13.8 ms (73 fps). |
| 3i | `UNINSTALL-i76e.bat` (twice) | PASS | 1.1-1.7 s; first time (no game run) **371 of 371 identical to pristine**; second time 370 of 371: `Lee.fot` differs in content only (same size 1,409 B, written 07:06 = the game's own write while I ran it, not the uninstaller). README's "every file byte-identical" holds only until the game has been played once. Left on disk as README says: 4 PLAY*.bat, UNINSTALL bat, README, `_i76e`, 4 backup files, 14 `save*.cmp` + `savegame.dir`. |
| 3j | reinstall + first run | PASS | README's delete list, fresh extract (0.9 s), `PLAY.bat`: process up 4.6 s, menu reached, same single probe event. |
| 4 | Nitro via `Build-From-GOG.ps1` | PARTIAL, see bugs 5-8 | on the PC (the laptop has no MSVC), 2.87.5 DLLs given by hand: build exit 0 in 16 s; the 548-file folder copied to the laptop (DDraw.dll c70a0ee6 = 2.87.5, Strlkup ac66cf20, nitro.exe 28b8ae27). `PLAY-Nitro.bat`: process up 2.1 s, title screen "Interstate '76" at 125 s, alive, 0 `CRASH` lines (4 "Nitro PIT probe ... not counted" lines), `nitro: 125 sites patched, 0 refused`. Direct boot `PLAY-i76.ps1 -Exe nitro.exe -Mission P01.msn` (with `-GameDir`): mission rendered, alive 100 s, `sim-tick: ON ... 12/12 sim gates`, 0 CRASH. Main menu click-through and driving not done. The first frame of P01 shows only sky and a tall dark pillar, the HUD at 95 s is enlarged and cropped (shot40 / shot95): not explained (start camera? 1920x1080 on `nitro-tick42` aspect keys?), needs the Nitro lane's eyes. |

## README / script wording problems (Gold)

1. **The setup ends with "Press any key to continue . . ."** (also UNINSTALL at the start and the end). README says nothing about key
   prompts; "about ten seconds" is 3-4 s. Proposed: "A window may ask you to press a key; do."
2. **The setup text names the developer**: `graphic detail: GOG's defaults -> the levels James plays with`. Proposed "the developer plays with".
3. **Developer-speak in the user's window**: "the daily-driver conf of 2026-10-03", "promotion 11", "gated 2026-10-08 (twin, driver promotion
   15)", "`only 4608x2880 / 1680x1050 has been run`", "`-Preset tick19-42 has NOT been run on this build ... re-run with -Preset stock`",
   "`-AllowNarrow`", "Check in Instant Melee ... Mission 5's ramp jump", "PLAY-i76.bat starts preset tick19-42". `-Preset` is not a
   documented option. Proposed: user summary on screen, the rest to `_i76e\setup.log`.
4. **The yellow MD5 line reads like a failure** ("NOT the GOG 2019 build ... the presets were gated on ... has NOT been run on this build");
   README calls it normal. Proposed: "i76.exe is GOG build 2.1.0.17; expected, nothing to do." (The whole 9a232dcc build ran clean on
   Win11 here; the line is also stale.)
5. **README says PLEASE STAND BY for up to a minute**: here intro text appeared within 15 s and the menu was reachable at about 85 s with Esc
   at 80 s; the first on-screen text is a story card, not a "PLEASE STAND BY" screen. Proposed: "a black window or a text card for a while".
6. **README uninstall list** omits `UNINSTALL-i76e.bat` itself (the script's own message names it) and the `Lee.fot` note above; proposed:
   "delete the four shipped PLAY*.bat, UNINSTALL-i76e.bat, README-PATCH-KIT.md and `_i76e` yourself; the game itself rewrites
   `Lee.fot` as you play, so a hash check after play shows one difference."
7. README troubleshooting rows `--display` / `--no-supersample` match the behaviour; `--display WxH` also changes the render size, not only
   the shape (1280x720 renders at 2560x1440 supersampled), worth one clause.
8. Not tested: forgetting Unblock (launcher clears the mark itself); the dgVoodoo global conf row; Remote Desktop; Program Files install.

## Bugs

- **B1 (environment): the laptop console locked at 05:38-05:51** (lock screen screenshots). Resolved by the owner at about 06:40.
  Lane scripts' LogonUI test is useless (LogonUI.exe is always resident on this build; `OpenInputDesktop(read)` also says unlocked on the lock screen).
- **B2: the setup in a no-desktop session (ssh) reads the display as 1024x768** and writes 4:3 confs; a real user is on the desktop. Not
  seen in the interactive runs (1920x1080).
- **B3: shared scheduled-task name `i76bench` and `job.ps1` across lanes** (I used `i76clean`); `.fps-lock` is taken back to back by the Nitro lane
  (my waiting script waited 412 s once).
- **B4: README troubleshooting is right that Gold's single frame-0 `CRASH` event prints 4 lines** (`code`, `stack`, `modules`, `exe code addresses`);
  a user grepping "CRASH" sees 4 lines and may count 4 crashes. Proposed: print one line, or prefix the probe `PIT probe (handled)` the way Nitro does.
- **B5 (`tools\Build-From-GOG.ps1`, commit 76227ce): the dgVoodoo download URL is wrong.** `Get-DgVoodoo '2.87.5'` builds `$u = '2_87_5'` and then
  names the file `dgVoodoo2_$u.zip` = `dgVoodoo2_2_87_5.zip`, which is a 404 (`Invoke-WebRequest : Not Found`, script line 57). It only works where
  `%LOCALAPPDATA%\i76e-cache\dgVoodoo2_87_5` already exists under the right name. A fresh user machine fails before building anything.
  Fix: `$u = $ver.Substring(2).Replace('.', '_')` (the release asset is `dgVoodoo2_87_5.zip`, tag `v2.87.5`).
  Workaround used: `-DgVoodooDir` / `-DgVoodooFallbackDir` pointing at the cache dirs.
- **B6: Build-From-GOG needs git, a repo clone and the VS 2019 Build Tools (C++ x86)** (it compiles the proxy). The laptop has git but no `cl`: a Nitro
  player cannot run the documented command. There is no Nitro patch kit. Needed: a Nitro zip like Gold's, or `Build-From-GOG.ps1 -Proxy <prebuilt dll>`.
- **B7: `build-proxy.ps1` calls `tar`; with Git for Windows' `usr\bin` earlier on PATH it picks GNU tar** and fails with "Cannot connect to C: resolve
  failed" (hit from this session's Git-bash PATH). Use `%SystemRoot%\System32\tar.exe`.
- **B8: Build-From-GOG's `-Display` defaults to the build machine's primary monitor** (3440x1440 here, built on the PC); correct for a user building on
  their own PC, wrong when building elsewhere (passed `-Display 1920x1080`). Also `PLAY-i76.ps1` run by hand without `-GameDir` defaults to
  `C:\Games\Interstate 76` (my first P01 run started nothing; only the bat passes `-GameDir`).
- **B9: Nitro P01 direct boot shows an odd start frame** (sky + pillar, then an enlarged HUD): see step 4.

## What a real GOG Galaxy user would see that this test cannot show

- Galaxy installs to `C:\GOG Games\Interstate 76` or under `C:\Program Files (x86)\GOG Galaxy\Games`; the Program Files "access denied" row was not tested
  (my path was user-owned, with spaces).
- The Galaxy overlay (README says to close it), Galaxy cloud saves of `save*.cmp` / `I76PLYR.DEF` (the setup copies campaign saves; cloud sync may
  upload or overwrite them), Galaxy auto-update / verify-repair touching changed files, and Galaxy's own launcher starting `i76.exe` instead of `PLAY.bat`.
- The exe Galaxy delivers: the pristine used is 9a232dcc from an offline-installer extraction; a Galaxy folder may carry extra files (`goggame-*.info`,
  `unins000.*`, Galaxy DLLs) and the other build the README mentions; only 9a232dcc was exercised.
- A real browser download (Mark-of-the-Web, SmartScreen, Defender prompts on the BAT / PS1 / DLLs): only a Zone.Identifier stream was imitated.
- A different monitor shape (only 1920x1080 here, `--display` was a same-shape test), a gamepad or wheel, Remote Desktop, a non-admin vs admin
  account difference (the account is the owner's).
- Mouse / keyboard in the menus was not driven (screens were reached by Esc only; no click-through to a mission via the menu on Gold).

## Top 5 fixes

1. **Fix `Build-From-GOG.ps1`'s dgVoodoo URL** (B5) and add a prebuilt-proxy option or a Nitro kit, so a Nitro player needs neither MSVC nor a clone (B6).
2. **Trim the first-run window** to a user summary; move developer-speak and "James plays with" to `_i76e\setup.log`; rewrite the MD5 line (items 2-4).
3. **README**: the "Press any key" prompt, the real setup time, no "PLEASE STAND BY" promise, UNINSTALL-i76e.bat and `Lee.fot` in the uninstall text (items 1, 5, 6).
4. **Print the frame-0 probe as one handled line** so "CRASH" greps do not show 4 lines (B4); Nitro's wording already does this.
5. **Look at the Nitro P01 start frame at 1920x1080** (B9) and click the Nitro menu through to a mission and a drive; then make the laptop stay unlocked and
   replace the LogonUI test in the lane scripts (B1, B3).
