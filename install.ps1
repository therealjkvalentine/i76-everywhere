<#
  Interstate '76 - ONE-COMMAND setup for a fresh Windows PC.
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
& (Join-Path $repo 'setup-windows.ps1') -GameDir $GameDir -DgVoodooDir $dgv -AhkDir $ahk

# --- 4. optional HD texture pack ---------------------------------------------
if (-not $WithHDTextures) {
    Say "`nSkipping HD texture pack (add -WithHDTextures to build it from your files)." 'Yellow'
} else {
    # prerequisites: python + deps + ESRGAN + lzo2.dll
    $py = (Get-Command python -ErrorAction SilentlyContinue)
    if (-not $py) { Say "Python not found - install Python 3 (python.org) and re-run with -WithHDTextures." 'Red'; exit 1 }
    # NOTE: only Pillow + numpy are needed. LZO is done via ctypes against lzo2.dll
    # (LZO2_DLL, set below) - the same path Open76 uses - so we do NOT install the
    # python-lzo module (it has no wheel on modern Python and fails to build).
    Say "Installing Python deps (Pillow, numpy) ..."
    python -m pip install --quiet --user Pillow numpy 2>&1 | Out-Null

    $esr = Join-Path $ToolsDir 'realesrgan\realesrgan-ncnn-vulkan.exe'
    if (-not (Test-Path $esr)) {
        Say "Downloading Real-ESRGAN ..."
        $z = Join-Path $ToolsDir 'esr.zip'
        Invoke-WebRequest 'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-windows.zip' -OutFile $z
        Expand-Archive $z (Join-Path $ToolsDir 'realesrgan') -Force; Remove-Item $z
    }
    # liblzo2 for the ZFS extractor (conda-forge package, no full conda needed).
    # Use the .tar.bz2 build, NOT the newer .conda: the .conda's inner tarball is
    # zstd-compressed, and Windows' bundled tar.exe (bsdtar) can't decode zstd
    # without a separate zstd.exe. bzip2 IS built into bsdtar, so .tar.bz2 extracts
    # offline with no extra tooling. Inside: Library\bin\lzo2.dll.
    $lzo = Join-Path $ToolsDir 'lzo2.dll'
    if (-not (Test-Path $lzo)) {
        Say "Fetching liblzo2 ..."
        $c = Join-Path $ToolsDir 'lzo.tar.bz2'
        Invoke-WebRequest 'https://conda.anaconda.org/conda-forge/win-64/lzo-2.10-he774522_1000.tar.bz2' -OutFile $c -UseBasicParsing
        $x = Join-Path $ToolsDir 'lzox'; New-Item -ItemType Directory -Force $x | Out-Null
        tar -xf $c -C $x
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

    # The Python/ESRGAN steps print progress and occasional benign warnings to
    # stderr - e.g. decode_all.py SKIPping a slightly-short loose file from the
    # Nitro Pack (a non-texture .map; harmless). Under -EA Stop, PowerShell 5.1
    # escalates ANY native stderr line into a terminating error and would abort
    # the whole build. So run these steps with -EA Continue and gate on the real
    # failure signal instead: each tool's exit code.
    $prevEA = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    try {
        Say "`n[1/4] Extracting game textures ..."
        python (Join-Path $tools 'zfs_extract.py') $zfs $assets
        if ($LASTEXITCODE) { throw "zfs_extract.py failed (exit $LASTEXITCODE)" }
        Say "[2/4] Decoding + de-duplicating ..."
        python (Join-Path $tl 'decode_all.py') $assets $staging $manifest
        if ($LASTEXITCODE) { throw "decode_all.py failed (exit $LASTEXITCODE)" }
        Say "[3/4] AI-upscaling (this is the ~30-40 min part) ..."
        & $esr -i $staging -o $enhanced -n realesrgan-x4plus-anime | Out-Null
        if ($LASTEXITCODE) { throw "Real-ESRGAN failed (exit $LASTEXITCODE)" }
        Say "[4/4] Blending (47/31/22) + re-encoding ..."
        python (Join-Path $tl 'reencode_all.py') $manifest $enhanced $assets $build $staging
        if ($LASTEXITCODE) { throw "reencode_all.py failed (exit $LASTEXITCODE)" }
    } finally {
        $ErrorActionPreference = $prevEA
    }

    $addon = Join-Path $GameDir 'ADDON'; New-Item -ItemType Directory -Force $addon | Out-Null
    Copy-Item (Join-Path $build '*') $addon -Force
    Say "HD pack installed to $addon" 'Green'
}

Say "`n=== DONE ===" 'Green'
Say "Play from the desktop shortcut 'Interstate '76' (or PLAY-i76.bat in the game folder)."
Say "First boot: 60-75s of 'PLEASE STAND BY' - ESC skips the intro."
