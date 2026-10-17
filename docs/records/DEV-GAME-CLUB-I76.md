# Dev Game Club on Interstate '76: what the developers said (2026-10-17)

Task W1 of the physics-step study (PHYSICS-STEP-STUDY-DESIGN s.9), approved by the owner. The four Dev Game Club
episodes on I'76 were downloaded, transcribed locally and searched for first-hand statements about the physics, the
frame rate, the hardware, tuning, the car model, AI, damage and versions.

**Short answer.**
- **The only first-hand physics statement is Julio Jerez's**, relayed in writing (email from listener "Carlos", read
  aloud by host Brett Douville, ep 424, 00:14:56-00:21:46). Jerez is credited as 3D Programmer, but says he also
  "worked extensively on the game['s] pseudo physics" and wrote the **tire suspension as a second-order digital
  filter**.
- **Design rate: 15 fps.** "The game was designed to run at 15 frames per second. Anything faster was considered a
  bonus." (00:20:04). Carlos's summary: "this target time step was 1/15th of a second" (00:17:39).
- **Acceptable range: 10-30 Hz.** The filter coefficients are "calculated to resonate at 15 hertz. It'll be OK in
  between 10 and maybe 30 hertz. Once you pass that sample rate, it's just a low pass filter" (00:21:12). Carlos:
  "10 to 20 frames per second, depending on the machine ... still within the acceptable range"; "anything beyond 30
  frames per second would make their numerical methods behave in unexpected manners" (00:17:44-00:17:59).
- **Not a fixed step:** "the physics was not independent of the time step. Everything ran in the same loop"
  (00:19:54); "the time step is not regulated, or at least it wasn't on the release project. There's no constraint
  physics of any kind in the game" (00:20:32).
- **The filter is code clue P1.** The wheel ride-height filter (init `push 15.0`, `push 0.7` -> 0x49e0f0) is a
  second-order filter whose period parameter is **15 calls**. Read with Jerez's "15", it was designed at **15 calls
  per second** (66.7 ms), where it gives a 1.31 Hz ride with a 1.0 s damped period [inference, medium].
- **But the shipped stepper never runs a 66.7 ms step.** C1 / C2 cap the substep below 50 ms, so a 15 fps frame
  runs 2 x 33.3 ms. **The filter therefore ran at 20-40 Hz on 1997 machines, i.e. at or past the top of Jerez's
  "OK" band.** Jerez says there were "many updates and changes after I moved on", so the substepper may postdate his
  tuning [inference].
- **What it means for the study (proposals, owner decides):** Jerez's band (10-30 Hz, i.e. 33.3-100 ms per filter
  call) intersected with the engine ceiling (< 50 ms) is **33.3 ms <= T < 50 ms**. That is the upper two-thirds of
  the pre-registered band (27-<50 ms); it moves the evidence toward the P1 side (44-50 ms) of the P1 / P6 trade-off
  and puts the 27-30 ms cells outside the implementer's stated range. Section 5.

## 1. Sources and integrity

Feed: https://devgameclub.libsyn.com/rss (fetched 2026-10-17; show notes saved as
`i76-uncap-lab\refs\devgameclub\show-notes-422-427.txt`). No transcript, captions or official show notes beyond the
topic list exist (checked in the earlier session; DEV-INTENT-EVIDENCE s.5 Nulls).

