<#
  Telemetry.ps1 - read the player vehicle's dynamics out of the live i76.exe.

  This is the INPUT half of the FFB interposer (FfbCore.ps1 is the output half).
  Dot-source it, call Tel-Open once, then Tel-Sample in your loop.

      . tools\ffb\Telemetry.ps1
      $t = Tel-Open
      while ($true) { $s = Tel-Sample $t; $s.LatG; $s.Understeer }

  ---------------------------------------------------------------------------
  WHAT IS CONFIRMED, AND HOW
  ---------------------------------------------------------------------------
  Offsets are from the player entity, [[[0x54a264]]+0x70]. Confidence is stated
  per field because two of them were WRONG in docs/MEMORY-MAP-INDEX.md and cost
  real time; see "the corrected map" below.

  +0x004..0x030  FOUR float3 = wheel contact points in LOCAL space.  CONFIRMED
        Parked they read (-0.99, 0.654, -2.37) (0.99, 0.654, -2.37)
        (0.99, 0.654, 2.29) (-0.99, 0.654, 2.29): x and z flip sign, y is
        constant. That is a rectangle in the xz plane at one ride height - four
        wheels, not a matrix. MEMORY-MAP-INDEX.md called +0x08 a "world
        transform (rotation matrix)" and marked it verified; it is not one.
        Somebody saw 0.654 sitting in a 0..1 range and read "matrix element",
        but it is a y coordinate. That error is WHY position was never found:
        the search was for something "adjacent to the matrix", and there is no
        matrix. An orthonormality scan across the whole first 0x200 bytes finds
        no rotation matrix anywhere in this struct.

  +0x0AC  float  speed = |velocity|                                  CONFIRMED
  +0x0BC  float3 velocity, world space (x, y, z)                     CONFIRMED
        Confirmed together by an exact numerical identity rather than by
        eyeballing plausible values. On a car left barely rolling:
            velocity = (0.5676, 0, 1.3592) -> |v| = 1.47296
            +0x0AC   =  1.473
        A stationary car cannot prove this (0 == 0) and a fast one is hard to
        sample coherently; a slowly-rolling one proves it in a single frame.
        docs/MEMORY-MAP-INDEX.md lists velocity as NOT FOUND ("RPM/gear/velocity:
        nothing anywhere"), so this closes that gap.
        +0x0C0 (the y term) stays ~0 on flat ground, which is exactly why the
        discovery probe saw velocity as "two moving floats with a dead one in
        the middle" instead of as a vector.

  +0x0C8  float3 angular velocity; YAW RATE is the middle term at +0x0CC  STRONG
        All three read ~0 parked and stay inside +/-2 while driving, and +0x0CC
        is the smoothest of the three (mean step 0.021 vs 0.082/0.031) - the
        signature of a car's yaw rate. Sign convention not yet pinned; see
        TEL_YAW_SIGN.

  +0x0D4  float3 acceleration / accumulated force                        LIKELY
        Same shape as velocity, noisier steps (0.33 vs 0.21), small but nonzero
        parked. Not relied on: longitudinal acceleration is differentiated from
        speed instead, which needs no assumption about units or sign.

  +0x0E0  float  steer applied, -1..1                                CONFIRMED
  +0x0E4  float  throttle applied, -1..1 (negative = brake/reverse)   CONFIRMED
        Both from disassembly (0x466e30 does fld [entity+0xe0]) and both agree
        with observed range and with a parked car reading steer ~0, throttle 0.

  Avoid +0x080..+0x08C: it is a LOOP TEMPORARY. Parked it holds a copy of the
  4th wheel vector, and while driving it sweeps the range of all four corners -
  it looks like juicy moving telemetry and means nothing.

  ---------------------------------------------------------------------------
  UNITS
  ---------------------------------------------------------------------------
  Metres and m/s. The wheel corners give a wheelbase of 4.66 and a track of
  1.98; as metres that is a large American car, which is what I'76 drives, and
  it makes the observed top speed 21.2 m/s = 47 mph, which matches the HUD's
  order of magnitude. Working in real units means the mixer can be tuned in g
  rather than in magic constants.

  ---------------------------------------------------------------------------
  WHY THIS IS TICK-AWARE (the thing that makes derivatives usable)
  ---------------------------------------------------------------------------
  I'76's sim is a FIXED 20 Hz timestep (Peelar; Roanish's world_tick) - physics
  advance in whole ticks and the renderer interpolates between them. So if you
  poll at 60 Hz and naively differentiate, two out of every three samples show
  zero change and the third shows the whole tick's delta: d(speed)/dt comes out
  as 0, 0, spike, 0, 0, spike. That is not noise you can filter, it is an
  artefact of sampling faster than the simulation.

  So: Tel-Sample polls fast (the FFB output wants a smooth high rate) but only
  recomputes derivatives when a sim value ACTUALLY CHANGED, dividing by the time
  since the previous change. Between ticks the derived values are HELD. That
  yields clean 20 Hz physics with a 60 Hz+ force update on top.
#>

# ---------------------------------------------------------------------------
# Tunables that encode an assumption rather than a measurement.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# THE HANDLING MODEL: I'76 COMMANDS LATERAL ACCELERATION, NOT STEERING ANGLE
# ---------------------------------------------------------------------------
# Measured from a real drive (959 samples, tools/ffb/ffb-calib-samples.csv), the
# relationship between steering input and yaw rate is:
#
#     yaw = a * steer / speed          R^2 = 0.9995, residual sd 0.013 rad/s
#
# and NOT the kinematic bicycle model (R^2 = 0.835) that this file used to
# assume. Multiply both sides by speed and the meaning is plain:
#
#     lateral acceleration = yaw * speed = a * steer
#
# Lateral g is directly proportional to steering input and INDEPENDENT OF SPEED.
# That is a 1997 arcade handling model - the engine treats the wheel as a lateral
# acceleration command - not a tyre model. It is why the cars feel go-kart-like.
#
# HOW THE OLD ASSUMPTION FAILED, because the failure was instructive: fitting a
# fixed steering lock to this data gives an answer that falls with speed (30 deg
# at 16 m/s, 4.7 deg at 40 m/s) because a constant-lock model cannot describe a
# constant-lateral-g car. The fit then lands wherever the drive spent its time.
# Two separate estimators both returned ~6 deg and both were blamed on the
# estimator before the data was plotted against speed.
#
# CONSEQUENCE FOR SLIP: the engine has no tyre slip model, so understeer and
# oversteer in the sim-racing sense do not occur in normal driving - the car does
# exactly what it is asked. What DOES happen is loss of control: spins, impacts
# and blown tyres, which show up as large DEVIATIONS from the relation above
# (40 of 783 samples deviated by >0.5 rad/s, all of them spins or hits). So the
# Understeer/Oversteer fields below are a loss-of-control signal, and that is
# more useful here than a tyre model would be.

# Lateral acceleration per unit steering input, m/s^2. 29.3 = 2.99 g at full
# lock, measured. This is the single parameter of the handling model.
$script:TEL_LAT_GAIN = 29.3

# Yaw rate ceiling, rad/s. a*steer/speed diverges as speed falls, but the engine
# clamps: the largest yaw rate ever observed is 2.95, and a/2.95 = 9.9 m/s, so
# below ~10 m/s the relation saturates rather than continuing to rise.
$script:TEL_YAW_MAX = 2.95

# +1 if a positive steer input produces a positive +0x0CC yaw rate. If the panel
# shows Yaw and Expect consistently opposite in sign, flip this.
$script:TEL_YAW_SIGN = 1

# Both values above are ASSUMPTIONS. ffb-calibrate.ps1 measures them from a short
# drive and writes ffb-calib.json; if that file exists it wins, because a
# measurement beats a plausible default. Delete the file to go back to these.
$script:TEL_CALIB_SOURCE = 'defaults (not calibrated - run ffb-calibrate.ps1)'
$script:__calib = Join-Path $PSScriptRoot 'ffb-calib.json'
if (Test-Path $script:__calib) {
    try {
        $c = Get-Content $script:__calib -Raw | ConvertFrom-Json
        if ($null -ne $c.TEL_YAW_SIGN) { $script:TEL_YAW_SIGN = [int]$c.TEL_YAW_SIGN }
        if ($null -ne $c.TEL_LAT_GAIN) { $script:TEL_LAT_GAIN = [double]$c.TEL_LAT_GAIN }
        if ($null -ne $c.TEL_YAW_MAX)  { $script:TEL_YAW_MAX  = [double]$c.TEL_YAW_MAX }
        # TEL_STEER_LOCK is deliberately NOT read. Calibration files written before
        # the handling model was measured carry one, and it described a kinematic
        # bicycle model this code no longer uses - honouring it would silently
        # reintroduce the assumption that was wrong.
        if ($null -ne $c.TEL_STEER_LOCK -and $null -eq $c.TEL_LAT_GAIN) {
            Write-Host "ffb-calib.json predates the handling-model fix - re-run ffb-calibrate.ps1" -ForegroundColor Yellow
        }
        $script:TEL_CALIB_SOURCE = ("calibrated from {0} ({1} samples, sign confidence {2:0}%)" -f `
            $c.Source, $c.Samples, ([double]$c.SignConfidence * 100))
    } catch {
        Write-Host "ffb-calib.json is unreadable, using defaults: $_" -ForegroundColor Yellow
    }
}

$script:TEL_OFF = @{
    Wheels   = 0x004   # 4 x float3, local space, CONSTANT per vehicle
    Speed    = 0x0AC
    Velocity = 0x0BC
    AngVel   = 0x0C8
    Accel    = 0x0D4
    Steer    = 0x0E0
    Throttle = 0x0E4
}
$script:TEL_BLOCK = 0x100   # one ReadProcessMemory covers every field above

if (-not ('I76Tel' -as [type])) {
    Add-Type @"
using System;
using System.Runtime.InteropServices;
public class I76Tel {
  [DllImport("kernel32.dll", SetLastError=true)]
  public static extern IntPtr OpenProcess(uint access, bool inherit, int pid);
  [DllImport("kernel32.dll", SetLastError=true)]
  public static extern bool ReadProcessMemory(IntPtr h, IntPtr addr, byte[] buf, int size, out int read);
  [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
}
"@
}

function Tel-Open {
    <#
      Resolves the process and the player entity. Returns a context object, or
      throws with a reason a human can act on. Safe to call repeatedly.
    #>
    $proc = Get-Process i76, nitro -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $proc) { throw "Interstate '76 is not running." }

    # PROCESS_VM_READ | PROCESS_QUERY_INFORMATION | PROCESS_VM_OPERATION
    $h = [I76Tel]::OpenProcess(0x38, $false, $proc.Id)
    if ($h -eq [IntPtr]::Zero) { throw "OpenProcess failed (run as the same user as the game)." }

    $ctx = [pscustomobject]@{
        Proc      = $proc
        H         = $h
        Ent       = 0
        Clock     = [System.Diagnostics.Stopwatch]::StartNew()
        Wheelbase = 0.0
        Track     = 0.0
        # tick-detection state (see the header note on fixed timestep)
        LastTickT     = 0.0
        LastTickSpeed = 0.0
        LastVx = 0.0; LastVy = 0.0; LastVz = 0.0
        Ticks     = 0
        Polls     = 0
        # derived values, HELD between sim ticks
        LongAccel = 0.0
        Jolt      = 0.0
        # First-change priming. Without this the first tick differentiates
        # against a zeroed baseline and emits a large bogus jolt - which the
        # mixer would happily deliver as a collision the moment you start it,
        # into hands resting on the wheel. Observed live: jolt 18.4 on a PARKED
        # car. Prime on the first change, derive from the second onward.
        Primed    = $false
        # Reused read buffer. Allocating a fresh byte[] per poll cost enough to
        # hold the loop to 38 Hz when 60 was requested.
        Buf       = (New-Object byte[] $script:TEL_BLOCK)
    }
    if (-not (Tel-Resolve $ctx)) { throw "Player entity is NULL - load a mission first." }
    Tel-Geometry $ctx
    return $ctx
}

function Tel-ReadInt {
    param($Ctx, [int64]$Addr)
    $b = New-Object byte[] 4
    $n = 0
    if ([I76Tel]::ReadProcessMemory($Ctx.H, [IntPtr]$Addr, $b, 4, [ref]$n) -and $n -eq 4) {
        return [BitConverter]::ToInt32($b, 0)
    }
    return 0
}

function Tel-Resolve {
    <#
      player entity = [[[0x54a264]] + 0x70]

      Re-resolve rather than cache across missions: the entity is a heap object
      in the engine's 2029-bucket entity store (Roanish), so its address is
      stable WITHIN a mission and changes on every load. The interposer calls
      this again whenever a sample looks wrong, which is how it survives the
      player restarting a mission without us noticing.
    #>
    param($Ctx)
    $world = Tel-ReadInt $Ctx 0x54a264
    if ($world -eq 0) { return $false }
    $sub = Tel-ReadInt $Ctx $world
    if ($sub -eq 0) { return $false }
    $ent = Tel-ReadInt $Ctx ($sub + 0x70)
    if ($ent -eq 0) { return $false }
    $Ctx.Ent = $ent
    return $true
}

function Tel-Geometry {
    <#
      Read the four wheel contact points once and derive wheelbase and track.
      These are LOCAL-space constants for the vehicle, so one read per mission is
      enough - and the wheelbase is what makes the bicycle-model slip estimate a
      real physical calculation instead of a fudge factor.
    #>
    param($Ctx)
    $b = New-Object byte[] 0x40
    $n = 0
    if (-not [I76Tel]::ReadProcessMemory($Ctx.H, [IntPtr]($Ctx.Ent), $b, 0x40, [ref]$n)) { return }
    $xs = @(); $zs = @()
    for ($i = 0; $i -lt 4; $i++) {
        $o = $script:TEL_OFF.Wheels + ($i * 12)
        $xs += [BitConverter]::ToSingle($b, $o)
        $zs += [BitConverter]::ToSingle($b, $o + 8)
    }
    $Ctx.Track     = [math]::Abs((($xs | Measure-Object -Maximum).Maximum) - (($xs | Measure-Object -Minimum).Minimum))
    $Ctx.Wheelbase = [math]::Abs((($zs | Measure-Object -Maximum).Maximum) - (($zs | Measure-Object -Minimum).Minimum))
    if ($Ctx.Wheelbase -lt 0.5) { $Ctx.Wheelbase = 4.66 }   # fall back to the measured stock value
}

function Tel-Slip {
    <#
      The reference model and the deviation from it, given nothing but speed,
      steer and yaw rate.

      Extracted from Tel-Sample so that ffb-replay.ps1 exercises THIS logic when
      it re-runs a captured drive, rather than a reimplementation of it that can
      quietly drift out of step with the live path.

      REFERENCE: yaw = a * steer / speed, measured at R^2 = 0.9997 on a real
      drive. Clamped, because the quotient diverges as speed falls while the
      engine does not.

      DEVIATION = loss of control. This engine has no tyre model, so ordinary
      cornering never deviates; spins, impacts and blown tyres do.

      Normalised against an ABSOLUTE rad/s scale, NOT against |expectedYaw|.
      Dividing by the expectation looks natural and is wrong here: the reference
      is accurate to a residual sd of 0.011 rad/s, so wherever expectedYaw is
      small a trivial absolute error becomes a huge ratio, and the wheel would
      report a spin every time you nudged it at speed. The deadband sits above
      the measured noise floor (worst residual on gripped samples: 0.053); real
      events deviate by more than 0.5.
    #>
    param([double]$Speed, [double]$Steer, [double]$YawRate)

    $DEV_DEAD = 0.15    # rad/s: below this it is measurement noise
    $DEV_REF  = 1.10    # rad/s: deviation treated as fully out of shape

    $expectedYaw = 0.0
    if ($Speed -gt 0.5) {
        $expectedYaw = $script:TEL_LAT_GAIN * $Steer / $Speed
        if ($expectedYaw -gt $script:TEL_YAW_MAX) { $expectedYaw = $script:TEL_YAW_MAX }
        elseif ($expectedYaw -lt -$script:TEL_YAW_MAX) { $expectedYaw = -$script:TEL_YAW_MAX }
    }

    $understeer = 0.0
    $oversteer  = 0.0
    if ($Speed -gt 3.0) {
        $aY = [math]::Abs($YawRate)
        $aE = [math]::Abs($expectedYaw)
        # Rotating AGAINST the steering is unambiguous - no magnitude comparison
        # can express it, and it is the signature of a genuine spin.
        if ($aY -gt 0.15 -and $aE -gt 0.15 -and
            [math]::Sign($YawRate) -ne [math]::Sign($expectedYaw)) {
            $oversteer = 1.0
        }
        else {
            $span = $DEV_REF - $DEV_DEAD
            $short  = $aE - $aY     # turning LESS than commanded (damage, blown tyre)
            $excess = $aY - $aE     # rotating MORE than commanded (spun, hit)
            if ($short -gt $DEV_DEAD) { $understeer = [math]::Min(1.0, ($short - $DEV_DEAD) / $span) }
            elseif ($excess -gt $DEV_DEAD) { $oversteer = [math]::Min(1.0, ($excess - $DEV_DEAD) / $span) }
        }
    }
    return [pscustomobject]@{
        ExpectedYaw = $expectedYaw; Understeer = $understeer; Oversteer = $oversteer
    }
}

function Tel-Sample {
    <#
      One poll. Returns a state object with raw and derived fields, or $null if
      the read failed (paused at a menu, mission unloaded, process gone).

      Derived fields are recomputed only on a sim tick and held in between - see
      the fixed-timestep note in the header.
    #>
    param($Ctx)

    $b = $Ctx.Buf
    $n = 0
    if (-not [I76Tel]::ReadProcessMemory($Ctx.H, [IntPtr]($Ctx.Ent), $b, $script:TEL_BLOCK, [ref]$n)) {
        if (-not (Tel-Resolve $Ctx)) { return $null }
        return $null
    }
    $Ctx.Polls++

    # Literal offsets, inlined deliberately. Going through a scriptblock helper
    # (& $f 0xAC) cost ~10 ms per poll in PowerShell 5.1 and was the difference
    # between 38 Hz and 200 Hz. The $TEL_OFF table above stays the readable
    # source of truth; these must agree with it.
    $speed    = [double][BitConverter]::ToSingle($b, 0xAC)
    $vx       = [double][BitConverter]::ToSingle($b, 0xBC)
    $vy       = [double][BitConverter]::ToSingle($b, 0xC0)
    $vz       = [double][BitConverter]::ToSingle($b, 0xC4)
    $rollRate = [double][BitConverter]::ToSingle($b, 0xC8)
    $yawRate  = [double][BitConverter]::ToSingle($b, 0xCC) * $script:TEL_YAW_SIGN
    $pitchRt  = [double][BitConverter]::ToSingle($b, 0xD0)
    $steer    = [double][BitConverter]::ToSingle($b, 0xE0)
    $throttle = [double][BitConverter]::ToSingle($b, 0xE4)

    # Sanity gate. A garbage read (mission unloading under us) shows up as
    # absurd magnitudes or NaN; re-resolve rather than feed nonsense to a device
    # that is bolted to the user's hands.
    if ([double]::IsNaN($speed) -or [double]::IsInfinity($speed) -or $speed -lt 0 -or $speed -gt 500) {
        [void](Tel-Resolve $Ctx)
        return $null
    }

    $t = $Ctx.Clock.Elapsed.TotalSeconds

    # ---- tick detection ---------------------------------------------------
    # A changed velocity means the sim advanced. Compare against the value at
    # the last CHANGE, not the last poll, so dt is a real tick interval.
    $moved = ([math]::Abs($vx - $Ctx.LastVx) -gt 1e-7) -or
             ([math]::Abs($vy - $Ctx.LastVy) -gt 1e-7) -or
             ([math]::Abs($vz - $Ctx.LastVz) -gt 1e-7)
    if ($moved) {
        $dt = $t - $Ctx.LastTickT
        if (-not $Ctx.Primed) {
            # First change we have ever seen: we have no valid previous tick to
            # differentiate against, so record the baseline and emit nothing.
            $Ctx.Primed = $true
        }
        elseif ($dt -gt 0.005 -and $dt -lt 1.0) {
            # Longitudinal acceleration from |v|: no unit or sign assumption.
            # Negative = slowing (braking, or hitting something).
            $Ctx.LongAccel = ($speed - $Ctx.LastTickSpeed) / $dt

            # Jolt = magnitude of the VECTOR velocity change per second. A crash
            # redirects velocity even when |v| barely moves (glancing a wall
            # spins you without much speed loss), so the vector delta catches
            # impacts that d(speed)/dt misses entirely.
            $dvx = $vx - $Ctx.LastVx; $dvy = $vy - $Ctx.LastVy; $dvz = $vz - $Ctx.LastVz
            $Ctx.Jolt = [math]::Sqrt($dvx*$dvx + $dvy*$dvy + $dvz*$dvz) / $dt
            $Ctx.Ticks++
        }
        $Ctx.LastTickT = $t
        $Ctx.LastTickSpeed = $speed
        $Ctx.LastVx = $vx; $Ctx.LastVy = $vy; $Ctx.LastVz = $vz
    }

    # ---- cornering and slip ----------------------------------------------
    # Lateral acceleration of a body rotating at yawRate while travelling at
    # speed: a_lat = omega * v. This is the cornering load - the thing that
    # should make the wheel feel heavy in a bend.
    $latAccel = $yawRate * $speed

    $slip = Tel-Slip -Speed $speed -Steer $steer -YawRate $yawRate
    $expectedYaw = $slip.ExpectedYaw

    $understeer = $slip.Understeer
    $oversteer  = $slip.Oversteer

    return [pscustomobject]@{
        T           = $t
        Ent         = $Ctx.Ent
        Speed       = $speed
        SpeedMph    = $speed * 2.23694
        Vx          = $vx; Vy = $vy; Vz = $vz
        YawRate     = $yawRate
        RollRate    = $rollRate
        PitchRate   = $pitchRt
        Steer       = $steer
        Throttle    = $throttle
        # derived
        LongAccel   = $Ctx.LongAccel
        LongG       = $Ctx.LongAccel / 9.81
        LatAccel    = $latAccel
        LatG        = $latAccel / 9.81
        ExpectedYaw = $expectedYaw
        Understeer  = $understeer
        Oversteer   = $oversteer
        Jolt        = $Ctx.Jolt
        Braking     = ($throttle -lt -0.05)
        Airborne    = ([math]::Abs($vy) -gt 2.0)
        Wheelbase   = $Ctx.Wheelbase
        Ticks       = $Ctx.Ticks
        Polls       = $Ctx.Polls
    }
}

function Tel-Close {
    param($Ctx)
    if ($Ctx -and $Ctx.H -ne [IntPtr]::Zero) { [void][I76Tel]::CloseHandle($Ctx.H) }
}
