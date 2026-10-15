# W95-18 baseline: the box-spec profile, measured (2026-10-14 / 15)

The full write-up is in lab `docs\W95-18-BASELINE-2026-10-14.md` (i76-uncap-lab), and the raw data is in
`captures\w95-18-20261014\`. Everything was measured on the lab twin; the daily driver was not touched.

**W95-18** is the unmodified game at **18.2 fps on a 55 ms GetTickCount tick**. It was the owner's box-spec guess (Windows 95
on a Pentium), first called R-BOX. The 55 ms tick is an **assumption**:
- the 86Box measurement found Windows 95's GetTickCount steps 1 ms (emu\results\RESULTS.md);
- the same rig measured P133 + Voodoo at ~26 fps, P166 + Voodoo at ~31 fps and P133 software at ~10 fps.

The owner has since defined stock as behaviour that does not change across those era configurations. Read the results with
that in mind.

## What was measured (n = 5 boots per condition unless noted; W95-18 vs stock20 / best-wide / TEST-next / parity candidate)

**Frames and physics steps.**
- W95-18 runs 2 physics steps of 27.5 ms per 55 ms frame (36.3 steps/s). Frame period 54.945 ms, sd at most 0.04 ms.
- One frame in about 1000 reads 0 ticks.
- stock20 runs 24 steps/s (46.9 ms / 2 × 31 ms). Our 120 fps builds run 24 steps/s of 41.7 ms.

**No difference within about 1 %:** gravity, acceleration (0-30 m/s in 5.6-5.7 s) and steady handling.

**Jumps.**
- **A harness error, caught by the owner watching.** The car ran the ramp's left edge: the placement used the object origin,
  not the ramp centre. Those jumps are excluded, and the jumps were re-run centred at player speed.
- **T06 ramp (38-44 m/s at the foot).** All conditions clear 30/30.

  | | W95-18 | stock20 | best-wide | TEST-next | parity |
  |---|---|---|---|---|---|
  | jump distance | 72 m | 81 m | 78 m | 80 m | 71 m |

- **T05 canyon (Mission 5).** A full-throttle run down from the hill top reaches the ramp at ~60 m/s. At that speed every
  condition clears 100 %.

  | | W95-18 | stock20 | best-wide | parity |
  |---|---|---|---|---|
  | jump distance | 222 m | 246 m | 243 m | 211 m |

- **best-wide's car was destroyed on that 60 m/s landing** in 5/5 boots, and TEST-next's in most; W95-18, stock20 and the parity
  candidate land intact.

**Body motion.** best-wide has a constant 12 /s roll wobble on flat road. W95-18 has none, and neither does the parity
candidate.

**Barricades (T05).**
- W95-18 knocks 8/10 and stock20 7.8; the 120 fps builds knock 6.6.
- The difference is two adjacent bars, and it comes with `I76_BREAKABLE_BOX`, not the frame rate.

**AI.**
- T04 racers lap at stock20's pace under W95-18. A coarse tick matched to the frame rate does not make the AI weave.
- t13's "4 hostile cars under W95-18" is the idle player's own car moving about 600 m into another group's range, not an AI
  change.
- The combat campaign was not run: the lead stopped it on the emulator results, and the owner took the console.

## Parity candidate (TEST-w95-18-parity.bat)
- **What it is:** TEST-next plus
  - `I76_FIXED_STEP=36.3636` (27.5 ms steps),
  - `I76_REF_FPS=18.2` (every frame-rate fix on an 18.2 fps reference),
  - `I76_AI_STOCK_CLOCK=55` with `I76_AI_STOCK_CLOCK_FPS=18.2`.
- **Measured:** it matches W95-18 on every physics row, including jump distances and canyon landings.
- **The method is reusable:** step = the reference's step, reference rate = its frame rate, AI clock = its tick. It can be
  pointed at any era profile.

## Installed in the lab twin (not the daily driver)
- `STRLKUP.DLL` 33211f11 (rollback `STRLKUP.DLL.f6d0c668-pre-w95-18`).
- `TEST-w95-18-reference.bat`: W95-18 itself, choppy on purpose.
- `TEST-w95-18-parity.bat`.
- Owner test 41.

## Proposed next step (owner's choice)
An **envelope test** at 1 ms tick profiles of about 10, 26 and 31 fps (P133 / P166 software, P133 + Voodoo, P166 + Voodoo).
Each key behaviour would be classified as:
- invariant: it becomes the target for the modern build;
- frame-rate dependent: it is an artefact.

Already known from W95-18: canyon and ramp clearing and the driving model are invariant; jump distance and body motion depend
on the step.
