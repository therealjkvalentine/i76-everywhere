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
| `./Setup-From-GOG.ps1 -WithHDTextures -Yes` | Also build the HD texture pack from your own files (~40 min, needs Python + a GPU) |
| `./Setup-From-GOG.ps1 -Force` | Reinstall even if a game is already there |

### What it does
1. **Silent-installs** the game (and Nitro Pack) from your GOG `.exe` — no wizard
   clicking. (GOG installers are Inno Setup; it drives them with
   `/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /NOICONS /DIR=…`.) Windows shows
   **one UAC prompt** for the GOG installer — click **Yes** (that's normal; it's
   the only click in the whole process).
2. Downloads **dgVoodoo2** into `C:\Games\_tools` and applies the repo's config:
   **19.2 FPS physics cap** (matches the Mac value — clears scene 5's canyon jump
   *and* the tighter later-mission ramps), sharp Voodoo-1 look, 3× internal res,
   8× MSAA, correct mouse in fullscreen/windowed.
3. Patches **`input.map`** (native layer): fixes GOG's phantom `joystick5` ->
   `joystick1`, adds **mouse driving** and the native **gamepad** bindings.
   *Never rebind via the in-game menu — it corrupts the file.*
4. Deploys the **full controller layer** — downloads AutoHotkey 1.1 (pinned +
   sha256-checked) and drops `i76-remap.ahk` in `<game>\_ahk\`, the same
   XInput/shift-layer scheme tuned on Mac: **LB shift layer (all five hardpoints),
   right-stick glance, independent triggers, look-back rear gun, camera cycle,
   rumble**. The launcher starts/stops it with the game.
5. Installs the **cutscene-music fix** (if the proxy DLL has been built) and the
   mouse-wheel targeting helper.
6. Makes a **desktop shortcut** ("Interstate '76") and `PLAY-i76.bat` in the game
   folder.

### Play
Double-click the **Interstate '76** desktop shortcut (or `PLAY-i76.bat`).
First boot shows ~60–75 s of "PLEASE STAND BY" — press **ESC** to skip the intro.

**Connect your controller before launching** — the 1997 engine only enumerates
joysticks at startup.

### Optional extras
- **Force feedback** (wheels / FFB sticks): right-click
  `enable-force-feedback.bat` in the game folder -> **Run as administrator**
  (one-time `HKLM` write).
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

**`-WithHDTextures`** builds the HD texture pack **once** into the install before
zipping, so every PC you copy the zip to gets HD textures with **no** Python, GPU,
or 40-minute build — the cost is paid once here. (Needs Python 3 + a capable GPU on
*this* machine; the pack is generated from your own `I76.ZFS`.) The controller
layer (`_ahk\`) is always carried along automatically.

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
| Cars flip on small bumps / can't make scene 5's jump | The 20 FPS cap isn't active — confirm dgVoodoo's `Glide2x.dll` is in the game folder and `dgVoodoo.conf` has `FPSLimit=20`. |
| Controller not detected | Plug it in **before** launching; the engine enumerates at startup only. |
