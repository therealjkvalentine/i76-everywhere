# Interstate '76 / Nitro Pack launcher (Windows + dgVoodoo recipe).
#
# Presentation is owned by dgVoodoo (dgVoodoo.windows.conf): starts FULLSCREEN
# (aspect-correct stretched_ar), Alt+Enter toggles fullscreen/windowed, and
# dgVoodoo's emulated cursor keeps the mouse correct in both modes.
#
# This launcher just starts the game plus i76wheel.exe (mouse wheel -> keys:
# wheel up = Tab = weapon_cycle, wheel down = 5 = hardpoint5_fire, see -WheelUp /
# -WheelDown below - the 1997 engine has no wheel tokens, see tools/i76wheel.c)
# and cleans it up when the game exits.
#
# Frame-rate presets (2026-10-02): -Preset <name> loads presets\<name>.psd1, a documented set of
# the music-fix proxy's opt-in I76_* switches (music-fix/README.md has the table), and hands it
# to the GAME PROCESS ONLY - your shell's environment is never touched. The default, stock, sets
# nothing and is exactly the old behaviour. -Preset ? lists them. -DryRun prints the command line
# and the environment the game would get, then exits without starting anything. The switches are
# no-ops unless the game folder's Strlkup.dll is the current music-fix build, so the launcher
# compares it against music-fix\Strlkup.dll and warns (it copies nothing: run setup-windows.ps1).
# Installed (no music-fix\ beside it) it compares against <game>\strlkup-proxy-build.txt, the
# build setup-windows.ps1 deployed; with neither it says nothing.
# Nothing in a preset is deployed to the playable install by default; see presets\*.psd1 headers
# for what is verified where.
# Preset guard (2026-10-10, -DryRun included): I76_TERRAIN_LOD > 1 without I76_FAR_CLIP is refused (exit 3:
# binoculars overrun the stock terrain vertex pool); I76_COLL_WINDOW without I76_FIXED_STEP gets a warning
# (it does nothing then). tests\test_presets.py checks every shipped preset against the same rules.
#
# Head look and FFB (2026-10-24, docs/records/LAUNCHERS-2026-10-24.md): ON when their hardware / software is there,
# skipped at once when it is not - opentrack installed -> head look; a force-feedback wheel attached -> the custom
# interposer. -NoHeadTrack / -NoFfb switch each off. What was chosen is written to <game>\play-i76.log.
#
# Usage: PLAY-i76.ps1 [-GameDir "C:\Games\Interstate 76"] [-Exe i76.exe] [-Preset smooth-60] [-DryRun] [-LegacyMultiplayer] [-NoHeadTrack] [-NoFfb]
param(
    [string]$GameDir = "C:\Games\Interstate 76",
    [string]$Exe = "i76.exe",
    # Which presets\<name>.psd1 to hand to the game process. 'stock' = no switches (the default,
    # the pre-preset behaviour). '?' lists the presets and exits. A path to a .psd1 also works.
    [string]$Preset = "stock",
    # Skip this machine's presets\local.psd1 override (see "per-machine override" below).
    [switch]$NoLocal,
    # Print the game command line and its environment, then exit. Starts nothing.
    [switch]$DryRun,
    # Frame generation. Pass "" to skip it. Steam does NOT need to be running.
    [string]$LosslessScaling = "C:\Program Files (x86)\Steam\steamapps\common\Lossless Scaling\LosslessScaling.exe",
    # Head tracking, ATTACH-ONLY by default since 2026-10-25: if opentrack is ALREADY RUNNING when the game launches the head-look
    # layer attaches to it (no wait); if it is not running, head look is skipped at once and opentrack is NOT started (a started
    # opentrack cost ~17 fps in the gate). -HeadTrack: start opentrack too (the 2026-10-24 behaviour below); -NoHeadTrack: off.
    # Earlier text, OPT-OUT and NON-BLOCKING since 2026-10-24 (owner: "no dependency on opentrack: if it's not
    # set up or running, just skip it every time instead of the current wait"). If opentrack is installed
    # ($OpenTrack exists) it is started (unless already running), told to begin tracking when the game starts
    # (game detection + i76-opentrack-autostart.ps1, both in the background) and the head-look layer runs; the
    # launcher never waits for tracking - the layer picks FT_SharedMem up whenever it appears. Not installed, or
    # it fails to start: one line in the log and the launch goes on at once. -NoHeadTrack: none of it.
    # -HeadTrack (the old explicit switch) is still accepted; it only adds a warning when opentrack is missing.
    [switch]$HeadTrack,
    [switch]$NoHeadTrack,
    [string]$OpenTrack = "C:\Program Files (x86)\opentrack\opentrack.exe",
    # Head-look mode at start: ANALOG (default since 2026-10-24, owner), DIGITAL or OFF. In the game
    # Ctrl+Alt+H cycles ANALOG -> DIGITAL -> OFF and shows the new mode on screen; holding any glance
    # key / button overrides head look until released.
    [ValidateSet('ANALOG', 'DIGITAL', 'OFF')][string]$HeadLookMode = 'ANALOG',
    # Custom force feedback (tools/ffb, the interposer). AUTOMATIC since 2026-10-24 (owner: one launcher for
    # everything): after the game has started, FfbCore's Ffb-Probe lists the attached DirectInput force-feedback
    # controllers (enumeration only - nothing is acquired, the game must find the wheel free); if one is a wheel
    # (DirectInput type "driving", or a wheel-like name - the T300 reports 0x16) the interposer starts. It takes
    # the wheel exclusively and switches the game's own effects off while it runs (tools/ffb/README.md). No wheel:
    # nothing happens. -NoFfb: never (the game's own force feedback). -Ffb: start it whatever the probe says.
    # Calibrate once: tools\ffb\ffb-calibrate.ps1 (in a game folder _ffb\FFB-CALIBRATE.bat).
    [switch]$Ffb,
    [switch]$NoFfb,
    # Soundtrack. ON by default, because this restores STOCK behaviour rather than
    # adding a feature: I'76 plays its music as Red Book CD audio through MCI, and
    # on a machine with no optical drive there is no cdaudio device to open, so the
    # engine gets silence. GOG ships the tracks as music\*.mp3 but never wires them
    # into the game. See docs/MUSIC.md and tools/i76-music.ps1.
    [switch]$NoMusic,
    # Play only while a mission is loaded, leaving menus quiet as the original did.
    # Off by default: it depends on the player-entity pointer resolving, and silence
    # in a menu reads like a fault even when it is correct.
    [switch]$MusicMissionOnly,
    # 385 = 30% below the old 550 default, by request - the soundtrack sat too loud against
    # engine and gunfire. Note this only scales tools\i76-music.ps1, the external player the
    # launcher starts. The OTHER path, the Strlkup MCI proxy, already honours the game's own
    # AUDIO CONTROL slider: auxSetVolume (a no-op on a machine with no optical drive) is
    # translated to "setaudio <alias> volume to N", so that one is adjustable in-game.
    [int]$MusicVolume = 385,
    # Boot straight into a mission, skipping the title screen and the menus - about
    # 10 seconds from launch to driving. See docs/MISSION-LAUNCH.md. Needs the
    # music-fix proxy deployed, since that is what applies the patch.
    #     .\PLAY-i76.ps1 -Mission t01.msn
    [string]$Mission,
    # With -Mission, also skip the intro and credits movies. Testing convenience -
    # the game reaches the mission on its own either way, just slower.
    [switch]$SkipMovies,
    # Mouse wheel bindings (i76wheel.exe). The engine's mouse device has three
    # buttons and no wheel channels, so the wheel cannot be bound in input.map at
    # all - it is translated to a keystroke instead.
    #   up   = Tab  -> weapon_cycle     (toggle the front weapon)
    #   down = 5    -> hardpoint5_fire  (normally the dropper)
    # Tab is weapon_cycle on this project's map (controls\input.map). On GOG's 1997 map Tab is
    # REVERSE and weapon_cycle is Enter, so in a folder set up with -Controls stock (recorded in
    # <game>\i76e-controls.txt) the default for -WheelUp becomes Enter. A -WheelUp given on the
    # command line always wins.
    # WhichKey the dropper needs depends on the CAR'S LOADOUT, not the game, so if
    # the dropper sits on a different hardpoint use -WheelDown 4 (etc).
    # Names must match input.map; verify with tools/lint-input-map.py.
    [string]$WheelUp = "Tab",
    [string]$WheelDown = "5",
    # Skip the CH Fighterstick HOTAS layer (docs/FIGHTERSTICK.md). It is otherwise
    # started with the game and is harmless without the stick - it detects the
    # device and exits on its own if it is not there.
    [switch]$NoStick,
    # On-screen pointer (i76-cursor-overlay.ahk). The OS cursor is invisible over the game's
    # client area - visible over every other window, gone over this one, even while the game
    # is in the background - so a click-through overlay draws one that the game cannot hide.
    # This is not cosmetic: the shell's modal prompts ("CAN'T GET VERY FAR WITHOUT AN ENGINE",
    # "Overwrite an existing bookmark?") spin at 100% CPU until they are answered, so a
    # pointer you cannot see reads exactly like a frozen game.
    # OPT-IN since 2026-10-12 (-CursorOverlay): the proxy cursor map (I76_CURSOR_MAP, driver promotion 15) and
    # u32x's modal arrow show the pointer in the menus and the OK popups, and the overlay's green crosshair
    # showed up mid-mission (owner report). -NoCursorOverlay is still accepted and does nothing.
    [switch]$CursorOverlay,
    [switch]$NoCursorOverlay,
    # Whole-sim tick length, ms (2026-10-20, docs/records/TICK-FINISH-2026-10-18.md s.19): replaces the tick preset's
    # I76_SIM_TICK_MS for this launch. 16.7..66.7, a plain number (41.667 = the 1997 car step); anything else is refused
    # (exit 4), as is a preset without the tick. PLAY-TICK.bat <ms> and its tick-ms.txt pass it. -CheckTickMs validates
    # the value, prints it and exits (0 / 4) without starting anything (the .bat runs it in a visible window first).
    # Single player: in a network game every player should run the same tick.
    [string]$TickMs,
    [switch]$CheckTickMs,
    # Multiplayer the old way (2026-10-20, owner: "a flag that supports --legacy_multiplayer so people that apply the patch
    # to their game can also play the old way if they have a setup that works"): I76_MP_MENU=0 for this launch, whatever
    # the preset or the shell says, so MULTI MELEE > HOST / JOIN show the stock MODEM / IPX / INTERNET / NULLMODEM row
    # instead of going straight to IPX (proxy mpmenu.c). PLAY*.bat pass --legacy-multiplayer through to it.
    [switch]$LegacyMultiplayer,
    # Computer-car skill in the AI melee arenas (2026-10-20, owner: "is the difficulty of the ai cars correct ... seem to be
    # spanking all these guys"): I76_AIMELEE_SKILL for this launch, 1..5 on the stock scale where 1 is the BEST driver and
    # shot (aim 1.0, fire 1.0, steering / throttle 1.0) and 5 the weakest (0.2 / 0.6 / 0.4); 3 is the stock melee's start and
    # the default. Only the host's value matters (the host runs the AI). PLAY-LAN.bat --ai-skill N passes it through.
    [ValidateRange(0, 5)][int]$AiSkill = 0,
    # Windowed (2026-10-25, owner: "some way to run the game in a window if we're expecting to keep both up at the same
    # time" - the game beside the FFB web panel). 'auto' = the screen's shape, 880 px narrower than the screen (2560x1072 on
    # 3440x1440: room for the panel on the right); or WxH. The game window is a borderless popup at the top left of the primary
    # screen, kept at that size for the whole session (the exe sizes its window to the screen at start and again on mode
    # changes; a hidden keeper puts it back). dgVoodoo.conf gets [Glide] Resolution = 2 x the window (a 2x2 supersample, capped
    # 8192 per side) for this launch only (the previous conf comes back when the game exits), and the proxy's camera / HUD /
    # Esc-menu aspect keys (I76_ASPECT, I76_U32X_MENU_ASPECT) take the window's shape. The menu pointer map follows the live
    # client rect by itself (proxy cursormap.c). PLAY.bat --windowed [WxH] passes it.
    [string]$Windowed = '',
    # The FFB / LFE tuning page (tools\ffb\ffb-panel.py, http://127.0.0.1:17691/): started with the interposer and opened in
    # the browser. Needs Python 3. PLAY.bat --panel passes it. Without a wheel (no interposer) it says so and starts nothing.
    [switch]$Panel
)
$ErrorActionPreference = 'SilentlyContinue'

