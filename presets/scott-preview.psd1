# scott-preview (tester build 2026-10-23, tools\package-scott.ps1 / PLAY-PREVIEW.bat): a verbatim copy of the owner's trial preset
# lab exp-polish2\Interstate 76\presets\OWNER-2300-FOG.psd1 as it stood on 2026-10-23 (only the Name below differs): the promotion-19
# candidate (tick 41.667, every non-graphics fix) + the graphics work under test - terrain morph (big-tile blend, shade fade), one-pass sky,
# the mirror's .m16 textures at 1000 m, far clip / roads / bushes 2300 m, Glide fog from 0.7 x far, I76_JUMP_NOSE 0.91. EXPERIMENTAL: not
# gated, not promoted; the owner's eyes decide. The aspect lines are rewritten per display by tools\Make-Wide-Conf.ps1 at install time.

# rebase-x5 (rebaseline lane 2026-10-21, lab tools\rebaseline\rungs.py; i76-everywhere docs\records\REBASELINE-2026-10-21.md):
# X5 = R07 + far clip / roads / bushes 2000 m (the planned ship value; owner soak) (main, owner's console A/B 2026-10-21 evening)
# Generated from this folder's presets\tick19-42.psd1 (md5 f7e589ef0759299fc0333a78aa7a2eb6, the promotion-19 candidate: tick 41.667 and every
# non-graphics fix as the candidate has them). Graphics keys removed (= the game's stock value): I76_FAR_CLIP, I76_ROAD_DIST, I76_CLUTTER_DIST, I76_CLUTTER_FADE, I76_TERRAIN_LOD, I76_TERRAIN_LOD_A, I76_TERRAIN_LOD_B, I76_TERRAIN_HYST, I76_TERRAIN_FREEZE, I76_TERRAIN_TEX, I76_OBJECT_LOD, I76_SHADOW_DIST, I76_ROAD_TEX, I76_MIRROR_FAR.
# Then this rung's keys, each with the reason it exists. Launched by PLAY-R07.bat. Lab ladder only: not a release preset.
@{
    Name        = 'scott-preview'
    Summary     = 'ALL + Glide fog to the horizon colour over the last quarter of the 2300 m (from 1725 m); sky, cockpit, HUD, mirror untouched'
    Verified    = '[lab 2026-10-23] far-edge lane rung on OWNER-2300-ALL; NOT promoted'
    Env         = @{
        I76_HIRES_CLOCK     = '1'
        I76_MUSIC_RETAIL    = '1'   # the owner's music ruling (OWNER-TEST-LIST item 49, test 05 PASS): retail 1.0 music rules ...
        I76_MUSIC_RESUME    = '1'   # ... except resume: the music continues where it stopped (Replay, shell entry)
        I76_COOP_AI         = '1'   # LAN (as PLAY-LAN.bat): the host runs the mission cars and mirrors them to joiners; computer cars in the 15 stock arenas (AI-MELEE-RESPAWN-2026-10-20; ai_hs*.lvl out); inert in single player (32a5b04)
        I76_COOP_CHAIN      = '1'   # LAN: co-op scene won -> the next scene for everybody; joiners respawn; a lost scenario reloads
        I76_MP_MENU         = '1'   # LAN: MULTI MELEE HOST / JOIN go straight to IPX (IPXWrapper DLLs beside i76.exe)
        I76_SIM_TICK_MS     = '41.667'   # 41.667 = 1000/24 ms = 24 ticks/s, the 1997 car step: the per-frame counters need no correction; whole sim (controls, collisions, cars, AI / scripts, weapons) once per tick, drawn interpolated at the display rate
        I76_SIM_TICK_INPUT  = '1'   # a key press runs the next tick at once (borrowed from the next one: same tick length, same rate)
        # removed (per-frame timing, replaced by the tick): I76_FIXED_STEP, I76_FRAMERATE_FIXES, I76_ENGINE_DT_FIX, I76_RENDER_INTERP, I76_INPUT_LATCH, I76_AI_BACKAWAY_GRID, I76_COLL_DEDUPE, I76_COLL_WINDOW, I76_COLL_WINDOW_WHEN, I76_AI_ROLL_HOLD
        I76_FIX_HEALTH_PCT  = '1'
        I76_FIX_LABEL_TABLE = '1'
        I76_CAM_GROUND_FIX  = '1'   # terrain kept when the eye dips under the ground (stock skips ALL terrain that frame = the terrain-to-sky flash; lab RENDER-FREEZE-2026-10-04.md s.9)
        I76_TERRAIN_HULL_FIX = '1'   # the near ground no longer vanishes for a frame in cockpit view (footprint hull rebuilt; lab TERRAIN-DROPOUT-HILL-2026-10-12.md s.10-11)
        I76_ZGLIDE_TMUFIX   = '1'   # needs dgVoodoo [Glide] MemorySizeOfTMU 8192 (promotion 12): no ZGLIDE flush freezes, no 2 MB boundary rewind (lab RENDER-FREEZE-2026-10-04.md; gate + soak 2026-10-04)
        I76_GLIDE_REFRESH   = '120'
        I76_ASPECT          = '3440x1440'
        I76_CURSOR_MAP      = '1'     # the proxy maps the menu pointer through the window (dgVoodoo.wide.conf CaptureMouse = false)
        I76_CURSOR_MAP_U32X = 'exe'   # ... taking i76.exe's u32x slots; i76shell keeps u32x (its arrow in the garage / reminder OK popups)
        I76_U32X_SHELL_STRETCH = '1'  # u32x maps the shell where dgVoodoo draws it: 4:3 fit under stretched_ar (dgVoodoo.wide.conf since 2026-10-12), whole client under stretched
        I76_CURSOR_MAP_DGV  = 'aw'    # the driver's wide (16:10) menu with the pointer on the pencil: dgVoodoo's cursor slots and u32x's shell map follow dgVoodoo.wide.conf dccd379a's picture (proxy 1ca6ba0+, CURSOR-FIX-ON-18 s.6; PLAY-TICK*.bat copy dgVoodoo.wide.conf)
        I76_U32X_MENU_ASPECT = '3440:1440'   # the mouse DLL maps the in-mission Esc menu to the full panel (verified: Exit answers where drawn)
        # no data yet (2026-10-03: the ram test could not stage its rams; no AI car entered the roll behaviour):
        # count only, behave as played on 2026-10-02
        I76_BREAKABLE_BOX   = '4'   # bar as a box (=1) + sign posts fall at the first ram, when the drawn car reaches them (sign-post sweep + render-interp timing; lab SIGN-FIX-3-2026-10-12.md)
        I76_SIGN_SOUND_RESTART = '1'   # a new sign / barricade hit stops the vnvco3 still playing on the car and starts it again (proxy polish.c; MENU-SOUND-POLISH-2026-10-20 item C)
        I76_FADE_NO_FLIP    = '1'   # the palette fade on leaving a mission / the game presents nothing under Glide: no two-frame flicker (polish.c; item B)
        # ---- rebaseline R07 graphics (5 keys)
        I76_FAR_CLIP        = '2300'   # stock 600 m (the missions set it). 1800 since promotion 2 (best-wide, PLAY.bat); RC-DRAW-FPS s.3: the T05 barn (1747 m) and the map edge from the hill top need it
        I76_ROAD_DIST       = '2300'   # stock 450 m whatever the far clip. 1800 since promotion 16 (owner-verified set 2026-10-12): roads drawn to the far clip
        I76_CLUTTER_DIST    = '2300'   # stock 120 m (bushes only within view z 120 m). 1800 since promotion 17 (owner chose the dense variant 2026-10-17)
        I76_CLUTTER_FADE    = '300'   # ... full density to 300 m, then thinned as (300 / d)^2 per bush (promotion 17, TEST-next-dense)
        I76_TERRAIN_LOD     = '24'   # promotion 18's terrain: split distance x24 AND height-error threshold / 24 (promotion 17: 8 -> 24; x8 since promotion 2)
        # ---- daily-driver detail keys (PLAY.bat = best-wide; missing from every trial preset until 2026-10-23 - the owner's "object detail is near")
        I76_TERRAIN_TEX     = '8'    # terrain texture level distance x8 (daily driver)
        I76_OBJECT_LOD      = '8'    # object detail distance x8 (daily driver)
        I76_SHADOW_DIST     = '4'    # shadow distance x4 (daily driver)
        I76_ROAD_TEX        = '8'    # road texture distance x8 (daily driver)
        # ---- owner A/B 2026-10-22 (main): built 449237d6 = i76-everywhere 05c5681
        I76_TERRAIN_MORPH   = '0.25'   # blend split vertices in over 25 % of their ring
        I76_TERRAIN_MORPH_STATELESS = '1'   # no tables (terrainmorph.c)
        I76_SKY_MIRROR      = '0'   # owner's pick 2026-10-23: one-pass sky (skymirror.c)
        I76_TERRAIN_MORPH_SHADE = '3'   # the shade fades over 3x the height band (terrainmorph.c 7dd568c)
        I76_TERRAIN_MORPH_BIG = '1'   # the 64+ sample tiles blended, height and shade (owner saw no sliding, 2026-10-23)
        # ---- mirror (mirror lane 2026-10-23, MIRROR-DETAIL-2026-10-23.md; cost 1.2 % at t01, n 2)
        I76_MIRROR_FAR      = '1000'   # the mirror camera's far clip, stock 100 m (owner 2026-10-23: 800-1200 m is plenty; was 2300)
        I76_MIRROR_LOD      = '1'      # the mirror's terrain pass splits at the STOCK constants (x1), not the main view's x24
        I76_MIRROR_EVERY    = '2'      # the mirror redraws every 2nd frame (60/s at 120 fps)
        I76_MIRROR_M16      = '1'      # mirror lane 2026-10-23 (5006d8c): the mirror's terrain samples the main view's .m16 art (quantised into the display palette, sky 3x3-blurred), not the 8-bit build's peach low-contrast drawings; 0.3 % at the x8 load, n 2
        I76_MIRROR_M16_SKY  = '0'      # the sky stays the stock 8-bit cloud art (owner 2026-10-23: 'I actually prefer the original mirror cloud texture ... we can imagine the mirror has a tint'); =1 would give it the .m16 cloud art
        I76_MIRROR_TEX      = '2'      # ... and takes the texture level a 1280 px wide view at x1 would (absolute; 1 and 8 looked the same, 2 leaves 10 % of its leaves on the 16 px tile; 5006d8c)
        I76_MIRROR_PAL      = '1'      # ... pixels remapped 8-bit-build palette -> hardware-build palette before the upload (near-identity on stock missions)
        # ---- jump (jump-pitch lane 2026-10-23, TICK-FINISH s.22.6)
        I76_JUMP_NOSE       = '0.91'   # owner ruling 2026-10-23, 9 % less: the nose-down pitch rate the car carries off a lip x 0.91 once at take-off (not the kick, the path or the ground); needs proxy e02d64a+
        # ---- far edge (far-edge lane 2026-10-23, FAR-EDGE-FADE-2026-10-23.md; proxy faredge.c, needs proxy 9496235+)
        I76_GLIDE_FOG               = '0.75,hzd'   # owner 2026-10-23: 0.85 too thin, 0.7 liked, then 'half as long' -> 0.75 (clear to 1725 m, full at 2300 m); colour = the horizon strips' base rows, never the sky
        # cost: 0 fps within noise (FAR-EDGE-FADE-2026-10-23.md s.3, s.6)
    }
}
