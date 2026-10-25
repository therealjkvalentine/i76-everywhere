# Player settings file and feedback via GitHub Issues (2026-10-25, settings-file lane)

Owner, 2026-10-25: *"Is psd1 easy for laypeople, or is there a more intuitive format that opens in a text editor?"* and *"Ask for
feedback via GitHub issues so it is easy to watch and process."*

## 1. Answer: psd1 is not for laypeople

A `.psd1` is PowerShell syntax (`@{ Env = @{ I76_FOV = '100' } }`): quotes, braces and engine key names, and one missing quote makes
the whole file unreadable (`Read-Preset` returns nothing and the launcher ignores the file). The player-facing file is now
**`i76-settings.txt`** in the game folder: plain `name = value` lines, `#` notes, grouped, opened in Notepad by `SETTINGS.bat`.
`presets\local.psd1` stays for power users.

```
# How big the 3D picture is drawn before it is fitted to your monitor: 2 = twice your monitor's size each way (sharpest,
# heaviest on the graphics card), 1 = your monitor's own size (lightest - try it if the game is not smooth). Windows only.
# allowed: 1, 1.5, 2, default.   now: 2 = the 3D drawn at 3840x2160 (the launcher's default)
render scale = default
```

## 2. The file (PLAY-i76.ps1, "player settings file")