# ---- launcher log (2026-10-24): the .bat files run this script hidden, so what was switched on is also written
# to <game>\play-i76.log (the last 400 lines are kept). Lines are "<time> <text>".
$launchClock = [Diagnostics.Stopwatch]::StartNew()
$launchLog = Join-Path $GameDir 'play-i76.log'
function Write-LaunchLog([string]$text, [string]$color = 'Cyan') {
    Write-Host $text -ForegroundColor $color
    if ($DryRun) { return }
    try {
        $old = @(); if (Test-Path $launchLog) { $old = @(Get-Content $launchLog -Tail 399) }
        $line = "{0} +{1:0.00}s {2}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $launchClock.Elapsed.TotalSeconds, $text
        Set-Content -Path $launchLog -Value ($old + $line) -Encoding UTF8
    } catch { }
}

# ---- frame-rate preset ------------------------------------------------------
# $gameEnv is every environment variable the GAME gets that this shell does not have. It is
# applied through ProcessStartInfo at launch, so nothing here leaks into the shell that ran
# this script (the old code set $env:I76MUSIC_LOG / $env:I76_MISSION in the script's own
# process, which is the user's shell when the script is run by hand).
$gameEnv = [ordered]@{}

# presets\ lives beside this script in the repo; setup-windows.ps1 and the portable zip copy it
# beside the installed PLAY-i76.ps1, and the game folder is tried too.
$presetDirs = @((Join-Path $PSScriptRoot 'presets'), (Join-Path $GameDir 'presets')) | Where-Object { Test-Path $_ } | Select-Object -Unique

function Read-Preset([string]$path) {
    # Data file only: Import-PowerShellDataFile evaluates no code, so a preset cannot do
    # anything but name variables. ErrorAction Stop because the script runs SilentlyContinue.
    try { $d = Import-PowerShellDataFile -Path $path -ErrorAction Stop } catch { return $null }
    if (-not $d.ContainsKey('Env')) { return $null }
    $d
}

if ($Preset -eq '?' -or $Preset -eq 'list') {
    Write-Host "presets (PLAY-i76.ps1 -Preset <name>):" -ForegroundColor Cyan
    $files = @(foreach ($d in $presetDirs) { Get-ChildItem (Join-Path $d '*.psd1') -ErrorAction SilentlyContinue })
    if (-not $files) { Write-Host "  no presets\ folder found next to the script or in the game folder." -ForegroundColor Yellow }
    foreach ($f in ($files | Sort-Object Name -Unique)) {
        $d = Read-Preset $f.FullName
        if (-not $d) { Write-Host ("  {0,-20} (unreadable)" -f $f.BaseName) -ForegroundColor Red; continue }
        $vars = if ($d.Env.Count) { ($d.Env.Keys | Sort-Object | ForEach-Object { "$_=$($d.Env[$_])" }) -join ' ' } else { '(nothing set)' }
        Write-Host ("  {0,-20} {1}" -f $f.BaseName, $d.Summary)
        Write-Host ("  {0,-20} {1}" -f '', $vars) -ForegroundColor DarkGray
        Write-Host ("  {0,-20} {1}" -f '', $d.Verified) -ForegroundColor DarkGray
    }
    exit 0
}

$presetFile = $null
if ($Preset -match '\.psd1$' -and (Test-Path $Preset)) {
    $presetFile = (Resolve-Path $Preset).Path
} else {
    foreach ($d in $presetDirs) {
        $p = Join-Path $d "$Preset.psd1"
        if (Test-Path $p) { $presetFile = $p; break }
    }
}
$presetData = $null
if ($presetFile) {
    $presetData = Read-Preset $presetFile
    if (-not $presetData) {
        Write-Host "preset file $presetFile could not be read as a data file - launching with NO switches." -ForegroundColor Red
    }
} elseif ($Preset -ne 'stock') {
    # An unknown name must not silently become stock: the player asked for 60 fps and would get
    # 20 with nothing on screen to say why. Refuse instead.
    Write-Host "unknown preset '$Preset'. PLAY-i76.ps1 -Preset ? lists them." -ForegroundColor Red
    exit 2
}
# stock with no presets\ folder at all (an old portable zip) is fine: stock sets nothing.
if ($presetData) { foreach ($k in ($presetData.Env.Keys | Sort-Object)) { $gameEnv[$k] = [string]$presetData.Env[$k] } }

# ---- per-machine override: <GameDir>\presets\local.psd1 (2026-10-24, owner: machines differ - Macs ~60 fps under Wine, a 5090,
# this PC at 120). Same format as a preset (an Env hashtable). Its keys REPLACE the preset's; a key set to '' REMOVES the preset's
# key (the game's stock value). Created per machine (copy presets\graphics-mac / -balanced / -high.psd1 and edit), never shipped
# in a pack, gitignored. Not applied to preset stock (PLAY-VANILLA.bat stays the stock game) or with -NoLocal.
$localOverride = @()
$localFile = Join-Path $GameDir 'presets\local.psd1'
if ($Preset -ne 'stock' -and -not $NoLocal -and (Test-Path $localFile)) {
    $ld = Read-Preset $localFile
    if (-not $ld) {
        $localOverride += "local override $localFile could not be read as a data file - IGNORED"
    } else {
        foreach ($k in ($ld.Env.Keys | Sort-Object)) {
            $nv = [string]$ld.Env[$k]
            $was = if ($gameEnv.Contains($k)) { $gameEnv[$k] } else { '(unset)' }
            if ($nv -eq '') { if ($gameEnv.Contains($k)) { $gameEnv.Remove($k) }; $nv = '(unset)' } else { $gameEnv[$k] = $nv }
            $localOverride += ("local override: {0}={1} (preset {2})" -f $k, $nv, $was)
        }
        if (-not $ld.Env.Count) { $localOverride += "local override $localFile sets nothing" }
    }
} elseif (Test-Path $localFile) {
    $localOverride += ("local override presets\local.psd1 NOT applied ({0})" -f $(if ($NoLocal) { '-NoLocal' } else { 'preset stock stays stock' }))
}