| ep | title, date | role | file (lab `refs\devgameclub\`) | bytes (= RSS enclosure length) | SHA-256 |
|---|---|---|---|---|---|
| 422 | Interstate '76 (part one), 2025-03-12 | hosts only | `ep422-dl\422-DGC-I76.mp3` | 45,601,560 | `83ec503b0e2f322881e2ecd23590d536fd7857577aa803783b6911faa8f02813` |
| 423 | Interstate '76 (part two), 2025-03-19 | hosts only | `ep423-dl\423-DGC-I76.mp3` | 47,798,468 | `28ad10665c0b68834732910d815080dcdb16521c776218723f0765db2bf5eba9` |
| 424 | Interstate '76 (part three), 2025-04-02 | **Jerez email** | `ep424-dl\424-DGC-I76.mp3` | 52,299,120 | `faa9e1f587fe9bde9a1540abece4d176feea76a79d5e5190fd59787cb7111d1e` |
| 427 | Interview with Sean Vesce and Zack Norman, 2025-04-23 | director + lead designer | `ep427-dl\427-DGC-I76.mp3` | 44,483,208 | `80649f8cae04d434dd81e3eac0133a316c920766a0e1a2de895c3235c20935b0` |

- URLs: `https://traffic.libsyn.com/secure/devgameclub/<ep>-DGC-I76.mp3?dest-id=358622`.
- 422 / 424 / 427 were downloaded by the earlier (paused) session; this session re-hashed them: all three match its
  `SHA256SUMS.txt` and the byte counts equal the RSS enclosure lengths, so they are complete. 423 was added here (its
  notes list "broken physics world, compounded errors") and appended to `SHA256SUMS.txt`.
- Hosts: Brett Douville (programmer; LucasArts, Bethesda; **not on the I'76 team**) and Tim Longo (designer). Their
  physics remarks are commentary, not developer testimony (section 4).
- Full transcripts stay in the lab only (copyright): `refs\devgameclub\transcripts\<ep>-DGC-I76.small.en.{txt,json}`
  and `424-clip-0870-1440.small.en.beam5.txt`.

## 2. Method

- faster-whisper 1.2.1 (CTranslate2 4.8.3) in a venv, `i76-uncap-lab\tools\stt\venv` (Python 3.12.10). Model
  `Systran/faster-whisper-small.en`; `model.bin` SHA-256 `62b2a45b...e37a` matches the Hugging Face LFS hash.
- CPU only, int8, `cpu_threads=2`, one episode at a time, BELOW_NORMAL priority. The earlier session's script set the
  priority with a truncated pseudo-handle and silently stayed at Normal (read back with Get-Process); fixed
  (`restype c_void_p`, exit on failure) and the running process lowered by hand. Verified BelowNormal afterwards.
- Pass 1: whole episodes, beam 1, VAD, no context carry-over, timestamps per segment. About 10.7 min wall per hour
  of audio (e.g. 424: 4,462 s audio in 782 s).
- Pass 2 (cross-check): the key 424 passage (870-1440 s) again with beam 5, no VAD, context on (`clip_check.py`).
  **Every number and technical phrase in section 3.1 is identical in both passes** (1/15 s, 10-20 fps, 30 fps,
  15 fps, 15 hertz, 10-30 hertz, "second-order digital filter", "y = ax^2 + bx + c", "not regulated").
- Scripts: `tools\stt\transcribe.py`, `clip_check.py`, `run_queue.ps1`; run from that folder with the audio path as
  an argument and `python -I`. Nothing was run from the download folders.
- Searched with keyword greps (physics, frame, hertz, fps, step, Pentium, 3Dfx, patch, Gold, suspension, damage,
  collision, AI, engine ...) and then read the surrounding passages in full.

## 3. Quotes

Timestamps are pass-1 segment starts (hh:mm:ss). [sic] marks likely transcription or speech errors.

### 3.1 Episode 424: Julio Jerez via Carlos (the only first-hand physics source)

Chain of custody: Jerez -> written replies to Carlos (a Discord member with "a loose work connection") -> Carlos's
email, which says he will "not alter" Jerez's words but adds his own context -> read aloud by Brett. Brett's
interjections are left out. The reading makes clear which paragraphs are Jerez's ("here's Julio's explanation",
"This is Carlos again").

**Carlos's context paragraph (second-hand; his summary, he calls his understanding "superficial at best"):**
- 00:17:29 "This is why physics engines tend to opt for a fixed time step update, which is often a multiple or
  independent from the game's frame rate. In the case of Interstate 76, this target time step was 1 15th of a second.
  However, the frame rate was never capped, which at the time meant that the game could run anywhere between 10 to
  20 frames per second, depending on the machine, which was ... still within the acceptable range for their
  simulation. Anything beyond 30 frames per second would make their numerical methods behave in unexpected manners,
  but that wasn't a realistic issue at the time."

**Jerez (first reply):**
- 00:19:00 "Yes, I was the graphics programmer for Interstate 76. Many games thereafter use my old software
  Rasterizer graphics library."
- 00:19:09 "When I joined Activision, the MechWarrior 2 engine was quite limited in terms of rendering features for
  i76. I offered my Rasterizer and they ended up replacing the majority of the graphics of the MechWarrior 2 engine,
  renaming it the dark side engine [sic; likely 'Darkside']. The main game logic part remained untouched. Many of the
  technical staff refused to modify it because they were proud of MechWarrior 2 and its derivatives."
- 00:19:32 "The vehicle physics in Interstate 76 actually stems from the MechWarrior physics. The cars were adapted
  from the mechs and the lead programmer on this was Daniel Stanfield [sic; Dan Stanfill, per the credits]."
- 00:19:41 "I contributed by adding physics elements like tire suspension, which they struggled to stabilize. To fix
  this, I implemented a second-order digital filter. I worked extensively on the game['s] pseudo physics."
- 00:19:54 "However, as I recall, the physics was not independent of the time step. Everything ran in the same loop,
  which was common for games back then."
- 00:20:04 "The game was designed to run at 15 frames per second. Anything faster was considered a bonus. I don't
  even think it had a vsync cap, though I might be wrong, as there were many updates and changes after I moved on to
  other projects. It's no surprise, in a very fast machine, the game doesn't run properly."

**Jerez (follow-up on the time step and constraint methods):**
- 00:20:32 "Yes, the time step is not regulated, or at least it wasn't on the release project. There's no constraint
  physics of any kind in the game."
- 00:20:57 "The suspension of the car is just a second order digital filter. That is, it samples the terrain height,
  applies that as an input of an equation. y equals ax squared plus bx plus c [sic, see below]. x is the relative
  elevation height. A, B, and C are calculated to resonate at 15 hertz. It'll be OK in between 10 and maybe 30 hertz.
  Once you pass that sample rate, it's just a low pass filter. The output is just the C constant."

**Carlos's gloss (second-hand):**
- 00:21:28 "The shorter the time step, the smaller the sampled elevation gain will be in its simulation step. With
  high enough frame rates, the elevation gain values are zeroed out in the equation above, which leads to the
  suspension of the car being tied to a simple constant value resulting in jittery physics."

Reading notes:
- "y = ax^2 + bx + c" is not a second-order *filter*; it is most likely Jerez's shorthand for a second-order
  difference equation (y[n] = a y[n-1] + b y[n-2] + c x[n], or the z-domain polynomial). The code's filter at
  0x49e1b0 is that form: a1 = -2 r cos(2 pi / period), a2 = r^2, unit DC gain (DEV-INTENT P1). Both passes heard the
  same words, so the oddity is the speaker's or Carlos's, not the transcriber's.
- "Resonate at 15 hertz" read literally (a 15 Hz ride) is implausible for a car body. The code's only 15 in the
  wheel code is the filter's **period of 15 calls**. The consistent reading: the coefficients were derived for a
  **15 Hz sample rate**, i.e. one call per 1/15 s frame, giving a resonance of 1 Hz. "OK between 10 and 30 Hz" and
  "once you pass that sample rate" are both sample-rate language. [inference, medium]
- "Jittery physics" at high rates matches the owner-facing symptom and our measured P4 buzz below about 25 ms.
- The 1997 numbers are a 28-year recollection by the renderer programmer, relayed twice. Treat the 15 fps design
  point and the 10-30 Hz band as **testimony, medium confidence**; they are not code facts.

### 3.2 Episode 427: Sean Vesce (director) and Zack Norman (lead designer)

Speaker attribution from context; the hosts named Vesce "Sean" and Norman "Zach".
- 00:33:25 (Vesce) "we pitched this on the premise that we would be using MEC2's [sic: Mech 2's] engine, and that
  would be a huge time saver."
- 00:34:08-00:34:52 (Vesce) "it was a complete disaster trying to leverage the mech 2 engine ... the engine itself
  was a complete mess. And I think we spent the first four or five months trying to leverage it. And the super
  secret, which I think I can finally reveal 30 years later ... is we ended up without telling anybody starting from
  scratch. We started a completely new engine and didn't mention it to anybody."
  - **Conflicts with Jerez** ("the main game logic part remained untouched"; the vehicle physics "stems from the
    MechWarrior physics") and with Vesce's own 1999 Gamasutra account ("MechWarrior 2 engine extended",
    DEV-INTENT s.4).
    Likely both are partly true: a new renderer, terrain, roads, tools and pipeline (Jerez's "dark side" engine)
    over retained MW2 game logic. Nothing here says the physics step was rewritten.
- 00:35:10-00:35:57 (Vesce) Julio "Jimenez" [sic: Jerez] as the "rock star engineer": dynamic terrain tessellation
  "really high definition up front and low pols [sic] in back".
- 00:36:21-00:36:59 (Norman) "If a car is traveling at 100 miles an hour inside the simulation, and you're trying to
  figure out if it's going to collide with another car, and you have to optimize that collision, because I can't do
  collision detection every frame. This is software. I can't do that every frame on every vehicle every time. You
  have to basically do these wonderful things that Sean and his team figured out how to do to optimize the game so
  it would actually run ... these vehicles that move very, very fast and do physics on different kinds of terrain
  types". Fits code P10: object / vehicle collision once per frame (only the last record survives) and far vehicles
  advanced by one whole-frame kinematic step (0x43a3c0).
- 00:37:06-00:37:43 (Vesce/Norman) roads are not tiles: a spline traced through the terrain grid, smoothed and banked
  ("a smoothing algorithm on it and then do a banking algorithm on it").
- 00:50:55-00:51:05 (Norman) terrain types with different grip: "the side of the road is different from the
  blacktop and then off into the desert".
- 00:51:41-00:52:44 (Vesce) heightmap painted as a greyscale bitmap, "Julio's terrain" renders it; roads as splines;
  "all of the mission design was done through an objective system that was all script-based"; "an AI system, a
  state-based machine for each individual car that could be configured". 00:55:44 the MW2 FSM was "very basic"; the
  I'76 FSM later seeded MechWarrior 4's.
- 00:44:23 team "like 12 or 13 people total".
- 00:18:09-00:19:04 MW2 history (Tim Morten got MW2 out of DOS protected-mode memory limits). Not about I'76.
- 01:04:48 the hosts say they would like to reach Dan Stanfill for a follow-up ("the Dan Stanfilling [sic]"). No such
  episode exists in the feed as of 2026-10-17 (all 489 item titles and notes searched for Stanfill / Jerez /
  Interstate). Eps 425 and 428 (Fez) list I'76 / Vesce / Norman among topics, probably follow-up mail; not
  downloaded.
- **No statement in 427 about frame rate, physics step, target hardware, 3Dfx / Gold or patches.**

### 3.3 Episodes 422 / 423: hosts only (not developer testimony)

- 422 00:50:11 (Longo) on GOG/modern hardware: "the physics when you're going over terrain, it's very jittery and
  very light. So is it because the frame rate's too high?" (Douville) "It is, yeah."
- 422 00:51:12 (Douville) "how many forces can we resolve in whatever, you know, 1 20th of a second, which I gather
  is like the sweet spot for the physics system for this." Community lore (the 20 fps cap), not a source.
- 422 00:50:36 Douville guessed "some kind of simple constraint system" with breakable joints; Jerez corrected this in
  424 ("no constraint physics of any kind").
- 423 00:34:11-00:35:52 (Douville) small time steps lose float precision; "wheels aren't touching the ground every
  other frame". A general mechanism argument. Our code reading instead finds per-step terms (P1 sampled-elevation
  filter, P4 snap) as the high-rate cause, which is also what Jerez/Carlos describe.
- 423 00:51:36 (Douville) "I'm down at 20 frames a second locked. So ... the physics have been mostly fine."
- 423 00:45:05 road LOD pops out with the mountains. Rendering, not physics.

### 3.4 Nulls

Nothing in any episode on: target CPU / minimum spec, the P90, 3Dfx / Glide, the Gold edition, Nitro Pack, patches
1.01-1.05, damage model internals, AI tuning numbers, or the substep / stepper itself.

## 4. How this fits the code evidence (DEV-INTENT-EVIDENCE)

| statement | code | fit |
|---|---|---|
| suspension = second-order digital filter by Jerez | P1: 0x49e0f0 init (period 15, r 0.7), 0x49e1b0 per substep; feeds the push-out | **match** (form and the number 15) |
| designed at 15 fps; filter "resonates at 15" | P1 period 15 calls: at 66.7 ms per call fn 1.31 Hz, damped period 1.0 s, damping 0.648 | consistent if "15" is the design sample rate [inference] |
| filter OK 10-30 Hz, low-pass beyond | P1 per call: 30 Hz = 33.3 ms (fn 2.63 Hz); 40 Hz (25 ms) fn 3.5 Hz | the per-call rate decides it; the stepper's < 50 ms cap means 1997 machines ran it at >= 20 Hz |
| time step not regulated; all in one loop | C2 variable substep = sim_dt / n; P10 per-frame systems | match |
| no constraint physics | push-out (P3), overshoot snap (P4), landing snap (P6) | match |
| collision not every frame on every vehicle (Norman) | P10: per-frame collision, far-vehicle kinematic step | match |
| frame rate never capped (Carlos), no vsync cap (Jerez, unsure) | not re-checked here; the C-table scan found no frame-time constant other than the stepper's | consistent, unverified |
| "> 30 fps behaves unexpectedly" | P4 buzz onset below about 25 ms (measured); community 20-25 fps caps | broadly consistent |
| vehicle physics from MechWarrior (Jerez) vs new engine (Vesce) | DEV-INTENT s.4: "the MechWarrior 2 engine extended" (Games Domain 1997; Vesce, Gamasutra 1999); data in `DATABASE.MW2` | Jerez fits the record better for the physics |

Open point: did the substepper (C1 / C2) exist when Jerez tuned the filter? If not, his 15 Hz was a 66.7 ms step,
which the shipped engine never runs. Every 1997 patch keeps the stepper byte-identical (I76-VERSIONS s.3.2), so
the archive cannot date it; only a pre-release build (a 1996 demo or press beta, if one surfaces) could.

## 5. Implications for the physics-step study (proposals; the pre-registered design is unchanged)

1. **Bounds.** Jerez's 10-30 Hz with the < 50 ms ceiling gives 33.3 <= T < 50 ms for the filter. The pre-registered
   lower bound (27 ms, measured P166 lowest detail) is a 37 Hz filter rate, past his "OK" edge. Propose: keep 27 ms
   as the measured era floor, but **flag 27 / 30 ms as outside the implementer's stated range** in the write-up, and
   weight the 33.3-49 ms cells.
2. **P1 vs P6.** The testimony identifies P1 as a designed, tuned element with a stated rate, which P6 (the 0.5 m
   landing band) has not. It raises P1's intent confidence from low-medium to medium and favours the upper band
   (40-49 ms) in a tie. Landing survival (P6) remains a hard constraint in the decision rule (s.6), so it is still
   measured, not assumed.
3. **The 15 fps design point (66.7 ms) is above the engine ceiling** and is not a candidate. It means a 2 x 33.3 ms
   regime on the hardware they targeted. That is inside the grid (33.3) and near the P166 default-detail measurement
   (2 x 37.6 ms).
4. **40 ms neutral start stands.** 40 ms = 25 Hz, inside Jerez's band, and within the 2 x 33-37 ms "as played"
   regime.
5. **Do not cite this as a fixed-step design.** Jerez says explicitly that the step was not fixed; "target time step
   1/15 s" is Carlos's phrasing.
6. **Follow-ups (optional, owner's call):** ask Dev Game Club / Carlos whether Jerez or Stanfill would answer two
   questions (did the substepper exist when the filter was tuned; what sample rate were the A/B/C coefficients
   computed for). OUTREACH-DRAFT.md is the place for that.
