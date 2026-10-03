# Promotion 4 (2026-10-03): u32x 696577dc (garage DONE popup no longer locks after a focus change; backlog P1-19) and the
# current proxy (HUD sprite squeeze in widescreen). Gated on the lab twin: autotest\runs\gate\20261003-141237 (18 PASS;
# row D = PLAY.bat selecting its conf, by design; row 5 INFO = the gate's own widescreen geometry) + widescreen Esc-menu
# Exit verified by hand. Sandbox popup repro: 6/6 closed after a focus change with this u32x, 0/2 with the old one.
param([switch]$Plan)
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'Promote-To-Driver.ps1') -Plan:$Plan `
    -What 'u32x 696577dc (garage popup lock fix) + proxy 0b18d77c (HUD sprite squeeze in widescreen)' `
    -Gate 'lab twin gate 20261003-141237: conf, bookmark route 3/3, trip route 120 fps 2/2, save screen 6/6, melee, lint, FFB, saves identical; widescreen Esc-menu Exit by hand; popup repro in the sandbox 6/6' `
    -Files @{
        'Interstate 76\u32x.dll'    = (Join-Path $repo 'u32x\u32x_full.dll')
        'Interstate 76\STRLKUP.DLL' = (Join-Path $repo 'music-fix\Strlkup.dll')
    }
