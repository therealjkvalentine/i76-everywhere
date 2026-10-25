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
    # Skip each mission's own briefing movie (intNNf01.smk) and its closing movie, through the menus, the campaign or
    # -Mission alike: the game goes straight to the mission (proxy I76_SKIP_CUTSCENES=1; the mission then plays exactly as
    # one that has no movie). Movies a mission plays in the middle stay on. Needs the proxy deployed.
    [switch]$SkipCutscenes,
    # Turn the game's own force feedback off without unplugging the wheel (proxy I76_FFB_OFF=1: I7_SFRCE.DLL is never loaded,
    # as on a machine without it; the wheel still steers). Implies -NoFfb (no custom interposer either).
    [switch]$FfbOff,
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
    # changes; a hidden keeper puts it back). dgVoodoo.conf gets [Glide] Resolution = I76_RENDER_SCALE (default 2) x the window (2 = a 2x2 supersample, capped
    # 8192 per side) for this launch only (the previous conf comes back when the game exits), and the proxy's camera / HUD /
    # Esc-menu aspect keys (I76_ASPECT, I76_U32X_MENU_ASPECT) take the window's shape. The menu pointer map follows the live
    # client rect by itself (proxy cursormap.c). PLAY.bat --windowed [WxH] passes it.
    [string]$Windowed = '',
    # The FFB / LFE tuning page (tools\ffb\ffb-panel.py, http://127.0.0.1:17691/): started with the interposer and opened in
    # the browser. Needs Python 3. PLAY.bat --panel passes it. Without a wheel (no interposer) it says so and starts nothing.
    [switch]$Panel,
    # Render scale for this launch (2026-10-25): replaces the I76_RENDER_SCALE preset / local.psd1 key (1, 1.5 or 2; see
    # "render scale + antialiasing" below). The patch kit's PLAY.bat --no-supersample passes -RenderScale 1.
    [string]$RenderScale = '',
    # Apply the render scale / antialiasing step (dgVoodoo.wide.conf -> dgVoodoo.conf), print it and exit 0 without starting
    # anything (exit 5 if the step failed). For tests and for checking a local.psd1.
    [switch]$RenderOnly,
    # Skip <GameDir>\i76-settings.txt, the player's settings file (see "player settings file" below).
    [switch]$NoSettings,
    # Write <GameDir>\i76-settings.txt (and SETTINGS.bat) for this preset and this PC if it is missing, then exit 0. Never overwrites
    # an existing file. SETTINGS.bat runs it when the file is not there yet; a setup can run it too.
    [switch]$WriteSettings
)
$ErrorActionPreference = 'SilentlyContinue'

# ---- feedback (2026-10-25, owner: "ask for feedback via GitHub issues"): every log the kit writes starts with this line.
$issueUrl = 'https://github.com/therealjkvalentine/i76-everywhere/issues/new/choose'
$issueBanner = "If something went wrong, attach this file to a GitHub issue: $issueUrl"
function Set-LogBanner([string]$path, [switch]$Create) {
    # Puts $issueBanner as the first line of a log another program appends to (the proxy's mciproxy.log, the interposer's,
    # opentrack-autostart's, the kit setup's). Byte level, so the writer's encoding is kept. Never fatal.
    try {
        if (-not (Test-Path -LiteralPath $path)) {
            if ($Create) { [IO.File]::WriteAllText($path, "$issueBanner`r`n", [Text.Encoding]::ASCII) }
            return
        }
        $b = [IO.File]::ReadAllBytes($path)
        $head = [Text.Encoding]::ASCII.GetBytes($issueBanner)
        if ($b.Length -ge $head.Length -and [Text.Encoding]::ASCII.GetString($b, 0, $head.Length) -eq $issueBanner) { return }
        $nb = New-Object byte[] ($head.Length + 2 + $b.Length)
        [Array]::Copy($head, $nb, $head.Length); $nb[$head.Length] = 13; $nb[$head.Length + 1] = 10
        [Array]::Copy($b, 0, $nb, $head.Length + 2, $b.Length)
        [IO.File]::WriteAllBytes($path, $nb)
    } catch { }
}

