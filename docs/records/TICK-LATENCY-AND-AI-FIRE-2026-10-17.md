STATUS: this lane was stopped unfinished on 2026-10-18 (00:35, blocked on a wait file that vanished); the physics rows and the AI-fire section were never written, and it is continued in TICK-FINISH-2026-10-18.md.

# Whole-sim tick: input latency and AI fire rate (2026-10-17, overnight lane)

Follow-up to [WHOLE-SIM-TICK-2026-10-17.md](WHOLE-SIM-TICK-2026-10-17.md) s.4 (open problems). Lab only; the daily
driver, the golden copy and `music-fix/Strlkup.dll` are untouched. Harness: lab `tools\whole-sim-tick\` (wst-run /
wst-queue; this lane's tables from `tl_analyse.py` and `tl_draw.py`), lab copy `game-wst` (headless twin, i76.exe
6319abf7, null renderers, 120 fps display cap), every boot on a private desktop, audio muted, console lock per hold.
Side builds `i76-uncap-lab\builds\tick-latency-20261017\Strlkup-lat1/2/3.dll` (sources from i76-everywhere git, not the
working tree; `make.ps1`), md5 in every boot's env record. Captures: lab `captures\whole-sim-tick-20261017`, tags
`L<n>` (latency / physics) and `F<n>` (combat); queues `queue-ticklat\*.txt`.

ANSWERS

## 1. Input latency

### 1.1 Why "sample every frame, apply at the next tick" cannot help (static, AiO 6319abf7)

- **Keyboard.** The main window procedure (0x4048ee) passes every key message to `input_KeyboardHandleMessage`
  0x44e920, which WinMain's per-frame PeekMessage / DispatchMessage loop (0x403f3a..0x4040b7) reaches on EVERY display
  frame, tick or not. `input_KeyboardUpdateKeyState` 0x44eab0 sets a key's down bit (0x6092d0[16]) at once and, on
  release, only marks it released (0x6092e0); `input_KeyboardPoll` 0x44e670 (driver vtable 0x4f5208 +0x14, called from
  `input_UpdateControls`) reports the down bits and only then clears the released ones. A tap shorter than a tick is
  therefore still seen for one tick. Typed (command) keys queue in a 64-entry ring (0x608e60, read one per
  `input_UpdateControls` by `input_KeyboardReadKey` 0x44e700).
- **Analog sinks** (keys or axes -> steer / throttle values) are evaluated inside `input_UpdateControls` when it runs;
  the key-driven ramps read `simclock_GetDt` (`input_UpdateKeyAnalogSink` 0x44d780 -> 0x49c8b0), so running
  `input_UpdateControls` every display frame would change the ramp rate (and clear the one-frame discrete pulses
  0x4f2864.. on frames the sim never sees).
- So the tick already applies the latest state, and a per-frame sample applied at the next tick would measure the
  same as the plain tick: the latency is the WAIT for the tick (uniform 0..T), not stale input. Not built.

### 1.2 What was built: an early tick on input (`I76_SIM_TICK_INPUT=1`, music-fix/simtick.c, off by default)

- Each non-tick display frame compares the keyboard driver's down bits with the snapshot taken right after the last
  tick's `input_UpdateControls`, and checks for a pending release (no game code runs for this). A change runs the tick
  NOW, borrowed from the accumulator: acc goes negative, at most one tick is outstanding (a second change waits until
  acc >= 0), so every tick is still exactly T of simulation and the tick grid and long-run rate are unchanged.
- Lab hook: the side build's drive block reports a new harness key sequence through `g_st_input_peek_fn` (the harness
  drives by shared memory, not keyboard messages). DirectInput devices (wheel, pad) are not watched.
- Drawing (second form, i76-everywhere 28a59f6): on the early frame each moving object's "would-be-drawn" pose D is
  kept, and until the next regular tick it is drawn from D to the new tick's pose with beta = (acc - acc0) / (T - acc0)
  (acc0 = the accumulator just after the borrow). The segment is (2 - a) T long and covers (1 - a) of the old tick's
  motion plus the new one, so steady motion keeps its drawn speed and the pose is continuous. The first form
  (backward extrapolation, alpha down to -1, 5e3fdba) kinked the drawn heading on the early frame; see 1.4.
- Instrument: `I76_SIM_TICK_DRAWLOG=<path>` logs the player's drawn pose per display frame (9f0460b).

### 1.3 Latency (mission T06, 40 steer-key toggles per boot at random phases, the proxy's latency probe; lat1 / lat3)

Per boot (A/A = an independent second boot set of the same condition, interleaved):

| condition | boots | key -> first sim step ms, median per boot | pooled median, p90, max | key -> first changed drawn frame, pooled median, p90, max | early ticks per boot (of 40 presses) |
|---|---|---|---|---|---|
| tick33 (+aa) | 2 + 2 | 17.9, 13.9 / 18.3, 15.9 | 16.4, 31.6, 36.0 | 16.6, 31.9, 36.4 | 0 |
| **tick33 + input** (+aa) | 2 + 2 | 3.6, 3.4 / 5.0, 4.8 | **4.1, 7.9, 8.8** | **4.2, 8.1, 9.1** | 27-33 |
| tick66 (+aa) | 2 + 2 | 25.3, 34.5 / 35.1, 32.1 | 32.8, 58.7, 66.7 | 33.1, 59.0, 66.9 | 0 |
| **tick66 + input** (+aa) | 2 + 2 | 4.6, 5.2 / 4.2, 3.6 | **4.3, 8.0, 9.0** | **4.6, 8.3, 9.3** | 34-37 |
| step33 (+aa), reference | 1 + 1 | 5.9 / 6.6 | 5.9, 15.2, 16.7 | 6.0, 15.3, 16.8 | - |
| tick33 + input, drawing form 2 (lat3) | 2 | 3.9, 5.2 | 4.8, 7.9, 8.3 | 5.0, 8.1, 8.4 | 26, 32 |
| tick66 + input, drawing form 2 (lat3) | 2 | 5.2, 4.4 | 4.8, 7.7, 8.9 | 5.1, 7.9, 9.2 | 35, 34 |

- The early tick takes the latency from "wait for the tick" (uniform 0..T: medians 14-18 ms at 33.3 ms, 25-35 ms at
  66.7 ms; A/A spread of the boot medians up to 10 ms) to "wait for the next display frame" (max 9 ms at the 120 fps
  cap, medians 3.4-5.2 ms in all 8 boots of both ticks), i.e. **at or below the per-stepper scheme's 6-7 ms**. The A/A
  spread is far smaller than the effect (no early-tick boot median above 5.2 ms, no plain-tick boot median below 13.9).
- Presses that did not fire an early tick (2-14 of 40) are those that landed on a frame that ran a regular tick anyway,
  or, at most 6 per boot, while a borrowed tick was still outstanding (`early_blocked`): those wait as before.
- The first changed drawn frame follows the first sim step within 0.3 ms in every arm (no added draw lag).
- **Correctness, every early-tick boot (14 boots, lat1/lat2/lat3):** ticks per wall second 15.018-15.032 at 66.7 ms and
  29.956-30.013 at 33.3 ms (plain tick 15.022-15.028 / 30.001-30.002), 0 leaks in 4 565-9 568 checks per boot, 0
  outside writes, 30 / 30 hooks read back live, no keyboard-path false trigger (`early_kb` 0 in every boot: the
  harness presses no keys, so every early tick came from its key sequence).
- The latency probe measures the first sim step and the first changed drawn pose, not photons.

### 1.4 Does the early tick show? Drawn-pose smoothness (`tl_draw.py`, the player's drawn pose per display frame)

Heading second difference per display frame (deg; a kink is a sudden change of the drawn turn rate):

| condition (DLL) | boots | frames next to an early tick: median, p99, max | all other frames: median, p99, max |
|---|---|---|---|
| tick66 (lat2 / lat3) | 1 + 1 | - | 0.000, 0.047 / 0.034, 1.28 / 2.17 |
| tick66 + input, form 1 (lat2: backward extrapolation) | 1 (76 frames) | **0.416, 1.253, 1.490** | 0.000, 0.019, 1.34 |
| tick66 + input, form 2 (lat3: blend from the would-be pose) | 2 (70 + 68) | **0.003 / 0.015, 0.188 / 0.186, 0.212 / 0.204** | 0.000, 0.026 / 0.022, 1.14 / 2.09 |
| tick33 (lat2 / lat3) | 1 + 1 | - | 0.000, 0.040 / 0.024, 0.71 / 0.69 |
| tick33 + input, form 1 (lat2) | 1 (68 frames) | 0.130, 0.493, 0.510 | 0.000, 0.018, 0.97 |
| tick33 + input, form 2 (lat3) | 2 (52 + 63) | 0.024 / 0.012, 0.148 / 0.182, 0.195 / 0.182 | 0.000, 0.021 / 0.024, 0.73 / 0.63 |

- Form 1 put a visible heading twitch (median 0.4 deg, up to 1.5 deg in one frame at 66.7 ms) on every early tick:
  the backward extrapolation uses the NEW tick's turn rate for the part of the old tick not yet shown. Form 2 (now in
  the source) brings it to about the size of ordinary frames' p99 (0.19 deg max vs 0.02-0.05 deg p99 elsewhere); the
  largest single-frame kinks in every condition (0.6-2.2 deg) are elsewhere (harness placements, landings).
- Speed judder (frame speed off its neighbours' mean by > 25 %) is 0.01-0.20 % of frames in every boot but one (a
  form-1 tick33 boot, 1.1 %: equal pose steps over unequal stamp intervals, i.e. the log's time stamp is taken at
  render time; none on early frames) and 0 % on early frames; backward drawn steps: 0 in every boot.
- What is still drawn late: a moving object's drawn pose lags the newest tick by up to one tick in every tick arm (the
  interpolation); the early tick removes the WAIT, not that lag. Its blend starts at once, so the response begins to
  show on the next frame and is fully shown when the next regular tick arrives.

PHYSICS_ROWS
