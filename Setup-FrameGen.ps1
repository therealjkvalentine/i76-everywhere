<#
  Interstate '76 - frame generation setup (Lossless Scaling), Windows.

  The engine's physics are hard-locked to a 20 FPS base and break above ~25, so
  the only route to a smoother picture is interpolating DISPLAY frames on top.
  That's what Lossless Scaling's LSFG does. Never raise dgVoodoo's FPSLimit to
  chase smoothness - that breaks the Mission 5 canyon jump.

  VERIFIED 2026-08-01 (docs/WINDOWS-PLAYBOOK.md sec 2): Lossless Scaling has NO
  Steam dependency. The install carries no steam_api64.dll and no Steamworks
  imports; launched directly it loads zero steam_api*/steamclient*/overlay
  modules and nothing from outside its own folder, and it keeps running with
  Steam fully shut down. Only the Steam-installed desktop shortcut
  (steam://rungameid/993090) was ever pulling Steam in.

  This script:
    1. finds LosslessScaling.exe across your Steam libraries
    2. adds an "Interstate '76 Gold Edition" profile with AutoScale=true and a
       fixed 2x multiplier, so frame-gen engages by itself when the game window
       appears - no Ctrl+Alt+S (idempotent; won't touch an existing one)
    3. optionally swaps the Steam-URL desktop shortcut for a direct one

  Usage:
    ./Setup-FrameGen.ps1                  # profile only
    ./Setup-FrameGen.ps1 -FixShortcut     # also replace the desktop shortcut
    ./Setup-FrameGen.ps1 -Revert          # remove the profile again

  Lossless Scaling must be CLOSED - it rewrites Settings.xml when it exits.
#>
param(
    [switch]$FixShortcut,
    [switch]$Revert
)
$ErrorActionPreference = 'Stop'
function Say($m, $c = 'Cyan') { Write-Host $m -ForegroundColor $c }

$TITLE = "Interstate '76 Gold Edition"   # matches the game's window title
$cfg = Join-Path $env:LOCALAPPDATA 'Lossless Scaling\Settings.xml'

# --- Lossless Scaling must not be running ------------------------------------
if (Get-Process -Name 'LosslessScaling' -ErrorAction SilentlyContinue) {
    Write-Host "Lossless Scaling is RUNNING - close it first (it rewrites Settings.xml on exit)." -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $cfg)) {
    Write-Host "No Settings.xml at $cfg" -ForegroundColor Red
    Write-Host "Install Lossless Scaling from Steam and launch it once, then re-run." -ForegroundColor Yellow
    exit 1
}

# --- locate the exe across all Steam libraries -------------------------------
function Find-LSExe {
    $roots = @("${env:ProgramFiles(x86)}\Steam")
    $vdf = "${env:ProgramFiles(x86)}\Steam\steamapps\libraryfolders.vdf"
    if (Test-Path $vdf) {
        foreach ($m in [regex]::Matches((Get-Content $vdf -Raw), '"path"\s+"([^"]+)"')) {
            $roots += $m.Groups[1].Value -replace '\\\\', '\'
        }
    }
    foreach ($r in ($roots | Select-Object -Unique)) {
        $p = Join-Path $r 'steamapps\common\Lossless Scaling\LosslessScaling.exe'
        if (Test-Path $p) { return $p }
    }
    return $null
}
$exe = Find-LSExe
if ($exe) { Say "Lossless Scaling: $exe" } else { Say "Lossless Scaling exe not found (profile can still be written)." 'Yellow' }

# --- the profile -------------------------------------------------------------
[xml]$xml = Get-Content $cfg -Raw
$profiles = $xml.Settings.GameProfiles
$existing = @($profiles.Profile | Where-Object { $_.Title -eq $TITLE })

if ($Revert) {
    if ($existing.Count -gt 0) {
        Copy-Item $cfg "$cfg.pre-revert" -Force
        $existing | ForEach-Object { $null = $profiles.RemoveChild($_) }
        $xml.Save($cfg)
        Say "Removed the '$TITLE' profile (backup: Settings.xml.pre-revert)." 'Green'
    } else { Say "No '$TITLE' profile present - nothing to revert." }
    exit 0
}

if ($existing.Count -gt 0) {
    Say "Profile '$TITLE' already present - leaving it alone."
} else {
    $template = @($profiles.Profile | Where-Object { $_.Title -eq 'Default' })[0]
    if (-not $template) { $template = @($profiles.Profile)[0] }
    if (-not $template) { Write-Host "No profile to use as a template." -ForegroundColor Red; exit 1 }

    Copy-Item $cfg "$cfg.pre-i76" -Force
    $new = $template.CloneNode($true)
    $new.Title           = $TITLE
    $new.AutoScale       = 'true'
    $new.ScalingType     = 'Off'      # frame generation only, no upscaling
    $new.FrameGeneration = 'LSFG3'
    $new.LSFG3Mode1      = 'FIXED'
    $new.LSFG3Multiplier = '2'        # 20 -> 40. x3 doubles the artifacts at a 20 base.
    $new.DrawFps         = 'true'     # proves the 20/40 split on screen
    $null = $profiles.AppendChild($new)
    $xml.Save($cfg)
    Say "Added profile '$TITLE' (AutoScale on, fixed 2x). Backup: Settings.xml.pre-i76" 'Green'
}

# --- desktop shortcut --------------------------------------------------------
if ($FixShortcut) {
    $desk = [Environment]::GetFolderPath('Desktop')
    $url  = Join-Path $desk 'Lossless Scaling.url'
    if (-not $exe) {
        Say "Skipping shortcut - exe not found." 'Yellow'
    } else {
        $sh = New-Object -ComObject WScript.Shell
        $lnk = $sh.CreateShortcut((Join-Path $desk 'Lossless Scaling.lnk'))
        $lnk.TargetPath       = $exe
        $lnk.WorkingDirectory = Split-Path $exe
        $lnk.Description      = 'Lossless Scaling (direct - no Steam)'
        # Reuse Steam's icon if it's still there, else the exe's own.
        $ico = $null
        if (Test-Path $url) {
            $m = [regex]::Match((Get-Content $url -Raw), 'IconFile=(.+)')
            if ($m.Success -and (Test-Path $m.Groups[1].Value.Trim())) { $ico = $m.Groups[1].Value.Trim() }
        }
        $lnk.IconLocation = if ($ico) { "$ico,0" } else { "$exe,0" }
        $lnk.Save()
        Say "Created 'Lossless Scaling.lnk' -> the exe directly." 'Green'
        if (Test-Path $url) {
            # Moved, not deleted - one click in Steam recreates it anyway.
            Move-Item $url (Join-Path $desk 'Lossless Scaling.url.bak') -Force
            Say "Old steam://rungameid shortcut moved to 'Lossless Scaling.url.bak'."
        }
    }
}

Say ""
Say "Done. Remaining manual step: set ForceVerticalSync = false in dgVoodoo.conf" 'Green'
Say "so Lossless Scaling owns presentation. PLAY-i76.ps1 starts/stops LS with the game."
Say "Expect artifacts - a 20 FPS base is below the ~30 the LS dev recommends; x2 is"
Say "the conservative choice and I76's slow desert is favourable content."
