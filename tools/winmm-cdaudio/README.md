# winmm-cdaudio — SUPERSEDED, see `music-fix/`

> **This was built without noticing that [`music-fix/`](../../music-fix/) already
> solves the same problem, by the same method, and is already deployed.** It reaches
> the identical conclusion — the game's soundtrack is CD audio over MCI, and an
> app-local `winmm.dll` cannot win because winmm is bound to `System32` before any
> of our code runs — and `music-fix/README.md` documented that dead end, including
> the DotLocal (`i76.exe.local`) failure, days earlier.
>
> `music-fix/` gets in via a **`Strlkup.dll` proxy**: a five-export helper the game
> imports statically, so it loads at process init, and its `DllMain` rewrites
> `i76.exe`'s IAT slot for `WINMM.dll!mciSendCommandA`. That sidesteps load order
> entirely, which is exactly what an app-local winmm cannot do.
>
> Kept for the parts that are still worth something: the **MCI cdaudio emulation
> details**, the **self-test** (`selftest.ps1`, 15 assertions — drives the emulation
> with no game running), and the measurements of *why* winmm proxying fails on this
> machine. Do not deploy it; it cannot work.
>
> **Lesson: grep the repo before building.** `grep -ril music` would have found it.

---

# winmm-cdaudio — pretend Interstate '76 has a CD drive

A 32-bit `winmm.dll` that sits in the game folder, forwards everything to the real
winmm, and **emulates a CD-audio device** backed by GOG's `music\*.mp3`.

Because the *game* asks for the track it wants, when it wants it, this is
**synchronised** — unlike [`tools/i76-music.ps1`](../i76-music.ps1), the stopgap
that plays the MP3s alongside the game and cannot know which track a mission wants.

## Why it works

| precondition | measured |
|---|---|
| `winmm` is not a KnownDLL | confirmed — an app-local copy *is* honoured |
| application directory searched first | yes, even with `SafeDllSearchMode` on |
| the game imports only 9 winmm functions | confirmed by parsing its import table |
| MP3s playable via MCI `mpegvideo` | `open 2.mp3` → `rc 0`, length 158018 ms |

The nine imports:

```
mciSendCommandA  mciGetErrorStringA          <- music. INTERCEPTED.
auxGetDevCapsA   auxGetNumDevs  auxSetVolume <- CD volume. Intercepted.
joyGetDevCapsA   joyGetNumDevs  joyGetPosEx  <- STEERING WHEEL. Forwarded verbatim.
timeGetTime                                  <- Forwarded verbatim.
```

`joy*` being in that list is the thing to be careful about: the 1997 engine reads
the wheel through winmm, so a proxy that got those wrong would break input. They
are passed straight through.

No audio decoding: the proxy translates CD-audio semantics into ordinary MCI file
playback by calling the **real** winmm's `mciSendStringA` with its `mpegvideo`
device. It also advertises a fake CD-audio `aux` device and routes its volume to
the player, so the in-game music slider works.

Track *N* is `music\N.mp3`. The original disc had track 1 as data and audio from
track 2, which is exactly how GOG named the files, so the numbering needs no
translation.

## Build and install

```powershell
tools\winmm-cdaudio\build.ps1                 # compile + verify
tools\winmm-cdaudio\build.ps1 -Install        # also copy into the game folder
```

The build **verifies its own output** rather than trusting the toolchain: it
asserts the DLL is x86, that all nine exports are present and undecorated, and
that it does not import winmm (a `winmm.dll` importing `winmm.dll` recurses until
the stack dies).

**The game must be restarted** — DLL paths are resolved at process start.

### To undo

Delete `winmm.dll` from the game folder. That is the entire rollback; nothing else
is modified, no registry, no system files.

## Verified so far, and what is not

**Verified:** it compiles to a 32-bit DLL with exactly the nine undecorated exports
the game imports and no self-import; MCI `mpegvideo` playback of the MP3s works;
the search-order and KnownDLLs preconditions hold on this machine.

**Not verified: the MCI emulation against the real caller.** It is written against
what the engine is *expected* to ask for, not against what it was observed asking
for. The engine may use time formats, status items or `MCI_NOTIFY` in ways this
gets wrong. That is what the log is for:

```powershell
$env:I76_CDAUDIO_LOG = "1"      # then launch the game
```

Every intercepted call is appended to `winmm-cdaudio.log` beside the DLL, including
anything unhandled (`unhandled MCI msg 0x...`). Read that after a session and the
gaps are explicit rather than guessed at. Logging is off by default — it is a hot
path.

Known gap: **`MCI_NOTIFY` is accepted but no `MM_MCINOTIFY` message is posted.** If
the engine relies on notification to advance tracks rather than polling
`MCI_STATUS_MODE`, music will play one track and stop. The log will show it.

## The trap that cost a round here

`cl.exe` not being on `PATH` is **not** the same as no compiler on the machine.
This repo previously recorded "no C compiler available" (which is why
`tools/ffb/FfbCore.ps1` walks DirectInput's COM vtables by hand from PowerShell).
In fact Visual Studio 2019 Build Tools are installed with an x86 cross-compiler at
`VC\Tools\MSVC\<ver>\bin\Hostx64\x86\cl.exe`. `build.ps1` finds it via
`vcvars32.bat`.

Second trap, in the build script itself: `& cmd.exe ... 2>&1` wraps every stderr
line in a `NativeCommandError`, which with `$ErrorActionPreference='Stop'` aborts
the script **even when the compiler succeeded**. `vcvars32.bat` emits a benign
`'vswhere.exe' is not recognized` warning, and the first build died on it before
writing any log. Redirection now happens inside `cmd`.
