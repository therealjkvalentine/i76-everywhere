<#
.SYNOPSIS  Desktop shortcuts for the main copies (owner ruling 2026-10-24: "Interstate 76 Gold" / "Interstate 76 Nitro") and tidy the old ones
           into Desktop\_i76-old-shortcuts. A shortcut is only created when its target exists; an old shortcut is only moved when its
           replacement exists (so the owner never loses the only way to play). Safe to re-run.
#>
$Desk = [Environment]::GetFolderPath('Desktop'); $Games = 'C:\Users\james\Games\I76'
$sh = New-Object -ComObject WScript.Shell
function New-Lnk($name, $target) {
  if (-not (Test-Path $target)) { Write-Host "SKIP  $name : target missing $target"; return $false }
  $l = $sh.CreateShortcut((Join-Path $Desk "$name.lnk")); $l.TargetPath = $target; $l.WorkingDirectory = Split-Path $target; $l.Save()
  Write-Host "MADE  $name -> $target"; return $true
}
$gold   = New-Lnk 'Interstate 76 Gold'   "$Games\Interstate 76 Gold\PLAY.bat"
$nitro  = New-Lnk 'Interstate 76 Nitro'  "$Games\Interstate 76 Nitro\PLAY-NITRO-ALL.bat"
$old = New-Item -ItemType Directory -Force (Join-Path $Desk '_i76-old-shortcuts')
# old name -> replacement that must exist first ($true = no replacement needed)
$moves = [ordered]@{
  'I76 - daily driver'                    = $true                     # target archived (daily-driver-pre-20261025)
  'I76 - LAN (family)'                    = $gold                     # LAN pack still the family pack until the Gold-LAN merge; keep until Gold exists
  'I76 - release candidate (tick test)'   = $gold
  'I76 Nitro - ALL (test)'                = $nitro
  'PLAY-LAB.bat - Shortcut'               = $true
  'I76 OWNER TESTS 2026-10-17'            = $true
}
foreach ($k in $moves.Keys) {
  $p = Join-Path $Desk "$k.lnk"
  if (-not (Test-Path $p)) { Write-Host "none  $k"; continue }
  if ($moves[$k]) { Move-Item $p $old.FullName -Force; Write-Host "MOVED $k" } else { Write-Host "KEPT  $k (replacement not there yet)" }
}
