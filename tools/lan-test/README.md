# tools/lan-test: re-run the family LAN matrix from the PC

Built 2026-10-18 for the overnight LAN test (results: `docs/records/LAN-MATRIX-2026-10-18.md`; player instructions:
`docs/MULTIPLAYER.md`, section "Family game night"). Everything runs from Git Bash on the PC; the Macs are reached
through James's laptop (Tailscale), the Deck directly.

| file | runs on | does |
|---|---|---|
| `hosts.sh` | PC | `. hosts.sh`, then `on L\|A\|M\|D <<'EOF' ... EOF` runs a script on the laptop / Andrew / Michael / Deck; `fetch` copies a file back |
| `build-probe.sh` | PC | builds `tools/wine-probe/i76probe.c` (MSVC 2019 Build Tools, x86) into `build/` |
| `deploy-probe.sh` | PC | copies the probe + `probe3.sh` to `/tmp/i76mp` on the laptop and both boys' Macs |
| `probe3.sh` | Mac | runs the probe inside an app's Wine session (the game's own wine + prefix) |
| `macnav.sh` | Mac / Deck | `calib2`, `nav host\|join`, `hostgo [row y]`, `joingo`, `drive SECS`, `pos`, `st`, `find`, ... (`APP` = the .app path, or `deck`) |
| `restart-mac.sh` | Mac | stop the game in that app's prefix only (`wineserver -k`), `open` the app, Esc to the main menu |
| `fbshot.sh` | Mac / Deck | dump the shell's 640x480 8-bit back buffer: a menu screenshot that works over SSH (convert on the PC: `PIL.Image.frombytes('L', (640, 480), data)`) |
| `cur.swift` | Mac | `cur X Y` warps the real macOS pointer (`CGWarpMouseCursorPosition`); build with `swiftc -O -target arm64-apple-macos11.0 cur.swift -o /tmp/i76mp/cur` |
| `deckprobe.sh` | Deck | the probe inside the Deck's Proton prefix (GE-Proton10-12, compatdata 2731345568); copy to `~/Games/Interstate76/lan-test-20261018/` |
| `pcnav.sh` | PC | the same commands for the PC's LAN copy (`start`, `calib2`, `nav`, `hostgo`, `joingo`, `drive`, `pos`, `stop`) with `build/i76probe.exe` |
| `pc-lock.ps1` | PC | take / release the lab console lock (`i76-uncap-lab/CONSOLE-LOCK.md`); the PC cells need it |

## One cell, by hand

```bash
cd tools/lan-test; . ./hosts.sh
# host: Andrew's Mac, Suburbia
on A <<'EOF'
A="$HOME/Games/Interstate76-MP/Interstate 76 Gold.app"; N=/tmp/i76mp/macnav.sh
/tmp/i76mp/restart-mac.sh "$A"; $N "$A" calib2; $N "$A" nav host; $N "$A" hostgo 208
EOF
# joiner: the Deck (game started with: steam steam://rungameid/11731039888668098560)
on D <<'EOF'
N=~/Games/Interstate76/lan-test-20261018/macnav.sh; $N deck nav join; sleep 8; $N deck joingo; $N deck pos
EOF
```

Pass = both `pos` lines list both cars, the stationary car at the same coordinates on both ends (within 0.1 m),
and the other machine's table follows a car while it drives (`drive 60`).

## What the automation can and cannot do (measured 2026-10-18)

- **Mac, screen unlocked:** works, but only with the real pointer moved first. The shell's menus and entry
  forms (host / join) hit-test the shell mouse object `[[0x100cc514]+0x2c/+0x30]`, which under Wine's Mac driver
  follows the real macOS pointer. The probe (started over SSH, no Mac driver) moves only Wine's own cursor, so the
  form buttons (JOIN GAME, BROADCAST GAME, CANCEL) were pressed wherever the real pointer sat. `macnav.sh` therefore
  calibrates by warping the real pointer and reading the mouse object (`calib2`, no clicks needed), and every click
  warps the real pointer first (`rclick`). The map differs per window (Andrew, 1392x900 window at x 24:
  `client x = 54.3 + 2.174 UI x, client y = 1.875 UI y`; the 4:3 letterbox guess missed HOST by about 10 UI px).
- **Mac, screen locked** (display slept, lock screen up): keys reach the game (Esc works), clicks do not, by any of
  SendInput, posted messages, a real-pointer warp, or writing the mouse object. Those cells need the screen unlocked.
- **Deck (Game Mode):** works with `I76PROBE_STRETCH=1` (the Deck's proxy cursor map stretches 640x480 over the
  1280x800 window). Game Mode suspends the Deck after ~10 minutes without physical input; the game and SSH go with
  it (2026-10-18: the Deck vanished mid-test). Keep it awake: `systemd-inhibit --what=sleep:idle --mode=block sleep 7200 &`
  over SSH before a run (not yet tried), or have someone touch it.
- **Screenshots:** `screencapture` over SSH returns the wallpaper only (no Screen Recording permission), `shot` /
  `deskshot` return black on the Macs; `fbshot.sh` works everywhere the shell is up (menus, not the 3D view).
- **Never** use `throttle` or `poke` on the boys' Macs (a probe memory write was followed by a crash on Andrew's Mac
  on 2026-10-17); drive with `key`.
