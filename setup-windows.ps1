# Interstate '76 - one-shot Windows setup (the WINDOWS-PLAYBOOK.md recipe, scripted).
#
# What it does, in order:
#   1. Verifies the game folder (i76.exe) and reports whether it's the known-good
#      GOG 2019 / AiO build (MD5 60abf7bc699da72476128ddce991a3d1).
#   2. Moves GOG's bundled OpenGLide DLLs aside (so dgVoodoo's Glide2x.dll wins).
#   3. Copies dgVoodoo2's x86 Glide DLLs + control panel into the game folder.
#   4. Installs dgVoodoo.windows.conf as the game folder's dgVoodoo.conf
#      (19.2 FPS physics cap - matches Mac; Voodoo1 2MB TMU, 3x res, 8x MSAA; starts
#      FULLSCREEN aspect-correct, Alt+Enter toggles windowed, mouse correct
#      in both via dgVoodoo cursor emulation).
#   5. Patches input.map: GOG's phantom joystick5 -> joystick1, adds native
#      mouse driving + pad bindings (port of setup-mouse-and-pad.sh; idempotent;
#      backup written beside it). NEVER rebind via the in-game menu - it's buggy.
#   6. Writes PLAY-i76.bat (launches i76.exe -glide from the game folder) and a
#      desktop shortcut.
#
# NOT done here (separate, optional):
#   - Force feedback: run enable-force-feedback.bat AS ADMINISTRATOR (HKLM write).
#   - Frame smoothing: Lossless Scaling x2 experiment - set ForceVerticalSync=false
#     in dgVoodoo.conf first so LS owns presentation (see WINDOWS-PLAYBOOK.md sec 2).
#
# Usage:  powershell -ExecutionPolicy Bypass -File setup-windows.ps1 `
#             -GameDir "C:\Games\Interstate 76" [-DgVoodooDir "C:\Games\_tools\dgVoodoo2_87_3"]
#         Nitro Pack (identical recipe, verified 2026-07-10):
#             -GameDir "C:\Games\Interstate 76 Nitro Pack" -Exe nitro.exe

param(
    [string]$GameDir = "C:\Games\Interstate 76",
    [string]$DgVoodooDir = "C:\Games\_tools\dgVoodoo2_87_3",
    [string]$AhkDir = "",  # folder holding AutoHotkeyU32.exe; enables the pad/XInput layer
    [string]$Exe = "i76.exe"   # "nitro.exe" for the GOG Nitro Pack - identical recipe
                               # (verified 2026-07-10, FINDINGS doc sec 1.1)
)

$ErrorActionPreference = 'Stop'
$repoGameDir = $PSScriptRoot
$isNitro = ($Exe -ieq 'nitro.exe')

# --- 1. sanity ---------------------------------------------------------------
# NOTE: local var deliberately NOT named $exe - PowerShell variables are
# case-insensitive, so $exe and the -Exe parameter would be the SAME variable
# and this assignment would silently clobber it with a full path (breaking the
# PLAY-*.bat written near the end, which needs the bare exe name). Bit us live
# 2026-07-21: shortcuts opened a cmd window and died instantly.
$exePath = Join-Path $GameDir $Exe
if (-not (Test-Path $exePath)) {
    Write-Host "$Exe not found in `"$GameDir`"." -ForegroundColor Red
    Write-Host "Install the GOG offline installer there (or unzip game-data/i76-stable-gog.zip), then rerun."
    exit 1
}
if ($isNitro) {
    Write-Host "Nitro Pack ($Exe): same engine, same recipe - no built-in FPS limiter, so the conf cap is load-bearing here."
} else {
    $md5 = (Get-FileHash $exePath -Algorithm MD5).Hash.ToLower()
    if ($md5 -eq '60abf7bc699da72476128ddce991a3d1') {
        Write-Host "i76.exe is the known-good GOG 2019 / AiO build (20 FPS limiter built in)." -ForegroundColor Green
    } else {
        Write-Host "i76.exe MD5 = $md5 - NOT the verified GOG 2019 build (60abf7bc...)." -ForegroundColor Yellow
        Write-Host "Setup continues, but VERIFY THE CAP after launch (see checklist in the repo README)."
    }
}

$glideSrc = Join-Path $DgVoodooDir '3Dfx\x86'
if (-not (Test-Path (Join-Path $glideSrc 'Glide2x.dll'))) {
    Write-Host "dgVoodoo2 not found at `"$DgVoodooDir`" (need 3Dfx\x86\Glide2x.dll)." -ForegroundColor Red
    Write-Host "Download from https://github.com/dege-diosg/dgVoodoo2/releases and extract there, then rerun."
    exit 1
}