# ---- tick override (-TickMs; TICK-FINISH s.19) ---------------------------------
if ($TickMs -or $CheckTickMs) {
    # a BOM or other non-ASCII bytes in front (tick-ms.txt saved by Notepad as UTF-8) are dropped; the rest must be a plain number
    $raw = ("$TickMs" -replace '^[^\x20-\x7E]+', '').Trim()
    $tv = 0.0
    $isNum = $raw -match '^\d+(\.\d+)?$' -and [double]::TryParse($raw, [Globalization.NumberStyles]::AllowDecimalPoint, [Globalization.CultureInfo]::InvariantCulture, [ref]$tv)
    if (-not $isNum -or $tv -lt 16.7 -or $tv -gt 66.7) {
        Write-Host ("REFUSED: tick '{0}' - give a number of milliseconds from 16.7 to 66.7, with a dot for decimals (e.g. 41.667, the 1997 car step). The game was not started." -f $TickMs) -ForegroundColor Red
        exit 4
    }
    if (-not $gameEnv.Contains('I76_SIM_TICK_MS')) {
        Write-Host ("REFUSED: preset {0} has no simulation tick (I76_SIM_TICK_MS), so there is nothing to change. Use a tick preset (PLAY-TICK.bat)." -f $Preset) -ForegroundColor Red
        exit 4
    }
    $tickOld = $gameEnv['I76_SIM_TICK_MS']
    $gameEnv['I76_SIM_TICK_MS'] = $tv.ToString('0.###', [Globalization.CultureInfo]::InvariantCulture)
    $steps = [Math]::Floor($tv / 50.0) + 1   # the engine's car stepper: floor(dt x 20) + 1 substeps
    $car = if ($steps -eq 1) { "the car in one {0} ms step" -f $gameEnv['I76_SIM_TICK_MS'] } else { "the car in {0} substeps of {1:0.##} ms (50 ms and over split the car step, as a slow 1997 frame did)" -f $steps, ($tv / $steps) }
    Write-Host ("tick {0} ms: {1:0.#} ticks/s, {2} (preset value {3} ms; 41.667 = 1997)" -f $gameEnv['I76_SIM_TICK_MS'], (1000.0 / $tv), $car, $tickOld) -ForegroundColor Cyan
    if ($CheckTickMs) { exit 0 }
}

# ---- legacy multiplayer menu (-LegacyMultiplayer / PLAY*.bat --legacy-multiplayer) ---------------
if ($LegacyMultiplayer) {
    $gameEnv['I76_MP_MENU'] = '0'
    $gameEnv['I76_AIMELEE_ARENAS'] = '0'   # and the 15 stock arenas stay stock (no AI pool): a stock joiner can play
    Write-Host "legacy multiplayer: I76_MP_MENU=0 - MULTI MELEE > HOST / JOIN show the stock MODEM / IPX / INTERNET / NULLMODEM row" -ForegroundColor Cyan
}

# ---- windowed (-Windowed auto | WxH; PLAY.bat --windowed) -----------------------
$winRect = $null; $winConfBak = $null
if ($Windowed) {
    Add-Type -AssemblyName System.Windows.Forms
    $scr = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    if ($Windowed -match '^\s*(\d+)\s*[xX]\s*(\d+)\s*$') { $ww = [int]$Matches[1]; $wh = [int]$Matches[2] }
    else {
        $ww = [int]([math]::Floor(($scr.Width - 880) / 2.0) * 2)
        $wh = [int]([math]::Floor($ww * $scr.Height / $scr.Width / 2.0) * 2)
    }
    $ww = [math]::Max(640, [math]::Min($ww, $scr.Width)); $wh = [math]::Max(480, [math]::Min($wh, $scr.Height))
    $winRect = @($scr.X, $scr.Y, $ww, $wh)
    $confPath = Join-Path $GameDir 'dgVoodoo.conf'
    if (Test-Path $confPath) {
        $ct = [IO.File]::ReadAllText($confPath, [Text.Encoding]::ASCII)
        $f = [math]::Min(2.0, [math]::Min(8192.0 / $ww, 8192.0 / $wh))
        $gw = [int]([math]::Floor($ww * $f / 2) * 2); $gh = [int]([math]::Floor($wh * $f / 2) * 2)
        $glRx = New-Object regex '(?ms)(^\[Glide\]\s.*?^Resolution\s*= )\d+x\d+'
        if ($glRx.IsMatch($ct) -and $ct -match '(?m)^FullScreenMode\s*= false') {
            $winConfBak = "$confPath.pre-windowed"
            Copy-Item $confPath $winConfBak -Force
            # AppControlledScreenMode = false: with the conf's own 'true' the game's exclusive full-screen request wins and dgVoodoo
            # keeps the window at the screen size, vetoing any resize (measured 2026-10-25: SetWindowPos returned TRUE and the rect
            # stayed 3440x1440); with 'false' it is a real window ([DirectX] Resolution sized, centred) that the keeper can size.
            $ct2 = $glRx.Replace($ct, ('${1}' + "${gw}x${gh}"), 1) -replace '(?m)^(AppControlledScreenMode\s*=\s*)true', '${1}false'
            [IO.File]::WriteAllText($confPath, $ct2, [Text.Encoding]::ASCII)
            Write-LaunchLog ("windowed {0}x{1} at the top left; dgVoodoo.conf [Glide] Resolution {2}x{3} for this launch (the previous conf is back when the game exits)" -f $ww, $wh, $gw, $gh) 'Cyan'
        } else {
            Write-LaunchLog ("windowed {0}x{1}: dgVoodoo.conf is not a windowed conf with a [Glide] Resolution line - the render size stays as it is" -f $ww, $wh) 'Yellow'
        }
    }
    $gameEnv['I76_ASPECT'] = "${ww}x${wh}"
    # the exe minimises itself when it loses activation (WndProc WM_ACTIVATEAPP 0, 0x404acc): a click on the panel beside it
    # would hide the game. The proxy's I76_NO_MINIMIZE turns that ShowWindow(SW_MINIMIZE) into SW_SHOWNA (strlkproxy.c); the game
    # still pauses while it is not the active window, as it always has.
    if (-not $gameEnv.Contains('I76_NO_MINIMIZE')) { $gameEnv['I76_NO_MINIMIZE'] = '1' }
    if ($gameEnv.Contains('I76_U32X_MENU_ASPECT')) { $gameEnv['I76_U32X_MENU_ASPECT'] = "${ww}:${wh}" }
}

# ---- AI skill (-AiSkill / PLAY-LAN.bat --ai-skill N) --------------------------
if ($AiSkill -ge 1) {
    $gameEnv['I76_AIMELEE_SKILL'] = "$AiSkill"
    Write-Host "AI skill: I76_AIMELEE_SKILL=$AiSkill (1 = best computer drivers, 5 = weakest; 3 = stock melee)" -ForegroundColor Cyan
}

# ---- preset guard: switch combinations with a known failure ------------------
# Judged on what the game will actually see: the preset's value, else this shell's (the game inherits it).
# tests/test_presets.py applies the same two rules to every presets\*.psd1.
function Get-GameVar([string]$name) {
    if ($gameEnv.Contains($name)) { return [string]$gameEnv[$name] }
    [string][Environment]::GetEnvironmentVariable($name)
}
$terrainLod = 0
[void][int]::TryParse((Get-GameVar 'I76_TERRAIN_LOD'), [ref]$terrainLod)
if ($terrainLod -gt 1 -and -not (Get-GameVar 'I76_FAR_CLIP')) {
    # Refuse: binoculars write past the stock transformed-vertex pool (exe+0x919B1), 3 of 3 batches on t05;
    # only I76_FAR_CLIP enlarges the pools (lab docs\RENDER-FREEZE-2026-10-04.md section 4).
    Write-Host ("REFUSED: preset {0} sets I76_TERRAIN_LOD={1} without I76_FAR_CLIP. More terrain detail overruns the stock terrain vertex pool in binoculars (crashed 3 of 3, lab RENDER-FREEZE-2026-10-04.md s.4); only I76_FAR_CLIP enlarges it. Add I76_FAR_CLIP (the shipped presets use 1200 or 1800) or drop I76_TERRAIN_LOD." -f $Preset, $terrainLod) -ForegroundColor Red
    exit 3
}
$collWindow = Get-GameVar 'I76_COLL_WINDOW'
if ($collWindow -and $collWindow -ne '0' -and -not (Get-GameVar 'I76_FIXED_STEP')) {
    # Warn only: without the fixed step there is no step to widen the sweep to, so the switch does nothing
    # (music-fix/README.md, I76_COLL_WINDOW: "needs I76_FIXED_STEP"; stock timing is left unchanged).
    Write-Host ("WARNING: I76_COLL_WINDOW={0} without I76_FIXED_STEP has no effect (the collision window is widened to the fixed physics step; there is none)." -f $collWindow) -ForegroundColor Yellow
}

