# soundhd: the Interstate '76 HD sound pack pipeline

Design and evidence: [`docs/SOUND-HD-PACK.md`](../../docs/SOUND-HD-PACK.md). This folder is the implementation.
It builds a pack into `tools\soundhd\out\pack-v1\`. Nothing here installs into a game folder unless you run
`install --apply` against a lab copy yourself, and that command refuses every folder except
`C:\Users\james\i76-uncap-lab\game*`.

## Build

```powershell
python -m venv tools\soundhd\.venv
tools\soundhd\.venv\Scripts\pip install -r tools\soundhd\requirements.txt
tools\soundhd\.venv\Scripts\python tools\soundhd\soundhd.py build        # extract .. check, about 2 minutes
tools\soundhd\.venv\Scripts\python -m pytest tests\test_soundhd.py -q    # offline tests (19)
```

`build` runs these stages in order. Each one can also be run on its own (`soundhd.py <stage> --help`):

| stage | reads | writes |
|---|---|---|
| `extract` | the pristine read-only `C:\Users\james\i76-map\sandbox-gog\main\app\I76.ZFS` (md5 `6dd57b16...`) plus the loose `music.wav` beside it, read through the repo's ZFS reader `re/tools/i76fmt/zfs.py`, which is byte-identical to `i76-map\tools\i76fmt\zfs.py` and passes its round-trip gate | `out\work\stock\` (631 files), `out\work\stock-wav\` (the bare RIFF of each `.gpw`, used as RX input), `out\work\stock-manifest.json` (md5 of every file and of the archive) |
| `analyze` | `out\work\stock\` | `out\work\analysis\stock-sound-survey.csv`, `summary.json`. This is a port of `i76-uncap-lab\captures\sound-hd-research\analyze_stock_sounds.py`. `build` compares it with the research CSV, and all 631 rows match (see "GAS columns" below) |
| `recipe` | the survey and `overrides.toml` | `pack-v1\recipes\recipes.json`: one recipe per sound with its category defaults, overrides, loop flag and check rule |
| `render` | the recipes and the stock files (or RX pre-pass files given with `--clean`) | `pack-v1\addon\*.gpw`: the speaker mix, 16-bit mono, with the stock 28-byte GAS0 header kept verbatim. `render-info.json` holds the measurements |
| `lfe` | the render's per-sound sub band | `pack-v1\lfe\<stem>.wav` (16 kHz mono 16-bit) and `lfe-manifest.json` |
| `manifest` | all of the above | `pack-v1\manifest.json`: md5 of every original, replacement and LFE stem, plus recipe, loudness and RX flag |
| `report` | stock and pack | `pack-v1\report\index.html` and one PNG per sound (stock and HD spectrograms 20-2000 Hz on a shared dB scale, plus octave-band energies) |
| `check` | pack, stock, manifest | `pack-v1\check-results.json`. Exits 1 on any FAIL |
| `install` / `uninstall` | pack + `--game <lab copy>` | `<game>\ADDON\*.gpw` and `ADDON\.sound-hd-installed.json`. **The default is a dry run.** `--apply` writes |

Committed: `manifest.json`, `check-results.json`, `recipes\`, `lfe\lfe-manifest.json`, `report\index.html`.
Gitignored: the audio (`addon\`, `lfe\*.wav`, `out\work\`) and the PNGs. Game-derived audio is never committed.
`build` reproduces them, and two renders gave byte-identical files for all 123 (the TPDF dither is seeded by
sound name).

`render --small-speakers` gives a laptop or TV-speaker variant: harmonics +4 dB and true sub -6 dB. Build it into
its own folder with `--pack`.

## v1 result (2026-10-10)

- **123 replacements**, one per in-mission effect stem. All 123 are `.gpw`: the only `.wav` effect, `xmv1.wav`,
  is shadowed by `xmv1.gpw`, which the loader prefers. The pack is 9.5 MB against 2.6 MB of stock bytes.
- **85 LFE stems.**
- **507 untouched:** 494 CB/dialogue lines, 12 shell/map UI chirps and the loose `music.wav`.
- **check: 123 of 123 pass, 0 fail.** Every check passes on every sound it applies to: decodable,
  `fmt `-then-`data` only, fmt 16 bytes PCM, mono, 16-bit, rate rule, GPW header equal to stock, loudness within
  0.5 LU, true peak at most -0.3 dBTP, E20-120 inside the recipe band, size at most 8x, md5s, loop seam (32 loops),
  integer sub cycles (8), and LFE stem format (85).
- Independent cross-checks: all 123 `.gpw` parse with `i76-map\data\fmt\other_formats.py`'s `GPW` struct, and
  priority, max instances, play mode, volume, random-pitch and frequency all equal stock.

## What each recipe does

Every rendered sound goes through the same steps:

1. 8-bit to float.
2. Clean-up (per category):
   - **de-clip**: runs of at least 2 samples on the 8-bit rails are redrawn with a cubic spline, capped at
     1.2x the rail.
   - **DC**: mean removal, plus a 10 Hz zero-phase high-pass on one-shots.
   - **de-click**: an isolated 1-2 sample spike, measured against its own 65-sample neighbourhood, is
     interpolated. Content near Nyquist is left alone.
   - **de-noise**: a mild spectral gate (at most -12 dB) against the known 8-bit quantisation floor. It uses no
     learned profile, so a steady engine drone survives.
3. Resample. One-shots use polyphase resampling to 22,050 Hz. Loops use an FFT resample, which is exactly
   periodic.
4. Bass synthesis (below).
5. Harmonics: the 30-90 Hz band goes through `tanh` + x², then a 90-250 Hz band-pass, and is added at the
   recipe level.
6. Gain to the stock BS.1770 loudness, then a 4x-oversampled -0.3 dBTP look-ahead limiter. When the limiter alone
   cannot hold the loudness within 0.3 LU without more than 4 dB of reduction, a soft clipper (linear to
   -3.7 dBFS, tanh into -0.6 dBFS) goes before it. That happens on 54 of 123 sounds: dense near-square 8-bit
   material whose stock true peak is already +1 to +2 dBTP.
7. 16-bit with seeded TPDF dither.

Loops are processed circularly at every step (tiled, processed, middle period kept), so the seam is the stock
seam. `check` compares the jump across the wrap with an ordinary sample step.

| category (n) | rate | clean | bass | harmonics | LFE |
|---|---|---|---|---|---|
| engine_loop (9) | **11,025** (the P5 constraint: pitch callback 0x424ca0 writes absolute Hz) | DC, de-noise | pitch-tracked octave-down sub, period-matched: the phase completes an integer number of cycles over the loop, -8 dB | -10 dB | yes, loops |
| engine_start (12) | 22,050 | DC, de-click, de-noise | transient sub drop on the cranking hits + octave-down on voiced frames (the catch), -6 dB | -8 dB | yes |
| vehicle_collision (15), explosion_impact (13) | 22,050 | de-clip, DC, de-noise | transient sub drop 90 to 35 Hz, tau 0.3 s, -5 dB | -8 dB | yes |
| weapon_fire (27) | 22,050 | DC, de-click | sub thump per shot, 90 to 40 Hz, tau 0.12 s, -8 dB. Dense MG loops (whmgun) use envelope peaks as onsets, and the summed sub is ducked under the source envelope | -8 dB | yes |
| handgun, nitro, dropper, damage (11) | 22,050 | DC, de-click | as weapons | -10 dB | yes |
| tyre_surface, surface_loop (15) + vskid | 22,050 | DC, de-noise | none: skids live at 150-400 Hz, and the shaker already makes road texture from telemetry | no | no |
| horn_siren (7) | 22,050 | DC | light octave-down, -12 dB | -10 dB | no |
| ambient (2) | 22,050 | DC, de-noise | none | no | no |
| cockpit_ui (10), missile_lock (3) | stock (11,025) | DC, de-click | none (16-bit only) | no | no |
| cb_voice, shell_ui, music | **untouched in v1** | | | | |

**Already bass-heavy, sub skipped** (survey E<120 at least 0.5; cleaned and loudness-matched only; LFE stem from
their own bass): dmines1, eimarx, eitank, esshp2, vexplode, vtcoll, wchem, whades, whcan, whowitz, wlcan, wlmgun,
wmcan, wmflame, wmmgun, wtank, xbridge, xcar, xemt2, xgas, xms2, xmv2.

**Overrides** (`overrides.toml`): `vskid` sorts under vehicle_collision by its name, but it is a 3.3 s mode-1
skid loop, so it is treated as a tyre (no sub, no LFE).

**LFE stems** (`pack-v1\lfe\`) are for the haptics host. Each stem is the 25-90 Hz band of the speaker mix's
low end (the source's bass plus the synthesised sub), at the same gain as the speaker mix. The format is 16 kHz
mono 16-bit, with a sample-peak ceiling of -1 dBFS. Stems are not normalised one by one, so an explosion stays
stronger than a tick. To use one:

1. Take the sound name from a `SOUND_START` event (lowercase, with or without extension).
2. Look it up in `lfe-manifest.json` `by_alias`.
3. Play `sounds[stem].file`.
4. Loop it while the voice lives when `loop` is true.

The event tap (P4 in `docs/records/SOUND-INTERPOSER-REVIEW.md`) is not built yet.

## Deviations from the design, and why

- **GAS0 header: magic + 6 i32 (28 bytes), not 7 i32 after the magic.** This was verified against
  `other_formats.py`, the loader's +0x1c RIFF start, and all 123 stock files. The research survey unpacked 7
  ints after the magic, so its `gas_*` columns are shifted by one: its `gas_freq` is the bytes `RIFF`, and the
  "mode" column in `low-end-ranking.md` is really volume. `analyze` writes the corrected columns, and
  `--compare` checks that every other column matches exactly.
- **The bass gate measures E20-120, not E<120.** On drifting 8-bit files most of "E<120" is below 20 Hz: dfire's
  0.25 was nearly all DC wander. The check's band fraction also uses the same frequency resolution at 11,025
  and 22,050 Hz; Welch with a fixed 4096-point segment made the upsampling alone look like a 0.1 bass loss.
- **The seam test** is the wrap jump against the 99th-percentile sample step. The design's "first and last 10 ms
  correlate" compares two unrelated parts of the waveform.
- **The f0 clarity threshold is 0.35, not 0.45**, because einp1 and eitank sit at a median of 0.37-0.41.
- **Engine loops with f0 at 51-60 Hz** (eihp, einp1, eishp, aheli) get the sub on the fundamental (divisor 1),
  not an octave down. Half of 56 Hz is 28 Hz, outside the 30-90 Hz band, and in game the idle pitch is x0.75
  (about 21 Hz). eisv (160 Hz) and vufo (387 Hz) are true octave-downs (/2, /8). Set `sub.band = [20, 90]` in
  `overrides.toml` for a true octave-down on those four.

## iZotope RX 11 as an optional manual pre-pass

RX 11 Audio Editor Advanced 11.2.0 is installed. It has no command line or scripting API, so the pipeline never
drives it. The pre-pass is a manual, recorded step:

1. Run `soundhd.py extract`. It writes the bare RIFF of every `.gpw` to `tools\soundhd\out\work\stock-wav\`,
   because RX cannot open `.gpw`.
2. In RX 11, open the Batch Processor (Window > Batch Processor, Ctrl+B).
3. In **Input**, Add files: the `stock-wav\*.wav` of the sounds you want cleaned. The effect stems only; leave the
   CB lines alone.
4. Build the **Module Chain** in this order (`+` adds a module to the end, drag to reorder):
   1. **De-click**: Algorithm *Single band*, Sensitivity 3.0, Click widening 0 ms, Output clicks only *off*.
      This takes out the narrow digital clicks 8-bit material has.
   2. **De-clip**: Threshold linked, set just under the rails. Use *Suggest* on a loud file, or about -0.3 dB.
      Quality *High*, Makeup gain 0 dB, Post-limiter *off*.
   3. **Spectral De-noise**: *Adaptive mode on* (a batch cannot Learn a profile per file), Threshold 0 dB,
      Reduction 6 dB for noisy and tonal, Quality *C*, Artifact control at its default. Keep the reduction
      mild: engine and flame loops are noise-like content.
5. Save the chain as a Module Chain preset named `I76 soundhd pre-pass`. Then save the whole thing as a Batch
   Processor preset of the same name.
6. In **Output**: Choose folder `tools\soundhd\out\rx-clean\`, no name suffix (the files must keep their stem
   names), File format **WAVE, 32-bit float** (keeps de-clipped peaks above 0 dBFS) or 24-bit. Keep the
   sample rate and keep the files mono.
7. Process. Then render with the RX files as the source:
   `soundhd.py build --clean tools\soundhd\out\rx-clean`. Sounds with a file in that folder skip the Python
   de-clip, de-click and de-noise. `manifest.json` marks them `rx_pass: true` with the RX file's md5, and
   `rx_pass_count` gives the total. Run `check` as usual.

Spectral Recovery (HF re-synthesis) and RX Resample are not part of the pre-pass. The bass goal does not need
them, and the pipeline's resampler is already windowed-sinc. The v1 pack was built **without** the RX pass
(`rx_pass_count` 0).

## What to listen for (A/B in the lab, never on the daily driver)

The owner's test is in [`docs/OWNER-TEST-LIST.md`](../../docs/OWNER-TEST-LIST.md). Per sound, the report's
row says which strategy ran.

- **Collisions and explosions** (vnvcs3/5, vshif1a, vvcre2, vvcbb3, xfire1, xbuild): the hit should have weight
  (a 90 to 35 Hz drop) without being louder than stock. vshif1a had almost no energy below 120 Hz in stock (E20-120 0.02 to 0.30 now).
- **Engines**: idle body on eisv, vufo and einp1. Listen for flutter or a tick at the loop point, and listen at
  high rpm, where the sub moves up with the pitch law (x1.65).
- **Ignitions** (eshp1, esnp1/2, esmarx): the sub should sit on the catch, not on the cranking. esmarx and estank
  had no stable pitch (tracker fallback), so their octave layer is nearly silent.
- **Machine guns** (whmgun, wlmgun, wmmgun): whmgun gets a thump per shot. Check that the loop stays seamless and
  that the shots do not blur into a drone.
- **Soft-clipped sounds** (54, listed in the report's "peak stage" column): the stock files are 8-bit and peak
  above 0 dBTP, so matching their loudness under -0.3 dBTP needs some saturation. Listen for added crunch on
  horns (vhorn2/3 show 6-7 dB peak reduction), whmgun and the big impacts. The soft clipper also leaves faint
  content above 5.5 kHz (about -40 dBFS in the 5.5-11 kHz band on vnvcs5).
- **Unchanged by design**: skids, gravel, CB voices, menu sounds.