# --- 2. retire GOG's bundled OpenGLide so dgVoodoo's Glide2x.dll wins ---------
$backup = Join-Path $GameDir '_openglide-backup'
# dgVoodoo's own DLLs are recognized by hash against the dist we deploy from -
# a text probe (Select-String 'dgVoodoo') misses their UTF-16 strings and on a
# re-run would move OUR deploy into the backup, clobbering the real originals.
$dgvHashes = Get-ChildItem (Join-Path $DgVoodooDir '3Dfx\x86') -Filter 'Glide*.dll' |
    ForEach-Object { (Get-FileHash $_.FullName -Algorithm SHA256).Hash }
$bundled = Get-ChildItem $GameDir -File | Where-Object {
    # glide*.dll / glide2x.ovl only - NEVER z*.dll (zglide etc. are the engine's
    # own renderer modules, not wrappers; FINDINGS doc sec 1.1)
    $_.Name -match '^glide.*\.(dll|ovl)$' -and
    ((Get-FileHash $_.FullName -Algorithm SHA256).Hash -notin $dgvHashes)
}
if ($bundled) {
    New-Item -ItemType Directory -Force $backup | Out-Null
    $bundled | ForEach-Object {
        $dest = Join-Path $backup $_.Name
        if (Test-Path $dest) {
            # a backup of this name already exists - assume it's the true original
            # and never overwrite it; just clear the game-dir copy out of the way
            Remove-Item $_.FullName -Force
            Write-Host "Removed bundled $($_.Name) (an original is already in _openglide-backup\)"
        } else {
            Move-Item $_.FullName $dest
            Write-Host "Moved bundled $($_.Name) -> _openglide-backup\"
        }
    }
}

# --- 3. deploy dgVoodoo ------------------------------------------------------
foreach ($dll in 'Glide.dll','Glide2x.dll','Glide3x.dll') {
    Copy-Item (Join-Path $glideSrc $dll) $GameDir -Force
}
# DDraw wrapping: the 2D shell (menus/cutscenes) is DirectDraw - wrapping it gives
# the menus the same 3x upscale as the sim (see [DirectX] in dgVoodoo.windows.conf)
foreach ($dll in 'DDraw.dll','D3DImm.dll') {
    Copy-Item (Join-Path $DgVoodooDir "MS\x86\$dll") $GameDir -Force
}
Copy-Item (Join-Path $DgVoodooDir 'dgVoodooCpl.exe') $GameDir -Force
Write-Host "dgVoodoo Glide + DirectDraw DLLs + control panel deployed."

# --- 4. config ---------------------------------------------------------------
$confPath = Join-Path $GameDir 'dgVoodoo.conf'
Copy-Item (Join-Path $repoGameDir 'dgVoodoo.windows.conf') $confPath -Force

