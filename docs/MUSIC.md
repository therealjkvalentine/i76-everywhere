# Why Interstate '76 has no music, and what to do about it

**Diagnosed 2026-08-04.** Short version: the game plays its soundtrack as Red Book
CD audio through MCI. On a machine with no optical drive there is no `cdaudio`
device to open, so the engine gets silence. GOG ships the tracks as MP3 files but
never wires them into the game.

## The evidence

Three independent confirmations, because "no music" has several plausible causes
and settings were already ruled out (music was enabled in-game).

**1. No app on this machine can open a CD-audio device.**

```
mciSendString("open cdaudio")  ->  rc 266   FAILED
Win32_CDROMDrive               ->  no drives
```

This is not specific to the game — nothing can open one, because there is no
optical drive. Reproducing the failure outside the game is what makes this a
diagnosis rather than a guess.

**2. The engine's own music state says the same thing.**

| address | reads | meaning |
|---|---|---|
| `0x4ed890` | `0xFFFFFFFF` | MCI device handle — never opened |
| `0x4ed894` | `0xFFFFFFFF` | aux-volume device — never opened |
| `0x524674` | `0` | music-active flag — nothing playing |

(Addresses from [MEMORY-MAP-INDEX.md](MEMORY-MAP-INDEX.md) Tier 1.)

**3. GOG's music bridge is present on disk and never loaded.**

`win32.dll` is the only binary in the folder referencing `audiere.dll` — that is
GOG's usual arrangement for replacing CD audio. Both files ship with the release.
**Neither is loaded into the running process.** The engine reaches for MCI cdaudio
and stops there.

## A false negative worth knowing about

Checking whether a DLL is loaded **must be done from a 32-bit host**. `i76.exe` is
32-bit, and from 64-bit PowerShell `$proc.Modules` reports **zero** matching
modules whether or not they are loaded:

```powershell
# WRONG - reports 0 modules for a 32-bit process, always
powershell -Command "(Get-Process i76).Modules"

# RIGHT - enumerates all 99 modules
C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe -Command "(Get-Process i76).Modules"
```

