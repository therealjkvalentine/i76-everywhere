<#
  ffb-interposer.ps1 - read Interstate '76's vehicle state and drive the wheel.

  Sits between the game and the wheel: samples telemetry (Telemetry.ps1), decides
  a force (FfbMixer.ps1), writes it to the device (FfbCore.ps1), and shows what it
  is doing (the panel below). Everything is optional and nothing is permanent -
  no game files are touched and no patches are applied unless you ask.

  ---------------------------------------------------------------------------
  START HERE
  ---------------------------------------------------------------------------
      # watch the telemetry and the force model WITHOUT touching the wheel.
      # Safe while the game holds the device - do this first.
      tools\ffb\ffb-interposer.ps1 -DryRun

      # for real
      tools\ffb\ffb-interposer.ps1

      # quieter / louder overall
      tools\ffb\ffb-interposer.ps1 -Master 0.6

      # one channel at a time, which is the only sane way to judge feel
      tools\ffb\ffb-interposer.ps1 -Only corner
      tools\ffb\ffb-interposer.ps1 -Mute texture,scrub

      # capture a drive for offline tuning
      tools\ffb\ffb-interposer.ps1 -Log drive.csv

  Live keys: [space] mute  [+/-] master  [s] save tune  [q] quit

  WEB PANEL (2026-10-25): this loop publishes its state to 127.0.0.1:17682 (UDP JSON,
  20 Hz; harmless when nobody listens) and takes gate / arm commands on
  127.0.0.1:17683. ffb-panel.py (FFB-WEB-PANEL.bat) serves the page at
  http://127.0.0.1:17691/ - telemetry, every channel as a meter with solo / mute,
  gain sliders, the event log, the feel checklist and the LFE bus. A slider writes
  ffb-tune-owner.json; this loop re-reads that file when it changes (twice a second)
  and logs each changed value to the event log and to ffb-interposer.log beside it.
  -PanelPort 0 turns the publishing and the command port off.

  ---------------------------------------------------------------------------
  ON EXCLUSIVITY
  ---------------------------------------------------------------------------
  FFB needs an EXCLUSIVE DirectInput acquisition and the game takes one at
  startup, so in principle only one of us can hold the wheel. -DryRun exists
  because of that: it exercises telemetry and the whole force model with the
  device untouched, so the interesting half can be developed and tuned while the
  game is running normally.

  Whether our acquire actually succeeds alongside the game's is an empirical
  question, not a deducible one - so this script TRIES, and reports plainly which
  happened rather than assuming. If it fails, see docs/WHEEL-T300.md.
#>
param(
    # Read + display only; never open or drive the wheel. Start here.
    [switch]$DryRun,
    # Force update rate. The sim only advances at 20 Hz, but a faster force loop
    # makes oscillating channels (texture, scrub, judder) smooth instead of steppy.
    #
    # MEASURED CEILING ~62 Hz. Start-Sleep's granularity on Windows is one
    # scheduler tick (~15.6 ms), so any request above ~64 Hz still yields ~62.
    # Telemetry itself is not the limit - it polls at 3400 Hz. Asking for 200
    # here buys nothing, so the default is what is actually achievable, and the
    # oscillator frequencies in FfbMixer.ps1 are chosen to stay well under the
    # Nyquist limit this implies.
    [int]$Hz = 60,
    [double]$Master = 1.0,
    # Channels: center corner oversteer brake texture scrub judder impact weapon
    [string[]]$Only = @(),
    [string[]]$Mute = @(),
    [switch]$NoPanel,
    # Render one panel frame from synthetic data and exit. No game, no wheel.
    [switch]$PanelDemo,
    [string]$Log = "",
    [string]$Tune = "",
    [int]$Seconds = 0,       # 0 = until [q] or Ctrl+C
    # Seconds to wait for a mission to load before giving up. The player entity
    # only exists in a mission, so this is what makes the tool launchable at the
    # title screen (or from the launcher) instead of only once you are driving.
    # 0 = do not wait, fail immediately.
    [int]$Wait = 180,
    # Leave the engine's own force feedback enabled. NOT the default: while we hold
    # the wheel, the engine's fire path faults at I7_SFRCE.DLL+0x2505 because it
    # dereferences its effect object without a null check. Use only if you want the
    # engine's weapon effects back and will not fire.
    [switch]$KeepEngineFfb,
    # Web panel (ffb-panel.py): state datagrams to this loopback UDP port, commands from
    # -ControlPort. 0 = off. Loopback only, never another address.
    [int]$PanelPort = 17682,
    [int]$ControlPort = 17683
)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $here 'Telemetry.ps1')
. (Join-Path $here 'FfbMixer.ps1')
if (-not $DryRun) { . (Join-Path $here 'FfbCore.ps1') }

$ALL_CH = @('center','corner','oversteer','brake','texture','scrub','judder','impact','weapon','shift',
            'engine','ignition','hit','landing')   # the last four: 2026-10-24

# ---------------------------------------------------------------------------
# Panel
# ---------------------------------------------------------------------------
function Bar {
    param([double]$V, [double]$Max, [int]$W = 26)
    if ($Max -le 0) { $Max = 1 }
    $n = [int]([math]::Round([math]::Min(1.0, [math]::Abs($V) / $Max) * $W))
    $c = if ($V -lt 0) { '<' } else { '#' }
    return ($c * $n).PadRight($W)
}
function CenterBar {
    param([double]$V, [double]$Max, [int]$Half = 22)
    if ($Max -le 0) { $Max = 1 }
    $n = [int]([math]::Round([math]::Min(1.0, [math]::Abs($V) / $Max) * $Half))
    $l = ' ' * $Half; $r = ' ' * $Half
    if ($V -lt 0) { $l = (' ' * ($Half - $n)) + ('<' * $n) }
    elseif ($V -gt 0) { $r = ('>' * $n) + (' ' * ($Half - $n)) }
    return "$l|$r"
}