# Window size is DISPLAY-DEPENDENT and dgVoodoo SNAPS it to a real enumerated
# display mode - an exact-14:9 computed size (1605x1032) silently became
# 1680x1050, and ExtraEnumeratedResolutions did not override it (verified
# 2026-07-22). So enumerate the modes the adapter actually supports, keep the
# ones that fit the desktop work area (a borderless window gets clamped to it),
# and pick whichever is CLOSEST to the Mac's 14:9 = 1.5556, largest wins on ties.
# Both Resolution lines get the value: [DirectX] owns the window, [Glide] the
# 3D render target, and they must agree.
try {
    Add-Type -AssemblyName System.Windows.Forms -ErrorAction Stop
    $b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    # 16:10 (1.600) is the closest STANDARD display aspect to the Mac's 14:9
    # (1.556) - and dgVoodoo only honours real modes, so this is the practical
    # target. Pick the largest 16:10 mode that fits the panel.
    $best = @(2560,1600), @(1920,1200), @(1680,1050), @(1440,900), @(1280,800) |
        Where-Object { $_[0] -le $b.Width -and $_[1] -le $b.Height } |
        Select-Object -First 1
    if ($best) {
        (Get-Content $confPath) -replace '^Resolution(\s+)= \d+x\d+', "Resolution`$1= $($best[0])x$($best[1])" |
            Set-Content $confPath -Encoding ascii
        Write-Host "dgVoodoo.conf installed (FPSLimit=19.2; Voodoo1 2MB/1TMU, 8x MSAA, borderless windowed)."
        Write-Host ("  aspect: {0}x{1} (ratio {2:N3}) - closest real display mode to the Mac's 14:9 = 1.556." -f $best[0], $best[1], ($best[0]/$best[1]))
    } else {
        Write-Host "dgVoodoo.conf installed (panel smaller than 1280x800 - left the default)." -ForegroundColor Yellow
    }
} catch {
    Write-Host "dgVoodoo.conf installed (couldn't read display size - left the default 1680x1050)." -ForegroundColor Yellow
}

# --- 5. input.map: joystick5 -> joystick1, mouse driving, pad bindings --------
$mapPath = Join-Path $GameDir 'input.map'
if (Test-Path $mapPath) {
    $map = Get-Content $mapPath -Raw
    if ($map -notmatch 'setup-windows\.ps1|setup-mouse-and-pad\.sh') {
        Copy-Item $mapPath "$mapPath.pre-windows-setup" -Force
        # analog sinks: stale joystick5 -> joystick1 + native mouse driving
        # (instance .Replace() because the static one has no count overload)
        $throttleRx = New-Object regex 'throttle \{[^}]*\}'
        $map = $throttleRx.Replace($map, "throttle {`r`n   - joystick1  Down/Up`r`n   - mouse      Down/Up`r`n}", 1)
        $steerRx = New-Object regex 'steer \{[^}]*\}'
        $map = $steerRx.Replace($map, "steer {`r`n   - joystick1  Left/Right`r`n   - mouse      Left/Right`r`n}", 1)
        $map = $map -replace '\+ joystick5  Button2', '+ joystick1  Button2'
        # Handbrake on Space, matching the Mac map (docs/input.map.reference) and
        # the verified rebind in docs/VERIFIED-FIXES.md: e_brake moves off C onto
        # Space, and keyboard fire moves off Space onto Enter so the two don't
        # collide (mouse LeftBtn + pad still fire; Space is the natural handbrake).
        $ebRx = New-Object regex 'e_brake \{\s*\+ keyboard\s+C\b'
        $map = $ebRx.Replace($map, "e_brake {`r`n   + keyboard   Space", 1)
        $wfRx = New-Object regex 'weapon_fire \{\s*\+ keyboard\s+Space\b'
        $map = $wfRx.Replace($map, "weapon_fire {`r`n   + keyboard   Enter", 1)
        # separate blocks = alternative bindings (not chords); engine has exactly
        # three mouse-button tokens, so weapon 4 stays on keyboard 'Four'
        $add = @(
            '',
            '# --- Mouse + gamepad additions (setup-windows.ps1) ---',
            'hardpoint1_fire {', '   + mouse      LeftBtn', '}',
            'hardpoint2_fire {', '   + mouse      RightBtn', '}',
            'pilot_glance_left {', '   + mouse      MiddleBtn', '}',
            'weapon_fire {', '   + joystick1  Button1', '}',
            'weapon_cycle {', '   + joystick1  Button3', '}',
            'e_brake {', '   + joystick1  Button4', '}',
            'pilot_glance_up {', '   + joystick1  HatUp', '}',
            'pilot_glance_down {', '   + joystick1  HatDown', '}',
            'pilot_glance_left {', '   + joystick1  HatLeft', '}',
            'pilot_glance_right {', '   + joystick1  HatRight', '}'
        ) -join "`r`n"
        $map = $map.TrimEnd() + "`r`n" + $add + "`r`n"
        Set-Content $mapPath $map -Encoding ascii
        Write-Host "input.map patched (backup: input.map.pre-windows-setup)."
    } else {
        Write-Host "input.map already patched - skipping."
    }
} else {
    Write-Host "input.map not found - run the game once to generate it, then rerun this script." -ForegroundColor Yellow
}