This is the same trap recorded in
[FFB-LAPTOP-RECON.md](FFB-LAPTOP-RECON.md#the-false-negative-that-cost-the-most-time),
where it sent a search after a `LoadLibrary` failure that never happened. **Running
from `SysWOW64` is the fix**, and it is simpler than the workaround used there
(reading an exe-internal `GetProcAddress` result).

## What GOG ships

`music\2.mp3` … `music\17.mp3` — sixteen files named by **original CD track
number**. There is no `1.mp3` because track 1 was the data track. Also
`music.wav`, a small 8-bit 11 kHz mono clip used for a sting rather than music.

These are files *beside* the game, not game audio.

## The fix used here

[`tools/i76-music.ps1`](../tools/i76-music.ps1) plays the tracks alongside the
game, through MCI's `mpegvideo` device — verified working: opening `2.mp3` returns
`rc 0` and reports a length of 158018 ms. No external player and nothing to
install.

```powershell
tools\i76-music.ps1                      # play while the game runs
tools\i76-music.ps1 -StartTrack 7        # begin on CD track 7
tools\i76-music.ps1 -MissionOnly         # quiet in the menus
tools\i76-music.ps1 -Shuffle -Volume 650
```

`PLAY-i76.ps1` starts it automatically. It is **on by default** — unlike `-Ffb`,
this restores stock behaviour rather than adding a feature — and is disabled with
`-NoMusic`. Volume defaults to 550/1000 so it sits under gunfire.

Tracks are sorted **numerically**, not lexically: as strings `10.mp3` sorts before
`2.mp3`, which would play the soundtrack in a nonsense order.

### What this does not do

**It is not synchronised to the game.** The engine drives music through an MCI
cdaudio device that does not exist here, so it has no way to tell this script which
track a mission wants — start mission 6 and you still hear track 2 unless you say
otherwise. `-StartTrack` is the manual answer.

Making it automatic needs the mission index found in memory, which is not yet
located; the mission → track mapping would also have to be established, and it is
not simply one track per mission. Worth doing, not done.

In mitigation: the original played CD tracks in sequence, so sequential playback is
closer to faithful than it sounds.

## The winmm proxy: built, works standalone, BLOCKED for the game

[`tools/winmm-cdaudio/`](../tools/winmm-cdaudio/) is a working 32-bit winmm proxy
that emulates a CD-audio device over the MP3s (15 self-test assertions, all
passing — it opens `cdaudio`, reports 16 tracks, plays a requested track, reports
mode and position, stops and closes).

**It cannot be loaded by i76.exe, and the reason is worth recording.**

| observation | |
|---|---|
| a minimal static-import exe in the game folder | loads **our** winmm (`winmm resolved to: …\Interstate 76\WINMM.dll`, DllMain logged) |
| i76.exe in the same folder, launched after install | loads `C:\WINDOWS\SYSTEM32\WINMM.dll` |
| module list difference | the game loads `apphelp.dll` and `AcGenral.DLL` at index 5–6 — the **AppCompat shim engine** |
| winmm's position in the game's load order | index **23**, before `DSOUND` (43) and `DDRAW` (44) — so no *game* dependency preloaded it |
| do the shim DLLs reference winmm? | **both do** |

The shim engine is injected before the executable's own imports are resolved, and
it pulls in `SYSTEM32\winmm.dll`. Once a module is loaded **by base name**, the
loader reuses it and never consults the application directory — so an app-local
proxy loses a race it was never in.

Things tried that do **not** help:

- **`i76.exe.local`** (DotLocal redirection) — placed beside the exe, no effect.
  DotLocal changes path *resolution*, and the already-loaded-by-name check happens
  before any path resolution.
- **Renaming the exe** to dodge `sysmain.sdb` matching — the copy still failed to
  pick up the proxy (and exits within seconds, so the game appears to check its own
  filename). The compatibility database matches on file attributes, not just name.
- `winmm` is **not** a KnownDLL, and the application directory *is* searched first;
  both were verified, and neither is the obstacle.

### What would actually work

1. **DLL injection + IAT patch.** Inject any-named DLL into the running game and
   rewrite `i76.exe`'s import-address-table entry for `mciSendCommandA` to point at
   our implementation. This sidesteps load order entirely, because it happens after
   loading. The emulation code already exists and is tested; what is missing is the
   injector and the IAT walk. This is the route with a real prospect of working.
2. **A virtual CD drive with genuine audio tracks** (WinCDEmu and similar). Then
   `open cdaudio` succeeds against a real device and the game needs no help at all —
   the most faithful outcome. Requires installing a kernel-mode virtual SCSI driver
   and building a CUE/BIN with the data track plus 16 audio tracks, so it is a
   system change and a user decision, not something to do unasked.
3. **Suppressing the shim engine for this exe** — no per-application "no shims"
   switch exists, so this is not straightforwardly available.

Until one of those, [`tools/i76-music.ps1`](../tools/i76-music.ps1) remains the
working answer: unsynchronised, but audible, and it needs nothing installed.

## The proper fix, not done

A **`winmm.dll` proxy** in the game folder, intercepting the game's MCI cdaudio
calls and redirecting them to the MP3s. The game would then drive its own music,
correct track and all, with no external process — this is a well-established
technique for CD-audio-era titles.

It needs a C compiler, and this machine has none (the same constraint that made
`tools/ffb/FfbCore.ps1` walk DirectInput's COM vtables by hand). Left for a machine
that has one.

## Ruled out

| suspected | verdict |
|---|---|
| music disabled in-game | checked — it was on |
| missing music files | all 16 tracks present; no `1.mp3` is correct |
| missing GOG music bridge | `win32.dll` and `audiere.dll` both present |
| sound device broken | `DSOUND.dll` and `WINMM.dll` load; effects audible |
| our launcher bypassing a GOG launcher | there is none — only `Splash.exe`, `i76.exe`, `dgVoodooCpl.exe`, `i76wheel.exe` |
| the `-1` MCI handles being the bug | they are a *symptom*; the cause is the absent device |