# Extracted from the loop rather than inlined so it can be rendered WITHOUT the
# game running (-PanelDemo). An observability panel you cannot look at until you
# are mid-mission with a wheel in your hands is one whose column alignment you
# find out about at the worst possible moment.
#
# Parameters are TYPED deliberately. Untyped, PowerShell's command-argument mode
# hands them over as strings - and a numeric format spec applied to a string is
# silently IGNORED rather than an error. That produced "entity 0x0x048C1388"
# (hex literals in argument mode stay strings, so "0x{0:X8}" -f "0x048C1388"
# just pasted it in) and "master 1.0" where "{0:0.00}" was asked for. Typing the
# parameters forces the coercion at the boundary.
function Build-Panel {
    param([string]$Mode, [int64]$Ent, [double]$Wheelbase, $S, $Out,
          [int]$Force, [double]$Peak, [double]$Rate, [double]$Master,
          [bool]$Enabled, $Active, $Notes, [string]$Calib)
    $L = New-Object System.Collections.ArrayList
    $rule = "  " + ("-" * 74)
    $null = $L.Add(("  I76 FFB INTERPOSER   {0}" -f $Mode))
    $null = $L.Add(("  entity 0x{0:X8}   wheelbase {1:0.00} m   sim ticks {2}" -f `
        $Ent, $Wheelbase, $(if ($S) { $S.Ticks } else { 0 })))
    $null = $L.Add(("  " + $Calib))
    # Persistent, not a one-off startup message. This is the one action that will
    # take the game down, and a warning that scrolled past ten minutes ago is not
    # a warning.
    if ($S -and $S.GameFfb -ne 0) {
        $null = $L.Add("  *** DO NOT FIRE - I7FF_SIM_Effect still live; a shot faults the DLL at +0x2505 ***")
    } else {
        $null = $L.Add("  engine FFB call bypassed (0x52bbe4 = 0) - firing safe; effects still readable")
    }
    $null = $L.Add($rule)
    if ($S) {
        $null = $L.Add(("   speed {0,6:0.0} mph ({1,5:0.0} m/s)    throttle {2,6:0.00}    steer {3,6:0.00}" -f `
            $S.SpeedMph, $S.Speed, $S.Throttle, $S.Steer))
        $null = $L.Add(("   long g {0,6:0.00}   lat g {1,6:0.00}   jolt {2,6:0.0}   {3}{4}" -f `
            $S.LongG, $S.LatG, $S.Jolt,
            $(if ($S.Braking) { "BRAKING " } else { "" }),
            $(if ($S.Airborne) { "AIRBORNE" } else { "" })))
        $null = $L.Add(("   yaw {0,7:0.000} rad/s   expected {1,7:0.000}   grip {2,3:0}%   U {3,4:0.00}  O {4,4:0.00}" -f `
            $S.YawRate, $S.ExpectedYaw, $(if ($Out) { $Out.Channels['grip%'] } else { 100 }),
            $S.Understeer, $S.Oversteer))
        # The raw fire flag and the sim-tick age, both shown because both have
        # been invisible failure modes: a weapon channel that never fires looks
        # identical to a wrong address, and a frozen sim looks identical to a
        # quiet road.
        # RPM is shown so it can be checked against the dashboard tachometer -
        # it was identified by a memory scan, not by a decompile, so the needle
        # is the only thing that confirms it.
        $null = $L.Add(("   rpm {0,5}  slide {1,5:0.00}  gear {2,2}  surf {3,2} {4,-7}x{5:0.00} {6}{7}{8}{9}" -f `
            $(if ($null -ne $S.Rpm) { $S.Rpm } else { 0 }),
            $(if ($null -ne $S.Slide) { $S.Slide } else { 0 }),
            $(if ($null -ne $S.Gear) { $S.Gear } else { -1 }),
            $(if ($null -ne $S.Surface) { $S.Surface } else { -1 }),
            $(if ($S.Paved) { 'paved' } else { 'offroad' }),
            $(if ($Out -and $null -ne $Out.Channels['surf%']) { $Out.Channels['surf%'] / 100.0 } else { 1.0 }),
            $(if ($S.EngineRunning) { 'ENG ' } else { 'eng- ' }),
            $(if ($S.DriftFlag) { 'DRIFT ' } else { '' }),
            $(if ($S.SkidFlag) { 'SLIDE ' } else { '' }),
            $(if ($S.ShotSource -eq 'ammo') { 'ammo' } else { 'fxblk' })))
        $null = $L.Add(("   engine fx: {0} active{1}   input fire {2}   |yaw-expect| {3,6:0.000}   tick {4,5:0.00}s{5}" -f `
            $(if ($null -ne $S.FxActive) { $S.FxActive } else { 0 }),
            $(if ($S.FxFired -and $S.FxFired.Count) { "  FIRED: " + (($S.FxFired | ForEach-Object { "id$($_.Id)" }) -join ' ') } else { "" }),
            $(if ($S.FireRaw -ne 0) { "YES" } else { "no " }),
            [math]::Abs($S.YawRate - $S.ExpectedYaw),
            $(if ($null -ne $S.SinceTick) { $S.SinceTick } else { 0 }),
            $(if ($null -ne $S.SinceTick -and $S.SinceTick -gt 0.5) { "  PAUSED" } else { "" })))

        # Yaw and the bicycle-model prediction should agree in SIGN whenever the
        # car is actually turning. Persistent disagreement means TEL_YAW_SIGN is
        # inverted, which is worth saying out loud rather than leaving to be felt.
        if ($S.Speed -gt 5 -and [math]::Abs($S.ExpectedYaw) -gt 0.05 -and
            [math]::Sign($S.YawRate) -ne [math]::Sign($S.ExpectedYaw)) {
            $null = $L.Add("   ^ yaw and prediction DISAGREE in sign - run ffb-calibrate.ps1")
        } else { $null = $L.Add("") }
    } else {
        $null = $L.Add("   (no telemetry - paused, at a menu, or between missions)")
        $null = $L.Add(""); $null = $L.Add(""); $null = $L.Add("")
    }
    $null = $L.Add($rule)
    if ($Out) {
        foreach ($c in $ALL_CH) {
            $v = [double]$Out.Channels[$c]
            $tag = if ($Active[$c]) { " " } else { "x" }
            $null = $L.Add(("  {0}{1,-10}{2,7}  |{3}|" -f $tag, $c, [int]$v, (Bar $v 5000)))
        }
        $null = $L.Add($rule)
        $null = $L.Add(("   FORCE {0,7}  {1}   peak {2,5:0}" -f `
            $Force, (CenterBar $Force 9500), $Peak))
    }
    $null = $L.Add($rule)
    $null = $L.Add(("   loop {0,5:0.0} Hz   master {1:0.00}   {2}" -f `
        $Rate, $Master, $(if ($Enabled) { "ARMED " } else { "MUTED " })))
    $null = $L.Add("   [space] mute  [+/-] master  [s] save tune  [q] quit")
    $null = $L.Add($rule)
    $null = $L.Add("   events:")
    $n = 0
    if ($Notes) { foreach ($x in $Notes) { $null = $L.Add("     $x"); $n++ } }
    for ($i = $n; $i -lt 6; $i++) { $null = $L.Add("") }
    return $L
}

