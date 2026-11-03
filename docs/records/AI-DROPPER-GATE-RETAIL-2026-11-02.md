# AI dropper gate in retail 1.0: drops at every pursuer speed, no 27.8 m/s ceiling (2026-11-02)

Ported 2026-11-03 from the I26 emu-verify lane (lab capture `i26-gaps-20261101`, `emu2.md` row 1). No kit code
changes: the kit runs the original's gate. This record exists so that the static reading it overturns is not carried
into any kit note or spec.

**The question.** When does an AI car with a dropper (oil, mines) release it on a car chasing it? The static reading of
the spec (the private RE spec's `ai.md` rule 7, constant C-ai-03) says the gate predicts the pursuer with the target
predictor, which adds 0.09 s, and drops within 2.5 m. A pursuer straight behind at speed v is then 0.09 v off the
prediction, so above 2.5 / 0.09 = **27.8 m/s it would never be dropped on**.

## Rig

- Retail 1.0 `I76.EXE` (`6cc509ad`), 86Box at BelowNormal, emulated P166, Windows 95 RTM, 320x200 low detail, sim
  physics, no kit, guest time only.
- T05, the Oil Slick car `t05fp03` attacking and driving free. The player is held d m behind it on its velocity line at
  speed v by the lab driver (`I76DRV chase`, rewritten every 2 ms); a lateral offset for the radius test.
- Oil = projectile records with a 20 s life from the lab watcher (`I76WAT /proj`); per-frame player speed and the
  nearest AI's position from `I76MEM`.
- One 86Box boot per series, one game start per test, 9-12 in-game trials per test (scene reset in place); a warm
  Windows restart between tests. 2 series, 8 tests, 1 aborted boot. Frame time p50 36-39 ms (25-27 fps).

## Result

| pursuer speed v, m/s | 0 | 20 | 26 | 29 | 32 | 40 | 50 | 60 |
|---|---|---|---|---|---|---|---|---|
| drops / valid trials | 0 / 2 | 46 / 6 | 10 / 2 | 11 / 2 | **36 / 4** | **23 / 2** | **11 / 2** | **3 / 1** |

- n: 4 boots (2 per script), 33 valid trials. Drop counts per trial vary with the dropper's own speed (the interval
  stretch) and gear (trials with gear != 1 drop little), so the counts are not a rate; what matters is that every
  speed above the claimed ceiling dropped.
- The measured player speed equals the commanded one (p10-p90 within 0.2 m/s). The straight-line miss at t is 0.00-0.09 m; a
  prediction at t + 0.09 s would miss by 2.88 m at v 32 up to 5.40 m at v 60, outside the 2.5 m radius.
- **Radius:** a lateral offset of 2.3 m drops (2 trials), 2.8 m does not: 2.5 m, on the **plain straight-line
  prediction at t** (t = planar distance / speed), with no +0.09 s.
- v = 0: no drops (the t = 9.9 s rule holds).

**Verdict:** the original drops on a pursuer straight behind at 20-60 m/s. The 27.8 m/s ceiling does not exist. Same
code in R, G and N (static), so this is not a build difference ([BUILD-RULES.md](../engine/BUILD-RULES.md) s.2).

## Open

- **Static vs measured conflict.** The decompiled gate in both retail and Gold does call the predictor (+0.09 s), yet
  the measurement matches a plain line. Why is open; the chase hold's velocity / yaw-rate fields (what the predictor
  reads while the lab driver holds the pursuer) are the suspect.
- A turning pursuer (arc vs line) was not run.
- The dropper *cadence* (interval 1 - 0.05 v (1 - 1/rate) below 20 m/s; Nitro 1.2 + 0.18 v /s) is still static only
  (NITRO-VS-RETAIL-2026-10-20).
- The private spec's `ai.md` rule 7 and `constants.md` C-ai-03 still state the ceiling; their correction is open.
