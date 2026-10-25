# Interstate '76 HD sound pack: research and design (2026-10-10)

Scope: design and research only. The game was not run and no game folder or existing code was changed. Analysis
outputs live in `<lab>\captures\sound-hd-research\` (script, CSV, ranking, summary).
Legend: **VERIFIED** = an instruction, a file parse or a listed install, cited; **INFERRED** = my reading of those;
**PROPOSED** = not built; **unknown** = not established here.

Owner's ask: enhance the stock sounds into an HD pack that fills in the low range 1997 sound files lack but today's
systems (and bass transducers) can reproduce; iZotope "x11" is on the machine.

---------------------------------------------------------------------------------------------------
## 0. Summary

- All in-mission sound is **631 PCM files: 628 at 11,025 Hz, 3 at 22,050 Hz, every one 8-bit unsigned mono**
  (survey of the extracted archive + the loose `music.wav`; `stock-sound-survey.csv`). 494 are CB/dialogue lines,
  ~125 are effects (12 shell-UI chirps aside). The sandbox's `I76.ZFS` is byte-identical to the pristine one
  (md5 6dd57b16...), so the survey describes the lab copy too.
- The loader (`snd_LoadSample` 0x425130) hands the file's own `fmt ` chunk to `IDirectSound::CreateSoundBuffer` and
  copies the `data` chunk into a static buffer, so **16-bit and higher-rate replacements are accepted by the engine
  as written**, with two hard rules: 3D voices are created with `DSBCAPS_CTRL3D`, which DirectSound only allows for
  mono formats, and the **engine loops are pitched in absolute Hz** (8268.75 Hz at idle), so an engine loop must stay
  at 11,025 Hz until the P5 proxy patch exists. No memory cap was found (section 1.3).
- Deployment is **loose files in `ADDON\`**, which the VFS searches first; the 123 `.gpw` effects must be replaced by
  `.gpw` files (GAS0 header + RIFF), not `.wav`, because the loader prefers `<name>.gpw` wherever it exists.
- **Bass is a bit-depth and content problem, not a sample-rate problem**: 11,025 Hz already carries everything below
  5.5 kHz; the 8-bit floor (about -48 dBFS) and the authoring are what starve the low end. The survey shows which
  effects lack it: engine loops (median 11 % of energy below 120 Hz), engine starts (12 %), horns, tyres and the
  collision family (several below 6 %), while the big explosions already sit at 50-85 % (`low-end-ranking.md`).
- Recommendation (section 4): render **two outputs per sound**: a speaker mix with psychoacoustic (harmonic) bass
  plus a modest true sub, loudness-matched to stock; and a separate **LFE stem** (30-90 Hz) that is never baked into
  the game file and is played to the shakers by the haptics layer, keyed by the proxy's sound-event tap (P4 of
  `docs/records/SOUND-INTERPOSER-REVIEW.md`), which is not built yet.
- iZotope **RX 11 Audio Editor Advanced 11.2.0** is installed. It has a GUI Batch Processor (module-chain presets,
  WAV out) and **no CLI or scripting API**; it contributes cleanup (De-clip, De-click, Spectral De-noise), high-quality
  Resample and Spectral Recovery (HF re-synthesis), not bass generation. The bass pipeline is Python (numpy/scipy are
  installed); RX is an optional, manually triggered pre-pass.

---------------------------------------------------------------------------------------------------
## 1. Inventory and format facts

### 1.1 Where the sounds live (VERIFIED)

| where | what | source |
|---|---|---|
| `I76.ZFS` (55,535,506 B, 6,116 entries) | 507 `.wav` + 123 `.gpw` = 630 sound files, 30.0 MB (54 % of the archive) | `<re-archive>\data\FORMATS.md` table; extracted corpus `<re-archive>\recon-2026-09-04\recon\formats\zfs_out` |
| `music.wav` (loose, 634,572 B) | one 57.6 s 11,025 Hz 8-bit file beside the exe | `sandbox-gog\main\app\music.wav`; also in `<lab>\game` |
| `music\N.mp3` (16 files) | GOG soundtrack, MPEG-1 layer III 44.1 kHz 160 kbps (frame header `ff fb a0 04`); played by the music-fix proxy through `mpegvideo` | `<lab>\game\music`; `docs/MUSIC.md` |
| `DATABASE.MW2` items 0x48-0x52 | 11 shell (menu) WAVs, 8-bit mono 11,025 Hz (one at 22,050), read by i76shell.dll, not the exe | FORMATS.md section 11 |
| `ADDON\` | the override folder; pristine has no sounds in it, the sandbox's carries the owner's .vcf/.lvl/.ter/.map mods and no sounds | directory listings 2026-10-10 |

Lab copies: `<lab>\game` (sandbox; its `I76.ZFS` md5 = pristine) and the pristine read-only
`<re-archive>\sandbox-gog\main\app`. The daily driver (`<games>\Interstate76-2026-10-03`) is
out of scope for anything in this document (memory: never experiment on the daily driver).

### 1.2 Format of every file (VERIFIED by parse, `stock-sound-survey.csv`)

- 631 files parsed, 0 errors: `fmt` tag 1 (PCM) in all; 8-bit in all; 1 channel in all; 11,025 Hz in 628,
  22,050 Hz in 3 (`dcaltrop.gpw`, `tcaltrop.gpw`, `vskid.gpw`); `fmt` chunk 16 or 18 bytes; total 2,771.6 s.
- `.gpw` = `GAS0` + 7 x i32 (priority, max instances, play mode, volume %, random-pitch flag, frequency) + RIFF
  (FORMATS.md section 8; `data\fmt\other_formats.py` GPW struct). The frequency field is overwritten by the WAVE
  rate at load (`mov [ebp+0x48],edx` 0x425753), the other fields default when -1.
- One stem has both forms (`xmv1.wav` and `xmv1.gpw`); 122 effects exist only as `.gpw`; the 507 `.wav` are the CB
  lines, shell-UI chirps and a few effects.
- Level: 611 of 631 files peak above -1 dBFS (8-bit material was normalised to full scale), median |DC offset|
  0.0002 but up to 0.18 (`vskid.gpw` -0.07, `dcaltrop` -0.02): remove DC before any processing.
- Categories by stock naming (cross-checked with `subsystems/sound.md`, `engsnd.dat`, the ORDF table):

| category | n | examples | role |
|---|---|---|---|
| cb_voice | 494 | `01sgc08`, `gdsgc26`, `tmsgc04`, `posta05` | CB radio / dialogue, 2D at voice level |
| weapon_fire | 27 | `whmgun`, `wcvr`, `wrock`, `whowitz` | fire / mechanism, 3D on the shooter |
| vehicle_collision | 15 | `vvch2`, `vnvcs3`, `vexplode`, `vland` | impacts (`physics_CollideBodyPair`), death |
| explosion_impact | 13 | `xemt1/2`, `xcar`, `xbulc1`... | ORDF pairs with .xdf effects, detached 3D one-shots |
| engine_start | 12 | `esnp1-3`, `eshp1-3`, `estank` | ignition by engine health (`engsnd.dat`) |
| engine_loop | 9 | `einp1`, `eihp`, `eishp`, `eisv`, `eitank`, `eimarx`, `aheli`, `vballoon`, `vufo` | mode-1 loops, pitched by rpm |
| tyre_surface / surface_loop | 11 / 4 | `tskid1-4`, `tturn1-4`, `tflat`, `vcddirt/sand/grav/oil` | sustained (mode 2) player-only loops |
| horn_siren, dropper, handgun, nitro, damage, ambient, missile_lock, cockpit_ui, shell_ui | 7/6/3/1/1/2/3/10/12 | | |

### 1.3 How a sound is loaded and played (what a replacement must satisfy)

All addresses are in the pristine exe (md5 9a232dcc), read with `<re-archive>\tools\disasm.py 0x425130` on 2026-10-10
unless cited to a map document.

1. **Name resolution** (VERIFIED): `_splitpath`, append `.gpw` (string 0x4ed898), `0x470340(exists)`; if absent, the
   original name is used, so a plain `.wav` loads when no `.gpw` exists (`data\notes\terrain-text-sound.md` s.2).
   Consequence: for the 123 `.gpw` effects a loose `addon\name.wav` is **ignored** while the archive's `name.gpw`
   exists; replacements must be `.gpw` with a GAS0 header (copy the stock header; keep mode/priority/volume).
2. **ADDON first** (VERIFIED for the VFS, INFERRED for sounds): I76.ZIX's container table has slot 0 hard-wired to
   `addon` (`vfs_LoadZix` 0x4b23e0, FORMATS.md s.6); the texture pack proved loose `ADDON\` files override archive
   entries in-game (`docs/HD-TEXTURES-RESEARCH.md`, "proven in-game"), and the sandbox's ADDON .vcf mods are live
   (memory: sandbox carries user mods). A `.gpw`/`.wav` in `ADDON\` has not been tried; it goes through the same
   `0x470340`/`0x46ffc0` pair, so I expect it to work. **First live test = one file (section 6).**
3. **Header parse** (VERIFIED): if the first dword is `GAS0` the 7 ints are copied to the voice (+0x30..+0x48) and
   the RIFF starts at +0x1c. The RIFF walk (0x425573..0x42563d) requires `RIFF`/`WAVE`, finds `fmt ` (size must be
   >= 14, `cmp esi,0xe` 0x425609) and `data`, skips unknown chunks with odd-size padding. Both chunks must be present;
   write `fmt ` before `data` and nothing else, to stay on the path the stock files take.
4. **Buffer creation** (VERIFIED): DSBUFFERDESC on the stack: `dwSize` 0x14; `dwFlags` = **0xb2**
   (`DSBCAPS_STATIC|CTRL3D|CTRLFREQUENCY|CTRLVOLUME`) when the voice has an object and the manager's 3D flag
   (`mgr+8`) is set, else **0xe2** (`STATIC|CTRLFREQUENCY|CTRLPAN|CTRLVOLUME`) (0x4253e6 / 0x4253f2);
   `dwBufferBytes` = the `data` chunk size; `lpwfxFormat` = **a pointer to the file's own `fmt ` body**
   (0x4255e3, 0x425612, 0x425670 `call [ecx+0xc]` = CreateSoundBuffer). Then `Lock` (vtbl+0x2c), `rep movs` of the
   data, `Unlock` (vtbl+0x4c); the sample rate from `fmt+4` goes to voice+0x48 and as a float to +0x18; 3D voices
   `QueryInterface(IID_IDirectSound3DBuffer {279AFA86-4981-11CE-A521-0020AF0BE560} at 0x4bcf48)`.
   - So the engine imposes **no format of its own**: 16-bit, 22,050 or 44,100 Hz pass straight to DirectSound.
   - DirectSound refuses `DSBCAPS_CTRL3D` on a non-mono format, and CTRL3D cannot be combined with CTRLPAN
     ([CreateSoundBuffer](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/ee418035(v=vs.85)),
     [DSBUFFERDESC](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/ee416820(v=vs.85)),
     [3D sound overview](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/ee416765(v=vs.85))).
     **Every effect replacement stays mono.** CB lines (2D, CTRLPAN) could be stereo in principle; not a goal.
   - On a failed CreateSoundBuffer the error hook is a bare `ret` (0x42d5d0, terrain-text-sound.md): the sound is
     silently missing, nothing crashes. INFERRED from the `test eax / je 0x425909` paths.
5. **Memory** (VERIFIED, partial): the whole file is loaded by `0x46ffc0` and released (`0x46fd40`) after the copy;
   a running total of buffer bytes is kept at `0x5fcbf4` (added at 0x425743, zeroed at init 0x4213ee and shutdown
   0x421709, adjusted at 0x425958/0x425adf, read by 0x425ef0). **No comparison of it against a limit was found**
   in the loader or the manager functions I read; what 0x425ef0 does with it is unknown. Budget if every effect is
   re-rendered at 22,050 Hz 16-bit: about 4x the stock ~3.4 MB of effects, ~14 MB; at 44.1 kHz ~27 MB. CB lines
   (27 MB stock) are loaded per mission; leave them 8-bit or 16-bit at 11,025 Hz (2x) unless the voice pass is wanted.
6. **Playback rules that constrain the render** (VERIFIED in `subsystems/sound.md`):
   - Frequency is set to the WAVE rate at start (0x4220fa) and reset every frame (0x4215d8); the random-pitch field
     (always -1 in stock) rolls x0.80..1.16 once at start when enabled.
   - **Engine loops**: callback 0x424ca0 writes absolute Hz, 8268.75 at idle to 18,208 at the 7,000 rpm limit, and
     never reads the sample rate (SOUND-INTERPOSER-REVIEW s.3.2). A 22,050 Hz loop would play 2.7x slow. Until
     proxy patch P5 (`I76_FIX_ENGINE_PITCH_RATE`) lands, **engine loops are rendered at 11,025 Hz** (16-bit is fine:
     the rate, not the depth, is what the callback assumes). `grep` of `music-fix\strlkproxy.c` for 0x424ca0 /
     0x4220c0 / 0x425130 on 2026-10-10: none of P4, P5, P8 is implemented yet.
   - Volume is the GAS volume (default 100 %, `eimarx` 60) through the -4 dB-per-halving millibel table and the SFX
     slider (default 4 of 10, i.e. -5.3 dB for a 100 % effect); the exe does no per-sound mixing beyond that, so the
     **file's own loudness is the mix**. Loudness-matching to stock is mandatory (section 2.6).
   - 3D: min distance 10 m (100 m for the detached vexplode / ORDF impacts), max 400 m, rolloff 1, Doppler 0.8; the
     player's own voices sit on the listener in cockpit view. Loops are parked/unparked by priority and the 600 m cull.
   - Loop seams: mode 1/2 buffers play with `DSBPLAY_LOOPING`; a replacement loop must be seamless at its own length
     (the stock loops are 0.98-6.19 s).

---------------------------------------------------------------------------------------------------
## 2. Enhancement methods, ranked

The measurements behind this ranking: `low-end-ranking.md` (60 stems, per-category medians). Metric caveat: the
"-20 dB low cutoff" column reads 0-10 Hz on many noisy 8-bit files because their floor is within 20 dB of the peak
everywhere; use **E<120 Hz (fraction of PSD energy below 120 Hz)** as the primary measure and the cutoff only when
it is above ~20 Hz.

What the survey says needs low end most (category weight x missing-bass, transient bonus): the collision family
(`vshif1a`, `vnvcs5`, `vnvcs3`, `vvcre2`: 2-6 % below 120 Hz), the engine loops (`vufo` 0 %, `eisv` 4 %, `einp1`
5 %, `eihp` 10 %, `eishp` 11 %), the ignitions (`esnp2` 1 %, `esnp1` 6 %, `eshp1` 3 %), several weapons (`wmgr2`,
`wmiss`, `wrock` 0-4 %), horns (0 %) and tyres (0 %). Already bass-heavy and to be left mostly alone: `xemt2`
(84 %), `whcan` (89 %), `vexplode`/`xcar` (74 %), `whowitz`/`wtank` (63 %), `xmv2`, `xgas`, `wmflame`, `eimarx` (60 %).

| rank | method | what it does | where it applies | notes |
|---|---|---|---|---|
| 1 | **Transient-triggered sub layer** | detect onsets on the 5 ms envelope; for each, add a decaying sine sweep (e.g. 90 -> 35 Hz over 150-400 ms, level from onset energy), band-limited 30-90 Hz | one-shots: collisions, explosions, weapon fire, ignitions, landings, handgun | Robust on 8-bit noisy sources where pitch tracking fails; this is the standard "sub drop" layering in sound design. The same envelope becomes the LFE stem. |
| 2 | **Subharmonic synthesis (octave-down)** | track the fundamental of tonal material, synthesise f0/2 with the source's amplitude envelope, band-limit 30-90 Hz | engine loops, horns/siren, surface loops, flame loops | Period-match to the loop length so the seam stays clean. The rpm pitch law moves it with the engine (x0.75..1.65), which is correct behaviour. Pitch-tracked synthesis is what Waves Submarine and SSL SubGen do ([Submarine review](https://www.soundonsound.com/node/4930265), [SubGen](https://solidstatelogic.com/products/subgen)); the dbx 120A range 26-56 Hz from 54-110 Hz input is a useful reference ([dbx 120A](https://www.zzounds.com/pagearea--61/item--DBX120A)). |
| 3 | **Psychoacoustic bass (MaxxBass-style harmonics)** | from the 30-90 Hz band (original + synthesised) generate 2nd-4th harmonics with a waveshaper, band-pass 90-250 Hz, add at -6..-12 dB; keep the true sub modest in the speaker mix | every speaker-mix file | Small speakers and laptops hear the missing fundamental through its harmonics; MaxxBass splits at a crossover and synthesises harmonics below it ([Sound On Sound MaxxBass](https://www.soundonsound.com/node/4917403); generic chain on [diyAudio](https://www.diyaudio.com/community/goto/post?id=3684217)). Set the crossover near 75-90 % of the small speaker's low cutoff; overuse sounds boxy. |
| 4 | **Clean-up before synthesis** | remove DC; de-click 8-bit steps; spectral de-noise the -48 dB quantisation floor; de-clip the near-full-scale peaks (611 of 631 files) | all | RX 11: De-click, De-clip, Spectral De-noise (installed; `Presets\` listing). Python fallback: DC removal, a spectral gate, soft de-clip. Do this first; bass synthesis on a noisy floor pumps noise. |
| 5 | **Resampling / upsampling** | 11,025 -> 22,050 (or 44,100) with a windowed-sinc polyphase filter (`scipy.signal.resample_poly`) or RX Resample | effects except engine loops | Gains nothing in the bass; it only creates room above 5.5 kHz. Worth it only with method 6 or when 16-bit headroom and a cleaner floor are wanted at the same time. |
| 6 | **HF re-synthesis** | RX 11 Advanced **Spectral Recovery** regenerates content above the source's cutoff | effects at 22,050/44,100 Hz, optionally CB lines | Manual GUI pass (Batch Processor). Listen critically; it is tuned for speech. Not needed for the bass goal. |
| 7 | **Loudness matching** | match each replacement's K-weighted integrated loudness (BS.1770 gating) to the stock file within +/-0.5 LU after 8->16 conversion; soft-limit true peak to -0.3 dBFS | every file | Preserves the stock balance the exe cannot re-mix. `pyloudnorm` is not installed (pip it into the venv) or implement K-weighting in scipy. Report both. |

How iZotope fits an automated pipeline: **RX 11 Advanced 11.2.0** (uninstall key; `C:\Program Files\iZotope\RX 11
Audio Editor\win64\iZotope RX 11 Audio Editor.exe`) has a **GUI Batch Processor** that applies a saved Module Chain
preset to dropped files/folders, keeps folder structure, and writes WAV/AIFF/FLAC/OGG/MP3 (`HTML Help\en\
batch-processor.html`). It has **no command-line interface or scripting API**: the help's only "command line" mention
is Resolve's external-process type; web search found only UI-macro workarounds ([iZotope batch processing](https://www.izotope.com/en/products/rx/features/batch-processing),
[SoundFlow macro thread](https://forum.soundflow.org/-11462)). The 17 installed RX VST3 plug-ins
(`C:\Program Files\Common Files\VST3\iZotope\`) are repair modules (De-click, De-clip, De-hum, Spectral De-noise,
Voice De-noise, Dialogue Isolate, Connect, Monitor...), none is an EQ or bass tool, and no VST host other than
Audacity 3.7.6 is installed. So: RX = an optional **manual pre-pass** (one Batch Processor preset: De-click ->
De-clip -> Spectral De-noise -> Resample -> 24-bit WAV to `stage\clean\`), recorded in the manifest by md5;
everything deterministic (bass synthesis, loudness match, GAS re-wrap, report) is Python. Audacity could host the
RX VST3s under a macro (mod-script-pipe) but adds nothing RX's own batcher lacks. Ozone/Neutron: not installed.

Tooling present: Python 3.13.14 (Store build), numpy 2.4.4, scipy 1.17.1; pip 26.1.2. Missing: soundfile,
librosa, matplotlib, pyloudnorm, resampy, pydub; ffmpeg/sox are not on PATH (only Audacity's FFmpeg DLLs and an old
`ffmpeg.exe` under `C:\Program Files (x86)\FFmpeg for Audacity`). Plan: a venv under the captures folder with
`numpy scipy matplotlib pyloudnorm` (stdlib `wave` handles 8/16-bit PCM; soundfile optional).

---------------------------------------------------------------------------------------------------
## 3. Pipeline design (PROPOSED)

### 3.1 CLI: `soundhd.py` (python, lab-only)

```
soundhd.py analyze   --src <zfs_out|I76.ZFS> --out stage\analysis      # the survey (exists: analyze_stock_sounds.py)
soundhd.py recipe    --analysis stage\analysis --out recipes\            # per-category recipe JSON, per-sound overrides
soundhd.py render    --recipes recipes\ --clean stage\clean\ --out pack\  # speaker mix (.gpw/.wav) + LFE stems
soundhd.py report    --pack pack\ --stock <zfs_out> --out pack\report\    # A/B spectrograms, loudness, format checks
soundhd.py manifest  --pack pack\ --stock <zfs_out>                       # md5 of every original and replacement
soundhd.py check     --pack pack\                                         # loader-conformance gate (3.4)
soundhd.py install   --pack pack\ --game <lab game dir> [--dry-run]       # ADDON drop-in, gated roots
soundhd.py uninstall --game <lab game dir>
```

Stages read the extracted corpus (`recon\formats\zfs_out`) or extract from a given `I76.ZFS` with `<re-archive>\tools\
i76fmt\zfs.py`; they never write into a game folder except `install`.

### 3.2 Per-category recipe (defaults; every field overridable per sound)

| category | out rate / bits | clean | sub (method) | sub band / level | harmonics | LFE stem | loop |
|---|---|---|---|---|---|---|---|
| engine_loop | **11,025 / 16** (P5 constraint) | DC, de-noise | octave-down tracked (2), envelope-following | 30-90 Hz, -8 dB rel. to source RMS | yes, -10 dB | yes, continuous | period-matched, 20 ms equal-power seam crossfade |
| engine_start | 22,050 / 16 | DC, de-click, de-noise | transient layer (1) on the ignition hits + octave-down on the catch | 35-90 Hz, -6 dB | yes | yes | n/a |
| vehicle_collision, explosion_impact | 22,050 / 16 | DC, de-clip, de-noise | transient layer (1): sweep 90->35 Hz, 150-400 ms | 30-90 Hz, -4..-6 dB; skip stems with E<120 >= 0.5 | yes, -8 dB | yes | n/a |
| weapon_fire | 22,050 / 16 | DC, de-click | transient layer per shot (onset detector tuned to the fire rate; mode-1 loops like `whmgun` period-matched) | 40-90 Hz, -8 dB | yes | yes | loops period-matched |
| handgun, nitro, dropper, damage | 22,050 / 16 | DC, de-click | transient layer | 40-90 Hz, -8 dB | yes | yes | |
| tyre_surface, surface_loop | 22,050 / 16 | DC, de-noise | **none or very light** (skids live at 150-400 Hz; the shaker already synthesises road texture from telemetry) | 50-90 Hz, -14 dB | light | optional | period-matched |
| horn_siren | 22,050 / 16 | DC | octave-down tracked, light | 45-90 Hz, -12 dB | yes | no | `aps2` loop period-matched |
| cockpit_ui, shell_ui, missile_lock | 11,025 / 16 or untouched | DC, de-click | none | | no | no | |
| cb_voice | untouched in v1 (optional: 16-bit, de-noise, de-click; no bass) | | | | | no | |

Synthesis details: the transient detector is a 5 ms RMS envelope with a 2 dB/ms attack threshold and a 60 ms
refractory; each onset spawns `A * sin(phi(t)) * exp(-t/tau)`, `f(t)` sweeping 90 -> 35 Hz, `A` proportional to the
onset's envelope peak, then a 4th-order 30-90 Hz band-pass. The octave-down path uses an autocorrelation f0 tracker
(40-400 Hz search, 46 ms hop), rejects frames whose periodicity is weak, drives a sine at f0/2 with the source's
50 ms RMS envelope, band-passed 30-90 Hz. Harmonics: the 30-90 Hz sum through `tanh(k x)`, high-passed at 90 Hz,
low-passed at 250 Hz, mixed at the table level. The speaker mix = clean source + harmonics + sub (speaker level);
the LFE stem = sub only (full level), written as 16-bit mono at 16,000 Hz (the rate `ffb-lfe-live.ps1` streams at).

### 3.3 Pack layout

```
sound-hd\                       (lab staging, e.g. <lab>\staging\sound-hd\v0.1)
  manifest.json                 version, source archive md5, per sound: stock payload md5, replacement md5, LFE md5,
                                recipe id + parameters, rate/bits, stock vs new loudness (LU) and true peak, RX pass used (y/n, preset md5)
  addon\*.gpw, *.wav            speaker mix, installed into <game>\ADDON  (GAS0 header copied from the stock .gpw)
  lfe\<name>.wav                LFE stems, consumed by the haptics layer only, never installed into the game
  recipes\*.json                the recipe table above plus per-sound overrides
  report\index.html, *.png      stock vs replacement spectrograms (20-2000 Hz log axis), envelopes, loudness table
  tools\soundhd.py              the CLI