# Render one frame with synthetic state and exit. Lets the layout be checked with
# no game, no mission and no wheel.
if ($PanelDemo) {
    . (Join-Path $here 'FfbMixer.ps1')
    $m = Mix-New
    # a plausible mid-corner-on-the-limit frame
    $fake = [pscustomobject]@{
        T = 3.0; Speed = 17.4; SpeedMph = 38.9; Steer = -0.42; Throttle = 0.65
        YawRate = -0.51; ExpectedYaw = -0.72; LongG = -0.18; LatG = -0.90
        Understeer = 0.41; Oversteer = 0.0; Jolt = 2.3
        AngVelX = 0.35; AngVelZ = 0.22; Tumble = 0.57; Vy = 0.4
        Braking = $false; Airborne = $false; Ticks = 412; Polls = 1240; Wheelbase = 4.662
        GameFfb = 0; Firing = $false; FireRaw = 0; SinceTick = 0.02
    }
    for ($t = 0.0; $t -lt 1.2; $t += 1.0/60) { $fake.T = $t; $o = Mix-Update $m $fake }
    $act = @{}; foreach ($c in $ALL_CH) { $act[$c] = $true }
    $act['judder'] = $false
    $notes = @("    2.9s  UNDERSTEER", "    1.4s  IMPACT 62%")
    Write-Host ""
    foreach ($ln in (Build-Panel -Mode "PANEL DEMO (synthetic data)" -Ent ([int64]0x048C1388) `
                -Wheelbase 4.662 -S $fake -Out $o -Force $o.Force -Peak $m.PeakForce `
                -Rate 61.8 -Master 1.0 -Enabled $true -Active $act -Notes $notes `
                -Calib $script:TEL_CALIB_SOURCE)) {
        Write-Host $ln
    }
    Write-Host ""
    exit 0
}

# ---------------------------------------------------------------------------
# Web panel plumbing (2026-10-25): publish, take commands, reload the tune file
# ---------------------------------------------------------------------------
$script:INV = [Globalization.CultureInfo]::InvariantCulture
function Jn([double]$v) {
    if ([double]::IsNaN($v) -or [double]::IsInfinity($v)) { return 'null' }
    return $v.ToString('0.####', $script:INV)
}
function Js([string]$s) { return '"' + (($s -replace '\\', '\\') -replace '"', '\"') + '"' }
function Jb($b) { if ($b) { 'true' } else { 'false' } }
$GEAR_NAMES = @{ 0 = 'R'; 1 = 'N'; 2 = '1'; 3 = '2'; 4 = '3' }
$SIDE_NAMES = @('front', 'left', 'right', 'back')

$intLogPath = Join-Path $here 'ffb-interposer.log'
function Write-IntLog([string]$Line) {
    try { Add-Content -LiteralPath $intLogPath -Value ("{0}  {1}" -f (Get-Date).ToString('yyyy-MM-ddTHH:mm:ss.fff'), $Line) -Encoding ASCII } catch { }
}
try {
    # keep the file small: the last 2000 lines
    if ((Test-Path -LiteralPath $intLogPath) -and (Get-Item -LiteralPath $intLogPath).Length -gt 400000) {
        $keep = @(Get-Content -LiteralPath $intLogPath -Tail 2000)
        Set-Content -LiteralPath $intLogPath -Value $keep -Encoding ASCII
    }
} catch { }

function New-LoopUdp([int]$BindPort) {
    $u = if ($BindPort -gt 0) {
        New-Object System.Net.Sockets.UdpClient (New-Object System.Net.IPEndPoint ([System.Net.IPAddress]::Loopback, $BindPort))
    } else { New-Object System.Net.Sockets.UdpClient }
    # SIO_UDP_CONNRESET off: a datagram to a port nobody listens on must not make a later call throw
    try { $null = $u.Client.IOControl(-1744830452, [byte[]](0, 0, 0, 0), $null) } catch { }
    return $u
}

$telCtx = $null
$dev    = $null
$logSw  = $null
$pubUdp = $null
$ctlUdp = $null
try {
    # Wait rather than fail. Tel-Open needs the player entity, which only exists
    # inside a mission - so a bare launch at the title screen used to abort. That
    # made this impossible to start alongside the game (see PLAY-i76.ps1 -Ffb):
    # you would have had to launch it by hand after loading a mission. Waiting
    # costs nothing and makes it launchable at any point.
    $waited = 0
    while (-not $telCtx) {
        try { $telCtx = Tel-Open }
        catch {
            if ($Wait -le 0) { throw }
            if ($waited -ge $Wait) { throw "waited $Wait s for a mission and gave up: $_" }
            if ($waited -eq 0) { Write-Host "waiting for a mission to load... ($_)" -ForegroundColor DarkGray }
            Start-Sleep -Seconds 2
            $waited += 2
        }
    }
    Write-Host ("telemetry OK - entity 0x{0:X8}, wheelbase {1:0.00} m, track {2:0.00} m" -f `
        $telCtx.Ent, $telCtx.Wheelbase, $telCtx.Track) -ForegroundColor Green

    $tuneTable = Mix-DefaultTune
    # THE OWNER'S TUNE PERSISTS (2026-10-24). PLAY-i76.ps1 -Ffb starts this script with
    # no -Tune, so a tune saved with [s] used to be written and never read again.
    # ffb-tune-owner.json next to this script now loads by default, and it holds ONLY
    # the values that differ from the defaults, so a default improved later still
    # reaches every key the owner never touched. Edit it by hand too, e.g.
    #     { "PavementScale": 0.4, "EngineGain": 300 }
    # (ffb-tune.json, the old full snapshot, is NOT auto-loaded: it predates current
    # defaults; pass it with -Tune to use it.)
    $ownerTune = Join-Path $here 'ffb-tune-owner.json'
    if (-not $Tune -and (Test-Path $ownerTune)) { $Tune = $ownerTune }
    if ($Tune -and (Test-Path $Tune)) {
        $j = Get-Content $Tune -Raw | ConvertFrom-Json
        foreach ($p in $j.PSObject.Properties) { $tuneTable[$p.Name] = $p.Value }
        Write-Host ("tune loaded from {0} ({1} values)" -f $Tune, @($j.PSObject.Properties).Count) -ForegroundColor Green
    }
    if ($PSBoundParameters.ContainsKey('Master') -or $null -eq $tuneTable['Master']) { $tuneTable['Master'] = $Master }
    $mix = Mix-New $tuneTable

    # LIVE TUNE (2026-10-25). The web panel's sliders write ffb-tune-owner.json; the loop
    # re-reads it when its time stamp changes. A reload rebuilds the table the way the
    # start did (defaults, then -Master if it was given, then the file) and writes the
    # changed values into $tuneTable IN PLACE - $mix.Tune is the same hashtable, so the
    # next Mix-Update uses them. A key removed from the file goes back to its default.
    # With an explicit -Tune <other file>, that file stays the base and the owner file
    # (if edited during the session) is applied over it.
    $masterBound = $PSBoundParameters.ContainsKey('Master')
    $ownerFull = [IO.Path]::GetFullPath($ownerTune)
    $explicitTune = $(if ($Tune -and (Test-Path $Tune) -and ([IO.Path]::GetFullPath($Tune) -ne $ownerFull)) { $Tune } else { '' })
    $tuneStamp = [IO.File]::GetLastWriteTimeUtc($ownerTune)
    function Tune-Reload {
        $new = Mix-DefaultTune
        if ($explicitTune) {
            $j0 = Get-Content $explicitTune -Raw | ConvertFrom-Json
            foreach ($p in $j0.PSObject.Properties) { $new[$p.Name] = $p.Value }
        }
        if ($masterBound) { $new['Master'] = $Master }
        if (Test-Path -LiteralPath $ownerTune) {
            $raw = Get-Content -LiteralPath $ownerTune -Raw
            if ($raw -and $raw.Trim()) {
                $j1 = $raw | ConvertFrom-Json
                foreach ($p in $j1.PSObject.Properties) { $new[$p.Name] = $p.Value }
            }
        }
        $chg = @()
        foreach ($k in @($new.Keys | Sort-Object)) {
            $b = $new[$k]; $a = $tuneTable[$k]
            if ($a -is [array] -or $b -is [array]) { continue }
            if ($null -eq $a -or [math]::Abs([double]$a - [double]$b) -gt 1e-9) {
                $chg += ("{0} {1} -> {2}" -f $k, $(if ($null -eq $a) { 'unset' } else { Jn ([double]$a) }), (Jn ([double]$b)))
                $tuneTable[$k] = [double]$b
            }
        }
        return ,$chg
    }
    $defaultTune = Mix-DefaultTune

    # Channel gating. -Only wins over -Mute.
    $active = @{}
    foreach ($c in $ALL_CH) {
        if ($Only.Count -gt 0) { $active[$c] = ($Only -contains $c) }
        else { $active[$c] = -not ($Mute -contains $c) }
    }

    if ($DryRun) {
        Write-Host "DRY RUN - the wheel will NOT be touched." -ForegroundColor Yellow
    } else {
        Write-Host "opening the wheel..." -ForegroundColor Cyan
        try {
            $dev = Ffb-Open
            Write-Host "ACQUIRED: $($dev.Name)" -ForegroundColor Green
        } catch {
            Write-Host "COULD NOT ACQUIRE THE WHEEL: $_" -ForegroundColor Red
            Write-Host ""
            Write-Host "The game holds an exclusive DirectInput acquisition while it runs." -ForegroundColor Yellow
            Write-Host "Re-run with -DryRun to work on telemetry and the force model," -ForegroundColor Yellow
            Write-Host "or see docs/WHEEL-T300.md. Nothing was changed." -ForegroundColor Yellow
            exit 2
        }
    }

    # ---- THE CRASH WARNING -------------------------------------------------
    # If the engine also has a live FFB device, FIRING A WEAPON CRASHES THE GAME
    # while we hold the wheel. The engine's fire path calls into I7_SFRCE.DLL and
    # dereferences its effect object WITHOUT null-checking it; our exclusive
    # acquisition kills that handle underneath it, and the next shot faults with
    # 0xC0000005 at I7_SFRCE.DLL+0x2505. Confirmed twice in the field 2026-08-04,
    # and predicted in docs/records/FFB-LAPTOP-RECON.md before it ever happened.
    #
    # Not made fatal: driving is unaffected and is most of the value here. But it
    # is impossible to miss, and the weapon channel is force-muted, because leaving
    # a channel called "weapon" armed implies firing is supported when it is the
    # one thing that will take the game down.
    # ---- make firing safe --------------------------------------------------
    # The engine's weapon-fire path dereferences its DirectInput effect object with
    # NO null check, so once we hold the wheel exclusively the first shot faults at
    # I7_SFRCE.DLL+0x2505 and the game dies. Confirmed twice in the field.
    #
    # Fixed by zeroing the engine's own "FF device present" flag at 0x52bbd0.
    # Disassembly of all six read sites shows every one gates on it and bails
    # cleanly when zero (see Tel-SetEngineFfb), so the whole subsystem becomes a
    # no-op and there is nothing left to dereference. 4 bytes of .data, restored on
    # exit, no code patched and no file touched.
    #
    # The engine's own weapon-rumble effects are the price, and they are already
    # lost the moment we take the device - this only stops it crashing over it.
    $probe = Tel-Sample $telCtx
    $engineFfbWas = $null
    if (-not $DryRun -and $probe -and $probe.GameFfb -ne 0) {
        if ($KeepEngineFfb) {
            $active['weapon'] = $false
            Write-Host ""
            Write-Host "  ##################################################################" -ForegroundColor Red
            Write-Host "  #  DO NOT FIRE WEAPONS. -KeepEngineFfb left the engine's FFB on,  #" -ForegroundColor Red
            Write-Host "  #  and its fire path will fault at I7_SFRCE.DLL+0x2505 while we   #" -ForegroundColor Red
            Write-Host "  #  hold the wheel. Driving is fine; firing crashes the game.      #" -ForegroundColor Red
            Write-Host "  ##################################################################" -ForegroundColor Red
            Write-Host ""
            Start-Sleep -Seconds 2
        } else {
            try {
                $engineFfbWas = Tel-SetEngineFfb $telCtx 0
                Write-Host ("engine FFB call disabled (0x52bbe4: 0x{0:X8} -> 0) so firing cannot crash it." -f $engineFfbWas) -ForegroundColor Green
                Write-Host "restored automatically on exit. -KeepEngineFfb to skip this." -ForegroundColor DarkGray
            } catch {
                $active['weapon'] = $false
                Write-Host "COULD NOT disable engine FFB: $_" -ForegroundColor Red
                Write-Host "DO NOT FIRE - a shot will crash the game." -ForegroundColor Red
            }
        }
    }

    if ($Log) {
        $logSw = [System.IO.StreamWriter]::new($Log, $false)
        # angVelX/angVelZ/vy are logged because the texture, judder and impact
        # channels depend on them, and a capture without them cannot judge those
        # three - ffb-replay.ps1 has to report "no data" instead of a number.
        #
        # The channel names are DERIVED FROM $ALL_CH rather than hand-written.
        # They were hand-written, and when the `weapon` channel was added to
        # $ALL_CH the row writer began emitting one more field than the header
        # named. Every column after the channels was then SHIFTED BY ONE, so
        # anything reading the file by column name got `impact` where it asked for
        # `force` - which read as a wheel that did nothing at all. A header that
        # cannot disagree with the writer is the only fix that stays fixed.
        $logCols = @('t','speed','mph','steer','throttle','longG','latG','yaw',
                     'expectYaw','understeer','oversteer','jolt',
                     'angVelX','angVelZ','vy','heave','slide','headingRate','rpm','rpmRate','shift','fireRaw','fxActive','fxFired',
                     'flags','surface','paved','surfPct','gear','steerK','latCap','shotSrc','shots','hits','wrow','gameFfb') +
                     # ch_ prefix, because 'oversteer' is BOTH a telemetry field
                     # (0..1 slip) and a force channel (scaled to OversteerGain).
                     # Emitting both under one name made every CSV reader silently
                     # keep the last one, so analysis read "max oversteer 3600" for
                     # a value that is bounded at 1. Deriving the header from
                     # $ALL_CH fixed a length mismatch and reintroduced this.
                     ($ALL_CH | ForEach-Object { "ch_$_" }) + @('force')
        $logSw.WriteLine($logCols -join ',')
    }

    if ($PanelPort -gt 0) {
        try { $pubUdp = New-LoopUdp 0 } catch { $pubUdp = $null; Write-Host "web panel: no publish socket ($_)" -ForegroundColor DarkGray }
        if ($ControlPort -gt 0) {
            try { $ctlUdp = New-LoopUdp $ControlPort }
            catch { $ctlUdp = $null; Write-Host "web panel: command port $ControlPort taken (another interposer?) - the page can watch but not mute / solo" -ForegroundColor Yellow }
        }
        if ($pubUdp) { Write-Host ("web panel feed -> udp 127.0.0.1:{0} (page: FFB-WEB-PANEL.bat, http://127.0.0.1:17691/)" -f $PanelPort) -ForegroundColor DarkGray }
    }
    Write-IntLog ("start pid {0} game pid {1} mode {2} tune {3} panel udp {4} / {5}" -f $PID, $telCtx.Proc.Id, $(if ($DryRun) { 'dry-run' } else { 'live' }), $(if ($Tune) { $Tune } else { 'defaults' }), $PanelPort, $(if ($ctlUdp) { $ControlPort } else { 'off' }))

    # Console capability probes, done ONCE. Both of these throw when stdin/stdout
    # are redirected (piped, launched from a .bat with output captured, run from a
    # harness), and a throw inside the loop would abandon a wheel that is holding
    # force. No console just means no panel and no hotkeys.
    $canKeys = $true
    try { $null = [Console]::KeyAvailable } catch { $canKeys = $false }
    $canDraw = -not $NoPanel
    if ($canDraw) {
        try { [Console]::SetCursorPosition(0, 0) } catch { $canDraw = $false }
    }
    if (-not $NoPanel -and -not $canDraw) {
        Write-Host "(no console available - panel disabled, still driving the wheel)" -ForegroundColor DarkGray
    }

    $period   = 1.0 / [math]::Max(1, $Hz)
    $sw       = [System.Diagnostics.Stopwatch]::StartNew()
    $nextDraw = 0.0
    $loops    = 0
    $lastSec  = 0.0
    $rateNow  = 0.0
    $loopsAtSec = 0
    $noteHist = New-Object System.Collections.ArrayList
    $lastS    = $null
    $lastForce = 0
    $lastOut   = $null
    $lostCount = 0
    $lastReacq = -10.0
    $lastAliveCheck = 0.0
    # web panel state
    $evList   = New-Object System.Collections.ArrayList   # @{Id; T; X} newest last, last 60
    $script:evId = 0
    $nextPub  = 0.0
    $nextMeta = 0.0
    $nextTuneCheck = 0.0
    $pubSeq   = 0
    $audioOpt = $null; $audioOptSaved = $null; $nextAudio = 0.0
    $prevSurf = $null; $prevRun = $null; $prevAir = $null
    $lastFlameEv = -10.0
    $recentSides = @{}   # side index -> time last seen in $s.Hits
    $lastTuneChange = @()
    function Add-Ev([double]$T, [string]$X) {
        $script:evId++
        $null = $evList.Add([pscustomobject]@{ Id = $script:evId; T = $T; X = $X })
        while ($evList.Count -gt 60) { $evList.RemoveAt(0) }
    }

    if ($canDraw) { Clear-Host }

    while ($true) {
        $frameStart = $sw.Elapsed.TotalSeconds
        if ($Seconds -gt 0 -and $frameStart -gt $Seconds) { break }

        # EXIT WHEN THE GAME DOES. Checked once a second, not per frame.
        #
        # This loop holds an EXCLUSIVE DirectInput acquisition. Left running after
        # the game closes it keeps holding the wheel, and because the 1997 engine
        # acquires FFB once at startup and never retries, the NEXT launch of the
        # game silently gets no force feedback at all - for the whole session, with
        # nothing to indicate why. Field-hit 2026-08-04 exactly this way.
        if (($frameStart - $lastAliveCheck) -ge 1.0) {
            $lastAliveCheck = $frameStart
            if ($telCtx.Proc.HasExited) {
                Write-Host "`nthe game exited - releasing the wheel so the next launch can claim it." -ForegroundColor Cyan
                break
            }
        }

        $s = Tel-Sample $telCtx
        if ($s) {
            $lastS = $s
            $out = Mix-Update $mix $s $active

            # Gating is applied INSIDE Mix-Update (it takes $active), so .Force is
            # already masked, slew-limited, ramped, master-scaled and clamped.
            # Re-summing the breakdown here is what bypassed the slew limiter.
            #
            # Mix-RenderWheel then applies the BELT-DRIVE compensation (MinForce),
            # which is device-specific and deliberately not in the shared path.
            $force = Mix-RenderWheel $out $tuneTable

            if (-not $DryRun) {
                $hr = Ffb-Constant $dev $force
                if ($hr -lt 0) {
                    # Device taken from us (alt-tab, the game reacquiring, the
                    # Thrustmaster panel opening). Recover rather than die - and
                    # rate-limit the attempts so a permanently-lost device does
                    # not spin the loop.
                    $lostCount++
                    if (($frameStart - $lastReacq) -gt 1.0) {
                        $lastReacq = $frameStart
                        if (Ffb-Reacquire $dev) {
                            $null = $noteHist.Insert(0, ("{0,7:0.0}s  device recovered" -f $frameStart))
                            Add-Ev $frameStart 'device recovered'
                        } else {
                            $null = $noteHist.Insert(0, ("{0,7:0.0}s  DEVICE LOST hr=0x{1:X8}" -f $frameStart, $hr))
                            Add-Ev $frameStart ("DEVICE LOST hr=0x{0:X8}" -f $hr)
                        }
                    }
                } else { $lostCount = 0 }
            }

            # Events for the web panel's log: the mixer's notes, made specific where the
            # sample says more (which gun, which side, which gear), plus state edges the
            # mixer does not announce (surface, engine stop, take-off, the flamer).
            foreach ($h in @($s.Hits)) { if ($h) { $recentSides[[int]$h.Side] = $frameStart } }
            foreach ($nt in $out.Notes) {
                $x = [string]$nt
                if ($x -eq 'FIRE' -and $s.Shots -and $s.Shots.Count) {
                    $g = @($s.Shots | Where-Object { $_.Klass -eq 2 } | Sort-Object Damage -Descending)
                    if ($g.Count) { $x = "FIRE gun/cannon (dmg $($g[0].Damage))" }
                } elseif ($x -eq 'HIT') {
                    $sd = @($recentSides.Keys | Where-Object { ($_ -eq 0 -or $_ -eq 3) -and ($frameStart - $recentSides[$_]) -lt 0.5 } | ForEach-Object { $SIDE_NAMES[$_] })
                    $x = $(if ($sd.Count) { "HIT " + ($sd -join '/') } else { 'HIT front/back' })
                } elseif ($x -eq 'UPSHIFT' -or $x -eq 'DOWNSHIFT') {
                    if ($null -ne $s.Gear -and $GEAR_NAMES.ContainsKey([int]$s.Gear)) { $x = "$x -> gear $($GEAR_NAMES[[int]$s.Gear])" }
                }
                $null = $noteHist.Insert(0, ("{0,7:0.0}s  {1}" -f $frameStart, $x))
                Add-Ev $frameStart $x
            }
            if ($s.Shots -and @($s.Shots | Where-Object { $_.Klass -eq 5 }).Count -and ($frameStart - $lastFlameEv) -gt 0.5) {
                $lastFlameEv = $frameStart; Add-Ev $frameStart 'FIRE flamer'
            }
            if ($null -ne $s.Surface) {
                if ($null -ne $prevSurf -and [int]$s.Surface -ne $prevSurf) {
                    Add-Ev $frameStart ("SURFACE {0} -> {1} ({2})" -f $prevSurf, [int]$s.Surface, $(if ($s.Paved) { 'paved' } else { 'off-road' }))
                }
                $prevSurf = [int]$s.Surface
            }
            if ($null -ne $s.EngineRunning) {
                if ($null -ne $prevRun -and $prevRun -and -not $s.EngineRunning) { Add-Ev $frameStart 'ENGINE stopped' }
                $prevRun = [bool]$s.EngineRunning
            }
            if ($null -ne $s.AirFlag) {
                if ($null -ne $prevAir -and -not $prevAir -and $s.AirFlag) { Add-Ev $frameStart 'AIRBORNE' }
                $prevAir = [bool]$s.AirFlag
            }
            while ($noteHist.Count -gt 6) { $noteHist.RemoveAt($noteHist.Count - 1) }

            if ($logSw) {
                # Built by joining a list rather than with a 21-slot -f format
                # string: the format-string version silently mismatched its
                # argument count and threw at runtime, and counting placeholders
                # by eye is not a thing worth doing twice.
                $cols = @(
                    ('{0:0.000}' -f $frameStart), ('{0:0.000}' -f $s.Speed), ('{0:0.0}' -f $s.SpeedMph),
                    ('{0:0.000}' -f $s.Steer),    ('{0:0.000}' -f $s.Throttle),
                    ('{0:0.000}' -f $s.LongG),    ('{0:0.000}' -f $s.LatG),
                    ('{0:0.000}' -f $s.YawRate),  ('{0:0.000}' -f $s.ExpectedYaw),
                    ('{0:0.000}' -f $s.Understeer), ('{0:0.000}' -f $s.Oversteer),
                    ('{0:0.000}' -f $s.Jolt),
                    ('{0:0.000}' -f $s.AngVelX), ('{0:0.000}' -f $s.AngVelZ), ('{0:0.000}' -f $s.Vy),
                    # These four MUST stay in the same order as $logCols. The header
                    # gained heave/slide/headingRate without this row gaining the
                    # values, which silently shifted every later column by three -
                    # the same desync that once made 'force' read as 'impact'.
                    ('{0:0.000}' -f $s.HeaveAccel),
                    ('{0:0.000}' -f $s.Slide), ('{0:0.000}' -f $s.HeadingRate),
                    ([string][int]$s.Rpm), ('{0:0}' -f $s.RpmRate), ([string][int]$s.Shift),
                    ([string][int]$s.FireRaw),
                    ([string][int]$s.FxActive),
                    # Semicolon-joined, NO quotes and NO spaces: a quoted field with
                    # spaces made the CSV ambiguous enough that a strict reader
                    # merged rows (2861 parsed from 7324 written). A log that
                    # cannot be re-read is not a log.
                    $(if ($s.FxFired -and $s.FxFired.Count) { (($s.FxFired | ForEach-Object { "id$($_.Id)m$($_.Mag)" }) -join ';') } else { '' }),
                    ([string][int64]$s.Flags), ([string][int]$s.Surface), ([string][int][bool]$s.Paved),
                    ([string][int]$out.Channels['surf%']), ([string][int]$s.Gear),
                    ('{0:0.00000}' -f [double]$s.SteerK), ('{0:0.000}' -f [double]$s.LatCap), [string]$s.ShotSource,
                    $(if ($s.Shots -and $s.Shots.Count) { (($s.Shots | ForEach-Object { "c$($_.Klass)d$($_.Damage)x$($_.Rounds)" }) -join ';') } else { '' }),
                    $(if ($s.Hits -and $s.Hits.Count) { (($s.Hits | ForEach-Object { "s$($_.Side)h$($_.Hp)" }) -join ';') } else { '' }),
                    ([string][int]$s.WeaponRow), ([string]$s.GameFfb)
                )
                foreach ($c in $ALL_CH) { $cols += [string][int]$out.Channels[$c] }
                $cols += [string]$force
                # Header and row have drifted apart three times now, and every time
                # it was silent: the CSV still parsed, the columns were just wrong,
                # and 'force' was read as 'impact' for a whole analysis session.
                # Checked once, on the first row, so it costs nothing per frame.
                if (-not $script:logColsChecked) {
                    $script:logColsChecked = $true
                    if ($cols.Count -ne $logCols.Count) {
                        Write-Host ("LOG COLUMN MISMATCH: header has {0}, row writes {1}. Fix before trusting this log." -f `
                            $logCols.Count, $cols.Count) -ForegroundColor Red
                    }
                }
                $logSw.WriteLine($cols -join ',')
            }
            $lastForce = $force
            $lastOut = $out
        }

        $loops++
        if (($frameStart - $lastSec) -ge 1.0) {
            $rateNow = ($loops - $loopsAtSec) / ($frameStart - $lastSec)
            $lastSec = $frameStart; $loopsAtSec = $loops
        }

        # ---- live tune file (web panel sliders, a hand edit) -----------------
        if ($frameStart -ge $nextTuneCheck) {
            $nextTuneCheck = $frameStart + 0.5
            $st = [IO.File]::GetLastWriteTimeUtc($ownerTune)
            if ($st -ne $tuneStamp) {
                $tuneStamp = $st
                try {
                    $chg = Tune-Reload
                    $lastTuneChange = $chg
                    if ($chg.Count) {
                        foreach ($c in $chg) { Add-Ev $frameStart ("tune: " + $c) }
                        $null = $noteHist.Insert(0, ("{0,7:0.0}s  tune reloaded: {1}" -f $frameStart, ($chg -join ', ')))
                        Write-IntLog ("tune reloaded from {0}: {1}" -f $ownerTune, ($chg -join ', '))
                    } else {
                        Write-IntLog ("tune file touched, no value changed ({0})" -f $ownerTune)
                    }
                    $nextMeta = 0.0
                } catch {
                    Add-Ev $frameStart "tune file unreadable - kept the old values"
                    Write-IntLog ("tune file unreadable, old values kept: {0}" -f $_)
                }
            }
        }

        # ---- web panel: commands in, state out --------------------------------
        while ($ctlUdp -and $ctlUdp.Available -gt 0) {
            try {
                $ep = New-Object System.Net.IPEndPoint ([System.Net.IPAddress]::Any, 0)
                $cb = $ctlUdp.Receive([ref]$ep)
                $cmd = [Text.Encoding]::UTF8.GetString($cb) | ConvertFrom-Json
                $what = ''
                switch ([string]$cmd.op) {
                    'gate' {
                        $chn = [string]$cmd.ch; $md = [string]$cmd.mode
                        if ($md -eq 'all') { foreach ($c in $ALL_CH) { $active[$c] = $true }; $what = 'all channels on' }
                        elseif ($ALL_CH -contains $chn) {
                            if ($md -eq 'solo') { foreach ($c in $ALL_CH) { $active[$c] = ($c -eq $chn) }; $what = "solo $chn" }
                            elseif ($md -eq 'mute') { $active[$chn] = $false; $what = "mute $chn" }
                            elseif ($md -eq 'on') { $active[$chn] = $true; $what = "unmute $chn" }
                        }
                    }
                    'arm' {
                        $mix.Enabled = [bool]$cmd.on
                        if (-not $DryRun -and -not $mix.Enabled) { $null = Ffb-Constant $dev 0 }
                        $what = $(if ($mix.Enabled) { 'armed' } else { 'muted (all force off)' })
                    }
                }
                if ($what) {
                    Add-Ev $frameStart ("panel: " + $what)
                    $null = $noteHist.Insert(0, ("{0,7:0.0}s  panel: {1}" -f $frameStart, $what))
                    Write-IntLog ("panel command: {0}" -f $what)
                    $nextPub = 0.0
                }
            } catch { }
        }
        if ($pubUdp -and $frameStart -ge $nextPub) {
            $nextPub = $frameStart + 0.05
            $pubSeq++
            # game audio options, read-only (0x654b90 music / sfx / voice / channels; +0x60 the saved copy)
            if ($frameStart -ge $nextAudio) {
                $nextAudio = $frameStart + 1.0
                $audioOpt = Tel-ReadBuf $telCtx 0x654b90 4
                $audioOptSaved = Tel-ReadBuf $telCtx 0x654bf0 4
            }
            $sb = New-Object System.Text.StringBuilder 4096
            $null = $sb.Append('{"k":"ffb","v":1,"seq":').Append($pubSeq).Append(',"t":').Append((Jn $frameStart))
            $null = $sb.Append(',"pid":').Append($PID).Append(',"game_pid":').Append($telCtx.Proc.Id)
            $null = $sb.Append(',"mode":').Append((Js $(if ($DryRun) { 'DRY RUN (wheel untouched)' } else { "LIVE $($dev.Name)" })))
            $null = $sb.Append(',"dry":').Append((Jb $DryRun)).Append(',"armed":').Append((Jb $mix.Enabled))
            $null = $sb.Append(',"master":').Append((Jn ([double]$tuneTable['Master']))).Append(',"rate":').Append((Jn $rateNow))
            $null = $sb.Append(',"ctl":').Append((Jb ([bool]$ctlUdp))).Append(',"lost":').Append($lostCount)
            $null = $sb.Append(',"game_ffb":').Append((Jn ([double]$(if ($lastS) { $lastS.GameFfb } else { 0 })))).Append(',"calib":').Append((Js ([string]$script:TEL_CALIB_SOURCE)))
            if ($lastS) {
                $q = $lastS
                $null = $sb.Append(',"tel":{"speed":').Append((Jn $q.Speed)).Append(',"mph":').Append((Jn $q.SpeedMph))
                $null = $sb.Append(',"steer":').Append((Jn $q.Steer)).Append(',"throttle":').Append((Jn $q.Throttle))
                $null = $sb.Append(',"yaw":').Append((Jn $q.YawRate)).Append(',"yaw_expect":').Append((Jn $q.ExpectedYaw))
                $null = $sb.Append(',"under":').Append((Jn $q.Understeer)).Append(',"over":').Append((Jn $q.Oversteer))
                $null = $sb.Append(',"slide":').Append((Jn ([double]$q.Slide))).Append(',"lat_g":').Append((Jn $q.LatG)).Append(',"long_g":').Append((Jn $q.LongG))
                $null = $sb.Append(',"jolt":').Append((Jn $q.Jolt)).Append(',"vy":').Append((Jn $q.Vy))
                $null = $sb.Append(',"surface":').Append($(if ($null -ne $q.Surface) { [int]$q.Surface } else { 'null' }))
                $null = $sb.Append(',"paved":').Append((Jb $q.Paved)).Append(',"surf_pct":').Append((Jn ([double]$(if ($lastOut) { $lastOut.Channels['surf%'] } else { 100 }))))
                $null = $sb.Append(',"grip_pct":').Append((Jn ([double]$(if ($lastOut) { $lastOut.Channels['grip%'] } else { 100 }))))
                $null = $sb.Append(',"air":').Append((Jb $q.AirFlag)).Append(',"engine":').Append((Jb $q.EngineRunning)).Append(',"starting":').Append((Jb $q.EngineStarting))
                $null = $sb.Append(',"drift":').Append((Jb $q.DriftFlag)).Append(',"skid":').Append((Jb $q.SkidFlag)).Append(',"braking":').Append((Jb $q.Braking))
                $null = $sb.Append(',"gear":').Append($(if ($null -ne $q.Gear) { [int]$q.Gear } else { 'null' }))
                $null = $sb.Append(',"rpm":').Append((Jn ([double]$q.Rpm))).Append(',"since_tick":').Append((Jn ([double]$q.SinceTick)))
                $null = $sb.Append(',"shot_src":').Append((Js ([string]$q.ShotSource))).Append(',"row":').Append($(if ($null -ne $q.WeaponRow) { [int]$q.WeaponRow } else { 'null' }))
                $null = $sb.Append(',"ammo":[')
                $first = $true
                foreach ($w in @($q.Ammo)) {
                    if (-not $w) { continue }
                    if (-not $first) { $null = $sb.Append(',') }; $first = $false
                    $null = $sb.Append('{"i":').Append([int]$w.Idx).Append(',"n":').Append([int64]$w.Ammo).Append(',"c":').Append([int]$w.Klass).Append(',"d":').Append([int]$w.Damage).Append('}')
                }
                $null = $sb.Append(']}')
            }
            if ($lastOut) {
                $null = $sb.Append(',"ch":{')
                $first = $true
                foreach ($c in $ALL_CH) {
                    if (-not $first) { $null = $sb.Append(',') }; $first = $false
                    $null = $sb.Append('"').Append($c).Append('":').Append([int]$lastOut.Channels[$c])
                }
                $null = $sb.Append('},"force":').Append([int]$lastForce).Append(',"model_force":').Append([int]$lastOut.Force).Append(',"peak":').Append((Jn $mix.PeakForce))
                $L = $lastOut.Bus.Lfe
                $null = $sb.Append(',"lfe":{"engine":').Append((Jn ([double]$L.EngineAmp))).Append(',"engine_hz":').Append((Jn ([double]$L.EngineFreq)))
                $null = $sb.Append(',"road":').Append((Jn ([double]$L.RoadAmp))).Append(',"road_hz":').Append((Jn ([double]$L.RoadFreq)))
                $null = $sb.Append(',"impulse":').Append((Jn ([double]$L.ImpulseAmp))).Append(',"impulse_hz":').Append((Jn ([double]$L.ImpulseFreq)))
                $null = $sb.Append(',"heave":').Append((Jn ([double]$L.HeaveAmp))).Append(',"heave_hz":').Append((Jn ([double]$L.CarrierFreq)))
                $null = $sb.Append(',"weapon":').Append((Jn ([double]$L.WeaponAmp))).Append(',"weapon_hz":').Append((Jn ([double]$L.WeaponFreq)))
                $null = $sb.Append(',"scrub":').Append((Jn ([double]$L.ScrubAmp))).Append(',"explode":').Append((Jn ([double]$L.ExplodeAmp))).Append('}')
            }
            $null = $sb.Append(',"act":{')
            $first = $true
            foreach ($c in $ALL_CH) {
                if (-not $first) { $null = $sb.Append(',') }; $first = $false
                $null = $sb.Append('"').Append($c).Append('":').Append((Jb $active[$c]))
            }
            $null = $sb.Append('}')
            if ($audioOpt) {
                $null = $sb.Append(',"audio":{"music":').Append([int]$audioOpt[0]).Append(',"sfx":').Append([int]$audioOpt[1]).Append(',"voice":').Append([int]$audioOpt[2]).Append(',"channels":').Append([int]$audioOpt[3])
                if ($audioOptSaved) { $null = $sb.Append(',"saved":[').Append((([int[]]$audioOptSaved) -join ',')).Append(']') }
                $null = $sb.Append('}')
            }
            $null = $sb.Append(',"ev_last":').Append($script:evId).Append(',"ev":[')
            $first = $true
            $from = [math]::Max(0, $evList.Count - 25)
            for ($i = $from; $i -lt $evList.Count; $i++) {
                $e = $evList[$i]
                if (-not $first) { $null = $sb.Append(',') }; $first = $false
                $null = $sb.Append('[').Append($e.Id).Append(',').Append((Jn $e.T)).Append(',').Append((Js $e.X)).Append(']')
            }
            $null = $sb.Append(']}')
            try { $bytes = [Text.Encoding]::UTF8.GetBytes($sb.ToString()); $null = $pubUdp.Send($bytes, $bytes.Length, '127.0.0.1', $PanelPort) } catch { }

            if ($frameStart -ge $nextMeta) {
                $nextMeta = $frameStart + 1.0
                $mb = New-Object System.Text.StringBuilder 8192
                $null = $mb.Append('{"k":"meta","v":1,"pid":').Append($PID).Append(',"t":').Append((Jn $frameStart))
                $null = $mb.Append(',"tune_file":').Append((Js $ownerFull)).Append(',"tune_explicit":').Append((Js $explicitTune))
                $null = $mb.Append(',"tune_stamp":').Append((Js ($tuneStamp.ToString('o'))))
                $null = $mb.Append(',"channels":[').Append((($ALL_CH | ForEach-Object { '"' + $_ + '"' }) -join ',')).Append(']')
                foreach ($pair in @(@('tune', $tuneTable), @('defaults', $defaultTune))) {
                    $null = $mb.Append(',"').Append($pair[0]).Append('":{')
                    $first = $true
                    foreach ($k in ($pair[1].Keys | Sort-Object)) {
                        $v = $pair[1][$k]
                        if ($v -is [array] -or $null -eq $v) { continue }
                        if (-not $first) { $null = $mb.Append(',') }; $first = $false
                        $null = $mb.Append('"').Append($k).Append('":').Append((Jn ([double]$v)))
                    }
                    $null = $mb.Append('}')
                }
                $null = $mb.Append(',"last_change":[').Append((($lastTuneChange | ForEach-Object { Js $_ }) -join ',')).Append(']}')
                try { $bytes = [Text.Encoding]::UTF8.GetBytes($mb.ToString()); $null = $pubUdp.Send($bytes, $bytes.Length, '127.0.0.1', $PanelPort) } catch { }
            }
        }

        # ---- panel ---------------------------------------------------------
        if ($canDraw -and $frameStart -ge $nextDraw) {
            $nextDraw = $frameStart + 0.07     # ~14 Hz; the force loop runs far faster
            [Console]::SetCursorPosition(0, 0)
            $mode = if ($DryRun) { "DRY RUN (wheel untouched)" } else { "LIVE -> $($dev.Name)" }
            foreach ($ln in (Build-Panel -Mode $mode -Ent $telCtx.Ent -Wheelbase $telCtx.Wheelbase `
                        -S $lastS -Out $lastOut -Force $lastForce -Peak $mix.PeakForce `
                        -Rate $rateNow -Master $tuneTable['Master'] -Enabled $mix.Enabled `
                        -Active $active -Notes $noteHist -Calib $script:TEL_CALIB_SOURCE)) {
                Write-Host $ln.PadRight(78)
            }
        }

        # ---- live keys -----------------------------------------------------
        # Probed once, not per frame: [Console]::KeyAvailable throws outright
        # when stdin is redirected (piped, or run from a harness rather than a
        # terminal), and a throw here would take down a loop that is holding the
        # wheel. No console just means no hotkeys.
        while ($canKeys -and [Console]::KeyAvailable) {
            $k = [Console]::ReadKey($true)
            switch ($k.KeyChar) {
                ' ' { $mix.Enabled = -not $mix.Enabled; if (-not $DryRun -and -not $mix.Enabled) { $null = Ffb-Constant $dev 0 }; Add-Ev $frameStart $(if ($mix.Enabled) { 'console: armed' } else { 'console: muted' }) }
                '+' { $tuneTable['Master'] = [math]::Min(1.5, $tuneTable['Master'] + 0.05) }
                '=' { $tuneTable['Master'] = [math]::Min(1.5, $tuneTable['Master'] + 0.05) }
                '-' { $tuneTable['Master'] = [math]::Max(0.0, $tuneTable['Master'] - 0.05) }
                's' {
                    # only what differs from the defaults (see ffb-tune-owner.json above)
                    $p = Join-Path $here 'ffb-tune-owner.json'
                    $def = Mix-DefaultTune; $diff = [ordered]@{}
                    foreach ($k in ($tuneTable.Keys | Sort-Object)) {
                        $a = $tuneTable[$k]; $b = $def[$k]
                        if ($a -is [array] -or $b -is [array]) { continue }
                        if ($null -eq $b -or [math]::Abs([double]$a - [double]$b) -gt 1e-9) { $diff[$k] = [math]::Round([double]$a, 4) }
                    }
                    ([pscustomobject]$diff | ConvertTo-Json) | Set-Content -Path $p -Encoding ASCII
                    $null = $noteHist.Insert(0, ("        saved {0} changed value(s) -> ffb-tune-owner.json" -f $diff.Count))
                    Write-IntLog ("[s] saved {0} changed value(s) -> {1}" -f $diff.Count, $p)
                }
                'q' { throw [OperationCanceledException]::new("quit") }
            }
        }

        $spent = $sw.Elapsed.TotalSeconds - $frameStart
        $rest  = $period - $spent
        if ($rest -gt 0.001) { Start-Sleep -Milliseconds ([int]($rest * 1000)) }
    }
}
catch [OperationCanceledException] {
    Write-Host "`nstopped." -ForegroundColor Cyan
}
finally {
    # A crash or Ctrl+C with a force applied leaves the wheel PULLING against
    # whoever is holding it. Release unconditionally, before anything else.
    # Put the engine's FFB flag back exactly as we found it. Best-effort: if the
    # game has already exited there is nothing to restore, and a stale 0 only means
    # no engine FFB until the next launch - not damage.
    if ($null -ne $engineFfbWas -and $telCtx) {
        try {
            $null = Tel-SetEngineFfb $telCtx $engineFfbWas
            Write-Host ("engine FFB restored (0x52bbd0 -> {0})" -f $engineFfbWas) -ForegroundColor Cyan
        } catch { }
    }
    if ($dev) {
        try { $null = Ffb-Constant $dev 0 } catch { }
        try { Ffb-Stop $dev } catch { }
        try { Ffb-Close $dev } catch { }
        Write-Host "wheel released." -ForegroundColor Cyan
    }
    if ($logSw) { $logSw.Flush(); $logSw.Close(); Write-Host "log -> $Log" -ForegroundColor Cyan }
    if ($pubUdp) {
        # one last datagram so the page shows "stopped" at once instead of timing out
        try { $bytes = [Text.Encoding]::UTF8.GetBytes(('{"k":"bye","pid":' + $PID + '}')); $null = $pubUdp.Send($bytes, $bytes.Length, '127.0.0.1', $PanelPort) } catch { }
        try { $pubUdp.Close() } catch { }
    }
    if ($ctlUdp) { try { $ctlUdp.Close() } catch { } }
    Write-IntLog ("stop pid {0}" -f $PID)
    if ($telCtx) { Tel-Close $telCtx }
}
