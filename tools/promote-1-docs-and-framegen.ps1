# Promotion 1 (2026-10-03): files that change no existing behaviour: the printable controls sheet and the
# framegen-90 preset (used only if a launcher names it). Run with the game closed. Add -Plan to preview.
param([switch]$Plan)
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'Promote-To-Driver.ps1') -Plan:$Plan `
    -What 'controls quick-reference PDF; framegen-90 preset (new files only, nothing replaced)' `
    -Gate 'no gate needed: documents and an unused preset; sheet consistency check + 161 offline tests pass' `
    -Files @{
        'Interstate76-Controls-Quick-Reference.pdf' = (Join-Path $repo 'docs\Interstate76-Controls-Quick-Reference.pdf')
        'Interstate 76\presets\framegen-90.psd1'    = (Join-Path $repo 'presets\framegen-90.psd1')
    }
