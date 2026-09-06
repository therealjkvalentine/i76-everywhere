# Ready to test — next hands-on session

Everything below is **already deployed to the portable daily-driver install**
(`…\Interstate76-i76-everywhere-portable-20260801\Interstate 76`) and verified as far as it can
be without a human at the machine. Both fixes are on and consistent (checked 2026-08-16).

> **Must be at the physical console.** The 3D engine won't initialize over RDP, so every item in
> section A needs you in front of the machine. Audio was left muted during the unattended work; unmute
> when you sit down.

Deployed state, confirmed:

| Fix | Where | Status |
|---|---|---|
| **u32x save/mouse proxy** (no freeze + full-screen mouse) | portable `i76shell.dll` → `u32x.dll` | PATCHED, `u32x.dll` present (74,752 B) |
| **60 fps camera rate** (death-cam / pan) | portable `i76.exe` constant | `-0.3333°` = stock × 20/60 → tuned for 60 fps |

---

## A. Tests to run at the console

### A1 — Full-screen mouse (the core of the freeze fix)
- In the garage/menus, the click should land **where the cursor visually is**, anywhere on the screen —
  not only in the top-left ~640×480 patch. Move to the far corners and click a button to confirm.
- **Pass = the old "mouse in the wrong place" is gone.**

### A2 — Save without freezing (the headline fix)
1. Start/continue a mission, open the save screen.
2. Press **SAVE**. When the **"Overwrite an existing bookmark?"** popup appears, click **YES/NO where they
   visually are.**
3. Expect: it answers immediately, writes the save, returns to the garage. **No "not responding," no hang.**
- This is the exact popup that used to spin forever. If it ever *does* seem stuck, the old emergency
  unstick still works (move to the top-left of the screen and click roughly where the button would be at
  640×480) — but it should not be needed.

### A3 — New save vs. "always overwriting"
- **Keep** the pre-filled name and SAVE → it **overwrites** your loaded progress bookmark. That's expected
  behavior now, not a bug.
- Type a **different** name and SAVE → it makes a **new slot**, no overwrite prompt.
- Takeaway to confirm: the "always says overwriting" was the field pre-filling the loaded bookmark's name;
  a fresh name gives a fresh slot.

### A4 — Save-name typing (open question — please observe, don't assume a fix)
The name box is a **message-queue / focus** path (traced to `i76shell.dll+0x1D630`: a 64-entry ring buffer +
`PeekMessageA(WM_KEYFIRST..WM_KEYLAST)` with its own `ToAscii` translation — *not* a slow poll, and untouched
by the cursor proxy). Prediction: **it works cleanly when you type at human speed into a focused field**; my
synthetic key injection dropped 4/5 chars only because it raced focus/delivery.
- Click the field first (ensure focus), type a name at normal speed. **Does every character land?**
- If it still drops keys **while focused**, that's the real remaining bug and I'll design a keyboard-path
  shell patch. If it's fine when focused, we can close 1c. Please note which.

### A5 — 60 fps camera feel (the rate fix)
- **Death camera:** get destroyed; the orbit/spin should look **smooth and normal-speed**, not the ~3× fast
  whip it had before at 60 fps.
- General camera pans/turns should feel right (not sped up). If anything feels *slow*, that's the opposite
  error and tells me the fps assumption is off — note it.

---

## B. Saves — what you actually have (answer to "not in the repo?")

You have **5 saves**, identical in the repo, the portable install, and the sandbox — decoded as:

| Slot | Mission | Loadout |
|---|---|---|
| save000 | 2 | Picard Piranha / Stock |
| save001 | 3 | Picard Piranha / Stock |
| save002 | 5 | Picard Piranha / Stock |
| save003 | 6 | Picard Piranha / Stock |
| save004 | 6–7 (not cleanly decoded; 71 items) | Picard Piranha / Stock |

**Missions 1, 4, and 7→end are not here.** The "every scene to the end" set you remember from the Mac work
was **never committed to git and is not anywhere on this machine** (checked all history in this repo and every
`.cmp` under your user profile — only these 5 exist). If it survives, it's in the Mac wrapper's own save
folder on the Mac, or a gitignored `game-data/` that never came across.

**Practical way to reach any missing mission without that set:** the save editor can re-point a save's scene.
Clone one of the 5 and bump its scene number:

```bash
python i76-save-editor.py --list                 # see the slots and their missions
```

Open the web editor (`i76-save-editor.html`) or the Mac `./i76-save-editor.command`, load a save, change
"Scene №," save-as a new slot. That jumps the campaign pointer; the garage inventory comes from the cloned
save, so start from the nearest mission you have.

---

## C. Rollback (if any test regresses)

Both fixes are reversible with backups kept beside the originals:

```bash
# from i76-uncap-lab:
tools\instruments\deploy-shellfix.ps1 -GameDir "<portable>\Interstate 76" -Restore   # mouse/save fix off
tools\framerate\patch-camera-rate.ps1 -GameDir "<portable>\Interstate 76" -Restore   # camera rate back to stock
```

`-Status` on either shows the current state without changing anything.

---

## A6 — Draw distance (NEW, 2026-08-16 — sandbox only, judge before deploying)

