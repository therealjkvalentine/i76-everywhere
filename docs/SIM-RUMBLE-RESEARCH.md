# Sim-Feel Rumble Design Research — for the I76 two-motor Xbox-pad mixer

Research date: 2026-07-19. Goal: translate sim-telemetry-to-tactile design (the
SimHub "ShakeIt" gold standard) into a concrete rumble-mixer spec for Interstate
'76, driving an Xbox pad's **two ERM motors** off the game's real physics force
stream. Priority #1 is **driving feel**: road connection, weight, traction.

Hardware reality we are designing for:
- **Left motor = low-frequency / heavy** (big eccentric mass). Reads as *weight
  and force in the gut/palm*. Use for body, load, low rumble, heavy impacts.
- **Right motor = high-frequency / buzz** (small mass). Reads as *texture and
  edge*. Use for tire scrub, road grain, squeal, light ticks.
- ERM physics constraints (see Sources: makeabilitylab): frequency and amplitude
  are **coupled** — you only command *one* value per motor (amplitude), and the
  motor picks its own frequency. Spin-up latency is **~20–30 ms**; spin-down is
  similar. There is a **start dead-zone** (~2.3 V of a 3.0 V motor → roughly the
  bottom ~25–35% of the 0–65535 XInput range does little or nothing). Amplitude
  grows ~quadratically with rotor speed (F = m·r·ω²) but *feels* roughly linear.
  Typical natural frequencies land ~150–235 Hz — you cannot make a pad "hum" at
  30 Hz like a bass shaker; you can only modulate how hard each buzz hits.

Consequence for us: unlike SimHub bass shakers (which pick a literal Hz per
effect), our only knobs are **per-motor amplitude over time**. So every ShakeIt
"frequency" decision becomes, for us, a **motor choice (left vs right) + an
amplitude envelope**. We port the *design intent* (what signal, how curved, how
gated, how it decays), not the literal Hz.

---

## Part A — How ShakeIt actually builds an effect (the mechanics to copy)

SimHub ShakeIt is the reference implementation for turning car telemetry into
tactile output. Its per-effect processing chain is the thing worth cloning
(Sources: SimHub wiki "ShakeIt V3 Effects configuration"):

**Signal path per effect:** `telemetry input → Input Gain → Response filters
(Gamma, Threshold, Min Force) → effect level (0–100%) → output mapping`.

The four **response filters**, in order — this is the whole toolkit:
1. **Input Gain** — amplify/reduce the raw telemetry before anything else. This
   is *the* clip/sensitivity control. Field-proven lesson (Sources: SimHub forum
   "Wheel Slip settings"): wheel-slip that fired during *every gentle corner* was
   fixed by **lowering Input Gain to ~10** so the signal only reaches meaningful
   levels during real slip. Default 100 clips constantly and communicates nothing.
2. **Threshold** — mute the effect entirely below a set level (dead-band). Kills
   idle chatter so transients still "read." (Slip example used Threshold ~15.)
3. **Minimum Force** — when the signal *is* above threshold, boost the floor so
   the effect is immediately *felt* rather than fading in from zero. Critical on
   ERM pads because of the start dead-zone. (Slip example used Min Force ~20.)
4. **Gamma factor** — curve shape: sensitivity to small values. Gamma > 1 makes
   small inputs quieter and only big inputs loud (expands dynamic range → keeps a
   floor calm, makes peaks pop); gamma < 1 lifts small inputs (compresses). This
   is exactly the linear-vs-exponential curve question — ShakeIt exposes it as
   gamma.

**Gains are multiplicative and layered:**
`out = effect_gain × per-channel_gain × channel_gain × general_gain`
(Sources: SimHub wiki). Port this as a master gain × effect gain so the user has
one global "calm it all down" knob plus per-effect trims.

**Envelope / sustain tools:**
- **Gain modulation** — "hold" a strong effect longer than the telemetry spike.
  Telemetry reports a big impact (e.g. a jump landing) as a *very short* spike;
  gain modulation stretches it so you actually feel it. This is our attack-hold-
  decay envelope for transients (Sources: SimHub wiki).
