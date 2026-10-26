# Content installer: community maps in the family pack, Patch Kit extras, German voices, extra music (2026-10-25)

Owner's rulings 2026-10-25 (on [CONTENT-FEASIBILITY-2026-10-25.md](../research/CONTENT-FEASIBILITY-2026-10-25.md)): (1) the 10 community maps into
the family pack now, slot 10 = RepoTown USA, Great Oval only as an extra if it tests better; (2) a Patch Kit installer step that
downloads (from the original sites, sha256-checked), converts and installs them, with credits; (3) optional helper apps with an
explanation each; (4) a private "shuffle in the Bullmark tracks" option read from a user-supplied folder; (5) a German-voices option
from a user-supplied German retail folder, switchable per launch.

## 0. Results

- **All 10 maps installed on every machine** of the family LAN, byte-identical (s.1): PC main Gold + main Nitro, and the Gold and
  Nitro apps of the developer's MacBook, the M4 Max tester's and the M2 tester Macs.
- **Patch Kit v0.7.4** with `INSTALL-EXTRAS.bat` (s.2), packed from commit 76227ce, **draft** release v0.7.4 (not published):
  https://github.com/therealjkvalentine/i76-everywhere/releases/tag/untagged-d0fc55f11e63b997d4f7 (draft URL; the tag is created on publish).
  Zip `Interstate76-Patch-Kit-i76-everywhere-v0.7.4-76227ce.zip`, 4,270,229 B, 103 files, md5 c8f3d0d850db6d79e8887064cbe30646,
  sha256 d55d172369e1a79b3099f7409675d79ec85e0ab73021b2b310986cbd6b3a4ec2 (the downloaded draft asset has the same sha256).
  Proxy inside: Strlkup.dll **689cb47c** (clean build of 4ec088e, `tools\build-proxy.ps1`).
- **Proxy:** `I76_VOICES=de|<folder>` (music-fix/voices.c) and `I76_MUSIC_EXTRA=<folder>` + `I76_MUSIC_EXTRA_EVERY=n`
  (music-fix/musicextra.c) (s.3).
- **Tests** (s.4): Gold 5 maps x 2 boots + control, 60 s each, all alive, 0 proxy crash lines; Nitro 5 maps + control + Great Oval,
  hosted 60 s each, all in the mission; German voices and the extra music in a lab twin (log lines, n 2); the kit on the laptop bench
  on a fresh pristine GOG copy: maps + opentrack + Python downloaded and installed, PLAY-T05 3 of 3 alive with head look attached;
  uninstall: all 371 GOG files identical to pristine.
- **Great Oval: out.** It loads and runs as well as RepoTown (s.4.2), not better, and its Nitro port carries the "without the authors
  expressed consent" note; the owner's rule is 10 maps. It stays a lab test file.
- Found on the way: the kit's `DEBUG.bat` could not start (i76debug.py imports `debug_logger`, which neither setup-windows nor the
  packager copied); fixed (both deploy `debug_logger.py` + `debug_haptics.py`), checked on the laptop with the kit's Python.

## 1. Family pack: what is installed where

Converted / staged by `tools\patch-kit\i76e-extras.ps1 -Maps` (the same code the kit runs), from the archive's copies of the original
zips (`-Offline <archive>\community-20261024\dl`, matched by name and sha256). Every output sha256 equals
`tools/content-archive/arena-pack.py`'s output (the pins in `tools/patch-kit/extras.json`; the Nitro files are the published files,
unchanged). Readmes beside the maps (`ADDON\<map>.txt`, Nitro `addon\<map>.txt`), credits in `COMMUNITY-MAPS.txt` in the game folder.

| file (md5) | | file (md5) | |
|---|---|---|---|
| ADDON\rageco.lvl | ab1a82a8 | miss16\gumball.cbt / miss8 | b46f06bb / 84bc8c49 |
| ADDON\rageco.ter | 3f40dd4e | miss16\intercpt.cbt / miss8 | f2e4d030 / 34ccdd6b |
| ADDON\76prcnct.lvl / .ter | 18552b21 / d1a359af | miss16\tex.cbt / miss8 | a2b26a33 / 3e951a8f |
| ADDON\leather.lvl / .ter | 8c3ad620 / 78e5d55a | miss16\offroad.cbt / miss8 | b1a6d5c5 / e95a6478 |
| ADDON\bigville.lvl / .ter | af890a44 / 38f10ee0 | miss16 + miss8\repo.cbt | dc8e15cc (same file) |
| ADDON\drugb.lvl / .ter | 7c3cecf9 / 8c034207 | addon\gumball / intercpt / tex / offroad / repo .ter | 848750cf / 2a124995 / dc6a8b4b / 9deccffe / 87713b90 |
| COMMUNITY-MAPS.txt (Gold) | 0f36c7c0 | COMMUNITY-MAPS.txt (Nitro) | 6a6fd28a |

