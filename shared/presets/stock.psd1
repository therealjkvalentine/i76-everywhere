#
# stock - what GOG ships, plus the music fix. No I76_* switch set.
#
# This is PLAY-i76.ps1's default and exactly its behaviour before -Preset existed: the Strlkup
# proxy (if deployed) plays the soundtrack, every opt-in engine switch stays off, and GOG's
# I76PATCH.DLL holds the frame rate at ~20 fps.
#
# Verification: [verified in play] - this is the daily driver's state (docs/RELEASE-PLAN.md
# section 1). Nothing to verify beyond what the launcher already did.
#
# Format (all presets): a PowerShell data file. Env is the set of environment variables handed
# to the GAME PROCESS ONLY (never the shell you launched from). Values are strings. An empty
# Env means "nothing set". Read with Import-PowerShellDataFile; no code runs.
#
@{
    Name        = 'stock'
    Summary     = '20 fps as GOG ships it (I76PATCH.DLL cap), music fix only, no engine switches'
    Verified    = '[verified in play] the daily driver state'
    Env         = @{}
}
