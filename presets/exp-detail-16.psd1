# exp-detail-16: exp-terrain-16 plus I76_TERRAIN_TEX=8 (sharp ground textures 8x farther) and I76_OBJECT_LOD=8
# (objects and vehicles keep their detailed mesh 8x farther). EXPERIMENT for the lab twin (music-fix/README.md).
@{
    Name        = 'exp-detail-16'
    Summary     = 'EXPERIMENT: best-120 + terrain shape x16 + terrain textures x8 + object detail x8'
    Verified    = '[experiment] 120 fps on t01 in the lab twin, one 6 s run; not soaked; not played'
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
        I76_TERRAIN_LOD     = '16'
        I76_TERRAIN_TEX     = '8'
        I76_OBJECT_LOD      = '8'
        # no data yet (2026-10-03: the ram test could not stage its rams; no AI car entered the roll behaviour):
        # count only, behave as played on 2026-10-02
        I76_COLL_DEDUPE     = '0'
        I76_AI_ROLL_HOLD    = '0'
    }
}
