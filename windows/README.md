# windows/

Everything the Windows install and launch path runs. Most people never open this folder: double-click `INSTALL.bat`
at the repository root (it calls `Setup-From-GOG.ps1` here), or use the Patch Kit from the releases page.

| File | What it is |
|---|---|
| `Setup-From-GOG.ps1` -> `install.ps1` -> `setup-windows.ps1` | The install chain: GOG installer, dgVoodoo, proxy, controls, launcher |
| `PLAY-i76.ps1` | The launcher; `setup-windows.ps1` copies it into the game folder |
| `LAUNCHER.ps1` | The small settings window |
| `Make-Portable-Zip.ps1`, `MAKE-PORTABLE.bat` | Pack a working install to move to another PC |
| `Setup-FrameGen.ps1`, `enable-force-feedback.bat` | Optional extras |
| `i76-*.ahk`, `i76-opentrack-autostart.ps1` | The AutoHotkey layers (pad, wheel, stick, head look); they are copied into `<game>\_ahk\` |
| `dgVoodoo.daily-driver-2026-10-03.conf`, `dgVoodoo.windows.conf` | The dgVoodoo confs the installer writes |
| `i76-with-remap.bat` | Launch the game with the remapper from Proton or a plain Windows folder |

These scripts find the rest of the repository (`presets/`, `tools/`, `u32x/`, `music-fix/`, `controls/`) one folder up. The Patch Kit
carries the same files flat in `_i76e\repo\`; the scripts handle both layouts.
