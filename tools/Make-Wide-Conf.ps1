<#
  Make-Wide-Conf.ps1 - the widescreen half of preset best-wide, for ONE installed game folder.

  best-wide (presets\best-wide.psd1) widens the camera (I76_ASPECT, Hor+), but the game still renders a
  640x480 frame, so dgVoodoo has to present it at the display's shape. That needs two things per display,
  and this script writes both into the game folder:

    1. <GameDir>\dgVoodoo.wide.conf. Since promotion 16 (2026-10-12) it is the daily driver's widescreen conf
       tools\conf\dgVoodoo.daily-wide-ss2x-2026-10-12.conf (dccd379a: windowed borderless, [General]
       ScalingMode = stretched_ar, CaptureMouse = false, [Glide] 6880x2880 + 4x MSAA, TMU 8192), with at most
       the DIGITS of its two Resolution lines changed:
         [Glide]   Resolution = -Scale (default 2) x the display per axis, i.e. a real 2x2 supersample of the
                                borderless window. Each side is capped at -MaxSide (8192); a display that would
                                pass the cap gets a smaller factor on BOTH axes, so the render target keeps the
                                window's shape (under stretched_ar a different shape would put bars beside the
                                3D picture). Width and height are rounded down to even.
         [DirectX] Resolution = the [DirectX] line of the folder's own 16:10 conf (dgVoodoo.16x10.conf, which
                                setup-windows.ps1 sizes to the largest 16:10 mode that fits), so the two confs
                                agree on the 2D shell's mode; the template's 1680x1050 when there is none.
         [Glide]   Antialiasing = -Antialiasing when given (2026-10-25, owner: "Supersampling and AA probably need to be in the
                                graphics setting options"; PLAY-i76.ps1 passes the I76_AA preset key): off / 2x / 4x / 8x / 16x
                                (0 = off). Not given = the template's value (4x).
       Every other byte is the template's: dgVoodoo 2.87.3 REJECTS the whole file over one line it does not like
       and silently falls back to %APPDATA%\dgVoodoo\dgVoodoo.conf (lab docs\DGVOODOO-CONF-REJECTED.md), so the
       output is checked to equal the template apart from those digits. On a 3440x1440 display with a 1680x1050
       16:10 conf the output is byte-equal to the driver's dgVoodoo.wide.conf (dccd379a).
       Why stretched_ar at the window's own shape: the forced [Glide] resolution has the window's aspect, so _ar
       draws the 3D picture full width, while the 640x480 menus, garage, save screen and movies are shown 4:3
       with side bars instead of stretched sideways. u32x 06467bd2 reads ScalingMode from dgVoodoo.conf and maps
       the shell pointer over the 4:3 fit (owner, TEST-shimmer-S-win2x-ar 2026-10-12: "S looks pretty awesome";
       docs\records\TEXTURE-SHIMMER-2026-10-12.md). CaptureMouse = false because the wide presets map the menu
       pointer themselves (promotion 15: proxy I76_CURSOR_MAP, u32x I76_U32X_SHELL_STRETCH).
       Until 2026-10-12 this script derived the conf from the 16:10 one instead (ScalingMode stretched,
       [Glide] the display's shape at 2160 lines: 5160x2160 on 3440x1440 = the driver's ac0ecdeb).
    2. <GameDir>\presets\best-wide.psd1 and best-wide-balanced.psd1 (each one present) with
       I76_ASPECT = '<W>x<H>' and I76_U32X_MENU_ASPECT = '<W>:<H>' for this display. The repo copy hard-codes the
       owner's 3440x1440; PLAY-i76.ps1 applies a preset's values over the environment, so the per-install copy is
       the way to change them.

  It does NOT copy the wide conf over dgVoodoo.conf: the launcher .bat does that before each start
  (setup-windows.ps1 -Preset best-wide writes PLAY-i76.bat that way, as on the daily driver).

  Status: played only on 3440x1440 (6880x2880, GTX 1080 Ti, 113-115 fps in the promotion 16 gate). Other displays
  get computed digits. A bigger panel means a bigger render target (2x of 3840x2160 is 7680x4320, never measured);
  -Scale 1.5 or 1 gives a lighter conf.

  Usage:
    tools\Make-Wide-Conf.ps1 -GameDir "C:\GOG Games\Interstate 76"                  # primary display
    tools\Make-Wide-Conf.ps1 -GameDir <dir> -Width 2560 -Height 1080 [-Scale 2] [-Antialiasing 4] [-MaxSide 8192] [-WhatIf]
    PLAY-i76.ps1 (I76_RENDER_SCALE / I76_AA, docs\records\RENDER-KEYS-2026-10-25.md) calls it with -Template = the folder's own
    installed wide conf (dgVoodoo.wide.conf.pre-render-keys), -SourceConf = the same file and -NoPreset.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string]$GameDir,
    [int]$Width = 0,            # display width in pixels; 0 = the primary display
    [int]$Height = 0,
    # the conf whose bytes are kept (only the Resolution digits change): the driver's wide conf in the repo
    [string]$Template = '',     # default: conf\dgVoodoo.daily-wide-ss2x-2026-10-12.conf beside this script
    # the 16:10 conf the [DirectX] Resolution is taken from; default <GameDir>\dgVoodoo.16x10.conf if present
    [string]$SourceConf = '',
    [ValidateRange(1.0, 4.0)] [double]$Scale = 2.0,     # [Glide] Resolution = Scale x the display per axis
    [ValidateRange(1024, 16384)] [int]$MaxSide = 8192,  # cap per side (the factor then shrinks on both axes)
    # [Glide] Antialiasing (MSAA): '' = the template's; 0 / off, 2 / 2x, 4 / 4x, 8 / 8x, 16 / 16x
    [ValidateSet('', '0', 'off', '2', '2x', '4', '4x', '8', '8x', '16', '16x')] [string]$Antialiasing = '',
    [switch]$NoPreset,          # write only the conf
    # the presets in <GameDir>\presets whose I76_ASPECT / I76_U32X_MENU_ASPECT get this display (2026-10-23, tester build:
    # the tick presets carry the same two keys); names, or one "a,b" string from powershell -File
    [string[]]$Presets = @('best-wide', 'best-wide-balanced'),
    # 2026-10-23 (tester build): a display no wider than 4:3 gets the same conf at its own shape (stretched_ar at 4:3 = the
    # stock picture; the proxy ignores a 4:3 I76_ASPECT) instead of a refusal, so one launcher serves every monitor
    [switch]$AllowNarrow,
    [switch]$WhatIf             # print what would be written, write nothing
)
$ErrorActionPreference = 'Stop'
function Die([string]$m) { Write-Host "Make-Wide-Conf: $m" -ForegroundColor Red; exit 1 }

