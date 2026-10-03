# Interstate '76 - one-shot Windows setup (the WINDOWS-PLAYBOOK.md recipe, scripted).
#
# What it does, in order:
#   1. Verifies the game folder (i76.exe) and reports whether it's the known-good
#      GOG 2019 / AiO build (MD5 60abf7bc699da72476128ddce991a3d1).
#   2. Moves GOG's bundled OpenGLide DLLs aside (so dgVoodoo's Glide2x.dll wins).
#   3. Copies dgVoodoo2's x86 Glide DLLs + control panel into the game folder.
#   4. Installs the game folder's dgVoodoo.conf. Since 2026-10-03, for the base game with the
#      default -Preset best-120: dgVoodoo.daily-driver-2026-10-03.conf, the conf of the owner's
#      daily driver (proven ACCEPTED by dgVoodoo 2.87.3; FPSLimit 0, 16:10 picture, 2x internal
#      resolution, 4x MSAA). With -Preset stock, and always for the Nitro Pack:
#      dgVoodoo.windows.conf as before (19.2 FPS physics cap, 8x MSAA).
#   5. Patches input.map: GOG's phantom joystick5 -> joystick1, adds native
#      mouse driving + pad bindings (port of setup-mouse-and-pad.sh; idempotent;
#      backup written beside it). NEVER rebind via the in-game menu - it's buggy.
#   6. Writes PLAY-i76.bat (PLAY-i76.ps1 -Preset <the -Preset given here, default best-120>),
#      PLAY-stock.bat (the same folder with -Preset stock: no engine switches) and a desktop
#      shortcut to PLAY-i76.bat (-NoShortcut skips the shortcut; nothing is then written
#      outside the game folder).
#   Also (5a2b, base game, preset other than stock): renames GOG's I76PATCH.DLL (the 20 fps
#      cap of the 2019 offline build) to I76PATCH.DLL.disabled, as on the daily driver; with it
#      loaded every 60/120 preset runs at 20. -Preset stock renames it back.
#   Also (5a3, base game only): installs the USER32 proxy u32x.dll and retargets the
#      USER32 imports of i76.exe and i76shell.dll to it - the menu / save-screen mouse
#      mapping and the Save Bookmark ghosting fix. Source, md5 and provenance of the
#      DLL: u32x\README.md. -U32xDll names another build (only recorded verified
#      builds are accepted here), -NoU32x skips the step.
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
    [string]$Exe = "i76.exe",  # "nitro.exe" for the GOG Nitro Pack - identical recipe
                               # (verified 2026-07-10, FINDINGS doc sec 1.1)
    # The USER32 proxy to install (step 5a3). Default: the committed, sandbox-verified
    # minimal build (u32x\u32x.dll, md5 a5927cea; built from u32x\u32x_min.c).
    [string]$U32xDll = (Join-Path $PSScriptRoot 'u32x\u32x.dll'),
    [switch]$NoU32x,
    # Which presets\<name>.psd1 the installed PLAY-i76.bat hands to PLAY-i76.ps1 (base game only;
    # the Nitro Pack has no proxy and always gets the stock recipe). best-120 is the owner's
    # daily driver since 2026-10-03. "stock" installs what this script installed before that
    # date: the 19.2 fps dgVoodoo cap, I76PATCH.DLL left active, no engine switches.
    [string]$Preset = 'best-120',
    # Do not create the desktop shortcut (the only thing this script writes outside -GameDir).
    [switch]$NoShortcut
)