**Cracked and verified unattended** — [DRAW-DISTANCE.md](DRAW-DISTANCE.md) has the full story. The
**sandbox** (`i76-uncap-lab\game`) is currently patched to **8000 m** (stock is 600; 12000 crashed
even big pools) with the render pools enlarged 128× (the fix for the crash that capped it). Screenshots in
`i76-uncap-lab\captures\farclip\` show the delta: fog-clipped mesa stubs → full mountain ranges.

Your call at the console, in the sandbox:
1. Launch the sandbox, drive the training mission (or any mission). **Does the long horizon look
   right to you?** Full mountain silhouettes, less haze — more Utah, less murk.
2. Watch for the known caveats: buildings/roads may still pop at their old shorter cull distance,
   and distant vehicles are now visible (including ones the mission design assumed were hidden).
3. FPS cost measured at zero (60.0 flat at 5000 m), but feel free to confirm it feels smooth.
4. Pick the portable's dose: **1800** (conservative, dramatic) or **5000** (maximal), then say the
   word and I'll deploy `patch-farclip.ps1` to the portable (with `.farorig` backup, composes with
   the camera patch) — or `-Restore` puts the sandbox back to stock if you hate it.

## A7 — Force feedback: RPM/shift + the bass shakers (NEW — two threads meeting)

Two separate threads both landed in `tools/ffb/` and have **never been run together**. This is
the session that tests that.

There is now a **third** claimant on the same events — the Mac's in-process shim, merged
2026-09-06. It does not run here, but it decoded the same effect block and disagrees about
one field. Read [FFB-STACKS.md](FFB-STACKS.md) before this session: it maps both stacks,
lists what they independently confirmed, and carries the pick-up notes for this box.

### Where the RPM/gear work is

| Thing | Where |
|---|---|
| **RPM itself** | `0x4F2334` — offset `+0x0C` inside the 364-byte FFB param block at `0x4f2328`. Read in `Telemetry.ps1:752`, clamped to 0–20000. It is **not** in the vehicle entity struct |
| Why the first scan failed | `ffb-find-rpm.ps1` scanned the entity struct: across 555 parked frames only **four** slots in 0x400 bytes moved, and they were throttle and steer. A true null, not a threshold problem |
| What found it | `ffb-find-rpm-wide.ps1` — whole-process scan including `MEM_IMAGE` (the exe's own data, which the standard dumper excludes), using an alternating idle→revs→idle→revs test rather than correlation |
| Shift detection | `Tel-DetectShift` in `Telemetry.ps1`, extracted so it can be tested against synthetic traces with no game running — same reason `Tel-Slip` was extracted |
| Shift force | `ShiftGain 2600`, `ShiftMs 90`, `ShiftDownScale 0.55` in `Mix-DefaultTune`; fires a 30 Hz `jolt` transient |

**It still keeps filling with the crash-guard active.** Bypassing the engine's FFB call at
`0x52bbe4` (which stops firing a weapon from crashing the game) does not stop the block being
written, so RPM survives the workaround. Worth re-confirming live.

### Where the shaker work is

`ffb-lfe-live.ps1` streams to the transducers while you play; `LfeSynth.ps1` holds the DSP,
the winmm device layer and the streaming class. `ffb-lfe-probe.ps1` renders scripted driving
scenarios and `ffb-lfe-trace.ps1` inspects the chain stage by stage — **both run with no game
and no operator**, so most faults should be found without a play session.

### What to run

```
powershell -NoProfile -ExecutionPolicy Bypass -File tools\ffb\ffb-lfe-live.ps1 -Device 0
powershell -NoProfile -ExecutionPolicy Bypass -File tools\ffb\ffb-interposer.ps1
```

Device 0 is the Audient EVO 4. Run the interposer alongside — telemetry reads are read-only,
so the two do not contend for game memory.

### What to watch, in order of what is least proven

1. **Shift detection has never seen a real drive.** The logic is unit-tested; the *thresholds*
   are guesses. `rpmRate` is logged, so one normal drive replaces them with numbers. Watch for
   shifts that fire twice, or fire on a lift-off.
2. **BOOM stays 0.00 while things explode.** The explosion channel is keyed on effect-table
   magnitude ≥40 (gunfire reads 5–10, something heavier reads 60). If a missile hits or a car
   blows up nearby and BOOM never moves, that table only carries the *player's* own effects and
   the blast signal has to be found elsewhere.
3. Impact / weapon / scrub / heave all reading sensible numbers rather than pinned or dead.
4. Whether the wheel and the shakers fight each other — untested in combination.

## D. Not blocking a test — research state

- **Texture LOD at distance** (the other half of improvement #3): path known, deferred — the far
  mips are hand-authored pak data; sharpening them is a content mod like the retired HD-textures
  experiment. See DRAW-DISTANCE.md's last section.
- **Collision pass-through** bug: now **fully automated and ready** — the earlier "not measurable"
  verdict was wrong (the training level has 89 saguaros with exact ODEF coordinates; the car just
  needed to be steered at them). When the machine is on the physical console, one command runs the
  whole 20-vs-60 A/B and prints the hit rates:

  ```
  powershell -ExecutionPolicy Bypass -File ..\i76-uncap-lab\tools\framerate\cactus-ab.ps1
  ```

  ~15 cactus approaches per rate across 3 cold mission loads each, ~15 min unattended. I can run it
  myself whenever the console session is active — it only needs the screen unlocked at the machine.
