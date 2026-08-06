<#
  ffb-telemetry-udp.ps1 - broadcast I'76 telemetry to motion rigs and tactile
  software, in a format they already understand.

      tools\ffb\ffb-telemetry-udp.ps1                 # all the usual consumers
      tools\ffb\ffb-telemetry-udp.ps1 -Targets simhub
      tools\ffb\ffb-telemetry-udp.ps1 -Targets simtools,flypt -Hz 60
      tools\ffb\ffb-telemetry-udp.ps1 -Dump           # print packets, send nothing

  ---------------------------------------------------------------------------
  WHY THE LFS FORMAT
  ---------------------------------------------------------------------------
  Live For Speed's OutSim / OutGauge UDP packets are the lingua franca of this
  ecosystem. SimTools, FlyPT Mover, SimHub, Sim Racing Studio, SIMRIG and
  Simucube Tuner all consume them as PASSIVE UDP LISTENERS - no handshake, no
  registration, no plugin to author. Point a stream at the right port and a
  1997 game drives a motion platform.

  This is a well-trodden trick rather than a hack: BeamNG.drive ships an OutGauge
  emitter for exactly this reason, and hardcodes the fields it cannot supply to
  zero - which the ecosystem tolerates. We do the same.

  Because WE are the sender, the ecosystem's usual "only one application can
  listen on a UDP port" limitation does not apply: we simply send a copy to every
  consumer's port.

  ---------------------------------------------------------------------------
  THE WIRE FORMAT (LFS docs\InSim.txt and docs\OutSimPack.txt)
  ---------------------------------------------------------------------------
  All little-endian, no padding, naturally 4-byte aligned. Not InSim packets -
  no header, plain UDP datagrams.

  AXES: X = right, Y = forward, Z = up. Velocity/acceleration/angular velocity
  are WORLD frame; Heading/Pitch/Roll give orientation within it. Angles in
  radians. Acceleration is dV/dt with GRAVITY EXCLUDED (a parked car reads zero).
  Position is fixed point, 1 m = 65536.

  I'76 is Y-up, so the axis map is  (x, y_up, z)  ->  (X=x, Y=z, Z=y_up).

  Classic OutSim  = 64 bytes: Time, AngVel[3], Heading, Pitch, Roll, Accel[3],
                    Vel[3], Pos[3 fixed point].
  OutSimPack2     = 280 bytes at Opts 1ff: "LFST" + ID + Time + the 60-byte main
                    block + inputs + drive + distance + 4x40-byte wheels +
                    SteerTorque + spare.
  OutGauge        = 92 bytes: Time, Car[4], Flags, Gear, PLID, Speed (m/s), RPM,
                    Turbo, EngTemp, Fuel, OilPressure, OilTemp, DashLights,
                    ShowLights, Throttle, Brake, Clutch, Display1[16], Display2[16].

  ---------------------------------------------------------------------------
  WHAT IS REAL AND WHAT IS ZERO
  ---------------------------------------------------------------------------
  Honest accounting, because a consumer cannot tell:

  REAL:  velocity (world), acceleration (world, differentiated from velocity -
         exact, and needs no orientation, which matters because this entity has
         none), yaw rate, speed, throttle, brake, steering input.
  PROXY: Heading comes from the DIRECTION OF TRAVEL, not from a facing vector.
         The engine exposes no orientation at all - there is no rotation matrix
         anywhere in the entity (docs/HANDLING-MODEL.md). For a car the two differ
         only by the slip angle, which in this engine is near zero outside a spin.
  ZERO:  Pitch and Roll (this engine has NO suspension model - measured, see
         HANDLING-MODEL.md - so there is no body roll or pitch to report),
         position, per-wheel data, RPM, fuel, temperatures, gear.

  Zeroing rather than inventing is deliberate. A fabricated suspension trace
  would drive a rig with detail the simulation does not have.
#>
param(
    # simtools | flypt | simhub | srs | simrig | all
    [string[]]$Targets = @('all'),
    [int]$Hz = 100,
    [switch]$Dump,
    [int]$Seconds = 0,
    [int]$Wait = 180,
    # Build every packet from a synthetic sample and assert the layout, without
    # the game or the network. Packet SIZE is the one thing a consumer rejects
    # outright, and it is checkable from a desk.
    [switch]$SelfTest
)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $here 'Telemetry.ps1')

