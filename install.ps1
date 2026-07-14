<#
  Interstate '76 — ONE-COMMAND setup for a fresh Windows PC.
  Bring your own GOG game files; this does everything else, idiot-proof.

  What it does:
    1. Finds your Interstate '76 install (GOG registry, common paths, or you point it at one).
    2. Installs the free tools it needs (dgVoodoo2, Real-ESRGAN, liblzo2) into C:\Games\_tools.
    3. Configures dgVoodoo (20fps cap, Voodoo1 look, 3x res, 8x MSAA, windowed) + input.map,
       and makes a desktop launcher   -> via setup-windows.ps1
    4. (Optional) Builds the full-game HD texture pack FROM YOUR OWN FILES and installs it.

  Usage (from this folder, in PowerShell):
    ./install.ps1                       # auto-detect game, config only
    ./install.ps1 -GameDir "D:\Games\Interstate 76"
    ./install.ps1 -WithHDTextures       # also build+install the HD pack (needs Python + a GPU, ~40 min)
    ./install.ps1 -WithHDTextures -Yes  # no prompts

  Nothing here is copyrighted-content: the game files stay yours; the HD pack is built locally
  from them and never redistributed.
#>
param(
    [string]$GameDir = "",
    [string]$ToolsDir = "C:\Games\_tools",
    [switch]$WithHDTextures,
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
$md5 = (Get-FileHash (Join-Path $GameDir 'i76.exe') -Algorithm MD5).Hash.ToLower()
Say "Game: $GameDir  (i76.exe MD5 $md5)" 'Green'
if ($md5 -ne '60abf7bc699da72476128ddce991a3d1') {
    Say "  note: not the verified GOG 2019 build - setup still runs; verify the 20fps cap after." 'Yellow'
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

# --- 3. configure (the load-bearing part) ------------------------------------
Say "`nConfiguring dgVoodoo + input.map + launcher ..."
& (Join-Path $repo 'setup-windows.ps1') -GameDir $GameDir -DgVoodooDir $dgv

# --- 4. optional HD texture pack ---------------------------------------------
if (-not $WithHDTextures) {
    Say "`nSkipping HD texture pack (add -WithHDTextures to build it from your files)." 'Yellow'
} else {
    # prerequisites: python + deps + ESRGAN + lzo2.dll
    $py = (Get-Command python -ErrorAction SilentlyContinue)
    if (-not $py) { Say "Python not found - install Python 3 (python.org) and re-run with -WithHDTextures." 'Red'; exit 1 }
    Say "Installing Python deps (Pillow, numpy, python-lzo) ..."
    python -m pip install --quiet --user Pillow numpy python-lzo 2>&1 | Out-Null

    $esr = Join-Path $ToolsDir 'realesrgan\realesrgan-ncnn-vulkan.exe'
    if (-not (Test-Path $esr)) {
        Say "Downloading Real-ESRGAN ..."
        $z = Join-Path $ToolsDir 'esr.zip'
        Invoke-WebRequest 'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-windows.zip' -OutFile $z
        Expand-Archive $z (Join-Path $ToolsDir 'realesrgan') -Force; Remove-Item $z
    }
    # liblzo2 for the ZFS extractor (conda-forge package, no full conda needed)
    $lzo = Join-Path $ToolsDir 'lzo2.dll'
    if (-not (Test-Path $lzo)) {
        Say "Fetching liblzo2 ..."
        $c = Join-Path $ToolsDir 'lzo.conda'
        Invoke-WebRequest 'https://api.anaconda.org/download/conda-forge/lzo/2.10/win-64/lzo-2.10-h6a83c73_1002.conda' -OutFile $c -UseBasicParsing
        $x = Join-Path $ToolsDir 'lzox'; New-Item -ItemType Directory -Force $x | Out-Null
        # .conda is a zip containing a zstd tarball; use tar (bsdtar ships with Win10+)
        tar -xf $c -C $x
        $pkg = Get-ChildItem $x -Filter 'pkg-*.tar.zst' | Select-Object -First 1
        tar -xf $pkg.FullName -C $x
        Copy-Item (Join-Path $x 'Library\bin\lzo2.dll') $lzo -Force
        Remove-Item $c,$x -Recurse -Force
    }
    $env:LZO2_DLL = $lzo

    $tl = Join-Path $repo 'texture-lab'; $tools = Join-Path $repo 'tools'
    $work = Join-Path $ToolsDir 'i76-hd'; New-Item -ItemType Directory -Force $work | Out-Null
    $assets = Join-Path $work 'assets'; $staging = Join-Path $work 'staging'
    $enhanced = Join-Path $work 'enhanced'; $build = Join-Path $work 'build'
    $manifest = Join-Path $work 'manifest.json'
    New-Item -ItemType Directory -Force $assets,$staging,$enhanced,$build | Out-Null

    $zfs = Join-Path $GameDir 'I76.ZFS'
    if (-not (Test-Path $zfs)) { Say "I76.ZFS not found in game dir - can't build the pack." 'Red'; exit 1 }
    if (-not $Yes) { if (-not (Ask "Build the full HD pack now? (~40 min, uses your GPU)")) { Say "Config done; skipped pack."; exit 0 } }

    Say "`n[1/4] Extracting game textures ..."
    python (Join-Path $tools 'zfs_extract.py') $zfs $assets
    Say "[2/4] Decoding + de-duplicating ..."
    python (Join-Path $tl 'decode_all.py') $assets $staging $manifest
    Say "[3/4] AI-upscaling (this is the ~30-40 min part) ..."
    & $esr -i $staging -o $enhanced -n realesrgan-x4plus-anime | Out-Null
    Say "[4/4] Blending (47/31/22) + re-encoding ..."
    python (Join-Path $tl 'reencode_all.py') $manifest $enhanced $assets $build $staging

    $addon = Join-Path $GameDir 'ADDON'; New-Item -ItemType Directory -Force $addon | Out-Null
    Copy-Item (Join-Path $build '*') $addon -Force
    Say "HD pack installed to $addon" 'Green'
}

Say "`n=== DONE ===" 'Green'
Say "Play from the desktop shortcut 'Interstate '76' (or PLAY-i76.bat in the game folder)."
Say "First boot: 60-75s of 'PLEASE STAND BY' - ESC skips the intro."
