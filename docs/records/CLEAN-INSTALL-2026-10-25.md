# Clean-install test on the Win11 laptop, 2026-10-25 (PARTIAL: blocked by the locked console)

Owner's ask: wipe the Windows 11 laptop's bench and rerun the install as a user would. Lane: clean-install (Sonnet). Laptop
LAPTOP-HPK11OMS (192.168.1.77, Win11 26100). Kit: GitHub release **v0.7.3** (the only one; no v0.7.4 draft),
`Interstate76-Patch-Kit-i76-everywhere-v0.7.3-f5d5ac0.zip`, md5 84b977c5, 4,187,799 B (same as the lab's build).
Working files and screenshots: lab `i76-uncap-lab\clean-install\` (`out\`, scripts).

## Verdict in one paragraph

Everything that does not need a picture was done and passes: wipe, pristine GOG layout, unblock, extract, first-run setup,
uninstall (371 of 371 files md5-identical afterwards). **Every step that needs the game on screen was NOT run**: the laptop's
console was on the Windows lock screen ("Dismiss the lock screen to sign in", screenshots at 05:38, 05:49, 05:51), so a boot
would show no picture and take no keys (coordinator: do not run on a locked desktop). The owner has to set the laptop to stay
awake / not lock. The Nitro half waits for the installer lane's Build-From-GOG fix (dgVoodoo 2.87.5; see NITRO-WIN11-2026-10-25.md).

## Step table

| # | step | verdict | notes |
|---|---|---|---|
| 1 | wipe `C:\i76-bench\` | done, with a deviation | deleted: controls, kit-a, rc-twin, rc-twin-dgv2875, scott-a, scott-b, scott-b.zip, scott-gog, wmr, wmr-twin, 10 old job/probe scripts, `runs\` older than today (list: lab `clean-install\wipe-list.txt`). **Kept** (deviation: the Nitro lane was using them live at 05:24-05:40): `.fps-lock`, `nitro-a/b/gog`, `parity-nitro`, `dgv`, `dlls`, `tools`, the bench scripts, `itask*.ps1`, `nitro-boot.ps1`, `job-i76bench-*.ps1`, today's `runs\`. Free space 45.9 GB. |
| 2 | pristine GOG Gold layout | PASS | PC `i76-map\sandbox-gog\main\app` (GOG 2.1.0.17, i76.exe 9a232dcc) copied by scp to `C:\i76-bench\clean\GOG Games\Interstate 76` (a path with spaces, like a real install): 371 files, md5 list made from the same source, **0 bad**, 16 s. No separately recorded md5 list exists in the records (only the count 371). Nitro pristine (520 files, nitro.exe 28b8ae27) not laid down yet (waits). |
| 3a | download | PARTIAL | `gh release download v0.7.3` on the PC, scp to the laptop, Zone.Identifier ZoneId=3 added by hand to imitate a browser download (the laptop has no gh; deviation). |
| 3b | Unblock + extract into the game folder | PASS | `Unblock-File` (stands in for Properties -> Unblock) then `Expand-Archive`: 1.1-1.3 s, +95 files, 0 GOG file changed (371 md5 still identical), 0 files carry the download mark. The README in the zip is byte-identical to `tools\patch-kit\README.md`. |
| 3c | `PLAY.bat` first run (setup) | PARTIAL | game part not run (locked). The setup alone was run once as `PLAY.bat --setup` over ssh in session 0: **3.3 s**, exit 0 (lab `out\setup-session0.txt`). It read the display as **1024x768** (session 0 has no monitor), an artifact of my route; but see items 1-4 below. That folder was then uninstalled and replaced by a fresh pristine copy plus a fresh extract, ready for the real first run. |
| 3d | PLAY-PREVIEW.bat, PLAY-T05.bat, `--display`, `--no-supersample` | NOT RUN | locked console |
| 3e | mciproxy.log / play-i76.log lines, screenshots at menu / T05, 0-CRASH check | NOT RUN | locked console |
| 3f | `UNINSTALL-i76e.bat` | PASS | 1.7 s; restored i76shell.dll, i76.exe, shell keys, Strlkup.dll, I76PLYR.DEF, input.map, the three Glide files; **all 371 files md5-identical to pristine**. Left behind: PLAY*.bat x4, README, UNINSTALL bat, `_i76e`, 4 backup files, plus 14 `save*.cmp` and `savegame.dir` (the kit's campaign saves; README says they stay). |
| 3g | reinstall | PARTIAL | fresh pristine copy + unblock + extract repeated (PASS, same numbers); first run on it not run (locked). |
| 4 | Nitro via `Build-From-GOG.ps1` | NOT RUN | waits for the installer lane's fix (the script still fetches dgVoodoo 2.87.3, which crashes the laptop at frame 0). |

## README / script wording problems

1. **The setup ends with "Press any key to continue . . ."** (after `--setup`; UNINSTALL asks at the start and at the end). The
   README says "about ten seconds ... then the game starts" and nothing about key prompts. The setup took 3.3 s, not ~10 s.
   Proposed README line: "A window may ask you to press a key; do." (or drop `pause` from the success path of PLAY.bat).
2. **The setup text names the developer**: `graphic detail: GOG's defaults -> the levels James plays with`. The README was
   de-personalised; this output was not. Proposed: "the levels the developer plays with".
3. **Developer-speak in the user's black window**: "the daily-driver conf of 2026-10-03", "promotion 11", "gated 2026-10-08
   (twin, driver promotion 15)", "-Preset tick19-42 has NOT been run on this build ... re-run with -Preset stock", "-AllowNarrow",
   "Check in Instant Melee ... Mission 5's ramp jump", "PLAY-i76.bat starts preset tick19-42". A user cannot act on these, and
   `-Preset` is not a documented option. Proposed: print a user summary (display, build detected, what changed, "done") and send
   the rest to `_i76e\setup.log`.
4. **The yellow MD5 line reads like a failure**: "i76.exe MD5 = 9a232dcc... - NOT the GOG 2019 build (60abf7bc...) the presets
   were gated on. Setup continues. Preset tick19-42 has NOT been run on this build". The README says it is normal. Proposed line:
   "i76.exe is GOG build 2.1.0.17; expected, nothing to do."
5. **README uninstall list**: it says to delete "the PLAY*.bat files, README-PATCH-KIT.md and the _i76e folder"; UNINSTALL's own
   output also names UNINSTALL-i76e.bat, and the README's launcher table lists PLAY-16x10 / balanced / stock / i76.bat as
   "written by the setup" (the uninstall removes those; I did not see them on disk). Proposed: "delete the four shipped PLAY*.bat,
   UNINSTALL-i76e.bat, README-PATCH-KIT.md and `_i76e` yourself".
6. README step 2 says that if Unblock is forgotten the launcher clears the download mark itself: not tested (I unblocked first).

## Bugs and observations

- **B1 (environment, blocks the whole test): the laptop console locks.** Lock screen at 05:38, 05:49 and 05:51 (lab
  `out\gold-play1.shot30.png`, `shot50.png`, `now.png`). A probe with `OpenInputDesktop(read access)` says UNLOCKED on the lock
  screen, and LogonUI.exe is always resident, so neither is a usable lock test for the lane scripts; use a screenshot (the task
  does capture the lock screen) or `OpenInputDesktop(DESKTOP_SWITCHDESKTOP 0x100)`, not verified. The owner must disable the
  lock / sleep (sign-in requirement, screen-off timeout, Dynamic Lock / Windows Hello).
- **B2: the setup reads the display in a no-desktop session as 1024x768 and writes confs for it** (Glide 2048x1536,
  `I76_ASPECT = '1024x768'`). A real user is on the desktop, so cosmetic; whether the next interactive start rewrites it was not
  verified.
- **B3: the lane scripts share one scheduled task name (`i76bench`) and `job.ps1`**: two lanes at once overwrite each other. I
  used my own task `i76clean`.
- **B4: the Nitro lane and I share `.fps-lock`; it runs back to back, the gaps are seconds**: my waiting script waited 412 s once
  before it got the lock (the later run was stopped before it started, because of the lock screen).

## What a real GOG Galaxy user would see that this test cannot show

- Galaxy installs to `C:\GOG Games\Interstate 76` or under `C:\Program Files (x86)\GOG Galaxy\Games`: the Program Files case
  (access denied row) was not tested; my path is under a user-owned directory.
- The Galaxy overlay (README row "close GOG Galaxy's overlay"), Galaxy cloud saves of `save*.cmp` / `I76PLYR.DEF` (the setup
  copies campaign saves; Galaxy may upload or overwrite them), and Galaxy's auto-update / verify-repair touching changed files.
- The exe Galaxy delivers: the lab's pristine is 9a232dcc (2.1.0.17, from an offline-installer extraction); a Galaxy folder may
  carry extra files (galaxy DLLs, `goggame-*.info`, `unins000.*`) and the other i76.exe build the README mentions; only 9a232dcc
  was exercised.
- A real browser download (Mark-of-the-Web, SmartScreen, Defender prompts on the BAT / PS1 / DLLs): I imitated the mark with a
  Zone.Identifier stream only.
- A monitor other than 1920x1080, a gamepad, Remote Desktop.

## Top 5 fixes needed

1. Make the laptop stay awake and unlocked, and make the lane scripts detect the lock reliably (screenshot or
   `OpenInputDesktop(0x100)`); until then no picture test there is valid.
2. Trim the first-run window to a user summary; move developer-speak and "James plays with" to `_i76e\setup.log` (items 2-4).
3. Tell in the README that a "Press any key" prompt appears and that setup takes seconds; add UNINSTALL-i76e.bat to the
   delete-yourself list (items 1, 5).
4. Build-From-GOG.ps1 must fetch dgVoodoo 2.87.5 with the 2.87.3 fallback (the installer lane has it) before the Nitro half.
5. Re-run steps 3c-3g and 4 once the screen is available. The laptop folder `C:\i76-bench\clean\GOG Games\Interstate 76` is
   ready (pristine + fresh extract, first run not done); lab `clean-install\run.sh` drives it, for example
   `./run.sh "-Tag gold-play1 -Cmd PLAY.bat -Hold 160 -Shots 20,50,100,150 -Esc 75"`.
