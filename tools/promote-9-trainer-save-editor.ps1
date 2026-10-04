# Promotion 9 (2026-10-04): TRAINER.bat and SAVE-EDITOR.bat in the folder root (owner request). The trainer code goes
# to _tools\trainer + _tools\telemetry (the GUI finds the telemetry header at ..\telemetry); TRAINER.bat passes --any
# because this folder is not the sandbox. SAVE-EDITOR.bat serves "Interstate 76" saves on 127.0.0.1:7676 and refuses
# while i76.exe runs; the root save editor html/py move to the current repo build (the old ones go to _rollback).
param([switch]$Plan)
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'Promote-To-Driver.ps1') -Plan:$Plan `
    -What 'TRAINER.bat + SAVE-EDITOR.bat in the folder root; trainer code in _tools; save editor html/py/server at the current repo build' `
    -Gate 'staged copy of the driver layout: trainer --selftest 12/12; save editor --check on 10 saves round-trip OK; server GET / , /api/saves, GET+PUT save009 (backup + pre-edit written); SAVE-EDITOR.bat refuses while i76.exe runs' `
    -Files @{
        'TRAINER.bat'                       = (Join-Path $repo 'tools\driver\TRAINER.bat')
        'SAVE-EDITOR.bat'                   = (Join-Path $repo 'tools\driver\SAVE-EDITOR.bat')
        'i76-save-editor-server.py'         = (Join-Path $repo 'i76-save-editor-server.py')
        'i76-save-editor.html'              = (Join-Path $repo 'i76-save-editor.html')
        'i76-save-editor.py'                = (Join-Path $repo 'i76-save-editor.py')
        '_tools\trainer\i76trainer_gui.py'  = (Join-Path $repo 'tools\trainer\i76trainer_gui.py')
        '_tools\trainer\i76trainer.py'      = (Join-Path $repo 'tools\trainer\i76trainer.py')
        '_tools\trainer\i76trn.h'           = (Join-Path $repo 'tools\trainer\i76trn.h')
        '_tools\trainer\README-GUI.md'      = (Join-Path $repo 'tools\trainer\README-GUI.md')
        '_tools\telemetry\i76tel.py'        = (Join-Path $repo 'tools\telemetry\i76tel.py')
        '_tools\telemetry\i76tel.h'         = (Join-Path $repo 'tools\telemetry\i76tel.h')
    }
