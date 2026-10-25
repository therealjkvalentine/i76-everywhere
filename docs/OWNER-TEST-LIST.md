# Owner to-do list

Only open items. Done items are deleted, not ticked. History of notes and answers up to 2026-10-25: `docs/records/OWNER-NOTES-ARCHIVE-2026-10-25.md`. Work items live on the GitHub board; this file is what needs the owner's hands or ruling.

## Test (desktop, main Gold: proxy 5d6f9828, launcher 07244591)
- [ ] Alt-Tab out of a mission and back: FFB still on, no crash
- [ ] Restart the level, then move to the next mission: no crash
- [ ] Terrain at 2300 m with the morph: still "more movement than you'd like", or settled?
- [ ] FFB: does our interposer feel better than the game's own? (`play-i76.log` says which ran)
- [ ] Ctrl+Alt+H cycles head look analog / digital / off; glance keys override it

## Test (Mac)
- [ ] Mac Kit as a user: download the Mac Kit zip from the v0.8.0 release, run `BUILD-I76-APPS.command` (right-click > Open), feed it the GOG offline installer; note every dialog and prompt
- [ ] Nitro on the Macs now uncapped (24 steps/s): does it feel right?

## Test (multiplayer)
- [ ] Gold co-op with the family Macs: AI respawn, joiner behind the host, enemy scaling, Esc cancel, host restart, host death, names (already reported from today: AI damage not visible, 0.5-1 s position gaps, joiner's pause menu ignores arrow keys; all under investigation)
- [ ] Nitro "[AI Drop-In]" arena, PC + a Mac

## Test (Deck)
- [ ] Switch on a paired Xbox controller (the rumble lane needs it), then the 9-row "felt it" checklist in `docs/records/DECK-2026-10-25.md`

## Captures for the launch video (1080p windowed; `tools\launch-video\RECORD-TAKE.bat` from Win+R)
- [ ] combat 90 s: `RECORD-TAKE.bat combat 90 0,0,1920,1080` (game at 1280x720 `--panel`, FFB page on the right)
- [ ] head look 45 s with the opentrack octopus window beside the game: `RECORD-TAKE.bat headlook 45 0,0,1920,1080`
- [ ] jump 40 s: `RECORD-TAKE.bat jump 40` (optionally once on PLAY-VANILLA.bat for the before side)

## Decide
- [ ] Internet play relay host: this desktop (router forward of one UDP port + firewall allow) or a small VPS; then the laptop-on-hotspot NAT test
- [ ] Ask Debacle about the Nitro RepoTown / Intercept conversions (their readmes say "without the author's consent"; the kit downloads them, it does not rehost)
- [ ] Deck Kit v0.1.0: publish beside the Patch Kit, or hold until a Deck user tests it
- [ ] Defender exclusion for the game and lab folders (steadies fps measurements; admin; optional)
- [ ] M4 Max Mac at 13 GB free: want a read-only breakdown of its Library / Downloads, or caches cleared with its owner's say-so?
- [ ] opentrack: the one untried rung is the small model (`head-pose-0.4-small-int8.onnx`)

## Waiting on lanes, nothing to do yet
Family rollout of the next proxy (FOV keys, cutscene skip fix, FFB off, co-op speed match, host-stall cap, AI names) to PC + Macs + Deck after the gate; history rewrite (you will be told before the force-push); hype video v2.
