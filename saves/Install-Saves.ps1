<#
  Install-Saves.ps1 - copy the repo's bookmark saves into a game folder.

  The whole set moves together: savegame.dir indexes the .cmp files by slot, so a partial
  copy leaves the index describing saves that are not there. Whatever is already installed
  is backed up first.
#>
param(
    [Parameter(Mandatory)] [string]$GameDir,
    [string]$SaveDir
)
$ErrorActionPreference = 'Stop'
# not a param default: $PSScriptRoot is not bound yet while the param block is evaluated
if (-not $SaveDir) { $SaveDir = $PSScriptRoot }
if (-not (Test-Path (Join-Path $GameDir 'i76.exe'))) { throw "no i76.exe in $GameDir" }
if (Get-Process i76 -EA SilentlyContinue) { throw "close the game first - it rewrites savegame.dir on exit" }

$src = @(Get-ChildItem (Join-Path $SaveDir 'save*.cmp')) + @(Get-Item (Join-Path $SaveDir 'savegame.dir'))

# refuse to install a short index rather than ship the truncation bug onward
$dir = Get-Item (Join-Path $SaveDir 'savegame.dir')
$n = [BitConverter]::ToUInt32([IO.File]::ReadAllBytes($dir.FullName), 0)
$want = 0x28 + $n * 60
if ($dir.Length -lt $want) { throw ("savegame.dir is truncated ({0} bytes, need {1} for {2} records) - repair it before installing" -f $dir.Length, $want, $n) }

$existing = @(Get-ChildItem (Join-Path $GameDir 'save*.cmp') -EA SilentlyContinue) +
            @(Get-Item (Join-Path $GameDir 'savegame.dir') -EA SilentlyContinue)
if ($existing.Count) {
    $backup = Join-Path $GameDir ("save-backup-" + (Get-Date -Format 'yyyyMMdd-HHmmss'))
    New-Item -ItemType Directory -Path $backup | Out-Null
    $existing | Copy-Item -Destination $backup
    Write-Host ("backed up {0} file(s) -> {1}" -f $existing.Count, $backup) -ForegroundColor DarkGray
    $existing | Remove-Item -Force
}
$src | Copy-Item -Destination $GameDir -Force
Write-Host ("installed {0} bookmark(s) into {1}" -f $n, $GameDir) -ForegroundColor Green