# --- 5a. saves: bring the repo's campaign saves across (base game only) --------
# The engine reads save###.cmp + savegame.dir from the game root (same place the
# save editor writes). The repo carries a set in saves/; deploy them ONLY if the
# install has none, so we never clobber real in-progress saves on a re-run.
# (Nitro has its own campaign/saves - the base-game saves don't apply there.)
if (-not $isNitro) {
    $repoSaves = Join-Path $repoGameDir 'saves'
    $haveSaves = Get-ChildItem $GameDir -Filter 'save*.cmp' -ErrorAction SilentlyContinue
    if ((Test-Path $repoSaves) -and -not $haveSaves) {
        Copy-Item (Join-Path $repoSaves 'save*.cmp') $GameDir -Force -ErrorAction SilentlyContinue
        Copy-Item (Join-Path $repoSaves 'savegame.dir') $GameDir -Force -ErrorAction SilentlyContinue
        Write-Host "Campaign saves deployed from repo (save*.cmp + savegame.dir)."
    } elseif ($haveSaves) {
        Write-Host "Existing saves found in game folder - left untouched."
    }
}

# --- 5b. controller layer: AutoHotkey + i76-remap.ahk into <game>\_ahk\ --------
# The full pad scheme (right stick -> glance arrows, independent triggers, LB
# shift layer with all five hardpoints, look-back fire, camera cycle, rumble)
# lives in i76-remap.ahk and runs identically on Wine (Mac), Proton (Deck) and
# native Windows. It emits the engine's STOCK keys, which input.map already
# binds, so it's purely additive. We keep it in the GAME FOLDER (not C:\AutoHotkey)
# so the portable zip carries it; PLAY-i76.ps1 starts/stops it with the game.
$ahkOut = Join-Path $GameDir '_ahk'
$remapSrc = Join-Path $repoGameDir 'i76-remap.ahk'
if ($AhkDir -and (Test-Path (Join-Path $AhkDir 'AutoHotkeyU32.exe')) -and (Test-Path $remapSrc)) {
    New-Item -ItemType Directory -Force $ahkOut | Out-Null
    Copy-Item (Join-Path $AhkDir 'AutoHotkeyU32.exe') $ahkOut -Force
    foreach ($extra in 'license.txt','AutoHotkey.chm') {
        $p = Join-Path $AhkDir $extra; if (Test-Path $p) { Copy-Item $p $ahkOut -Force -ErrorAction SilentlyContinue }
    }
    Copy-Item $remapSrc $ahkOut -Force
    Write-Host "Controller layer deployed (_ahk\AutoHotkeyU32.exe + i76-remap.ahk; starts with the game)."
    Write-Host "  Pad scheme: LB shift layer, triggers=fire/hp2, look-back rear gun, camera cycle, rumble."
    Write-Host "  Connect the controller BEFORE launching (the engine + XInput enumerate at startup)."
} else {
    Write-Host "Controller (AHK/XInput) layer NOT deployed - native pad + mouse only." -ForegroundColor Yellow
    if (-not $AhkDir) { Write-Host "  (run via install.ps1, which fetches AutoHotkey and passes -AhkDir.)" -ForegroundColor DarkGray }
}

