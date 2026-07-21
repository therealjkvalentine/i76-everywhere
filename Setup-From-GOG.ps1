<#
  Interstate '76 Everywhere - install straight from your GOG offline backup.

  You bring: the GOG offline installer(s) you downloaded from gog.com/account
             (setup_interstate76_*.exe, and optionally the Nitro Pack one).
  This does: silent-installs the game (+ Nitro Pack) from those .exe files, then
             applies every improvement in this repo - dgVoodoo (20fps physics cap,
             sharp Voodoo look, MSAA), the corrected input.map (mouse driving +
             gamepad), the cutscene-music fix hook, and a desktop launcher.

  Ships NO copyrighted game files. The bytes come from YOUR GOG .exe; this repo is
  only scripts + config.

  Usage (PowerShell, from this folder):
    ./Setup-From-GOG.ps1                      # auto-find the GOG .exe(s) in Downloads
    ./Setup-From-GOG.ps1 -GameDir "D:\Games\Interstate 76"
    ./Setup-From-GOG.ps1 -GogExe "C:\path\setup_interstate76_2.1.0.17.exe" -NitroExe "C:\path\setup_interstate76_nitro_pack_2.1.0.17.exe"
    ./Setup-From-GOG.ps1 -SkipNitro          # base game only
    ./Setup-From-GOG.ps1 -WithHDTextures -Yes # also build the HD pack from your files, no prompts

  Or just double-click INSTALL.bat.
#>
param(
    [string]$GogExe   = "",
    [string]$NitroExe = "",
    [string]$GameDir  = "C:\GOG Games\Interstate 76",  # GOG's own default: user-writable, so the installer stays headless (no UAC)
    [string]$ToolsDir = "C:\Games\_tools",
    [switch]$SkipNitro,
    [switch]$WithHDTextures,
    [switch]$Force,      # re-run the GOG installer even if i76.exe already exists
    [switch]$Yes
)
$ErrorActionPreference = 'Stop'
$repo = $PSScriptRoot
function Say($m,$c='Cyan'){ Write-Host $m -ForegroundColor $c }
function Ask($m){ if($Yes){return $true}; $r=Read-Host "$m [Y/n]"; return ($r -eq '' -or $r -match '^[Yy]') }

Say "`n=== Interstate '76 - install from your GOG copy ===`n" 'Green'

# --- 0. find the GOG offline installers --------------------------------------
$searchDirs = @("$env:USERPROFILE\Downloads", "$env:USERPROFILE\Desktop", $repo, (Get-Location).Path) |
    Select-Object -Unique | Where-Object { Test-Path $_ }

if (-not $GogExe) {
    $GogExe = Get-ChildItem $searchDirs -Filter 'setup_interstate76_*.exe' -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -notmatch 'nitro' } |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1 -ExpandProperty FullName
}
if (-not $GogExe -or -not (Test-Path $GogExe)) {
    Say "Couldn't find a GOG installer (setup_interstate76_*.exe)." 'Yellow'
    Say "Download it from https://www.gog.com/account (Interstate '76 -> More -> Download offline backup),"
    Say "then re-run:  ./Setup-From-GOG.ps1 -GogExe `"C:\path\to\setup_interstate76_2.1.0.17.exe`""
    exit 1
}
if (-not $SkipNitro -and -not $NitroExe) {
    $NitroExe = Get-ChildItem $searchDirs -Filter 'setup_interstate76_nitro*.exe' -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1 -ExpandProperty FullName
}
Say "Base game  : $GogExe" 'Green'
if ($NitroExe) { Say "Nitro Pack : $NitroExe" 'Green' } else { Say "Nitro Pack : (none found - base game only)" 'Yellow' }

# --- 1. silent-install the GOG installers (Inno Setup) -----------------------
function Invoke-GogInstaller($exe, $dir, $label) {
    Say "`nInstalling $label ..."
    # GOG offline installers are Inno Setup. These flags do a headless install
    # into $dir: no wizard, no message boxes, no auto-launch, no reboot, and
    # /NOICONS so GOG's own (non-dgVoodoo) shortcuts don't compete with ours.
    # NOTE: do NOT pass /LANG or /NOCANCEL - GOG's wrapper aborts (exit 2) on them.
    $log = Join-Path $env:TEMP ("i76-gog-install-{0}.log" -f ($label -replace '\W','_'))
    $flags = @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/NOICONS',"/DIR=`"$dir`"","/LOG=`"$log`"")
    $p = Start-Process -FilePath $exe -ArgumentList $flags -Wait -PassThru
    if ($p.ExitCode -ne 0) {
        Say "  installer for $label exited with code $($p.ExitCode) - see $log" 'Yellow'
    }
}

