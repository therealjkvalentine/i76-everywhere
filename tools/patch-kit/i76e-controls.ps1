<#
  i76e-controls.ps1 - what CONTROLS.bat of the Patch Kit runs (kit-controls lane 2026-10-25, docs\records\KIT-CONTROLS-UPDATER-2026-10-25.md).

  The setup never replaces a player's own key bindings (input.map): when it finds one that is not GOG's and not what the kit
  wrote, it keeps it and puts the kit's layout beside it as input.map.i76e-default. This script lets the player choose:

    keep   keep my input.map as it is (nothing changes)
    kit    use the kit's layout (Gold: this project's WASD map + the gamepad / wheel button layer; Nitro: my map + the kit's
           small additions). My map is copied into _i76e\backup\input.map.mine-<time> first.
    mine   restore my own map: the newest _i76e\backup\input.map.mine-*, else the one from before the kit
           (_i76e\backup\pre-kit\input.map). No gamepad button layer (it types the kit's keys).
    status what is in place now (the default with -Choice and no menu)

    i76e-controls.ps1 [-Choice menu|status|keep|kit|mine] [-NoPause]
  The game must be closed. Nothing outside the game folder is touched.
#>
param([ValidateSet('menu', 'status', 'keep', 'kit', 'mine')][string]$Choice = 'menu', [switch]$NoPause)
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot; $gameDir = Split-Path -Parent $here; $repo = Join-Path $here 'repo'
$backupDir = Join-Path $here 'backup'; $preKit = Join-Path $backupDir 'pre-kit'
$map = Join-Path $gameDir 'input.map'; $def = "$map.i76e-default"
$isNitro = -not (Test-Path -LiteralPath (Join-Path $gameDir 'i76.exe')) -and (Test-Path -LiteralPath (Join-Path $gameDir 'nitro.exe'))
$logFile = Join-Path $here 'setup.log'
function Log([string]$m) { try { Add-Content -LiteralPath $logFile -Value ("{0}  controls: {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $m) -Encoding ascii } catch { } }
function Say([string]$m, [string]$c = 'Gray') { Write-Host $m -ForegroundColor $c; Log $m }
function Md5([string]$p) { if (Test-Path -LiteralPath $p) { (Get-FileHash -LiteralPath $p -Algorithm MD5).Hash.ToLower() } else { '' } }
$canPause = -not $NoPause -and -not $env:I76E_NO_PAUSE
try { if ([Console]::IsOutputRedirected -or [Console]::IsInputRedirected) { $canPause = $false } } catch { $canPause = $false }
function Done([int]$rc) {
    if ($canPause) { Write-Host ''; Write-Host '  Press any key to close this window . . .' -ForegroundColor Cyan; try { [void]$Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown') } catch { } }
    exit $rc
}
if (-not (Test-Path -LiteralPath (Join-Path $gameDir 'PLAY-i76.ps1'))) { Say "The kit is not set up in this folder yet: start PLAY.bat$(if ($isNitro) { ' (PLAY-Nitro.bat)' }) once, then run CONTROLS.bat." 'Yellow'; Done 1 }

$gogMd5 = '74d2da3734b1c304e88b7ceb88050f1d'
$kitMd5 = if ($isNitro) { '' } else { Md5 (Join-Path $repo 'controls\input.map') }
$mode = Get-Content -LiteralPath (Join-Path $gameDir 'i76e-controls.txt') -TotalCount 1 -ErrorAction SilentlyContinue
# i76e-layers.txt 'on' = the player chose the kit's layout here: PLAY-i76.ps1 then starts the pad / wheel / stick key layers even
# after he edits that map (without it, a map that is not a kit layout runs with the layers off)
$layersFile = Join-Path $gameDir 'i76e-layers.txt'
function Set-Layers([bool]$on) {
    if ($on) { Set-Content -LiteralPath $layersFile -Value @('on', "# CONTROLS.bat $(Get-Date -Format 'yyyy-MM-dd HH:mm'): the kit's layout was chosen; PLAY-i76.ps1 starts the key layers") -Encoding ascii }
    else { Remove-Item -LiteralPath $layersFile -Force -ErrorAction SilentlyContinue }
}
function Mine-Backup {   # the newest copy of the player's own map
    $m = Get-ChildItem -LiteralPath $backupDir -Filter 'input.map.mine-*' -File -ErrorAction SilentlyContinue | Sort-Object Name -Descending | Select-Object -First 1
    if ($m) { return $m.FullName }
    if (Test-Path -LiteralPath (Join-Path $preKit 'input.map')) { return (Join-Path $preKit 'input.map') }
    return ''
}
function Describe {
    $cur = Md5 $map
    $what = if (-not $cur) { 'none (the game writes one with its default keys)' }
            elseif ($kitMd5 -and $cur -eq $kitMd5) { "the kit's layout (this project's WASD map)" }
            elseif ($cur -eq $gogMd5) { "GOG's original (the 1997 keys)" }
            elseif ($isNitro -and (Get-Content -LiteralPath $map -Raw) -match 'setup-windows\.ps1') { "the kit's Nitro layout (GOG's keys + the kit's additions)" }
            else { 'your own' }
    Write-Host ''
    Write-Host "  Controls in $gameDir"
    Write-Host "    input.map now:          $what"
    Write-Host "    mode:                   $(switch ($mode) { 'i76e' { 'kit (WASD map + gamepad / wheel button layer)' } 'stock' { "GOG's keys + the kit's small additions" } 'own' { 'your own map, no gamepad button layer' } default { 'not recorded' } })"
    Write-Host "    key layers (pad/wheel/stick): $(if ($mode -eq 'own') { 'off (your map)' } elseif ((Get-Content -LiteralPath $layersFile -TotalCount 1 -ErrorAction SilentlyContinue) -eq 'on' -or ($kitMd5 -and (Md5 $map) -eq $kitMd5)) { 'on' } else { 'off unless input.map is the kit''s (PLAY.bat decides at each start)' })"
    Write-Host "    the kit's layout ready: $(if (Test-Path -LiteralPath $def) { 'yes (input.map.i76e-default)' } else { 'no (input.map is already the kit''s, or the setup has not run)' })"
    $mb = Mine-Backup
    Write-Host "    your backup:            $(if ($mb) { $mb.Substring($gameDir.Length + 1) } else { 'none' })"
    Write-Host ''
}
function Running-Here { @(Get-Process i76, nitro -ErrorAction SilentlyContinue | Where-Object { $_.Path -and $_.Path.StartsWith($gameDir + '\', [StringComparison]::OrdinalIgnoreCase) }).Count -gt 0 }
function Run-Setup([string[]]$extra) {
    $argv = @('-GameDir', $gameDir, '-ControlsOnly', '-NoShortcut') + $extra
    if ($isNitro) { $argv += @('-Exe', 'nitro.exe') } else { $argv += @('-AhkDir', (Join-Path $here 'AutoHotkey')) }
    Log "> setup-windows.ps1 $($argv -join ' ')"
    $ErrorActionPreference = 'Continue'; $global:LASTEXITCODE = 0
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $repo 'setup-windows.ps1') @argv 2>&1 | ForEach-Object { Log "  $_"; if ("$_" -match 'input\.map|Controls|KEPT|_ahk') { Write-Host "    $_" -ForegroundColor DarkGray } }
    $rc = $LASTEXITCODE; Log "< exit $rc"; return $rc
}
function Backup-Mine {   # the current map into _i76e\backup unless it is the kit's / GOG's / already backed up
    $cur = Md5 $map
    if (-not $cur -or $cur -eq $kitMd5 -or $cur -eq $gogMd5) { return }
    foreach ($b in @(Get-ChildItem -LiteralPath $backupDir -Recurse -File -Filter 'input.map*' -ErrorAction SilentlyContinue)) { if ((Md5 $b.FullName) -eq $cur) { return } }
    New-Item -ItemType Directory -Force $backupDir | Out-Null
    $to = Join-Path $backupDir ("input.map.mine-" + (Get-Date -Format 'yyyyMMdd-HHmmss'))
    Copy-Item -LiteralPath $map -Destination $to
    Say "  your input.map is backed up as _i76e\backup\$(Split-Path -Leaf $to)."
}

if ($Choice -eq 'menu') {
    Describe
    Write-Host '  1  keep my input.map as it is (the kit''s gamepad / wheel / stick key layers go off: they type the kit''s keys)'
    Write-Host ('  2  use the kit''s layout' + $(if (-not $isNitro) { ' (W A S D drive; with the gamepad / wheel button layer)' } else { '' }))
    Write-Host '  3  restore my own map from the backup'
    Write-Host '  Q  quit'
    $k = Read-Host '  Choose 1, 2, 3 or Q'
    $Choice = switch ($k.Trim()) { '1' { 'keep' } '2' { 'kit' } '3' { 'mine' } default { 'quit' } }
    if ($Choice -eq 'quit') { Done 0 }
}
if ($Choice -eq 'status') { Describe; Done 0 }
if (Running-Here -and $Choice -ne 'keep') { Say '  Close the game first, then run CONTROLS.bat again.' 'Red'; Done 1 }
if ($Choice -eq 'keep') {
    # "mine, as it is": a map that is not the kit's (nor GOG's untouched one) switches the mode to own, which takes the kit's
    # gamepad / wheel / stick key layers out of _ahk\ (they type the kit's keys over the player's bindings, OWN-INPUT-MAP s.2)
    $cur = Md5 $map
    if ($cur -and $cur -ne $kitMd5 -and $mode -ne 'own' -and -not ($isNitro -and $mode -eq 'stock' -and (Get-Content -LiteralPath $map -Raw) -match 'setup-windows\.ps1')) {
        if (Running-Here) { Say '  Close the game first, then run CONTROLS.bat again.' 'Red'; Done 1 }
        $rc = Run-Setup @('-Controls', 'own')
        if ($rc -ne 0) { Say "  The setup step failed (exit $rc): _i76e\setup.log has the details. input.map is unchanged." 'Red'; Done 1 }
        Set-Layers $false
        Say '  Kept: input.map is unchanged, and the kit''s gamepad / wheel / stick key layers are off (they type the kit''s keys).' 'Green'
    } else { Say "  Kept: input.map is unchanged.$(if (Test-Path -LiteralPath $def) { ' The kit''s layout stays beside it as input.map.i76e-default.' })" 'Green' }
    Done 0
}

if ($Choice -eq 'kit') {
    Backup-Mine
    # an edited gamepad layer script goes into the backup too: -ReplaceControls puts the kit's back
    foreach ($ahk in @(Get-ChildItem -LiteralPath (Join-Path $gameDir '_ahk') -Filter '*.ahk' -File -ErrorAction SilentlyContinue)) {
        $src = Join-Path $repo $ahk.Name
        if ((Test-Path -LiteralPath $src) -and (Md5 $src) -ne (Md5 $ahk.FullName)) {
            New-Item -ItemType Directory -Force (Join-Path $backupDir '_ahk') | Out-Null
            Copy-Item -LiteralPath $ahk.FullName -Destination (Join-Path $backupDir "_ahk\$($ahk.Name).mine-$(Get-Date -Format 'yyyyMMdd-HHmmss')")
            Say "  your edited _ahk\$($ahk.Name) is backed up in _i76e\backup\_ahk\."
        }
    }
    $mode = if ($isNitro) { 'stock' } else { 'i76e' }
    $rc = Run-Setup @('-Controls', $mode, '-ReplaceControls')
    if ($rc -ne 0) { Say "  The setup step failed (exit $rc): _i76e\setup.log has the details. input.map is as before or the kit's." 'Red'; Done 1 }
    if (-not $isNitro) { Set-Layers $true }
    Say "  Done: input.map is the kit's layout$(if (-not $isNitro) { ' (W A S D drive), with the gamepad / wheel button layer' }). CONTROLS.bat, option 3, goes back to yours." 'Green'
    Done 0
}
if ($Choice -eq 'mine') {
    $src = Mine-Backup
    if (-not $src) { Say '  No backup of your own map was found (_i76e\backup\ is empty): nothing changed.' 'Yellow'; Done 1 }
    if ((Md5 $src) -ne (Md5 $map)) {
        Backup-Mine
        Copy-Item -LiteralPath $src -Destination $map -Force
        if ((Md5 $map) -ne (Md5 $src)) { Say '  The copy did not read back - input.map may be read-only.' 'Red'; Done 1 }
    }
    $rc = Run-Setup @('-Controls', 'own')
    if ($rc -ne 0) { Say "  The setup step failed (exit $rc): _i76e\setup.log has the details. input.map is your own." 'Red'; Done 1 }
    Set-Layers $false
    Say "  Done: input.map is your own again (from $($src.Substring($gameDir.Length + 1))). No gamepad button layer; the kit's layout stays as input.map.i76e-default." 'Green'
    Done 0
}
