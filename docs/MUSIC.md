# Why Interstate '76 had no music, and how it got it back

**Diagnosed 2026-08-04. Fixed 2026-08-08.** Short version: the game plays its
soundtrack as Red Book CD audio through MCI. On a machine with no optical drive
there is no `cdaudio` device to open, so the engine gets silence. GOG ships the
tracks as MP3 files but never wires them into the game.

The fix is a proxy DLL that answers the game's MCI calls with a **pretend CD**
built from those MP3s. The engine opens it, reads the table of contents, picks
tracks and sequences them exactly as it would from the disc — see
[the fix](#the-fix-a-pretend-cd-behind-strlkupdll). Confirmed in a mission:

```
auxSetVolume(0xB337B337) -> 700/1000
MCI_PLAY flags=0xC from=104012301 -> track 13
  str ok: open "...\music\13.mp3" type mpegvideo alias i76cd
  str ok: play i76cd
  str ok: close i76cd
MCI_PLAY flags=0xC from=2 -> track 2
```

Those track numbers are the **engine's** choices, not ours.

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

## The fix: a pretend CD behind Strlkup.dll

[`music-fix/strlkproxy.c`](../music-fix/strlkproxy.c). The game statically imports
five functions from its own `Strlkup.dll`, so a replacement with those exports is
loaded **by the game itself**, before anything else runs — no injector, no load-order
race, and none of the winmm trouble below. It forwards all five to the renamed
original (`strlkup_orig.dll`) and, on the way past, rewrites `i76.exe`'s
import-address table so `mciSendCommandA` — plus `auxGetNumDevs`, `auxGetDevCapsA`
and `auxSetVolume` — land on our code.

From there it answers as a CD drive with 16 tracks would, and hands the actual
playback to MCI's `mpegvideo` device pointed at `music\N.mp3`.

Build and install:

```powershell
music-fix\build.ps1 -Install
```

Needs the x86 `cl.exe` from VS Build Tools; `build.ps1` finds it via `vswhere`. It
builds to `Strlkup.build.dll` and only replaces the real one after checking the
architecture came out 32-bit — an earlier version overwrote the working DLL on
failure, twice.

### The four things the engine checks before it will play

Each was a separate silent failure, and each was found by logging what the game
asked rather than by reasoning about it (`I76MUSIC_LOG=1`, written to
`mciproxy.log`).

| the game asks | what it wanted |
|---|---|
| `MCI_OPEN` with flags `0x3000` | It **always** sets `MCI_OPEN_TYPE_ID`, passing the device type as an *integer* in the low word of `lpstrDeviceType` — not the string "cdaudio". An early guard treated `TYPE_ID` as disqualifying and refused every open. |
| `MCI_STATUS` / `NUMBER_OF_TRACKS` | 16. |
| `MCI_STATUS` per track, with `MCI_TRACK` set | Length **and type** of each track. Answering 0 reads as an empty disc. |
| `MCI_STATUS_POSITION` **with** `MCI_TRACK` | This is a table-of-contents query — the *start time of that track*, not the current playback position. Answering with the playhead makes the TOC nonsense and the engine gives up. |

The last one is the subtle one: the same status code means two different things
depending on whether `MCI_TRACK` is set.

```c
p->dwReturn = trk ? fmt_time(track_start_ms(trk), trk)
                  : fmt_time(position_ms(), g_curTrack);
```

Times go back in the packed MSF/TMSF format the caller asked for; returning
milliseconds silently yields absurd track lengths.

### Volume

The game's music slider drives `auxSetVolume` against a device that does not
exist. Hooking the aux trio lets the slider control the `mpegvideo` playback
instead, so in-game volume works normally.

## The stopgap, superseded

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

`PLAY-i76.ps1` **suppresses it automatically** whenever `strlkup_orig.dll` is
present, since that means the proxy is installed and the game is driving its own
music — running both plays two soundtracks at once. It is otherwise on by default
(unlike `-Ffb`, this restores stock behaviour rather than adding a feature) and is
disabled with `-NoMusic`. Volume defaults to 550/1000 so it sits under gunfire.

Keep it for machines without the proxy built.

Tracks are sorted **numerically**, not lexically: as strings `10.mp3` sorts before
`2.mp3`, which would play the soundtrack in a nonsense order.

### What this does not do

**It is not synchronised to the game.** The engine drives music through an MCI
cdaudio device that does not exist here, so it has no way to tell this script which
track a mission wants — start mission 6 and you still hear track 2 unless you say
otherwise. `-StartTrack` is the manual answer.

In mitigation: the original played CD tracks in sequence, so sequential playback is
closer to faithful than it sounds.

This limitation is **the reason the proxy exists**, and the proxy removes it
entirely — no mission→track table was ever needed, because the engine already has
one and simply asks for the track it wants.

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

### What actually worked

The IAT patch — but reached **without an injector**. Proxying a DLL the game itself
imports (`Strlkup.dll`) gets our code running inside the process during normal load,
and from there the IAT walk is the same. The insight was that the obstacle was never
"can we patch the IAT", it was "how do we get into the process", and the game's own
import table answers that for free.

Two other routes, neither needed now:

- **A virtual CD drive with genuine audio tracks** (WinCDEmu and similar). Then
  `open cdaudio` succeeds against a real device and the game needs no help at all —
  the most faithful outcome. Requires installing a kernel-mode virtual SCSI driver
  and building a CUE/BIN with the data track plus 16 audio tracks, so it is a system
  change and a user decision.
- **Suppressing the shim engine for this exe** — no per-application "no shims"
  switch exists, so this is not straightforwardly available.

[`tools/winmm-cdaudio/`](../tools/winmm-cdaudio/) is kept for its emulation detail
and 15-assertion self-test, both of which fed the working proxy. **Do not deploy
it** — its README says so too.

## Two wrong claims this document used to make

Both were stated here confidently, and both cost real time.

**"This machine has no C compiler."** It has VS 2019 Build Tools with the x86
cross-compiler. `cl.exe` merely was not on `PATH`, which is not the same thing and
was never checked — `vswhere` finds it in one call. This claim is what deferred the
proper fix, and it is also the premise behind
[`tools/ffb/FfbCore.ps1`](../tools/ffb/FfbCore.ps1) hand-walking DirectInput's COM
vtables from PowerShell.

**"`i76.exe` is packed."** It is not. `strings -n 6` returned 74 results, which
looked like packing; proper extraction returns 8,046 and the entropy is 6.61,
normal for an unpacked binary of this age. The tool was wrong, not the file.

## Ruled out

| suspected | verdict |
|---|---|
| music disabled in-game | checked — it was on |
| missing music files | all 16 tracks present; no `1.mp3` is correct |
| missing GOG music bridge | `win32.dll` and `audiere.dll` both present |
| sound device broken | `DSOUND.dll` and `WINMM.dll` load; effects audible |
| our launcher bypassing a GOG launcher | there is none — only `Splash.exe`, `i76.exe`, `dgVoodooCpl.exe`, `i76wheel.exe` |
| the `-1` MCI handles being the bug | they are a *symptom*; the cause is the absent device |
