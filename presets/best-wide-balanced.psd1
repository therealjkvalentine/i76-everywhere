# best-wide-balanced (2026-10-05): best-wide with the far clip at 1200 m instead of 1800 m, launched by PLAY-balanced.bat as an
# EXTRA option (PLAY.bat stays best-wide). Per-switch cost on t04 open desert (lab autotest\runs\twin-sync-20261005\COST.md):
# in the cockpit no switch costs anything measurable (120 fps paced, CPU ~8.7 ms/frame, GPU 3D ~33 % in every condition);
# only the binoculars run below 120, and there the far clip is the one switch with a clear effect (terrain vertices 15.8k
# -> 4.3k, 79 -> 99 fps). Halving terrain LOD / terrain tex / object LOD / road tex / shadows / clutter changed nothing
# beyond run-to-run spread, so they stay at best-wide's values.
# best-wide: the 2026-10-03 daily-driver candidate. best-120 + the exp-detail-8 set + I76_ASPECT (Hor+ widescreen).
# Needs the widescreen dgVoodoo conf (dgVoodoo.wide.conf: [Glide] Resolution 5160x2160, ScalingMode stretched);
# the daily driver's PLAY.bat copies it in before launching. I76_ASPECT is this panel's shape (3440x1440); for another
# display set it to that display's width x height (tools\Make-Wide-Conf.ps1 writes both the conf and this file's
# values for one game folder; setup-windows.ps1 -Preset best-wide runs it). Menus, cutscenes and 2D text are
# stretched sideways (known cost).
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
        I76_ZGLIDE_TMUFIX   = '1'   # needs dgVoodoo [Glide] MemorySizeOfTMU 8192 (promotion 12): no ZGLIDE flush freezes, no 2 MB boundary rewind (lab RENDER-FREEZE-2026-10-04.md; gate + soak 2026-10-04)
        I76_INPUT_LATCH     = '1'   # ignition (I) / lights (H) survive frames without a physics step: 50/50 each at 120 fps vs 13/50 and 7/50 without (lab 2026-10-04, consolidated proxy 89a97d25)
        I76_AI_BACKAWAY_GRID = '1'  # AI back_away stuck test on the 20 Hz grid, not 4 rendered frames: T12 opening cut 6.6 s 5/5 + 3/3 as vanilla 7/7 (was 0/5); route gate rows 2-4 PLAY.bat + PLAY-16x10.bat 14/15 each, only D (lab 2026-10-05, proxy 89a97d25)
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