# The switches are implemented by music-fix/Strlkup.dll, so a preset that sets any of them is
# a no-op unless the game folder's Strlkup.dll is (a) the proxy and (b) the build that knows
# them. The playable install has run an older proxy build for weeks (backlog P1-07): compare
# size + md5 against the repo's copy and SAY so. Nothing is copied here - deploying a DLL to the
# install the owner plays on is its own deliberate step (setup-windows.ps1 / the deploy step).
if ($gameEnv.Count) {
    $installed = Join-Path $GameDir 'Strlkup.dll'
    $reference = Join-Path $PSScriptRoot 'music-fix\Strlkup.dll'
    if (-not (Test-Path (Join-Path $GameDir 'strlkup_orig.dll'))) {
        Write-Host "WARNING: the music-fix proxy is not deployed in $GameDir (no strlkup_orig.dll) - every I76_* switch in this preset is a NO-OP. Run setup-windows.ps1 (it deploys Strlkup.dll)." -ForegroundColor Red
    } elseif (Test-Path $reference) {
        $iLen = (Get-Item $installed).Length; $rLen = (Get-Item $reference).Length
        $iMd5 = (Get-FileHash $installed -Algorithm MD5).Hash; $rMd5 = (Get-FileHash $reference -Algorithm MD5).Hash
        if ($iLen -ne $rLen -or $iMd5 -ne $rMd5) {
            Write-Host ("WARNING: {0} is {1} B md5 {2}, not the current music-fix build ({3} B md5 {4}) - switches it does not know are silently ignored. Run setup-windows.ps1 (or the deploy step) to update it; this launcher copies nothing." -f $installed, $iLen, $iMd5.Substring(0,8), $rLen, $rMd5.Substring(0,8)) -ForegroundColor Yellow
        } else {
            Write-Host ("Strlkup.dll matches music-fix\Strlkup.dll ({0} B md5 {1})." -f $iLen, $iMd5.Substring(0,8)) -ForegroundColor DarkGray
        }
    } elseif (Test-Path (Join-Path $GameDir 'strlkup-proxy-build.txt')) {
        # An installed launcher has no music-fix\ beside it: check against the build setup-windows.ps1
        # recorded when it deployed the proxy (line 1: md5 and size). Says nothing about newer repo builds.
        $rec = "$(Get-Content (Join-Path $GameDir 'strlkup-proxy-build.txt') -TotalCount 1)".Trim()
        $iLen = (Get-Item $installed).Length; $iMd5 = (Get-FileHash $installed -Algorithm MD5).Hash.ToLower()
        if ($rec -eq "$iMd5 $iLen") {
            Write-Host ("Strlkup.dll is the build the setup deployed ({0} B md5 {1})." -f $iLen, $iMd5.Substring(0,8)) -ForegroundColor DarkGray
        } else {
            Write-Host ("WARNING: {0} is {1} B md5 {2}, not the build the setup deployed (strlkup-proxy-build.txt: {3}) - switches it does not know are silently ignored. Re-run setup-windows.ps1 to put the proxy back; this launcher copies nothing." -f $installed, $iLen, $iMd5.Substring(0,8), $rec) -ForegroundColor Yellow
        }
    }   # neither music-fix\ nor a record (an older install): nothing to compare against, so nothing is said
    # GOG's I76PATCH.DLL is the AiO 20 fps cap. With it in place a 60 fps preset runs its fixes
    # under a 20 fps cap, which looks exactly like "the preset does nothing". Say so; renaming
    # it is a file change to the install and is left to the owner (RELEASE-PLAN section 2).
    if (Test-Path (Join-Path $GameDir 'I76PATCH.DLL')) {
        Write-Host "note: I76PATCH.DLL (GOG's 20 fps cap) is present in $GameDir - the frame rate stays ~20 until it is renamed (e.g. I76PATCH.DLL.disabled). This launcher does not rename it." -ForegroundColor Yellow
    }
}

# Print what the game will get, before anything starts.
$presetLabel = if ($presetData) { $presetData.Name } else { 'stock' }
if ($gameEnv.Count) {
    Write-Host ("preset {0}: {1}" -f $presetLabel, $presetData.Summary) -ForegroundColor Cyan
    foreach ($k in $gameEnv.Keys) { Write-Host ("  {0}={1}" -f $k, $gameEnv[$k]) -ForegroundColor Cyan }
    if ($presetData.Verified) { Write-Host ("  {0}" -f $presetData.Verified) -ForegroundColor DarkGray }
} else {
    Write-Host "preset $presetLabel (no engine switches)" -ForegroundColor DarkGray
}
Write-LaunchLog ("---- PLAY-i76.ps1 {0}" -f (($MyInvocation.BoundParameters.GetEnumerator() | ForEach-Object { if ($_.Value -is [switch]) { "-$($_.Key)" } else { "-$($_.Key) $($_.Value)" } }) -join ' ')) 'DarkGray'
foreach ($lo in $localOverride) { Write-LaunchLog $lo 'Yellow' }

# music-fix/ (the Strlkup.dll IAT hook that restores the CD-audio soundtrack) logs to
# mciproxy.log only when this is set. Set UNCONDITIONALLY: it was opt-in, which meant the
# normal launch path - desktop shortcut -> .bat -> here, no env var anywhere - produced no
# log, and "hook installed but silent" looked exactly like "hook never ran". A handful of
# lines per session is worth never being blind again. (Game process only, see $gameEnv.)
$gameEnv['I76MUSIC_LOG'] = '1'

if ($Mission) {
    if (-not (Test-Path (Join-Path $GameDir 'strlkup_orig.dll'))) {
        Write-Host "-Mission needs the music-fix proxy deployed (it applies the patch)." -ForegroundColor Yellow
        Write-Host "  build it with: music-fix\build.ps1 -Install" -ForegroundColor DarkGray
    } else {
        $gameEnv['I76_MISSION'] = $Mission
        if ($SkipMovies) { $gameEnv['I76_SKIP_MOVIES'] = '1' }
        Write-Host "booting directly into $Mission$(if ($SkipMovies) { ' (movies skipped)' })" -ForegroundColor Cyan
    }
}

