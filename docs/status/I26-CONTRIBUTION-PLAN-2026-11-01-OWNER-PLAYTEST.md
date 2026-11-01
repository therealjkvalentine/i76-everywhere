# I26 0.11.0 owner playtest, 2026-11-01 (Apple Silicon Mac, re-signed app)

Companion to [I26-CONTRIBUTION-PLAN-2026-10-31.md](I26-CONTRIBUTION-PLAN-2026-10-31.md). What the developer noticed
playing I26, sorted by where it goes. "Community fix" = candidate for an early PR (reported or report-shaped, one
root cause, provable); "later list" = the developer's own wish list, not for an early PR.

## Works well
- The game chooser appears; menus work well with the mouse; bookmark and salvage screens work beautifully.
- Music changes track and keeps playing on the menu.

## Community-fix candidates (to verify, then rank)
| # | observation | first lead | status |
|---|---|---|---|
| 1 | suspension bounce too fast / frenetic, not floaty enough; handling "for sure not the same" | the suspension filter runs per physics substep (pole 0.7, 15-call period); I26's 20 Hz = frames of 102/103 x 1/2048 s, the 103s split in two (substeps = trunc(dt x 20) + 1, VehicleStep.cs:25) = 28 substeps/s; the developer's kit (41.667 ms) and GOG on Windows 10 (46.9 / 2 x 31.25 ms) = 24/s, so the bounce runs ~17 % faster. Quick check: Simulation Rate 25 (82/2048 s, one substep, 25/s) | owner to try 25 Hz; side-by-side lane |
| 2 | Taurus's radio lines cut off by the map view or a cut-scene skip in scene 1 (scene 2 resumed after the map); same with Skeeter in the menu | CB queue vs pause / map / skip handling; note P16's own script calls killCB on a skip | investigation lane |
| 3 | Taurus gets far ahead before the scene-2 cut-scene; in the race he is too fast and leaves the road in turns | AI path following + car physics + substep rate (#1) | side-by-side lane (time-synced trajectories) |
| 4 | rockets and bullets seem too fast: the lead needed on a target is much less | round speeds / per-tick integration vs the spec (the weapons audit found the rocket speed ease matching) | side-by-side lane: measure flight times |
| 5 | 1997-look tracers too wide | tracer quad width vs the original renderer (renderer.md kind 8) | investigation lane |
| 6 | save bookmark -> Cancel goes to a game menu instead of back to the repair form | shell flow vs shell/SCREENS.md | investigation lane |
| 7 | the microphone permission is asked at launch, before the player opens anything (macOS) | the CB voice's audio input opened at start; ask only when CB voice is used | Mac report (with the signing issue) |
| 8 | clouds maybe too fast | sky scroll per tick in the 1997 look (deviations.md); compare with the original per frame | investigation lane |
| 9 | the target health bar is too thin and wide | HUD bracket readout vs the original's | later, verify first |

## Later list (the developer's taste; not early PRs)
- the hood is distractingly shiny in the modern look: options to matte it;
- modern-look MG tracers do not look like tracers;
- the original's special mouse cursors are not used (mid-list).

## Requests
- Port the developer's GOG saves into I26 (or at least one per mission): save-port lane.
- Comparisons with the developer's kit in the 1997 look, so the pictures match almost exactly.