$ErrorActionPreference = 'Stop'
$repoGameDir = $PSScriptRoot
$isNitro = ($Exe -ieq 'nitro.exe')
if ($isNitro) { $Preset = 'stock' }
if ($Preset -notmatch '^[\w-]+$' -or -not (Test-Path (Join-Path $repoGameDir "presets\$Preset.psd1"))) {
    Write-Host "Unknown -Preset '$Preset' (no presets\$Preset.psd1 in $repoGameDir)." -ForegroundColor Red
    exit 1
}
$fastPreset = ($Preset -ne 'stock')   # a preset that needs the 20 fps caps out of the way

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
    # after a first run i76.exe carries the u32x import rename; the build is identified by the kept original
    $md5From = if (Test-Path "$exePath.u32xorig") { "$exePath.u32xorig" } else { $exePath }
    $md5 = (Get-FileHash $md5From -Algorithm MD5).Hash.ToLower()
    if ($md5 -eq '60abf7bc699da72476128ddce991a3d1') {
        Write-Host "i76.exe is the known-good GOG 2019 / AiO build (20 FPS limiter built in)." -ForegroundColor Green
    } else {
        Write-Host "i76.exe MD5 = $md5 - NOT the GOG 2019 build (60abf7bc...) the presets were gated on." -ForegroundColor Yellow
        if ($fastPreset) {
            Write-Host "Setup continues. Preset $Preset has NOT been run on this build: the proxy checks the bytes at every patch site and skips a mismatch (<game>\mciproxy.log lists each). If the game runs too fast, re-run with -Preset stock."
        } else {
            Write-Host "Setup continues, but VERIFY THE CAP after launch (see checklist in the repo README)."
        }
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
$driverConf = Join-Path $repoGameDir 'dgVoodoo.daily-driver-2026-10-03.conf'
if ($fastPreset -and (Test-Path $driverConf)) {
    # The daily driver's conf (2026-10-03). dgVoodoo 2.87.3 REJECTS a whole conf over one line it
    # does not like and then silently uses %APPDATA%\dgVoodoo\dgVoodoo.conf instead, so this file
    # is deployed byte for byte wherever the display allows, and otherwise only the DIGITS of the
    # two Resolution lines change (same keys, same sections, same compact WxH form, ASCII, CRLF).
    #   [DirectX] Resolution: 1680x1050 as proven, or the largest smaller 16:10 mode that fits
    #                         the panel (the mode list this script has always used).
    #   [Glide]   Resolution: 2x the 16:10 frame at the panel's height. 1440 lines and taller
    #                         -> 4608x2880, the proven value (measured on a 1440-line display;
    #                         a taller panel keeps it rather than a GPU load nobody measured);
    #                         1080 lines -> 3456x2160.
    # Only the 1440-line result (the unchanged file) has been run. The others are computed.
    $proven = [IO.File]::ReadAllText($driverConf, [Text.Encoding]::ASCII)
    $conf = $proven
    $dx = $null; $gl = $null
    try {
        Add-Type -AssemblyName System.Windows.Forms -ErrorAction Stop
        $b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
        $dx = @(1680,1050), @(1440,900), @(1280,800) |
            Where-Object { $_[0] -le $b.Width -and $_[1] -le $b.Height } | Select-Object -First 1
        $ph = [Math]::Min($b.Height, 1440); $pw = [int][Math]::Floor($ph * 1.6)
        if ($pw -gt $b.Width) { $pw = $b.Width; $ph = [int][Math]::Floor($pw / 1.6) }
        $gl = @((2 * $pw), (2 * $ph))
    } catch { }
    if ($gl) {
        $glRx = New-Object regex '(?ms)(^\[Glide\]\s.*?^Resolution\s*= )\d+x\d+'
        $dxRx = New-Object regex '(?ms)(^\[DirectX\]\s.*?^Resolution\s*= )\d+x\d+'
        $conf = $glRx.Replace($conf, ('${1}' + "$($gl[0])x$($gl[1])"), 1)
        # a panel smaller than 1280x800 keeps the [DirectX] line as it is (this script always did)
        if ($dx) { $conf = $dxRx.Replace($conf, ('${1}' + "$($dx[0])x$($dx[1])"), 1) }
        # Same shape or nothing: apart from the Resolution digits the text must equal the proven file.
        $mask = '(?m)^(Resolution\s*= )\d+x\d+'
        if (($conf -replace $mask, '$1') -cne ($proven -replace $mask, '$1')) { $conf = $proven }
    }
    [IO.File]::WriteAllText($confPath, $conf, [Text.Encoding]::ASCII)
    if ($conf -ceq $proven) {
        Write-Host "dgVoodoo.conf installed: the daily-driver conf of 2026-10-03, unchanged (FPSLimit 0, [Glide] 4608x2880, 4x MSAA, borderless)."
    } else {
        $resNow = ([regex]::Matches($conf, '(?m)^Resolution\s*= (\d+x\d+)') | ForEach-Object { $_.Groups[1].Value }) -join ' / '
        Write-Host "dgVoodoo.conf installed: the daily-driver conf of 2026-10-03 with [Glide] / [DirectX] Resolution $resNow for this display (computed; only 4608x2880 / 1680x1050 has been run)." -ForegroundColor Yellow
    }
    if (Test-Path (Join-Path $env:APPDATA 'dgVoodoo\dgVoodoo.conf')) {
        Write-Host "  note: a global $env:APPDATA\dgVoodoo\dgVoodoo.conf exists on this PC. dgVoodoo uses it, silently, if it ever rejects the game folder's conf (a watermark or a 4:3 picture is the sign)." -ForegroundColor Yellow
    }
} else {
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
}   # end: stock / Nitro conf

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
        #
        # LeftBtn goes on weapon_fire, NOT hardpoint1_fire. weapon_fire is "fire
        # the selected/linked weapons" - the same action Enter and pad Button1
        # emit - and it is also what fires the HANDGUN on foot. hardpoint1_fire
        # fires hardpoint 1 specifically: in-car it ignores selection/linking,
        # and on foot it does nothing, which shipped as "mouse doesn't fire the
        # handgun" and made the left button feel broken outside the car.
        # (docs/input.map.reference:213 also puts LeftBtn on weapon_fire.)
        $add = @(
            '',
            '# --- Mouse + gamepad additions (setup-windows.ps1) ---',
            'weapon_fire {', '   + mouse      LeftBtn', '}',
            'hardpoint2_fire {', '   + mouse      RightBtn', '}',
            'pilot_glance_left {', '   + mouse      MiddleBtn', '}',
            'weapon_fire {', '   + joystick1  Button1', '}',
            'weapon_cycle {', '   + joystick1  Button3', '}',
            'e_brake {', '   + joystick1  Button4', '}',
            'pilot_glance_up {', '   + joystick1  HatUp', '}',
            'pilot_glance_down {', '   + joystick1  HatDown', '}',
            'pilot_glance_left {', '   + joystick1  HatLeft', '}',
            'pilot_glance_right {', '   + joystick1  HatRight', '}',
            '',
            '# Home-row hardpoints 1-4. Additive: a second block for the same action is',
            '# an ALTERNATIVE binding, not a chord, so the number keys and mouse buttons',
            '# above keep working. Fires that ONE hardpoint, ignoring selection/linking.',
            'hardpoint1_fire {', '   + keyboard   L', '}',
            'hardpoint2_fire {', '   + keyboard   O', '}',
            'hardpoint3_fire {', '   + keyboard   LeftBracket', '}',
            'hardpoint4_fire {', '   + keyboard   RightBracket', '}'
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

# --- 5a2. in-mission music fix (base game only) -------------------------------
# The base game plays its soundtrack as CD audio via MCI cdaudio, which won't
# open on a PC with no optical drive - so no music + "Please insert CD 2". We
# proxy Strlkup.dll (a 5-export DLL i76.exe imports statically) to IAT-hook the
# game's mciSendCommandA and play GOG's music\N.mp3 through the mpegvideo device
# instead. See music-fix/README.md. Nitro uses audiere.dll and needs none of this.
$musicProxy = Join-Path $repoGameDir 'music-fix\Strlkup.dll'
$strlk = Join-Path $GameDir 'Strlkup.dll'
if (-not $isNitro -and (Test-Path $musicProxy) -and (Test-Path $strlk)) {
    $orig = Join-Path $GameDir 'strlkup_orig.dll'
    # Only back up the GENUINE original once - never overwrite the backup with our
    # proxy on a re-run (same trap as the dgVoodoo DLL backup). Recognise our proxy
    # by hash so a re-run is a no-op.
    $proxyHash = (Get-FileHash $musicProxy -Algorithm SHA256).Hash
    $liveHash  = (Get-FileHash $strlk -Algorithm SHA256).Hash
    if ($liveHash -ne $proxyHash) {
        if (-not (Test-Path $orig)) { Copy-Item $strlk $orig -Force }
        Copy-Item $musicProxy $strlk -Force
        Write-Host "In-mission music fix installed (Strlkup.dll proxy; original -> strlkup_orig.dll)."
    } else {
        Write-Host "In-mission music fix already installed - skipping."
    }
}

# --- 5a2b. GOG's I76PATCH.DLL (the 2019 offline build's 20 fps cap) --------------
# With it loaded a 60/120 preset runs its fixes under a 20 fps cap and looks like it does
# nothing, so it is renamed (never deleted), as tools\Make-Daily-Driver.ps1 does for the daily
# driver. -Preset stock puts it back. The 2017 Galaxy build ships no such file: nothing to do.
if (-not $isNitro) {
    $patchDll = Join-Path $GameDir 'I76PATCH.DLL'
    $patchOff = "$patchDll.disabled"
    if ($fastPreset -and (Test-Path $patchDll)) {
        Move-Item $patchDll $patchOff -Force
        Write-Host "I76PATCH.DLL -> I76PATCH.DLL.disabled (GOG's 20 fps cap off; preset $Preset paces the game)."
    } elseif ($fastPreset) {
        Write-Host "I76PATCH.DLL: not present$(if (Test-Path $patchOff) { ' (already disabled)' }) - nothing to do."
    } elseif ((Test-Path $patchOff) -and -not (Test-Path $patchDll)) {
        Move-Item $patchOff $patchDll
        Write-Host "I76PATCH.DLL.disabled -> I76PATCH.DLL (preset stock: GOG's 20 fps cap back on)."
    }
}

# --- 5a3. USER32 proxy (u32x.dll): menu / save-screen mouse ---------------------
# The shell and the engine hit-test raw screen coordinates against 640x480 widget
# rectangles, so under dgVoodoo's stretch the mouse lands wrong in the menus and the
# overwrite prompt can spin forever; and DWM ghosts the Save Bookmark screen after
# ~5.9 s idle. u32x.dll translates the coordinates and switches ghosting off. Until
# 2026-10-02 only the portable zip carried it - a fresh install had the bug (backlog
# P3-03). deploy-u32x.ps1 checks, before writing anything, that the DLL exports every
# USER32 function the two binaries import, keeps i76shell.dll.orig / i76.exe.u32xorig,
# and reads each write back. Undo: u32x\deploy-u32x.ps1 -GameDir <dir> -Restore.
# NOT YET PROVEN on a fresh GOG install end to end (needs a console run of
# Setup-From-GOG.ps1 on a clean folder; RELEASE-PLAN section 7 item 3).
$u32xDeploy = Join-Path $repoGameDir 'u32x\deploy-u32x.ps1'
if ($NoU32x) {
    Write-Host "u32x (menu/save-screen mouse fix) skipped (-NoU32x)."
} elseif ($isNitro) {
    Write-Host "u32x not installed for the Nitro Pack: its export list was built from i76.exe + i76shell.dll and has never been run with nitro.exe." -ForegroundColor Yellow
} elseif (-not (Test-Path $u32xDeploy) -or -not (Test-Path $U32xDll)) {
    Write-Host "u32x NOT installed: $u32xDeploy or $U32xDll is missing (menus will mis-map the mouse)." -ForegroundColor Yellow
} else {
    try {
        & $u32xDeploy -GameDir $GameDir -U32xDll $U32xDll -Exe $Exe | ForEach-Object { Write-Host "  u32x: $_" }
        Write-Host "Menu / save-screen mouse fix installed (u32x.dll; originals kept as i76shell.dll.orig, $Exe.u32xorig)."
    } catch {
        Write-Host "u32x NOT installed: $($_.Exception.Message)" -ForegroundColor Yellow
        Write-Host "  The game still runs; the menu mouse will be mis-mapped under dgVoodoo's stretch." -ForegroundColor Yellow
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
    # CH Fighterstick HOTAS layer, deployed alongside the remapper so a fresh
    # install has it. Harmless without the stick: it identifies the device itself
    # and exits if there is none. Enumerated here BY NAME because that is how this
    # script works - and that is precisely how _ahk\i76-remap.ahk sat three weeks
    # stale while the repo's copy grew a whole wheel layer nobody was running.
    # Add new AHK layers here or they silently never ship.
    $stickSrc = Join-Path $repoGameDir 'i76-ch-fighterstick.ahk'
    if (Test-Path $stickSrc) { Copy-Item $stickSrc $ahkOut -Force }
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
# The frame-rate presets PLAY-i76.ps1 -Preset reads (presets\*.psd1, data files). Copied beside
# the launcher so the installed copy finds them. PLAY-i76.bat below names the one to apply.
$presetSrc = Join-Path $repoGameDir 'presets'
if (Test-Path $presetSrc) {
    New-Item -ItemType Directory -Force (Join-Path $GameDir 'presets') | Out-Null
    Copy-Item (Join-Path $presetSrc '*.psd1') (Join-Path $GameDir 'presets') -Force
}
$wheelExe = Join-Path $repoGameDir 'tools\i76wheel.exe'
if (Test-Path $wheelExe) {
    Copy-Item $wheelExe $GameDir -Force
    Write-Host "i76wheel.exe deployed (wheel up = target reticle, down = target nearest)."
} else {
    Write-Host "tools\i76wheel.exe not built - wheel targeting disabled (see tools\i76wheel.c)." -ForegroundColor Yellow
}
$batName = if ($isNitro) { 'PLAY-Nitro.bat' } else { 'PLAY-i76.bat' }
$bat = Join-Path $GameDir $batName
$launch = "start `"`" /min powershell -ExecutionPolicy Bypass -WindowStyle Hidden -File `"%~dp0PLAY-i76.ps1`" -GameDir `"%~dp0.`" -Exe $Exe"
if ($fastPreset) {
    # "-LosslessScaling none" as in the daily driver's PLAY.bat: the preset renders every frame
    # itself, so frame generation is not started ("none" is not a path; an empty string would be
    # swallowed by powershell.exe -File).
    Set-Content $bat "@echo off`r`nREM Interstate '76, preset $Preset (see presets\$Preset.psd1). PLAY-stock.bat = no engine switches.`r`nREM Run at the physical console, never over Remote Desktop. Plug the wheel/pad in first.`r`n$launch -Preset $Preset -LosslessScaling none" -Encoding ascii
    Set-Content (Join-Path $GameDir 'PLAY-stock.bat') "@echo off`r`nREM The same folder with NO engine switches (preset stock). This is NOT the 20 fps game: this`r`nREM install has GOG's 20 fps cap off (I76PATCH.DLL.disabled, where GOG shipped one) and FPSLimit 0, so`r`nREM the frame rate is whatever dgVoodoo paces (60) and the physics are not corrected for it.`r`nREM For the game as GOG ships it (20 fps), re-run the setup with -Preset stock:`r`nREM   setup-windows.ps1 -GameDir <this folder> -Preset stock`r`n$launch -Preset stock -LosslessScaling none" -Encoding ascii
} else {
    Set-Content $bat "@echo off`r`n$launch`r`n" -Encoding ascii
    # a PLAY-stock.bat left by an earlier best-120 setup would describe a state that is gone
    $staleStock = Join-Path $GameDir 'PLAY-stock.bat'
    if (-not $isNitro -and (Test-Path $staleStock)) { Remove-Item $staleStock -Force }
}
# Desktop shortcut is a convenience, NOT load-bearing - never let it abort setup
# (e.g. a redirected/OneDrive Desktop, or a detached session where the shell folder
# can't be written). PLAY-i76.bat in the game folder is always the real entry point.
try {
    if ($NoShortcut) {
        Write-Host "$batName created (-NoShortcut: no desktop shortcut)."
    } else {
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
    }   # end: -NoShortcut
} catch {
    Write-Host "$batName created (couldn't write the desktop shortcut: $($_.Exception.Message))." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "DONE. Boot takes 60-75s of 'PLEASE STAND BY' - ESC skips the intro." -ForegroundColor Green
if ($fastPreset) {
    Write-Host "$batName starts preset $Preset (120 fps, physics stepped as at 20); PLAY-stock.bat starts the same folder with no engine switches."
    Write-Host "Check in Instant Melee: smooth picture, no flips on bumps; then Mission 5's ramp jump."
} else {
    Write-Host "Verify the cap in Instant Melee (no flips on bumps; AI cars exceed 35 mph),"
    Write-Host "then the canonical test: Mission 5's ramp jump."
}
Write-Host "Optional: enable-force-feedback.bat AS ADMIN for FFB wheels/sticks."
Write-Host "Connect controller BEFORE launching - the engine enumerates joysticks at startup only."
