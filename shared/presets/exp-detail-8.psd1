# exp-detail-8: exp-terrain-8 plus I76_TERRAIN_TEX=8 (sharp ground textures 8x farther) and I76_OBJECT_LOD=8
# (objects and vehicles keep their detailed mesh 8x farther). EXPERIMENT for the lab twin (music-fix/README.md).
@{
    Name        = 'exp-detail-8'
    Summary     = 'EXPERIMENT: best-120 + terrain shape x8 + terrain textures x8 + object detail x8 + shadows 200 m + road textures 480 m + bushes to 300 m'
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
