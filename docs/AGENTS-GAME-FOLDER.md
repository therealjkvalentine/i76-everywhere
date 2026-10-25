# AGENTS.md - Interstate '76 game folder (template: copy to the folder root, fill the <angle brackets>)

Latest information: https://github.com/therealjkvalentine/i76-everywhere (docs/, docs/records/, tools/). This file is a pointer, not the source of truth.

## What this folder is
- Role: **<dev | test | rc | daily driver | nitro-dev | nitro-test | nitro-rc>**. Game: **<Gold (Interstate '76 + Arsenal) | Nitro Pack>**. Version/proxy: see `VERSION.md` and the md5 of `Interstate 76\STRLKUP.DLL` (Nitro: `strlkup.dll`).
- dev = the one working copy lanes build into. test = the gate twin; lanes copy it, never build new long-lived copies. rc = what the owner plays before promotion. daily driver = what the owner plays; never experiment on it.
- Launchers: `PLAY.bat` / `PLAY-TICK.bat` = the default single player; `PLAY-LAN.bat` = host or join the family; `DEBUG.bat` = debug tool; `PLAY-STABLE.bat` / `PLAY-P18-BALANCED.bat` = controls; `PLAY-T05.bat` = the 05 variant. <list only what exists here; `README.md` in `Games\I76` has the owner-facing table>.
- Where things are: proxy `Interstate 76\STRLKUP.DLL` (plus `strlkup_orig.dll` = the real original); presets `Interstate 76\presets\*.psd1`; launcher `Interstate 76\PLAY-i76.ps1`; dgVoodoo `dgVoodoo.conf` + `Interstate 76\dgVoodoo.conf`; controls `Interstate 76\input.map`; log `Interstate 76\mciproxy.log` (rotates; look for the `CRASH` line); rollbacks `_rollback\`.
- The one real original of each patched file stays: `strlkup_orig.dll`, `i76.exe.u32xorig`, `i76shell.dll.orig` (and `input.map` backup kept as one `known-good`). Do not delete these; anything else named `*.pre-*`, `*.driver-*`, `STRLKUP.DLL.<md5>` is cruft (`tools\consolidate-copies.ps1 -Phase Cruft` lists it).

## Troubleshooting (first stop)
- No picture / black / wrong size: dgVoodoo reads a **global** conf if it rejects this one; flip a visible key (`dgVoodoo.conf` resolution) to prove the conf loads. Windows 11 October-2026 update: use dgVoodoo **2.87.5** plus the winmm fix.
- No sound: Windows remembers a mute **per exe path**. Close the game, then `tools\unmute-persisted.ps1 -Exe "<folder>\Interstate 76\i76.exe"` (lab `tools\`). Music needs `i76.exe`, not `i76_pristine_fix.exe`.
- Crash or freeze: open `Interstate 76\mciproxy.log`, find the `CRASH` line (fault offset, module), then the repo `docs\records\`; a hang with a ghost window is DWM ghosting, not the engine.
- LAN will not connect: **everyone needs the same proxy md5** (and the same pack version); check Windows Private network allowed for `i76.exe` / `nitro.exe`, IPX wrapper adapter = the home Ethernet, UDP 54792 (Nitro).
- Sluggish or stepped motion: tick/preset mismatch; start from `PLAY-TICK.bat`, not an old variant. Nitro: `PLAY-NITRO-LAN.bat` / `PLAY-NITRO-ALL.bat`.

## Rules
- Never experiment on the daily driver or the rc. Test from a twin of `test`; delete the twin at lane end.
- One game per console: take `C:\Users\james\i76-uncap-lab\.console-owner` (exclusive create) before a visible run; honour `.console-test.lock`, `.fps-lock` / `.fps-queue`; never kill a process you did not start.
- Automated runs set `I76_SHM_SUFFIX` and their own desktop and mute only the game they launched (`I76_MUTE=1` + `tools\start-mute-watch.ps1`). Never run against default shared-memory names while the owner may be playing.
- Check which build is live before diagnosing (docs record intent, not state); read the setting back after every write; keep the folder name, `VERSION.md` and the proxy md5 in agreement.
- Saves (`savegame*`, `*.sav`, `*.dir`) are the owner's: never delete or "clean" them.
