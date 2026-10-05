# best-120: what the owner played as TEST-FRAMERATE option 6 on 2026-10-02 ("120hz works great"), minus telemetry.
# smooth-60-bugfixes + 1800 m draw distance + the 120 Hz Glide refresh override.
#
#   I76_HIRES_CLOCK=1       exact frame dt from QPC
#   I76_FIXED_STEP=24       physics always in 41.67 ms slices (stock's mean step): jumps and body roll as tuned
#   I76_FRAMERATE_FIXES=1   per-frame starts held to the 20 Hz grid (36 sites + hazard contact, radar turn, WMISS,
#                           AI skid/horn rolls added 2026-10-03; hazard contact measured: oil slick 20 contacts/s
#                           at 20 / 60 / 120 fps, 9 of 10 runs, one staging miss; WMISS 20/s at 20 / 60 / 120, 2 runs each;
#                           radar turn not measured)
#   I76_ENGINE_DT_FIX=1     engine model's 0.05 s substep
#   I76_RENDER_INTERP=1     draws between physics poses (what makes 60/120 smooth)
#   I76_FIX_HEALTH_PCT=1    target health bar: min(28 + 72 x side, 100 x core) (verified live 2026-10-02)
#   I76_FIX_LABEL_TABLE=1   label table growth fix (only huge custom missions reach it)
#   I76_FAR_CLIP=1800       draw distance 1800 m (soaked on t01-t17 with hood view + binoculars, no crash)
#   I76_GLIDE_REFRESH=120   ZGLIDE asks dgVoodoo for 120 Hz instead of 60 (120 is the ceiling of this route)
#
# Needs a dgVoodoo.conf that dgVoodoo actually ACCEPTS (lab docs/DGVOODOO-CONF-REJECTED.md): fake fullscreen,
# [Glide] Resolution 3840x2880 + Antialiasing 4x is the measured pick (120.1 fps, 28-37 % of a GTX 1080 Ti).
# Status: [console-verified 2026-10-02, sandbox] by the owner for the switch set at 120 (option 6);
#         [measured, sandbox] 120.0 fps through TRIP -> bookmark -> garage -> DONE; not multiplayer-tested.
@{
    Name        = 'best-120'
    Summary     = 'Smooth 120 fps + bug fixes + 1800 m draw distance (the 2026-10-02 option 6 set, no telemetry)'
    Verified    = '[console-verified 2026-10-02, sandbox]; [measured, sandbox] via the trip menus'
    Env         = @{
        I76_HIRES_CLOCK     = '1'
        I76_FIXED_STEP      = '24'
        I76_FRAMERATE_FIXES = '1'
        I76_ENGINE_DT_FIX   = '1'
        I76_RENDER_INTERP   = '1'
        I76_FIX_HEALTH_PCT  = '1'
        I76_FIX_LABEL_TABLE = '1'
        I76_FAR_CLIP        = '1800'
        I76_ZGLIDE_TMUFIX   = '1'   # needs dgVoodoo [Glide] MemorySizeOfTMU 8192 (promotion 12): no ZGLIDE flush freezes, no 2 MB boundary rewind (lab RENDER-FREEZE-2026-10-04.md; gate + soak 2026-10-04)
        I76_INPUT_LATCH     = '1'   # ignition (I) / lights (H) survive frames without a physics step: 50/50 each at 120 fps vs 13/50 and 7/50 without (lab 2026-10-04, consolidated proxy 89a97d25)
        I76_AI_BACKAWAY_GRID = '1'  # AI back_away stuck test on the 20 Hz grid, not 4 rendered frames: T12 opening cut 6.6 s 5/5 + 3/3 as vanilla 7/7 (was 0/5); route gate rows 2-4 PLAY.bat + PLAY-16x10.bat 14/15 each, only D (lab 2026-10-05, proxy 89a97d25)
        I76_GLIDE_REFRESH   = '120'
        # no data yet (2026-10-03: the ram test could not stage its rams; no AI car entered the roll behaviour):
        # count only, behave as played on 2026-10-02
        I76_COLL_DEDUPE     = '0'
        I76_AI_ROLL_HOLD    = '0'
    }
}
