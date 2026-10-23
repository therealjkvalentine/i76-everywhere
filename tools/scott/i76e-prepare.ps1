<#
  i76e-prepare.ps1 - what PLAY.bat / PLAY-PREVIEW.bat of the tester build run BEFORE the game starts (tester build
  2026-10-23, tools\package-scott.ps1 puts this file and its payload in <game>\_i76e\, the .bat files beside i76.exe).

  1. First run (or an updated overlay, or -Resetup): the one-time setup = this repo's own installer, setup-windows.ps1,
     run on the game folder the _i76e folder sits in: dgVoodoo 2.87.3 (from _i76e\dgVoodoo), the proxy Strlkup.dll,
     the shell keyboard patches (Apply-Shell-Keys.ps1 + fix-shell-textentry.ps1, on the user's own i76shell.dll),
     u32x (import rename of i76.exe + i76shell.dll), the control map, the presets, the launcher. Originals are kept
     beside every changed file (i76.exe.u32xorig, i76shell.dll.pre-i76e-keys / .orig, strlkup_orig.dll,
     input.map.stock-*, _openglide-backup\). Nothing outside the game folder is written (no shortcut, no registry).
  2. Every run: the primary monitor's size is read (-Display WxH overrides it; a Remote Desktop session is refused)
     and, when it differs from the last run (or -NoSupersample changed), tools\Make-Wide-Conf.ps1 rewrites
     dgVoodoo.wide.conf ([Glide] render target = 2x the display per axis, 1x with -NoSupersample; stretched_ar at the
     display's own shape, so 21:9 / 16:9 / 16:10 / 4:3 all get a correct picture) and the presets' I76_ASPECT /
     I76_U32X_MENU_ASPECT (tick19-42, scott-preview, best-wide*). Then dgVoodoo.wide.conf -> dgVoodoo.conf.
  The .bat then starts PLAY-i76.ps1 -Preset <x> itself (exit 0 here = go; anything else = do not start).

    i76e-prepare.ps1 [-Preset tick19-42] [-NoSupersample] [-Display 1920x1080] [-Resetup] [-DryRun]
    i76e-prepare.ps1 -Uninstall        put the originals back and remove what the setup added (the _i76e folder,
                                       PLAY*.bat and README-SCOTT.md are left for the user to delete)
#>
param([string]$Preset = 'tick19-42', [switch]$NoSupersample, [string]$Display = '', [switch]$Resetup, [switch]$Uninstall, [switch]$DryRun)
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot; $game = Split-Path -Parent $here; $repo = Join-Path $here 'repo'
function Say([string]$m, [string]$c = 'Gray') { Write-Host $m -ForegroundColor $c }
function Fail([string]$m) { Write-Host ''; Write-Host "i76e: $m" -ForegroundColor Red; Write-Host 'The game was not started.' -ForegroundColor Red; exit 1 }
function Child([string]$script, [string[]]$argv) {
    # the repo scripts call exit freely: run each as its own powershell and read its exit code
    $global:LASTEXITCODE = 0
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $script @argv 2>&1 | ForEach-Object { Say "  $_" }
    return $LASTEXITCODE
}

$exe = Join-Path $game 'i76.exe'
if (-not (Test-Path -LiteralPath $exe)) { Fail "no i76.exe next to the _i76e folder ($game). Unzip the build INTO your Interstate '76 folder, the one that holds i76.exe." }
$version = (Get-Content (Join-Path $here 'VERSION.txt') -TotalCount 1).Trim()
$stampFile = Join-Path $here 'installed.txt'; $dispFile = Join-Path $here 'display.txt'

# ---- uninstall ---------------------------------------------------------------------------------------------------
if ($Uninstall) {
    Say "=== removing the i76-everywhere overlay ($version) from $game ===" 'Cyan'
    if (Get-Process i76 -ErrorAction SilentlyContinue) { Fail 'close the game first' }
    if (Test-Path -LiteralPath (Join-Path $game 'i76.exe.u32xorig')) { [void](Child (Join-Path $repo 'u32x\deploy-u32x.ps1') @('-GameDir', $game, '-Restore')) }
    [void](Child (Join-Path $repo 'tools\scott\Apply-Shell-Keys.ps1') @('-GameDir', $game, '-Revert'))
    foreach ($pair in @(@('strlkup_orig.dll', 'Strlkup.dll'), @('I76PATCH.DLL.disabled', 'I76PATCH.DLL'))) {
        $from = Join-Path $game $pair[0]
        if (Test-Path -LiteralPath $from) { Move-Item -LiteralPath $from -Destination (Join-Path $game $pair[1]) -Force; Say "  $($pair[1]) restored" }
    }
    $stock = Get-ChildItem -LiteralPath $game -Filter 'input.map.stock-*' -File | Sort-Object Name | Select-Object -First 1
    if ($stock) { Copy-Item -LiteralPath $stock.FullName -Destination (Join-Path $game 'input.map') -Force; Say "  input.map restored from $($stock.Name)" }
    foreach ($n in 'Glide.dll', 'Glide2x.dll', 'Glide3x.dll', 'DDraw.dll', 'D3DImm.dll', 'dgVoodooCpl.exe', 'dgVoodoo.conf', 'dgVoodoo.16x10.conf', 'dgVoodoo.wide.conf',
                   'u32x.dll', 'i76wheel.exe', 'PLAY-i76.ps1', 'PLAY-i76.bat', 'PLAY-16x10.bat', 'PLAY-balanced.bat', 'PLAY-stock.bat', 'DEBUG.bat', 'TRAINER.bat',
                   'strlkup-proxy-build.txt', 'i76e-controls.txt', 'input.map.as-installed', 'mciproxy.log', 'u32x.log') {
        Remove-Item -LiteralPath (Join-Path $game $n) -Force -ErrorAction SilentlyContinue
    }
    $ogb = Join-Path $game '_openglide-backup'
    if (Test-Path -LiteralPath $ogb) {
        Get-ChildItem -LiteralPath $ogb -File | ForEach-Object { Move-Item -LiteralPath $_.FullName -Destination (Join-Path $game $_.Name) -Force; Say "  $($_.Name) restored" }
        Remove-Item -LiteralPath $ogb -Recurse -Force -ErrorAction SilentlyContinue
    }
    foreach ($d in 'presets', '_ahk', '_tools') { Remove-Item -LiteralPath (Join-Path $game $d) -Recurse -Force -ErrorAction SilentlyContinue }
    Remove-Item -LiteralPath $stampFile, $dispFile -Force -ErrorAction SilentlyContinue
    Say "done. Left for you to delete: PLAY.bat, PLAY-PREVIEW.bat, PLAY-T05.bat, PLAY-PREVIEW-T05.bat, UNINSTALL-i76e.bat, README-SCOTT.md and the _i76e folder." 'Green'
    Say "Backups kept (safe to delete): i76.exe.u32xorig, i76shell.dll.orig, i76shell.dll.pre-i76e-keys, input.map.stock-*. GOG Galaxy's 'verify / repair' also restores everything."
    exit 0
}

# ---- session + display -----------------------------------------------------------------------------------------------
Add-Type -AssemblyName System.Windows.Forms
$isRdp = $false; try { $isRdp = [System.Windows.Forms.SystemInformation]::TerminalServerSession } catch { }
if ($isRdp -and -not $DryRun) { Fail "this is a Remote Desktop session: the game's 3D cannot start over Remote Desktop (it sits on PLEASE STAND BY forever). Start it at the PC itself." }
if ($Display) {
    if ($Display -notmatch '^(\d+)x(\d+)$') { Fail "--display wants WIDTHxHEIGHT, e.g. 1920x1080 (got '$Display')" }
    $W = [int]$Matches[1]; $H = [int]$Matches[2]; $from = '--display'
} else {
    $b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds; $W = $b.Width; $H = $b.Height; $from = 'the primary monitor'
}
if ($W -lt 640 -or $H -lt 480) { Fail "display ${W}x${H} is smaller than 640x480" }
$scale = if ($NoSupersample) { 1 } else { 2 }
$narrow = (($W / $H) -le (4.0 / 3.0 + 0.01))

# ---- one-time setup ----------------------------------------------------------------------------------------------------
$installed = if (Test-Path -LiteralPath $stampFile) { (Get-Content $stampFile -TotalCount 1).Trim() } else { '' }
$need = $Resetup -or ($installed -ne $version) -or
        -not (Test-Path -LiteralPath (Join-Path $game 'strlkup_orig.dll')) -or -not (Test-Path -LiteralPath (Join-Path $game 'u32x.dll')) -or
        -not (Test-Path -LiteralPath (Join-Path $game "presets\$Preset.psd1")) -or -not (Test-Path -LiteralPath (Join-Path $game 'PLAY-i76.ps1'))
if ($need) {
    Say "=== one-time setup of the i76-everywhere overlay ($version) in $game ===" 'Cyan'
    Say "    display ${W}x${H} ($from); originals are kept beside every file that changes; nothing outside this folder is written."
    if ($DryRun) { Say '  (dry run: nothing written)' 'Yellow' }
    else {
        if (Get-Process i76 -ErrorAction SilentlyContinue) { Fail 'close the running game first' }
        # 1. the shell patches, before u32x renames the shell's import (the patch is keyed by the stock md5)
        $rc = Child (Join-Path $repo 'tools\scott\Apply-Shell-Keys.ps1') @('-GameDir', $game)
        if ($rc -ne 0 -and $rc -ne 2) { Fail "Apply-Shell-Keys.ps1 exited $rc" }
        try { & (Join-Path $repo 'tools\fix-shell-textentry.ps1') -GameDir $game 2>&1 | ForEach-Object { Say "  $_" } } catch { Say "  text-entry check: $($_.Exception.Message)" 'Yellow' }
        # 2. the installer
        $argv = @('-GameDir', $game, '-DgVoodooDir', (Join-Path $here 'dgVoodoo'), '-AhkDir', (Join-Path $here 'AutoHotkey'), '-Preset', $Preset, '-NoShortcut', '-Display', "${W}x${H}")
        if ($narrow) { $argv += '-AllowNarrow' }
        $rc = Child (Join-Path $repo 'setup-windows.ps1') $argv
        if ($rc -ne 0) { Fail "setup-windows.ps1 exited $rc - read the lines above; nothing more was done" }
        Set-Content -LiteralPath $stampFile -Value $version -Encoding ascii
        Remove-Item -LiteralPath $dispFile -Force -ErrorAction SilentlyContinue
        Say "=== setup done ===" 'Green'
    }
}

# ---- the display, every run --------------------------------------------------------------------------------------------
$dispStamp = "${W}x${H} scale $scale"
$was = if (Test-Path -LiteralPath $dispFile) { (Get-Content $dispFile -TotalCount 1).Trim() } else { '' }
if ($was -ne $dispStamp -or -not (Test-Path -LiteralPath (Join-Path $game 'dgVoodoo.wide.conf'))) {
    Say "display: ${W}x${H} ($from), render target x$scale$(if ($narrow) { ' (4:3 or narrower: nothing widened)' })" 'Cyan'
    if (-not $DryRun) {
        $wa = @{ GameDir = $game; Width = $W; Height = $H; Scale = $scale; Presets = @('tick19-42', 'scott-preview', 'best-wide', 'best-wide-balanced') }
        if ($narrow) { $wa['AllowNarrow'] = $true }
        $global:LASTEXITCODE = 0
        & (Join-Path $repo 'tools\Make-Wide-Conf.ps1') @wa 2>&1 | ForEach-Object { Say "  $_" }
        if ($LASTEXITCODE -or -not (Test-Path -LiteralPath (Join-Path $game 'dgVoodoo.wide.conf'))) { Fail 'the display conf could not be written (see above)' }
        Set-Content -LiteralPath $dispFile -Value $dispStamp -Encoding ascii
    }
}
if (-not $DryRun) { Copy-Item -LiteralPath (Join-Path $game 'dgVoodoo.wide.conf') -Destination (Join-Path $game 'dgVoodoo.conf') -Force }
if (Test-Path -LiteralPath (Join-Path $env:APPDATA 'dgVoodoo\dgVoodoo.conf')) {
    Say "note: $env:APPDATA\dgVoodoo\dgVoodoo.conf exists; dgVoodoo uses it silently if it ever rejects the game folder's conf (a 4:3 picture or a 3dfx logo is the sign)." 'Yellow'
}
Say "ready: preset $Preset, ${W}x${H} x$scale" 'DarkGray'
exit 0