| machine | folder | files | backup / rollback |
|---|---|---|---|
| PC main Gold | `Games\I76\Interstate 76 Gold\Interstate 76` | 16 new (0 replaced) | md5 inventory of the add-on folders before: `..\_rollback\maps-20261025-054405\before.md5`; the kit ledger `_i76e\extras-installed.txt` lists every file (`i76e-extras.ps1 -GameDir <folder> -Uninstall` takes them out) |
| PC main Nitro | `Games\I76\Interstate 76 Nitro\Interstate 76 Nitro Pack` | 20 new | same (`Interstate 76 Nitro\_rollback\maps-20261025-054405`) |
| The developer's MacBook | Gold app + Nitro app (`~/Applications/Sikarugir/`) | 16 + 20, read back | `<game folder>/_rollback-maps-20261025/` (empty: nothing replaced) |
| The M4 Max tester | `~/Games/Interstate76-MP/Interstate 76.app`, `Interstate 76 Nitro.app` | 16 + 20, read back | same (holds the first credits text) |
| The M2 tester | `~/Games/Interstate76-MP/Interstate 76 Gold.app`, `Interstate 76 Nitro.app` | 16 + 20, read back | same |

No game ran from a folder while it was written (PC: only lab copies ran; Macs: the deploy script refuses while `i76.exe` / `nitro.exe`
runs; the MacBook and the M4 Max tester Mac each had an i76.exe of another lane's test up at 05:38 and were done when it had exited).
Final read-back on all three Macs: credits, `rageco.lvl` and `repo.cbt` md5 = the PC's. Mac deploy pack + script: lab
`builds\content-installer-20261025\mac\` (`deploy.sh` copies file by file into the existing game folders; not mp-mac-install.sh `update`,
which replaces the whole folder).

Main Gold's proxy (5d6f9828) and Nitro's (3f27c797) are unchanged: the maps need no proxy change. The new proxy keys (s.3) are only in
the kit and the lab twin.

## 2. Patch Kit v0.7.4: `INSTALL-EXTRAS.bat`

`_i76e\i76e-extras.ps1` + `_i76e\extras.json` (repo `tools/patch-kit/`). No Python needed. Interactive (asks per option) or with
switches (`-Maps [-NitroDir <Nitro Pack folder>] [-Offline <folder>]`, `-OpenTrack`, `-Python`, `-GermanVoices <folder>`,
`-MusicExtra <folder>|off`, `-Yes`, `-List`, `-Uninstall`). Writes only inside the game folder(s); a replaced file is kept as
`<file>.pre-i76e-extras`; every write is in the ledger; `UNINSTALL-i76e.bat` calls `-Uninstall` first.

| option | what the user is told it enables | source, pin |
|---|---|---|
| community maps | the 5 Gold arenas in MELEE's list by title; with `-NitroDir` the 5 Nitro arenas in HOST > COMBAT; credits shown before the download and written to COMMUNITY-MAPS.txt | Local Ditch (`localditch.com/interstate-76/maps/<map>.zip`) and LSM (`interstate76.com/lsm/...`), each zip size + sha256 pinned, each output sha256 pinned; the 1997 conversion is arena-pack.py's ported to PowerShell (insert the 13-byte horizon name at WRLD +0x86 by palette, WREV 9, WRLD / WDEF sizes +13; strict chunk walk) |
| opentrack (head look) | turn your head, the view turns; webcam / phone / IR; OPENTRACK.bat, Output = freetrack 2.0 Enhanced, Start, then PLAY.bat; Ctrl+Alt+H | opentrack 2026.1.0 `win32-portable.7z` from its GitHub release (196,482,178 B, sha256 92ed738f..., = GitHub's digest), unpacked with `7zr.exe` 26.04 from 7-Zip's GitHub release (sha256 256feca8...; Windows 10's tar.exe has no LZMA: "LZMA codec is unsupported") into `_tools\opentrack`; the head-look layer (`i76-opentrack-headlook.ahk`, `-autostart.ps1/.ahk`, now in the zip) into `_ahk\`. PLAY-i76.ps1 uses `_tools\opentrack\opentrack.exe` when `-OpenTrack` is not given and the default install path has none |
| AutoHotkey | explanation only (already bundled: pad / wheel / stick and head-look layers) | bundled |
| Python | DEBUG.bat / TRAINER.bat dashboard; the game never needs it | python.org `python-3.12.10-embed-amd64.zip` (sha256 4acbed6d...; md5 fe8ef205 = python.org's listed md5) into `_tools\python`; its `._pth` renamed `.off` so the script folder is on sys.path; DEBUG.bat prefers it |
| German voices | the German dub from the user's own German retail disc; `PLAY.bat --voices de`; private | the user's folder: CD 1 root or an install folder (its `I76.ZFS`, stored entries read directly) or a folder of loose `.wav`; only names the user's Gold `I76.ZFS` has; refused unless >= 300 shared and most differ in length (482 of 495 do); `-Default` makes it the launch default |
| extra music (private) | your own songs shuffled in, one song start in N (default 3); nothing downloaded or copied | the user's folder; written to `_i76e\extras.env` (`I76_MUSIC_EXTRA`, `I76_MUSIC_EXTRA_EVERY`) |

Launchers: every PLAY*.bat reads `_i76e\extras.env` (KEY=VALUE) and takes `--voices de|en` and `--music-extra off|<folder>`; the
environment reaches the game through PLAY-i76.ps1 (ProcessStartInfo inherits it). README-PATCH-KIT.md has the section and the table.
Kit also: v0.7.4 ships `tools\debug\debug_logger.py` / `debug_haptics.py` (DEBUG.bat failed without them) and the head-look layer.

Packed from a clean worktree of 76227ce (lab `builds\content-installer-20261025\wt-kit`; the working tree held another lane's uncommitted
PLAY-i76.ps1 render-scale work, which must not ship); `tools\trainer\waypoints.json` (gitignored) copied in as v0.7.3 did (same md5
fe242bfc). dgVoodoo 2.87.5 + 2.87.3 and AutoHotkey from the v0.7.3 zip (md5-checked by the packer). Name guard passed; independent
check: 0 files content-identical to any of GOG's 371.

Build-From-GOG (coordinator's addition, commit 76227ce): it downloaded dgVoodoo 2.87.3 only and called the packer without a fallback.
Now it fetches `dgVoodoo2_87_5.zip` (sha256 5ffde692...) and `dgVoodoo2_87_3.zip` (6fb954be...) from Dege's GitHub releases, checks
both, passes `-DgVoodooFallbackDir`; the Nitro path gives setup-windows the full 2.87.5 folder and setup-windows deploys D3D8 / D3D9 on
Nitro (seven x86 DLLs). Release md5s = the packer's pins (DDraw c70a0ee6, D3DImm 71b3bf5a, Glide2x 3fbe9528; D3D8 e215a1ee,
D3D9 e9a6ec6b). Not run end to end here (the clean-install lane runs it).

## 3. Proxy: I76_VOICES and I76_MUSIC_EXTRA

- **Voices, mechanism.** Loose files in `ADDON\` already beat I76.ZFS (VFS container 0 = "addon"; the lowest container that holds a name
  wins in 0x4b2e00; proven for `ADDON\vppirna1.vcf`), but ADDON is always on and part of what LAN partners must match. The VFS builds its
  file table once (vfs_Lookup 0x4b28c0: `FindFirstFileA("addon\*.*")` / `FindNextFileA`, names into 16-byte records) and opens a
  container-0 file as `fopen("addon\<name>")` (0x4b3030 / 0x4b3310, `"%s\\%s"`). voices.c hooks those four i76.exe IAT slots only when
  `I76_VOICES` is set: the addon scan also lists the overlay folder's `.wav` that ADDON does not hold, and `fopen("addon\x.wav")` for such
  a name opens `<overlay>\x.wav`. ADDON's own files still win; nothing on disk changes; unset = no hooks. Gold only.
- **Extra music.** The virtual disc (tracks 2..17, TOC, lengths) is untouched; every Nth new song start in `play_track` opens the next
  file of a shuffle bag of the folder's `.mp3` / `.wav` (folder + one sub-folder level) instead of `music\N.mp3`; the run keeps the logical
  track, so the run continues with the next game track when it ends. Gold and Nitro (shared code). `off` / `0` = off.

## 4. Tests

### 4.1 Gold maps (lab twin `content-inst-gold-20261025` = test-gold + proxy 689cb47c, other add-ons parked; `tools\content-trial\arena-trial.ps1`, Instant Melee, arena index written, 60 s W + A/D weave, preset OWNER-2300-ALL minus the cursor-map keys; muted, own shm suffix; console lock per boot)

The shell's list (read from memory): 15 '76th Precinct', 16 'Biggsville', 17 'Drug Bust', 18 'Leathertown', 19 'Rage County'.

| map | boots | mission file read back | 60 s | max speed (m/s) | proxy crash lines |
|---|---|---|---|---|---|
| The Crater (control, idx 0) | 1 | stock | alive | 43.5 | 0 |
| 76th Precinct | 2 | 76prcnct.lvl, far clip 600 | alive, alive | 17.2, 3.1 | 0, 0 |
| Biggsville | 2 | bigville.lvl, 600 | alive, alive | 10.2, 3.3 | 0, 0 |
| Drug Bust | 2 | drugb.lvl, 600 | alive, alive | 13.3, 14.5 | 0, 0 |
| Leathertown | 2 | leather.lvl, 600 | alive, alive | 13.7, 16.4 | 0, 0 |
| Rage County | 2 | rageco.lvl, 600 | alive, alive | 8.1, 3.7 | 0, 0 |

10 of 10 add-on boots alive (the content lane's 1-in-3 crash on Rage County was the old proxy's coop-ai double hook; none here).
Biggsville and Drug Bust had only been checked statically before. Low speeds = the scripted weave in built-up spawns (as before).
Runs: lab `tools\content-trial\runs\20261025-053902-inst-gold\`.

### 4.2 Nitro maps (lab twin `content-inst-nitro-mp-20261025` = exp-content-nitro-mp: GOG nitro.exe 28b8ae27 + the nitro-mp instrument drv2 8d298467, not our proxy; hosted alone through nitshell's HOST form, private desktop; `tools\content-trial\inst-nitro-host.ps1`)

| arena | GAME TYPE | list index | mission read back | sim time | state |
|---|---|---|---|---|---|
| n01.cbt (control) | Combat | 2 of 29 | N01.CBT | 61.5 s | 5, host + 1 player |
| Gumball Rally | Combat | 0 of 29 | gumball.cbt | 60.75 | 5 |
| Intercept and Pursuit | Combat | 1 of 29 | intercpt.cbt | 61.0 | 5 |
| BorderTown | Combat | 28 of 29 | tex.cbt | 61.0 | 5 |
| Offroad Gold | Combat | 26 of 29 | offroad.cbt | 60.75 | 5 |
| RepoTown USA | Combat | 27 of 29 | repo.cbt | 60.75 | 5 |
| Great Oval (comparison only) | row 1 Racing (type 2, list 14, first 'Great Oval') | 0 of 14 | goval.rac | 61.0 | 5 |

n 1 each; the only non-C++ exceptions are the 9 boot-time `c0000096` PIT probes every run has, the control included. Logs: lab
`captures\nitro-mp-20261021\inst-*.log/.json`. The host car was not driven (the instrument holds).

### 4.3 German voices and extra music (Gold twin, direct boot into T01, `I76_VOICES=de`, `I76_MUSIC_EXTRA=<owner's private folder>`, `I76_MUSIC_EXTRA_EVERY=1`; hook `tools\content-trial\inst-extras-env.ps1`)

| boot | voices | music |
|---|---|---|
| 1 | `voices: I76_VOICES=de - 495 voice files ... VFS scan + fopen hooked`; `VFS scan of addon\*.*: 28 ADDON entries + 495 overlay voice files`; during the mission `addon\gdsta09.wav -> ...\voices-de\gdsta09.wav`, `01sta61.wav` (6 redirects) | `music-extra: 42 extra songs ...`; `track 2 -> ...\ost-only\08 - Code Six Pack.mp3`, `str ok: open ... type mpegvideo`, `PLAY track 2`; then `track 3 -> ...\bullmark-demo\11 - Pocket Full of Yanni.mp3` |
| 2 | same, `gdsta08`, `gdsta10`, `gdsta25` redirected | `track 2 -> ...\ost-only\26 - Payback Recon.mp3` |

Both alive 60 s, 0 crash lines, drove 844 m (= the T01 control of the content lane). Muted: "played" is the log (the file the engine
opened), not by ear. The 495 German files are byte-identical to the archive's own extraction (`I76_CD1.ZFS-text-voice`).

The owner's private music folder: `<archive>/community/<private-music>\` (copies; README.txt): `bullmark-demo\` the 24
Bullmark Demo mp3s, `ost-only\` the 18 OST cues not on the game disc as interstate76.com ALL.ZIP mp3s (TRACKnn = OST track nn, matched by
duration, named after the FLAC titles). Never in any pack.

### 4.4 Patch Kit on the laptop bench (the laptop bench, Windows 11 26100, 1920x1080)

Fresh pristine GOG copy (371 files, i76.exe 9a232dcc) at `<bench>\kit074b\game` + the 76227ce zip; first the 0ba5940 build at
`kit074` (same content but the download-size text and Build-From-GOG).

| step | result |
|---|---|
| unzip + `PLAY-T05.bat --setup --display 1920x1080` | 474 files; setup done, "ready: preset tick19-42, 1920x1080 x2"; i76.exe 64165126, STRLKUP 689cb47c |
| `INSTALL-EXTRAS.bat -Maps -OpenTrack -Python -Yes` (online) | 16 s: the 5 Gold zips from localditch.com, 7zr.exe + opentrack 187 MB from GitHub, Python from python.org, every sha256 ok; maps 5 of 5; the 10 Gold map files = the tested sha256 |
| `INSTALL-EXTRAS.bat --list` | 22 entries |
| Python | 3.12.10; `i76debug.py --help` runs on it (the module set is complete) |
| opentrack | `_tools\opentrack\opentrack.exe` started: window "opentrack-2026.1.0 :: default.ini" |
| PLAY-T05.bat with that opentrack running | 3 of 3 alive at 20 s, t05.msn, launcher: **"head look: ON (opentrack was already running)"**; CRASH lines = the documented frame-0 PIT probe `0xC0000096 exe+0x99997` only |
| `UNINSTALL-i76e.bat` on the first copy | "extras removed: 22 entries", originals restored; **all 371 GOG files md5-identical to pristine**; no _tools, voices-de, OPENTRACK.bat, COMMUNITY-MAPS.txt, ADDON .lvl left |

Not tested: a head tracker moving the view (no tracker at the bench), German voices / extra music on the laptop (lab twin only), the
Nitro half of `-Maps` through the kit (`-NitroDir`; the same code installed main Nitro and the Nitro twin), the interactive menu by hand.

## 5. Licence notes and open points

- Maps: credits shown before the download and in COMMUNITY-MAPS.txt; readmes kept beside the maps; the kit links, it does not rehost.
  **RepoTown's and Intercept's Nitro versions are Lightfoot conversions whose readmes say "modified / converted without the author's
  consent"** (the same kind of note as Great Oval's); RepoTown is in by the owner's ruling. Before a public release of v0.7.4 the owner
  may want to ask Debacle (still the plan in CONTENT-FEASIBILITY s.5).
- German voices and extra music: user-supplied only, private; nothing of either is in the kit or the repo.
- The M4 Max tester Mac kept the first credits text in its `_rollback-maps-20261025` (the refreshed one is installed).
- Lab twins `content-inst-gold-20261025` and `content-inst-nitro-mp-20261025` deleted at lane end (runs and captures kept); one file is left, `content-inst-nitro-mp-20261025\Interstate 76 Nitro Pack\lee_____.ttf`, held open by Windows (the font a Nitro run registered); delete it after the next logoff.

Commits: i76-everywhere 4ec088e (installer + proxy + packager), 3e5a268 (README), 0ba5940 (packager fix), 76227ce (Build-From-GOG
dgVoodoo 2.87.5, D3D8/9 on Nitro), this record; lab 8eaaf32 (test scripts).
