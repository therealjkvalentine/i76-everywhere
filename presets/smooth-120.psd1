#
# smooth-120 - smooth-60-bugfixes with the Glide window opened at 120 Hz (docs/FPS-120.md).
#
#   (everything in smooth-60-bugfixes.psd1, same values)
#   I76_GLIDE_REFRESH=120   ZGLIDE.DLL opens its window with grSstWinOpen(..., GR_REFRESH_60Hz, ...)
#                           and dgVoodoo paces windowed presents at the refresh the app asked for,
#                           whatever the panel, FPSLimit or a forced Resolution say (all measured
#                           60.0). The proxy repoints ZGLIDE's grSstWinOpen import at a wrapper
#                           that substitutes the code for this rate. Physics stays at 24 steps/s,
#                           so four frames in five draw an interpolated pose; input latency, AI and
#                           physics fidelity do not change (FPS-120.md "The short answer").
#                           Accepted values: 60 70 72 75 80 85 90 100 120; 0 = none.
#
# Verification: [measured, sandbox] 2026-10-02: 120 -> 120.0 fps on the proxy frame counter.
# Measured only - NOT console-played, NOT A/B'd for feel, and the display has to be able to
# show it (a 60 Hz panel will not). NOT deployed to the playable install.
#
@{
    Name        = 'smooth-120'
    Summary     = 'smooth-60-bugfixes + I76_GLIDE_REFRESH=120 (needs a display above 60 Hz)'
    Verified    = '[measured, sandbox] 120.0 fps on the proxy frame counter 2026-10-02; not played at the console; not deployed'
    Env         = @{
        I76_HIRES_CLOCK     = '1'
        I76_FIXED_STEP      = '24'
        I76_FRAMERATE_FIXES = '1'
        I76_ENGINE_DT_FIX   = '1'
        I76_RENDER_INTERP   = '1'
        I76_FIX_HEALTH_PCT  = '1'
        I76_FIX_LABEL_TABLE = '1'
        I76_GLIDE_REFRESH   = '120'
    }
}
