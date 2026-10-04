<#
  restore_set.ps1 - put the lab save set back to the state in a save-backup-<ts>\ folder (made by leg-a.ps1 / leg-b.ps1).

    powershell -ExecutionPolicy Bypass -File restore_set.ps1 -Backup C:\Users\james\i76-uncap-lab\game\save-backup-20261001-HHMMSS [-WhatIf]

  Copies every backed-up file over the game copy (names with "__" are ADDON\ files), deletes files the backup lists as
  ABSENT if they now exist (user.rpr, ADDON\vehscn.vsf) and any save*.cmp / save-*.cmp the backup does not hold, then
  verifies every md5 against md5.txt. Refuses while an i76* process runs. Sandbox only.
#>
param([Parameter(Mandatory = $true)][string]$Backup, [switch]$WhatIf)
$ErrorActionPreference = "Stop"
$G = "C:\Users\james\i76-uncap-lab\game"
if (-not (Test-Path (Join-Path $Backup "md5.txt"))) { throw "no md5.txt in $Backup" }
if (Get-Process | Where-Object { $_.ProcessName -like "i76*" }) { throw "an i76* process is running" }
$lines = Get-Content (Join-Path $Backup "md5.txt") | Where-Object { $_.Trim() }
$held = @{}
foreach ($l in $lines) {
    $l = $l.Trim([char]0xFEFF)
    if ($l -match '^ABSENT\s+(.+)$') {
        $rel = $Matches[1].Trim(); $p = Join-Path $G $rel
        if (Test-Path $p) { Write-Host "DELETE (was absent) $rel" -ForegroundColor Yellow; if (-not $WhatIf) { Remove-Item $p -Force } }
        else { Write-Host "absent as before    $rel" }
        continue
    }
    if ($l -match '^([0-9a-f]{32})\s+(\d+)\s+(.+)$') {
        $md5 = $Matches[1]; $rel = $Matches[3].Trim(); $held[$rel.ToLower()] = $md5
        $src = Join-Path $Backup ($rel -replace "\\", "__"); $dst = Join-Path $G $rel
        if (-not (Test-Path $src)) { Write-Host "MISSING in backup   $rel" -ForegroundColor Red; continue }
        $cur = if (Test-Path $dst) { (Get-FileHash $dst -Algorithm MD5).Hash.ToLower() } else { "ABSENT" }
        if ($cur -eq $md5) { Write-Host "already identical   $rel" }
        else { Write-Host ("RESTORE             {0} ({1} -> {2})" -f $rel, $cur, $md5) -ForegroundColor Yellow; if (-not $WhatIf) { Copy-Item $src $dst -Force } }
    }
}
foreach ($f in Get-ChildItem (Join-Path $G "save*.cmp")) {
    if (-not $held.ContainsKey($f.Name.ToLower())) { Write-Host "DELETE (not in backup) $($f.Name)" -ForegroundColor Yellow; if (-not $WhatIf) { Remove-Item $f.FullName -Force } }
}
if ($WhatIf) { exit 0 }
$bad = 0
foreach ($rel in $held.Keys) {
    $p = Join-Path $G $rel; $cur = if (Test-Path $p) { (Get-FileHash $p -Algorithm MD5).Hash.ToLower() } else { "ABSENT" }
    if ($cur -ne $held[$rel]) { Write-Host "VERIFY FAIL $rel $cur != $($held[$rel])" -ForegroundColor Red; $bad++ }
}
Write-Host ("verify: {0} files, {1} mismatches" -f $held.Count, $bad) -ForegroundColor $(if ($bad) { "Red" } else { "Green" })
exit $bad
