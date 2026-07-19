# Find-what-writes — the decisive technique, and how to run it here

*The one capability our AHK tooling can't provide: a hardware breakpoint that
catches the instruction writing a value, revealing the struct base register and
field offset in one shot. This is how the live-ammo question (and armor, speed,
gear) gets settled instead of scanned for. Method background:
[RE-METHODOLOGY.md](RE-METHODOLOGY.md) §5.*

## Why x32dbg and not Cheat Engine (decided 2026-07-19)

CE was the obvious choice and we tried to install it. It isn't obtainable
cleanly:

- **GitHub (`cheat-engine/cheat-engine`) publishes source only** — no compiled
  binaries in any release.
- **cheatengine.org serves the Windows build through a third-party
  "download manager" stub** hosted on CloudFront
  (`cheatengine_Download_Manager.exe`). Every direct installer URL 404s. The
  site states plainly that the free installer comes "with extra software
  recommendation during install," and that the clean file is **Patreon-gated**.
  A wrapper stub that fetches arbitrary payloads is not something to install
  into the game prefix.
- The **Mac** and **Linux** CE builds *are* clean direct zips — but a native-macOS
  debugger hits the same wall that already defeated `winedbg` attach: macOS
  denies debug attach to a process it didn't create (`error 5`).

**x32dbg** (the 32-bit build of x64dbg) is open source, ships as a plain zip
from its own GitHub releases, and provides the same hardware-breakpoint
capability. Installed *inside* the prefix it runs as a Windows process, so Wine
mediates the debug API through wineserver rather than macOS ptrace.

What CE would still have given us is its polished successive-scan UI — and the
debug menu's **F10 scan** now covers that workflow natively (see
[DEBUG-MENU-FIELD-TEST.md](DEBUG-MENU-FIELD-TEST.md)).

## Status — installed and RUNNING (2026-07-19)

Verified on the Mac build this session:

- ✅ x32dbg installs into the prefix and **launches** (`C:\x64dbg\x32\x32dbg.exe`
  runs as a Windows process; the game kept running alongside it).
- ✅ **The debug API is available on both sides**: x32dbg imports
  `DebugActiveProcess` / `DebugActiveProcessStop` / `WaitForDebugEvent` /
  `ContinueDebugEvent` / `DebugSetProcessKillOnExit`, and this Wine's
  `kernel32` exports them. So **attach is mediated by wineserver, not by macOS
  `task_for_pid`** — which is precisely the barrier that returned `error 5` for
  winedbg. This is the reason to expect it to work here.
- ⬜ **Not yet exercised:** the attach itself, and whether Wine honours the
  x86 debug registers (DR0–DR3) that back a hardware breakpoint. Those are the
  two remaining unknowns, and they need a human at the GUI.

⚠️ Attaching **suspends the game**. Do it at a safe point — not mid-mission with
unsaved progress — and expect a 1997 title under DxWnd to be capable of dying
when resumed.

## A caution about obtaining Cheat Engine (2026-07-19)

A file named `CheatEngine77.exe` obtained via the site's download-manager link
was inspected here and is **not Cheat Engine**: 6.6 MB (the real installer is
~40–60 MB), **zero** occurrences of "Cheat Engine"/"Heijnen"/"Dark Byte" in the
binary, publisher fields reading **"Pluto Inc."** spelled with **Unicode
homoglyphs** (`𝖯loo𝗍o` — mathematical sans-serif letters substituted for ASCII,
a string-detection evasion), NSIS+Inno markers wrapping one opaque 5.9 MB blob.
It is the bundler/downloader stub, code-signed by the bundler rather than by
CE's author. It was not installed. If CE is ever wanted, get it somewhere that
serves a direct installer, and verify the publisher before running it.

## Install

```
tools/setup-debugger.sh            # pinned download + sha256 verify + install
tools/setup-debugger.sh --launch   # run it inside the prefix
tools/setup-debugger.sh --remove   # undo
```

The download is sha256-pinned (same convention as `setup-input-remapper.sh`);
the binary is never committed to this repo.

## The workflow — step by step

**Order matters: get the address FIRST, then breakpoint it.**

### 1. Find a candidate address (debug menu, no debugger)
In a mission with `tools/debugmenu.sh` running: press **F10**, type your current
HUD ammo (e.g. `1995`) → fire a few rounds → **F10** again, type the new number
→ repeat. 2–4 passes usually leaves a handful. Note one address (the SCAN view
and `debugmenu.log` both list them).

### 2. Attach x32dbg
`tools/setup-debugger.sh --launch`, then in x32dbg: **File → Attach** (Alt+A),
pick **i76.exe** from the list. The game freezes — that's expected, the
debugger owns it now.

*If attach is refused:* fall back to launching the game *from* x32dbg so the
debugger creates the process and inherits rights. Caveat from the RE log:
`i76.exe` launched outside its DxWnd context crashed with `c0000005`, so point
the debugger at the DxWnd launcher instead of the bare exe.

### 3. Breakpoint the address
In the **Dump** pane, Ctrl+G → type the address from step 1 → Enter. Select the
4 bytes, right-click → **Breakpoint → Hardware, Write → Dword (4 bytes)**.
(Hardware = a DR register, which is what catches a *write* without patching
code. If Wine refuses the hardware breakpoint, that's our remaining unknown —
note it and fall back to the scan ladder below.)

### 4. Resume and fire
Press **F9** (Run) to let the game continue, switch to the game, and **fire the
weapon once**. x32dbg breaks the instant something writes that address.

### 5. Read the answer
The instruction at EIP is the prize. Something like `mov [esi+0x18], eax` gives:
- `esi` (see the Registers pane) = **the struct base** — the real record's base
- `0x18` = **the field's offset** inside that struct

Also read the few instructions *above* the write: they reveal the **encoding**
(e.g. a `sub eax, [fired]` would prove the HUD value is derived rather than
stored), which is exactly what three rounds of blind scanning could never settle.

### 6. Make it permanent
Convert the base into something relocation-proof: either walk it up to a static
global, or express it relative to the player entity (our chain already resolves
`[[[0x54a264]]+0x70]`). `tools/findval.sh peek 0xADDR` prints any address as an
entity-relative offset. Then it goes into `tools/i76-addresses.json` and becomes
a named row in the debug menu.

**Bring back:** the instruction text, the register values at the break, and the
entity-relative offset. That trio is enough to wire it into every tool we have.

## Honest expectations

Debug-attach on macOS-hosted Wine is unproven for x32dbg — `winedbg` attach was
denied and launch-under-debugger crashed outside DxWnd. x32dbg uses the Win32
debug API that Wine implements internally, so it has a genuinely better chance,
but **treat it as an experiment, not a certainty**. If it can't attach, the
fallback ladder is:

1. the debug menu's F10 successive scan (works today, no debugger),
2. the chain differential (`i76-chaindiff.ahk`) for relocation-proof offsets,
3. running the whole stack on the Windows box or the Steam Deck, where
   debugger attach has no OS-level restriction.
