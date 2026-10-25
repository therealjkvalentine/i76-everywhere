# dgVoodoo DeframerSize and the map / notepad corner remnant (2026-10-25)

Report (an outside tester, v0.7.3 preview launcher): after closing the in-game map or notepad a remnant stays visible in a corner;
the tester sets the deframer to 3 and adjusts the resolution a bit.

## What the option is
dgVoodoo 2.87.3 `[GeneralExt] DeframerSize` (the CPL's "Deframer size"; text read from dgVoodooCpl.exe): "When resolution is forced to
other than the app default then a black frame is drawn around the output image coming from a wrapped API to remove scaling artifacts
(max 16 pixels, 0 = disable)". It is a pixel thickness 0-16, not a 0-3 mode. Our confs do not carry the key (default 0). It does not
change the window or render size; it paints a black border over the picture's edge.

## Reproduction (laptop, bench clean2 Gold kit 0.7.3, 1920x1080, lock held, PLAY-PREVIEW-T05 / PLAY-T05, no FFB, cutscenes skipped)
Scripted M (map) and N (notepad) open + close (scancode keys, `captures/deframer/`). Frames after closing: no map/notepad remnant in
any corner (edge/corner patches checked for white paper pixels: 0 % in all four corners, 2x supersample; PLAY-T05 and 1x also clean).
NOT reproduced; n 1 per launcher, one display, no wheel. The tester's display, scale or window size may differ (not available here).

## DeframerSize 3 side effects (n 1 each, Preview, 2x)
Picture size/aspect unchanged (window 3840x2160 under 1920x1080 desktop); only a ~3 px black border at the left edge (1 px baseline).
So "adjust the resolution" is not needed for the border, but a 3 px frame crops 3 px of picture per side.

## Decision
No change shipped: nothing to verify a fix against. Suggestion for the tester: try `DeframerSize = 3` under `[GeneralExt]` in
dgVoodoo.conf (and dgVoodoo.wide.conf) and report the display size and render scale; ask for a screenshot of the remnant.
Test-harness note: the lab's fix-step SendKeys did not reach the game's M/N keys; scancode keybd_event (fix-step-nolock.ps1) did.
