# exp-terrain-8: best-120 plus I76_TERRAIN_LOD=8 (music-fix/README.md). EXPERIMENT for the lab twin, not the daily driver:
# more terrain vertices per frame brings the 32,767-vertex crash ceiling closer; needs a soak on wide vistas first.
@{
    Name        = 'exp-terrain-8'
    Summary     = 'EXPERIMENT: best-120 + terrain detail x8 (ground refines farther out)'
    Verified    = '[experiment] runs at 120 fps on t01 in the lab; owner judged x8 better by eye 2026-10-03; not soaked with the far clip'
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
        I76_TERRAIN_LOD     = '8'
        # no data yet (2026-10-03: the ram test could not stage its rams; no AI car entered the roll behaviour):
        # count only, behave as played on 2026-10-02
        I76_COLL_DEDUPE     = '0'
        I76_AI_ROLL_HOLD    = '0'
    }
}