if (-not (Test-Path -LiteralPath $GameDir)) { Die "game folder not found: $GameDir" }
# set here, not as a param default: in Windows PowerShell 5.1 an advanced script started with -File sees an empty
# $PSScriptRoot in its param block (found 2026-10-12)
if (-not $Template) { $Template = Join-Path $PSScriptRoot 'conf\dgVoodoo.daily-wide-ss2x-2026-10-12.conf' }
if ($Width -le 0 -or $Height -le 0) {
    try {
        Add-Type -AssemblyName System.Windows.Forms -ErrorAction Stop
        $b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
        $Width = $b.Width; $Height = $b.Height
    } catch { Die "could not read the display size; pass -Width and -Height" }
}
$aspect = $Width / $Height
if ($aspect -le (4.0 / 3.0 + 0.01)) {
    if ($AllowNarrow) { Write-Host "display ${Width}x${Height} (aspect $([Math]::Round($aspect,3))) is not wider than 4:3: the conf takes its shape (a 4:3 picture, nothing widened; -AllowNarrow)." -ForegroundColor Yellow }
    else { Die "display ${Width}x${Height} (aspect $([Math]::Round($aspect,3))) is not wider than 4:3; best-wide has nothing to widen. Use best-120 (or -AllowNarrow)." }
}
$Presets = @($Presets | ForEach-Object { "$_" -split ',' } | ForEach-Object { $_.Trim() } | Where-Object { $_ } | Select-Object -Unique)

if (-not (Test-Path -LiteralPath $Template)) { Die "template conf not found: $Template" }
$tplBytes = [IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $Template).Path)
foreach ($b in $tplBytes) { if ($b -gt 127) { Die "$Template contains non-ASCII bytes" } }
$src = [Text.Encoding]::ASCII.GetString($tplBytes)
if (-not $SourceConf) {
    $c = Join-Path $GameDir 'dgVoodoo.16x10.conf'
    if (Test-Path -LiteralPath $c) { $SourceConf = $c }
}

