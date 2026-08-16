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
**sandbox** (`i76-uncap-lab\game`) is currently patched to **5000 m** (stock is 600) with the render
pools enlarged 16× (the fix for the crash that capped it). Screenshots in
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

## D. Not blocking a test — research state

- **Texture LOD at distance** (the other half of improvement #3): path known, deferred — the far
  mips are hand-authored pak data; sharpening them is a content mod like the retired HD-textures
  experiment. See DRAW-DISTANCE.md's last section.
- **Collision pass-through** bug: found **not cleanly auto-measurable** on the training level (it's a straight
  accelerating road with no early obstacle on the car's auto-path). Needs a mission with a known early wall,
  or a manual run.
