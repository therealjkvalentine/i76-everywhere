# Nitro polish: the owner's five notes from his Nitro session (2026-10-24 evening / 10-25 night)

Owner's notes: docs/OWNER-TEST-LIST.md "2026-10-24 afternoon: owner playing Nitro missions". He played them in
`i76-uncap-lab\exp-nitro-owner` (PLAY-NITRO-ALL.bat, preset OWNER-NITRO-ALL).

All tests ran in a lab copy, `i76-uncap-lab\exp-nitro-polish`. Most were console boots of p01 (n per row) and the owner's
menus route. The tools are lab `tools\nitro-polish\`:
- `np-run.ps1` and `pcon.ps1`: the nitro-owner lane's no-run / ncon, with the MP lane's headless `game-mpo-*` copies no longer
  blocking a boot;
- `edgecap.ps1`, `loud_files.py`, `lufs_cat.py`, `loud_music.py`, `nsdis.py`.

Logs are in lab `captures\nitro-owner-20261023\np-*` and `captures\nitro-polish-20261024\`.

## Answer

| # | note | cause | fix | status |
|---|---|---|---|---|
| 3 | voices too quiet, SFX too loud, worse than Gold | **Nitro has had no 3D sound since A3D drivers went away, and with 3D on it applies no volume.** Every SFX played 2D at full level, whatever its distance | proxy `I76_NITRO_DS3D` and `I76_NITRO_3D_VOLUME` (default on, Nitro only), plus per-category gains and the music slider curve | built and measured (s.3); installed in the owner's copy |
| 5 | "Rename variant to save": mouse can't reach it, Enter does nothing | it is a `Modal_Ok` popup. Its loop presents no frame, so dgVoodoo's drawn pencil stays frozen on DONE while the real pointer moves; a blind click on OK works. The loop also reads no key (1997; Gold's shell has the F7 fix) | NITSHELL F7 + M2 + K1-K4 (the nitro-port lane's scripts, staged since 10-21 and installed nowhere), now installed | reproduced and fixed on the console (s.5) |
| 4 | the bus can't be made to stop | **player technique**. P17 "Velocity" has no speed test. The bus stops (`sit`) once its health is under 65 %, i.e. one side's armour below ~51 % of 1050 (about 10 hard rams on the same side) | none needed | static (s.4) |
| 1 | a dropper-like sound repeats / sticks | not reproduced. Gold's sign-sound restart is already on Nitro, and no voice outlived its sample in the logs. The only periodic sound in p01, `CRADAR.WAV` (radar ping, ~0.3 / s), has the same rate with and without the tick. The likely contributor was #3: every distant sound played at full level | #3; the owner's preset now logs the sound names (`I76_SOUND_VOL_LOG`) so the next occurrence is identified | open, needs a mission / moment from the owner (s.1) |
| 2 | flashing a few pixels wide around the screen edges | not reproduced: 950 edge-strip grabs over 45 s of driving, no edge-only flash. No Gold "edge flash" fix exists in the repo, lab docs or proxy; the owner's Gold and Nitro presets and dgVoodoo.conf are identical | none | open, needs where / when from the owner (s.2) |

Installed in `exp-nitro-owner` (no nitro.exe running; 2026-10-25 ~00:00):
- `strlkup.dll` **9f220ac3**, built from 8ba6f70. The old one is kept as `strlkup.dll.53944fb2`.
- `nitshell.dll` **a32ffba6**. The old one is kept as `nitshell.dll.f804f50d`.
- `presets\OWNER-NITRO-ALL.psd1` **1cc67766**, adding the sound keys in s.3. The old one is kept as `.f629a78b`.
- `WHAT-THIS-IS.txt` updated.

## 1. The repeating / sticking sound

- **Gold's fixes already apply on Nitro.**
  - `I76_SIGN_SOUND_RESTART` was ported by the nitro-owner lane (NITRO-PORT s.11.1). The owner's log reads
    `sign-sound: I76_SIGN_SOUND_RESTART=1`.
  - The tick's sustained-loop keep-alive (TICK-FINISH s.10) runs on Nitro: `sustained sounds kept between ticks ON`. Nitro's
    frame loop calls the camera wrapper (0x432e5b) before the sound update (0x432e6c), as Gold does (0x403e16 / 0x403e27).
  - The repo has no other "stuck dropper" fix. OWNER-TEST-LIST, records and lab docs were searched.
- **Census** (`I76_SOUND_CENSUS`, now also on Nitro; p01, 64-66 s, console):

  | arm | CRADAR starts | rate |
  |---|---|---|
  | tick 24 / s, DS3D on | 18 | 0.27 / s |
  | tick 24 / s, DS3D off | 21 | 0.33 / s |
  | no tick | 19 | 0.30 / s |

  The CB lines play the same 7 in the same order in all three arms.
- **Active voice list** (every 10 s, with each buffer's own GetStatus / GetFrequency / GetVolume): no one-shot outlived its
  sample. Loops belong to live cars (engines; tyre / dust with keep-alive).
- **Likely contributor: s.3.** Before the fix every sound played 2D at full level wherever it came from: AI weapons, droppers
  and impacts hundreds of metres away. In Gold these fade with distance (min 10 m, max 400 m).
- **Next time.** The owner's preset now carries `I76_SOUND_VOL_LOG=1`. When the sound happens again, the time of day is enough
  to name it from `mciproxy.log`'s `sound-vol: active` lines.

## 2. Edge flashing

- **No Gold fix to port.** No record, lab doc or proxy source has an edge / border flash fix. The searches covered flash /
  flicker / edge / border / letterbox / pixel; the hits were the terrain-to-sky flash (`I76_CAM_GROUND_FIX`) and the hull
  fix (`I76_TERRAIN_HULL_FIX`), both on in the owner's Nitro set.
- **The Gold and Nitro setups are identical here.**
  - The owner's Gold preset OWNER-2300-ALL and Nitro preset differ only in the u32x / LAN keys.
  - Both copies have dgVoodoo.conf dccd379a and launch with `-LosslessScaling none`.
- **Capture** (`edgecap.ps1`): mean colour of 2-px bands 0..31 px in from each screen edge, against a band 200 px in, ~20
  grabs / s.
  - Two runs in the melee arena (Evening Stroll), cockpit view, menus route: 450 grabs straight on, then 500 turning.
  - Result: 0 edge-only jumps, at thresholds of 40 and 25 grey levels.
  - The outer 1-2 px are a constant dark border on every side. One 3-grab rise of the 4th-5th row from the bottom (+14
    grey over the inner band) is the only edge-specific change.
- **Not settled.**
  - A one-frame flash (8 ms at 120 fps) falls between ~50 ms grabs, so a rare flash can be missed (n 2 runs, 45 s).
  - Not tested: other missions, chase view, explosions, the menus.
- **Needs from the owner:** where it happens (menus or mission, which edge, cockpit or chase), and whether it is the same as
  Gold's old one.

## 3. Sound balance

### 3.1 How the engine sets loudness (static, both exes side by side)

- **SFX and voices.**
  - One SetVolume call per exe: Gold 0x421854, Nitro 0x419d2c.
  - millibels = T[trunc(vol% x 0.1 x L)], where T[0] = -10000 and T[i] = 400 log2(i / 100) (Gold 0x5fcc20, Nitro 0x654680).
  - L is the SFX level (manager +0x14) or the voice level (+0x18) for voices with flag 4 (CB / mission speech).
  - So the sliders fall **4 dB per halving**.
- **Music.**
  - The level goes to auxSetVolume, then the proxy's `setaudio volume` 0..1000, then mciqtz32 0x1c102b49:
    `AmpFactorToDB(v x 65535 / 1000)` (quartz).
  - That is linear amplitude: **6 dB per halving**. At equal mid sliders, music sits 2 dB further down than SFX and voices.
- **Options.** Nitro's block is at 0x5fb0a0; music / SFX / voice are bytes 0x51 / 0x52 / 0x53. Gold's is at 0x654b40, bytes
  0x50 / 0x51 / 0x52.
  - The owner's Nitro nitplyr.def: **music 7, SFX 2, voice 10**.
  - His Gold set: music 6, SFX 8, voice 10.
  - He had already pulled SFX down to 2 and voices up to full, and still heard SFX too loud and voices too quiet.

### 3.2 Nitro's two faults (measured)

1. **No 3D at all.**
   - Nitro's DirectSound start (0x41bea0) asks for 3D only through Aureal A3D: CoCreateInstance(CLSID 0x4c1b30, IID 0x4c5468)
     at 0x41befc.
   - With no A3D driver it clears the 3D flag [0x4f1e84] (`mov [ebp], ebx` at 0x41bf16) and falls back to plain DirectSound.
     The primary buffer is then made without CTRL3D and no listener is asked for.
   - Gold always uses DirectSound 3D: primary flags 0x11 and the listener QI at 0x425db9. Gold does not even start sound
     without it.
   - Measured: listener 0 and flag 0 on the console (n 2) and headless (n 2). Every voice was 2D at its full level.
2. **With 3D on, no volume.**
   - Nitro's apply step 0x419c90 jumps over its volume block when the manager has a listener (`mov eax, [mgr + 8]; test; jne`
     at 0x419ce9). Gold's block is skipped only by [0x52467c], which is zeroed at sound start and never set.
   - Measured with DS3D on and the block stock: **0 SetVolume calls in 45 s** (console p01).
   - So a 3D Nitro would ignore both sliders and every sound's own volume %. This is presumably why the A3D era was set up
     that way (A3D handled level itself).

**Fix** (music-fix/soundmix.c, commit 8ba6f70):
- `I76_NITRO_DS3D` (default 1 on Nitro): 0x41bf16 -> nop. The flag stays on for the DirectSound fallback, so the game gets a
  3D primary buffer and a listener, as Gold.
- `I76_NITRO_3D_VOLUME` (default 1 on Nitro): 0x419ce9 -> a stub that runs the stock block (same table, same 0.1 x L product,
  ftol truncation) before the 3D path.

| console p01, owner's set (n) | listener | 3D flag | SetVolume on the 3D path | CB lines | faults |
|---|---|---|---|---|---|
| stock (proxy before), n 2 | 0 | 0 | n/a (2D path: 4800 / 10 s) | 7 | 0 |
| DS3D only, n 1 | present | 1 | **0** | 7 | 0 |
| DS3D + 3D volume, n 3 (incl. the menus route) | present | 1 | 3692 / 10 s, = the SFX calls | 7, same order | 0 |

With the fix, objectless sounds (CB lines, radar, gear-shift) stay 2D. Car sounds are 3D and carry the slider's millibels: SFX
level 2 gives -928 mB, and eimarx at 60 % gives -1223.

### 3.3 Equal sliders = equal loudness

- **Content loudness** (BS.1770 K-weighted, gated LUFS, medians; `lufs_cat.py`):

  | category | n | median LUFS | p25..p75 |
  |---|---|---|---|
  | SFX (.gpw: engines, impacts, weapons) | 123 | -11.5 | -14.2..-9.5 |
  | Nitro voice lines | 765 | -13.3 | -14.7..-11.9 |
  | music mp3s | 11 | -19.5 | -19.9..-17.5 |

  - Nitro and Gold voice files are within 0.3 dB of each other (active RMS -14.3 / -14.6), so the files are not why Nitro
    sounded worse.
- **New switches** (both exes, off when unset, so Gold is unchanged):
  - `I76_SFX_GAIN` / `I76_VOICE_GAIN` (dB at the SetVolume call; silence kept; clamped to 0 dB);
  - `I76_MUSIC_GAIN`;
  - `I76_MUSIC_CURVE=sfx`: the music slider follows T, amplitude = level^0.664, so equal slider positions give equal mix gain.
- **Owner's preset:** SFX -8, voice -6, music curve sfx. These bring all three to the music's level at equal sliders (music is
  the quietest content and cannot go above 1000).
- **Read back** (console, n 1):
  - `sound-mix: on - SFX -8.0 dB, voice -6.0 dB`;
  - `01jad01.wav ... voice level 10 -> 0 mB stock, -600 sent`;
  - `eihp.wav ... sfx level 2 -> -928 mB stock, -1728 sent`;
  - music `auxSetVolume(0x59945994) -> 498/1000` (stock 350).
- **Not measured: audible playback.** The test instances are muted (CONSOLE-LOCK rule), so there was no loopback recording.
  The balance comes from the exe's own gain laws, read from code, plus the content loudness. **The owner judges by ear.**
  - With his current sliders (music 7, SFX 2, voice 10), SFX will now be much quieter (distance and gain): raise SFX.
  - Equal positions should give equal loudness. If one category is off by ear, change its `I76_*_GAIN` in the preset by a few
    dB.

## 4. The bus mission (static; subagent read, checked against the damage doc)

- **The mission.** P17 "Velocity" (miss16\P17.MSN; objectives from nitro.zfs p17.npt): "Find the bus and disable it using
  your car. Remember - no weapons!"
- **The bus's script** (machine m2, disassembled in lab `builds\nitro-polish-20261024\bus\fsm\P17.MSN.fsm`):
  - it drives path "speed" at BP[3] m/s;
  - every 3 s BP[3] += 1, and a ram sets it to 35;
  - above 45 the bus explodes, and it also explodes if shot, if airborne, or at the path end.
  - **Win:** `hpLesser(bus, 0, 65)`. Then success, and the bus `sit`s: that is the "stop".
- **No velocity test anywhere.** Braking or blocking cannot satisfy it; a 13 t bus is re-commanded every pass.
- **The condition in numbers.**
  - Health = 28 + 72 x the worst side ratio (min of armour and chassis), so one side must fall below ~51 %: ~540 of 1050
    armour.
  - At ~53 hp per 20 m/s ram (FRAME-BOUND row 7, n 3), that is about 10 hard rams on the same side.
  - Each ram must come within ~33 s of the last (the fuse), without lifting the bus.
- **Does our build change it?**
  - **The tick:** neutral. The script, the ram stamps and the damage all run per tick; timers are in sim seconds.
  - **`I76_FIX_HEALTH_PCT`:** no change here. Core components are damaged only by what gets through a side's armour and chassis
    (damage.md), and by then health is already under 65.
- **Verdict: technique.** Ram one flank repeatedly and hard, never shoot, don't launch it.

## 5. "Rename variant to save"

- **Reproduced on the console** (exp-nitro-polish, stock NITSHELL f804f50d). Route: MELEE > INSTANT MELEE > CONFIGURE CHASSIS,
  armour -1, DONE. A stock variant cannot be overwritten, so NITSHELL raises **"RENAME VARIANT TO SAVE" [OK]**, a `Modal_Ok`.
  - **Mouse.** The OS pointer was moved onto OK; the drawn pencil stayed on DONE. The modal loop presents once, before the
    loop (as Gold's, lab GARAGE-POPUP-STUCK.md), so dgVoodoo's pencil does not move. A click at OK's position closed it. So
    "can't reach it" is an invisible pointer, not a dead one.
  - **Enter: nothing.** The loop reads no key (1997 design).
- **Fix.** NITSHELL F7 (Enter / Space close Modal_Ok and Modal_ImageOk), M2 and K1-K4 (Y / N / Esc on yes-no prompts, Enter /
  Esc in the team picker and other modals), from `tools/patch-nitshell-f7.py` + `tools/patch-nitshell-modals.py`.
  - These were written and emulation-tested by the nitro-port lane on 10-21 (NITRO-PORT s.7.3 / s.8.2) but installed nowhere.
  - Rebuilt here from GOG's f804f50d: md5 **a32ffba6**, equal to the staged file.
- **Console with a32ffba6** (n 1, full flow):
  1. DONE > popup > **Enter closes it**;
  2. RENAME > Backspace, X, Enter: the variant reads "Army GX";
  3. DONE > "Wanna save the new variant?" > **Y**: back at the entry form with variant Army GX;
  4. ENTER AREA > 70 s driving: 0 faults.
- **Not fixed: the frozen pencil inside a popup.** It is the same on Gold, needs a present inside the loop, and is not done.
  Enter / Space / Y / N make it irrelevant for these popups.

## Files

- **i76-everywhere:**
  - `music-fix/soundmix.c` (new), plus strlkproxy.c hunks: include, apply calls, `sm_music_volume` in hook_auxSetVolume,
    `apply_sound_census` on Nitro;
  - music-fix/README.md rows;
  - this record.
- **lab:**
  - `tools\nitro-polish\` (np-run.ps1, pcon.ps1, edgecap.ps1, loud_files.py, lufs_cat.py, loud_music.py, nsdis.py);
  - builds `builds\nitro-polish-20261024\` (w1..w6, nitshell\, bus\, wt = this lane's worktree). w4\Strlkup.dll was overwritten
    with w5 for a queued run; see w4\NOTE.txt;
  - captures `captures\nitro-polish-20261024\` and `captures\nitro-owner-20261023\np-*`;
  - copy `exp-nitro-polish` (WHAT-THIS-IS.txt).
