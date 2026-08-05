# Interstate '76 / Nitro Pack launcher (Windows + dgVoodoo recipe).
#
# Presentation is owned by dgVoodoo (dgVoodoo.windows.conf): starts FULLSCREEN
# (aspect-correct stretched_ar), Alt+Enter toggles fullscreen/windowed, and
# dgVoodoo's emulated cursor keeps the mouse correct in both modes.
#
# This launcher just starts the game plus i76wheel.exe (mouse-wheel -> targeting
# keys: wheel up = Q frontal_target, wheel down = T target_nearest_enemy - the
# 1997 engine has no wheel tokens, see tools/i76wheel.c) and cleans it up when
# the game exits.
#
# Usage: PLAY-i76.ps1 [-GameDir "C:\Games\Interstate 76"] [-Exe i76.exe]
param(
    [string]$GameDir = "C:\Games\Interstate 76",
    [string]$Exe = "i76.exe",
    # Frame generation. Pass "" to skip it. Steam does NOT need to be running.
    [string]$LosslessScaling = "C:\Program Files (x86)\Steam\steamapps\common\Lossless Scaling\LosslessScaling.exe",
    # Head tracking. Pass "" to skip. opentrack is started AND told to begin
    # tracking (it has no auto-start switch - see opentrack-autostart.ahk).
    [string]$OpenTrack = "C:\Program Files (x86)\opentrack\opentrack.exe",
    # Custom force feedback (tools/ffb). OPT-IN on purpose: it synthesises real
    # slip/load/impact feel from telemetry, but the gains have not been judged by
    # hand yet, and force feedback nobody has tuned goes straight into the user's
    # hands. Calibrate first (tools\ffb\ffb-calibrate.ps1), then add -Ffb.
    [switch]$Ffb,
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
    [int]$MusicVolume = 550,
    # Turn on logging in the winmm CD-audio proxy (tools/winmm-cdaudio), if it is
    # installed. Writes winmm-cdaudio.log beside the game exe, recording every MCI
    # call the engine makes - including ones the proxy does not handle. Set here
    # rather than left to the user because the variable has to be present in the
    # environment of the process that LAUNCHES the game, which is easy to get wrong.
    [switch]$CdAudioLog,
    # Mouse wheel bindings (i76wheel.exe). The engine's mouse device has three
    # buttons and no wheel channels, so the wheel cannot be bound in input.map at
    # all - it is translated to a keystroke instead.
    #   up   = Tab  -> weapon_cycle     (toggle the front weapon)
    #   down = 5    -> hardpoint5_fire  (normally the dropper)
    # WhichKey the dropper needs depends on the CAR'S LOADOUT, not the game, so if
    # the dropper sits on a different hardpoint use -WheelDown 4 (etc).
    # Names must match input.map; verify with tools/lint-input-map.py.
    [string]$WheelUp = "Tab",
    [string]$WheelDown = "5"
)
$ErrorActionPreference = 'SilentlyContinue'

$wheel = $null
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