# --- 6. launcher + shortcut ---------------------------------------------------
# dgVoodoo (the conf above) owns presentation: fullscreen by default,
# Alt+Enter toggles windowed, emulated cursor keeps the mouse correct in both.
# PLAY-i76.ps1 just launches the game plus i76wheel.exe (mouse wheel ->
# targeting keys; the engine has no wheel tokens - see tools/i76wheel.c;
# build: gcc -O2 -s -mwindows -o i76wheel.exe i76wheel.c -luser32).
Copy-Item (Join-Path $repoGameDir 'PLAY-i76.ps1') $GameDir -Force
$wheelExe = Join-Path $repoGameDir 'tools\i76wheel.exe'
if (Test-Path $wheelExe) {
    Copy-Item $wheelExe $GameDir -Force
    Write-Host "i76wheel.exe deployed (wheel up = target reticle, down = target nearest)."
} else {
    Write-Host "tools\i76wheel.exe not built - wheel targeting disabled (see tools\i76wheel.c)." -ForegroundColor Yellow
}
$batName = if ($isNitro) { 'PLAY-Nitro.bat' } else { 'PLAY-i76.bat' }
$bat = Join-Path $GameDir $batName
Set-Content $bat "@echo off`r`nstart `"`" /min powershell -ExecutionPolicy Bypass -WindowStyle Hidden -File `"%~dp0PLAY-i76.ps1`" -GameDir `"%~dp0.`" -Exe $Exe`r`n" -Encoding ascii
# Desktop shortcut is a convenience, NOT load-bearing - never let it abort setup
# (e.g. a redirected/OneDrive Desktop, or a detached session where the shell folder
# can't be written). PLAY-i76.bat in the game folder is always the real entry point.
try {
    $ws = New-Object -ComObject WScript.Shell
    $desktop = [Environment]::GetFolderPath('Desktop')
    if ($desktop -and (Test-Path $desktop)) {
        $lnkName = if ($isNitro) { "Interstate '76 Nitro Pack.lnk" } else { "Interstate '76.lnk" }
        $lnk = $ws.CreateShortcut((Join-Path $desktop $lnkName))
        $lnk.TargetPath = $bat
        $lnk.WorkingDirectory = $GameDir
        # GOG ships proper multi-res icons (goggame-*.ico on Galaxy installs,
        # gfw_high.ico on offline ones) - much nicer than the 1997 exe's own
        # icon resource, which renders tiny/blank at modern desktop sizes.
        $ico = Get-ChildItem $GameDir -File -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match '^(goggame-\d+|gfw_high)\.ico$' } |
            Sort-Object { $_.Name -notmatch '^goggame' } | Select-Object -First 1
        $lnk.IconLocation = if ($ico) { "$($ico.FullName),0" } else { "$exePath,0" }
        $lnk.Save()
        Write-Host "$batName + desktop shortcut created."
    } else {
        Write-Host "$batName created (Desktop not writable here - skipped the shortcut)." -ForegroundColor Yellow
    }
} catch {
    Write-Host "$batName created (couldn't write the desktop shortcut: $($_.Exception.Message))." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "DONE. Boot takes 60-75s of 'PLEASE STAND BY' - ESC skips the intro." -ForegroundColor Green
Write-Host "Verify the cap in Instant Melee (no flips on bumps; AI cars exceed 35 mph),"
Write-Host "then the canonical test: Mission 5's ramp jump."
Write-Host "Optional: enable-force-feedback.bat AS ADMIN for FFB wheels/sticks."
Write-Host "Connect controller BEFORE launching - the engine enumerates joysticks at startup only."
