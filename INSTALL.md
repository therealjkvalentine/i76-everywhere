# Install & move Interstate '76 (i76-everywhere)

Two jobs, two scripts:

1. **You have a GOG copy and want it set up well** -> [Install from GOG](#1-install-from-your-gog-copy)
2. **You have it working and want it on another of your PCs** -> [Move it in a zip](#2-move-a-working-install-to-another-pc)

This repo ships **no game files**. The game bytes always come from *your* GOG
download; everything here is scripts + config.

---

## 1. Install from your GOG copy

### What you need
- The GOG **offline backup installer** for Interstate '76
  (`setup_interstate76_*.exe`), from <https://www.gog.com/account> ->
  Interstate '76 -> *More* -> *Download offline backup game installers*.
- Optionally the **Nitro Pack** installer (`setup_interstate76_nitro_pack_*.exe`).
- Windows 10/11.

Leave those `.exe` files in your **Downloads** folder (the installer finds them
there automatically).

### Run it
Double-click **`INSTALL.bat`**.

That's it. Or, from PowerShell in this folder:

```powershell
./Setup-From-GOG.ps1
```

Useful switches:

| Command | Does |
|---|---|
| `./Setup-From-GOG.ps1` | Auto-find the GOG `.exe`(s) in Downloads, install to `C:\GOG Games\Interstate 76`, apply everything |
| `./Setup-From-GOG.ps1 -GameDir "D:\Games\I76"` | Install somewhere else |
| `./Setup-From-GOG.ps1 -GogExe "C:\path\setup_interstate76_2.1.0.17.exe"` | Point at a specific installer |
| `./Setup-From-GOG.ps1 -SkipNitro` | Base game only |
| `./Setup-From-GOG.ps1 -Force` | Reinstall even if a game is already there |
| `./Setup-From-GOG.ps1 -Preset stock` | The recipe from before 2026-10-03: 20 fps, no engine switches (see [Presets](#presets-best-120-and-stock)) |
| `./Setup-From-GOG.ps1 -NoShortcut` | No desktop shortcut |
| `./Setup-From-GOG.ps1 -Controls stock` (or `INSTALL.bat -Controls stock`) | Keep GOG's 1997 keys. The default installs this project's own WASD-style control map (see [Controls](#controls-this-projects-map-or-the-1997-keys)) |
| `./setup-windows.ps1 -GameDir "<game folder>" -Controls stock -ControlsOnly` | On an install already made: switch the controls back to the 1997 keys and touch nothing else (`-Controls i76e` switches forward again) |
| `./install.ps1 -GameDir "D:\Games\I76" -NoShortcut -SkipNitro` | Configure a game that is already installed, writing nothing outside that folder (once `C:\Games\_tools` holds dgVoodoo and AutoHotkey) |

### What it does

Since 2026-10-03 the installer sets the base game up like the owner's daily driver
([docs/records/NEW-DAILY-DRIVER-RECIPE.md](docs/records/NEW-DAILY-DRIVER-RECIPE.md)). What was tested and what was not is in
[Evidence](#evidence-what-was-tested) below: **the result has not been started on a fresh install yet.**

1. **Silent-installs** the game (and Nitro Pack) from your GOG `.exe` — no wizard
   clicking. (GOG installers are Inno Setup; it drives them with
   `/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /NOICONS /DIR=…`.) Windows shows
   **one UAC prompt** for the GOG installer — click **Yes** (that's normal; it's
   the only click in the whole process).
2. Downloads **dgVoodoo2** 2.87.3 into `C:\Games\_tools` and installs
   `dgVoodoo.daily-driver-2026-10-03.conf` as the game's `dgVoodoo.conf`: no dgVoodoo frame cap
   (the preset paces the game), 16:10 picture in a borderless window, 2× internal resolution,
   4× MSAA. On a display 1440 lines tall or taller the file is copied byte for byte; on a
   smaller one only the digits of the two `Resolution` lines change (1080 lines:
   `[Glide]` 3456x2160). dgVoodoo rejects a whole conf over one bad line and then silently
   uses `%APPDATA%\dgVoodoo\dgVoodoo.conf` if there is one, which is why nothing else is edited.
3. Installs the **music-fix proxy** (`music-fix\Strlkup.dll` as `Strlkup.dll`, GOG's original
   kept as `strlkup_orig.dll`): the CD soundtrack in missions, and the opt-in `I76_*` engine
   switches the presets use.
4. Installs **`u32x.dll`** (menu and save-screen mouse mapping, Save Bookmark ghosting fix) and
   points the USER32 import of `i76.exe` and `i76shell.dll` at it (10 bytes each; originals kept
   as `i76.exe.u32xorig`, `i76shell.dll.orig`; undo: `u32x\deploy-u32x.ps1 -GameDir <dir> -Restore`).
5. Renames GOG's **`I76PATCH.DLL`** (the 20 fps cap, where the build ships one) to
   `I76PATCH.DLL.disabled`.
6. Installs **this project's own control map** as `input.map`
   ([`controls/input.map`](controls/input.map), the owner's daily-driver map): `W` `A` `S` `D` drive, the
   arrow keys look around. **It is not the 1997 layout.** GOG's map is kept beside it as
   `input.map.stock-<timestamp>`. `-Controls stock` keeps GOG's keys instead; see
   [Controls](#controls-this-projects-map-or-the-1997-keys) just below.
   *Never rebind via the in-game menu — it corrupts the file.*
7. Deploys the **controller layers** — downloads AutoHotkey 1.1 (pinned +
   sha256-checked) and puts `i76-remap.ahk` and `i76-ch-fighterstick.ahk` in `<game>\_ahk\`:
   **LB shift layer, right-stick glance, independent triggers, look-back rear gun, camera
   cycle**, the wheel's buttons, the flight stick. The launcher starts/stops them with the game.
   Not with `-Controls stock`: the layers type this project's keys.
8. Installs the **cutscene-music fix** (if the proxy DLL has been built) and the
   mouse-wheel helper (wheel up = cycle weapon, wheel down = hardpoint 5).
9. Copies the launcher (`PLAY-i76.ps1`) and `presets\*.psd1`, writes **`PLAY-i76.bat`**
   (`-Preset best-120`) and **`PLAY-stock.bat`** (`-Preset stock`) in the game folder, and makes a
   **desktop shortcut** ("Interstate '76") to `PLAY-i76.bat`.

The Nitro Pack, if installed, gets the earlier recipe unchanged (`dgVoodoo.windows.conf` with the
19.2 fps cap, no proxy, no preset).

### Play
Double-click the **Interstate '76** desktop shortcut (or `PLAY-i76.bat`).
First boot shows ~60–75 s of "PLEASE STAND BY" — press **ESC** to skip the intro.
Run it at the PC itself, not over Remote Desktop (the game hangs on "PLEASE STAND BY" there).

### Presets: best-120 and stock

| Launcher | Preset | What you get |
|---|---|---|
| `PLAY-i76.bat` (and the desktop shortcut) | `best-120` | 120 fps with the physics stepped as at 20 fps, the frame-rate bug fixes, 1800 m draw distance ([presets/best-120.psd1](presets/best-120.psd1) lists every switch) |
| `PLAY-stock.bat` | `stock` | The same folder with **no** engine switches. This is *not* the 20 fps game: the caps are off in this install, so it runs at whatever dgVoodoo paces and the physics are not corrected for it. It is there for comparing and for troubleshooting |

For the game as it was installed before 2026-10-03 (20 fps: dgVoodoo's 19.2 fps cap, `I76PATCH.DLL`
active, no switches), run the setup again with **`-Preset stock`**:

```powershell
./install.ps1 -GameDir "C:\GOG Games\Interstate 76" -Preset stock
```

That swaps the conf, renames `I76PATCH.DLL.disabled` back, rewrites `PLAY-i76.bat` without a preset
and removes `PLAY-stock.bat`. Running it once more without `-Preset stock` returns to `best-120`.
`PLAY-i76.ps1 -Preset ?` lists the other presets. **Play multiplayer on the `-Preset stock` install**:
no other preset has been tested between two machines.

### Evidence: what was tested

Tested on 2026-10-03, **without starting the game**:

- GOG's `setup_interstate76_2.1.0.17.exe` was unpacked with innoextract 1.9 into a scratch folder (the
  installer itself was not run), and `install.ps1 -NoShortcut -SkipNitro` was run on it. That installer
  yields `i76.exe` md5 `9a232dcc`, `i76shell.dll` `deb41008`, **no `I76PATCH.DLL`**, and an `input.map`
  with no analog `steer` / `throttle` block.
- Result, by file listing and md5: `dgVoodoo.conf` identical to the daily-driver conf (`fd68005a`, on a
  3440x1440 display); `Strlkup.dll` = the repo's proxy with `strlkup_orig.dll` `e5951e0f`; `u32x.dll`
  `a5927cea` with exactly 10 bytes changed in each of `i76.exe` and `i76shell.dll` (that run used the
  installer's default of the day; since later on 2026-10-03 the default is `u32x\u32x_full.dll`, `054fb411`:
  see the not-tested list); six preset files
  identical to the repo's; `PLAY-i76.bat` and `PLAY-stock.bat` as described; `tools\lint-input-map.py`
  OK; `PLAY-i76.ps1 -Preset best-120 -DryRun` prints the eleven `I76_*` values and the game folder as
  working directory.
- A second run changed 0 files. `-Preset stock` and back was run. The `I76PATCH.DLL` rename and its
  undo were run with a dummy file, because this installer ships none. The `Resolution` rewrite was run
  for eight display sizes: the text differs from the daily-driver conf in those digits only.
- The same run on a copy of a configured lab install (owner's `input.map`, lab `u32x`): the map was left
  alone and lints OK, the previous `u32x.dll` was kept beside the new one.
- The desktop, `C:\Games\_tools` and the GOG registry keys were unchanged by these runs.

**Not tested:**

- **Starting the game from this install.** In particular `best-120` has never been run on the
  `9a232dcc` exe that the 2.1.0.17 installer gives. Every gate behind the preset ran on the 2019 build
  (`60abf7bc`) and exes derived from it. The proxy checks the bytes at each patch site and skips a
  mismatch (`mciproxy.log` in the game folder lists each one); if the game runs too fast, use
  `-Preset stock`.
- The GOG installer's own silent run (it writes registry keys and asks for elevation), and the desktop
  shortcut. That code is unchanged.
- Whether dgVoodoo accepts the conf with other `Resolution` digits. Only the unchanged file
  (1440-line display) is proven accepted. Signs of a rejected conf: a dgVoodoo or 3dfx watermark, a
  4:3 picture.
- `u32x.dll` at run time on a fresh GOG install, either build. Since 2026-10-03 the installer deploys the
  daily driver's build (`u32x\u32x_full.dll`, md5 `054fb411`, also maps the Esc menu; source
  `u32x\u32x_full.c`). Checked without the game: `deploy-u32x.ps1` on scratch copies of GOG's `i76.exe`
  (`9a232dcc`) and `i76shell.dll` accepts it (every imported USER32 name is exported), changes exactly 10
  bytes in each file, and `-Restore` returns both to their original md5. Its gate ran on the lab sandbox
  and the daily driver, not on a fresh GOG folder, and the whole installer was not re-run with it.
  `setup-windows.ps1 -U32xDll u32x\u32x.dll` installs the minimal build (`a5927cea`) instead.
- The installed map on a fresh install. It is the daily driver's map (md5 `a937f36d`), which the owner plays
  on, plus three fire keys added 2026-10-03 (`1`, `J`, `L`; md5 `90122d37`, `controls/README.md`); no game was
  started from an installer-made folder, and the three keys have not been played.
- The Nitro Pack path (unchanged).

Not installed, although the daily driver has them: the cursor-overlay and head-tracking AutoHotkey scripts, Lossless Scaling, and the owner's saves.

### Controls: this project's map or the 1997 keys

The installer writes its own control map by default (`-Controls i76e`). The keys, beside the original ones, are
in [docs/CONTROLS.md](docs/CONTROLS.md); the printable sheet is
[docs/Interstate76-Controls-Quick-Reference.pdf](docs/Interstate76-Controls-Quick-Reference.pdf).

| | `-Controls i76e` (default) | `-Controls stock` |
|---|---|---|
| `input.map` | `controls\input.map`, written whole; verified by md5 and by `tools\lint-input-map.py` when Python is installed | GOG's map plus the minimal patch: analog `joystick1` steer / throttle, three mouse buttons, native pad buttons 1 / 3 / 4 and hat, `K` `O` `[` `]` for hardpoints 1 to 4 |
| What is kept | GOG's map as `input.map.stock-<timestamp>`, taken once. A map that is not GOG's own (hand-tuned, or patched by an earlier run) as `input.map.before-i76e-<timestamp>` | `input.map.pre-windows-setup`. Coming from i76e: GOG's map is restored from `input.map.stock-<timestamp>` first |
| AutoHotkey pad / wheel / stick layers | installed in `_ahk\` | not installed; copies from an earlier run are moved to `_ahk\off-stock-controls\` |
| Gamepad | left stick native, everything else through the layer | native only: left stick, A fire, X cycle weapon, Y handbrake, D-pad glance (button numbers assumed) |
| Wheel, flight stick | steering and pedals native, buttons through the layers | steering and pedals only |

- **Going back on an installed game:** `setup-windows.ps1 -GameDir "<game folder>" -Controls stock -ControlsOnly`.
  It needs the `input.map.stock-<timestamp>` file the first install left; without it (a portable zip, or a
  folder whose first map was already hand-tuned) it says so and changes nothing.
- The choice is written to `<game>\i76e-controls.txt`. A later run without `-Controls` keeps it, so updating
  an install never switches the keys.
- **A hand-tuned `input.map` is replaced** by the default mode (it is kept as `.before-i76e-<timestamp>`).
  To keep your own map through a re-run, put it back afterwards, or change `controls\input.map` in your clone.
- Mouse steering is not offered.

Tested offline on a copy of the unpacked GOG 2.1.0.17 tree (`controls-test`), the game never started:
fresh -> i76e (md5 of the result = the repo's map, lint OK, GOG's map kept); -> stock (GOG's map restored and
patched, lint OK, layer scripts moved out of `_ahk\`); -> i76e -> stock again (no second backup); a re-run with
no `-Controls` (stays stock); `install.ps1 -Controls i76e` end to end; a hand-tuned map in place (kept as
`.before-i76e-*`, and `-Controls stock` then refuses for lack of a stock backup). The launcher's `input.map`
guard was run in isolation on both results: it does nothing on either, and on a map wrecked by the in-game
menu it restores `input.map.as-installed`. **Not tested:** any of it in play, and the Nitro Pack with the
i76e map (the lint runs against `nitro.exe` at install time and puts the old map back if it has findings).

**Connect your controller before launching** — the 1997 engine only enumerates
joysticks at startup.

### Optional extras
- **Force feedback** (wheels / FFB sticks): nothing to switch on. Start-up of the game's force feedback is
  unconditional on the Gold exe ([docs/WHEEL-T300.md](docs/WHEEL-T300.md), from disassembly), so
  `enable-force-feedback.bat` is not needed; it is harmless. Nobody has re-tested a wheel on a PC where it was
  never run. Close the wheel's control panel before launching.
- **Save editing:** open `i76-save-editor.html` in any browser, or use the
  [hosted editor](https://therealjkvalentine.github.io/i76-everywhere/i76-save-editor.html)
  — drag a save in, edit, download it back out (runs locally, nothing uploaded).

---

## 2. Move a working install to another PC

Once one PC is set up, you don't reinstall on the next — you carry the whole
configured game in a zip.

### Make the zip
On the working PC, double-click **`MAKE-PORTABLE.bat`** (or run
`./Make-Portable-Zip.ps1`). It:
- copies your configured game folder (dgVoodoo, patched `input.map`, launcher and
  all) minus backup cruft,
- adds `PLAY.bat`, a per-machine `Setup-This-PC.bat`, the browser save editor, and
  a README,
- writes **`Interstate76-i76-everywhere-portable-<date>.zip`** to your Desktop.

Switches: `-IncludeSaves` to bring your savegames along; `-OutDir "D:\"` to write
the zip elsewhere; `-GameDir "…"` if it can't auto-find the install.

The controller layer (`_ahk\`) is always carried along automatically.

### On the other PC
1. Copy the zip over (USB, network share, cloud drive — whatever).
2. Unzip it anywhere (e.g. `C:\Games\`).
3. Double-click **`PLAY.bat`**. Done — no install, no GOG, no registry.

Optionally run `Setup-This-PC.bat` there to drop a desktop shortcut, and enable
force feedback as above.

> **Why this works:** dgVoodoo is a drop-in wrapper and every config
> (`dgVoodoo.conf`, `input.map`, `PLAY-i76.bat`) is folder-relative, so the game
> folder is location-independent. The only machine-specific bits — a desktop
> shortcut and the force-feedback registry key — are handled by the little
> per-machine helpers in the zip.

> **Keep it to your own machines.** The portable zip contains your copyrighted
> game files, so it's for moving between computers *you own* — not for sharing.
> The thing that's meant to be shared is this repo (scripts only, no game bytes):
> anyone else runs [step 1](#1-install-from-your-gog-copy) with their own GOG copy.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| "Couldn't find a GOG installer" | Put `setup_interstate76_*.exe` in Downloads, or pass `-GogExe "…"`. |
| `i76.exe still not found after install` | The GOG installer needed elevation — re-run in an **Administrator** PowerShell, or install to a user-writable folder: `-GameDir "$env:USERPROFILE\Interstate 76"`. |
| Installer log | Each GOG install writes `%TEMP%\i76-gog-install-*.log`. |
| Cars flip on small bumps / can't make scene 5's jump / everything runs too fast | The game is running faster than its physics are stepped. Open `mciproxy.log` in the game folder: it lists every switch of the preset as applied or skipped. If patches were skipped (an exe build the proxy does not know), run `./install.ps1 -GameDir "<game>" -Preset stock` for the 20 fps recipe. On a `-Preset stock` install: confirm dgVoodoo's `Glide2x.dll` is in the game folder and `dgVoodoo.conf` has `FPSLimit = 19.2`. |
| Still 20 fps after installing | `I76PATCH.DLL` is active in the game folder (the setup renames it to `.disabled`), or the launcher was started without a preset: use `PLAY-i76.bat`. |
| A dgVoodoo / 3dfx watermark, or a 4:3 picture | dgVoodoo rejected the game folder's `dgVoodoo.conf` and is using `%APPDATA%\dgVoodoo\dgVoodoo.conf`. Re-run the setup to restore the conf; do not hand-edit keys into other sections. |
| Game never gets past "PLEASE STAND BY" | You are connected over Remote Desktop. Start it at the PC itself. |
| Controller not detected | Plug it in **before** launching; the engine enumerates at startup only. |
