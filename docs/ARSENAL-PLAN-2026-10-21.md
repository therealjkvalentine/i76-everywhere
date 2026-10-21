# Arsenal plan (2026-10-21): ship for Gold AND Nitro, multiplayer on Nitro

Owner ruling, 2026-10-21 morning (verbatim): "arsenal is both and they are separate, got it. let's do the work to
understand and fix nitro same as we did for gold. we'll plan to ship for arsenal so it's complete. get as far as you
can with that. i guess from a multiplayer perspective we'd want nitro to be the basis instead of gold so we'll have
some rebuilding to do there. let's try to do it nondestructively, so that community play of nitro multiplayer is
unperturbed. perhaps it's a new menu item we'd add separately but not sure what we'd call it ai drop in coop something".

## Facts the plan rests on (measured 2026-10-20/21)

- GOG's *Arsenal* is two standalone products: Gold (`i76.exe` 9a232dcc; we ship 6319abf7 = Gold + AiO patch + our
  import rename) and Nitro Pack (`nitro.exe` 28b8ae27). Nitro ships ONLY its own content: campaign P01-P19, arenas
  N01-N32 (combat / capture-the-flag / race). The original campaign T01-T17, arenas M01-M15 and scenarios S01-S07 are
  not in it (records/NITRO-BASE-2026-10-21.md; a playable `Games\I76\nitro` and `nitro-plus-original` exist for the
  owner's own check).
- Nitro = Gold's engine relinked (records/NITRO-VS-RETAIL-2026-10-20.md): physics and car-step loop identical, formats
  identical, 1,997 of 2,200 Nitro functions matched to Gold (1,781 identical after relinking). Differences: combat
  (droppers, specials, 7 weapons), ANet 2 with new transport DLLs (WIPX2 / WINETS2 / WMODEM2 / WSERIAL2), a game-server
  lobby, vehicle validation, its own shell `NITSHELL.DLL`, race / CTF logic, Aureal sound, Gold's far-clip cap.
- `nitro.exe` imports `Strlkup.dll` (our proxy's load vector, unchanged), `WIN32.dll` (GOG's winmm replacement:
  the music hooks must take that route, cf. memory "i76fix exe has no WINMM import"), `anet2.dll`, `NITSHELL.DLL`,
  `USER32.dll` directly (our u32x attaches by import rename as on Gold).
- The proxy has 845 distinct address-bound sites in 13 source files, all placed for the Gold exe.

## Shape of the work

1. **Port foundations (lane: nitro-port).** Exe detection by hash in the proxy -> a per-exe address table; a
   Gold-to-Nitro site map generated from the Ghidra function matches (ghidra\export, export-nitro) and verified per
   site by byte signature; the proxy refuses a site whose signature does not match (log line, feature off) rather
   than patching blind. Port order: DllMain / logging / telemetry / trainer shm; hires clock + whole-sim tick;
   far clip + terrain (LOD, hysteresis, freeze, vertex guard, cam-ground, hull); cursor map + u32x shell map (NITSHELL);
   music (WIN32.dll route); fixes (health %, label table, breakable box, sign sweep, ZGLIDE TMU); the shell key / popup
   patches (NITSHELL equivalents of the i76shell F7 set); the debug tool. Each subsystem: the same measurement that
   proved it on Gold, re-run on Nitro (harness `autotest\proxy-run.ps1` pointed at a Nitro copy), recorded in
   records/NITRO-PORT-*.md, staged in lab builds\nitro-port-*\.
2. **Multiplayer on Nitro, non-destructive (lane: nitro-mp-design, then nitro-mp).** Stock Nitro multiplayer
   (ANet 2, lobby, IPX, race / CTF) stays byte-for-byte in behaviour; our features live behind a SEPARATE entry in
   Nitro's multiplayer menu (working name to be chosen by the owner: "AI DROP-IN", "CO-OP / AI MELEE", "ARENA+") that
   turns on: join / leave any time with AI filling empty slots, AI respawn and scoreboard rows, teams rule, co-op
   scenes with per-joiner scaling, difficulty-driven AI skill, the original 15 arenas and 7 scenarios and co-op scenes
   as list entries. The entity-level code (injected pool records, mpfill, aimelee, teams) is netcode-independent; the
   packet layer (our 'AT' / 'AK' / 'AM' / 'ST' use of dpReceive) must be rebuilt on ANet 2's receive path. A player who
   never opens the new entry sees stock Nitro; a stock Nitro player can join stock sessions hosted by a patched game.
3. **Campaign content on Nitro (lane: nitro-base, running).** Whether Nitro's shell plays the original campaign,
   arenas and scenarios from files placed beside it; what the trip / garage / FMV / save path needs.
4. **Gold keeps shipping.** Promotion 19 on Gold (tick + terrain + polish + AI + difficulty) proceeds as planned; the
   family plays Gold until the Nitro multiplayer entry is gated. Arsenal = both patched exes in one pack, one README.

## Validation (unchanged)

Every Nitro subsystem is measured the way its Gold version was, against the same 1997 reference, and the community
validation list (OWNER-TEST-LIST "Rulings 2026-10-20 evening", the Local Ditch email) applies to both exes.
