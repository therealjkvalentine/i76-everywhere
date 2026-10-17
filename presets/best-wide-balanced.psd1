# best-wide-balanced (2026-10-05): best-wide with the far clip at 1200 m instead of 1800 m, launched by PLAY-balanced.bat as an
# EXTRA option (PLAY.bat stays best-wide). Per-switch cost on t04 open desert (lab autotest\runs\twin-sync-20261005\COST.md):
# in the cockpit no switch costs anything measurable (120 fps paced, CPU ~8.7 ms/frame, GPU 3D ~33 % in every condition);
# only the binoculars run below 120, and there the far clip is the one switch with a clear effect (terrain vertices 15.8k
# -> 4.3k, 79 -> 99 fps). Halving terrain LOD / terrain tex / object LOD / road tex / shadows / clutter changed nothing
# beyond run-to-run spread, so they stay at best-wide's values.
# best-wide: the 2026-10-03 daily-driver candidate. best-120 + the exp-detail-8 set + I76_ASPECT (Hor+ widescreen).
# Needs the widescreen dgVoodoo conf (dgVoodoo.wide.conf: [Glide] Resolution 6880x2880 + 4x, ScalingMode stretched_ar = 2x supersampled, 2026-10-12);
# the daily driver's PLAY.bat copies it in before launching. I76_ASPECT is this panel's shape (3440x1440); for another
# display set it to that display's width x height (tools\Make-Wide-Conf.ps1 writes both the conf and this file's
# values for one game folder; setup-windows.ps1 -Preset best-wide runs it). Since 2026-10-12 the 640x480 menus, garage and movies
# are shown 4:3 with side bars (stretched_ar), not stretched sideways.
@{
    Name        = 'best-wide-balanced'
    Summary     = 'best-wide with draw distance 1200 m instead of 1800 m: binoculars ~99 fps instead of ~79, cockpit unchanged (120)'
    Verified    = '[lab 2026-10-05] t04 cost run n=3 base / n=1 valid far1200 binoculars; route gate on the twin before the driver'
    Env         = @{
        I76_HIRES_CLOCK     = '1'
        I76_FIXED_STEP      = '24'
        I76_FRAMERATE_FIXES = '1'
        I76_ENGINE_DT_FIX   = '1'
        I76_RENDER_INTERP   = '1'
        I76_FIX_HEALTH_PCT  = '1'
        I76_FIX_LABEL_TABLE = '1'
        I76_FAR_CLIP        = '1200'   # balanced: 1800 in best-wide
        I76_ROAD_DIST       = '1200'   # road segments drawn to the far clip (1200 here; stock 450; best-wide 1800)
        I76_CAM_GROUND_FIX  = '1'   # terrain kept when the eye dips under the ground (stock skips ALL terrain that frame = the terrain-to-sky flash; lab RENDER-FREEZE-2026-10-04.md s.9)
        I76_TERRAIN_HULL_FIX = '1'   # the near ground no longer vanishes for a frame in cockpit view (footprint hull rebuilt; lab TERRAIN-DROPOUT-HILL-2026-10-12.md s.10-11)
        I76_ZGLIDE_TMUFIX   = '1'   # needs dgVoodoo [Glide] MemorySizeOfTMU 8192 (promotion 12): no ZGLIDE flush freezes, no 2 MB boundary rewind (lab RENDER-FREEZE-2026-10-04.md; gate + soak 2026-10-04)
        I76_INPUT_LATCH     = '1'   # ignition (I) / lights (H) survive frames without a physics step: 50/50 each at 120 fps vs 13/50 and 7/50 without (lab 2026-10-04, consolidated proxy 89a97d25)
        I76_AI_BACKAWAY_GRID = '1'  # AI back_away stuck test on the 20 Hz grid, not 4 rendered frames: T12 opening cut 6.6 s 5/5 + 3/3 as vanilla 7/7 (was 0/5); route gate rows 2-4 PLAY.bat + PLAY-16x10.bat 14/15 each, only D (lab 2026-10-05, proxy 89a97d25)
        I76_GLIDE_REFRESH   = '120'
        I76_ASPECT          = '3440x1440'
        I76_CURSOR_MAP      = '1'     # the proxy maps the menu pointer through the window (dgVoodoo.wide.conf CaptureMouse = false)
        I76_CURSOR_MAP_U32X = 'exe'   # ... taking i76.exe's u32x slots; i76shell keeps u32x (its arrow in the garage / reminder OK popups)
        I76_U32X_SHELL_STRETCH = '1'  # u32x maps the shell where dgVoodoo draws it: 4:3 fit under stretched_ar (dgVoodoo.wide.conf since 2026-10-12), whole client under stretched
        I76_CURSOR_MAP_DGV  = '1'     # dgVoodoo draws its cursor where the pointer really is
        I76_U32X_MENU_ASPECT = '3440:1440'   # the mouse DLL maps the in-mission Esc menu to the full panel (verified: Exit answers where drawn)
        I76_TERRAIN_LOD     = '24'   # terrain detail split distance x24 (was x8; the split distance grows with the square root: x24 = about 1.7 x x8): distant mounds and ridges keep their shape; the vertex guard stops splits past 28,000 vertices a frame
        I76_TERRAIN_TEX     = '8'
        I76_OBJECT_LOD      = '8'
        I76_SHADOW_DIST     = '4'
        I76_ROAD_TEX        = '8'
        I76_CLUTTER_DIST    = '1200'   # bushes drawn to 1200 m (was 300 m; owner 2026-10-12: 'brush ... as far as the road draw distance')
        I76_CLUTTER_FADE    = '300'   # ... at full density to 300 m like before, then thinned as (300 / d)^2 per bush (owner 2026-10-17 chose this dense variant, TEST-next-dense, over fade 200); with terrain x24 the T05 hill-top view costs the same as the fade-200 / x32 variant, lab DRAW-DISTANCE-2026-10-12.md
        I76_MIRROR_FAR      = '300'   # rear-view mirror sees 300 m instead of 100 m
        # no data yet (2026-10-03: the ram test could not stage its rams; no AI car entered the roll behaviour):
        # count only, behave as played on 2026-10-02
        I76_COLL_DEDUPE     = '1'   # one impact = one sound / damage per physics step (collision G, lab COLL-TIMING-2026-10-12.md)
        I76_COLL_WINDOW     = '2'   # contacts accepted over the whole physics step: barricades and signs hit at 120 fps (control: about 1 in 3)
        I76_COLL_WINDOW_WHEN = 'stepframe'   # ... only on the frame whose step moves the car: no fly-off before the bumper gets there
        I76_BREAKABLE_BOX   = '4'   # bar as a box (=1) + sign posts fall at the first ram, when the drawn car reaches them (sign-post sweep + render-interp timing; lab SIGN-FIX-3-2026-10-12.md)
        I76_AI_ROLL_HOLD    = '0'
    }
}
