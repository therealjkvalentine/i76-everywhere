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

## Install

```
tools/setup-debugger.sh            # pinned download + sha256 verify + install
tools/setup-debugger.sh --launch   # run it inside the prefix
tools/setup-debugger.sh --remove   # undo
```

The download is sha256-pinned (same convention as `setup-input-remapper.sh`);
the binary is never committed to this repo.

## The workflow (what we're actually after)

1. **Get an address for a value you can see.** Use the debug menu's F10
   successive scan (type the HUD ammo → fire → F10 → type the new value →
   repeat) until a handful of candidates survive. Note one address.
2. **Launch x32dbg** and attach to `i76.exe` (File → Attach). If attach is
   refused — the same macOS restriction that blocked winedbg may apply here —
   fall back to launching the game *from* x32dbg so the debugger creates the
   process and inherits debug rights. Caveat from the RE log: launching
   `i76.exe` outside its DxWnd context crashed with `c0000005`, so this may
   need the DxWnd launcher as the debuggee instead.
3. **Set a memory-write breakpoint** on the address (right-click in the dump →
   Breakpoint → Hardware, Write, 4 bytes).
4. **Fire the weapon.** The debugger breaks on the writing instruction.
5. **Read the instruction.** Something like `mov [esi+0x18], eax` tells you:
   - `esi` = the struct base → its live value is the real record base
   - `0x18` = the field's offset inside that struct
6. **Walk the base up to a static root** (or express it relative to the player
   entity, which our chain already resolves) so it survives relocation, then
   add it to `tools/i76-addresses.json` and the debug menu.

Step 5 is the payoff: it also *names* the encoding by showing the arithmetic
around the write (e.g. `sub eax, [fired]` would prove a derived display), which
is exactly what settled nothing in three rounds of blind scanning.

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
