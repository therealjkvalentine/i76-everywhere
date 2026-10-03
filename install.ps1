<#
  Interstate '76 - ONE-COMMAND setup for a fresh Windows PC.
  Bring your own GOG game files; this does everything else, idiot-proof.

  What it does:
    1. Finds your Interstate '76 install (GOG registry, common paths, or you point it at one).
    2. Installs the free tools it needs (dgVoodoo2, AutoHotkey) into C:\Games\_tools.
    3. Configures dgVoodoo + the music-fix proxy + u32x + input.map + saves + a desktop
       launcher   -> via setup-windows.ps1. Since 2026-10-03 the base game is set up like
       the owner's daily driver: preset best-120 (120 fps, physics stepped as at 20), the
       daily-driver dgVoodoo.conf, GOG's I76PATCH.DLL (20 fps cap) renamed .disabled.
       -Preset stock installs the earlier recipe instead (19.2 fps dgVoodoo cap, no switches).
       (The Nitro Pack, if installed, always gets the earlier recipe: it has no proxy.)

  (An experimental full-game HD texture pack was explored and RETIRED - the
  in-game improvement did not justify shipping it, and palette-indexed tiles
  broke on night missions. The research is preserved in
  docs/HD-TEXTURES-RESEARCH.md for future work.)

  Usage (from this folder, in PowerShell):
    ./install.ps1                       # auto-detect game
    ./install.ps1 -GameDir "D:\Games\Interstate 76"
    ./install.ps1 -Yes                  # no prompts
    ./install.ps1 -Preset stock         # the pre-2026-10-03 recipe: 20 fps, no engine switches
    ./install.ps1 -GameDir <dir> -NoShortcut -SkipNitro   # write nothing outside <dir>
                                        # (given that -ToolsDir already holds dgVoodoo + AutoHotkey)

  Nothing here is copyrighted content: the game files stay yours.
#>
param(
    [string]$GameDir = "",
    [string]$ToolsDir = "C:\Games\_tools",
    [string]$Preset = 'best-120',   # handed to setup-windows.ps1 (base game); 'stock' = the old recipe
    [switch]$NoShortcut,            # no desktop shortcut
    [switch]$SkipNitro,             # do not look for / configure an installed Nitro Pack
    [switch]$Yes
)
$ErrorActionPreference = 'Stop'
$repo = $PSScriptRoot
function Say($m,$c='Cyan'){ Write-Host $m -ForegroundColor $c }
function Ask($m){ if($Yes){return $true}; $r=Read-Host "$m [Y/n]"; return ($r -eq '' -or $r -match '^[Yy]') }

Say "`n=== Interstate '76 one-command setup ===`n" 'Green'