- **White-noise / frequency randomization** — jitter the value so a sustained
  effect (RPM, road) feels organic and quieter rather than a pure droning tone.
  On a pad, port this as a small per-frame amplitude dither on continuous effects.

**Bass-shaker frequency mapping (for intent, not literal use):** ShakeIt maps
effect level to a **base frequency** (at low level) up to a **high frequency**
(at 100%). Notable inversion for tires (Sources: blekenbleu SG.htm): **tire
haptic frequency should *decrease* as slip/grip rises**, because the strongest
puck sensation lives at low frequency (30–60 Hz), while 150+ Hz reads as audible
squeal onset. For our pad this becomes: **rising slip → shift energy from the
right (buzz) motor toward the left (heavy) motor** as the tire goes from
fine-grain scrub to a heavy, low, letting-go slide.

**Golden rules from every guide (Sources: SimHub wiki, SimXPro, Reiza forum):**
- **Max ~3 continuous effects per motor** (punctual/one-shot effects like gear
  shift don't count). More than that = mush.
- **"Less is more" / signal over noise.** "When your rig is buzzing constantly,
  you don't feel ABS — you feel annoyance." A constant strong floor destroys the
  ability of transients to read. This is the single most important principle.
- **Tune one effect at a time** (two-lap method: lap 1 notice what you want, lap
  2 change exactly one parameter).

---

## Part B — PRIORITIZED EFFECT CATALOG (mixer spec)

Ordered by importance to *driving feel* on a gamepad. Each effect:
`{input signal · motor · intensity curve · envelope/timing · threshold · feel}`.
"L" = left/low/heavy motor, "R" = right/high/buzz motor. Amplitudes described as
fractions of usable range (remember: bottom ~30% is dead — scale into ~0.30–1.0).

### TIER 1 — the core "connected car" set (build these first; ~80% of the feel)

**1. Wheel slip / traction loss — THE money effect**
- Input: per-wheel slip ratio, ideally slip×tire-load, cross-checked against
  lateral+longitudinal accel. If I76 exposes a grip/slip scalar, use slip/grip
  *ratio* — "tire slip/grip ratio is more useful feedback than slip alone"
  (Sources: blekenbleu SG.htm).
- Motor: **split by severity.** Light scrub → **R** (fine buzz). As slip grows,
  **crossfade energy R→L** so a full slide is a heavy low churn. Rear-vs-front:
  if wheel data is separable, rear slip (oversteer) → **L bias** (feel the back
  step out heavy), front slip (understeer/push) → **R bias** (lighter, higher,
  "washing"). If not separable, use one combined slide on R with L crossfade.
- Curve: **gamma ~2** (expander) so gentle cornering stays silent and only real
  slip ramps up hard. Low **Input Gain (~10, not 100)** to prevent clipping in
  every corner.
- Envelope: near-instant attack, short decay (~50–100 ms) so it tracks the slide
  live. No long hold — slip is a *continuous* state, not a one-shot.
- Threshold: **~15%** dead-band + **Min Force ~20%** floor so onset is felt
  immediately, not faded from zero.
- Feel: good = silent until the tire actually lets go, then a clear rising
  churn that tells you *how much* you're over the limit and lets you catch it.
  Muddy = fires in every corner (Input Gain too high, threshold too low) → you
  learn to ignore it and lose the one cue that matters most.

**2. Wheel lock under braking**
- Input: wheel angular speed near-zero while road speed high (locked), or the
  sim's lock/ABS flag; combine with brake pressure.
- Motor: **L** primary (heavy grinding thud of a sliding locked tire) with a
  little **R** grain on top.
- Curve: gamma ~1.5; scales with brake pressure × amount of lock.
- Envelope: instant attack, sustains while locked, quick release (~50 ms) the
  instant the wheel spins up again.
- Threshold: only above meaningful brake pressure + real lock; must not trigger
  on normal deceleration.
- Feel: this is your ABS-substitute for a '70s muscle car — a hard, alarming low
  grind that says "you've locked, ease off." Keep it clearly distinct from slip
  (lock = lower/heavier/steadier; slip = churning and variable).

**3. Road surface / texture rumble (the "connection" floor)**
- Input: vertical/heave suspension deflection velocity, or a speed×surface-
  roughness proxy. In ShakeIt this is "Road Vibration / Road Texture."
- Motor: **R** at low amplitude (fine grain = high-freq buzz), scaling with speed.
- Curve: roughly linear with speed but **capped low** — this is a *floor*, not an
  event. Apply white-noise dither so it feels like grain, not a tone.
- Envelope: continuous, no envelope; just track speed/surface.
- Threshold: off below a crawl (~walking pace) so parked/idle is dead silent.
- Feel: good = a subtle, ever-present sense that the tires are on tarmac and how
  fast you're going, without ever masking Tier-1 events. Muddy = too strong →
  it's the "massage chair" floor that swallows slip and lock. **Keep this quiet.**

**4. Impacts / collisions (weapons, walls, rams, jump landings)**
- Input: sudden spike in acceleration/force magnitude (|Δaccel| per frame) — cue
  the **onset/jerk**, not steady contact (see Part C, washout).
- Motor: **both**, L-dominant. Big hit = hard L slam + R crack for the sharp edge.
  Scale L:R by hit character (soft heavy ram = more L; sharp metallic hit/bullet
  = more R).
- Curve: near-1:1 with impact magnitude but **saturate/clip** the top so a huge
  hit and a catastrophic hit both peg (you can't feel "more than max" anyway).
- Envelope: **this is where Gain Modulation matters** — telemetry impact is a
  1-frame spike; stretch it to an audible **attack ~0 ms, hold ~30–60 ms, decay
  ~150–250 ms** so it lands as a *thump* not a click. Bigger hit → longer decay.
- Threshold: above a real-collision magnitude so normal bumps don't read as hits.
- Feel: good = punchy, distinct, weighty, over quickly (so the next one reads).
  Muddy = decay too long → hits smear together in a firefight into one buzz.

### TIER 2 — strong support (add once Tier 1 feels right)

**5. G-force: longitudinal (accel / braking weight transfer)**
- Input: surge accel (+ = throttle squat, − = brake dive).
- Motor: **L**, gentle. A soft low swell under hard acceleration and under hard
  braking — the car's *mass* loading and unloading.
- Curve: gamma ~2 so only *hard* accel/brake registers; cruising is silent.
- Envelope: slow attack/decay (~150–300 ms) — this is weight, it should feel
  smooth and heavy, never buzzy.
- Threshold: mid — only meaningful longitudinal G.
- Feel: adds "this car is heavy." Keep it a whisper under Tier 1.

**6. G-force: lateral (cornering load)**
- Input: sway/lateral accel magnitude.
- Motor: **L**, very gentle, rising with corner load.
- Curve: gamma ~2; capped low.
- Envelope: smooth, tracks the corner.
- Threshold: mid-high, so only committed cornering.
- Feel: a subtle build of load as you lean on the tires — and crucially it should
  *give way to* the slip effect (#1) as you pass the limit. Motion-sim doctrine:
  you feel the load build (seat/L) then the wheel goes light as grip breaks
  (Sources: Cruden, MOZA). Port that handoff: lateral-G swell on L, then slip
  churn takes over as grip is lost.

**7. Engine RPM vibration (the idle/rev floor)**
- Input: engine RPM (and/or a throttle term).
- Motor: **L** at *very low* amplitude, pulsing subtly with RPM; optionally a
  faint R at high RPM.
- Curve: low at idle, rising gently with RPM; white-noise dither so it's organic.
  Keep the ceiling low.
- Envelope: continuous.
- Threshold: present at idle (a car is alive at idle) but **barely**.
- Feel: EVERY guide says keep engine vibration **very low or off** — "easy to
  overwhelm everything" (Sources: SimXPro). It is a *floor/ambience*, the quietest
  thing in the mix. Its job is to make the car feel alive, not to be noticed.

**8. Wheelspin (throttle-induced, launch/burnout)**
- Input: drive-wheel slip specifically under positive throttle (differentiate
  from braking lock and cornering slip).
- Motor: **R** buzz rising to **L** churn as it escalates (same R→L crossfade as
  slip, but throttle-gated).
- Curve: gamma ~1.5, scales with throttle × slip.
- Envelope: instant, tracks live, quick release.
- Threshold: only under throttle + real spin.
- Feel: the back-tires-lighting-up cue on a launch. Distinct from cornering slip
  by being straight-line + throttle-gated.

### TIER 3 — punctual / flavor (cheap to add, one-shot, don't count toward the 3-per-motor budget)

**9. Gear shift (one-shot tick)**
- Input: gear-change event.
- Motor: **R** (small snappy tick), optional tiny L for a "clunk" on a heavy box.
- Curve: fixed magnitude per shift.
- Envelope: single pulse, **~40–80 ms**, done.
- Threshold: event-driven.
- Feel: a crisp confirmation. Optional per SimXPro. Keep it short or it muddies.

**10. Kerb / bump strikes (discrete road impacts)**
- Input: sharp vertical suspension spike on one side (distinct from continuous
  road texture #3).
- Motor: **L** thud + **R** edge, brief.
- Curve: scales with strike severity, saturates.
- Envelope: short attack, **~80–150 ms** decay.
- Threshold: only real strikes, above the texture floor.
- Feel: "you clipped something." SimXPro rates kerbs a high-value early effect,
  at **low intensity**.

**11. Suspension bottom-out / big landing**
- Input: heave/vertical accel spike beyond normal travel (jump landing, hard
  compression).
- Motor: **L** heavy, with Gain Modulation hold so the short telemetry spike is
  felt as a real *slam*.
- Envelope: attack ~0, hold ~40 ms, decay ~200 ms.
- Threshold: high — only genuine bottom-outs.
- Feel: the satisfying weight of landing a jump. This is the textbook Gain-
  Modulation use case (Sources: SimHub wiki).

*(Not recommended for the pad: a dedicated "wind/speed" continuous effect and
"ABS pulse." I76 has no ABS. Wind/speed overlaps road texture #3 — fold speed
into that floor instead of adding a fourth continuous effect and blowing the
3-per-motor budget.)*

---

## Part C — Motion-cueing / FFB principles that transfer

From motion-platform and FFB literature (Sources: Telban/washout research,
Cruden "Acceleration is not enough," MOZA motion blog, nesdev/gamedev threads):

- **Washout / high-pass the sustained component.** A motion platform can't hold a
  steady 1 G, so it *cues the onset* then washes the signal out below perceptual
  threshold. **Direct port:** don't render steady-state force as steady rumble —
  it just becomes fatiguing mush. Rumble the **change**. For continuous states
  (load, road) keep a low floor; for events, cue the **onset/jerk (dAccel/dt)**
  and let it decay.
- **Cue the change, not the constant, for impacts.** The informative, felt part
  of a hit is the leading edge (jerk). Trigger transients on the derivative of
  force, not its level. A car pinned against a wall shouldn't buzz forever.
- **Saturation / clipping is expected and fine.** Above the top of the felt range,
  clip. Slip during a high-speed lockup "still clips — that's expected, not a
  problem" (Sources: SimHub forum). Don't waste dynamic range trying to represent
  "beyond max."
- **Nonlinear washout: sustain small cues, wash big ones fast.** Small cues held
  longer read as texture; big cues washed quickly keep punch and make room for
  the next event (Sources: Telban nonlinear MCA). Port: short decay on small
  transients isn't needed, but *cap the decay* on big hits so they don't smear.
- **FFB layering / timing = road-feel vs steering-weight separation.** In sims the
  seat (motion) steps the rear out *before* the wheel goes light (FFB). Two
  channels, different jobs, staggered in time. **Port:** L motor = weight/body
  (steering-weight analogue, slow), R motor = road/tire grain (road-feel
  analogue, fast). Let load build on L, then slip take over — don't put both jobs
  on one motor.

---

## Part D — DRIVING-FEEL HIERARCHY (what to make loud vs quiet)

Loudest at top. This ordering *is* the design: a clear peak structure is what
lets each cue read. Everything above the line is Tier-1 "must have."

| Rank | Effect | Loudness role | Motor |
|---|---|---|---|
| 1 | **Impacts / collisions** | sharp PEAKS (loudest, briefest) | L+R |
| 2 | **Wheel lock (braking)** | strong, alarming | L |
| 3 | **Wheel slip / traction loss** | strong MID, the star | R→L crossfade |
| 4 | **Wheelspin (throttle)** | strong, throttle-gated | R→L |
| — | *— above = events that must always cut through —* | | |
| 5 | Kerb / bottom-out strikes | medium, brief (Tier 3) | L+R |
| 6 | Longitudinal G (accel/brake weight) | gentle swell | L |
| 7 | Lateral G (cornering load) | gentle swell → hands off to slip | L |
| 8 | Road texture floor | quiet, ever-present | R |
| 9 | **Engine RPM** | QUIETEST floor / ambience | L |

**The minimal 80%-of-the-feel set (build exactly these four first):**
1. **Wheel slip / traction loss** (R→L crossfade) — the connection to grip.
2. **Wheel lock under braking** (L) — the connection under braking.
3. **Road texture floor** (R, quiet) — the connection to the road at speed.
4. **Impacts** (L+R, sharp) — this is a *combat* game; hits must land.

Add engine RPM as a near-silent floor for "alive," then the G-forces for weight.
That is the whole car.

**Intensity discipline (the one rule that makes or breaks it):** engine = quiet
floor, road = quiet floor, G-forces = gentle swells, slip/lock/spin = strong
mids that appear only at the limit, impacts = sharp peaks. If the floors creep
up, the mids and peaks stop reading and the pad becomes a massage chair. When in
doubt, **turn the continuous stuff down.**

---

## Part E — TWO-MOTOR ALLOCATION SUMMARY (the mixer's job)

**Left / low / heavy motor** — WEIGHT & BODY (the slow channel):
- Continuous floors: engine RPM (very quiet), longitudinal-G, lateral-G swells.
- The heavy end of slip/wheelspin (as the tire fully lets go, crossfaded in).
- Wheel lock grind.
- Low-frequency body of impacts, kerbs, bottom-outs.
- Budget: engine + one G-load + slip-heavy ≈ the 3-continuous limit. Guard it.

**Right / high / buzz motor** — TEXTURE & EDGE (the fast channel):
- Road-texture/speed floor (quiet, ever-present).
- The fine-grain onset of slip / wheelspin (before it goes heavy).
- Front-slip / understeer "wash" bias.
- The sharp crack/edge of impacts and kerbs; gear-shift tick.
- Budget: road floor + slip-grain + shift-tick — keep it ~3 continuous max.

**Mixing rules (port these exactly — Sources: AV-Racer devlog, SimHub):**
1. **Per-motor MAX, not SUM.** Each frame, collect all effects' requested
   amplitude for L and for R, then take the **maximum**, don't add them.
   Summing weak effects = constant mush; max-selection lets the strongest event
   dominate and keeps a clear peak structure. (Multiply the winner by master
   gain.)
2. **Queue then flush once per frame.** Gather all effect requests during the
   frame, compute final L/R once, send one XInput update. (Direct XInput calls
   overwrite each other otherwise.)
3. **Longest-duration wins** for one-shot envelopes competing on a motor — avoids
   harsh cut-offs mid-thump.
4. **Envelope every transient** (attack-hold-decay via gain modulation): impacts
   ~0/40/200 ms, kerbs ~0/0/120 ms, gear tick ~single 60 ms pulse. Continuous
   effects need no envelope — just track telemetry with a short (~50 ms) smoothing
   so they don't chatter.
5. **Respect the ERM dead-zone:** map every effect's 0–100% level into roughly
   **0.30–1.0 of the XInput 0–65535 range** (a "Min Force" floor), so anything
   that fires is actually felt. Below ~30% the motor barely moves.
6. **Account for ~20–30 ms spin-up latency:** don't rely on sub-30-ms micro-
   pulses to read distinctly; make ticks at least ~40–60 ms. Fast machine-gun
   events should be represented as a single sustained buzz, not per-shot pulses.
7. **Gate hard, floor low.** Every effect wants a **Threshold** (dead-band so it's
   silent when nothing's happening) and a **Gamma ≥ ~1.5–2 expander** on the
   limit effects (slip, G, lock) so gentle driving is calm and only real events
   ramp up. Low **Input Gain** on slip so it doesn't clip every corner.

**Suggested starting numbers to code against** (all tunable; derived from the
SimHub slip recipe + ERM constraints — field-test and adjust):
- Master gain: 1.0 (single global "calm down" knob).
- Slip: Input Gain ~0.10, Threshold ~0.15, Min Force ~0.20, Gamma ~2.0.
- Lock: Threshold gated behind brake-pressure > ~0.4; Gamma ~1.5.
- Road floor: linear w/ speed, hard-capped at ~0.25 amplitude, off below crawl.
- Engine: idle ~0.10, redline ~0.30 amplitude, on L only, white-noise dither ±10%.
- G-forces: Gamma ~2, capped ~0.30 amplitude, 150–300 ms smoothing.
- Impacts: 1:1 to magnitude, clip at 1.0, envelope 0/40/200 ms (decay scales up
  with hit size, cap ~300 ms).
- ERM output mapping: `xinput = deadzone_floor + level*(1 - deadzone_floor)` with
  `deadzone_floor ≈ 0.30`, then `× 65535`.

---

## Sources
- SimHub ShakeIt V3 Effects configuration (gain layers, gamma/threshold/min-
  force, base/high frequency, white noise, gain modulation, input vs output
  mode): https://github.com/SHWotever/SimHub/wiki/ShakeIt-V3-Effects-configuration
- SimHub ShakeIt V3 Bass Shakers audio output config:
  https://github.com/SHWotever/SimHub/wiki/ShakeIt-V3-Bass-Shakers---Audio-Output-Configuration
- SimXPro ShakeIt-for-beginners (priority hierarchy: ABS>kerbs>gear>engine;
  "signal over noise"; less-is-more; placement; two-lap tuning):
  https://simxpro.com/en-us/blogs/guides/simhub-shakeit-for-beginners-tactile-feedback-that-makes-sense
- blekenbleu SimHub bass-shaker profiles (25–1000 Hz limits; effect composition):
  https://blekenbleu.github.io/pedals/shakeit.htm
- blekenbleu Slip/Grip haptic discussion (slip/grip ratio > slip alone; 30–60 Hz
  strongest, 150+/800+ Hz squeal; freq decreases with slip; randomization):
  https://blekenbleu.github.io/pedals/ShakeIt/SG.htm
- SimHub forum, Wheel Slip settings (Input Gain 10 / Threshold 15 / Min Force 20;
  clipping-in-every-corner fix; clip-on-lockup is expected):
  https://www.simhubdash.com/community-2/simhub-support/wheel-slip-shakeit-settings/
- makeabilitylab Vibromotors (ERM spin-up ~20–30 ms; freq/amp coupled; ~2.3 V
  start; F=m·r·ω²; 150–235 Hz natural freqs):
  https://makeabilitylab.github.io/physcomp/advancedio/vibromotor.html
- Microsoft XINPUT_VIBRATION (left = low-freq motor, right = high-freq motor;
  0–65535 range): https://learn.microsoft.com/en-us/windows/win32/api/xinput/ns-xinput-xinput_vibration
- WasSimulator AV-Racer devlog 5 (rumble event manager: queue-then-flush, per-
  motor MAX not sum, longest-duration wins):
  https://wassimulator.com/blog/programming/av-racer/devlog_5.html
- GameJuice haptic feedback article (reactive-not-constant; scale to
  significance; build a vocabulary; intensity tiers; low-motor=weight,
  high-motor=light events): https://gamejuice.co.uk/articles/haptic-feedback-rumble-dualsense
- Cruden "Acceleration is not enough" + MOZA motion blog (seat cues rear stepping
  out before the wheel goes light; onset cues > steady state):
  https://www.cruden.com/article/acceleration-is-not-enough-theres-more-to-accurate-motion-cueing-than-meets-the-eye
  ; https://mozaracing.com/blogs/focus/how-does-a-motion-simulator-work-in-sim-racing
- Telban, "A Nonlinear Motion Cueing Algorithm With a Human Perception Model"
  (washout high-pass; sustain small cues, wash big cues fast):
  https://repository.fit.edu/link_modeling/34/