- **Settings** (one schema table drives writing, reading and checking): Graphics - render scale, antialiasing, field of view, hood
  view field of view, draw distance, road distance, terrain detail, terrain / object / road texture distance, shadow distance, bush
  distance and density, mirror distance, refresh rate, windowed; Controls - head look (auto / start / off), head look mode, wheel force
  feedback (auto / on / off), game force feedback, pavement scale, mouse wheel up / down; Sound - effects / voice / music volume (dB);
  Multiplayer - player name (a note: typed in the game's menus, no key exists), co-op scaling, co-op extra enemies, co-op damage,
  computer car skill, legacy multiplayer menu; Advanced - skip mission movies, simulation tick, and any `I76_*` switch by its own name
  (passed as written; empty value removes the preset's). Engine key names (`I76_RENDER_SCALE = 1`) are accepted for the listed ones too.
- **Values**: every line is written as `default` (= the launcher's choice), with `now: <value> (<source>)` in its note, taken from
  this PC at write time (preset + local.psd1, the display from `_i76e\display.txt` or the main monitor, the FFB tune file). Writing
  real values instead would pin them: `draw distance = 1800` from PLAY.bat would silently override PLAY-PREVIEW's 2300.
- **Written** on the first start when missing (not for preset stock, not under -DryRun / -RenderOnly), or by
  `PLAY-i76.ps1 -WriteSettings` (never overwrites; also writes `SETTINGS.bat`). The kit ships `SETTINGS.bat` (Gold / Nitro preset by
  which exe is in the folder; before the first PLAY.bat it says to start the game once).
- **Precedence**, lowest first: preset < `i76-settings.txt` < `presets\local.psd1` < command line (`-RenderScale`, `-NoFfb`, `-Ffb`,
  `-TickMs`, `-Windowed`, ... and the .bat flags that pass them). A local.psd1 override of a file value is logged
  (`local override: I76_FOV=110 (i76-settings.txt line 28 said 100)`); a command-line win too (`... - the command line says otherwise,
  it wins`). Preset stock: the file's game switches are not applied (logged), its launcher options are. `-NoSettings` skips it.
- **Bad lines are not fatal**: each is logged with its number and skipped, the launcher's value stays:
  `settings: i76-settings.txt line 23: 'antialiasing = 16' - not one of off, 2, 4, 8; skipped (the launcher's value is used)`;
  also not-a-`name = value` line, unknown name, not a number (`1,5`), out of range, a repeated name (the later line wins). Summary line:
  `settings: i76-settings.txt read - N value(s) changed from the launcher's, M line(s) not understood`.
- Pavement scale goes to the interposer's `ffb-tune-owner.json` (that one key, only when it differs; the FFB panel writes the same
  file, so the panel changes it for a session and the settings line sets it again at the next start).
- Also fixed on the way: `-DryRun -Windowed` used to rewrite `dgVoodoo.conf` (and leave a `.pre-windowed`); it now changes nothing.

Not done here (other lane's files): `setup-windows.ps1` / `i76e-prepare.ps1` do not generate the file; PLAY-i76.ps1 writes it on the
first start instead, which covers every layout (kit, RC, driver). The first-run summary got two lines (SETTINGS.bat, FIREWALL.bat) on
the coordinator's request. Not deployed to Gold / release-candidate / test-gold / the RC stage (their PLAY-i76.ps1 is the previous
one; a promotion decision). VERSION.md "Graphics settings" in those folders still names local.psd1.

## 3. Feedback via GitHub Issues

- `.github/ISSUE_TEMPLATE/`: `bug_report.yml` (game Gold / Nitro / both, platform Windows 10 / 11 / Mac / Deck / Wine, kit version and
  launcher, monitor + GPU, what happened, steps, files - required; a table of where `mciproxy.log`, `play-i76.log`, `i76-settings.txt`
  are on Windows, Mac and the Deck), `lan_report.yml` (host / joiner machines one line each, connection, game type, arena, stage, logs
  from every machine renamed host- / joiner-), `feature_request.yml` (was `feature_or_platform.yml`; points vote-worthy ideas at
  Discussions > Ideas), `config.yml` (no blank issues; contact links Discussions > Ideas and Q&A - the coordinator enabled Discussions
  during this lane - the GOG store, the kit README, VERIFIED-FIXES). Labels `needs-triage` and `multiplayer` created on GitHub.
- README.md and the kit README: "Problems and feedback" (link, what to attach, the personal-data sentence); kit README "Settings
  (`i76-settings.txt`)" with local.psd1 under it; `--no-supersample` = `render scale = 1`; "Network games (LAN)" with FIREWALL.bat;
  the Defender exclusion note in the low-frame-rate row.
- **First line of every log**: `If something went wrong, attach this file to a GitHub issue: https://github.com/therealjkvalentine/i76-everywhere/issues/new/choose`.
  play-i76.log (kept as line 1 by Write-LaunchLog), mciproxy.log / `_ffb\ffb-interposer.log` / `_ahk\opentrack-autostart.log` /
  `_i76e\setup.log` (put on top byte-for-byte by PLAY-i76.ps1 at launch and after the game exits; created for mciproxy.log when the
  proxy is deployed), and the proxy itself writes it as the first line of a new mciproxy.log (6240f43, every platform). Also line 2 of
  i76-settings.txt. Not covered: setup.log on a first setup that fails before PLAY-i76.ps1 ever runs; the Deck's deck-launch.log.

### The personal-data claim, checked

Read the logs on this PC (test-gold: mciproxy.log 459 lines, play-i76.log, ffb-interposer.log, opentrack-autostart.log) for paths,
IPs, MAC addresses, host names; and the proxy sources for every `%s` log argument; and the kit scripts for user / computer / WMI reads.
Found: paths (`C:\Users\<name>\...`), device names (wheel model), monitor size. **One more**: with the extra-music option the proxy
logged the player's own song file names twice (`music-extra: track T -> <file>` and `str ok: open "<folder>\<song>.mp3" ...`).
Fixed in source (5d83efd): the MCI open of an extra song, or of any file outside the game folder, is logged as `open "<your own song>"`,
and the music-extra line gives the song's number. The README sentence is therefore: *no personal data except your Windows user name in
folder paths (they also name your monitor size and controller model).* The fix ships with the next proxy build (the committed
`music-fix\Strlkup.dll` was not rebuilt here; kit v0.8.0's proxy still names extra songs).

## 4. Tests

- `tests/test_settings_file.py`, 7 tests: the written file (banner line 2, every setting `default`, each with `allowed:` + `now:`,
  draw distance `now: 1800 (preset tick19-42)`, render `now: 2 = the 3D drawn at 6880x2880`, SETTINGS.bat), read back = no change
  (DryRun environment equal to `-NoSettings`); values applied + four bad lines reported by their line numbers; precedence (file beats
  preset, local.psd1 beats file with the log line, `-RenderOnly` render `1x (3440x1440) ... from i76-settings.txt line N`,
  `-RenderScale 2` beats it); launcher options (wheel FFB off, tick, windowed) and command-line wins; preset stock stays stock; never
  overwritten, -DryRun writes nothing; the log banner (mciproxy.log once, play-i76.log line 1). With test_render_keys + test_presets:
  **39 passed**.
- **test-gold, -DryRun** (repo PLAY-i76.ps1, preset OWNER-2300-ALL, a game from another lane was running there; files removed
  afterwards, dgVoodoo.conf md5 0eb52fd6 before and after): render scale 1, field of view 95, draw distance 1500, effects volume -3,
  wheel FFB off, `antialiasing = lots` -> `I76_FOV=95`, `I76_FAR_CLIP=1500` (preset 2300), `I76_SFX_GAIN=-3`, the bad line at line
  171 reported, `field of view: 95 deg at 4:3 -> 125.8 deg`, no FFB interposer; the render step said `render keys NOT applied (scale 1
  from i76-settings.txt line 19 ...)` because that folder's dgVoodoo.conf was not its wide conf at the time (no PLAY.bat copy in a dry
  run). Output: lab `captures\settings-file-20261025\test-gold-dryrun.txt`.
- **Laptop boots** (LAPTOP-HPK11OMS, 1920x1080; bench copy `C:\i76-bench\sf` = the render-keys copy `rk` + this PLAY-i76.ps1 3adc51b5,
  proxy b53d1271; lab `laptop-bench\bench\sf-setup.ps1` / `sf-job.ps1` via `laptop-run.ps1`: lock `C:\i76-bench\.fps-lock`, PLAY.bat's
  conf copy, `-Preset tick19-42 -Mission t05 -SkipMovies -NoFfb -NoHeadTrack`, I76_SKIP_CUTSCENES=1, I76_MUTE=1, own shm suffix, only
  its own i76.exe stopped):

| row | i76-settings.txt | play-i76.log | conf [Glide] | game client | in mission / alive / CRASH |
|---|---|---|---|---|---|
| first | none (first start) | `settings: wrote i76-settings.txt (first start ...)`; `render: 2x (3840x2160) ... as installed` | 3840x2160 / 4x (c16c8150) | 3840x2160 | 3.7 s / yes / 0 |
| back | all `default` | `read - 0 value(s) changed ..., 0 line(s) not understood`; `render: 2x` | 3840x2160 / 4x (c16c8150) | 3840x2160 | 3.2 s / yes / 0 |
| r1b | `render scale = 1` (line 19) | `line 19: render scale = 1 -> I76_RENDER_SCALE=1`; `render: 1x (1920x1080), AA 4x (from i76-settings.txt line 19 / default; ... rewritten ...)` | **1920x1080** / 4x (f0905e20) | **1920x1080** | 3.2 s / yes / 0 |
| music | all `default`; proxy 0a45e71f (this lane's source); local.psd1 extra music, every song | `render: 2x ... the installed dgVoodoo.wide.conf put back` | 3840x2160 / 4x (c16c8150) | 3840x2160 | 3.2 s / yes / 0 |

  play-i76.log and mciproxy.log line 1 = the GitHub-issue line in every row. The changed render scale from the file applied: the
  conf and the game window followed it (n 1 for render scale 1; two more r1 boots found the bench lock held by other lanes for 20 + 20 min and were dropped), and going back to `default` put the installed conf back byte for byte. One planned
  r1 row was lost to the bench's shared `job.ps1` (another lane's job ran in its slot; the retry loop then checked the job name in itask's reply). The music
  row did **not** exercise the redaction: in 12 s of t05 the proxy logged no song start (no `str ok: open` / `music-extra` line), so
  the new log filter is compiled and booted (no CRASH) but not seen working. Captures: lab `captures\settings-file-20261025\`.

## 5. Commits

f235b16 launcher + tests; 5d83efd proxy log redaction; 21121ec issue forms, READMEs, kit SETTINGS.bat; 6240f43 proxy log banner;
5184173 Discussions links; 91db8e4 FIREWALL.bat / Defender / summary lines; lab c995619 bench scripts; this record.