# [Glide] render target: Scale x the display per axis, both sides <= MaxSide (one factor for both = same shape), even
$f = [Math]::Min($Scale, [Math]::Min($MaxSide / $Width, $MaxSide / $Height))
$wi = [int]([Math]::Floor($Width * $f / 2.0) * 2)
$hi = [int]([Math]::Floor($Height * $f / 2.0) * 2)

$glRx = New-Object regex '(?ms)(^\[Glide\]\s.*?^Resolution\s*= )\d+x\d+'
$dxRx = New-Object regex '(?ms)(^\[DirectX\]\s.*?^Resolution\s*= )(\d+x\d+)'
if (-not $glRx.IsMatch($src)) { Die "$Template has no [Glide] Resolution = WxH line" }
if (-not $dxRx.IsMatch($src)) { Die "$Template has no [DirectX] Resolution = WxH line" }
if ($src -notmatch '(?m)^ScalingMode\s*= stretched_ar\s*$') { Die "$Template is not a ScalingMode = stretched_ar conf" }
$dx = $dxRx.Match($src).Groups[2].Value; $dxFrom = 'the template'
if ($SourceConf) {
    if (-not (Test-Path -LiteralPath $SourceConf)) { Die "-SourceConf not found: $SourceConf" }
    $m = $dxRx.Match([IO.File]::ReadAllText($SourceConf, [Text.Encoding]::ASCII))
    if ($m.Success) { $dx = $m.Groups[2].Value; $dxFrom = (Split-Path -Leaf $SourceConf) }
}
$out = $glRx.Replace($src, ('${1}' + "${wi}x${hi}"), 1)
$out = $dxRx.Replace($out, ('${1}' + $dx), 1)

# [Glide] Antialiasing: the line must be inside the [Glide] section (no section header between the two)
$aaRx = New-Object regex '(?ms)(^\[Glide\]\s(?:(?!^\[).)*?^Antialiasing\s*= )(\S+)'
if (-not $aaRx.IsMatch($src)) { Die "$Template has no Antialiasing line in its [Glide] section" }
$aaWas = $aaRx.Match($src).Groups[2].Value
$aa = $aaWas
if ($Antialiasing) {
    $aa = switch ($Antialiasing) { { $_ -in '0', 'off' } { 'off' } default { ($Antialiasing -replace 'x$', '') + 'x' } }
    $out = $aaRx.Replace($out, ('${1}' + $aa), 1)
}

# Same shape or nothing: masking the Resolution digits and the Antialiasing value must give back the template text exactly.
$mask = { param($t) ($t -replace '(?m)^(Resolution\s*= )\d+x\d+', '$1') -replace '(?m)^(Antialiasing\s*= )\S+', '$1' }
if ((& $mask $out) -cne (& $mask $src)) { Die "internal error: the output differs from $Template in more than the Resolution digits and the Antialiasing value" }
$changed = @(Compare-Object ($src -split "`n") ($out -split "`n") | Where-Object SideIndicator -eq '=>').Count
if ($changed -gt 3) { Die "internal error: $changed lines changed (expected at most 3)" }

$confOut = Join-Path $GameDir 'dgVoodoo.wide.conf'
Write-Host ("display {0}x{1} (aspect {2:N3}); template {3}" -f $Width, $Height, $aspect, $Template)
$capNote = if ($f -lt $Scale) { (" (capped at {0} per side: factor {1:N3} on both axes)" -f $MaxSide, $f) } else { '' }
Write-Host "  dgVoodoo.wide.conf: ScalingMode = stretched_ar, CaptureMouse = false, [Glide] Resolution = ${wi}x${hi} = $Scale x the display$capNote, Antialiasing = $aa$(if ($aa -ne $aaWas) { " (template $aaWas)" }), [DirectX] Resolution = $dx (from $dxFrom)"
if ($WhatIf) { Write-Host "  -WhatIf: nothing written." } else {
    [IO.File]::WriteAllText($confOut, $out, [Text.Encoding]::ASCII)
    Write-Host "  written: $confOut"
}

if (-not $NoPreset) {
    $widePresets = @($Presets | ForEach-Object { Join-Path $GameDir "presets\$_.psd1" } |
        Where-Object { Test-Path -LiteralPath $_ })
    if (-not $widePresets.Count) {
        Write-Host "  none of presets\$($Presets -join ' / ') is in the game folder: no preset adjusted (setup-windows.ps1 copies them)." -ForegroundColor Yellow
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