if ($DryRun) {
    Write-Host "DRY RUN - nothing started." -ForegroundColor Yellow
    Write-Host ("  command:  `"{0}`" -glide" -f (Join-Path $GameDir $Exe))
    Write-Host ("  cwd:      {0}" -f $GameDir)
    Write-Host  "  environment handed to the game process (in addition to this shell's):"
    foreach ($k in $gameEnv.Keys) { Write-Host ("    {0}={1}" -f $k, $gameEnv[$k]) }
    $skipped = @()
    if ($LosslessScaling -and (Test-Path $LosslessScaling)) { $skipped += 'Lossless Scaling' }
    if (-not $NoHeadTrack -and $OpenTrack -and (Test-Path $OpenTrack) -and (Test-Path (Join-Path $GameDir '_ahk\i76-opentrack-headlook.ahk')) -and ($HeadTrack -or (Get-Process -Name 'opentrack' -ErrorAction SilentlyContinue))) { $skipped += 'opentrack + head look' }
    if (Test-Path (Join-Path $GameDir '_ahk\AutoHotkeyU32.exe')) { $skipped += 'AHK layers' }
    if ($Ffb -and -not $NoFfb) { $skipped += 'FFB interposer' } elseif (-not $NoFfb) { $skipped += 'FFB interposer if a wheel is found' }
    if ($skipped) { Write-Host ("  helpers that a real run would also start: {0}" -f ($skipped -join ', ')) -ForegroundColor DarkGray }
    exit 0
}

$wheel = $null
# Controls mode of this folder, as setup-windows.ps1 recorded it (absent = i76e, this project's map).
$controlsMode = Get-Content (Join-Path $GameDir 'i76e-controls.txt') -TotalCount 1 -ErrorAction SilentlyContinue
if ($controlsMode -eq 'stock' -and -not $PSBoundParameters.ContainsKey('WheelUp')) { $WheelUp = 'Enter' }
if (Test-Path (Join-Path $GameDir 'i76wheel.exe')) {
    # Mouse wheel -> keystroke. Which hardpoint holds the dropper depends on the
    # car's loadout, not on the game, so it is a parameter rather than a constant.
    $wheel = Start-Process -FilePath (Join-Path $GameDir 'i76wheel.exe') `
        -ArgumentList "/up=$WheelUp","/down=$WheelDown" -PassThru
}

# The XInput/shift-layer controller scheme (i76-remap.ahk): AutoHotkey inside the
# game folder emits the engine's stock keys for triggers, the LB shift layer,
# look-back fire, camera cycle and rumble. Started with the game and killed on
# exit (same lifetime model the Mac launcher and i76-with-remap.bat use), so its
# global hotkeys only live during a play session. Connect the pad BEFORE launch.
$ahk = $null
$ahkExe = Join-Path $GameDir '_ahk\AutoHotkeyU32.exe'
$ahkCfg = Join-Path $GameDir '_ahk\i76-remap.ahk'
if ((Test-Path $ahkExe) -and (Test-Path $ahkCfg)) {
    $ahk = Start-Process -FilePath $ahkExe -ArgumentList "`"$ahkCfg`"" -WorkingDirectory (Join-Path $GameDir '_ahk') -PassThru
}

# CH Fighterstick HOTAS layer (docs/FIGHTERSTICK.md): the stick's deflection is the
# gearbox and handbrake, its grip buttons are weapons and targeting. Started here
# for the same reason as the remapper - so it lives exactly as long as the play
# session does - and started UNCONDITIONALLY, because the script identifies the
# device itself and exits immediately if no Fighterstick is plugged in. That keeps
# the decision in one place rather than duplicating device detection here.
# -NoStick skips it.
$stick = $null
# The on-screen pointer. Started before the stick so it is up by the time the menus are, and
# it hides itself whenever the game is not the active window (see the script).
$cursorCfg = Join-Path $GameDir '_ahk\i76-cursor-overlay.ahk'
if ($CursorOverlay -and -not $NoCursorOverlay -and (Test-Path $ahkExe) -and (Test-Path $cursorCfg)) {
    $cursor = Start-Process -FilePath $ahkExe -ArgumentList "`"$cursorCfg`"" -WorkingDirectory (Join-Path $GameDir '_ahk') -PassThru
}

$stickCfg = Join-Path $GameDir '_ahk\i76-ch-fighterstick.ahk'
if (-not $NoStick -and (Test-Path $ahkExe) -and (Test-Path $stickCfg)) {
    $stick = Start-Process -FilePath $ahkExe -ArgumentList "`"$stickCfg`"" -WorkingDirectory (Join-Path $GameDir '_ahk') -PassThru
}

# Head tracking: opentrack + the freetrack->game layer. opentrack has NO command-line switch to begin
# tracking, and the old i76-opentrack-autostart.ahk never managed to press Start (opentrack 2026.1 is
# Qt 6: its buttons are not windows, so ControlClick found nothing - owner 2026-10-24, reproduced).
# Now, either is enough (docs/HEAD-TRACKING.md):
#  1. opentrack's own Options > Game detection, switched on here for i76.exe -> the current profile
#     BEFORE opentrack starts (it reads the setting at start): opentrack starts tracking ~1 s after the
#     game's process appears and stops when it exits. Existing rows are kept. It is a setting of the
#     owner's opentrack, so it also applies when opentrack is opened by hand and any i76.exe runs;
#     switch it off in opentrack's Options > Game detection.
#  2. _ahk\i76-opentrack-autostart.ps1 (hidden): if tracking is not live a few seconds after the game
#     starts (or opentrack was already open), it presses Start through UI Automation. Both verify that
#     FT_SharedMem's DataID advances, not merely that it exists. Log: _ahk\opentrack-autostart.log.
function Enable-OpentrackGameDetect {
    # Global settings: HKCU\Software\opentrack-2.3\OrganizationDefaults (QSettings). The list is
    # exe <0x1F> profile, records joined by <0x1E> (opentrack gui/process_detector.cpp).
    $key = 'HKCU:\Software\opentrack-2.3\OrganizationDefaults'
    try {
        if (-not (Test-Path $key)) { New-Item -Path $key -Force | Out-Null }
        $US = [char]0x1F; $RS = [char]0x1E
        $cur = (Get-ItemProperty -Path $key -Name 'executable-list' -ErrorAction SilentlyContinue).'executable-list'
        $on  = (Get-ItemProperty -Path $key -Name 'executable-detector-enabled' -ErrorAction SilentlyContinue).'executable-detector-enabled'
        $otProfile = 'default.ini'
        $iniDir = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'opentrack-2.3'
        if (-not (Test-Path (Join-Path $iniDir $otProfile))) {
            $first = Get-ChildItem $iniDir -Filter *.ini -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($first) { $otProfile = $first.Name }
        }
        $rows = @(); if ($cur) { $rows = @($cur -split [regex]::Escape([string]$RS) | Where-Object { $_ }) }
        $have = @($rows | ForEach-Object { ($_ -split [regex]::Escape([string]$US))[0] })
        $changed = $false
        # opentrack compares process names case-sensitively (as Windows reports them)
        foreach ($exe in @('i76.exe', 'I76.EXE', 'I76.exe')) {
            if ($have -notcontains $exe) { $rows += "$exe$US$otProfile"; $changed = $true }
        }
        if ($changed) { Set-ItemProperty -Path $key -Name 'executable-list' -Value ($rows -join $RS) -Type String }
        if ("$on" -ne 'true') { Set-ItemProperty -Path $key -Name 'executable-detector-enabled' -Value 'true' -Type String; $changed = $true }
        return @{ ok = $true; changed = $changed; profile = $otProfile }
    } catch { return @{ ok = $false; changed = $false; error = $_.Exception.Message } }
}
$ot = $null
$otHelper = $null
$track = $null
$otDetect = $false
# Opt-out, never blocking (2026-10-24): decide once, say it once, move on.
$headOn = $false
$headStatus = ''
if ($NoHeadTrack) {
    $headStatus = 'head look: OFF (-NoHeadTrack)'
} elseif (-not $OpenTrack -or -not (Test-Path $OpenTrack)) {
    $headStatus = "head look: skipped - opentrack is not installed ($OpenTrack)"
    if ($HeadTrack) { $headStatus += ' although -HeadTrack was given' }
} elseif (-not ((Test-Path $ahkExe) -and (Test-Path (Join-Path $GameDir '_ahk\i76-opentrack-headlook.ahk')))) {
    # e.g. the patch kit: no head-look layer in this folder, so starting opentrack would do nothing for the game
    $headStatus = 'head look: skipped - this folder has no head-look layer (_ahk\i76-opentrack-headlook.ahk)'
} elseif (-not $HeadTrack -and -not (Get-Process -Name 'opentrack' -ErrorAction SilentlyContinue)) {
    # 2026-10-25 (owner: "if it's not set up or running, just skip it"): the default only ATTACHES to an opentrack that is already
    # running; it never starts one (a launched opentrack cost ~17 fps at 120 fps in the gate). -HeadTrack starts it as before.
    $headStatus = 'head look: skipped - opentrack is not running (start opentrack first if you want head look; the launcher attaches to it; -HeadTrack starts it)'
} else {
    $headOn = $true
}
if ($headOn) {
    if (-not (Get-Process -Name 'opentrack' -ErrorAction SilentlyContinue)) {
        $det = Enable-OpentrackGameDetect
        if ($det.ok) {
            $otDetect = $true
            if ($det.changed) { Write-Host ("opentrack: game detection switched on (i76.exe -> {0}); it starts tracking when the game starts" -f $det.profile) -ForegroundColor DarkGray }
        } else { Write-Host "opentrack: could not set game detection ($($det.error)) - the Start button will be pressed instead" -ForegroundColor Yellow }
        try { $ot = Start-Process -FilePath $OpenTrack -WindowStyle Minimized -PassThru -ErrorAction Stop } catch { $ot = $null }
        if (-not $ot) {
            $headOn = $false
            $headStatus = "head look: skipped - opentrack did not start ($OpenTrack)"
        } else {
            $headStatus = 'head look: ON (opentrack started; tracking begins when the game starts)'
        }
    } else {
        $headStatus = 'head look: ON (opentrack was already running)'
    }
}
if ($headOn) {
    $autoStartPs = Join-Path $GameDir '_ahk\i76-opentrack-autostart.ps1'
    $autoStart = Join-Path $GameDir '_ahk\i76-opentrack-autostart.ahk'
    if (Test-Path $autoStartPs) {
        $a = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$autoStartPs`"", '-Log', "`"$(Join-Path $GameDir '_ahk\opentrack-autostart.log')`"")
        if ($otDetect) { $a += '-WaitGame' }
        $otHelper = Start-Process -FilePath 'powershell.exe' -ArgumentList $a -WindowStyle Hidden -PassThru
    } elseif ((Test-Path $ahkExe) -and (Test-Path $autoStart)) {
        $otHelper = Start-Process -FilePath $ahkExe -ArgumentList "`"$autoStart`"" -PassThru
    }
}
$trackCfg = Join-Path $GameDir '_ahk\i76-opentrack-headlook.ahk'
if ($headOn -and (Test-Path $ahkExe) -and (Test-Path $trackCfg)) {
    $env:I76_HEADLOOK_MODE = $HeadLookMode
    $track = Start-Process -FilePath $ahkExe -ArgumentList "`"$trackCfg`"" -WorkingDirectory (Join-Path $GameDir '_ahk') -PassThru
    Remove-Item Env:\I76_HEADLOOK_MODE -ErrorAction SilentlyContinue
    Write-Host ("head look: {0} at start.  Ctrl+Alt+H cycles ANALOG -> DIGITAL -> OFF (shown on screen)." -f $HeadLookMode) -ForegroundColor Cyan
    Write-Host  "  Hold any glance key / button (arrows, middle mouse, pad right stick, stick hat) to override it." -ForegroundColor DarkGray
}
Write-LaunchLog $headStatus $(if ($headOn) { 'Cyan' } else { 'DarkGray' })

# Frame generation (Lossless Scaling), optional. The engine's physics are locked
# at 20 FPS and break above ~25 (docs/STEAMDECK.md sec 5), so the ONLY way to a
# smoother picture is interpolating display frames on top - which is exactly what
# LSFG does. VERIFIED 2026-08-01: Lossless Scaling has NO Steam dependency -
# launched directly it loads zero steam_api/steamclient/overlay modules and
# nothing from outside its own folder, so Steam never has to be running.
# The "Interstate '76 Gold Edition" profile in
# %LOCALAPPDATA%\Lossless Scaling\Settings.xml has AutoScale=true + a 2x fixed
# multiplier, so it engages on its own when the game window appears - no hotkey.
# Set ForceVerticalSync=false in dgVoodoo.conf so LS owns presentation.
# We only stop it if WE started it (don't kill a session the user already had up).
$ls = $null
if ($LosslessScaling -and (Test-Path $LosslessScaling)) {
    if (-not (Get-Process -Name 'LosslessScaling' -ErrorAction SilentlyContinue)) {
        $ls = Start-Process -FilePath $LosslessScaling -PassThru
        Start-Sleep -Seconds 2   # let it register its window hook before the game appears
    }
}

# ---- ORDER MATTERS -----------------------------------------------------------
# The game is started LAST, on purpose:
#   * the 1997 engine enumerates joysticks ONLY at startup, so the wheel must be
#     present and settled first;
#   * FFB is acquired once at startup too, so nothing else may be grabbing the
#     device at that moment;
#   * i76-remap.ahk detects the wheel by capability once when it starts.
# opentrack is NOT waited for (2026-10-24; it was a bounded 20 s wait for FT_SharedMem when game detection could
# not be set): the head-look layer retries FT_SharedMem on every 8 ms tick (OpenFT in i76-opentrack-headlook.ahk)
# and the autostart helper presses Start in the background, so head look comes up whenever tracking does.
# ---- savegame.dir short-file guard ---------------------------------------------
# CORRECTED 2026-10-01. This block used to say the engine writes its save index 36 bytes short on every save. It
# does not: a directory is exactly 4 + 60 x count bytes (u32 count, then 60-byte records {u32 scene, name[32],
# file[16], u32 state, u32 0}). The "36 missing bytes" were the save editor's model (0x28 header, scene at +0x18 of
# a record starting 36 bytes late), which read each record's scene from the record after it. The 2026-09-05 field
# case ("304 bytes where 5 records need 340") was a complete 5-record file. The guard now pads only a file that is
# really shorter than 4 + 60 x count, which the game has never been seen to write, and no longer rewrites whole files
# or keeps .trunc copies of them.
$dirPath = Join-Path $GameDir 'savegame.dir'
if (Test-Path $dirPath) {
    $sg = [IO.File]::ReadAllBytes($dirPath)
    if ($sg.Length -ge 4) {
        $count = [BitConverter]::ToUInt32($sg, 0)
        $want  = 4 + $count * 60
        # sanity-bound the count so a corrupt header can never make us write a
        # huge file; 64 bookmarks is far beyond anything the engine offers.
        if ($count -ge 1 -and $count -le 64 -and $sg.Length -lt $want) {
            $bak = "$dirPath.trunc-" + (Get-Date -Format 'yyyyMMdd-HHmmss')
            Copy-Item $dirPath $bak -Force
            $fixed = New-Object byte[] $want
            [Array]::Copy($sg, $fixed, $sg.Length)      # zero-fill the rest
            [IO.File]::WriteAllBytes($dirPath, $fixed)
            Write-Host ("savegame.dir was short ({0} bytes, need {1} for {2} records) - padded with zeros. Original kept as {3}." -f $sg.Length, $want, $count, (Split-Path $bak -Leaf)) -ForegroundColor Yellow
        }
    }
}

# ---- shell text-entry guard --------------------------------------------------
# YOU CAN ONLY TYPE ONE CHARACTER (USUALLY NONE) INTO A BOOKMARK NAME, and the
# overwrite prompt cannot be answered. Not an engine bug - two bytes in the widely
# circulated patched i76shell.dll:
#
#     stock    mov ecx, 0x41  /  lea edi, [esp+8]      zeroes esp+8 .. esp+0x10B
#     patched  mov ecx, 0x40  /  lea edi, [esp+0xC]    zeroes esp+0xC .. esp+0x10B
#
# esp+8 is the WORD ToAscii writes the character into; esp+0xC is the 256-byte key
# state (confirmed by +0x1C14C `mov byte [esp+0x1C],0x80` setting keystate[VK_SHIFT]).
# The stock clear covers output + key state exactly - 4 + 256 = 0x104 - overrunning
# nothing, so the "out-of-bounds write" the narrowing was meant to fix is not there.
# What it does cause is the output word being read back uninitialised at +0x1C16F
# (`mov eax,[esp+8]` / `and eax,0xffff`), so 'a' arrives as 0xB261 and the field
# drops it. Intermittent only because stale stack is occasionally zero - that is
# the one character that sometimes gets through.
#
# Measured 2026-09-06: before, ToAscii returned 0xB261/0xE90D; after, 0x0068/0x000D,
# and "HELLO" typed, displayed and saved. Same repair as tools\fix-shell-textentry.ps1.
$shellPath = Join-Path $GameDir 'i76shell.dll'
if (Test-Path $shellPath) {
    $sh = [IO.File]::ReadAllBytes($shellPath)
    if ($sh.Length -gt 0x1B535 -and $sh[0x1B52C] -eq 0x40 -and $sh[0x1B535] -eq 0x0C) {
        $bak = "$shellPath.pre-toascii-fix"
        if (-not (Test-Path $bak)) { Copy-Item $shellPath $bak -Force }
        $sh[0x1B52C] = 0x41
        $sh[0x1B535] = 0x08
        [IO.File]::WriteAllBytes($shellPath, $sh)
        $chk = [IO.File]::ReadAllBytes($shellPath)          # never trust the write
        if ($chk[0x1B52C] -eq 0x41 -and $chk[0x1B535] -eq 0x08) {
            Write-Host "i76shell.dll could not accept typed text - repaired." -ForegroundColor Yellow
            Write-Host "  Bookmark names and the overwrite prompt work now. Original kept as" -ForegroundColor DarkGray
            Write-Host ("  {0}." -f (Split-Path $bak -Leaf)) -ForegroundColor DarkGray
        } else {
            Write-Host "i76shell.dll text-entry repair did NOT stick - is the file read-only?" -ForegroundColor Red
        }
    }
}

# ---- input.map guard --------------------------------------------------------
# The in-game controls menu REWRITES input.map and silently drops joystick BUTTON
# blocks while leaving the two analog lines intact. The result is the symptom that
# has now cost two sessions: steering, pedals and force feedback all work, and no
# button does anything - with the device innocent (winmm still enumerates all 13
# buttons) and the linter clean (what survives IS valid, there is just nothing
# bound).
#
# WHAT THIS TESTS CHANGED 2026-08-08, and the reason matters.
#
# It used to check "analog joystick lines but no joystick Button binding". That was
# right while input.map carried a button tier. It no longer does: buttons are owned
# by i76-remap.ahk (docs/WHEEL-T300.md), which gives a shift layer worth ~27 actions
# from 13 buttons - something native binding cannot express, since it tops out at
# one action per button. Under that design "axes but no buttons" is the CORRECT
# state, and the old test would have fired on every launch and pasted a stale map
# over a good one.
#
# The protection is still wanted, so it now watches what actually kills the wheel,
# and what AGENTS.md names FIRST in the corruption signature: the ANALOG SINKS. A
# menu rewrite drops the steer/throttle blocks, and with no analog sink there is no
# steering and no pedals however healthy the device is. That test is independent of
# where buttons live, so it holds under either design.
$mapPath = Join-Path $GameDir 'input.map'
if (Test-Path $mapPath) {
    $mapText = Get-Content $mapPath -Raw
    $hasAxis   = ($mapText -match '(?ims)^\s*steer\s*\{[^}]*joystick\d*\s+\S+/\S+') -and
                 ($mapText -match '(?ims)^\s*throttle\s*\{[^}]*joystick\d*\s+\S+/\S+')
    $hasButton = $true   # buttons live in i76-remap.ahk now, not here
    if (-not $hasAxis) {
        Write-Host "input.map has lost a joystick ANALOG SINK (steer / throttle) -" -ForegroundColor Yellow
        Write-Host "the in-game controls menu has rewritten it. No analog sink = no wheel, no pedals." -ForegroundColor Yellow
        # Pick a backup by the SAME test that just failed - intact analog sinks -
        # not by the old button-tier test, or we would restore a map that is broken
        # in precisely the way we are trying to repair.
        #
        # 2026-10-03, the two -Controls modes of setup-windows.ps1 (i76e = this project's
        # map, stock = GOG's keys + a minimal patch). Both leave joystick1 analog sinks, so
        # this guard does not fire on either. When it DOES fire it must not switch modes:
        # "newest backup with sinks" could be input.map.before-i76e-* (a stock-keys map) in a
        # folder whose AutoHotkey layers type the i76e keys, or the other way round. So:
        #   - input.map.as-installed (what the installer last left, either mode) is tried first;
        #   - input.map.stock-*, .before-i76e-* and .before-stock-* (the mode switch's own
        #     backups) are never candidates.
        # A folder the installer has not touched since has none of those names: unchanged there.
        $bak = Get-ChildItem (Join-Path $GameDir 'input.map.*') -ErrorAction SilentlyContinue |
               Where-Object { $_.Name -notmatch '\.(stripped|stock|before-i76e|before-stock)-' } |
               Sort-Object @{ Expression = { $_.Name -ne 'input.map.as-installed' } }, @{ Expression = { $_.LastWriteTime }; Descending = $true } |
               Where-Object {
                   $t = Get-Content $_.FullName -Raw
                   ($t -match '(?ims)^\s*steer\s*\{[^}]*joystick\d*\s+\S+/\S+') -and
                   ($t -match '(?ims)^\s*throttle\s*\{[^}]*joystick\d*\s+\S+/\S+')
               } | Select-Object -First 1
        if ($bak) {
            Copy-Item $mapPath (Join-Path $GameDir ("input.map.stripped-" + (Get-Date -Format 'yyyyMMdd-HHmmss'))) -Force
            Copy-Item $bak.FullName $mapPath -Force
            Write-Host ("restored analog sinks from {0}" -f $bak.Name) -ForegroundColor Green
        } else {
            Write-Host "no backup with intact analog sinks found - the wheel will be dead." -ForegroundColor Red
            Write-Host "Restore input.map from the portable zip, then re-lint with" -ForegroundColor Red
            Write-Host "  python3 tools/lint-input-map.py '$GameDir'" -ForegroundColor Red
        }
    }
}

# NOTHING MAY BE HOLDING THE WHEEL WHEN THE GAME STARTS.
#
# tools/ffb/ffb-interposer.ps1 takes an EXCLUSIVE DirectInput acquisition. If one
# is still running from a previous session - easy to do, since it lives in its own
# terminal window and outlives the game - then the engine's one-shot FFB acquire
# fails at startup and there is NO force feedback for the whole session, with
# nothing on screen to say why. Field-hit 2026-08-04 exactly this way.
#
# So clear it here rather than relying on anyone remembering the order. The
# interposer now also exits on its own when the game closes; this is the backstop
# for one that was started by hand, or that hung.
$stale = @(Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
           Where-Object { $_.CommandLine -match 'ffb-interposer\.ps1' })
foreach ($sp in $stale) {
    Write-Host "stopping a running FFB interposer (PID $($sp.ProcessId)) - it holds the wheel exclusively" -ForegroundColor Yellow
    Stop-Process -Id $sp.ProcessId -Force -ErrorAction SilentlyContinue
}
if ($stale.Count) { Start-Sleep -Milliseconds 700 }   # let the device release

Start-Sleep -Milliseconds 800     # let the AHK layers finish their device probe

# (I76MUSIC_LOG and I76_MISSION / I76_SKIP_MOVIES are in $gameEnv, set above with the preset.)

# music-fix/ (the deployed Strlkup.dll IAT hook) is the REAL soundtrack fix and it is
# SYNCHRONISED - the game picks its own track. tools/i76-music.ps1 is only a stopgap
# that plays the MP3s alongside the game in a fixed order. Running both gives two
# soundtracks out of step with each other, which is exactly what "random music plays
# when launched" was. If the hook is deployed, the stopgap stays off. strlkup_orig.dll
# is the marker: it only exists because the proxy displaced the original.
if (-not $NoMusic -and (Test-Path (Join-Path $GameDir 'strlkup_orig.dll'))) {
    Write-Host "music-fix (Strlkup hook) is deployed - not starting the i76-music stopgap." -ForegroundColor DarkGray
    $NoMusic = $true
}

# ProcessStartInfo rather than Start-Process so the preset's I76_* variables (and the log /
# mission switches) exist in the GAME process only. PowerShell 5.1's Start-Process has no
# -Environment, and $env: assignments would land in the shell that ran this script.
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName         = Join-Path $GameDir $Exe
$psi.Arguments        = '-glide'
$psi.WorkingDirectory = $GameDir
$psi.UseShellExecute  = $false
foreach ($k in $gameEnv.Keys) { $psi.EnvironmentVariables[$k] = [string]$gameEnv[$k] }
$proc = [System.Diagnostics.Process]::Start($psi)
if (-not $proc) {
    Write-LaunchLog ("could not start {0}" -f $psi.FileName) 'Red'
} else {
    Write-LaunchLog ("game started: {0} pid {1}, preset {2}{3}" -f $Exe, $proc.Id, $presetLabel, $(if ($gameEnv.Contains('I76_MISSION')) { ", mission $($gameEnv['I76_MISSION'])" })) 'DarkGray'
}

# Custom force feedback, AFTER the game: it reads the game's own memory, so the
# process has to exist first. It waits for a mission to load on its own (the
# player entity only exists in one), so starting it here rather than making the
# user launch it by hand mid-mission is safe. Own window so the panel is visible.
$ffbProc = $null
$ffbDir = Join-Path $PSScriptRoot 'tools\ffb'
if (-not (Test-Path (Join-Path $ffbDir 'ffb-interposer.ps1'))) { $ffbDir = Join-Path $GameDir '_ffb' }
$ffbScript = Join-Path $ffbDir 'ffb-interposer.ps1'
$ffbStatus = ''
$ffbWant = $false
if ($NoFfb) {
    $ffbStatus = "FFB: the game's own (-NoFfb)"
} elseif (-not (Test-Path $ffbScript)) {
    $ffbStatus = "FFB: the game's own - the interposer (ffb-interposer.ps1) is not in this folder"
    if ($Ffb) { $ffbStatus += ' although -Ffb was given' }
} elseif ($Ffb) {
    $ffbWant = $true; $ffbStatus = 'FFB: custom interposer ON (-Ffb)'
} else {
    # Probe AFTER the game has started, so it adds nothing to the time to the game. Enumeration only (Ffb-Probe).
    $wheels = @()
    try {
        . (Join-Path $ffbDir 'FfbCore.ps1')
        if (Get-Command Ffb-Probe -ErrorAction SilentlyContinue) { $wheels = @(Ffb-Probe) } else { $wheels = $null }
    } catch { }
    $pick = @($wheels | Where-Object { $_.Wheel }) | Select-Object -First 1
    if ($null -eq $wheels) {
        $ffbStatus = "FFB: the game's own - this folder's FfbCore.ps1 has no Ffb-Probe (older than 2026-10-24); -Ffb starts the interposer anyway"
    } elseif ($pick) {
        $ffbWant = $true; $ffbStatus = ("FFB: custom interposer ON - wheel found: {0}" -f $pick.Name)
    } elseif ($wheels.Count) {
        $ffbStatus = ("FFB: the game's own - force-feedback device(s) but no wheel: {0}" -f (($wheels | ForEach-Object { '{0} (type 0x{1:X2})' -f $_.Name, $_.DevType }) -join ', '))
    } else {
        $ffbStatus = "FFB: the game's own - no force-feedback wheel attached"
    }
}
if ($ffbWant -and $proc) {
    try {
        $ffbProc = Start-Process -FilePath 'powershell.exe' `
            -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',"`"$ffbScript`"" -WindowStyle Hidden -PassThru -ErrorAction Stop
    } catch { $ffbProc = $null }
    if (-not $ffbProc) { $ffbStatus = "FFB: the game's own - the interposer did not start" }
    else { $ffbStatus += ' (it takes the wheel and turns the game''s own effects off while it runs; its panel is the window it opens)' }
}
Write-LaunchLog $ffbStatus $(if ($ffbProc) { 'Cyan' } else { 'DarkGray' })