$exePath = Join-Path $GameDir 'i76.exe'
if ((Test-Path $exePath) -and -not $Force) {
    Say "`ni76.exe already present in `"$GameDir`" - skipping base install (use -Force to reinstall)." 'Yellow'
} else {
    if (-not (Test-Path $GameDir)) { New-Item -ItemType Directory -Force $GameDir | Out-Null }
    Invoke-GogInstaller $GogExe $GameDir 'Interstate 76 (base)'
    if (-not (Test-Path $exePath)) {
        Say "`ni76.exe still not found in `"$GameDir`" after install." 'Red'
        Say "If the GOG installer asked for elevation, re-run this in an *Administrator* PowerShell,"
        Say "or pick a user-writable folder:  -GameDir `"$env:USERPROFILE\Interstate 76`""
        exit 1
    }
}

# Nitro Pack installs into the SAME game folder (adds expansion assets to ADDON/, etc.)
if ($NitroExe -and (Test-Path $NitroExe)) {
    Invoke-GogInstaller $NitroExe $GameDir 'Nitro Pack'
}

Say "`nGame installed:" 'Green'
Say "  $GameDir  (i76.exe MD5 $((Get-FileHash $exePath -Algorithm MD5).Hash.ToLower()))"

# --- 2. apply every repo improvement (delegates to install.ps1) --------------
# install.ps1 fetches dgVoodoo2 into $ToolsDir and runs setup-windows.ps1:
#   dgVoodoo config (20fps cap / Voodoo1 look / MSAA), input.map (mouse + pad),
#   PLAY-i76.bat + desktop shortcut.  -WithHDTextures builds the HD pack too.
Say "`nApplying i76-everywhere improvements ..." 'Cyan'
$installArgs = @{ GameDir = $GameDir; ToolsDir = $ToolsDir }
if ($WithHDTextures) { $installArgs['WithHDTextures'] = $true }
if ($Yes)            { $installArgs['Yes'] = $true }
& (Join-Path $repo 'install.ps1') @installArgs

# --- 3. cutscene-music fix (optional, if the proxy DLL has been built) --------
$smack = Join-Path $repo 'smack-music-fix\SMACKW32.DLL'
if (Test-Path $smack) {
    $dest = Join-Path $GameDir 'SMACKW32.DLL'
    if (Test-Path $dest) { Copy-Item $dest "$dest.gog-original" -Force -ErrorAction SilentlyContinue }
    Copy-Item $smack $dest -Force
    Say "Cutscene-music fix installed (proxy SMACKW32.DLL; original saved as .gog-original)." 'Green'
} else {
    Say "Cutscene-music fix not built (optional) - see smack-music-fix\build.sh to enable it." 'DarkGray'
}

Say "`n=== DONE ===" 'Green'
Say "Play from the desktop shortcut `"Interstate '76`" (or PLAY-i76.bat in the game folder)."
Say "First boot: ~60-75s of 'PLEASE STAND BY' - ESC skips the intro."
Say "To move this working install to another PC, run:  ./Make-Portable-Zip.ps1"
