<#
  cal-probe2.ps1 - run the remaining calibration probes (docs/EDITOR-FIELD-TESTS.md) unattended, one game session per
  probe: leg-b.ps1 to the LOAD board (rows >= 10 are below the fold: leg-b aborts at B1.5 and leaves the board up),
  scroll the board to the bottom (10 clicks on the down arrow), click the row (y = 193 + 23 x (row - 7) when 17
  records are listed), LOAD, ACCEPT SALVAGE, capture the Build and Repair Form and the Field Salvage screen, then the
  probe's extras, then close. Captures: runs\garage-ui\<save>-*.png.

    cal-probe2.ps1 -Probes save011,save012,save013,save014,save015
#>
param([string[]]$Probes = @("save011", "save012", "save013", "save014", "save015"), [int]$Records = 17)
$ErrorActionPreference = "Continue"
$Probes = @($Probes | ForEach-Object { $_ -split "," } | Where-Object { $_ })
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$ui = "$Here\garage-ui.ps1"
function Step { param($args) & $ui @args 2>&1 | Where-Object { $_ -match "shot|B1.6|clicked" } | ForEach-Object { "    $_" } }
foreach ($p in $Probes) {
    $row = [int]$p.Substring(4)
    Write-Host "[cal-probe2] $p row $row" -ForegroundColor Cyan
    & $ui -Close | Out-Null
    & $ui -Start $p -Row $row 2>&1 | Where-Object { $_ -match "B1.6|Abort" } | ForEach-Object { "    $_" }
    if ($row -ge 10) {
        1..10 | ForEach-Object { & $ui -Click "212,422" -Settle 250 | Out-Null }
        $y = 193 + 23 * ($row - ($Records - 10))
        & $ui -Click "320,$y" -Settle 600 -Shot "$p-board" | Where-Object { $_ -match "shot" }
        & $ui -Click "352,428" -Settle 2500 | Out-Null
        & $ui -Click "412,460" -Settle 1500 | Out-Null
    }
    & $ui -Shot "$p-form" | Where-Object { $_ -match "shot" }
    switch ($p) {
        "save011" { & $ui -Click "540,251" -Settle 1200 -Shot "$p-select-repairs" | Where-Object { $_ -match "shot" } }
        "save012" { & $ui -Click "258,65" -Settle 900 -Shot "$p-susp-chooser" | Where-Object { $_ -match "shot" } }
        "save014" { & $ui -Click "258,317" -Settle 900 -Shot "$p-special3-chooser" | Where-Object { $_ -match "shot" } }
        "save013" {
            & $ui -Click "240,460" -Settle 1500 -Shot "$p-salvage" | Where-Object { $_ -match "shot" }
            & $ui -Click "412,460" -Settle 1500 | Out-Null                     # ACCEPT SALVAGE back to the form
            & $ui -Click "400,460" -Settle 1500 | Out-Null                     # DONE -> mission
            Start-Sleep -Seconds 10
            1..4 | ForEach-Object { & $ui -Key ESC -Settle 1500 | Out-Null }
            & $ui -Shot "$p-mission" | Where-Object { $_ -match "shot" }
            & $ui -Key F6 -Settle 1500 -Shot "$p-hood" | Where-Object { $_ -match "shot" }
        }
    }
    if ($p -ne "save013") {
        if ($p -eq "save011" -or $p -eq "save012" -or $p -eq "save014") { & $ui -Close | Out-Null; & $ui -Start $p -Row $row 2>&1 | Out-Null; if ($row -ge 10) { 1..10 | ForEach-Object { & $ui -Click "212,422" -Settle 250 | Out-Null }; $y = 193 + 23 * ($row - ($Records - 10)); & $ui -Click "320,$y" -Settle 600 | Out-Null; & $ui -Click "352,428" -Settle 2500 | Out-Null; & $ui -Click "412,460" -Settle 1500 | Out-Null } }
        & $ui -Click "240,460" -Settle 1500 -Shot "$p-salvage" | Where-Object { $_ -match "shot" }
    }
    & $ui -Close | Out-Null
}
Write-Host "[cal-probe2] done"
