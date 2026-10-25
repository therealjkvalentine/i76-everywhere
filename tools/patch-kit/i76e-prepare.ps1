<#
  i76e-prepare.ps1 - what PLAY.bat / PLAY-PREVIEW.bat / PLAY-Nitro.bat of the Patch Kit run BEFORE the game starts (tester build
  2026-10-23, tools\package-patch-kit.ps1 puts this file and its payload in <game>\_i76e\, the .bat files beside the exe).

  The folder decides the game: i76.exe = Interstate '76 Gold (GOG), nitro.exe = the Nitro Pack (GOG) (2026-10-25: the kit covers
  Nitro with the same prebuilt proxy, no compiler; -Game forces one).

  1. First run (or an updated overlay, or -Resetup): the one-time setup = this repo's own installer, setup-windows.ps1,
     run on the game folder the _i76e folder sits in: dgVoodoo 2.87.5 (from _i76e\dgVoodoo), the proxy Strlkup.dll,
     the shell keyboard patches (Apply-Shell-Keys.ps1: i76shell.dll + fix-shell-textentry.ps1 on Gold, nitshell.dll on Nitro),
     u32x (Gold only: import rename of i76.exe + i76shell.dll), the control map (Gold: this project's; Nitro: GOG's keys + the
     minimal patch), the presets. Originals are kept beside every changed file (i76.exe.u32xorig, i76shell.dll.pre-i76e-keys /
     .orig, nitshell.dll.pre-i76e-keys, strlkup_orig.dll, input.map.stock-* / .pre-windows-setup, _openglide-backup\). Nothing
     outside the game folder is written (no shortcut, no registry).
  2. Every run: the primary monitor's size is read (-Display WxH overrides it; a Remote Desktop session is refused)
     and, when it differs from the last run (or -NoSupersample changed), tools\Make-Wide-Conf.ps1 rewrites
     dgVoodoo.wide.conf ([Glide] render target = 2x the display per axis, 1x with -NoSupersample; stretched_ar at the
     display's own shape, so 21:9 / 16:9 / 16:10 / 4:3 all get a correct picture) and the presets' I76_ASPECT /
     I76_U32X_MENU_ASPECT. Then dgVoodoo.wide.conf -> dgVoodoo.conf.
  The .bat then starts PLAY-i76.ps1 -Preset <x> itself (exit 0 here = go; anything else = do not start).
  Since 2026-10-25 the render scale and antialiasing are also preset keys (I76_RENDER_SCALE 1 / 1.5 / 2, I76_AA 0 / 2 / 4 / 8, in
  presets\local.psd1 like every graphics key): PLAY-i76.ps1 applies them over the conf written here (it reads this folder's
  display.txt for the display). --no-supersample stays as the alias: this script writes the 1x conf, the .bat passes
  PLAY-i76.ps1 -RenderScale 1 (docs\records\RENDER-KEYS-2026-10-25.md).

  The window (clean-install fixes 2026-10-25): the user sees a short summary - what was installed, the monitor and the field of
  view, how to launch, how to undo - and "Press any key"; every line of the setup scripts goes to _i76e\setup.log (on a failure
  the window shows the log's last lines). No pause with -NoPause, I76E_NO_PAUSE=1, or when the output is redirected (harnesses).

    i76e-prepare.ps1 [-Game auto|Gold|Nitro] [-Preset tick19-42] [-NoSupersample] [-Display 1920x1080] [-Resetup] [-SetupOnly] [-NoPause] [-DryRun]
    i76e-prepare.ps1 -Uninstall        put the originals back and remove what the setup added (the _i76e folder,
                                       PLAY*.bat and README-PATCH-KIT.md are left for the user to delete)
#>
param([ValidateSet('auto', 'Gold', 'Nitro')][string]$Game = 'auto', [string]$Preset = '', [switch]$NoSupersample, [string]$Display = '',
      [switch]$Resetup, [switch]$Uninstall, [switch]$SetupOnly, [switch]$NoPause, [switch]$DryRun)
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot; $gameDir = Split-Path -Parent $here; $repo = Join-Path $here 'repo'
$logFile = Join-Path $here 'setup.log'
function Log([string]$m) { try { Add-Content -LiteralPath $logFile -Value ("{0}  {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $m) -Encoding ascii } catch { } }
function Say([string]$m, [string]$c = 'Gray') { Write-Host $m -ForegroundColor $c; Log $m }
function Fail([string]$m) {
    Write-Host ''; Write-Host "i76e: $m" -ForegroundColor Red; Log "FAIL: $m"
    if (Test-Path -LiteralPath $logFile) {
        Write-Host ''; Write-Host "The last lines of _i76e\setup.log:" -ForegroundColor DarkGray
        Get-Content -LiteralPath $logFile -Tail 15 | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkGray }
    }
    Write-Host 'The game was not started. README-PATCH-KIT.md, "If something goes wrong", has the usual causes.' -ForegroundColor Red; exit 1
}
function Running-Here { # the game started from THIS folder (another copy elsewhere on the PC does not lock our files)
    return @(Get-Process i76, nitro -ErrorAction SilentlyContinue | Where-Object { $_.Path -and $_.Path.StartsWith($gameDir + '\', [StringComparison]::OrdinalIgnoreCase) }).Count -gt 0
}
function Child([string]$script, [string[]]$argv) {
    # the repo scripts call exit freely: run each as its own powershell and read its exit code; its lines go to setup.log only
    # Continue here: under 'Stop' the first stderr line of a child (PS 5.1 wraps it as an error record) ended THIS script (uninstall 2026-10-23)
    $ErrorActionPreference = 'Continue'; $global:LASTEXITCODE = 0
    Log "> $(Split-Path -Leaf $script) $($argv -join ' ')"
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $script @argv 2>&1 | ForEach-Object { Log "  $_" }
    $rc = $LASTEXITCODE; Log "< exit $rc"
    return $rc
}

# ---- which game ------------------------------------------------------------------------------------------------------
$hasGold = Test-Path -LiteralPath (Join-Path $gameDir 'i76.exe'); $hasNitro = Test-Path -LiteralPath (Join-Path $gameDir 'nitro.exe')
$kind = $Game
if ($kind -eq 'auto') { $kind = if ($hasGold) { 'Gold' } elseif ($hasNitro) { 'Nitro' } else { '' } }
# the half that is absent: a plain message, nothing changed, no log dump (owner 2026-10-25: Gold-only, Nitro-only and both work)
function Absent([string]$m) { Write-Host ''; Write-Host "  $m" -ForegroundColor Yellow; Write-Host '  Nothing was changed in this folder.' -ForegroundColor Yellow; Log "absent: $m"; exit 3 }
if (-not $kind) { Absent "This folder ($gameDir) has neither i76.exe (Interstate '76 Gold) nor nitro.exe (the Nitro Pack). Unzip the kit INTO your game folder: the one that holds i76.exe, or the one that holds nitro.exe (or both, one copy each)." }
if ($kind -eq 'Nitro' -and -not $hasNitro) { Absent "PLAY-Nitro.bat is for the Nitro Pack folder (the one with nitro.exe). This is the Interstate '76 Gold folder: start PLAY.bat here. To set up the Nitro Pack too, unzip the kit into its folder as well." }
if ($kind -eq 'Gold' -and -not $hasGold) { Absent "This folder has no i76.exe$(if ($hasNitro) { ": it is the Nitro Pack folder - start PLAY-Nitro.bat here" })." }
$isNitro = ($kind -eq 'Nitro')
$exeName = if ($isNitro) { 'nitro.exe' } else { 'i76.exe' }
$gameName = if ($isNitro) { "Interstate '76 Nitro Pack" } else { "Interstate '76 Gold" }
if (-not $Preset) { $Preset = if ($isNitro) { 'nitro-tick42' } else { 'tick19-42' } }
if ($isNitro -and $Preset -ne 'nitro-tick42' -and $Preset -ne 'stock') { $Preset = 'nitro-tick42' }   # a Gold preset name from an old .bat
$widePresets = if ($isNitro) { @('nitro-tick42') } else { @('tick19-42', 'preview', 'best-wide', 'best-wide-balanced') }

$version = (Get-Content (Join-Path $here 'VERSION.txt') -TotalCount 1).Trim()
# Mark of the Web: a zip downloaded from GitHub and extracted without ticking Unblock tags every file (Zone.Identifier), and
# Copy-Item carries the tag to the deployed copies (_ahk\AutoHotkeyU32.exe, the dgVoodoo DLLs; seen on lab the lab motw copy
# 2026-10-23). A tagged exe started by the launcher can stop on Windows' "Open File - Security Warning" behind the game. The
# folder is the user's own game folder; removing the tag changes no file's content.
if (-not $DryRun) { Get-ChildItem -LiteralPath $gameDir -Recurse -File -ErrorAction SilentlyContinue | Unblock-File -ErrorAction SilentlyContinue }
$stampFile = Join-Path $here 'installed.txt'; $dispFile = Join-Path $here 'display.txt'
Log "==== i76e-prepare $version, $gameName, $gameDir, $(if ($Uninstall) { 'uninstall' } else { "preset $Preset" })"

# ---- uninstall ---------------------------------------------------------------------------------------------------
if ($Uninstall) {
    Say "Removing the i76-everywhere Patch Kit ($version) from $gameDir ..." 'Cyan'
    if (Running-Here) { Fail 'close the game first' }
    if (Test-Path -LiteralPath (Join-Path $here 'extras-installed.txt')) { [void](Child (Join-Path $here 'i76e-extras.ps1') @('-GameDir', $gameDir, '-Uninstall')) }   # INSTALL-EXTRAS.bat's maps / opentrack / Python / voices
    if (Test-Path -LiteralPath (Join-Path $gameDir 'i76.exe.u32xorig')) { [void](Child (Join-Path $repo 'u32x\deploy-u32x.ps1') @('-GameDir', $gameDir, '-U32xDll', (Join-Path $repo 'u32x\u32x_full.dll'), '-Restore')) }   # -U32xDll explicit: PS 5.1 -File leaves $PSScriptRoot empty in its param default
    foreach ($sh in 'i76shell.dll', 'nitshell.dll') {
        if (Test-Path -LiteralPath (Join-Path $gameDir "$sh.pre-i76e-keys")) { [void](Child (Join-Path $repo 'tools\patch-kit\Apply-Shell-Keys.ps1') @('-GameDir', $gameDir, '-Shell', $sh, '-Revert')) }
    }
    foreach ($pair in @(@('strlkup_orig.dll', 'Strlkup.dll'), @('I76PATCH.DLL.disabled', 'I76PATCH.DLL'))) {
        $from = Join-Path $gameDir $pair[0]
        if (Test-Path -LiteralPath $from) { Move-Item -LiteralPath $from -Destination (Join-Path $gameDir $pair[1]) -Force; Log "  $($pair[1]) restored" }
    }
    $defo = Join-Path $gameDir 'I76PLYR.DEF.pre-i76e'
    if (Test-Path -LiteralPath $defo) { Move-Item -LiteralPath $defo -Destination (Join-Path $gameDir 'I76PLYR.DEF') -Force; Log "  I76PLYR.DEF restored (graphic detail options as before the setup)" }
    # GOG's own control map: input.map.stock-* (Gold, this project's map was installed) or input.map.pre-windows-setup (Nitro: GOG's
    # keys + the minimal patch)
    $stock = Get-ChildItem -LiteralPath $gameDir -Filter 'input.map.stock-*' -File | Sort-Object Name | Select-Object -First 1
    if (-not $stock) { $stock = Get-Item -LiteralPath (Join-Path $gameDir 'input.map.pre-windows-setup') -ErrorAction SilentlyContinue }
    if ($stock) { Copy-Item -LiteralPath $stock.FullName -Destination (Join-Path $gameDir 'input.map') -Force; Log "  input.map restored from $($stock.Name)" }
    foreach ($n in 'Glide.dll', 'Glide2x.dll', 'Glide3x.dll', 'DDraw.dll', 'D3DImm.dll', 'D3D8.dll', 'D3D9.dll', 'dgVoodooCpl.exe', 'dgVoodoo.conf', 'dgVoodoo.16x10.conf', 'dgVoodoo.wide.conf',
                   'u32x.dll', 'i76wheel.exe', 'PLAY-i76.ps1', 'PLAY-i76.bat', 'PLAY-16x10.bat', 'PLAY-balanced.bat', 'PLAY-stock.bat', 'DEBUG.bat', 'TRAINER.bat',
                   'strlkup-proxy-build.txt', 'i76e-controls.txt', 'input.map.as-installed', 'mciproxy.log', 'u32x.log', 'play-i76.log') {
        Remove-Item -LiteralPath (Join-Path $gameDir $n) -Force -ErrorAction SilentlyContinue
    }
    $ogb = Join-Path $gameDir '_openglide-backup'
    if (Test-Path -LiteralPath $ogb) {
        Get-ChildItem -LiteralPath $ogb -File | ForEach-Object { Move-Item -LiteralPath $_.FullName -Destination (Join-Path $gameDir $_.Name) -Force; Log "  $($_.Name) restored" }
        Remove-Item -LiteralPath $ogb -Recurse -Force -ErrorAction SilentlyContinue
    }
    foreach ($d in 'presets', '_ahk', '_tools') { Remove-Item -LiteralPath (Join-Path $gameDir $d) -Recurse -Force -ErrorAction SilentlyContinue }
    Remove-Item -LiteralPath $stampFile, $dispFile -Force -ErrorAction SilentlyContinue
    Say "Done: the game files are back the way GOG installed them." 'Green'
    Say "Left for you to delete: PLAY.bat, PLAY-PREVIEW.bat, PLAY-T05.bat, PLAY-PREVIEW-T05.bat, PLAY-Nitro.bat, UNINSTALL-i76e.bat, INSTALL-EXTRAS.bat,"
    Say "README-PATCH-KIT.md and the _i76e folder. The backups beside the game files (*.u32xorig, *.orig, *.pre-i76e-keys, input.map.stock-*,"
    Say "input.map.pre-windows-setup) are safe to delete too. GOG Galaxy's 'verify / repair' also restores everything."
    exit 0
}

# ---- session + display -----------------------------------------------------------------------------------------------
Add-Type -AssemblyName System.Windows.Forms
$isRdp = $false; try { $isRdp = [System.Windows.Forms.SystemInformation]::TerminalServerSession } catch { }
if ($isRdp -and -not $DryRun) { Fail "this is a Remote Desktop session: the game's 3D cannot start over Remote Desktop (it sits on a black screen forever). Start it at the PC itself." }
if ($Display) {
    if ($Display -notmatch '^(\d+)x(\d+)$') { Fail "--display wants WIDTHxHEIGHT, e.g. 1920x1080 (got '$Display')" }
    $W = [int]$Matches[1]; $H = [int]$Matches[2]; $from = '--display'
} else {
    $b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds; $W = $b.Width; $H = $b.Height; $from = 'your primary monitor'
}
if ($W -lt 640 -or $H -lt 480) { Fail "display ${W}x${H} is smaller than 640x480" }
$scale = if ($NoSupersample) { 1 } else { 2 }
$narrow = (($W / $H) -le (4.0 / 3.0 + 0.01))

# ---- one-time setup ----------------------------------------------------------------------------------------------------
$installed = if (Test-Path -LiteralPath $stampFile) { (Get-Content $stampFile -TotalCount 1).Trim() } else { '' }
$need = $Resetup -or ($installed -ne "$version $kind") -or
        -not (Test-Path -LiteralPath (Join-Path $gameDir 'strlkup_orig.dll')) -or
        (-not $isNitro -and -not (Test-Path -LiteralPath (Join-Path $gameDir 'u32x.dll'))) -or
        -not (Test-Path -LiteralPath (Join-Path $gameDir "presets\$Preset.psd1")) -or -not (Test-Path -LiteralPath (Join-Path $gameDir 'PLAY-i76.ps1'))
$didSetup = $false; $detail = ''
if ($need) {
    Say "Setting up the i76-everywhere Patch Kit for $gameName (a few seconds) ..." 'Cyan'
    Log "    display ${W}x${H} ($from); originals are kept beside every file that changes; nothing outside this folder is written."
    if ($DryRun) { Say '  (dry run: nothing written)' 'Yellow' }
    else {
        if (Running-Here) { Fail 'close the running game first' }
        # 1. the shell patches, before u32x renames the shell's import (the patch is keyed by the stock md5)
        $shell = if ($isNitro) { 'nitshell.dll' } else { 'i76shell.dll' }
        $rc = Child (Join-Path $repo 'tools\patch-kit\Apply-Shell-Keys.ps1') @('-GameDir', $gameDir, '-Shell', $shell)
        if ($rc -ne 0 -and $rc -ne 2) { Fail "Apply-Shell-Keys.ps1 exited $rc" }
        $shellKeys = ($rc -eq 0)
        if (-not $isNitro) {
            try { & (Join-Path $repo 'tools\fix-shell-textentry.ps1') -GameDir $gameDir *>&1 | ForEach-Object { Log "  $_" } } catch { Log "  text-entry check: $($_.Exception.Message)" }
        }
        # 2. the installer
        $argv = @('-GameDir', $gameDir, '-DgVoodooDir', (Join-Path $here 'dgVoodoo'), '-Preset', $Preset, '-NoShortcut', '-Display', "${W}x${H}")
        if ($isNitro) { $argv += @('-Exe', 'nitro.exe', '-Controls', 'stock', '-NoLauncher') }   # GOG's Nitro keys (+ the minimal patch); PLAY-Nitro.bat is the kit's
        else { $argv += @('-AhkDir', (Join-Path $here 'AutoHotkey')) }
        if ($narrow) { $argv += '-AllowNarrow' }
        $rc = Child (Join-Path $repo 'setup-windows.ps1') $argv
        if ($rc -ne 0) { Fail "setup-windows.ps1 exited $rc - nothing more was done" }
        # 3. Gold: the graphic-detail options at the developer's levels, ONLY when the options file still holds GOG's defaults.
        #    I76PLYR.DEF is the exe's 96-byte options block (i76-map data\FORMATS.md s.10). A fresh GOG 2.1.0.17 install has
        #    +0x4A / +0x4D / +0x4E = 1 / 1 / 0, the release candidate 2 / 2 / 1; at the GOG values the rear-view mirror is at its
        #    middle level, objects only on a flat sky-coloured background (MIRROR-DETAIL-2026-10-23 s.1: the 300 m / 1000 m mirror
        #    and the preview's mirror textures never show). Seen on a lab test copy 2026-10-23: flat mirror at 1/1/0, road, terrain and
        #    clouds in it at 2/2/1. Original kept as I76PLYR.DEF.pre-i76e; the game's Options > Graphic Detail menu changes them later.
        $def = Join-Path $gameDir 'I76PLYR.DEF'
        if (-not $isNitro -and (Test-Path -LiteralPath $def)) {
            $ob = [IO.File]::ReadAllBytes($def)
            if ($ob.Length -eq 96 -and $ob[0x4A] -eq 1 -and $ob[0x4D] -eq 1 -and $ob[0x4E] -eq 0) {
                if (-not (Test-Path -LiteralPath "$def.pre-i76e")) { Copy-Item -LiteralPath $def -Destination "$def.pre-i76e" }
                $ob[0x4A] = 2; $ob[0x4D] = 2; $ob[0x4E] = 1; [IO.File]::WriteAllBytes($def, $ob)
                $rb = [IO.File]::ReadAllBytes($def)
                if ($rb[0x4A] -eq 2 -and $rb[0x4D] -eq 2 -and $rb[0x4E] -eq 1) { Log "  graphic detail: GOG's defaults -> the developer's levels (rear mirror full: road + terrain in it); original I76PLYR.DEF.pre-i76e"; $detail = 'graphic detail raised (the rear mirror shows road and terrain)' }
                else { Log "  graphic detail: the write did not read back - left as it was"; Copy-Item -LiteralPath "$def.pre-i76e" -Destination $def -Force }
            } else { Log "  graphic detail: your own settings kept (I76PLYR.DEF is not GOG's default)" }
        }
        Set-Content -LiteralPath $stampFile -Value "$version $kind" -Encoding ascii
        Remove-Item -LiteralPath $dispFile -Force -ErrorAction SilentlyContinue
        Log "=== setup done ==="
        $didSetup = $true
    }
}

# ---- the display, every run --------------------------------------------------------------------------------------------
$dispStamp = "${W}x${H} scale $scale"
$was = if (Test-Path -LiteralPath $dispFile) { (Get-Content $dispFile -TotalCount 1).Trim() } else { '' }
if ($was -ne $dispStamp -or -not (Test-Path -LiteralPath (Join-Path $gameDir 'dgVoodoo.wide.conf'))) {
    $m = "display: ${W}x${H} ($from), render target x$scale$(if ($narrow) { ' (4:3 or narrower: nothing widened)' })"
    if ($didSetup -or -not $was) { Log $m } else { Say "Your display changed: the picture is now sized for ${W}x${H} ($from)." 'Cyan'; Log $m }
    if (-not $DryRun) {
        $wa = @{ GameDir = $gameDir; Width = $W; Height = $H; Scale = $scale; Presets = $widePresets }
        if ($narrow) { $wa['AllowNarrow'] = $true }
        $global:LASTEXITCODE = 0
        Log "> Make-Wide-Conf.ps1 ${W}x${H} x$scale presets $($widePresets -join ',')"
        & (Join-Path $repo 'tools\Make-Wide-Conf.ps1') @wa *>&1 | ForEach-Object { Log "  $_" }
        if ($LASTEXITCODE -or -not (Test-Path -LiteralPath (Join-Path $gameDir 'dgVoodoo.wide.conf'))) { Fail 'the display conf could not be written (see above)' }
        Set-Content -LiteralPath $dispFile -Value $dispStamp -Encoding ascii
    }
}
if (-not $DryRun) { Copy-Item -LiteralPath (Join-Path $gameDir 'dgVoodoo.wide.conf') -Destination (Join-Path $gameDir 'dgVoodoo.conf') -Force }
if (Test-Path -LiteralPath (Join-Path $env:APPDATA 'dgVoodoo\dgVoodoo.conf')) {
    Log "note: $env:APPDATA\dgVoodoo\dgVoodoo.conf exists; dgVoodoo uses it silently if it ever rejects the game folder's conf (a 4:3 picture or a 3dfx logo is the sign)."
}
Log "ready: $gameName, preset $Preset, ${W}x${H} x$scale"

# ---- the first-run summary: what the user needs, nothing else -------------------------------------------------------------
if ($didSetup -or $SetupOnly) {
    # the field of view this monitor gets (the proxy's Hor+ maths, as PLAY-i76.ps1 logs it): base I76_FOV at 4:3, stock 90
    $fov = 90.0
    foreach ($pf in @((Join-Path $gameDir "presets\$Preset.psd1"), (Join-Path $gameDir 'presets\local.psd1'))) {
        try { if (Test-Path -LiteralPath $pf) { $e = (Import-PowerShellDataFile -LiteralPath $pf).Env; if ($e -and $e['I76_FOV']) { $fov = [double]"$($e['I76_FOV'])" } } } catch { }
    }
    $aspD = if ($narrow) { 4.0 / 3.0 } else { $W / $H }
    $fovW = 2.0 * [Math]::Atan(0.75 * $aspD * [Math]::Tan($fov / 2.0 * [Math]::PI / 180.0)) * 180.0 / [Math]::PI
    $g = $W; $h2 = $H; while ($h2) { $t = $g % $h2; $g = $h2; $h2 = $t }
    $shape = "$($W / $g):$($H / $g)"; if ($shape -eq '64:27' -or $shape -eq '43:18') { $shape = '21:9' } elseif ($shape -eq '8:5') { $shape = '16:10' }
    Write-Host ''
    Write-Host "  Interstate '76 Patch Kit ($($version -replace '^patch-kit-v', 'v')) is set up for $gameName." -ForegroundColor Green
    Write-Host ''
    Write-Host '  Installed in this folder:'
    Write-Host '    - smooth frame rate (up to 120 fps) with the 1997 driving physics kept'
    Write-Host '    - widescreen picture and dgVoodoo graphics (sharper, longer view distance)'
    if (-not $isNitro) {
        Write-Host '    - the menu mouse fix and keyboard answers in the menus (Enter / Y / N / Esc)'
        Write-Host '    - this project''s controls: W A S D drive, arrow keys look (README-PATCH-KIT.md has the full list)'
        Write-Host '    - gamepad / wheel button layer (plug the controller in before starting)'
        if ($detail) { Write-Host "    - $detail" }
    } else {
        Write-Host '    - keyboard answers in the menus (Enter / Y / N / Esc)'
        Write-Host '    - GOG''s own Nitro keys, plus mouse buttons and gamepad stick / buttons 1, 3, 4'
    }
    Write-Host ''
    Write-Host ("  Your monitor: {0}x{1} ({2}, from {3}); the 3D is drawn at {4}x{5}{6}." -f $W, $H, $shape, $from, ($W * $scale), ($H * $scale), $(if ($scale -eq 2) { ' (2x: smoother edges)' } else { '' }))
    Write-Host ("  Field of view: {0:0} degrees across ({1:0} at the old 4:3 shape) - more to the sides, nothing stretched." -f $fovW, $fov)
    Write-Host ''
    $bat = if ($isNitro) { 'PLAY-Nitro.bat' } else { 'PLAY.bat' }
    Write-Host "  To play: double-click $bat in this folder (it checks your monitor each time and starts the game)."
    if (-not $isNitro) { Write-Host '           PLAY-PREVIEW.bat = the same with the graphics preview; PLAY-T05.bat = straight into mission 5.' }
    Write-Host '  To undo: double-click UNINSTALL-i76e.bat - it puts every original game file back.'
    Write-Host '  Details of this setup: _i76e\setup.log'
    Write-Host ''
}
$canPause = -not $NoPause -and -not $env:I76E_NO_PAUSE -and -not $DryRun
try { if ([Console]::IsOutputRedirected -or [Console]::IsInputRedirected) { $canPause = $false } } catch { $canPause = $false }
if (($didSetup -or $SetupOnly) -and $canPause) {
    Write-Host $(if ($SetupOnly) { '  Press any key to close this window . . .' } else { '  Press any key to start the game . . .' }) -ForegroundColor Cyan
    try { [void]$Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown') } catch { }
}
exit 0
