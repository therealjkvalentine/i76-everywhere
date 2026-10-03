#
# lab-all - everything i76-uncap-lab\TEST-FRAMERATE.bat mode 5 ("all") sets. This is the set the
# owner console-verified in the sandbox on 2026-10-02, so it is the exact reproduction of that
# session, telemetry included. It is a LAB preset: the far clip and the telemetry export are
# instruments, not play features.
#
#   (everything in smooth-60-bugfixes.psd1, same values)
#   I76_FAR_CLIP=1800   draw distance: the missions' 600 m far clip replaced at its one read site,
#                       the renderer's two fixed pools enlarged 16x in the same step. Keep it at or
#                       below 2500: the hood view (F6) and binoculars (B) overflow the terrain
#                       tessellator's 16-bit vertex indices between 2500 and 2750 m and crash the
#                       game (docs/records/FARCLIP-CAMERA-CRASH.md); the proxy refuses values above 2500.
#   I76_TELEMETRY=1     UDP to 127.0.0.1:7676 + shared memory Local\I76Telemetry; watch it with
#                       python tools\telemetry\i76tel.py (tools/telemetry/README.md).
#
# Verification: [console-verified 2026-10-02, sandbox] by the owner, TEST-FRAMERATE.bat mode 5:
# in-mission music, F6 hood view and B binoculars at 1800 m, flamer, music slider, AI behaviour,
# Mission 5 jump without nitrous, out-of-gas jumps, body roll, keyboard save (n = 1).
# I76_FAR_CLIP in-memory form [measured, sandbox] 2026-10-01: a 10-minute session, no crash.
# NOT deployed to the playable install.
#
@{
    Name        = 'lab-all'
    Summary     = 'TEST-FRAMERATE mode 5: smooth-60-bugfixes + I76_FAR_CLIP=1800 + I76_TELEMETRY=1 (lab reproduction)'
    Verified    = '[console-verified 2026-10-02, sandbox] n = 1, the owner''s TEST-FRAMERATE mode 5 session; not deployed'
    Env         = @{
        I76_HIRES_CLOCK     = '1'
        I76_FIXED_STEP      = '24'
        I76_FRAMERATE_FIXES = '1'
        I76_ENGINE_DT_FIX   = '1'
        I76_RENDER_INTERP   = '1'
        I76_FIX_HEALTH_PCT  = '1'
        I76_FIX_LABEL_TABLE = '1'
        I76_FAR_CLIP        = '1800'
        I76_TELEMETRY       = '1'
    }
}