# ---- launcher log (2026-10-24): the .bat files run this script hidden, so what was switched on is also written
# to <game>\play-i76.log (the last 400 lines are kept, after the feedback line). Lines are "<time> <text>".
$launchClock = [Diagnostics.Stopwatch]::StartNew()
$launchLog = Join-Path $GameDir 'play-i76.log'
function Write-LaunchLog([string]$text, [string]$color = 'Cyan') {
    Write-Host $text -ForegroundColor $color
    if ($DryRun -or $WriteSettings) { return }
    try {
        $old = @(); if (Test-Path $launchLog) { $old = @(Get-Content $launchLog -Tail 399 | Where-Object { $_ -ne $issueBanner }) }
        $line = "{0} +{1:0.00}s {2}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $launchClock.Elapsed.TotalSeconds, $text
        Set-Content -Path $launchLog -Value (@($issueBanner) + $old + $line) -Encoding UTF8
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
$envSrc = @{}   # key -> where a value that is not the preset's came from (i76-settings.txt line N), for the log lines

# ---- player settings file: <GameDir>\i76-settings.txt (2026-10-25, owner: "Is psd1 easy for laypeople, or is there a more intuitive
# format that opens in a text editor?"; docs/records/SETTINGS-FILE-2026-10-25.md). Plain "name = value" lines, # comments, grouped;
# every line says what it does, the allowed values and the value at the time the file was written. "default" (or an empty value)
# = keep what the launcher chooses. SETTINGS.bat opens it in Notepad. Written on the first launch when missing (and by -WriteSettings).
# PRECEDENCE, lowest first: the launcher's preset < i76-settings.txt < presets\local.psd1 (power users) < command-line options
# (-RenderScale, -NoFfb, -Windowed, ... and the .bat flags that pass them). A line that cannot be read is reported by its line number
# (console + play-i76.log) and skipped; the launch goes on. Game switches (I76_*) are not applied to preset stock (PLAY-VANILLA /
# PLAY-stock stay the stock game, as with local.psd1); the launcher's own options (force feedback, head look, mouse wheel) are.
# -NoSettings skips the file.
$settingsFile = Join-Path $GameDir 'i76-settings.txt'
$onOff = @{ 'on' = 'on'; 'yes' = 'on'; 'true' = 'on'; '1' = 'on'; 'off' = 'off'; 'no' = 'off'; 'false' = 'off'; '0' = 'off' }
# Kind: choice (Allowed, optional Map of synonyms -> value), number (Min, Max), onoff, key (a key name for i76wheel), windowed, note.
# Target: env:<I76_KEY> | param:<name> (handled below) | ffb:<tune key> | none.
$settingsSchema = @(
  @{ Group = 'Graphics'; Name = 'render scale'; Target = 'env:I76_RENDER_SCALE'; Kind = 'choice'; Allowed = @('1', '1.5', '2'); Stock = '2'; Unset = 'the launcher''s default'
     Help = @('How big the 3D picture is drawn before it is fitted to your monitor: 2 = twice your monitor''s size each way (sharpest,',
              'heaviest on the graphics card), 1 = your monitor''s own size (lightest - try it if the game is not smooth). Windows only.') }
  @{ Group = 'Graphics'; Name = 'antialiasing'; Target = 'env:I76_AA'; Kind = 'choice'; Allowed = @('off', '2', '4', '8'); Stock = '4'; Unset = 'the launcher''s default'
     Map = @{ '0' = 'off'; 'off' = 'off'; 'none' = 'off'; '2x' = '2'; '4x' = '4'; '8x' = '8' }
     Help = @('Smooths jagged edges (MSAA). off is the lightest, 8 the smoothest and heaviest. Windows only.') }
  @{ Group = 'Graphics'; Name = 'field of view'; Target = 'env:I76_FOV'; Kind = 'number'; Min = 60; Max = 120; Unit = 'degrees'; Stock = '90'
     Help = @('How wide you see, in degrees, measured on a 4:3 screen (the 1997 value is 90). A wide monitor shows more to the sides',
              'on top of this by itself (90 becomes about 106 on 16:9 and 122 on 21:9); nothing is stretched.') }
  @{ Group = 'Graphics'; Name = 'hood view field of view'; Target = 'env:I76_FOV_HOOD'; Kind = 'number'; Min = 80; Max = 150; Unit = 'degrees'; Stock = '120'
     Help = @('The same for the hood view (F6). The 1997 value is 120.') }
  @{ Group = 'Graphics'; Name = 'draw distance'; Target = 'env:I76_FAR_CLIP'; Kind = 'number'; Min = 100; Max = 2500; Unit = 'metres'; Stock = '600'
     Help = @('How far the terrain, cars and buildings are drawn. 1997: 600. Farther costs frame rate, mostly in the binoculars.') }
  @{ Group = 'Graphics'; Name = 'road distance'; Target = 'env:I76_ROAD_DIST'; Kind = 'number'; Min = 450; Max = 3000; Unit = 'metres'; Stock = '450'
     Help = @('How far roads are drawn. 1997: 450.') }
  @{ Group = 'Graphics'; Name = 'terrain detail'; Target = 'env:I76_TERRAIN_LOD'; Kind = 'number'; Min = 1; Max = 256; Integer = $true; Stock = '1'
     Help = @('How far out the ground keeps its full shape (1 = 1997). Above 1 needs a draw distance (the launcher refuses otherwise).') }
  @{ Group = 'Graphics'; Name = 'terrain texture distance'; Target = 'env:I76_TERRAIN_TEX'; Kind = 'number'; Min = 1; Max = 16; Integer = $true; Stock = '1'
     Help = @('How many times farther the sharp ground textures reach (1 = 1997).') }
  @{ Group = 'Graphics'; Name = 'object detail distance'; Target = 'env:I76_OBJECT_LOD'; Kind = 'number'; Min = 1; Max = 16; Integer = $true; Stock = '1'
     Help = @('How many times farther cars and buildings keep their detailed models (1 = 1997).') }
  @{ Group = 'Graphics'; Name = 'road texture distance'; Target = 'env:I76_ROAD_TEX'; Kind = 'number'; Min = 1; Max = 16; Integer = $true; Stock = '1'
     Help = @('How many times farther the sharp road texture reaches (1 = 1997).') }
  @{ Group = 'Graphics'; Name = 'shadow distance'; Target = 'env:I76_SHADOW_DIST'; Kind = 'number'; Min = 1; Max = 16; Integer = $true; Stock = '1'
     Help = @('How many times farther shadows are drawn (1 = 1997, 50 m).') }
  @{ Group = 'Graphics'; Name = 'bush distance'; Target = 'env:I76_CLUTTER_DIST'; Kind = 'number'; Min = 120; Max = 2500; Unit = 'metres'; Stock = '120'
     Help = @('How far the little bushes are drawn. 1997: 120.') }
  @{ Group = 'Graphics'; Name = 'bush density'; Target = 'env:I76_CLUTTER_DENSITY'; Kind = 'number'; Min = 0.1; Max = 1; Stock = '1'
     Help = @('1 = every bush, 0.5 = half of them.') }
  @{ Group = 'Graphics'; Name = 'mirror distance'; Target = 'env:I76_MIRROR_FAR'; Kind = 'number'; Min = 100; Max = 2500; Unit = 'metres'; Stock = '100'
     Help = @('How far the rear-view mirror sees. 1997: 100.') }
  @{ Group = 'Graphics'; Name = 'refresh rate'; Target = 'env:I76_GLIDE_REFRESH'; Kind = 'choice'; Allowed = @('60', '70', '72', '75', '80', '85', '90', '100', '120'); Stock = '60'
     Help = @('The refresh rate the 3D asks for, in Hz: the frame-rate ceiling. 120 = up to 120 fps.') }
  @{ Group = 'Graphics'; Name = 'windowed'; Target = 'param:Windowed'; Kind = 'windowed'; Stock = 'off'
     Help = @('off = full screen. auto = a window at the top left, narrower than the screen. Or a size such as 1920x1080.') }

  @{ Group = 'Controls'; Name = 'head look'; Target = 'param:HeadLook'; Kind = 'choice'; Allowed = @('auto', 'start', 'off'); Stock = 'auto'
     Help = @('Head tracking with opentrack. auto = used when opentrack is already running when you start the game; start = the',
              'launcher starts opentrack too; off = never.') }
  @{ Group = 'Controls'; Name = 'head look mode'; Target = 'param:HeadLookMode'; Kind = 'choice'; Allowed = @('analog', 'digital', 'off'); Stock = 'analog'
     Help = @('How head look starts (Ctrl+Alt+H changes it in the game).') }
  @{ Group = 'Controls'; Name = 'wheel force feedback'; Target = 'param:WheelFfb'; Kind = 'choice'; Allowed = @('auto', 'on', 'off'); Stock = 'auto'
     Help = @('Our force feedback for a steering wheel. auto = on when a force-feedback wheel is plugged in; on = always try;',
              'off = the game''s own 1997 effects.') }
  @{ Group = 'Controls'; Name = 'game force feedback'; Target = 'param:GameFfb'; Kind = 'onoff'; Stock = 'on'
     Help = @('off = no force feedback at all (the wheel still steers).') }
  @{ Group = 'Controls'; Name = 'pavement scale'; Target = 'ffb:PavementScale'; Kind = 'number'; Min = 0; Max = 1; Stock = '0.5'
     Help = @('With our wheel force feedback: how busy the road feels on pavement compared with off-road (1 = the same, 0.5 = half).',
              'The FFB panel''s slider changes it for one session; this line sets it again at the next start.') }
  @{ Group = 'Controls'; Name = 'mouse wheel up'; Target = 'param:WheelUp'; Kind = 'key'; Stock = 'Tab'
     Help = @('The key the mouse wheel types when rolled up (Tab = next weapon on this kit''s keys). A key name as in input.map.') }
  @{ Group = 'Controls'; Name = 'mouse wheel down'; Target = 'param:WheelDown'; Kind = 'key'; Stock = '5'
     Help = @('The key for the wheel rolled down (5 = fire hardpoint 5, usually the dropper).') }

  @{ Group = 'Sound'; Name = 'effects volume'; Target = 'env:I76_SFX_GAIN'; Kind = 'number'; Min = -40; Max = 20; Unit = 'dB'; Stock = '0'; Unset = 'as the game has it'
     Help = @('Louder or quieter than the game''s own mix, in dB: 0 = as the game has it, -6 = about half as loud, +6 = twice.') }
  @{ Group = 'Sound'; Name = 'voice volume'; Target = 'env:I76_VOICE_GAIN'; Kind = 'number'; Min = -40; Max = 20; Unit = 'dB'; Stock = '0'; Unset = 'as the game has it'
     Help = @('The same for the voices.') }
  @{ Group = 'Sound'; Name = 'music volume'; Target = 'env:I76_MUSIC_GAIN'; Kind = 'number'; Min = -40; Max = 20; Unit = 'dB'; Stock = '0'; Unset = 'as the game has it'
     Help = @('The same for the music (the game''s AUDIO slider still works on top).') }

  @{ Group = 'Multiplayer'; Name = 'player name'; Target = 'none'; Kind = 'note'
     Help = @('Your driver name for network games is typed in the game''s own menus; it is not stored in this file.') }
  @{ Group = 'Multiplayer'; Name = 'co-op scaling'; Target = 'env:I76_COOP_SCALE'; Kind = 'onoff'; Stock = 'on'; Unset = 'the default with computer cars in network games'
     Help = @('Co-op missions with friends: each enemy that attacks brings one extra copy per friend who joined. off = the 1997 mission.') }
  @{ Group = 'Multiplayer'; Name = 'co-op extra enemies'; Target = 'env:I76_COOP_SCALE_MAX'; Kind = 'number'; Min = 0; Max = 3; Integer = $true; Stock = '3'; Unset = 'the default'
     Help = @('The most extra copies of one enemy co-op scaling brings in (0 to 3).') }
  @{ Group = 'Multiplayer'; Name = 'co-op damage'; Target = 'env:I76_COOP_DAMAGE'; Kind = 'number'; Min = 0.1; Max = 4; Stock = '1'
     Help = @('In network games, how hard your weapons hit (1 = as 1997, 0.5 = half).') }
  @{ Group = 'Multiplayer'; Name = 'computer car skill'; Target = 'param:AiSkill'; Kind = 'choice'; Allowed = @('1', '2', '3', '4', '5'); Stock = '3'
     Help = @('Computer cars in the melee arenas: 1 = the best drivers and shots, 5 = the weakest. Only the host''s value counts.') }
  @{ Group = 'Multiplayer'; Name = 'legacy multiplayer menu'; Target = 'param:LegacyMultiplayer'; Kind = 'onoff'; Stock = 'off'
     Help = @('on = the 1997 MODEM / IPX / INTERNET / NULLMODEM choice in HOST / JOIN (and no computer cars), for playing with a stock game.') }

  @{ Group = 'Advanced'; Name = 'skip mission movies'; Target = 'env:I76_SKIP_CUTSCENES'; Kind = 'onoff'; Stock = 'off'
     Help = @('on = no briefing / closing movie around each mission (movies in the middle of a mission stay).') }
  @{ Group = 'Advanced'; Name = 'simulation tick'; Target = 'param:TickMs'; Kind = 'number'; Min = 16.7; Max = 66.7; Unit = 'ms'; Stock = '41.667'
     Help = @('How often the game world is simulated, in milliseconds (41.667 = 24 times a second, the 1997 car step). Only for',
              'launchers with a simulation tick. In a network game every player should use the same value.') }
)
function ConvertTo-SettingKey([string]$s) { ($s.ToLowerInvariant() -replace '[^a-z0-9]', '') }
$settingsByKey = @{}
foreach ($e in $settingsSchema) {
    $settingsByKey[(ConvertTo-SettingKey $e.Name)] = $e
    if ($e.Target -like 'env:*') { $settingsByKey[(ConvertTo-SettingKey $e.Target.Substring(4))] = $e }   # I76_RENDER_SCALE = 1 also works
}
function Test-SettingValue($e, [string]$v) {
    # @($ok, $normalised, $why)
    $lv = $v.Trim().ToLowerInvariant()
    switch ($e.Kind) {
        'choice' {
            if ($e.Map -and $e.Map.ContainsKey($lv)) { $lv = $e.Map[$lv] }
            if ($e.Allowed -contains $lv) { return @($true, $lv, '') }
            return @($false, $null, ('not one of ' + ($e.Allowed -join ', ')))
        }
        'onoff' { if ($onOff.ContainsKey($lv)) { return @($true, $onOff[$lv], '') }; return @($false, $null, 'not on or off') }
        'number' {
            $tv = 0.0
            if ($lv -notmatch '^[+-]?\d+(\.\d+)?$' -or -not [double]::TryParse($lv, [Globalization.NumberStyles]::Float, [Globalization.CultureInfo]::InvariantCulture, [ref]$tv)) {
                return @($false, $null, 'not a number (use a dot for decimals, e.g. 1.5)')
            }
            if ($e.Integer -and $tv -ne [Math]::Floor($tv)) { return @($false, $null, 'not a whole number') }
            if ($tv -lt $e.Min -or $tv -gt $e.Max) { return @($false, $null, ("outside {0} to {1}" -f $e.Min, $e.Max)) }
            return @($true, $tv.ToString('0.###', [Globalization.CultureInfo]::InvariantCulture), '')
        }
        'key' { if ($v.Trim() -match '^[A-Za-z0-9]{1,12}$') { return @($true, $v.Trim(), '') }; return @($false, $null, 'not a key name (letters / digits, e.g. Tab, Enter, 5)') }
        'windowed' {
            if ($lv -in 'off', 'no', 'auto') { return @($true, $(if ($lv -eq 'no') { 'off' } else { $lv }), '') }
            if ($lv -match '^\s*\d{3,5}\s*x\s*\d{3,5}\s*$') { return @($true, ($lv -replace '\s', ''), '') }
            return @($false, $null, 'not off, auto or a size like 1920x1080')
        }
    }
    return @($false, $null, 'this line is a note, not a setting')
}
function Read-I76Settings([string]$path) {
    # -> @{ Values = list of @{ Entry; Raw; Value; Line } (or @{ Env; Value; Line } for a plain I76_* line); Errors = list of text }
    $res = @{ Values = New-Object System.Collections.ArrayList; Errors = New-Object System.Collections.ArrayList }
    try { $lines = [IO.File]::ReadAllLines($path) } catch { [void]$res.Errors.Add("could not be read: $($_.Exception.Message)"); return $res }
    $seen = @{}
    for ($i = 0; $i -lt $lines.Count; $i++) {
        $n = $i + 1; $t = ($lines[$i] -replace '^﻿', '').Trim()
        if (-not $t -or $t.StartsWith('#') -or $t.StartsWith(';') -or ($t.StartsWith('[') -and $t.EndsWith(']'))) { continue }
        $eq = $t.IndexOf('=')
        if ($eq -lt 1) { [void]$res.Errors.Add(("line {0}: '{1}' - not a 'name = value' line; skipped" -f $n, $t)); continue }
        $name = $t.Substring(0, $eq).Trim(); $val = $t.Substring($eq + 1)
        $hc = $val.IndexOf(' #'); if ($hc -ge 0) { $val = $val.Substring(0, $hc) }   # a note after the value
        $val = $val.Trim().Trim('"').Trim("'").Trim()
        $nk = ConvertTo-SettingKey $name
        $e = $settingsByKey[$nk]
        if (-not $e) {
            if ($name -match '^I76_[A-Z0-9_]+$') {   # Advanced: any engine switch by its own name, passed to the game as written
                if ($val -ieq 'default') { continue }
                [void]$res.Values.Add(@{ Env = $name; Value = $val; Line = $n }); continue
            }
            [void]$res.Errors.Add(("line {0}: '{1}' - no setting called '{2}'; skipped" -f $n, $t, $name)); continue
        }
        if ($e.Kind -eq 'note') { continue }
        if ($val -eq '' -or $val -ieq 'default') { continue }
        $chk = Test-SettingValue $e $val
        if (-not $chk[0]) { [void]$res.Errors.Add(("line {0}: '{1}' - {2}; skipped (the launcher's value is used)" -f $n, $t, $chk[2])); continue }
        if ($seen.ContainsKey($e.Name)) { [void]$res.Errors.Add(("line {0}: '{1}' - '{2}' is already set on line {3}; the later line wins" -f $n, $t, $e.Name, $seen[$e.Name])) }
        $seen[$e.Name] = $n
        [void]$res.Values.Add(@{ Entry = $e; Raw = $val; Value = $chk[1]; Line = $n })
    }
    return $res
}
$settingsLog = @()
$settingsParams = @{}   # param name -> @(value, line) for the launcher's own options, applied below unless given on the command line
$ffbTuneWant = $null
if (-not $NoSettings -and -not $WriteSettings -and (Test-Path -LiteralPath $settingsFile)) {
    $sr = Read-I76Settings $settingsFile
    $nSet = 0
    foreach ($v in $sr.Values) {
        $src = "i76-settings.txt line $($v.Line)"
        if ($v.Env) {
            if ($Preset -eq 'stock') { $settingsLog += ("settings: {0} {1} = {2} NOT applied (preset stock stays stock)" -f $src, $v.Env, $v.Value); continue }
            $was = if ($gameEnv.Contains($v.Env)) { $gameEnv[$v.Env] } else { '(unset)' }
            if ($v.Value -eq '') { if ($gameEnv.Contains($v.Env)) { $gameEnv.Remove($v.Env) } } else { $gameEnv[$v.Env] = $v.Value }
            $envSrc[$v.Env] = $src; $nSet++
            $settingsLog += ("settings: {0}: {1}={2} (preset {3})" -f $src, $v.Env, $(if ($v.Value -eq '') { '(unset)' } else { $v.Value }), $was)
            continue
        }
        $e = $v.Entry; $tgt = $e.Target -split ':', 2
        switch ($tgt[0]) {
            'env' {
                $k = $tgt[1]
                if ($Preset -eq 'stock') { $settingsLog += ("settings: {0}: {1} = {2} NOT applied (preset stock stays stock)" -f $src, $e.Name, $v.Raw); break }
                $ev = $v.Value
                if ($e.Kind -eq 'onoff') { $ev = if ($v.Value -eq 'on') { '1' } else { '0' } }
                if ($k -eq 'I76_AA' -and $ev -eq 'off') { $ev = '0' }
                if ($k -eq 'I76_SKIP_CUTSCENES' -and $ev -eq '0') { $ev = '' }
                $was = if ($gameEnv.Contains($k)) { $gameEnv[$k] } else { '(unset)' }
                if ($ev -eq '') { if ($gameEnv.Contains($k)) { $gameEnv.Remove($k) } } else { $gameEnv[$k] = $ev }
                $envSrc[$k] = $src; $nSet++
                $settingsLog += ("settings: {0}: {1} = {2} -> {3}={4} (preset {5})" -f $src, $e.Name, $v.Raw, $k, $(if ($ev -eq '') { '(unset)' } else { $ev }), $was)
            }
            'param' { $settingsParams[$tgt[1]] = @($v.Value, $src, $e.Name, $v.Raw); $nSet++ }
            'ffb' { $ffbTuneWant = @($tgt[1], [double]::Parse($v.Value, [Globalization.CultureInfo]::InvariantCulture), $src); $nSet++ }
        }
    }
    foreach ($er in $sr.Errors) { $settingsLog += "settings: i76-settings.txt $er" }
    $settingsLog += ("settings: i76-settings.txt read - {0} value(s) changed from the launcher's, {1} line(s) not understood{2}" -f $nSet, $sr.Errors.Count, $(if ($sr.Errors.Count) { ' (listed above; the game starts anyway)' } else { '' }))
} elseif ($NoSettings -and (Test-Path -LiteralPath $settingsFile)) {
    $settingsLog += 'settings: i76-settings.txt NOT read (-NoSettings)'
}
# the launcher's own options from the file; a switch / value given on the command line wins
foreach ($pn in @($settingsParams.Keys)) {
    $pv = $settingsParams[$pn][0]; $src = $settingsParams[$pn][1]; $label = "{0}: {1} = {2}" -f $src, $settingsParams[$pn][2], $settingsParams[$pn][3]
    $cli = switch ($pn) {
        'HeadLook' { $PSBoundParameters.ContainsKey('HeadTrack') -or $PSBoundParameters.ContainsKey('NoHeadTrack') }
        'WheelFfb' { $PSBoundParameters.ContainsKey('Ffb') -or $PSBoundParameters.ContainsKey('NoFfb') }
        'GameFfb'  { $PSBoundParameters.ContainsKey('FfbOff') }
        default    { $PSBoundParameters.ContainsKey($pn) }
    }
    if ($cli) { $settingsLog += "settings: $label - the command line says otherwise, it wins"; continue }
    if ($pn -eq 'TickMs' -and -not $gameEnv.Contains('I76_SIM_TICK_MS')) { $settingsLog += "settings: $label - NOT applied: this launcher's preset has no simulation tick"; continue }
    switch ($pn) {
        'HeadLook' { if ($pv -eq 'start') { $HeadTrack = [switch]$true } elseif ($pv -eq 'off') { $NoHeadTrack = [switch]$true } }
        'WheelFfb' { if ($pv -eq 'on') { $Ffb = [switch]$true } elseif ($pv -eq 'off') { $NoFfb = [switch]$true } }
        'GameFfb'  { if ($pv -eq 'off') { $FfbOff = [switch]$true } }
        'HeadLookMode' { $HeadLookMode = $pv.ToUpperInvariant() }
        'WheelUp' { $WheelUp = $pv }
        'WheelDown' { $WheelDown = $pv }
        'AiSkill' { $AiSkill = [int]$pv }
        'LegacyMultiplayer' { if ($pv -eq 'on') { $LegacyMultiplayer = [switch]$true } }
        'Windowed' { if ($pv -ne 'off') { $Windowed = $pv } }
        'TickMs' { $TickMs = $pv }
    }
    $settingsLog += "settings: $label"
}

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
            $wasFrom = if ($envSrc.ContainsKey($k)) { "$($envSrc[$k]) said" } else { 'preset' }
            if ($nv -eq '') { if ($gameEnv.Contains($k)) { $gameEnv.Remove($k) }; $nv = '(unset)' } else { $gameEnv[$k] = $nv }
            $envSrc[$k] = 'local'
            $localOverride += ("local override: {0}={1} ({2} {3})" -f $k, $nv, $wasFrom, $was)
        }
        if (-not $ld.Env.Count) { $localOverride += "local override $localFile sets nothing" }
    }
} elseif (Test-Path $localFile) {
    $localOverride += ("local override presets\local.psd1 NOT applied ({0})" -f $(if ($NoLocal) { '-NoLocal' } else { 'preset stock stays stock' }))
}

