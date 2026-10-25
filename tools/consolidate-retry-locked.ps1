<#
.SYNOPSIS  Finish the 2026-10-25 consolidation items that were blocked by Windows Font Cache Service holding lee_____.ttf open
           (reboot, log off/on, or `Restart-Service FontCache` as admin releases it). DRY-RUN by default; -Execute to act.
  For each stub (a C: folder left with only the locked .ttf; the verified copy is on D:) it removes the remains and leaves a junction to the D: copy.
  For exp-nitro-owner (main Nitro was COPIED to Games\I76\Interstate 76 Nitro because the rename was blocked) it first compares the two
  trees; if they differ it only reports (a lane wrote to the stale copy), otherwise it removes the old folder and leaves a junction.
#>
param([switch]$Execute)
$Lab=(Join-Path $env:USERPROFILE 'i76-uncap-lab'); $G=(Join-Path $env:USERPROFILE 'Games\I76'); $A=(Join-Path $(if ($env:I76_ARCHIVE_ROOT) { $env:I76_ARCHIVE_ROOT } else { 'D:\archive' }) 'consolidated-20261025')
$stubs = @(
 @("$G\nitro","$A\Games-I76\nitro"), @("$G\nitro-plus-original","$A\Games-I76\nitro-plus-original"),
 @("$Lab\exp-debug","$A\lab\exp-debug"), @("$Lab\exp-nitro-port","$A\lab\exp-nitro-port"), @("$Lab\game-fresh-nitro","$A\lab\game-fresh-nitro"),
 @("$Lab\exp-nitro-mp-b","$A\lab\exp-nitro-mp-b"), @("$Lab\exp-nitro-types","$A\lab\exp-nitro-types"), @("$Lab\exp-nitro-types-b","$A\lab\exp-nitro-types-b"),
 @("$Lab\exp-mac","$A\lab\exp-mac"), @("$Lab\exp-rcdraw","$A\lab\exp-rcdraw"))
function Clear-Dir($p,$target,$junction){
  if (-not (Test-Path $p)) { Write-Host "gone    $p"; return }
  if ((Get-Item $p -Force).Attributes -band 'ReparsePoint') { Write-Host "junction already: $p"; return }
  if (-not $Execute) { Write-Host "WOULD remove $p and junction -> $target"; return }
  try { Remove-Item $p -Recurse -Force -ErrorAction Stop; if ($junction) { New-Item -ItemType Junction -Path $p -Target $target | Out-Null }; Write-Host "done    $p -> $target" }
  catch { Write-Host "STILL LOCKED $p : $($_.Exception.Message)" }
}
foreach ($s in $stubs) { Clear-Dir $s[0] $s[1] $true }
# exp-nitro-owner
$old="$Lab\exp-nitro-owner"; $new="$G\Interstate 76 Nitro"
if ((Test-Path $old) -and -not ((Get-Item $old -Force).Attributes -band 'ReparsePoint')) {
  # files only in the old copy or newer there; cruft moved out of main on 2026-10-25 (logs, proxy backups, input.map.pre-*) is expected and ignored
  $diff = robocopy $old $new /L /E /NJH /NJS /NP /NDL /XF MOVED-TO-Interstate-76-Nitro.txt | ? { $_ -match 'New File|Newer|Older|Modified' -and $_ -notmatch 'histogram\.txt|mciproxy\.log|strlkup\.dll\.[0-9a-f]{8}|input\.map\.pre-|\.pre-|\.driver-' }
  if ($diff) { Write-Host "exp-nitro-owner DIFFERS from main (a lane wrote to the stale copy). Merge by hand, then re-run:"; $diff | % { Write-Host "   $_" } }
  else { Clear-Dir $old $new $true }
}
