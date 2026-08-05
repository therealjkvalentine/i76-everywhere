# In-mission music fix (base game) — a Strlkup.dll IAT hook

Restores Interstate '76's in-mission soundtrack on a machine with **no optical
drive** (i.e. most modern laptops), and kills the "Please insert CD 2" prompt.

## The problem

The base game plays its soundtrack as **CD audio through MCI** — it opens the
`cdaudio` device with `mciSendCommandA` and plays track N. GOG ships those tracks
as `music\N.mp3`, but with no CD drive the MCI `cdaudio` device won't open
(`MCIERR_CANNOT_LOAD_DRIVER`, 266), so there's no music and the game asks for the
disc. (The **Nitro Pack is unaffected** — it plays music through `audiere.dll`,
not MCI, which is why its music already works.)

## Why not just a winmm.dll proxy

The obvious fix — drop a `winmm.dll` next to the game — **does not work here**:
dgVoodoo hardens the process's DLL search path to `System32`, so the game binds
`mciSendCommandA` to the real `SysWOW64\winmm.dll` before an app-directory
`winmm.dll` can load. Verified with a module lister; DotLocal (`i76.exe.local`)
didn't override it either.

## How this works

`Strlkup.dll` is a tiny 5-export helper that **i76.exe imports statically**, so it
loads at process init. We proxy it: all five exports are forwarded to the renamed
original (`strlkup_orig.dll`), and in `DllMain` we rewrite i76.exe's Import Address
Table slot for `WINMM.dll!mciSendCommandA` to point at our own function. The loader
has already snapped that slot to the real winmm before any `DllMain` runs, and the
game doesn't call it until a mission starts, so the overwrite always wins.

Our hook emulates the `cdaudio` device:

- `MCI_OPEN "cdaudio"` → succeeds against a virtual device id.
- `MCI_PLAY` track N → plays `music\N.mp3` via the **mpegvideo** MCI device (which
  works fine with no CD). Track N maps directly to `music\N.mp3` (track 1 was the
  data track — there is no `1.mp3`).
- `MCI_STATUS … MEDIA_PRESENT` → reports a disc present, so the CD prompt never fires.
- Everything non-cdaudio is passed straight through to the real winmm.

## Deploy / revert

`setup-windows.ps1` deploys it automatically for the base game: it backs up the
original as `strlkup_orig.dll` and drops the proxy in as `Strlkup.dll`.

- **Revert:** restore `strlkup_orig.dll` over `Strlkup.dll` (delete the proxy,
  rename the backup back).
- **Diagnose:** set the environment variable `I76MUSIC_LOG=1` before launching to
  write `mciproxy.log` in the game folder — it records the IAT patch and every
  cdaudio MCI call (open / play / track number / status), which is the thing to
  read if music misbehaves.

## Build

A prebuilt 32-bit `Strlkup.dll` is committed here (it's our own code — it forwards
to the GOG `strlkup_orig.dll` by name, so it works on any GOG install). To rebuild
after editing `strlkproxy.c`, run `build.ps1` (needs w64devkit's 32-bit gcc).

## 2026-08-04: THREE bugs, found by logging every call

The hook had been installed and deployed for days while doing nothing. Making the
log record **every** call — not just cdaudio ones — turned "no music" into three
specific, sequential bugs. Each one was invisible behind the previous.

**1. `MCI_OPEN_TYPE_ID` was explicitly rejected.** `wants_cdaudio()` began:

```c
if (!(flags & MCI_OPEN_TYPE) || !p || (flags & MCI_OPEN_TYPE_ID)) return 0;
```

and the log showed the game opening five times with `flags 0x3000` =
`MCI_OPEN_TYPE | MCI_OPEN_TYPE_ID` — the *only* form it ever uses. The hook refused
the exact call it exists to catch. With `TYPE_ID` set, `lpstrDeviceType` is not a
string but an integer device id, so a string compare can never match and
dereferencing it would be a wild read — presumably why the original bailed rather
than risk it. Correct handling is to compare the low word against
`MCI_DEVTYPE_CD_AUDIO`.

**2. Per-track status answered `0`.** After the open worked, the log showed the game
asking eighteen per-track questions (`flags 0x110` = `MCI_STATUS_ITEM | MCI_TRACK`)
and then never playing. The handler's `default: dwReturn = 0` told it every track was
type 0 and length 0 — an empty disc. **Answering `MCI_OPEN` is necessary but nowhere
near sufficient: the engine validates the disc before touching it.**

**3. `MCI_STATUS_POSITION` + `MCI_TRACK` is a TOC query, not "where is playback".**
It asks *where track N starts on the disc*, and the engine derives each track's
length from consecutive starts. Returning the playback position (0 while stopped)
made all sixteen tracks zero-length. Now it returns cumulative start offsets, and
the values check out against the format the game selects — `MCI_FORMAT_TMSF`, packed
`track | m<<8 | s<<16 | f<<24`. Track 4 starts at 229896 ms → m3 s49 f67 →
`1127285508`, exactly what the game is handed. (Worth noting because in decimal those
TOC values look like garbage and are not.)

### Confirmed working

The engine's own state, before and after (addresses from
[MEMORY-MAP-INDEX.md](../docs/MEMORY-MAP-INDEX.md) Tier 1):

