# SMACKW32 proxy — stop the music when a cutscene starts

> **Correction 2026-10-16 (static, [docs/records/MUSIC-RETAIL-INTENT.md](../docs/records/MUSIC-RETAIL-INTENT.md)):**
> both retail 1.0 and the GOG exe *do* stop or pause CD music for movies.
> - WinMain calls StopCdMusic before the mission intro movie and before the win outro movie.
> - The movie player pauses the CD at the start of a movie and resumes it at the end (retail 0x44e6e0 / 0x44ed90;
>   AiO 0x4234a0 / 0x4234e0).
>
> Music under a cutscene therefore comes from a music layer that ignores the exe's MCI_STOP / MCI_PAUSE, not from
> the game. On Windows the Strlkup proxy answers both. The proxy below remains a belt-and-braces fix for layers that
> ignore them (DxWnd's virtual CD, GOG's win32.dll shim). The paragraph below is kept as first written.

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

**Related (memory RE, 2026-07-18):** the engine keeps a **music-active flag at
`0x524674`** (nonzero = a track should be playing; cleared by the MCI_CLOSE path)
and the aux-volume device handle at `0x4ed894` fed by `auxSetVolume`. Any future
launcher/trainer logic can *read* whether music should be playing instead of
inferring it, and could set music volume live instead of re-encoding tracks.
That's for intent/volume work only — the cutscene STOP belongs here in the
SMACKW32 proxy, which is the correct trigger point. Details:
[docs/MEMORY-MAP-INDEX.md](../docs/MEMORY-MAP-INDEX.md).

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
