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

## Field finding 2026-08-04: the hook was installed and NEVER CALLED

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