# Head tracking: opentrack + the freetrack->game layer. opentrack has NO
# command-line switch to begin tracking, so opentrack-autostart.ahk presses Start
# for it (idempotent - it exits immediately if FT_SharedMem already exists, so a
# session you started by hand is left alone).
$ot = $null
$otHelper = $null
$track = $null
if ($OpenTrack -and (Test-Path $OpenTrack)) {
    if (-not (Get-Process -Name 'opentrack' -ErrorAction SilentlyContinue)) {
        $ot = Start-Process -FilePath $OpenTrack -PassThru
    }
    $autoStart = Join-Path $GameDir '_ahk\opentrack-autostart.ahk'
    if ((Test-Path $ahkExe) -and (Test-Path $autoStart)) {
        $otHelper = Start-Process -FilePath $ahkExe -ArgumentList "`"$autoStart`"" -PassThru
    }
}
$trackCfg = Join-Path $GameDir '_ahk\i76-headtrack.ahk'
if ((Test-Path $ahkExe) -and (Test-Path $trackCfg)) {
    $track = Start-Process -FilePath $ahkExe -ArgumentList "`"$trackCfg`"" -WorkingDirectory (Join-Path $GameDir '_ahk') -PassThru
}

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
#   * i76-remap.ahk detects the wheel by capability once when it starts, and
#     i76-headtrack.ahk wants opentrack already publishing.
# So: wait (briefly, bounded) for opentrack to actually publish before launching.
if ($OpenTrack -and (Test-Path $OpenTrack)) {
    $deadline = (Get-Date).AddSeconds(20)
    while ((Get-Date) -lt $deadline) {
        try {
            $m = [System.IO.MemoryMappedFiles.MemoryMappedFile]::OpenExisting('FT_SharedMem')
            $m.Dispose(); break
        } catch { Start-Sleep -Milliseconds 400 }
    }
}
Start-Sleep -Milliseconds 800     # let the AHK layers finish their device probe

# music-fix/ (the Strlkup.dll IAT hook that restores the CD-audio soundtrack) logs
# to mciproxy.log only when this is set. Set UNCONDITIONALLY: it was opt-in, which
# meant the normal launch path - desktop shortcut -> .bat -> here, no env var
# anywhere - produced no log, and "hook installed but silent" looked exactly like
# "hook never ran". A handful of lines per session is worth never being blind again.
$env:I76MUSIC_LOG = "1"

if ($CdAudioLog) {
    $env:I76_CDAUDIO_LOG = "1"
    Write-Host "CD-audio proxy logging ON -> $GameDir\winmm-cdaudio.log" -ForegroundColor Cyan
}

# If the winmm CD-audio proxy is installed it handles music itself, correctly
# synchronised, so the PowerShell fallback must not ALSO play - two soundtracks at
# once out of step with each other is worse than none.
if (-not $NoMusic -and (Test-Path (Join-Path $GameDir 'winmm.dll'))) {
    Write-Host "winmm CD-audio proxy detected - leaving music to it (skipping i76-music.ps1)." -ForegroundColor DarkGray
    $NoMusic = $true
}

$proc = Start-Process -FilePath (Join-Path $GameDir $Exe) -ArgumentList '-glide' -WorkingDirectory $GameDir -PassThru

# Custom force feedback, AFTER the game: it reads the game's own memory, so the
# process has to exist first. It waits for a mission to load on its own (the
# player entity only exists in one), so starting it here rather than making the
# user launch it by hand mid-mission is safe. Own window so the panel is visible.
$ffb = $null
if ($Ffb) {
    $ffbScript = Join-Path $PSScriptRoot 'tools\ffb\ffb-interposer.ps1'
    if (-not (Test-Path $ffbScript)) { $ffbScript = Join-Path $GameDir '_ffb\ffb-interposer.ps1' }
    if (Test-Path $ffbScript) {
        $ffb = Start-Process -FilePath 'powershell.exe' `
            -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',"`"$ffbScript`"" -PassThru
    } else {
        Write-Host "-Ffb requested but ffb-interposer.ps1 was not found." -ForegroundColor Yellow
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

$proc.WaitForExit()

if ($wheel    -and -not $wheel.HasExited)    { Stop-Process -Id $wheel.Id    -Force }
if ($ahk      -and -not $ahk.HasExited)      { Stop-Process -Id $ahk.Id      -Force }
if ($ls       -and -not $ls.HasExited)       { Stop-Process -Id $ls.Id       -Force }
if ($track    -and -not $track.HasExited)    { Stop-Process -Id $track.Id    -Force }
if ($otHelper -and -not $otHelper.HasExited) { Stop-Process -Id $otHelper.Id -Force }
# The interposer releases the wheel in its own finally block, but Stop-Process
# -Force skips that - so ask it to stop, and only kill it if it will not.
# The music helper exits on its own when the game does, but kill it if it lingers -
# an MCI device left open holds the file and can wedge later playback.
if ($music -and -not $music.HasExited) { Stop-Process -Id $music.Id -Force }
if ($ffb -and -not $ffb.HasExited) {
    Stop-Process -Id $ffb.Id -Force
    # Belt and braces: if the force was latched when we killed it, the wheel would
    # keep pulling. Re-open the device briefly and zero it.
    try {
        . (Join-Path $PSScriptRoot 'tools\ffb\FfbCore.ps1')
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
# These are the keys i76-remap.ahk can hold (RSGExit's list + the @wheel holds).
try {
    Add-Type -Name KbRelease -Namespace I76 -MemberDefinition @'
[DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint flags, System.UIntPtr extra);
'@ -ErrorAction SilentlyContinue
    $KEYUP = 0x2; $EXT = 0x1
    # arrows (extended keys), digits 1-8, Enter, and the letters the layer emits
    $vks = @(0x25,0x26,0x27,0x28) + (0x31..0x38) + @(0x0D) +
           @(0x48,0x49,0x4E,0x4D,0x59,0x55,0x56,0x58,0x42,0x47,0x45,0x52,0x51,0x54,0x09,0x20)
    foreach ($vk in $vks) {
        $flags = $KEYUP
        if ($vk -ge 0x25 -and $vk -le 0x28) { $flags = $KEYUP -bor $EXT }
        [I76.KbRelease]::keybd_event([byte]$vk, 0, $flags, [System.UIntPtr]::Zero)
    }
} catch { }