# ---- the window keeper (-Windowed): the exe sizes its popup to the whole screen at start and on mode changes; this hidden
# helper puts it back to the window size every time (polled 4x a second, for the life of the game). Position: the top left
# until the window has the right size once; after that a move by the player is kept and only the size is restored.
$winKeeper = $null
if ($winRect -and $proc) {
    $keeper = @'
param([int]$GamePid, [int]$X, [int]$Y, [int]$W, [int]$H)
Add-Type -Namespace I76W -Name U -MemberDefinition @"
[DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, IntPtr a, int x, int y, int cx, int cy, uint f);
[DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
[DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
[DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint p);
public delegate bool EnumProc(IntPtr h, IntPtr l);
[DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
public struct RECT { public int L, T, R, B; }
"@
$p = Get-Process -Id $GamePid -ErrorAction SilentlyContinue
$px = $X; $py = $Y; $sized = $false
while ($p -and -not $p.HasExited) {
    $script:best = [IntPtr]::Zero; $script:area = 0; $script:rb = $null
    $cb = [I76W.U+EnumProc]{ param($h, $l)
        $o = 0; [void][I76W.U]::GetWindowThreadProcessId($h, [ref]$o)
        if ($o -eq $GamePid -and [I76W.U]::IsWindowVisible($h)) {
            $r = New-Object I76W.U+RECT; [void][I76W.U]::GetWindowRect($h, [ref]$r)
            $a = ($r.R - $r.L) * ($r.B - $r.T)
            if ($a -gt $script:area) { $script:area = $a; $script:best = $h; $script:rb = $r }
        }
        $true }
    [void][I76W.U]::EnumWindows($cb, [IntPtr]::Zero)
    $best = $script:best; $rb = $script:rb
    if ($best -ne [IntPtr]::Zero) {
        if (($rb.R - $rb.L) -ne $W -or ($rb.B - $rb.T) -ne $H) {
            [void][I76W.U]::SetWindowPos($best, [IntPtr]::Zero, $px, $py, $W, $H, 0x0014)   # NOZORDER | NOACTIVATE
        } else { $px = $rb.L; $py = $rb.T; $sized = $true }
    }
    Start-Sleep -Milliseconds 250
}
'@
    try {
        $kb64 = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes("& { $keeper } -GamePid $($proc.Id) -X $($winRect[0]) -Y $($winRect[1]) -W $($winRect[2]) -H $($winRect[3])"))
        $winKeeper = Start-Process -FilePath 'powershell.exe' -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-WindowStyle', 'Hidden', '-EncodedCommand', $kb64 -WindowStyle Hidden -PassThru
        Write-LaunchLog ("window keeper pid {0}: the game window stays {1}x{2}" -f $winKeeper.Id, $winRect[2], $winRect[3]) 'DarkGray'
    } catch { Write-LaunchLog "window keeper did not start: $_ - the game stays full screen" 'Yellow' }
}

# ---- the FFB web panel (-Panel; tools\ffb\ffb-panel.py) ----------------------------
$panelProc = $null
if ($Panel) {
    $panelPy = Join-Path $ffbDir 'ffb-panel.py'
    if (-not $ffbProc) { Write-LaunchLog "FFB panel: not started - no interposer runs (no wheel, -NoFfb, or it did not start), so the page would have nothing to show" 'DarkGray' }
    elseif (-not (Test-Path $panelPy)) { Write-LaunchLog "FFB panel: ffb-panel.py is not in $ffbDir (older _ffb) - not started" 'Yellow' }
    else {
        $pyExe = $null; $pyArgs = @()
        $pyCmd = Get-Command py.exe -ErrorAction SilentlyContinue
        if ($pyCmd) { $pyExe = $pyCmd.Source; $pyArgs = @('-3') } else { $pyCmd = Get-Command python.exe -ErrorAction SilentlyContinue; if ($pyCmd) { $pyExe = $pyCmd.Source } }
        if (-not $pyExe) { Write-LaunchLog "FFB panel: no Python 3 (py / python) on the PATH - not started; the interposer's console panel still works" 'Yellow' }
        else {
            try {
                $panelProc = Start-Process -FilePath $pyExe -ArgumentList ($pyArgs + @("`"$panelPy`"")) -WindowStyle Minimized -PassThru -ErrorAction Stop
                Write-LaunchLog ("FFB panel: http://127.0.0.1:17691/ (pid {0}; it opens the browser)" -f $panelProc.Id) 'Cyan'
            } catch { Write-LaunchLog "FFB panel did not start: $_" 'Yellow' }
        }
    }
}

# Soundtrack, AFTER the game: it finds the game by process and reads the music
# folder next to the exe. It exits on its own when the game exits.
$music = $null
if (-not $NoMusic) {
    $musicScript = Join-Path $PSScriptRoot 'tools\i76-music.ps1'
    if (-not (Test-Path $musicScript)) { $musicScript = Join-Path $GameDir '_ffb\i76-music.ps1' }
    if ((Test-Path $musicScript) -and (Test-Path (Join-Path $GameDir 'music'))) {
        $args = @('-NoProfile','-ExecutionPolicy','Bypass','-File',"`"$musicScript`"",
                  '-Volume',"$MusicVolume")
        if ($MusicMissionOnly) { $args += '-MissionOnly' }
        $music = Start-Process -FilePath 'powershell.exe' -ArgumentList $args -WindowStyle Hidden -PassThru
    }
}

# The helpers (opentrack, the interposer, the panel) can come up in front of the game and leave it inactive from its first tick
# (gate finding 2026-10-25: with helpers on, the T05 opening never finished; helpers off or this step: it runs). They are started
# minimised / hidden above; once they are up the game window is brought back to the front, ONCE. Nothing a helper does changes.
if ($proc) {
    try {
        Add-Type -Namespace I76F -Name W -ErrorAction SilentlyContinue -MemberDefinition @'
[DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
[DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint flags, System.UIntPtr extra);
'@
        $fgEnd = (Get-Date).AddSeconds(40)
        while ((Get-Date) -lt $fgEnd -and -not $proc.HasExited) { $proc.Refresh(); if ($proc.MainWindowHandle -ne [IntPtr]::Zero) { break }; Start-Sleep -Milliseconds 500 }
        if (-not $proc.HasExited -and $proc.MainWindowHandle -ne [IntPtr]::Zero) {
            Start-Sleep -Seconds 4
            [I76F.W]::keybd_event(0x12, 0, 0, [UIntPtr]::Zero); [I76F.W]::keybd_event(0x12, 0, 2, [UIntPtr]::Zero)   # a tap of Alt lets SetForegroundWindow through
            $fgOk = [I76F.W]::SetForegroundWindow($proc.MainWindowHandle)
            Write-LaunchLog ("game window brought to the front after the helpers started ({0})" -f $fgOk) 'DarkGray'
        }
    } catch { }
}

if ($proc) {
    $proc.WaitForExit()
    Write-LaunchLog ("game exited (code {0})" -f $proc.ExitCode) 'DarkGray'
}

if ($wheel    -and -not $wheel.HasExited)    { Stop-Process -Id $wheel.Id    -Force }
if ($ahk      -and -not $ahk.HasExited)      { Stop-Process -Id $ahk.Id      -Force }
if ($stick    -and -not $stick.HasExited)    { Stop-Process -Id $stick.Id    -Force }
if ($cursor   -and -not $cursor.HasExited)   { Stop-Process -Id $cursor.Id   -Force }
if ($ls       -and -not $ls.HasExited)       { Stop-Process -Id $ls.Id       -Force }
if ($track    -and -not $track.HasExited)    { Stop-Process -Id $track.Id    -Force }
if ($otHelper -and -not $otHelper.HasExited) { Stop-Process -Id $otHelper.Id -Force }
# The interposer releases the wheel in its own finally block, but Stop-Process
# -Force skips that - so ask it to stop, and only kill it if it will not.
# The music helper exits on its own when the game does, but kill it if it lingers -
# an MCI device left open holds the file and can wedge later playback.
if ($music -and -not $music.HasExited) { Stop-Process -Id $music.Id -Force }
if ($winKeeper -and -not $winKeeper.HasExited) { Stop-Process -Id $winKeeper.Id -Force }
if ($panelProc -and -not $panelProc.HasExited) { Stop-Process -Id $panelProc.Id -Force }
if ($winConfBak -and (Test-Path $winConfBak)) {
    Copy-Item $winConfBak (Join-Path $GameDir 'dgVoodoo.conf') -Force; Remove-Item $winConfBak -Force
    Write-LaunchLog 'windowed: dgVoodoo.conf put back' 'DarkGray'
}
if ($ffbProc -and -not $ffbProc.HasExited) {
    Stop-Process -Id $ffbProc.Id -Force
    # Belt and braces: if the force was latched when we killed it, the wheel would
    # keep pulling. Re-open the device briefly and zero it.
    try {
        . (Join-Path $ffbDir 'FfbCore.ps1')
        $d = Ffb-Open
        $null = Ffb-Constant $d 0
        Ffb-Close $d
    } catch { }
}
# Only close opentrack if WE started it - leave a session the user had open.
if ($ot       -and -not $ot.HasExited)       { Stop-Process -Id $ot.Id       -Force }

# Release any key the AHK layer might have been HOLDING when we killed it.
# Stop-Process -Force skips AHK's OnExit handler (RSGExit), which is what would
# normally send the matching key-ups - so a key held at that moment stays LATCHED
# DOWN system-wide, surviving into the next launch. Field-diagnosed 2026-08-01:
# a stuck glance-left persisted across a relaunch and looked like a game hang.
# These are the keys i76-remap.ahk can hold (RSGExit's list + the @wheel holds),
# PLUS the ones i76-ch-fighterstick.ahk can hold. The stick matters more here, not
# less: its handbrake is `Space` held for as long as the stick is pulled back, and
# its cone hat holds an arrow key for as long as you are looking that way - so
# quitting mid-corner while glancing left is an ordinary thing to do, and it is
# exactly the moment a force-kill latches a key. Its OnExit/ReleaseAll cannot help
# here, because Stop-Process -Force never lets it run.
# F (0x46) = weapon_link on the pinky and K (0x4B) = radar camera on the serrated
# hat were BOTH missing from this list until 2026-08-08 - the stick can hold them
# and nothing was releasing them.
try {
    Add-Type -Name KbRelease -Namespace I76 -MemberDefinition @'
[DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint flags, System.UIntPtr extra);
'@ -ErrorAction SilentlyContinue
    $KEYUP = 0x2; $EXT = 0x1
    # arrows (extended keys), digits 1-8, Enter, and the letters the layer emits
    $vks = @(0x25,0x26,0x27,0x28) + (0x31..0x38) + @(0x0D) +
           @(0x48,0x49,0x4E,0x4D,0x59,0x55,0x56,0x58,0x42,0x47,0x45,0x52,0x51,0x54,0x09,0x20) +
           @(0x46,0x4B)   # F weapon_link, K radar camera - Fighterstick only
    foreach ($vk in $vks) {
        $flags = $KEYUP
        if ($vk -ge 0x25 -and $vk -le 0x28) { $flags = $KEYUP -bor $EXT }
        [I76.KbRelease]::keybd_event([byte]$vk, 0, $flags, [System.UIntPtr]::Zero)
    }
} catch { }