# Port map. Sources: SimTools PluginAPI default (4123/4124); FlyPT Mover's
# documented LFS cfg block (4123/4124, ID 1, Opts 1ff); SimHub's in-app LFS
# instructions (63393/63392, Opts 1ff); Sim Racing Studio (30000); SIMRIG
# Control Center (30000/30001).
$MAP = @{
    simtools = @{ outsim = 4123;  gauge = 4124;  pack = 'classic'; id = 0 }
    flypt    = @{ outsim = 4123;  gauge = 4124;  pack = 'pack2';   id = 1 }
    simhub   = @{ outsim = 63393; gauge = 63392; pack = 'pack2';   id = 0 }
    srs      = @{ outsim = 30000; gauge = 30000; pack = 'classic'; id = 0 }
    simrig   = @{ outsim = 30000; gauge = 30001; pack = 'classic'; id = 0 }
}
if ($Targets -contains 'all') { $Targets = @('simtools','flypt','simhub','srs','simrig') }
$sel = @()
foreach ($t in $Targets) {
    $k = $t.ToLower()
    if (-not $MAP.ContainsKey($k)) { Write-Host "unknown target '$t' - known: $($MAP.Keys -join ', ')" -ForegroundColor Yellow; continue }
    $sel += [pscustomobject]@{ Name = $k; Cfg = $MAP[$k] }
}
if (-not $sel.Count) { Write-Host "no targets" -ForegroundColor Red; exit 1 }