# ---- i76-settings.txt: written when missing (first launch, or -WriteSettings / SETTINGS.bat), with this PC's values in the notes
function Get-SettingNow($e) {
    # the value this launch would use without the file (preset + local.psd1), as the file spells it
    $tgt = $e.Target -split ':', 2
    switch ($tgt[0]) {
        'env' {
            $k = $tgt[1]
            if (-not $gameEnv.Contains($k)) { return @($e.Stock, $(if ($e.Unset) { $e.Unset } else { 'the 1997 value' })) }
            $v = "$($gameEnv[$k])"; $from = if ($envSrc[$k] -eq 'local') { 'presets\local.psd1' } else { "preset $presetName" }
            if ($e.Kind -eq 'onoff') { $v = if ($v -eq '0' -or $v -eq '') { 'off' } else { 'on' } }
            if ($k -eq 'I76_AA' -and $v -eq '0') { $v = 'off' }
            return @($v, $from)
        }
        'param' {
            switch ($tgt[1]) {
                'HeadLook' { return @($(if ($NoHeadTrack) { 'off' } elseif ($HeadTrack) { 'start' } else { 'auto' }), '') }
                'WheelFfb' { return @($(if ($NoFfb) { 'off' } elseif ($Ffb) { 'on' } else { 'auto' }), '') }
                'GameFfb' { return @($(if ($FfbOff) { 'off' } else { 'on' }), '') }
                'HeadLookMode' { return @($HeadLookMode.ToLowerInvariant(), '') }
                'WheelUp' { return @($WheelUp, '') }
                'WheelDown' { return @($WheelDown, '') }
                'AiSkill' { return @($(if ($AiSkill -ge 1) { "$AiSkill" } else { '3' }), '') }
                'LegacyMultiplayer' { return @($(if ($LegacyMultiplayer) { 'on' } else { 'off' }), '') }
                'Windowed' { return @($(if ($Windowed) { $Windowed } else { 'off' }), '') }
                'TickMs' { if ($gameEnv.Contains('I76_SIM_TICK_MS')) { return @("$($gameEnv['I76_SIM_TICK_MS'])", "preset $presetName") }; return @('-', 'this launcher has no simulation tick') }
            }
        }
        'ffb' {
            $tf = Get-FfbTuneFile
            try { if ($tf -and (Test-Path -LiteralPath $tf)) { $j = Get-Content -LiteralPath $tf -Raw | ConvertFrom-Json; if ($null -ne $j.($tgt[1])) { return @("$($j.($tgt[1]))", 'the FFB tune file') } } } catch { }
            return @($e.Stock, 'the FFB default')
        }
    }
    return @('', '')
}
function Get-FfbTuneFile {
    # the interposer reads ffb-tune-owner.json beside itself (tools\ffb in the repo, _ffb in a game folder)
    $d = Join-Path $PSScriptRoot 'tools\ffb'
    if (-not (Test-Path (Join-Path $d 'ffb-interposer.ps1'))) { $d = Join-Path $GameDir '_ffb' }
    if (-not (Test-Path -LiteralPath $d)) { return $null }
    return (Join-Path $d 'ffb-tune-owner.json')
}
function Write-I76Settings {
    $dW = 0; $dH = 0; $dFrom = 'the main monitor'
    $kd = Join-Path $GameDir '_i76e\display.txt'
    if ((Test-Path -LiteralPath $kd) -and ((Get-Content -LiteralPath $kd -TotalCount 1) -match '^\s*(\d+)x(\d+)')) { $dW = [int]$Matches[1]; $dH = [int]$Matches[2]; $dFrom = '_i76e\display.txt' }
    else { try { Add-Type -AssemblyName System.Windows.Forms; $b0 = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds; $dW = $b0.Width; $dH = $b0.Height } catch { } }
    $otHere = (Test-Path $OpenTrack) -or (Test-Path (Join-Path $GameDir '_tools\opentrack\opentrack.exe'))
    $L = New-Object System.Collections.Generic.List[string]
    $L.Add('# Interstate ''76 settings (i76-settings.txt)')
    $L.Add("# $issueBanner")
    $L.Add('#')
    $L.Add('# HOW TO CHANGE A SETTING: change the word after the = sign, save (Ctrl+S), close Notepad and start the game as usual.')
    $L.Add('#   default  = keep what the launcher chooses; the "now:" note above each line says what that is.')
    $L.Add('#   Lines that start with # are notes. A line the launcher cannot read is listed in play-i76.log with its line number')
    $L.Add('#   and skipped - the game still starts. Delete this file to get a fresh one (SETTINGS.bat or the next start writes it).')
    $L.Add(("# Written {0} for this PC: monitor {1}x{2} (from {3}), launcher preset {4}, opentrack {5}." -f (Get-Date -Format 'yyyy-MM-dd HH:mm'), $dW, $dH, $dFrom, $presetName, $(if ($otHere) { 'installed' } else { 'not installed' })))
    $L.Add('# Order: the launcher''s preset < this file < presets\local.psd1 (for power users, if you made one) < options typed after')
    $L.Add('# the launcher''s name (e.g. PLAY.bat --no-supersample). The stock launchers (PLAY-stock / PLAY-VANILLA) ignore the game')
    $L.Add('# settings here and use only the controls ones.')
    $grp = ''
    foreach ($e in $settingsSchema) {
        if ($e.Group -ne $grp) {
            $grp = $e.Group
            $L.Add(''); $L.Add(('# ==== {0} {1}' -f $grp, ('=' * [Math]::Max(4, 100 - $grp.Length)))); $L.Add("[$grp]")
        }
        $L.Add('')
        foreach ($h in $e.Help) { $L.Add("# $h") }
        if ($e.Kind -eq 'note') { continue }
        $allowed = switch ($e.Kind) {
            'choice' { $e.Allowed -join ', ' }
            'onoff' { 'on, off' }
            'number' { "{0} to {1}{2}" -f $e.Min, $e.Max, $(if ($e.Unit) { " $($e.Unit)" } else { '' }) }
            'key' { 'a key name, e.g. Tab, Enter, 5' }
            'windowed' { 'off, auto, or a size like 1920x1080' }
        }
        $now = Get-SettingNow $e
        $nowText = "now: $($now[0])"
        if ($e.Name -eq 'render scale' -and $dW -gt 0) {
            $rs = 2.0; [void][double]::TryParse("$($now[0])", [Globalization.NumberStyles]::Float, [Globalization.CultureInfo]::InvariantCulture, [ref]$rs)
            $nowText += " = the 3D drawn at {0}x{1}" -f ([int]([Math]::Floor($dW * $rs / 2) * 2)), ([int]([Math]::Floor($dH * $rs / 2) * 2))
        }
        if ($now[1]) { $nowText += " ($($now[1]))" }
        $L.Add("# allowed: $allowed, default.   $nowText")
        $L.Add("$($e.Name) = default")
    }
    $L.Add('')
    $L.Add('# Any engine switch from the project''s list (music-fix/README.md) can be added here by its own name, e.g.')
    $L.Add('#   I76_GLIDE_GAMMA = 1.3')
    $L.Add('# It goes to the game as written; I76_SOMETHING =  (nothing after the =) removes the launcher''s value.')
    [IO.File]::WriteAllLines($settingsFile, $L.ToArray(), (New-Object Text.UTF8Encoding $false))
}
function Write-SettingsBat {
    $bat = Join-Path $GameDir 'SETTINGS.bat'
    if (Test-Path -LiteralPath $bat) { return }
    $gameFull = (Resolve-Path -LiteralPath $GameDir).Path.TrimEnd('\')
    $me = if ($PSScriptRoot.TrimEnd('\') -ieq $gameFull) { '%~dp0PLAY-i76.ps1' } else { $PSCommandPath }
    $pr = if ($presetFile -and $Preset -notmatch '\.psd1$') { $Preset } elseif ($presetFile) { $presetFile } else { 'stock' }
    @('@echo off',
      'REM Opens i76-settings.txt (the game''s settings: graphics, controls, sound, multiplayer) in Notepad.',
      'REM Change a value, save, close Notepad, start the game. Written by PLAY-i76.ps1.',
      "if not exist `"%~dp0i76-settings.txt`" powershell -NoProfile -ExecutionPolicy Bypass -File `"$me`" -GameDir `"%~dp0.`" -Preset `"$pr`" -WriteSettings >nul",
      'start "" notepad.exe "%~dp0i76-settings.txt"') | Set-Content -LiteralPath $bat -Encoding ascii
}
$presetName = if ($presetData) { "$($presetData.Name)" } else { 'stock' }
if ($WriteSettings) {
    if (Test-Path -LiteralPath $settingsFile) { Write-Host "i76-settings.txt already exists in $GameDir - not overwritten." -ForegroundColor DarkGray }
    else {
        try { Write-I76Settings; Write-Host "wrote $settingsFile (launcher preset $presetName)" -ForegroundColor Cyan }
        catch { Write-Host "could not write $settingsFile : $_" -ForegroundColor Red; exit 6 }
    }
    try { Write-SettingsBat } catch { }
    exit 0
}
if (-not $DryRun -and -not $RenderOnly -and -not $NoSettings -and $Preset -ne 'stock' -and -not (Test-Path -LiteralPath $settingsFile)) {
    try { Write-I76Settings; Write-SettingsBat; $settingsLog += "settings: wrote i76-settings.txt (first start; every line says 'default', so nothing changes until you edit it; SETTINGS.bat opens it)" }
    catch { $settingsLog += "settings: could not write i76-settings.txt: $_" }
}
# pavement scale -> the interposer's tune file (only the one key; the FFB panel writes the same file)
if ($ffbTuneWant -and -not $DryRun -and -not $RenderOnly) {
    $tf = Get-FfbTuneFile
    if (-not $tf) { $settingsLog += "settings: $($ffbTuneWant[2]): pavement scale NOT applied - no _ffb folder (no wheel force feedback in this folder)" }
    else {
        try {
            $tune = [ordered]@{}
            if (Test-Path -LiteralPath $tf) { $j = Get-Content -LiteralPath $tf -Raw | ConvertFrom-Json; foreach ($p in $j.PSObject.Properties) { $tune[$p.Name] = $p.Value } }
            $old = $tune[$ffbTuneWant[0]]
            if ($null -eq $old -or [double]$old -ne $ffbTuneWant[1]) {
                $tune[$ffbTuneWant[0]] = $ffbTuneWant[1]
                Set-Content -LiteralPath $tf -Value ($tune | ConvertTo-Json) -Encoding ascii
                $settingsLog += ("settings: {0}: {1} {2} -> {3} in {4}" -f $ffbTuneWant[2], $ffbTuneWant[0], $(if ($null -eq $old) { '(default)' } else { $old }), $ffbTuneWant[1], (Split-Path $tf -Leaf))
            } else { $settingsLog += ("settings: {0}: {1} {2} (the tune file has it already)" -f $ffbTuneWant[2], $ffbTuneWant[0], $ffbTuneWant[1]) }
        } catch { $settingsLog += "settings: pavement scale NOT applied: $_" }
    }
} elseif ($ffbTuneWant) { $settingsLog += ("settings: {0}: {1} = {2} (DRY RUN: the FFB tune file is not written)" -f $ffbTuneWant[2], $ffbTuneWant[0], $ffbTuneWant[1]) }

Write-LaunchLog ("---- PLAY-i76.ps1 {0}" -f (($MyInvocation.BoundParameters.GetEnumerator() | ForEach-Object { if ($_.Value -is [switch]) { "-$($_.Key)" } else { "-$($_.Key) $($_.Value)" } }) -join ' ')) 'DarkGray'
foreach ($lo in $settingsLog) { Write-LaunchLog $lo $(if ($lo -match 'not understood|skipped|NOT|wins|could not') { 'Yellow' } else { 'Cyan' }) }
foreach ($lo in $localOverride) { Write-LaunchLog $lo 'Yellow' }
# the other logs a player may be asked for start with the feedback line too (proxy, interposer, opentrack helper, kit setup)
if (-not $DryRun) {
    Set-LogBanner (Join-Path $GameDir 'mciproxy.log') -Create:(Test-Path (Join-Path $GameDir 'strlkup_orig.dll'))
    foreach ($lg in '_ffb\ffb-interposer.log', '_ahk\opentrack-autostart.log', '_i76e\setup.log') { Set-LogBanner (Join-Path $GameDir $lg) }
}

# ---- render scale + antialiasing (I76_RENDER_SCALE / I76_AA; 2026-10-25, owner: "Supersampling and AA probably need to be in the
# graphics setting options"; docs/records/RENDER-KEYS-2026-10-25.md). Graphics keys like the others (preset, presets\local.psd1,
# -RenderScale), but read HERE, not by the proxy: they size dgVoodoo's [Glide] render target and MSAA.
#   I76_RENDER_SCALE  1 | 1.5 | 2 (default 2): [Glide] Resolution = scale x the display per axis (2 = the 2x2 supersample played since
#                     2026-10-12; 1 = the display's own size, the lightest). Each side capped at 8192 (the factor shrinks on both axes).
#   I76_AA            0 | 2 | 4 | 8 (default 4): [Glide] Antialiasing = off / 2x / 4x / 8x.
# Applied only when the launcher copied dgVoodoo.wide.conf to dgVoodoo.conf (PLAY.bat, PLAY-T05, PLAY-STABLE, PLAY-TICK*; not
# PLAY-VANILLA's 16:10 conf), and only when the wanted values differ from the conf's own: tools\Make-Wide-Conf.ps1 then rewrites
# dgVoodoo.wide.conf from the folder's installed one (kept once as dgVoodoo.wide.conf.pre-render-keys; only the [Glide] Resolution
# digits and the Antialiasing value change) and it is copied to dgVoodoo.conf again. Neither key set and never changed = nothing
# is touched (today's conf). Back to 2 / 4 = the installed file is put back byte for byte. The display: _i76e\display.txt (the patch
# kit's --display) if present, else the primary monitor. The keys are not passed to the game.
$renderLine = $null; $renderFailed = $false
function Get-RenderKey([string]$name) {
    if ($ld -and $ld.Env -and $ld.Env.ContainsKey($name) -and "$($ld.Env[$name])" -ne '') { return @("$($ld.Env[$name])", 'local') }
    if ($gameEnv.Contains($name)) { return @("$($gameEnv[$name])", $(if ($envSrc.ContainsKey($name)) { $envSrc[$name] } else { "preset $Preset" })) }
    $e = [Environment]::GetEnvironmentVariable($name); if ($e) { return @("$e", 'environment') }
    return @($null, 'default')
}
$inv = [Globalization.CultureInfo]::InvariantCulture
$rsRaw = Get-RenderKey 'I76_RENDER_SCALE'; $aaRaw = Get-RenderKey 'I76_AA'
if ($RenderScale) { $rsRaw = @($RenderScale, '-RenderScale') }
# I76_RENDER_WIDTH is reserved for a Mac render-size key (not implemented: RENDER-KEYS-2026-10-25.md s.3): nothing on Windows
foreach ($k in 'I76_RENDER_SCALE', 'I76_AA', 'I76_RENDER_WIDTH') { if ($gameEnv.Contains($k)) { $gameEnv.Remove($k) } }
$rScale = 2.0; $rsFrom = $rsRaw[1]
if ($null -ne $rsRaw[0]) {
    $tv = 0.0
    if ([double]::TryParse(("$($rsRaw[0])").Trim(), [Globalization.NumberStyles]::AllowDecimalPoint, $inv, [ref]$tv) -and @(1.0, 1.5, 2.0) -contains $tv) { $rScale = $tv }
    else { Write-LaunchLog ("render: I76_RENDER_SCALE='{0}' ({1}) is not 1, 1.5 or 2 - using 2" -f $rsRaw[0], $rsRaw[1]) 'Yellow'; $rsFrom = 'default' }
}
$rAA = 4; $aaFrom = $aaRaw[1]
if ($null -ne $aaRaw[0]) {
    $av = ("$($aaRaw[0])").Trim().ToLowerInvariant() -replace 'x$', ''
    if ($av -eq 'off') { $av = '0' }
    if (@('0', '2', '4', '8') -contains $av) { $rAA = [int]$av }
    else { Write-LaunchLog ("render: I76_AA='{0}' ({1}) is not 0, 2, 4 or 8 - using 4" -f $aaRaw[0], $aaRaw[1]) 'Yellow'; $aaFrom = 'default' }
}
$aaText = if ($rAA -eq 0) { 'off' } else { "${rAA}x" }
$wideConf = Join-Path $GameDir 'dgVoodoo.wide.conf'; $liveConf = Join-Path $GameDir 'dgVoodoo.conf'
$wideOrig = "$wideConf.pre-render-keys"
function Read-GlideRender([string]$path) {
    # @('WxH', 'aa') of a conf's [Glide] section, $null if it has no such lines
    if (-not (Test-Path -LiteralPath $path)) { return $null }
    $t = [IO.File]::ReadAllText($path, [Text.Encoding]::ASCII)
    $mr = [regex]::Match($t, '(?ms)^\[Glide\]\s(?:(?!^\[).)*?^Resolution\s*=\s*(\d+x\d+)')
    $ma = [regex]::Match($t, '(?ms)^\[Glide\]\s(?:(?!^\[).)*?^Antialiasing\s*=\s*(\S+)')
    if (-not $mr.Success -or -not $ma.Success) { return $null }
    return @($mr.Groups[1].Value, $ma.Groups[1].Value)
}
$explicit = ($rsFrom -ne 'default') -or ($aaFrom -ne 'default')
$sameFile = $false
if ((Test-Path -LiteralPath $wideConf) -and (Test-Path -LiteralPath $liveConf)) {
    $sameFile = ((Get-FileHash -LiteralPath $wideConf -Algorithm MD5).Hash -eq (Get-FileHash -LiteralPath $liveConf -Algorithm MD5).Hash)
}
$srcText = (@(@($rsFrom, $aaFrom) | Select-Object -Unique) -join ' / ')
if (-not $sameFile) {
    if ($explicit) { Write-LaunchLog ("render keys NOT applied (scale {0:0.##} from {1}, AA {2} from {3}): dgVoodoo.conf is not dgVoodoo.wide.conf - this launcher uses another conf" -f $rScale, $rsFrom, $aaText, $aaFrom) 'Yellow' }
} else {
    # the display the conf is for
    $dW = 0; $dH = 0; $dFrom = 'the primary monitor'
    $kitDisp = Join-Path $GameDir '_i76e\display.txt'
    if ((Test-Path -LiteralPath $kitDisp) -and ((Get-Content -LiteralPath $kitDisp -TotalCount 1) -match '^\s*(\d+)x(\d+)')) { $dW = [int]$Matches[1]; $dH = [int]$Matches[2]; $dFrom = '_i76e\display.txt' }
    else { try { Add-Type -AssemblyName System.Windows.Forms; $b0 = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds; $dW = $b0.Width; $dH = $b0.Height } catch { } }
  if (-not $explicit -and -not (Test-Path -LiteralPath $wideOrig)) {
    $cur = Read-GlideRender $liveConf
    if ($cur) {
        $cs = if ($dW -gt 0) { "{0:0.##}x " -f ([int]($cur[0] -split 'x')[0] / $dW) } else { '' }
        $renderLine = "render: {0}({1}), AA {2} (default: no I76_RENDER_SCALE / I76_AA set, dgVoodoo.wide.conf as installed; display {3}x{4} from {5})" -f $cs, $cur[0], $cur[1], $dW, $dH, $dFrom
    }
  } elseif ($dW -lt 640 -or $dH -lt 480) {
        Write-LaunchLog "render keys NOT applied: the display size could not be read" 'Yellow'; $renderFailed = $true
    } else {
        $f0 = [Math]::Min($rScale, [Math]::Min(8192.0 / $dW, 8192.0 / $dH))
        $wantRes = "{0}x{1}" -f ([int]([Math]::Floor($dW * $f0 / 2.0) * 2)), ([int]([Math]::Floor($dH * $f0 / 2.0) * 2))
        $cur = Read-GlideRender $wideConf
        $how = 'unchanged'
        if (-not $cur -or $cur[0] -ne $wantRes -or $cur[1] -ne $aaText) {
            $orig = Read-GlideRender $wideOrig
            if ($DryRun) { $how = 'DRY RUN: would rewrite dgVoodoo.wide.conf' }
            elseif ($rScale -eq 2.0 -and $rAA -eq 4 -and $orig -and $orig[0] -eq $wantRes -and $orig[1] -eq $aaText) {
                Copy-Item -LiteralPath $wideOrig -Destination $wideConf -Force
                Remove-Item -LiteralPath $wideOrig -Force
                $how = 'the installed dgVoodoo.wide.conf put back'
            } else {
                $mwc = @((Join-Path $PSScriptRoot 'tools\Make-Wide-Conf.ps1'), (Join-Path $GameDir '_tools\Make-Wide-Conf.ps1'),
                         (Join-Path $GameDir '_i76e\repo\tools\Make-Wide-Conf.ps1')) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
                if (-not $mwc) { Write-LaunchLog "render keys NOT applied: tools\Make-Wide-Conf.ps1 is not beside PLAY-i76.ps1, in _tools\ or in _i76e\repo\tools\" 'Yellow'; $renderFailed = $true }
                else {
                    if (-not (Test-Path -LiteralPath $wideOrig)) { Copy-Item -LiteralPath $wideConf -Destination $wideOrig -Force }
                    $mwArgs = @{ GameDir = $GameDir; Width = $dW; Height = $dH; Template = $wideOrig; SourceConf = $wideOrig; Scale = $rScale
                                 Antialiasing = "$rAA"; NoPreset = $true }
                    if (($dW / $dH) -le (4.0 / 3.0 + 0.01)) { $mwArgs['AllowNarrow'] = $true }
                    $global:LASTEXITCODE = 0
                    $mwOut = @(& $mwc @mwArgs 2>&1 | ForEach-Object { "$_" })
                    $after = Read-GlideRender $wideConf
                    if ($LASTEXITCODE -or -not $after -or $after[0] -ne $wantRes -or $after[1] -ne $aaText) {
                        foreach ($l in $mwOut) { Write-LaunchLog ("  Make-Wide-Conf: $l") 'Yellow' }
                        Write-LaunchLog "render keys NOT applied: Make-Wide-Conf.ps1 failed - putting the installed dgVoodoo.wide.conf back" 'Red'
                        Copy-Item -LiteralPath $wideOrig -Destination $wideConf -Force
                        $renderFailed = $true
                    } else { $how = "dgVoodoo.wide.conf rewritten (installed copy kept as dgVoodoo.wide.conf.pre-render-keys)" }
                }
            }
            if (-not $DryRun) {
                Copy-Item -LiteralPath $wideConf -Destination $liveConf -Force
                if ((Get-FileHash -LiteralPath $wideConf -Algorithm MD5).Hash -ne (Get-FileHash -LiteralPath $liveConf -Algorithm MD5).Hash) {
                    Write-LaunchLog "render: dgVoodoo.conf did not read back equal to dgVoodoo.wide.conf" 'Red'; $renderFailed = $true
                }
            }
        }
        $now = Read-GlideRender $liveConf
        $shown = if ($DryRun -and $how -ne 'unchanged') { @($wantRes, $aaText) } elseif ($now) { $now } else { @('?', '?') }
        $renderLine = "render: {0:0.##}x ({1}), AA {2} (from {3}; display {4}x{5} from {6}; {7})" -f $rScale, $shown[0], $shown[1], $srcText, $dW, $dH, $dFrom, $how
        if ($renderFailed) { $renderLine = "render: {0} AA {1} as the conf is (the keys asked for {2:0.##}x / AA {3}, see above)" -f $shown[0], $shown[1], $rScale, $aaText }
  }
}
if ($renderLine) { Write-LaunchLog $renderLine 'Cyan' }
# the field of view this panel gets (the proxy's Hor+ maths, apply_aspect: f -> 2 atan(0.75 D tan(f/2)); I76_FOV / I76_FOV_HOOD = the
# 4:3 base, stock 90 / 120). Said here because the launcher log is what a player reads: widescreen shows MORE, nothing is stretched.
$asp = if ($gameEnv.Contains('I76_ASPECT')) { "$($gameEnv['I76_ASPECT'])" } else { '' }
$fovB = 90.0; $fovH = 120.0; $tv2 = 0.0
if ($gameEnv.Contains('I76_FOV') -and [double]::TryParse("$($gameEnv['I76_FOV'])", [Globalization.NumberStyles]::AllowDecimalPoint, $inv, [ref]$tv2) -and $tv2 -ge 60 -and $tv2 -le 120) { $fovB = $tv2 }
if ($gameEnv.Contains('I76_FOV_HOOD') -and [double]::TryParse("$($gameEnv['I76_FOV_HOOD'])", [Globalization.NumberStyles]::AllowDecimalPoint, $inv, [ref]$tv2) -and $tv2 -ge 80 -and $tv2 -le 150) { $fovH = $tv2 }
if ($asp -match '^\s*([\d.]+)\s*[:xX]\s*([\d.]+)\s*$') { $aspD = [double]::Parse($Matches[1], $inv) / [double]::Parse($Matches[2], $inv) } elseif ($asp -match '^\s*[\d.]+\s*$') { $aspD = [double]::Parse($asp.Trim(), $inv) } else { $aspD = 4.0 / 3.0 }
if ($aspD -lt 1.34 -or $aspD -gt 3.6) { $aspD = 4.0 / 3.0 }
$wid = { param($f) 2.0 * [Math]::Atan(0.75 * $aspD * [Math]::Tan($f / 2.0 * [Math]::PI / 180.0)) * 180.0 / [Math]::PI }
Write-LaunchLog ("field of view: {0:0} deg at 4:3 -> {1:0.#} deg horizontal on this {2:0.###}:1 picture (hood view {3:0} -> {4:0.#}); widescreen shows more of the world, nothing is stretched (I76_FOV / I76_FOV_HOOD change the base)" -f $fovB, (& $wid $fovB), $aspD, $fovH, (& $wid $fovH)) 'DarkGray'
if ($RenderOnly) { if ($renderFailed) { exit 5 } else { exit 0 } }

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
        $f = [math]::Min($rScale, [math]::Min(8192.0 / $ww, 8192.0 / $wh))   # I76_RENDER_SCALE (default 2)
        $gw = [int]([math]::Floor($ww * $f / 2) * 2); $gh = [int]([math]::Floor($wh * $f / 2) * 2)
        $glRx = New-Object regex '(?ms)(^\[Glide\]\s.*?^Resolution\s*= )\d+x\d+'
        if ($DryRun) {
            Write-Host ("windowed {0}x{1}: DRY RUN - dgVoodoo.conf not changed" -f $ww, $wh) -ForegroundColor Yellow
        } elseif ($glRx.IsMatch($ct) -and $ct -match '(?m)^FullScreenMode\s*= false') {
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

if ($FfbOff -or $env:I76_FFB_OFF -eq '1') {   # the lab harness sets the env key: the interposer stays off too
    $gameEnv['I76_FFB_OFF'] = '1'; $NoFfb = $true
    Write-Host "force feedback OFF (I76_FFB_OFF=1: no game effects, no interposer)" -ForegroundColor Cyan
}

if ($SkipCutscenes) {
    $gameEnv['I76_SKIP_CUTSCENES'] = '1'
    Write-Host "mission briefing / closing movies skipped (I76_SKIP_CUTSCENES=1)" -ForegroundColor Cyan
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
if ($controlsMode -eq 'stock' -and -not $PSBoundParameters.ContainsKey('WheelUp') -and -not $settingsParams.ContainsKey('WheelUp')) { $WheelUp = 'Enter' }
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
# The Patch Kit's optional opentrack (INSTALL-EXTRAS.bat, 2026-10-25) is a portable copy inside the game folder: use it when
# -OpenTrack was not given and the default install path holds none.
if (-not $PSBoundParameters.ContainsKey('OpenTrack') -and -not (Test-Path $OpenTrack) -and (Test-Path (Join-Path $GameDir '_tools\opentrack\opentrack.exe'))) {
    $OpenTrack = Join-Path $GameDir '_tools\opentrack\opentrack.exe'
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
    # logs first written during the session get the feedback line too
    Set-LogBanner (Join-Path $GameDir 'mciproxy.log')
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
# the helpers' logs (they have exited or been stopped above) start with the feedback line too
foreach ($lg in '_ffb\ffb-interposer.log', '_ahk\opentrack-autostart.log') { Set-LogBanner (Join-Path $GameDir $lg) }
