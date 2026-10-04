# Testing scripted set pieces and bug-prone weapons

*What worked, what didn't, and how to run the tests that still need a human to line them up.*

## Runtime FPS switch — works, and it matters

`i76uncap.dll` now limits frames itself: put `fpscap=N` in `captures/i76uncap.ctl` and the rate
changes **without relaunching the game**. Verified live: 60 → 20 → 30 → 60 → 20 fps, each
holding exactly.

This removes the biggest confound in every earlier comparison. dgVoodoo's `FPSLimit` and
`I76PATCH.DLL` are both read once at startup, so changing the rate used to mean a relaunch —
and a relaunch meant a different spawn, different terrain, and a different run. Now one process
can be measured at several rates from the same state.

## Save-state — attempted, and it does not work. Use bookmarks instead.

The goal was emulator-style snapshot/restore so a human could line up a scripted set piece (the
Mission 5 canyon jump) once and have it replayed identically. `savestate=1` snapshots fine
(246 regions, ~43 MB). **`loadstate=1` kills the game, in three different ways:**

1. Restoring every private RW region clobbered the calling thread's **own stack** — the return
   address went with it and the process died instantly.
2. Excluding stacks: still died. Other threads kept running over heap that was being rolled
   back underneath them.
3. Suspending every other thread first: still died.

The reason is structural. Those regions hold heap metadata, CRT state, and dgVoodoo/DirectDraw
internals, plus handles to objects the OS owns. An emulator can restore a snapshot because it
owns a flat, self-contained memory image; a live Win32 process does not have that property.
The code is kept, disabled-by-warning, as a record of the attempt.

**What to use instead — and it is enough:** the game's own bookmark saves give a reproducible
start state, and `fpscap` changes the rate without relaunching. Two independent loads of the
same bookmark put the player within **0.4 m** (z within 0.02 m) and all four entities within a
metre — against the tens of metres of divergence that made earlier runs incomparable.

```powershell
autotest\enter-mission5.ps1                  # load bookmark -> mission 5 gameplay
autotest\enter-mission5.ps1 -SceneY 833      # scene 6 (rows are ~50 px apart)
autotest\enter-mission5.ps1 -StopAtGarage    # stop on Build & Repair to change weapons
```

## Mission 5 canyon jump — needs a human to line it up

`enter-mission5.ps1` reaches mission 5 gameplay reliably (save002, 4 entities, sim confirmed
running). What automated driving **cannot** do is find the canyon ramp: a blind full-throttle
run with weaving reached only 19.4 m/s and produced two 0.3 s hops, nowhere near the jump.

To finish this test, drive the approach yourself and then hand it over — the frame rate can be
switched mid-session with `fpscap`, and `tools/framerate/fall-test.ps1` records every frame, so the same
approach can be flown at 20 Hz and 60 Hz and the trajectories compared directly.

## Weapons

- `weapon_fire` is bound to **Enter**, not Space. The comment at the top of `input.map` is
  stale and cost a round of "the weapon isn't firing" debugging.
- **MG fire rate is timer-driven, not per-frame** — the measurable version of the "weapons
  break at high FPS" report. Over 5 s of held fire the ammo counter went 2000 → 1951 at 20 Hz
  and 2000 → 1931 at 60 Hz: 9.7 vs 13.8 rounds/second, but 0.505 vs 0.228 rounds/**frame**. A
  per-frame weapon would have drained three times faster at 60 Hz. It did not.
- **Flamethrower: not tested.** It exists in save003/save004 (`flm01`, in the van), but
  equipping it needs the Build & Repair weapon-slot cycle arrows, and those clicks did not
  register. `CONFIGURE CHASSIS` is disabled in Instant Melee, so the melee route is closed too.
- **Mortar/rocket projectiles: not measurable from the entity table.** Fired rockets do not
  appear in the world position table (18 slots, unchanged across shots), so projectiles live in
  a separate system that has not been located. Tracking them needs that system found first.
