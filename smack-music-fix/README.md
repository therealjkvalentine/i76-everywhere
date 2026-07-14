# SMACKW32 proxy — stop the music when a cutscene starts

Interstate '76 never stops CD music for FMV movies: on a 1997 CD-ROM drive, reading
the movie data physically interrupted redbook audio, so the devs never wrote a stop.
File-based music (GOG's `win32.dll`/audiere on Windows, DxWnd's virtual CD on our Mac
build) has no such limit → the last mission/menu track plays **over** each cutscene's
own baked-in score. Known GOG bug; the community's only "fix" was *buy the CD version*.

This proxy recreates the hardware behavior at the exact same trigger point:

- `_SmackOpen@12` (= a movie starts) → broadcast `MCI_STOP` to every open MCI device,
  on every layer that could be playing (static winmm import — DxWnd IAT-patches it, so
  on the Mac it reaches dxwplay; plus GOG's `win32.dll` shim via `GetProcAddress`).
- All 39 exports forward to the renamed original (`smackorg.dll`).
- **Ordinal-exact**: `i76.exe` imports SMACKW32 *by ordinal* (Watcom-era linker), so
  the export ordinals must match the original DLL exactly (14 = `_SmackOpen@12`, etc.).
  `smackw32.def` was generated from the original's export table.
- Freestanding build: imports KERNEL32 + WINMM only (no CRT) — safe in any prefix.

Mission music is untouched: the game itself issues a fresh `MCI_PLAY` for menus and
missions after movies, exactly as it did on CD hardware.

## Build (the DLL is not committed — repo ships no binaries)

    brew install mingw-w64     # once
    ./build.sh                 # -> SMACKW32.DLL

## Install

- **Mac:** `../setup-cutscene-music-fix.sh` (finds every wrapper; original kept as
  `smackorg.dll`; `--revert` to undo).
- **Windows / Steam Deck:** in the game folder, rename `SMACKW32.DLL` →
  `smackorg.dll`, then copy the built proxy in as `SMACKW32.DLL`.

## Files

- `smackproxy.c` — the proxy (generated wrappers + the `stop_cd_music()` hook)
- `smackw32.def` — exports with pinned ordinals (from the real DLL's export table)
- `build.sh` — one-command mingw build
