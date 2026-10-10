<#
  Make-Wide-Conf.ps1 - the widescreen half of preset best-wide, for ONE installed game folder.

  best-wide (presets\best-wide.psd1) widens the camera (I76_ASPECT, Hor+), but the game still renders a
  640x480 frame, so dgVoodoo has to present it stretched to the display's shape. That needs two things
  per display, and this script writes both into the game folder:

    1. <GameDir>\dgVoodoo.wide.conf, derived from the folder's own accepted conf
       (dgVoodoo.16x10.conf if present, else dgVoodoo.conf). At most three lines change:
         [General] ScalingMode  = stretched             (was stretched_ar: keep the app's 4:3)
         [General] CaptureMouse = false                 (since promotion 15, 2026-10-08; the 16:10 conf keeps true)
         [Glide]   Resolution   = <Wi>x<Hi>             (display aspect, Hi = -InternalHeight, default 2160)
       Every other byte is kept: dgVoodoo 2.87.3 REJECTS the whole file over one line it does not like and
       silently falls back to %APPDATA%\dgVoodoo\dgVoodoo.conf (lab docs\DGVOODOO-CONF-REJECTED.md), so the
       output is checked to equal the source apart from those three values.
       Why CaptureMouse = false, for this stretched wide conf ONLY: the wide presets (best-wide,
       best-wide-balanced) map the menu pointer themselves since promotion 15 - the proxy's I76_CURSOR_MAP
       (+ I76_CURSOR_MAP_U32X=exe, I76_CURSOR_MAP_DGV) and u32x 06467bd2's I76_U32X_SHELL_STRETCH translate the
       real pointer through the stretched picture. With CaptureMouse = true dgVoodoo clips the OS pointer to a
       640x480 box at the screen's top left and draws an emulated arrow, so the drawn pointer and the real one
       disagree (u32x/README.md, 2026-10-07 note; golden PROMOTIONS.md row 15: dgVoodoo.wide.conf 907a31a4 ->
       ac0ecdeb). The 16:10 conf is not touched: PLAY-16x10.bat runs best-120, which sets no cursor map.
       On a 16:10 source equal to the driver's dgVoodoo.16x10.conf (299a6811) and a 3440x1440 display the
       output is byte-equal to the driver's dgVoodoo.wide.conf (ac0ecdeb).
       2160 internal lines is what the daily driver runs on its 3440x1440 panel (5160x2160, 1.5x the panel,
       measured 120 fps on a GTX 1080 Ti); on a 1080-line display it is 2x. Nothing else has been run.
    2. <GameDir>\presets\best-wide.psd1 and best-wide-balanced.psd1 (each one present) with
       I76_ASPECT = '<W>x<H>' and I76_U32X_MENU_ASPECT = '<W>:<H>' for this display. The repo copy hard-codes the owner's 3440x1440; PLAY-i76.ps1 applies a preset's
       values over the environment, so the per-install copy is the way to change them.

  It does NOT copy the wide conf over dgVoodoo.conf: the launcher .bat does that before each start
  (setup-windows.ps1 -Preset best-wide writes PLAY-i76.bat that way, as on the daily driver).

  Status: offline only. The generated files were checked on a scratch copy (parse, two-line diff, preset
  loads; 2026-10-10 with the CaptureMouse line: three-line diff, output md5 = the driver's ac0ecdeb); widescreen has been PLAYED only on 3440x1440. Menus, cutscenes and 2D text stay stretched to the
  display's shape (dgVoodoo applies one presentation config per process; lab docs\WIDESCREEN-2D.md).

  Usage:
    tools\Make-Wide-Conf.ps1 -GameDir "C:\GOG Games\Interstate 76"                  # primary display
    tools\Make-Wide-Conf.ps1 -GameDir <dir> -Width 2560 -Height 1080 [-InternalHeight 2160] [-WhatIf]
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string]$GameDir,
    [int]$Width = 0,            # display width in pixels; 0 = the primary display
    [int]$Height = 0,
    [string]$SourceConf = '',   # default: <GameDir>\dgVoodoo.16x10.conf, else <GameDir>\dgVoodoo.conf
    [ValidateRange(480, 4320)] [int]$InternalHeight = 2160,
    [switch]$NoPreset,          # write only the conf
    [switch]$WhatIf             # print what would be written, write nothing
)
$ErrorActionPreference = 'Stop'
function Die([string]$m) { Write-Host "Make-Wide-Conf: $m" -ForegroundColor Red; exit 1 }

if (-not (Test-Path -LiteralPath $GameDir)) { Die "game folder not found: $GameDir" }
if ($Width -le 0 -or $Height -le 0) {
    try {
        Add-Type -AssemblyName System.Windows.Forms -ErrorAction Stop
        $b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
        $Width = $b.Width; $Height = $b.Height
    } catch { Die "could not read the display size; pass -Width and -Height" }
}
$aspect = $Width / $Height
if ($aspect -le (4.0 / 3.0 + 0.01)) { Die "display ${Width}x${Height} (aspect $([Math]::Round($aspect,3))) is not wider than 4:3; best-wide has nothing to widen. Use best-120." }

