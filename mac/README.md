# mac/

The Apple Silicon build: Wine wrapper setup, launch stubs and helpers. On a Mac, double-click `mac-install.command` at the
repository root (a one-line hand-over to `mac/mac-install.command`). The guide is [docs/guides/MAC-BUILD.md](../docs/guides/MAC-BUILD.md).

| Files | What they are |
|---|---|
| `mac-install.command` | The installer: DxWnd profile, music, cutscene-music proxy, arrow-key fix, launchers |
| `build-launchers.sh`, `i76-*-stub.swift` | Build the double-click launcher apps from the Swift stubs |
| `setup-*.sh`, `fix-arrows-for-mac.sh`, `slim-wrapper.sh`, `play.sh` | The individual steps the installer runs; each can be run alone |
| `open-*.command`, `i76-trainer.command` | Double-click helpers (settings panels, the pad diagram, the trainer overlay) |
| `dgVoodoo.conf`, `dxvk.conf`, `interstate-76.dxw` | The Mac graphics configs. The Steam Deck installer also fetches `dgVoodoo.conf` from here |

The scripts find the rest of the repository (`docs/`, `saves/`, `tools/`, `smack-music-fix/`, `music-fix/`) one folder up and the
AutoHotkey sources in `../windows/`.
