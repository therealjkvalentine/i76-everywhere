# Reverse-engineering vintage games: a cited field guide

*Deep-research synthesis (2026-07-18): 6 search angles, 26 sources fetched, 110
claims extracted, 25 adversarially verified (3-vote), 24 confirmed / 1 refuted.
Framed as a learning roadmap for someone RE-ing a legally-owned 1997 Win32 game
(Interstate '76) under Wine on a Mac, reading its process memory to build a
trainer and map data structures. Each finding below cleared a 3-0 verification
vote unless noted.*

## The textbook canon (four load-bearing titles)
- **Nick Cano, *Game Hacking* (No Starch, 2016)** — the single most on-target
  book for our task: memory scanning, debugging, programmatic memory
  manipulation, and code injection, taught hands-on against Windows game
  processes. Part 1 "Tools of the Trade" canonizes the exact toolset: **Cheat
  Engine** (scan), **OllyDbg** (debug; today x64dbg), **Process Monitor/Explorer**
  (recon). https://nostarch.com/gamehacking
- **Chris Eagle, *The IDA Pro Book* 2nd ed. (No Starch, 2011)** — the standard
  static-disassembly reference (navigating/commenting disassembly, library-routine
  ID, cross-reference/call graphing). Vintage but still the IDA bible; for a
  from-scratch project on an owned binary, **Ghidra** (free, NSA) is now the
  pragmatic default. https://nostarch.com/idapro2
- **Dennis Andriesse, *Practical Binary Analysis* (No Starch, 2019)** — full
  spectrum, hands-on: binary formats, disassembly, instrumentation, taint
  analysis, symbolic execution. https://nostarch.com/binaryanalysis
- **Dennis Yurichev, *Reverse Engineering for Beginners* (RE4B)** — free/libre
  (CC BY-SA), 1000+ pages, the beginner→intermediate x86/asm canon.
  https://beginners.re/
- *Named in the ask but not independently verified in this pass (real books,
  lower-confidence here): Eilam's* Reversing: Secrets of Reverse Engineering,
  *Bruce Dang's* Practical Reverse Engineering, *Huang's* Hacking the Xbox.

## Canonical wikis & reference sites
- **Cheat Engine wiki** — the primary reference for the memory-RE workflow:
  finding integer/float values, pointers & pointer scanning, the stack, value
  types, basic/full code injection, Array-of-Bytes (AOB) scanning. (CE 7.6.)
  https://wiki.cheatengine.org
- **ModdingWiki / ShikadiWiki** — the canonical *static* file-format reference
  for DOS-era PC games (427 file formats, 67 archive formats: EXE/RFF/WAD/PAK…),
  written to help people build editing tools. https://moddingwiki.shikadi.net
- **GameHacking.org** — anchors the *runtime* side: "modification of a platform's
  system memory during game play… single-player cheat codes." https://gamehacking.org
  *(A claim that it hosts "the largest collection of hacking guides on the web"
  was refuted 0-3 and dropped.)*

## Curated roadmaps & the standard toolchain
- **kovidomi/game-reversing** — a memory-first 10-step progression: Google →
  Cheat Engine → hex/binary+memory → x86 asm → C++ → IDA/Ghidra → game
  programming → Win32 API → Windows internals → practice.
  https://github.com/kovidomi/game-reversing
- **dsasmblr/game-hacking** — ~5.5k-star curated list grouping the toolchain by
  function. https://github.com/dsasmblr/game-hacking
- **The standard Win32 process-memory toolset** (both repos agree): **Cheat
  Engine** (scanning), **ReClass.NET** (struct dissection — mapping in-memory
  data structures), **x64dbg** (debugger), **IDA** / **Ghidra** (static
  disassembly), HxD/ImHex (hex).

## The endgame: engine recreations vs source ports
A **recreation** is a new engine written from scratch that reads the original
game's data files, usually built by studying/reverse-engineering the original
executable (ScummVM, OpenMW, Chocolate Doom, Exult, DevilutionX-class). A
**source port** is the special case where the original developers released the
source. https://en.wikipedia.org/wiki/List_of_game_engine_recreations
*(Our repo's context: Roanish/i76 is a recreation-style Ghidra decompile;
Open76 is a Unity recreation.)*

## Legal & ethical framing (US; not legal advice)
- **Reverse engineering is broadly lawful.** It "generally doesn't violate trade
  secret law because it is a fair and independent means of learning information"
  (EFF). https://www.eff.org/issues/coders/reverse-engineering-faq
- **Sega v. Accolade (9th Cir. 1992)** — disassembly to reach unprotected
  functional/interface elements is **fair use** where it's the only means of
  access and there's a legitimate reason.
- **Sony v. Connectix (9th Cir. 2000)** — intermediate copying/disassembly of
  console firmware to build an emulator is fair use, valued as transformative and
  expanding consumer platform choice.
- **DMCA §1201** is the real constraint: it bars circumventing technological
  protection measures (auth handshakes, encryption, code signing, obfuscation)
  that control access. **§1201(f)** carves out RE by a lawful user "for the sole
  purpose of identifying and analyzing those elements… necessary to achieve
  interoperability of an independently created program."
  https://www.everycrsreport.com/reports/RL32692.html
- **Upshot for this repo:** inspecting your own legally-owned, **DRM-free** game's
  process memory defeats no access control, so §1201 isn't even triggered; the
  interoperability/preservation purpose sits squarely in the protected zone.
  (See docs/LEGITIMACY-AND-SCOPE.md.)

## The memory-first roadmap for I'76 (what this maps to for us)
1. **Cheat Engine + the CE wiki** for value discovery and unknown-value /
   increased-decreased scans — run CE *inside the wineprefix* (docs/RE-METHODOLOGY.md)
   so it attaches cleanly to the Wine process.
2. **"Find what writes/accesses this address"** (CE / x64dbg watchpoint) to read
   the encoding off the disassembly and get the base-register + offset — the
   conclusive step our pure-AHK reader can't do.
3. **ReClass.NET** to dissect the vehicle/weapon structs once a base pointer is
   known.
4. **Ghidra** for the static side (we already do this via tools/exe-xref.py +
   exe-disasm.py; Ghidra adds a decompiler and xref graph).
5. **Cano's *Game Hacking*** as the connecting text tying scanning → debugging →
   injection → trainer.

*Caveats: textbook/legal findings rest on primary sources (publisher pages,
statute via CRS/Cornell, EFF, court reporters) at 3-0 confidence; tooling/wiki
findings rest on authoritative self-descriptions (3-0, one rung below judicial
primary sources). The IDA book (2011) and OllyDbg are dated; Ghidra/x64dbg are
the modern defaults. Legal notes are US-only and not legal advice. Several items
named in the research question — Eilam, decomp.me/m2c, Data Crystal, TCRF,
Xentax, specific named individuals — did not surface as independently verified
claims in this pass and are omitted rather than asserted.*
