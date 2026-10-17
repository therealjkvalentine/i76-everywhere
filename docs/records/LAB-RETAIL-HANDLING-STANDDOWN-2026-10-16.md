# lab-retail-handling lane, overnight 2026-10-16: stood down (with a verify note)

Written by the overnight synthesizer from the lane's own report (its report_path was empty) and its verifier.
The switch, builds and write-up this lane was briefed for belong to the console lane: [RETAIL-HANDLING-SWITCH.md](RETAIL-HANDLING-SWITCH.md)
(commit 151cf13, s.7 in be5e594).

## What the lane reported

- **Switch already existed.** `I76_RETAIL_HANDLING=1` in `music-fix/strlkproxy.c` (`retail_handling_frame` line 7249,
  `apply_retail_handling` line 7261): each frame it sets entity +0x454 bit 0x10000 (= Options > Arcade Phys.) on the player's car.
  - The lane said "uncommitted". **Stale:** it was committed in 151cf13 (23:15:37) before the lane reported (verifier).
- **Builds** (hashes read back by the verifier): `music-fix\out\Strlkup-rh1.dll` 73eb2cfd, `Strlkup-rh2.dll` 0406e909
  (= lab `builds\retail-handling-20261016`; build-rh2.log 23:04). Only rh1 carries the wrong "1997 retail default" log text.
- **No handling patch is needed** (RETAIL-HANDLING-DIFF s.6, 3f468e4): the retail vs Gold gap was Arcade Phys. on by accident in the
  retail emu runs. Both exes default the option off, so our exe already has stock retail handling. The switch only reproduces the
  arcade runs as they were measured; it does not move us toward the gold standard.
- **Lateral limit C** (recomputed by the verifier with `tools\retail-handling\latlimit.py`): Gold, arcade off, 31.48-31.75
  (5 runs / 16 phases); retail, arcade on, raw medians 19.31-23.45 (6 runs / 18 phases); the slope-corrected 23.32-23.47 was
  checked on one worked example only. Arcade-off retail run 224135-r166sim-mloop: 31.55-31.63 (8 phases, 1 run) = Gold.

## What actually happened after the report (verifier)

- The same agent kept working after returning "stood down":
  - 04:15Z wrote `tools\retail-handling\steerhold.py` and `run-rh.ps1`;
  - 04:16Z (23:16 local) ran `run-rh.ps1 -N 1 -Conds on`: took `.console-owner`, booted the twin via proxy-run with
    Strlkup-rh2, T06, in the mission after 102 s over RDP. Capture: lab `captures\retail-handling-20261016\trial\t06-on-1.*`.
- **The switch was not shown to work in that run:** flagpeek `acquired:false`, flags null, arcade_bit 0; no `retail-handling: on`
  line in this run's proxy log (the lines grepped came from earlier rh1 boots). The twin's STRLKUP.DLL is back to 33211f11
  (read back by the verifier, and again by the synthesizer 2026-10-17).
- **Audio rule broken:** `tools\mute.ps1` threw `Element not found (0x80070490)` at 04:14Z, so mute was neither set nor read back,
  and the game was booted two minutes later in an RDP-active session. `run-rh.ps1` takes the lock but has no mute check and no RDP
  refusal (`with-console.ps1` has both). Fix before reuse: route `run-rh.ps1` through `with-console.ps1`.
- One misdirected coordination message to an emu agent (af376c1c), retracted.

## Not done

- No off vs on yaw measurement (12 / 18 / 25 m/s), no read-back of the switch from a running game in this lane's run, no launcher.
  The console lane's s.7 reports an arcade-bit read-back of 158/158 frames (n 1, RDP window); not re-verified here.

## Next

- Optional opt-in retail front-wheel-pull patch (file 0x3c341 `74 20` -> `eb 20`, only for a car with both front wheels damaged).
- Emu A/B: Gold with Arcade Phys. on, n >= 2, to confirm K drops to about 23.4 (headless, agent work).
- Owner test 44's `TEST-p166-retail-handling.bat` refuses to start until proxy 0406e909 is installed; an agent should install it
  on the twin with a read-back (or James uses the Options toggle route, item 45).
