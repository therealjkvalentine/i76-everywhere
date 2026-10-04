# Promotion 10 (2026-10-04): the quick reference with pictures of the wheel and the flight stick (owner request).
# Five pages now: keyboard and mouse, gamepad, wheel (T300RS), flight stick (CH Fighterstick), 1997 keys vs ours.
# Document only; no game file changes.
param([switch]$Plan)
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'Promote-To-Driver.ps1') -Plan:$Plan `
    -What 'Controls quick reference PDF: wheel and flight stick pages drawn around labelled pictures (5 pages)' `
    -Gate 'tools\controls-sheet\build.ps1: lint OK, sources agree (57 actions, 0 mismatches), tests\test_controls.py 5 passed; pages 3 and 4 looked at as PNGs' `
    -Files @{
        'Interstate76-Controls-Quick-Reference.pdf' = (Join-Path $repo 'docs\Interstate76-Controls-Quick-Reference.pdf')
    }
