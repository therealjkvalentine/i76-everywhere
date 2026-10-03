#
# smooth-120 - smooth-60-bugfixes with the Glide window opened at 120 Hz (docs/FPS-120.md).
#
#   (everything in smooth-60-bugfixes.psd1, same values)
#   I76_GLIDE_REFRESH=120   ZGLIDE.DLL opens its window with grSstWinOpen(..., GR_REFRESH_60Hz, ...)
#                           and dgVoodoo paces windowed presents at the refresh the app asked for,
#                           whatever the panel says. (The FPSLimit and forced-Resolution tests that
#                           also read 60.0 are void: dgVoodoo was rejecting the sandbox conf then.) The proxy repoints ZGLIDE's grSstWinOpen import at a wrapper
#                           that substitutes the code for this rate. Physics stays at 24 steps/s,
#                           so four frames in five draw an interpolated pose; input latency, AI and
#                           physics fidelity do not change (FPS-120.md "The short answer").
#                           Accepted values: 60 70 72 75 80 85 90 100 120; 0 = none.
#
# Verification: [measured, sandbox] 2026-10-02: 120 -> 120.0 fps on the proxy frame counter; 120.1 fps on
# 2026-10-03. This exact set has not been console-played; the owner played the same switches plus
# I76_FAR_CLIP=1800 at 120 on 2026-10-02 (best-120.psd1, which is what the 2026-10-03 daily driver
# uses). The display has to be able to show it (a 60 Hz panel will not). 120 is the ceiling.
#
@{
    Name        = 'smooth-120'
    Summary     = 'smooth-60-bugfixes + I76_GLIDE_REFRESH=120 (needs a display above 60 Hz)'
    Verified    = '[measured, sandbox] 120.1 fps; played at the console as best-120 (this set + far clip 1800)'
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