if (-not $SourceConf) {
    $SourceConf = @('dgVoodoo.16x10.conf', 'dgVoodoo.conf') | ForEach-Object { Join-Path $GameDir $_ } |
        Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $SourceConf) { Die "no dgVoodoo.16x10.conf or dgVoodoo.conf in $GameDir (run setup-windows.ps1 first)" }
}
$src = [IO.File]::ReadAllText($SourceConf, [Text.Encoding]::ASCII)

# internal render size: the display's shape at -InternalHeight lines, width even
$hi = $InternalHeight
$wi = [int]([Math]::Round($hi * $aspect / 2.0) * 2)

$scRx = New-Object regex '(?ms)(^\[General\]\s.*?^ScalingMode\s*= )[A-Za-z_]+'
$cmRx = New-Object regex '(?ms)(^\[General\]\s.*?^CaptureMouse\s*= )[A-Za-z]+'
$glRx = New-Object regex '(?ms)(^\[Glide\]\s.*?^Resolution\s*= )\d+x\d+'
if (-not $scRx.IsMatch($src)) { Die "$SourceConf has no [General] ScalingMode line" }
if (-not $cmRx.IsMatch($src)) { Die "$SourceConf has no [General] CaptureMouse line" }
if (-not $glRx.IsMatch($src)) { Die "$SourceConf has no [Glide] Resolution = WxH line" }
$out = $scRx.Replace($src, '${1}stretched', 1)
$out = $cmRx.Replace($out, '${1}false', 1)    # the wide presets' cursor map needs a free pointer (header)
$out = $glRx.Replace($out, ('${1}' + "${wi}x${hi}"), 1)

# Same shape or nothing: masking the three values must give back the source text exactly.
$mask = { param($t) (($t -replace '(?m)^(ScalingMode\s*= )[A-Za-z_]+', '$1') -replace '(?m)^(CaptureMouse\s*= )[A-Za-z]+', '$1') -replace '(?m)^(Resolution\s*= )\d+x\d+', '$1' }
if ((& $mask $out) -cne (& $mask $src)) { Die "internal error: the output differs from $SourceConf in more than the three values" }
$changed = @(Compare-Object ($src -split "`n") ($out -split "`n") | Where-Object SideIndicator -eq '=>').Count
if ($changed -gt 3) { Die "internal error: $changed lines changed (expected at most 3)" }

$confOut = Join-Path $GameDir 'dgVoodoo.wide.conf'
Write-Host ("display {0}x{1} (aspect {2:N3}); source {3}" -f $Width, $Height, $aspect, $SourceConf)
Write-Host "  dgVoodoo.wide.conf: ScalingMode = stretched, CaptureMouse = false, [Glide] Resolution = ${wi}x${hi}"
if ($WhatIf) { Write-Host "  -WhatIf: nothing written." } else {
    [IO.File]::WriteAllText($confOut, $out, [Text.Encoding]::ASCII)
    Write-Host "  written: $confOut"
}

if (-not $NoPreset) {
    $widePresets = @(@('best-wide', 'best-wide-balanced') | ForEach-Object { Join-Path $GameDir "presets\$_.psd1" } |
        Where-Object { Test-Path -LiteralPath $_ })
    if (-not $widePresets.Count) {
        Write-Host "  presets\best-wide.psd1 / best-wide-balanced.psd1 not in the game folder: no preset adjusted (setup-windows.ps1 copies them)." -ForegroundColor Yellow
    }
    foreach ($presetFile in $widePresets) {
        $presetName = Split-Path -Leaf $presetFile
        $p = [IO.File]::ReadAllText($presetFile)
        $aRx = New-Object regex "(?m)^(\s*I76_ASPECT\s*=\s*)'[^']*'"
        $mRx = New-Object regex "(?m)^(\s*I76_U32X_MENU_ASPECT\s*=\s*)'[^']*'"
        if (-not $aRx.IsMatch($p)) { Die "$presetFile has no I76_ASPECT line" }
        $p2 = $aRx.Replace($p, ('${1}' + "'${Width}x${Height}'"), 1)
        if ($mRx.IsMatch($p2)) { $p2 = $mRx.Replace($p2, ('${1}' + "'${Width}:${Height}'"), 1) }
        Write-Host "  presets\${presetName}: I76_ASPECT = '${Width}x${Height}', I76_U32X_MENU_ASPECT = '${Width}:${Height}'"
        if (-not $WhatIf) {
            if ($p2 -cne $p) {
                # keep the file's own form: a BOM only if it had one (the repo's presets are ASCII
                # without BOM, so the installed copy differs from the repo only in the two values)
                $raw = [IO.File]::ReadAllBytes($presetFile)
                $hadBom = ($raw.Length -ge 3 -and $raw[0] -eq 0xEF -and $raw[1] -eq 0xBB -and $raw[2] -eq 0xBF)
                [IO.File]::WriteAllText($presetFile, $p2, (New-Object Text.UTF8Encoding($hadBom)))
            }
            $d = Import-PowerShellDataFile -LiteralPath $presetFile   # read back: must still parse
            if ($d.Env.I76_ASPECT -ne "${Width}x${Height}") { Die "read-back of $presetFile gave I76_ASPECT '$($d.Env.I76_ASPECT)'" }
            Write-Host "  written and read back: $presetFile"
        }
    }
}
if ($Width -ne 3440 -or $Height -ne 1440) {
    Write-Host "  note: widescreen has only been played on 3440x1440. ${Width}x${Height} is computed, not tested." -ForegroundColor Yellow
}