| | before | after |
|---|---|---|
| `0x524674` music-active flag | `0` | **`1`** |
| `0x4ed890` MCI device handle | `0xFFFFFFFF` | **`0x0000C0DE`** |
| `0x4ed894` aux-volume device | `0xFFFFFFFF` | `0x00000000` |

`0xC0DE` is `FAKE_CD_ID` — the engine stored our virtual device's handle. It opens
the device, sets `TMSF`, reads the full TOC for tracks 1..17, queries our fake
`AUXCAPS_CDAUDIO` aux device, and sets volume (so the in-game music slider now
works: `auxSetVolume(0xB337B337) -> 700/1000`).

**Not yet observed: `MCI_PLAY`.** Every test above was at the title/menu, and the
base game plays its soundtrack in missions. Load one with `I76MUSIC_LOG=1` (the
launcher sets it) and the log will show either `MCI_PLAY … -> track N`, which is
done, or another status query answered wrongly — in which case the log names it.

## Earlier finding: the hook was installed and NEVER CALLED

With `I76MUSIC_LOG=1`, `mciproxy.log` after a full session read exactly one line:

```
--- strlkproxy: IAT patch mciSendCommandA old=75511840 new=73ff16c0 ---
```

The patch lands. Then nothing — no `MCI_OPEN`, no `MCI_PLAY`, in a mission or
anywhere else. **The game is not failing at CD audio, it is declining to attempt
it**, so hooking `mciSendCommandA` alone cannot be enough.

The cause is almost certainly the **aux gate**. The game imports
`auxGetNumDevs` / `auxGetDevCapsA` / `auxSetVolume`, and on a machine with no
optical drive the real `auxGetNumDevs()` returns **0** (measured). On 90s hardware
CD audio was mixed in *analogue* and its level set through an `aux` device, so "no
aux device" meant "no CD audio present" — and the engine checks that before it ever
opens the MCI device.

`strlkproxy.c` now also hooks those three, advertising exactly one
`AUXCAPS_CDAUDIO` aux device **when the system has none** (so a machine with real
aux hardware is untouched), and translating `auxSetVolume` to
`setaudio <alias> volume to N` — which also fixes the volume limitation below.

**This is written but NOT YET BUILT OR CONFIRMED.** See the build note.

## Building the aux change: needs 32-bit gcc

The committed `Strlkup.dll` predates the aux hooks. Rebuilding needs a **32-bit
gcc** (w64devkit), which is not installed here.

**MSVC cannot substitute, despite being available.** The five exports are
*forwarders* to `strlkup_orig.dll`, and `link.exe` refuses to emit them from either
form:

```
strlkup.def : error LNK2001: unresolved external symbol StrLookupCreate   (.def forwarder syntax)
LINK        : error LNK2001: unresolved external symbol StrLookupCreate   (/EXPORT:name=strlkup_orig.name)
```

It insists the symbols exist locally rather than treating a dotted target as a
forward. gcc/dlltool reads the `.def` correctly, which is why the original was built
that way.

Two ways forward, neither started:

1. **Install w64devkit** (portable, no installer) and run `build.ps1` — it prefers
   gcc and only falls back to MSVC.
2. **Drop linker forwarders entirely**: implement the five exports as
   `__declspec(naked)` stubs that `jmp` to `GetProcAddress(strlkup_orig, …)`. On x86
   a plain jump preserves the stack frame for any calling convention and any
   argument list, so the signatures never need to be known. `StrLookup_Global_Object`
   is DATA and would need separate handling.

`build.ps1` is now **non-destructive** — it builds to `Strlkup.build.dll`, verifies
the architecture, and only then replaces `Strlkup.dll`. It previously built straight
over the committed, deployed binary and destroyed it on each failure.

## Known limitation

The game sets music volume via `auxSetVolume` on the aux device; with no aux
device that's a no-op, so it can't attenuate our mpegvideo playback — music plays
at the mpegvideo device's volume. If it's too loud, a follow-up is to also hook
`auxSetVolume` and translate it to `setaudio <alias> volume to …` on the mpegvideo
alias. (Left out for now: get music playing first.)