```

### 3.4 `check` gate (offline, deterministic; an implementation agent runs it before any install)

1. Every replacement parses as RIFF/WAVE with `fmt ` (16 bytes, tag 1) before `data`, no other chunks; `.gpw` files
   begin with `GAS0` and the stock values for priority / max instances / mode / volume / random-pitch (frequency -1).
2. Mono everywhere (CTRL3D rule); engine_loop stems at exactly 11,025 Hz until the manifest declares P5 present.
3. Loops: first and last 10 ms correlate above 0.9 after the seam crossfade; the octave-down sub completes an
   integer number of cycles over the loop length.
4. Loudness: |LU(new) - LU(stock)| <= 0.5 for the speaker mix; true peak <= -0.3 dBFS; E<120 Hz of the speaker mix
   within the recipe's target band (so bass is added, not dumped).
5. No file grows beyond 8x its stock byte size; total pack size reported against the budget in 1.3.
6. md5 of every original matches the manifest's source archive (the lab `I76.ZFS` is the pristine one; re-check).

### 3.5 Install / uninstall (PowerShell or the python CLI; lab only until gated)

- Allowed targets are an explicit list: `<lab>\game*` only. Any other path (the daily driver
  especially) is refused unless a `-Gated` switch is passed together with a path listed in a future
  `docs/records/READY-TO-TEST.md` entry. Default is `--dry-run`.
- Before writing, `install` refuses if a target name already exists in `ADDON\` with an md5 that is not in the
  manifest (the sandbox ADDON carries the owner's mods; nothing of theirs may be overwritten).
- Writes the files, then **reads each back and compares md5** (memory: verify the write landed), and records
  `ADDON\.sound-hd-installed.json` (pack version, file list, md5s).
- `uninstall` deletes only the files whose md5 matches that record, then the record. `I76.ZFS` is never touched;
  the ZFS repack route (`data\mod\zfspatch.py`, stored entries) is the fallback only if the ADDON route fails the
  live test, and it would be run on a copy.

---------------------------------------------------------------------------------------------------
## 4. Bass transducers: a separate LFE stem, routed by the haptics layer (RECOMMENDED)

Recommendation: **do not bake the full sub into the speaker files; ship an LFE stem per sound and play it to the
shakers from the haptics framework**, with the speaker mix carrying harmonics plus a modest sub. Reasons:

1. **Headroom.** 611 of 631 stock files already peak above -1 dBFS and the exe cannot re-mix (volume is the GAS
   value every frame); a 30-60 Hz layer at the level a shaker wants would force limiting or a quieter effect, which
   changes the stock balance. The stem has its own gain on the shaker interface.
2. **Separate destination exists.** `tools/ffb/LfeSynth.ps1` already opens a chosen `waveOut` device (the Audient EVO
   4 for the shakers) and `ffb-lfe-live.ps1` streams 16 kHz synthesis at ~64 ms queue while playing; the LFE bus is a
   first-class output in `FfbMixer.ps1` (`tools/ffb/README.md` "The force bus"). Sample-triggered stems slot in as
   one more source in `LfeCore.Step`.
3. **Keying.** The stem needs the event (which sound, player or AI, position, start/stop). That is exactly the
   proxy **event tap P4** of `docs/records/SOUND-INTERPOSER-REVIEW.md` s.4.1 (hook `sound_StartVoice` 0x4220c0 and
   `sound_StopVoice` 0x422d20, publish name/object/is_player/pos/Hz/vol/mode over UDP 17677). It is PROPOSED, not
   built (grep 2026-10-10). Distance and ownership let the shaker play the player's own hits at full weight and AI
   events attenuated, which a baked file cannot do. The old content-hash route (`sound-rumble/dsndrumble.c`) breaks
   as soon as a file is replaced and is slated for retirement (P9); do not build on it.
4. **Speakers without a sub still benefit** through the harmonics in the speaker mix; owners with a sub-equipped
   system get a modest real sub there plus the shaker stem, without the two fighting for the same headroom.

Caveat: two paths means two latencies. The in-game buffer starts when DirectSound plays; the stem starts when the
UDP event arrives and the shaker queue drains (~64 ms at the current settings). For impacts that is on the edge of
noticeable; measure it (log timestamps at the tap and at the shaker write) and, if needed, shorten the queue or
pre-delay nothing on the speaker side. Until P4 exists, an interim A/B can bake the sub into a few test files to
judge the sound itself (section 6, test 3).

---------------------------------------------------------------------------------------------------
## 5. Risks

| risk | why | mitigation |
|---|---|---|
| Clipping / pumping | near-full-scale sources + added sub; DirectSound sums many voices into the primary | harmonics over true sub in the speaker mix; soft limiter at -0.3 dBFS; loudness match; count overlapping voices in the ring during the live test |
| Engine loop plays slow | absolute-Hz pitch callback 0x424ca0 | engine loops stay 11,025 Hz until P5; `check` enforces it |
| Stereo or odd format silently fails | CTRL3D requires mono; a bare `ret` error hook hides the failure | mono only; `check` gate; live test reads voice+0x48 in the ring to prove the buffer exists |
| ADDON override of .gpw not proven | only textures/.vcf were proven loose; sounds inferred | first live test is a single marked `vexplode.gpw` (section 6) |
| `.wav` replacement shadowed by archive `.gpw` | loader prefers `.gpw` | replace by `.gpw` for the 123; manifest records the extension used |
| Memory / load time | 4-8x larger files; unknown reader at 0x425ef0 of the byte total | effects only in v1 (~14 MB at 22,050/16); measure mission load time stock vs pack |
| Loop seams, sub period mismatch | loops restart at the buffer end | period-matched synthesis + seam check |
| Mix balance drift | no per-sound mixer in the exe | loudness match to stock; P8 (`I76_SOUND_MIX`) if a deliberate re-balance is wanted later |
| Owner mods in ADDON | the sandbox ADDON is live modded data | install refuses to touch any file not in its manifest |
| Fingerprint consumers break | `gpw-fingerprints.py` / dsndrumble hash content | they are already marked for retirement; the event tap replaces them |
| Two-path latency (speaker vs shaker) | UDP + shaker queue | measure; keep the stem path under ~40 ms or accept for sustained effects only |

---------------------------------------------------------------------------------------------------
## 6. Test plan

### 6.1 Offline (an implementation agent, no console)

1. `analyze` reproduces `stock-sound-survey.csv` bit-for-bit from the lab `I76.ZFS` (md5 6dd57b16...).
2. `check` passes on the whole pack (section 3.4); the report lists loudness deltas and E<120 before/after.
3. Round-trip: parse each `.gpw` replacement with `data\fmt\other_formats.py` GPW handler; header fields equal stock.
4. Loop seam test and sub-cycle test on every mode-1/2 stem.
5. Synthetic pass: a 1 kHz tone file through the pipeline gains a 35-90 Hz sub only at onsets and nothing else.
6. Dry-run install against `<lab>\game` prints the exact file list; a real install there, read-back md5s,
   `uninstall` restores the ADDON listing to its prior state (diff of `Get-ChildItem` before/after).

### 6.2 Live, on the lab copy only (console agent, with `<lab>\tools\mute.ps1` as needed)

1. **Loader proof**: install one file, `vexplode.gpw`, rendered at 22,050 Hz 16-bit with an audible marker (a short
   440 Hz blip at its start). Destroy a car; the proxy's debug ring should show the voice with `+0x48 = 22050`; the
   blip is heard. Then the same file as 44,100 Hz, then one engine loop at 11,025/16 (`eimarx.gpw`) to confirm pitch.
2. **Format-failure probe**: a stereo `vexplode.gpw` must produce silence and no crash (confirms the mono rule and
   the silent error path); then uninstall.
3. **A/B listening**: `TEST-sound-A-stock.bat` vs `TEST-sound-B-hd.bat` (same preset, pack on/off) on t01/t04.

### 6.3 Owner listening list (short)

1. Ram a car and a building at speed: does the hit have weight without being louder than stock? Any pumping?
2. Fire the .30 cal, the 7.62 mm, a cannon, a rocket: do shots thump, and does the loop (`whmgun`) stay seamless?
3. Idle, then rev to the limiter: does the engine gain body at idle and stay clean at high rpm (no flutter, no seam)?
4. Ignition from cold (healthy and damaged engine): sub on the catch, not on the cranking noise?
5. Skids and gravel: unchanged or lighter, not boomy.
6. Shakers (when P4 exists): own hits heavy, AI hits lighter, nothing felt late enough to notice.
7. Overall: with eyes closed, is the mix balance (CB vs engine vs weapons) the same as stock?

---------------------------------------------------------------------------------------------------
## 7. Files and sources

- Analysis outputs: `<lab>\captures\sound-hd-research\analyze_stock_sounds.py`,
  `stock-sound-survey.csv` (631 rows), `low-end-ranking.md`, `summary.json`.
- Format and loader evidence: `<re-archive>\data\FORMATS.md` (s.6, s.8, s.11), `data\notes\terrain-text-sound.md`
  (s.2), `data\fmt\other_formats.py`, `data\mod\zfspatch.py`, `subsystems\sound.md`, `tools\disasm.py 0x425130`
  (pristine `ghidra\i76_ref.exe`), `docs\records\SOUND-INTERPOSER-REVIEW.md`,
  `docs\HD-TEXTURES-RESEARCH.md`, `docs\MUSIC.md`, `music-fix\strlkproxy.c`, `tools\ffb\LfeSynth.ps1`,
  `tools\ffb\ffb-lfe-live.ps1`, `tools\ffb\README.md`, `tools\gpw-envelopes.py`, `sound-rumble\dsndrumble.c`.
- Installed tools: registry uninstall keys (RX 11 Audio Editor Advanced 11.2.0, Audacity 3.7.6, FFmpeg for Audacity,
  Virtual Audio Cable 4.64, Audient and Behringer USB drivers); `C:\Program Files\iZotope\RX 11 Audio Editor\`
  (`Presets\`, `HTML Help\en\batch-processor.html`, `working-with-files.html`, `rx-overview.html`);
  `C:\Program Files\Common Files\VST3\iZotope\`; `C:\Program Files (x86)\iZotope\Meter Tap 3`.
- Web: DirectSound [CreateSoundBuffer](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/ee418035(v=vs.85)),
  [DSBUFFERDESC](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/ee416820(v=vs.85)),
  [3D sound](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/ee416765(v=vs.85));
  psychoacoustic bass [Sound On Sound MaxxBass 101](https://www.soundonsound.com/node/4917403),
  [diyAudio harmonic chain](https://www.diyaudio.com/community/goto/post?id=3684217),
  [Production Expert on small-speaker bass](https://www.production-expert.com/production-expert-1/how-to-make-sure-bass-is-heard-on-small-speaker-devices);
  subharmonic synthesis [SSL SubGen](https://solidstatelogic.com/products/subgen),
  [Waves LoAir](https://www.mixonline.com/?p=66774), [Waves Submarine review](https://www.soundonsound.com/node/4930265),
  [dbx 120A](https://www.zzounds.com/pagearea--61/item--DBX120A), [DAGA 2014 real-time subharmonic method](https://pub.dega-akustik.de/DAGA_2014/data/articles/000089.pdf);
  RX automation [iZotope batch processing](https://www.izotope.com/en/products/rx/features/batch-processing),
  [SoundFlow RX batch macro](https://forum.soundflow.org/-11462).

Unknowns to carry forward: whether `0x425ef0` enforces a buffer-byte limit; whether a loose `ADDON\*.gpw` is
honoured (expected yes, one live test settles it); the real speaker-vs-shaker latency; whether Spectral Recovery is
worth running on effects at all.
