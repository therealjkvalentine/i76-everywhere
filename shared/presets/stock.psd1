#
# stock - what GOG ships, plus the music fix. No I76_* switch set.
#
# This is PLAY-i76.ps1's default and exactly its behaviour before -Preset existed: the Strlkup
# proxy (if deployed) plays the soundtrack and every opt-in engine switch stays off. The frame
# rate is whatever the folder's own files give: GOG's installer (2.1.0.17) ships no I76PATCH.DLL
# (checked 2026-11-03 on a full extraction of the installer and on two GOG test installs); that
# ~20 fps limiter DLL comes with the 2019 AiO community patch (docs/records/I76-VERSIONS.md s.2.8).
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
    Summary     = 'The game as installed, music fix only, no engine switches (an AiO-patched folder''s I76PATCH.DLL caps it at ~20 fps; GOG ships no such DLL)'
    Verified    = '[verified in play] the daily driver state'
    Env         = @{}
}
