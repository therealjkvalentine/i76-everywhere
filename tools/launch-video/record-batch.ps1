# record-batch.ps1 - record several shots, one boot each, one console acquisition each (CONSOLE-LOCK.md: release between boots so
# other lanes interleave). Each shot runs in its own PowerShell so no I76_* key leaks from one shot into the next.
#   .\record-batch.ps1 -Shots route-stock, route-all, mirror-before, mirror-after
param([Parameter(Mandatory)][string[]]$Shots, [int]$MaxWaitMin = 240)
foreach ($s in $Shots) {
    Write-Host ("[lv-batch] {0:HH:mm:ss} shot {1}" -f (Get-Date), $s) -ForegroundColor Cyan
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'record-shot.ps1') -Shot $s -MaxWaitMin $MaxWaitMin
}
