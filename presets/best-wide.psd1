# best-wide: the 2026-10-03 daily-driver candidate. best-120 + the exp-detail-8 set + I76_ASPECT (Hor+ widescreen).
# Needs the widescreen dgVoodoo conf (dgVoodoo.wide.conf: [Glide] Resolution 5160x2160, ScalingMode stretched);
# the daily driver's PLAY.bat copies it in before launching. I76_ASPECT is this panel's shape (3440x1440); for another
# display set it to that display's width x height (tools\Make-Wide-Conf.ps1 writes both the conf and this file's
# values for one game folder; setup-windows.ps1 -Preset best-wide runs it). Menus, cutscenes and 2D text are
# stretched sideways (known cost).
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
        I76_GLIDE_REFRESH   = '120'
        I76_ASPECT          = '3440x1440'
        I76_U32X_MENU_ASPECT = '3440:1440'   # the mouse DLL maps the in-mission Esc menu to the full panel (verified: Exit answers where drawn)
        I76_TERRAIN_LOD     = '8'
        I76_TERRAIN_TEX     = '8'
        I76_OBJECT_LOD      = '8'
        I76_SHADOW_DIST     = '4'
        I76_ROAD_TEX        = '8'
        # I76_ROAD_DIST removed 2026-10-03: 1800 m overflows the depth-bucket node pool (exe+0x9051B); t11 crashed at boot 2/2 (lab docs/SOAK-BEST-WIDE-2026-10-03.md). Stock 450 m.
        I76_CLUTTER_DIST    = '300'   # ground clutter (bushes) to 300 m view depth; see music-fix/README.md
        I76_MIRROR_FAR      = '300'   # rear-view mirror sees 300 m instead of 100 m
        # no data yet (2026-10-03: the ram test could not stage its rams; no AI car entered the roll behaviour):
        # count only, behave as played on 2026-10-02
        I76_COLL_DEDUPE     = '0'
        I76_AI_ROLL_HOLD    = '0'
    }
}
