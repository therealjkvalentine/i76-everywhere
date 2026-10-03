# framegen-90: the best-120 switch set with the game at 90 fps, meant to run under Lossless Scaling frame generation
# x2 for 180 fps on a ~180 Hz panel (2026-10-03, on the owner's question "can we use frame interpolation to try 180").
#
# Why 90: no renderer tested gets the game itself past 120 (docs/RENDERER-ALTERNATIVES.md section 11), and fixed x2 on
# 120 gives 240, more than the panel shows. Two routes to 180:
#   a) this preset (real 90) + LSFG fixed x2            -> every second frame is generated
#   b) best-120 (real 120) + LSFG 3 ADAPTIVE, target 179 -> one frame in three is generated (needs LS 3.1+; 3.2.2 is bundled)
# Route b keeps more real frames and is the one to try first; this preset exists for route a.
# I76_GLIDE_REFRESH=90 alone was measured working (FPS-120.md); with frame generation NOTHING is tested.
# Generated frames add latency and can smear the cockpit/HUD; judge by eye.
@{
    Name        = 'framegen-90'
    Summary     = 'best-120 at 90 fps, for Lossless Scaling x2 = 180 on a 180 Hz panel (UNTESTED)'
    Verified    = '[untested]: 90 Hz refresh measured alone 2026-10-02; never run with frame generation'
    Env         = @{
        I76_HIRES_CLOCK     = '1'
        I76_FIXED_STEP      = '24'
        I76_FRAMERATE_FIXES = '1'
        I76_ENGINE_DT_FIX   = '1'
        I76_RENDER_INTERP   = '1'
        I76_FIX_HEALTH_PCT  = '1'
        I76_FIX_LABEL_TABLE = '1'
        I76_FAR_CLIP        = '1800'
        I76_GLIDE_REFRESH   = '90'
        # no data yet (2026-10-03: the ram test could not stage its rams; no AI car entered the roll behaviour):
        # count only, behave as played on 2026-10-02
        I76_COLL_DEDUPE     = '0'
        I76_AI_ROLL_HOLD    = '0'
    }
}