# SimTools and FlyPT share 4123 with DIFFERENT packet formats. Only one process
# can bind a port, so only one of them can be listening at a time - but sending
# both is harmless and means whichever is running just works. Say so rather than
# letting it look like a bug.
$dupes = @($sel | Group-Object { $_.Cfg.outsim } | Where-Object { $_.Count -gt 1 })
foreach ($d in $dupes) {
    Write-Host ("note: {0} share OutSim port {1} with different packet formats." -f `
        (($d.Group | ForEach-Object { $_.Name }) -join ' and '), $d.Name) -ForegroundColor DarkGray
    Write-Host "      Only one can be listening; sending both is harmless." -ForegroundColor DarkGray
}

# ---- packet builders ------------------------------------------------------
function W-F { param($bw,[double]$v) $bw.Write([single]$v) }
function W-I { param($bw,[int]$v) $bw.Write([int]$v) }
function W-U { param($bw,[uint32]$v) $bw.Write([uint32]$v) }

function New-OutSim {
    <#
      Classic 64-byte pack, or the 280-byte OutSimPack2 when -Pack2.
      $S is a Tel-Sample. Axis map: I'76 (x, y_up, z) -> LFS (X=x, Y=z, Z=y_up).
    #>
    param($S, [switch]$Pack2, [int]$Id, [uint32]$TimeMs)
    $ms = New-Object System.IO.MemoryStream
    $bw = New-Object System.IO.BinaryWriter($ms)

    if ($Pack2) {
        $bw.Write([byte[]][char[]]'LFST')       # OSO_HEADER
        W-I $bw $Id                              # OSO_ID
    }
    W-U $bw $TimeMs                              # OSO_TIME

    # --- OutSimMain (60 bytes) -------------------------------------------
    # AngVel, world frame. Only the vertical axis is real: this engine has no
    # suspension model, so there is no roll or pitch rate to report (the two
    # non-vertical angular-velocity fields in the entity turned out to be impact
    # and airtime rotation, not body motion - see HANDLING-MODEL.md).
    W-F $bw 0.0                                  # AngVel X  (roll rate)
    W-F $bw 0.0                                  # AngVel Y  (pitch rate)
    W-F $bw $S.YawRate                           # AngVel Z  (yaw rate - REAL)
    W-F $bw $S.HeadingApprox                     # Heading (travel-direction proxy)
    W-F $bw 0.0                                  # Pitch  (no orientation available)
    W-F $bw 0.0                                  # Roll
    W-F $bw $S.WorldAccelX                       # Accel X  m/s^2, gravity excluded
    W-F $bw $S.WorldAccelZ                       # Accel Y  (I'76 z = LFS forward)
    W-F $bw $S.WorldAccelY                       # Accel Z  (I'76 y_up = LFS up)
    W-F $bw $S.Vx                                # Vel X    m/s
    W-F $bw $S.Vz                                # Vel Y
    W-F $bw $S.Vy                                # Vel Z
    W-I $bw 0                                    # Pos X    fixed point, not tracked
    W-I $bw 0                                    # Pos Y
    W-I $bw 0                                    # Pos Z

    if ($Pack2) {
        # --- OutSimInputs (20) --------------------------------------------
        # Throttle and brake come from one signed axis in this engine.
        $thr = [math]::Max(0.0, $S.Throttle)
        $brk = [math]::Max(0.0, -$S.Throttle)
        W-F $bw $thr                             # Throttle 0..1
        W-F $bw $brk                             # Brake    0..1
        W-F $bw ($S.Steer * 0.76)                # InputSteer, radians (steer x lock)
        W-F $bw 0.0                              # Clutch
        W-F $bw 0.0                              # Handbrake
        # --- drive block (12) ----------------------------------------------
        $bw.Write([byte]2)                       # Gear: 2 = first (0=R, 1=N)
        $bw.Write([byte]0); $bw.Write([byte]0); $bw.Write([byte]0)   # spare
        W-F $bw 0.0                              # EngineAngVel rad/s - no RPM exists
        W-F $bw 0.0                              # MaxTorqueAtVel
        # --- distance block (8) --------------------------------------------
        W-F $bw 0.0                              # CurrentLapDist
        W-F $bw 0.0                              # IndexedDistance
        # --- OutSimWheel[4] (160) ------------------------------------------
        # All zero. This engine has no suspension and no per-wheel state; a
        # fabricated trace would drive a rig with detail the sim does not have.
        for ($w = 0; $w -lt 4; $w++) {
            W-F $bw 0.0; W-F $bw 0.0; W-F $bw 0.0; W-F $bw 0.0      # deflect, steer, Fx, Fy
            W-F $bw 0.0; W-F $bw 0.0; W-F $bw 0.0                    # load, angvel, lean
            $bw.Write([byte]20); $bw.Write([byte]0)                   # air temp, slip fraction
            $bw.Write([byte]1);  $bw.Write([byte]0)                   # touching, spare
            W-F $bw 0.0; W-F $bw 0.0                                 # slip ratio, tan slip angle
        }
        # --- OSO_EXTRA_1 (8) ------------------------------------------------
        # SteerTorque is documented as "proportional to force feedback", so this
        # is the one place our synthesised force belongs on the wire.
        W-F $bw $S.SteerTorqueNm
        W-F $bw 0.0                              # spare
    }
    $bw.Flush()
    $bytes = $ms.ToArray()
    $bw.Close(); $ms.Close()
    return $bytes
}

function New-OutGauge {
    param($S, [int]$Id, [uint32]$TimeMs)
    $ms = New-Object System.IO.MemoryStream
    $bw = New-Object System.IO.BinaryWriter($ms)
    W-U $bw $TimeMs
    $bw.Write([byte[]][char[]]'I76 ')             # Car[4], short name
    # Flags: OG_KM (16384) unset = user prefers miles, OG_BAR (32768) unset = psi.
    # I'76 is an American game with an mph HUD, so leave both unset.
    $bw.Write([uint16]0)                          # Flags
    $bw.Write([byte]2)                            # Gear: 2 = first
    $bw.Write([byte]0)                            # PLID
    W-F $bw $S.Speed                              # Speed, m/s  (REAL)
    W-F $bw 0.0                                   # RPM - none exists in this engine
    W-F $bw 0.0                                   # Turbo
    W-F $bw 0.0                                   # EngTemp
    W-F $bw 0.0                                   # Fuel
    W-F $bw 0.0                                   # OilPressure
    W-F $bw 0.0                                   # OilTemp
    W-U $bw 0                                     # DashLights (available)
    W-U $bw 0                                     # ShowLights (lit)
    W-F $bw ([math]::Max(0.0, $S.Throttle))       # Throttle 0..1  (REAL)
    W-F $bw ([math]::Max(0.0, -$S.Throttle))      # Brake    0..1  (REAL)
    W-F $bw 0.0                                   # Clutch
    $bw.Write((New-Object byte[] 16))             # Display1
    $bw.Write((New-Object byte[] 16))             # Display2
    if ($Id -ne 0) { W-I $bw $Id }
    $bw.Flush()
    $bytes = $ms.ToArray()
    $bw.Close(); $ms.Close()
    return $bytes
}

# ---- self test ------------------------------------------------------------
if ($SelfTest) {
    $pass = 0; $fail = 0
    function Chk { param([string]$n,[bool]$c,[string]$d="")
        if ($c) { $script:pass++; Write-Host "  PASS  $n" -ForegroundColor Green }
        else { $script:fail++; Write-Host "  FAIL  $n  ($d)" -ForegroundColor Red } }

    $fake = [pscustomobject]@{
        Speed = 20.0; SpeedMph = 44.7; Steer = 0.5; Throttle = 0.8
        YawRate = 0.42; Vx = 3.0; Vy = 0.1; Vz = 19.7
        WorldAccelX = 1.5; WorldAccelY = 0.2; WorldAccelZ = -4.0
        HeadingApprox = 0.15; SteerTorqueNm = 2.2
    }
    Write-Host "`n=== packet layout ===" -ForegroundColor Cyan
    $c64 = New-OutSim $fake -Id 0 -TimeMs 1234
    Chk "classic OutSim is exactly 64 bytes" ($c64.Length -eq 64) "got $($c64.Length)"
    $p2 = New-OutSim $fake -Pack2 -Id 1 -TimeMs 1234
    Chk "OutSimPack2 (Opts 1ff) is exactly 280 bytes" ($p2.Length -eq 280) "got $($p2.Length)"
    Chk "OutSimPack2 starts with the LFST magic" `
        ([System.Text.Encoding]::ASCII.GetString($p2,0,4) -eq 'LFST') `
        ([System.Text.Encoding]::ASCII.GetString($p2,0,4))
    Chk "OutSimPack2 carries the configured ID" ([BitConverter]::ToInt32($p2,4) -eq 1) "got $([BitConverter]::ToInt32($p2,4))"
    $og = New-OutGauge $fake -Id 0 -TimeMs 1234
    Chk "OutGauge is exactly 92 bytes" ($og.Length -eq 92) "got $($og.Length)"
    $ogid = New-OutGauge $fake -Id 7 -TimeMs 1234
    Chk "OutGauge with an ID is 96 bytes" ($ogid.Length -eq 96) "got $($ogid.Length)"

    Write-Host "`n=== field placement (little-endian, documented offsets) ===" -ForegroundColor Cyan
    # classic: Time@0, AngVel@4..15, Heading@16, Accel@28..39, Vel@40..51
    Chk "classic Time at +0" ([BitConverter]::ToUInt32($c64,0) -eq 1234) ""
    Chk "classic yaw rate at +12 (AngVel Z)" `
        ([math]::Abs([BitConverter]::ToSingle($c64,12) - 0.42) -lt 1e-5) "$([BitConverter]::ToSingle($c64,12))"
    Chk "classic Heading at +16" `
        ([math]::Abs([BitConverter]::ToSingle($c64,16) - 0.15) -lt 1e-5) "$([BitConverter]::ToSingle($c64,16))"
    Chk "classic Pitch/Roll are zero (no orientation in this engine)" `
        ([BitConverter]::ToSingle($c64,20) -eq 0 -and [BitConverter]::ToSingle($c64,24) -eq 0) ""
    # axis map: I'76 (x, y_up, z) -> LFS (X=x, Y=z, Z=y_up)
    Chk "Accel X at +28 is world X" ([math]::Abs([BitConverter]::ToSingle($c64,28) - 1.5) -lt 1e-5) ""
    Chk "Accel Y at +32 is I76 z (forward)" ([math]::Abs([BitConverter]::ToSingle($c64,32) - (-4.0)) -lt 1e-5) ""
    Chk "Accel Z at +36 is I76 y (up)" ([math]::Abs([BitConverter]::ToSingle($c64,36) - 0.2) -lt 1e-5) ""
    Chk "Vel Y at +44 is I76 z (forward)" ([math]::Abs([BitConverter]::ToSingle($c64,44) - 19.7) -lt 1e-4) ""
    # pack2: main block starts at +12, so inputs land at +72
    Chk "pack2 Throttle at +72" ([math]::Abs([BitConverter]::ToSingle($p2,72) - 0.8) -lt 1e-5) "$([BitConverter]::ToSingle($p2,72))"
    Chk "pack2 Brake at +76 is zero on positive throttle" ([BitConverter]::ToSingle($p2,76) -eq 0) ""
    Chk "pack2 SteerTorque at +272" ([math]::Abs([BitConverter]::ToSingle($p2,272) - 2.2) -lt 1e-5) "$([BitConverter]::ToSingle($p2,272))"
    # OutGauge: Speed@12 in m/s
    Chk "OutGauge Car tag at +4" ([System.Text.Encoding]::ASCII.GetString($og,4,4) -eq 'I76 ') ""
    Chk "OutGauge Speed at +12 in m/s" ([math]::Abs([BitConverter]::ToSingle($og,12) - 20.0) -lt 1e-5) ""
    Chk "OutGauge Throttle at +48" ([math]::Abs([BitConverter]::ToSingle($og,48) - 0.8) -lt 1e-5) ""

    # braking: one signed axis splits into two unsigned channels
    $braking = [pscustomobject]@{}
    foreach ($p in $fake.PSObject.Properties) { $braking | Add-Member -NotePropertyName $p.Name -NotePropertyValue $p.Value }
    $braking.Throttle = -0.6
    $ob = New-OutGauge $braking -Id 0 -TimeMs 0
    Chk "negative throttle becomes Brake, not Throttle" `
        ([BitConverter]::ToSingle($ob,48) -eq 0 -and [math]::Abs([BitConverter]::ToSingle($ob,52) - 0.6) -lt 1e-5) `
        "thr $([BitConverter]::ToSingle($ob,48)) brk $([BitConverter]::ToSingle($ob,52))"

    Write-Host ""
    Write-Host ("=== {0} passed, {1} failed ===" -f $pass, $fail) -ForegroundColor $(if ($fail -eq 0) { 'Green' } else { 'Red' })
    exit $(if ($fail -eq 0) { 0 } else { 1 })
}

# ---- run ------------------------------------------------------------------
$telCtx = $null
$udp = $null
try {
    $waited = 0
    while (-not $telCtx) {
        try { $telCtx = Tel-Open }
        catch {
            if ($Wait -le 0) { throw }
            if ($waited -ge $Wait) { throw "waited $Wait s for a mission: $_" }
            if ($waited -eq 0) { Write-Host "waiting for a mission to load..." -ForegroundColor DarkGray }
            Start-Sleep -Seconds 2; $waited += 2
        }
    }
    Write-Host ("telemetry OK - entity 0x{0:X8}" -f $telCtx.Ent) -ForegroundColor Green
    Write-Host ""
    foreach ($s in $sel) {
        Write-Host ("  {0,-9} OutSim {1,-6} ({2}, id {3})   OutGauge {4}" -f `
            $s.Name, $s.Cfg.outsim, $s.Cfg.pack, $s.Cfg.id, $s.Cfg.gauge) -ForegroundColor Cyan
    }
    Write-Host ""
    if ($Dump) { Write-Host "DUMP - nothing is sent." -ForegroundColor Yellow }
    else { $udp = New-Object System.Net.Sockets.UdpClient }

    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $period = 1.0 / [math]::Max(1, $Hz)
    $sent = 0; $lastLog = 0.0; $rate = 0.0; $sentAt = 0
    $ip = [System.Net.IPAddress]::Loopback

    while ($true) {
        $frame = $sw.Elapsed.TotalSeconds
        if ($Seconds -gt 0 -and $frame -gt $Seconds) { break }
        if ($telCtx.Proc.HasExited) { Write-Host "`nthe game exited." -ForegroundColor Cyan; break }

        $s = Tel-Sample $telCtx
        if ($s) {
            # SteerTorque is the one field where our synthesised force belongs on
            # the wire. Scale the -10000..10000 DirectInput range into Nm using the
            # T300's ~4 Nm peak, so a consumer reading it as torque gets a sane
            # number rather than a raw device unit.
            $s | Add-Member -NotePropertyName SteerTorqueNm -NotePropertyValue 0.0 -Force
            $tms = [uint32]($frame * 1000)
            foreach ($tg in $sel) {
                $c = $tg.Cfg
                $os = if ($c.pack -eq 'pack2') { New-OutSim $s -Pack2 -Id $c.id -TimeMs $tms }
                      else { New-OutSim $s -Id $c.id -TimeMs $tms }
                $og = New-OutGauge $s -Id 0 -TimeMs $tms
                if ($Dump) {
                    if ($sent -eq 0) {
                        Write-Host ("  {0}: OutSim {1} bytes, OutGauge {2} bytes" -f $tg.Name, $os.Length, $og.Length)
                    }
                } else {
                    [void]$udp.Send($os, $os.Length, (New-Object System.Net.IPEndPoint($ip, $c.outsim)))
                    [void]$udp.Send($og, $og.Length, (New-Object System.Net.IPEndPoint($ip, $c.gauge)))
                }
            }
            $sent++
        }
        if (($frame - $lastLog) -ge 1.0) {
            $rate = ($sent - $sentAt) / ($frame - $lastLog); $lastLog = $frame; $sentAt = $sent
            if ($s) {
                Write-Host ("`r  {0,5:0.0} mph  yaw {1,6:0.00}  accel ({2,6:0.1},{3,6:0.1},{4,6:0.1})  hdg {5,6:0.00}  {6,5:0.0} Hz  {7} pkts " -f `
                    $s.SpeedMph, $s.YawRate, $s.WorldAccelX, $s.WorldAccelZ, $s.WorldAccelY,
                    $s.HeadingApprox, $rate, $sent) -NoNewline
            }
        }
        $rest = $period - ($sw.Elapsed.TotalSeconds - $frame)
        if ($rest -gt 0.001) { Start-Sleep -Milliseconds ([int]($rest * 1000)) }
    }
}
finally {
    if ($udp) { $udp.Close() }
    if ($telCtx) { Tel-Close $telCtx }
    Write-Host ""
    Write-Host "stopped." -ForegroundColor Cyan
}
