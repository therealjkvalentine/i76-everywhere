#
# smooth-60-bugfixes - smooth-60 plus the two stock bug fixes the proxy carries
# (music-fix/README.md switch table).
#
#   (everything in smooth-60.psd1, same values)
#   I76_FIX_HEALTH_PCT=1    stock bug: the vehicle health percent drops its x100 once engine,
#                           suspension or brakes are below 99.99%, so a scratched car reads under
#                           1% (smoke, handgun targeting, script hpLesser, AI fleeing, target
#                           brackets all see it). Fixed value: min(28 + 72 x worst side ratio,
#                           100 x worst core ratio). Missions may be tuned around the bug, which is
#                           why it is a separate preset. docs/HEALTH-BAR-COLOUR.md
#   I76_FIX_LABEL_TABLE=1   stock bug: the per-mission object-label table grows through a broken
#                           path (new pointer discarded, NULL written through on failure). Only
#                           huge custom missions reach it.
#
# Verification: smooth-60 part as in smooth-60.psd1 [console-verified 2026-10-02, sandbox].
# I76_FIX_HEALTH_PCT [measured, sandbox] 2026-10-02: tools/trainer/tests/health_pct_live_test.py
# (stock 0.99 / fix 49.6 on a 30% armour car with a 99% engine); target-bracket colours under
# the fix still open (backlog P1-01). I76_FIX_LABEL_TABLE [measured, sandbox]: T01 with the test
# capacity 16 grew to 272, all 88 labels kept. Both were on during the owner's 2026-10-02 console
# session (TEST-FRAMERATE mode 5). NOT deployed to the playable install.
#
@{
    Name        = 'smooth-60-bugfixes'
    Summary     = 'smooth-60 + the health-percent and label-table stock bug fixes'
    Verified    = '[measured, sandbox] both fixes; on during the 2026-10-02 console session (mode 5); not deployed to the playable install'
    Env         = @{
        I76_HIRES_CLOCK     = '1'
        I76_FIXED_STEP      = '24'
        I76_FRAMERATE_FIXES = '1'
        I76_ENGINE_DT_FIX   = '1'
        I76_RENDER_INTERP   = '1'
        I76_FIX_HEALTH_PCT  = '1'
        I76_FIX_LABEL_TABLE = '1'
    }
}