# --- 1. locate the game -------------------------------------------------------
if (-not $GameDir) {
    $cands = @()
    foreach ($k in 'HKLM:\SOFTWARE\WOW6432Node\GOG.com\Games','HKLM:\SOFTWARE\GOG.com\Games') {
        if (Test-Path $k) { Get-ChildItem $k | ForEach-Object {
            $g = Get-ItemProperty $_.PSPath
            if ($g.gameName -match 'Interstate') { $cands += $g.path }
        } }
    }
    $cands += 'C:\Games\Interstate 76','C:\GOG Games\Interstate 76',"$env:USERPROFILE\GOG Games\Interstate 76"
    $GameDir = $cands | Where-Object { Test-Path (Join-Path $_ 'i76.exe') } | Select-Object -First 1
}
if (-not $GameDir -or -not (Test-Path (Join-Path $GameDir 'i76.exe'))) {
    Say "Couldn't auto-find Interstate '76." 'Yellow'
    $GameDir = Read-Host "Enter the folder that contains i76.exe (e.g. C:\Games\Interstate 76)"
}
if (-not (Test-Path (Join-Path $GameDir 'i76.exe'))) { Say "No i76.exe in `"$GameDir`" - aborting." 'Red'; exit 1 }
# (a re-run sees i76.exe with the u32x import rename; the kept original identifies the build)
$md5From = Join-Path $GameDir 'i76.exe.u32xorig'
if (-not (Test-Path $md5From)) { $md5From = Join-Path $GameDir 'i76.exe' }
$md5 = (Get-FileHash $md5From -Algorithm MD5).Hash.ToLower()
Say "Game: $GameDir  (i76.exe MD5 $md5)" 'Green'
if ($md5 -ne '60abf7bc699da72476128ddce991a3d1') {
    Say "  note: not the GOG 2019 offline build the presets were gated on - setup still runs; the proxy checks the bytes it patches and skips what does not match." 'Yellow'
}

# --- 2. tools -----------------------------------------------------------------
New-Item -ItemType Directory -Force $ToolsDir | Out-Null
$dgv = Join-Path $ToolsDir 'dgVoodoo2_87_3'
if (-not (Test-Path (Join-Path $dgv '3Dfx\x86\Glide2x.dll'))) {
    Say "Downloading dgVoodoo2 2.87.3 ..."
    $z = Join-Path $ToolsDir 'dgv.zip'
    Invoke-WebRequest 'https://github.com/dege-diosg/dgVoodoo2/releases/download/v2.87.3/dgVoodoo2_87_3.zip' -OutFile $z
    Expand-Archive $z $dgv -Force; Remove-Item $z
}
Say "dgVoodoo2 ready." 'Green'

# AutoHotkey 1.1.37.02 (portable) for the controller layer - pinned + sha256-checked
# (same build the Mac/Deck remapper uses). Optional: a failure here just skips the
# pad/XInput layer, it never aborts the install.
$ahk = Join-Path $ToolsDir 'AutoHotkey_1.1.37.02'
if (-not (Test-Path (Join-Path $ahk 'AutoHotkeyU32.exe'))) {
    try {
        Say "Downloading AutoHotkey 1.1.37.02 (controller layer) ..."
        $z = Join-Path $ToolsDir 'ahk.zip'
        Invoke-WebRequest 'https://github.com/AutoHotkey/AutoHotkey/releases/download/v1.1.37.02/AutoHotkey_1.1.37.02.zip' -OutFile $z
        $sha = (Get-FileHash $z -Algorithm SHA256).Hash.ToLower()
        if ($sha -ne '6f3663f7cdd25063c8c8728f5d9b07813ced8780522fd1f124ba539e2854215f') {
            Say "  AutoHotkey sha256 mismatch ($sha) - skipping controller layer." 'Yellow'; $ahk = ''
        } else {
            Expand-Archive $z $ahk -Force
        }
        Remove-Item $z -ErrorAction SilentlyContinue
    } catch {
        Say "  AutoHotkey download failed ($($_.Exception.Message)) - skipping controller layer." 'Yellow'; $ahk = ''
    }
}
if ($ahk) { Say "AutoHotkey ready." 'Green' }

# --- 3. configure (the load-bearing part) ------------------------------------
Say "`nConfiguring dgVoodoo + input.map + launcher ..."
$global:LASTEXITCODE = 0
& (Join-Path $repo 'setup-windows.ps1') -GameDir $GameDir -DgVoodooDir $dgv -AhkDir $ahk -Preset $Preset -NoShortcut:$NoShortcut
if ($LASTEXITCODE) { Say "setup-windows.ps1 stopped (exit $LASTEXITCODE) - see its message above." 'Red'; exit $LASTEXITCODE }

# --- 3b. Nitro Pack, if present (identical recipe - FINDINGS doc sec 1.1) -----
# GOG ships it as a standalone game (own nitro.exe, no built-in FPS limiter, so
# the conf cap is load-bearing there). Auto-detected; skipped silently if absent.
# Sibling of the chosen base install first - the registry may point at a
# different (e.g. GOG Galaxy) copy than the one we just configured.
$ncands = @()
if (-not $SkipNitro) {
$ncands = @((Join-Path (Split-Path $GameDir -Parent) 'Interstate 76 Nitro Pack'))
foreach ($k in 'HKLM:\SOFTWARE\WOW6432Node\GOG.com\Games','HKLM:\SOFTWARE\GOG.com\Games') {
    if (Test-Path $k) { Get-ChildItem $k | ForEach-Object {
        $g = Get-ItemProperty $_.PSPath
        if ($g.gameName -match 'Nitro') { $ncands += $g.path }
    } }
}
$ncands += 'C:\Games\Interstate 76 Nitro Pack','C:\GOG Games\Interstate 76 Nitro Pack'
}   # end: -SkipNitro
$NitroDir = $ncands | Where-Object { $_ -and (Test-Path (Join-Path $_ 'nitro.exe')) } | Select-Object -First 1
if ($NitroDir) {
    Say "`nNitro Pack found: $NitroDir - applying the same recipe ..."
    & (Join-Path $repo 'setup-windows.ps1') -GameDir $NitroDir -DgVoodooDir $dgv -AhkDir $ahk -Exe nitro.exe -NoShortcut:$NoShortcut
}

Say "`n=== DONE ===" 'Green'
if ($NoShortcut) { Say "Play from PLAY-i76.bat in the game folder." }
else             { Say "Play from the desktop shortcut 'Interstate '76' (or PLAY-i76.bat in the game folder)." }
Say "First boot: 60-75s of 'PLEASE STAND BY' - ESC skips the intro."
