# A working copy from a fresh GOG install, Gold and Nitro, in one command (2026-10-23 night)

Owner (overnight ask, via the coordinator): "make sure that our repo can build a working copy of the game from a new GOG install for
Gold and Nitro." Lane: Tester-release. Repo commits fa50460 (build-proxy.ps1), b6d1e81 (Build-From-GOG.ps1, Gold), 5cee886 (Nitro),
73cfd8d (the options bytes, see SCOTT-BUILD s.8.1 c).

## Answer

```
tools\Build-From-GOG.ps1 -GogDir <fresh GOG install> -OutDir <new folder> [-Ref <sha>] [-Preset <name>] [-Display WxH] [-NoSupersample]
```

reads the GOG folder (never writes it), copies it to `-OutDir` and makes it a working i76-everywhere copy. Game detected by the exe
(`i76.exe` = Gold, `nitro.exe` = Nitro Pack); a folder that already carries our files is refused. Proven on lab copies of the pristine
GOG installs, n 2 each, console:

| | Gold (GOG 2.1.0.17, i76.exe 9a232dcc; `<re-archive>\sandbox-gog\main\app`) | Nitro (GOG, nitro.exe 28b8ae27; `<re-archive>\sandbox-gog\nitro-full\app`, NITRO-BASE) |
|---|---|---|
| copy | lab `game-fresh-gold` | lab `game-fresh-nitro` |
| build | exit 0; proxy b45643d2 from fa50460 | exit 0; proxy b45643d2 from b6d1e81 (same music-fix tree) |
| boot + menu pointer | gate row 3 through the built PLAY.bat: TRIP -> LOAD BOOKMARK -> row -> LOAD -> ACCEPT SALVAGE -> DONE by clicks, mission up at 120 fps, **2 of 2** | PLAY-Nitro.bat as built: title -> main menu -> click MELEE -> MULTI MELEE / INSTANT MELEE shown, **2 of 2** (identical captures) |
| mission + drive | gate row 9 (T05, the owner's route, keys): hill **120.0 fps, 1 % low 87.9 / 89.2** over 2607 / 2615 m, n 2 | P01 direct boot (`PLAY-i76.ps1 -Exe nitro.exe -Mission P01.msn`), I + W / Up held 24 s: **419 / 424 m driven, 33.2 / 33.8 m/s** (telemetry), 120.0 fps, 1 % low 103.9 / 105.3, n 2 |
| proxy log | every tick19-42 switch applied (as SCOTT-BUILD s.6.2) | `sim-tick: ON ... 12/12 sim gates`, aspect 20/20, cursor map (shell aw); 0 UNEXPECTED / NOT applied |
| crash lines | the frame-0 PIT probe only (exe+0x99997, handled) | the same probe at Nitro's exe+0x9ACB7 only |

Evidence: lab `builds\tester-20261023\gate-20261023-213910` (+ autotest runs 214341 / 215227 / 220504), `nitro-proof-20261023-221707`
(captures, telemetry CSVs, proxy logs; the first pass 220911 had a title screen where the menu was expected - the script now clicks
through the title first).

## What it does

1. `tools\build-proxy.ps1 -Ref <sha>`: git archive of music-fix at that commit, MSVC x86 /MT /O2 /Brepro (the staged builds' recipe, now
   in the repo). Deterministic: `-Ref 9fe3510` gives the the tester zip's 6208d3ad byte for byte.
2. `tools\package-tester.ps1 -Proxy <it> -Stage <cache>`: the overlay stage with nothing of GOG's (dgVoodoo 2.87.3 and AutoHotkey 1.1.37.02
   downloaded once into `%LOCALAPPDATA%\i76e-cache` when not given; dgVoodoo md5-checked against the release by the packer; the downloaded
   AutoHotkeyU32.exe is b6af97aa, the shipped one).
3. Gold: the copy, the overlay over it, `_i76e\i76e-prepare.ps1` (the tester build's first-run setup: shell key patch, setup-windows.ps1
   with tick19-42, u32x, dgVoodoo, controls, saves, the graphic-detail options, and the display fit). Launchers as in README-TESTER.md:
   PLAY.bat (stable), PLAY-PREVIEW.bat (graphics preview), PLAY-T05*.bat, UNINSTALL-i76e.bat.
4. Nitro: the copy, then the stage's own `setup-windows.ps1 -Exe nitro.exe -Preset nitro-tick42 -Controls stock -Display <primary>`:
   dgVoodoo's Glide for GOG's OpenGLide, the proxy (built at -Ref), `presets\nitro-tick42.psd1`, the wide conf for the display,
   `PLAY-Nitro.bat` (and `PLAY-stock.bat` = no engine switches). setup-windows.ps1 change: Nitro stays stock unless `-Preset` is named;
   with one it gets the proxy; PLAY-16x10 / PLAY-balanced (Gold presets) are not written for Nitro.

## The Nitro preset

`presets\nitro-tick42.psd1` = the nitro-port lane's lab `tools\nitro-port\nitro-tick42.psd1` (the ported subset of tick19-42: tick
41.667, hires clock, 1200 m view, terrain / object / road / shadow detail, ground + hull fixes, health % / label table, ZGLIDE TMU fix,
120 Hz, Hor+) plus the cursor-map keys of NITRO-PORT s.10 (`I76_CURSOR_MAP=1`, `_DGV=aw`, `_SHELL=aw`: Nitro imports USER32 directly, no
u32x). The nitro lane's owner preset (OWNER-NITRO-ALL, exp-nitro-owner, in progress tonight) did not exist yet; when it settles, copy it
to `presets\` and pass `-Preset <name>` (or make it the default in Build-From-GOG.ps1).

## Limits

- Gold and Nitro sources were the lab's extracted GOG installs (Galaxy layout), not a run of GOG's offline installer.
- The Nitro copy keeps GOG's 1997 key map (`-Controls stock`): this repo's input.map and the AHK pad / wheel layers are Gold's.
- Nitro: no u32x (never run with nitro.exe); the save screen / Esc menu were not exercised on Nitro.
- `-Ref` decides the proxy only; the scripts, presets and launchers come from the working tree (package-tester warns when they are dirty).
- Setup messages still name i76.exe in places on Nitro (e.g. the music note); cosmetic.
