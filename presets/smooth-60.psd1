#
# smooth-60 - the recommended switch set for playing above 20 fps (music-fix/README.md,
# "Playing above 20 fps: the recommended switch set", 2026-09-27).
#
#   I76_HIRES_CLOCK=1      exact dt (QueryPerformanceCounter) instead of 15.6 ms GetTickCount steps
#   I76_FIXED_STEP=24      physics always steps 41.7 ms, the mean step of stock play at 20 fps;
#                          the first choice, 40 (25 ms), made jumps fall short - do not "tune" this up
#   I76_FRAMERATE_FIXES=1  sky drift, free-look, zoom, keyboard throttle, lock tones, radar ping,
#                          per-frame sounds, AI gains and fire gate, flamers, smoke, missile trails
#                          all pinned to the 20 Hz grid
#   I76_ENGINE_DT_FIX=1    engine RPM/torque smoothing counted per substep
#   I76_RENDER_INTERP=1    vehicles and camera drawn between the last two physics poses
#                          (removes the 40 Hz judder the fixed step leaves at 60 fps)
#
# Verification: [measured, sandbox] i76-map captures/014-framerate (dt exact, gravity dt-correct,
# 24 Hz body motion as calm as stock 20, 31-33% motionless frames -> 0% with interpolation);
# [console-verified 2026-10-02, sandbox] by the owner via i76-uncap-lab\TEST-FRAMERATE.bat
# (feel, Mission 5 jump without nitrous, out-of-gas jumps, AI, F6/B, keyboard save; n = 1).
# NOT deployed to the playable install. Needs music-fix/Strlkup.dll (the current build) in the
# game folder; the launcher checks and warns. GOG's I76PATCH.DLL must be renamed (e.g.
# I76PATCH.DLL.disabled) or the game stays capped at 20 fps - the launcher only warns, it does
# not rename anything.
#
@{
    Name        = 'smooth-60'
    Summary     = '60 fps: hires clock, fixed 24 Hz physics, frame-rate fixes, engine dt fix, render interpolation'
    Verified    = '[measured, sandbox] capture 014; [console-verified 2026-10-02, sandbox] n = 1; not deployed to the playable install'
    Env         = @{
        I76_HIRES_CLOCK     = '1'
        I76_FIXED_STEP      = '24'
        I76_FRAMERATE_FIXES = '1'
        I76_ENGINE_DT_FIX   = '1'
        I76_RENDER_INTERP   = '1'
    }
}
