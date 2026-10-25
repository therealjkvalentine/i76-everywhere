# Promotion 2 (2026-10-03): widescreen + detail as the daily default, controls update, current proxy.
# Gated on the lab twin <lab>\game-dd-20261003 (autotest\runs\gate\20261003-115416: 18 PASS; row D "dgVoodoo.conf
# changed" is PLAY.bat selecting its conf by design; Esc-menu Exit in widescreen verified by hand with
# I76_U32X_MENU_ASPECT). Saves are not touched. Run with the game closed. Add -Plan to preview.
param([switch]$Plan)
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$twin = (Join-Path $env:USERPROFILE 'i76-uncap-lab\game-dd-20261003')
$files = @{
    'Interstate 76\STRLKUP.DLL'                       = (Join-Path $repo 'music-fix\Strlkup.dll')
    'Interstate 76\input.map'                         = (Join-Path $repo 'controls\input.map')
    'Interstate 76\_ahk\i76-remap.ahk'                = (Join-Path $repo 'i76-remap.ahk')
    'Interstate 76\_ahk\i76-ch-fighterstick.ahk'      = (Join-Path $repo 'i76-ch-fighterstick.ahk')
    'Interstate 76\PLAY-i76.ps1'                      = (Join-Path $repo 'PLAY-i76.ps1')
    'Interstate 76\dgVoodoo.16x10.conf'               = (Join-Path $twin 'Interstate 76\dgVoodoo.16x10.conf')
    'Interstate 76\dgVoodoo.wide.conf'                = (Join-Path $twin 'Interstate 76\dgVoodoo.wide.conf')
    'PLAY.bat'                                        = (Join-Path $twin 'PLAY.bat')
    'PLAY-16x10.bat'                                  = (Join-Path $twin 'PLAY-16x10.bat')
    'PLAY-stock.bat'                                  = (Join-Path $twin 'PLAY-stock.bat')
    'PLAY-with-FrameGen.bat'                          = (Join-Path $twin 'PLAY-with-FrameGen.bat')
    'Interstate76-Controls-Quick-Reference.pdf'       = (Join-Path $repo 'docs\Interstate76-Controls-Quick-Reference.pdf')
}
foreach ($f in Get-ChildItem (Join-Path $repo 'presets\*.psd1')) { $files["Interstate 76\presets\$($f.Name)"] = $f.FullName }
& (Join-Path $PSScriptRoot 'Promote-To-Driver.ps1') -Plan:$Plan `
    -What 'widescreen 21:9 + detail (best-wide) as PLAY.bat, PLAY-16x10.bat for the old picture; controls 1/J/L + pad fixes; current proxy; presets; PDF' `
    -Gate 'lab twin gate 20261003-115416: conf accepted, bookmark route 3/3, trip route via PLAY.bat 120 fps 2/2, save screen NO/YES, melee, lint, FFB live, saves byte-identical; Esc-menu Exit in widescreen verified by hand; owner approved widescreen in the sandbox' `
    -Files $files
