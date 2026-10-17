# best-wide: the 2026-10-03 daily-driver candidate. best-120 + the exp-detail-8 set + I76_ASPECT (Hor+ widescreen).
# Needs the widescreen dgVoodoo conf (dgVoodoo.wide.conf: [Glide] Resolution 6880x2880 + 4x, ScalingMode stretched_ar = 2x supersampled, 2026-10-12);
# the daily driver's PLAY.bat copies it in before launching. I76_ASPECT is this panel's shape (3440x1440); for another
# display set it to that display's width x height (tools\Make-Wide-Conf.ps1 writes both the conf and this file's
# values for one game folder; setup-windows.ps1 -Preset best-wide runs it). Since 2026-10-12 the 640x480 menus, garage and movies
# are shown 4:3 with side bars (stretched_ar), not stretched sideways.
@{
    Name        = 'best-wide'
    Summary     = 'Widescreen 21:9 (Hor+) + best-120 + detail farther out: terrain x8, textures x8, objects x8, bushes 300 m, shadows 200 m, mirror 300 m'
    Verified    = '[owner-played 2026-10-03, sandbox] widescreen full-width cockpit approved; detail set measured 120 fps on t01; gate on the lab twin before the daily driver'
    Env         = @{
        I76_HIRES_CLOCK     = '1'
        I76_FIXED_STEP      = '24'
        I76_FRAMERATE_FIXES = '1'
        I76_ENGINE_DT_FIX   = '1'
        I76_RENDER_INTERP   = '1'
        I76_FIX_HEALTH_PCT  = '1'
        I76_FIX_LABEL_TABLE = '1'
        I76_FAR_CLIP        = '1800'
        I76_ROAD_DIST       = '1800'   # road segments drawn to 1800 m like the far clip (stock 450; owner 2026-10-12: 'road at 1800 seems to run fine'; the 2026-10-03 t11 crash was the node pool, fixed by I76_ROAD_POOL since promotion 8)
        I76_CAM_GROUND_FIX  = '1'   # terrain kept when the eye dips under the ground (stock skips ALL terrain that frame = the terrain-to-sky flash; lab RENDER-FREEZE-2026-10-04.md s.9)
        I76_TERRAIN_HULL_FIX = '1'   # the near ground no longer vanishes for a frame in cockpit view (footprint hull rebuilt; lab TERRAIN-DROPOUT-HILL-2026-10-12.md s.10-11)
        I76_AI_BACKAWAY_GRID = '1'   # AI back_away stuck test on the 20 Hz grid, not 4 rendered frames: T12 opening 5/5 as vanilla (lab 2026-10-04 milk-truck doc s7-9)
        I76_INPUT_LATCH     = '1'   # ignition (I) / lights (H) presses survive frames without a physics step (lab 2026-10-04: 50/50 vs 13/50)
        I76_ZGLIDE_TMUFIX   = '1'   # with dgVoodoo MemorySizeOfTMU 8192: no ZGLIDE flush freezes, no 2 MB boundary rewind (lab RENDER-FREEZE-2026-10-04.md)
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
        I76_CLUTTER_DIST    = '1800'   # bushes drawn to 1800 m (was 300 m; owner 2026-10-12: 'brush ... as far as the road draw distance')
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
