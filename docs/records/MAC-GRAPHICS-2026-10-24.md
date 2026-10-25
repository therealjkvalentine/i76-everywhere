# Mac graphics keys 2026-10-24: which of the owner's PC render keys work under Wine + OpenGLide + DxWnd

Question (owner): "Any minor graphics improvements that would translate to the Macs?" Test lane, scripted, n 1 per group.
Machine: the owner's MacBook (the family Mac over ssh, 3456x2234 panel, unlocked, nobody at it). Times CDT, 2026-10-24 20:40-21:20.
Evidence: lab `captures\mac-graphics-20261024\` (g*.log = the Mac clone's mciproxy.log per group, gfxrun.sh / gfxall.sh = the scripts).

## Method

- Clone: `tools/mac-test-clone.sh make "I76 GFX LAB" "Interstate 76 Gold"` (APFS clone of the Gold app, own bundle id, null audio, movies skipped). The shipped
  `Interstate 76 Gold.app` was only read (STRLKUP 0ce90a90, pack keys in its prefix `[Environment]`, which the clone inherits: COOP_AI, COOP_CHAIN,
  FIXED_STEP 24, FRAMERATE_FIXES, RENDER_INTERP, FPS_CAP 120, FPS_LOG 5, ...). Not modified.
- Proxy in the clone: **53944fb2** (lab `builds\nitro-port-20261021\wmr-3ef108d\Strlkup.dll`); the old 0ce90a90 kept beside it as `STRLKUP-0ce90a90.dll`.
- Start: `open -n --env I76_MISSION=t05 --env I76_SKIP_MOVIES=1 --env <group keys> "I76 GFX LAB.app"`, 115 s per group, then stop. The mission loads about
  50 s after launch (10 proxy fps lines "no mission frames" = the load, not a cutscene; no key needed); fps = mean of the last 8 five-second proxy lines
  (`I76_FPS_LOG=5` from the pack's own env; the shm frame_stats was not used).
- Groups are cumulative: baseline / +sky+morph+smooth / +mirror / +clutter / +distance 2300 + detail x8 / +fog alpha.

## Result

| group | keys added | boots to t05 | each key logs (proxy says) | CRASH | fps (last 8 lines) | picture |
|---|---|---|---|---|---|---|
| g0 baseline | pack keys only | yes | 27/27 coop-ai sites | 0 | 59.7 (min 55.6) | none |
| g1 | SKY_MIRROR=0, TERRAIN_MORPH 0.25 + STATELESS + SHADE 3 + NEAR 100, SHADE_SMOOTH=1 | yes | morph "on, STATELESS ... no blend nearer than 100 m", shade-smooth "on", sky-mirror line | 0 | 61.8 (58.8) | none |
| g2 | MIRROR_FAR 1000, M16, LOD 1, EVERY 2, TEX 2, PAL 1, M16_SKY 0 | yes | mirror-far / -every / -detail / -tex / -m16 (terrain + roads quantised) / -pal / -lod all "on" | 0 | 62.9 (58.1) | none |
| g3 | CLUTTER_DENSITY 0.5, FADE 450, ALPHA_FADE 150 | yes | clutter-alpha "on" | 0 | 60.4 (57.2) | none |
| g4 | FAR_CLIP / ROAD_DIST / CLUTTER_DIST 2300, TERRAIN_LOD 24, TERRAIN_TEX / OBJECT_LOD / ROAD_TEX 8, SHADOW_DIST 4 | yes | all "on" (far-clip 6/6, clutter-dist 8/8, road-pool, terrain-lod 6/6, ...) | 0 | **13.2 (12.0)** | none |
| g5 | GLIDE_FOG 0.75,hzd + GLIDE_FOG_ALPHA 1 | yes | glide-fog "on", grFogMode / grFogColorValue / grFogTable / guFogTableIndexToW ok; alpha: grAlphaBlendFunction / grAlphaCombine / grChromakeyMode hooked in ZGLIDE | 0 | 13.4 (12.0) | none |

The proxy does not log "applied" / "NOT applied" for these keys; each logs its own "<name>: on ..." line. Every key above logged one. Whether the fog
alpha and the clutter alpha blend LOOK right needs eyes: **no pictures** (see below).

Bisect of g4 (on top of g3, one run each): distances only (FAR_CLIP / ROAD_DIST / CLUTTER_DIST 2300) 21.5 fps (min 20.5);
LOD / TEX / OBJECT / SHADOW / ROAD_TEX only 37.3 fps (min 29.1). So under Wine the 2300 m distances cost about 3x, the x8 detail about 1.6x, both about 4.5x.
(On the PC the same keys cost ~1 % at 120 fps.)

## Findings that need a ruling

1. **I76_SKY_MIRROR=0 stops two coop-ai patches on the Mac**: `patch: coop-ai: trigger/damage at 0x00401CFE has UNEXPECTED bytes` and `0x00401FDE`,
   `coop-ai: 25/27 ... sites repointed` (baseline 27/27). Reproduced by the key alone (14 s boots: SKY_MIRROR=0 -> 25/27; TERRAIN_MORPH group, SHADE_SMOOTH
   each 27/27; every cumulative group g1-g5 25/27). Those are the LAN AI/damage sites, so the key must not go into the shared pack until the clash is
   understood (the proxy's sky-mirror patch and the coop-ai patch both touch 0x401xxx; why the PC does not hit it is not known here: the PC lan folder
   runs cf4f81da and the key was not tried there).
2. **Distance and detail keys are not usable on the Macs**: 60 -> 13 fps at 2300 m / x8. Even the lighter half is 21 / 37 fps.
3. The Mac baseline runs ~60 fps (display / vsync bound; the pack's FPS_CAP 120 is not reached), so g1-g3 deltas (+2.1, +3.2, +0.7) are within the spread of
   the 5 s lines (min 55-59) and are read as "no cost", n 1, not as a gain.
4. Not run: the same-rate control run (n 1 per group), the fog alpha by eye, a LAN join with the keys on, 53944fb2 vs the pack's 0ce90a90 on the Mac Esc menu.

## Screenshots: none

`screencapture` fails over SSH on this Mac in every form tried (plain, `launchctl asuser`, from a Terminal.app script, after `caffeinate -u`):
"could not create image from display" (the display is online and the console unlocked, so this looks like the missing Screen Recording grant for
the SSH / Terminal parent; granting it is a click in System Settings on the Mac). The proxy has no whole-screen capture (its texcensus BMP dump only
runs after Glide flushes). Sending Esc by `osascript` (System Events) hung with no answer (an Accessibility permission wait; killed, a prompt may still
be on the laptop's screen). So the "does it look right" half of the question is open: needs the owner at the Mac, or the two permission grants.

## Recommendation (keys for the Macs' pack preset)

The pack preset is byte-identical across machines, so anything added lands on every Mac AND the PC lan folder at once.

- **Safe by this test (boot, mission, 0 CRASH, no fps cost, own "on" line):** `I76_TERRAIN_MORPH=0.25`, `I76_TERRAIN_MORPH_STATELESS=1`, `I76_TERRAIN_MORPH_SHADE=3`,
  `I76_TERRAIN_MORPH_NEAR=100`, `I76_SHADE_SMOOTH=1`, the mirror set (`MIRROR_FAR=1000`, `M16=1`, `M16_SKY=0`, `LOD=1`, `EVERY=2`, `TEX=2`, `PAL=1`),
  `I76_CLUTTER_DENSITY=0.5`, `CLUTTER_FADE=450`, `CLUTTER_ALPHA_FADE=150`. All need proxy 53944fb2, which the Macs and the PC lan folder do not run
  (0ce90a90 / cf4f81da): they do nothing on the old proxies, and moving the pack's proxy is the LAN-compatibility question RC-20261024 s.5 already
  keeps separate. Look at them once on the Mac before shipping (no pictures here).
- **Not yet:** `I76_SKY_MIRROR=0` (costs 2 coop-ai sites; escalate to the proxy owner), the 2300 m distance keys and the x8 detail keys (13-37 fps
  on the Mac; a Mac-sized value such as 1200-1500 m with TERRAIN_LOD 8 is a new test), `GLIDE_FOG` / `GLIDE_FOG_ALPHA` (hooks attach, appearance unseen).
- The clone `~/Applications/Sikarugir/I76 GFX LAB.app` stays on the laptop for the follow-ups (proxy 53944fb2, null audio); delete it when done.
