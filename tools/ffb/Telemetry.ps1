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

  +0x0C8  float3 angular velocity; YAW RATE is the middle term at +0x0CC  CONFIRMED
        +0x0CC is the yaw rate, settled beyond doubt: the steering model below fits
        it at R^2 = 0.9997. The middle index is the vertical axis, consistent with
        velocity, whose middle term (+0x0C0) is the one that stays ~0 on flat
        ground.

        THE OTHER TWO ARE NOT ROLL AND PITCH RATE. They were labelled that way
        until they were checked against a 3407-sample drive:

            +0x0C8 vs d(longG)/dt  [pitch test]  correlation -0.03
            +0x0C8 vs d(latG)/dt   [roll test]   correlation +0.02
            +0x0D0 vs d(longG)/dt  [pitch test]  correlation +0.02
            +0x0D0 vs d(latG)/dt   [roll test]   correlation +0.08

        i.e. nothing. A car pitches under braking and rolls as cornering load
        changes, so a real roll or pitch rate would track those derivatives. These
        do not. Both sit at p50 = 0.000, p90 = 0.10 (against yaw's p90 of 1.25),
        and where they DO move, 77% of the time it coincides with a jolt > 5.

        So I'76 HAS NO SUSPENSION MODEL - no body roll, no pitch, and vertical
        velocity peaked at 0.77 m/s over 77 s of driving. These two fields are
        rotation imparted by impacts and by leaving the ground. Exposed as AngVelX
        / AngVelZ and summed into `Tumble`, and deliberately NOT used as a
        road-roughness signal: a texture channel driven off them is silent except
        when you crash, which is the opposite of what road texture means.

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
# Measured over 1072 cornering samples from two real drives, the yaw rate the
# engine produces is whichever of TWO LIMITS binds:
#
#     yaw = sign(steer) * min( (speed / L) * tan(|steer| * lock),     <- geometry
#                              a * |steer| / speed )                  <- lateral g
#
#     lock = 0.76 rad (43.5 deg)     a = 31.0 m/s^2 (3.16 g)     L = 4.662 m
#     crossover at v = sqrt(a*L) = 12.0 m/s = 27 mph
#
# Below 27 mph the car is limited by steering geometry, exactly like a real car at
# parking speeds. Above it, by a lateral-acceleration ceiling: multiply the second
# branch by speed and it says lateral g is proportional to steering input and
# INDEPENDENT of speed. That upper branch is a 1997 arcade simplification - the
# engine treats the wheel as a lateral-acceleration command - and it is why the
# cars feel go-kart-like at speed.
#
# Fit quality: median |residual| between 0.01 and 0.07 rad/s in EVERY speed band
# from 0 to 45 m/s. Either branch alone scores a NEGATIVE R^2 over the same data.
#
# HOW THE EARLIER ASSUMPTIONS FAILED, because the sequence is instructive:
#   1. A fixed steering lock alone gives an answer that falls with speed - 30 deg
#      at 16 m/s, 4.7 at 40 - because a constant-lock model cannot describe the
#      lateral-g branch. The fit lands wherever the drive spent its time, and two
#      different estimators both returned ~6 deg. Both times the ESTIMATOR was
#      blamed, before anyone plotted the implied lock against speed.
#   2. The lateral-g branch alone then fitted beautifully (R^2 = 0.9997) - but only
#      because that drive was 80-93 mph almost throughout, entirely above the
#      crossover. It reported 158 false understeer samples on the next drive, which
#      included the low-speed regime it could not describe.
# A model validated on data that only covers one regime looks perfect and is half
# a model. Both drives together were needed to see the elbow.
#
# CONSEQUENCE FOR SLIP: the engine has no tyre slip model, so understeer and
# oversteer in the sim-racing sense do not occur in normal driving - the car does
# exactly what it is asked. What DOES happen is loss of control: spins, impacts
# and blown tyres, which show up as large DEVIATIONS from the relation above
# (40 of 783 samples deviated by >0.5 rad/s, all of them spins or hits). So the
# Understeer/Oversteer fields below are a loss-of-control signal, and that is
# more useful here than a tyre model would be.

# Lateral acceleration per unit steering input, m/s^2. 31.0 = 3.16 g at full lock.
$script:TEL_LAT_GAIN = 31.0

# Steering lock at full input, radians. 0.76 rad = 43.5 deg. This governs the
# LOW-SPEED branch only (see the two-regime note above).
$script:TEL_STEER_LOCK = 0.76

# Hard safety cap on the reference, rad/s. The min() of the two branches already
# bounds it; this only guards against a nonsense calibration file.
$script:TEL_YAW_MAX = 3.2

# Bumped when the shape of the handling model changes, so a stale ffb-calib.json
# cannot feed parameters from a superseded model into this one. Model 1 fitted a
# single fixed steering lock and its numbers are meaningless here.
$script:TEL_MODEL = 2

# Weapon-fire flags, STATIC globals (not in the entity struct).
#
# MEASURED with tools\ffb\ffb-find-fire.ps1: an idle baseline followed by firing
# with the steering held still. Two bytes changed while firing and not while idle,
# both taking exactly the values {0, 1}:
#
#     0x5367D0    0x5367DE
#
# CORRECTED 2026-09-27 from the static map (i76-map symbols\globals.tsv, capstone over the pristine exe):
#   0x5367D0  input_throttle_up  - read only by input_ApplyToEntity 0x44f1c0, beside the throttle
#             (0x44f249 / 0x44f433). It moved in the measurement because the fire button was also
#             bound to throttle-up (or throttle was touched); it is not a fire flag.
#   0x5367DB  input_weapon_fire  - read by the weapon code 0x4a5870 (0x4a5945, 0x4a5acf, 0x4a5b22).
#             It stayed still in the measurement because firing went through a HARDPOINT key.
#   0x5367DE..0x5367E2  input_hardpoint1..5_fire - the five per-hardpoint fire bytes, registered
#             by 0x4a2d30 into the table at 0x5da738 (0x4a2dc8..0x4a2df0).
# So the channel reads one 16-byte block from 0x5367DB: +0 = weapon_fire, +3..+7 = hardpoints 1-5,
# and any of the six going nonzero is "firing". The mixer still prefers the engine's own effect
# slots (below), which is what actually fired.
#
# Set TEL_FIRE_ADDR to 0 to disable the channel outright. If no byte ever
# changes, the channel is silent - it cannot produce spurious kicks.
$script:TEL_FIRE_ADDR  = 0x5367db

# ---------------------------------------------------------------------------
# THE ENGINE'S OWN EFFECT TABLE - far better than the input flag above
# ---------------------------------------------------------------------------
# I7_SFRCE.DLL exports one effect entry point, I7FF_SIM_Effect, and the engine
# calls it with a single 364-byte parameter block at 0x4f2328 (dispatcher at
# 0x446110, which writes 0x16c as the struct size). Inside that block, starting
# at +0x030 with a stride of 0x1C, is an ARRAY OF EFFECT SLOTS. Captured live
# while firing:
#
#   slot  +0x00 active  +0x0C id  +0x10 param  +0x14 magnitude  +0x18 flag
#     0        0/1            8      0.8104          10            1
#     1        0/1           17      0.8104           5            1
#     2        0/1            8    180.8              10            1
#     3        0/1           13    180.8              60            1
#
# The timing settles what they are: slot 3 fired six times at 0.75 s intervals -
# a weapon on a reload cycle - while slots 0-2 fired in 0.1 s bursts, i.e. rapid
# fire. The field shape matches the engine's own logging format from
# I7_SFRCE.DLL ("Hardpoint:%d WpnId:%d Freq:%d Gain:%d Direction:%d"), and +0x10
# taking exactly two values (0.81 and 180.8) reads as a DIRECTION.
#
# This is strictly better than watching an input byte: it is what the engine
# DECIDED after input handling, weapon logic, ammo and damage rules all ran. An
# input flag says a button moved; this says a weapon actually fired.
#
# Only slots 0-5 are read. Slot 6 would start at +0x0D8, and that region updates
# continuously at the sim tick rate with hundreds of distinct values, so it is a
# different structure - not another on/off slot.
$script:TEL_FX_BLOCK  = 0x4f2328
$script:TEL_FX_BASE   = 0x030
$script:TEL_FX_STRIDE = 0x1C
$script:TEL_FX_SLOTS  = 6
$script:TEL_FIRE_ADDR2 = 0x5367de

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
        # The sign never depends on the model's shape, so it is always honoured.
        if ($null -ne $c.TEL_YAW_SIGN) { $script:TEL_YAW_SIGN = [int]$c.TEL_YAW_SIGN }
        # Fire addresses are independent of the handling model, so they load
        # regardless of TEL_MODEL.
        if ($null -ne $c.TEL_FIRE_ADDR)  { $script:TEL_FIRE_ADDR  = [int]$c.TEL_FIRE_ADDR }
        if ($null -ne $c.TEL_FIRE_ADDR2) { $script:TEL_FIRE_ADDR2 = [int]$c.TEL_FIRE_ADDR2 }
        # The fitted PARAMETERS are only meaningful for the model they were fitted
        # to. A model-1 file carries a single fixed steering lock (~0.10 rad from a
        # broken fit), which would be silently accepted as this model's low-speed
        # lock and make the reference nonsense. So gate on the version.
        if ([int]$c.TEL_MODEL -ge 2) {
            if ($null -ne $c.TEL_LAT_GAIN)   { $script:TEL_LAT_GAIN   = [double]$c.TEL_LAT_GAIN }
            if ($null -ne $c.TEL_STEER_LOCK) { $script:TEL_STEER_LOCK = [double]$c.TEL_STEER_LOCK }
            $script:TEL_CALIB_SOURCE = ("calibrated from {0} ({1} samples, sign confidence {2:0}%)" -f `
                $c.Source, $c.Samples, ([double]$c.SignConfidence * 100))
        } else {
            $script:TEL_CALIB_SOURCE = "sign only - ffb-calib.json predates the two-regime model, re-run ffb-calibrate.ps1"
        }
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
$script:TEL_BLOCK = 0x480   # one ReadProcessMemory covers every field above, plus (2026-10-24) the component
                            # slot pointers +0x3a8.., the steer gain +0x110, armour/chassis +0x138..+0x177, flags
                            # +0x454, surface +0x45c and ground_g +0x46c (tools/telemetry/i76tel.h has the map)

if (-not ('I76Tel' -as [type])) {
    Add-Type @"
using System;
using System.Runtime.InteropServices;
public class I76Tel {
  [DllImport("kernel32.dll", SetLastError=true)]
  public static extern IntPtr OpenProcess(uint access, bool inherit, int pid);
  [DllImport("kernel32.dll", SetLastError=true)]
  public static extern bool ReadProcessMemory(IntPtr h, IntPtr addr, byte[] buf, int size, out int read);
  [DllImport("kernel32.dll", SetLastError=true)]
  public static extern bool WriteProcessMemory(IntPtr h, IntPtr addr, byte[] buf, int size, out int written);
  [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
}
"@
}

function Tel-Open {
    <#
      Resolves the process and the player entity. Returns a context object, or
      throws with a reason a human can act on. Safe to call repeatedly.
    #>
    param([int]$GamePid = 0)
    # -GamePid / $env:I76_FFB_PID pick one game when several run (a lab lane beside the owner's game);
    # otherwise the first i76 / nitro process, as before.
    if ($GamePid -le 0 -and $env:I76_FFB_PID) { $GamePid = [int]$env:I76_FFB_PID }
    $proc = if ($GamePid -gt 0) { Get-Process -Id $GamePid -ErrorAction SilentlyContinue } else { Get-Process i76, nitro -ErrorAction SilentlyContinue | Select-Object -First 1 }
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
        VyRate    = 0.0
        WAx = 0.0; WAy = 0.0; WAz = 0.0
        LastHeading = 0.0; HeadingRate = 0.0; Slide = 0.0
        Rpm = 0; LastRpm = 0; RpmRate = 0.0; Shift = 0; ShiftHold = 0.0
        LastSpeedShift = 0.0
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
        FireBuf   = (New-Object byte[] 16)
        FxBuf     = (New-Object byte[] ($script:TEL_FX_BASE + $script:TEL_FX_SLOTS * $script:TEL_FX_STRIDE))
        FxPrev    = (New-Object int[] $script:TEL_FX_SLOTS)
        FxPrevId  = (New-Object int[] $script:TEL_FX_SLOTS)
        FxPrevMag = (New-Object int[] $script:TEL_FX_SLOTS)
        # ---- 2026-10-24: surface, engine, damage and weapon state (Tel-Extras) ----
        Obj       = 0
        X         = $null       # Tel-Extras state, rebuilt whenever the entity changes
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
    if ($ent -ne $Ctx.Ent) { $Ctx.X = $null }   # new mission / respawn: no baselines carry over
    $Ctx.Ent = $ent
    $Ctx.Obj = $sub
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

function Tel-DetectShift {
    <#
      Was that a gear change?

      No gear field was ever found in this game and none is needed. An upshift is
      the one thing in the whole car that makes ENGINE speed fall while ROAD speed
      does not.

      THE SPEED CONDITION IS THE WHOLE TRICK. Revs also fall every time the driver
      lifts off, and that is not a gear change: on a lift the car slows WITH the
      engine, on a shift it does not. Without that test this fires on every
      corner entry in the game.

      A downshift is the mirror image - revs jump while road speed does not rise -
      and needs a higher threshold, because ordinary acceleration raises revs too
      and only a shift does it near-instantly.

      Dt MUST be a sim-tick interval, not a poll interval. At 20 Hz a poll-rate
      derivative divides a real rev change by a fraction of the interval that
      produced it and reads several times too fast.

      Extracted from Tel-Sample so it can be tested against synthetic traces with
      no game running - same reason as Tel-Slip. Returns the decision, the rate it
      decided on, and the updated refractory timer.
    #>
    param(
        [int]$Rpm, [int]$LastRpm,
        [double]$Speed, [double]$LastSpeed,
        [double]$Dt, [double]$Hold,
        # PROVISIONAL: reasoned, not measured. rpmRate is logged on every drive
        # so these can be replaced with numbers from a real capture.
        [double]$DropRate = 6000.0,   # rpm/s. Lifting off decays at roughly 3000.
        [double]$RiseRate = 9000.0    # rpm/s. Accelerating climbs at roughly 5000.
    )
    $shift = 0
    $rpmRate = 0.0
    if ($Dt -le 0) { return [pscustomobject]@{ Shift = 0; RpmRate = 0.0; Hold = $Hold } }
    if ($LastRpm -gt 0) { $rpmRate = ($Rpm - $LastRpm) / $Dt }

    if ($Hold -gt 0) {
        # One shift is ONE event. Without this the whole ramp fires on every frame
        # the revs are still falling, which is a buzz, not a gear change.
        $Hold -= $Dt
        if ($Hold -lt 0) { $Hold = 0.0 }
    }
    elseif ($Speed -gt 3.0 -and $Rpm -gt 0 -and $LastRpm -gt 0) {
        $spdRate = ($Speed - $LastSpeed) / $Dt
        if ($rpmRate -lt -$DropRate -and $spdRate -gt -1.5) {
            $shift = 1;  $Hold = 0.35
        } elseif ($rpmRate -gt $RiseRate -and $spdRate -lt 1.5) {
            $shift = -1; $Hold = 0.35
        }
    }
    return [pscustomobject]@{ Shift = $shift; RpmRate = $rpmRate; Hold = $Hold }
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
    param(
        [double]$Speed, [double]$Steer, [double]$YawRate,
        [double]$Slide = 0.0,
        # THE ENGINE'S OWN LAW, read live (2026-10-24). physics_ComputeSteerYawRate 0x43ce10
        # (i76-map subsystems/physics.md "The steering routine"):
        #     w = steer * s * K                 K   = entity+0x110 = 1/(2*wheelbase)
        #     capped at w = steer * lim / s     lim = 7.84 * (grip of tyres 0,1,4,5)
        # When both are given (Tel-Sample reads them every half second) the reference IS
        # the engine's law for THIS car with THESE tyres, and no fitted constant is used.
        # The fitted (lock, a) pair stays as the fallback for CSV replays without them.
        # Why it matters, measured on the owner's 2026-10-24 calibration drive: his car's
        # tyres sum to lim = 37.5 m/s^2 (the size-factor grip bonus before the first hit),
        # the RC folder's calibration said 31.0, and the model therefore read 781 of 957
        # ordinary steady-turn samples (82 %) as rotating MORE than commanded - oversteer -
        # which is the "pronounced under/oversteer jerk" he reported.
        [double]$SteerK = 0.0, [double]$LatCap = 0.0)

    # LOWERED from 0.15 so the wheel WARNS about the approach instead of only
    # REPORTING the departure. The evidence for how far it can safely come down:
    #   * the reference fits gripped driving to a residual sd of 0.011
    #   * a whole gentle drive never exceeded 0.105, with p99 at 0.089
    #   * a drive with donuts reached 2.539
    # So 0.08 sits about 7 sigma above model noise while still firing on well
    # under 1% of ordinary driving, and the response is progressive from there -
    # which matters because the thing being communicated ("when does the skid
    # start, and how much") is exactly what a driver cannot otherwise perceive.
    $DEV_DEAD = 0.08
    $DEV_REF  = 1.10    # rad/s: deviation treated as fully out of shape

    # TWO REGIMES, and the yaw rate is whichever LIMIT binds:
    #   low speed  - steering geometry:  (v/L) * tan(steer * lock)
    #   high speed - lateral g ceiling:  a * steer / v
    # They cross at v = sqrt(a*L) = 12.0 m/s (27 mph).
    $expectedYaw = 0.0
    if ($Speed -gt 0.5) {
        $aSteer = [math]::Abs($Steer)
        if ($SteerK -gt 0.01 -and $SteerK -lt 2.0 -and $LatCap -gt 5.0 -and $LatCap -lt 200.0) {
            $kin = $aSteer * $Speed * $SteerK
            $lat = $LatCap * $aSteer / $Speed
        } else {
            $kin = ($Speed / 4.662) * [math]::Tan($aSteer * $script:TEL_STEER_LOCK)
            $lat = $script:TEL_LAT_GAIN * $aSteer / $Speed
        }
        $mag = [math]::Min($kin, $lat)
        if ($mag -gt $script:TEL_YAW_MAX) { $mag = $script:TEL_YAW_MAX }
        if ($Steer -lt 0) { $mag = -$mag }
        $expectedYaw = $mag
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
    # ---- SIDESLIP, folded in ------------------------------------------------
    # Everything above compares yaw rate against the yaw the STEERING asked for.
    # That catches the car disobeying the driver, which is why it fires on spins
    # and handbrake turns but stayed quiet through ordinary skids: in a four-wheel
    # drift the car can slide a long way while still rotating roughly as commanded.
    #
    # Slide is the other half - how far the car's DIRECTION OF TRAVEL has come
    # adrift from where its nose is turning (see Tel-Sample). It is the measure
    # that actually corresponds to the skid the player hears.
    #
    # Taken as a MAXIMUM rather than a sum. These are two views of one physical
    # event, not two separate events, and adding them would double-count a spin,
    # which trips both at once.
    if ($Slide -gt 0) {
        $sDead = 0.12   # rad/s. Above derivative noise on a gripped line.
        $sRef  = 1.20   # rad/s. Fully sideways.
        if ($Slide -gt $sDead) {
            $slideN = [math]::Min(1.0, ($Slide - $sDead) / ($sRef - $sDead))
            if ($slideN -gt $oversteer) { $oversteer = $slideN }
        }
    }

    return [pscustomobject]@{
        ExpectedYaw = $expectedYaw; Understeer = $understeer; Oversteer = $oversteer
    }
}

function Tel-ReadBuf {
    # One ReadProcessMemory into a fresh buffer; $null unless every byte arrived.
    param($Ctx, [int64]$Addr, [int]$Len)
    if ($Addr -le 0x10000 -or $Len -le 0) { return $null }
    $buf = New-Object byte[] $Len
    $n = 0
    if ([I76Tel]::ReadProcessMemory($Ctx.H, [IntPtr]$Addr, $buf, $Len, [ref]$n) -and $n -eq $Len) { return ,$buf }
    return $null
}

function Tel-CompData {
    <#
      A vehicle component's data block: o = [ent+0x3a8+4*slot]; [o+0x6c] must be the
      expected class; data = [o+0x70]. The proxy's tel_comp (music-fix/strlkproxy.c) does
      the same walk in-process. Returns 0 when the slot is empty or holds another class.
    #>
    param($Ctx, [byte[]]$EntBuf, [int]$Slot, [int]$Class)
    $o = [BitConverter]::ToUInt32($EntBuf, 0x3a8 + 4 * $Slot)
    if ($o -lt 0x10000) { return 0 }
    $h = Tel-ReadBuf $Ctx ([int64]$o + 0x6c) 8
    if (-not $h) { return 0 }
    if ([BitConverter]::ToInt32($h, 0) -ne $Class) { return 0 }
    return [int64][BitConverter]::ToUInt32($h, 4)
}

function Tel-SurfacePaved {
    <#
      Is this surface pavement? Pure, so ffb-mixer-test.ps1 can check it.

      The surface type is entity+0x45c, an index (0..7) into the level's WRLD surface
      table at 0x644220 (8 records x 20 bytes: +0 tyre grip, +4 rolling resistance,
      +8 bump amplitude, +0x10 damage rate; i76-map data/notes/terrain-text-sound.md).
      Stock values by type: rolling .03 .10 .01 .03 .08 .20 .01 .03, and the skid/dust
      sound table gives 2 and 6 no dust - tarmac. So "paved" = the low-rolling-resistance
      records, read from THIS level's table (a mod or another map can renumber them);
      the fixed index set {2, 6} is the fallback when the table cannot be read.
    #>
    param([int]$Surface, $Roll = $null, [double]$RollMax = 0.015)
    if ($Surface -lt 0 -or $Surface -gt 7) { return $false }
    if ($null -ne $Roll -and $Roll.Count -eq 8) {
        $r = [double]$Roll[$Surface]
        if ($r -gt 0.0 -and $r -lt 1.0) { return ($r -le $RollMax) }
    }
    return ($Surface -eq 2 -or $Surface -eq 6)
}

function Tel-DiffDamage {
    <#
      Hits taken, from the per-side hit points. Pure, for the test file.
      Prev / Cur: int[4] = armour + chassis per side (entity+0x138 / +0x148, sides
      0 front 1 left 2 right 3 back; i76tel.h). Only LOSSES are hits: a repair or a
      respawn raises them and resets the baseline instead. Returns @(@{Side; Hp}).
    #>
    param($Prev, $Cur)
    $hits = @()
    if ($null -eq $Prev -or $null -eq $Cur) { return ,$hits }
    for ($i = 0; $i -lt 4; $i++) {
        $d = [int]$Prev[$i] - [int]$Cur[$i]
        if ($d -gt 0 -and $d -lt 100000) { $hits += [pscustomobject]@{ Side = $i; Hp = $d } }
    }
    return ,$hits
}

function Tel-DiffAmmo {
    <#
      Shots fired, from the player's weapon instances' ammo counters (instance +0x20,
      spent at 0x4a6f64; i76-map types/i76_runtime.h I76_WeaponInstance). Pure.
      Prev: hashtable instance index -> ammo. Cur: @(@{Idx; Ammo; Klass; Damage}).
      0x0fffffff is "unlimited" (never spent) and an INCREASE is a reload or pickup,
      so neither is a shot. Returns @(@{Klass; Damage; Rounds; Idx}).
    #>
    param($Prev, $Cur)
    $shots = @()
    if ($null -eq $Prev) { return ,$shots }
    foreach ($w in $Cur) {
        if (-not $Prev.ContainsKey($w.Idx)) { continue }
        $p = [int]$Prev[$w.Idx]
        if ($p -eq 0x0fffffff -or $w.Ammo -eq 0x0fffffff) { continue }
        $d = $p - [int]$w.Ammo
        if ($d -gt 0 -and $d -lt 1000) {
            $shots += [pscustomobject]@{ Klass = $w.Klass; Damage = $w.Damage; Rounds = $d; Idx = $w.Idx }
        }
    }
    return ,$shots
}

function Tel-Extras {
    <#
      2026-10-24: everything the custom FFB needed that the FFB effect block could not
      be trusted to supply. The block at 0x4f2328 is written ONLY while the engine's own
      FFB device is present (0x52bbd0 = 1; i76tel.h ffb_present), so every channel that
      read it - weapon kicks, rpm, gear shifts - was silent on a setup where the 1997
      DLL did not take the wheel. These come from the entity and its components instead,
      which exist whenever a car does:

        flags      entity+0x454  0x1 engine running, 0x2 slide, 0x4 airborne, 0x8 starting,
                                 0x400 oil, 0x2000 drift band (L < |w s| <= 2L), 0x10000 arcade
        surface    entity+0x45c  -> Tel-SurfacePaved, against the level's WRLD table 0x644220
        engine     [[ent+0x3c4]+0x70]: +0x08 gear (0 R, 1 N, 2..4), +0x1c rpm (float)
        steer law  entity+0x110 K = 1/(2 wb); lim = 7.84 x grip of tyres 0, 1, 4, 5 (+0x0c)
        damage     entity+0x138 armour[4] + +0x148 chassis[4] -> hits per side
        weapons    the player's vehicle weapon record (0x5be4d8 + i x 0x2c8, +0 = the
                   player object, +4 selected row) and its instances (0x5aab08 + i x 0x4c:
                   +0x18 record, +0x20 ammo, +0x30 weapdef); weapdef 0x5d88d8 + i x 0xd8:
                   +0x5c class (2 gun/cannon, 3 mortar, 4 rocket/missile, 5 flamer,
                   6 dropper), +0x60 damage

      Addresses are the proxy's own (music-fix/strlkproxy.c tel_player_fill) for the
      i76.exe builds the launchers run (9a232dcc / 6319abf7; nitro shifts +0x444.. by 4
      and is not handled here). Slow-changing reads are throttled; per poll this costs
      two small reads plus one per weapon span.
    #>
    param($Ctx, [byte[]]$B, [double]$T)
    if ($null -eq $Ctx.X) {
        $Ctx.X = [pscustomobject]@{
            EngData = 0; EngT = -10.0; GripT = -10.0; GripSum = 0.0; Handling = 0.0
            SurfRoll = $null; SurfGrip = $null; SurfT = -10.0
            WRec = 0; WInst = @(); WScanT = -10.0; PrevAmmo = $null; DefCache = @{}
            PrevRow = -99; PrevSides = $null; LastGear = -1
            LastAmmo = @()   # 2026-10-25: the current ammo per weapon instance, for the web panel
        }
    }
    $X = $Ctx.X
    $objU = [uint32]([int64]$Ctx.Obj -band 0xFFFFFFFFL)
    $flags   = [BitConverter]::ToUInt32($B, 0x454)
    $surface = [BitConverter]::ToInt32($B, 0x45c)
    $steerK  = [double][BitConverter]::ToSingle($B, 0x110)
    $groundG = [double][BitConverter]::ToSingle($B, 0x46c)

    # ---- surface table: once per 5 s (per level, it never changes in a mission) ----
    if (($T - $X.SurfT) -gt 5.0) {
        $X.SurfT = $T
        $st = Tel-ReadBuf $Ctx 0x644220 160
        if ($st) {
            $roll = New-Object double[] 8; $grip = New-Object double[] 8
            for ($i = 0; $i -lt 8; $i++) {
                $grip[$i] = [BitConverter]::ToSingle($st, $i * 20)
                $roll[$i] = [BitConverter]::ToSingle($st, $i * 20 + 4)
            }
            $X.SurfRoll = $roll; $X.SurfGrip = $grip
        }
    }
    $paved = Tel-SurfacePaved -Surface $surface -Roll $X.SurfRoll

    # ---- engine: gear and rpm, every poll (the data pointer is cached) ----
    if ($X.EngData -eq 0 -and ($T - $X.EngT) -gt 1.0) {
        $X.EngT = $T
        $X.EngData = Tel-CompData $Ctx $B 7 21
    }
    $gear = -1; $rpmF = 0.0
    if ($X.EngData -ne 0) {
        $eb = Tel-ReadBuf $Ctx $X.EngData 0x28
        if ($eb) {
            $gear = [BitConverter]::ToInt32($eb, 0x08)
            $rpmF = [double][BitConverter]::ToSingle($eb, 0x1c)
            if ($gear -lt 0 -or $gear -gt 8 -or [double]::IsNaN($rpmF) -or $rpmF -lt 0 -or $rpmF -gt 20000) {
                $gear = -1; $rpmF = 0.0; $X.EngData = 0
            }
        } else { $X.EngData = 0 }
    }
    $shift = 0
    if ($gear -ge 2 -and $X.LastGear -ge 2 -and $gear -ne $X.LastGear) {
        $shift = $(if ($gear -gt $X.LastGear) { 1 } else { -1 })
    }
    if ($gear -ge 0) { $X.LastGear = $gear }

    # ---- tyre grip -> the engine's lateral limit, twice a second ----
    if (($T - $X.GripT) -gt 0.5) {
        $X.GripT = $T
        $sum = 0.0; $got = 0
        foreach ($sl in @(0, 1, 4, 5)) {
            $wd = Tel-CompData $Ctx $B $sl 30
            if ($wd -ne 0) {
                $wb = Tel-ReadBuf $Ctx ($wd + 0x0c) 4
                if ($wb) { $sum += [BitConverter]::ToSingle($wb, 0); $got++ }
            }
        }
        $X.GripSum = $(if ($got -eq 4 -and $sum -gt 0.5 -and $sum -lt 20) { $sum } else { 0.0 })
        $sd = Tel-CompData $Ctx $B 8 23
        $X.Handling = 0.0
        if ($sd -ne 0) {
            $hb = Tel-ReadBuf $Ctx ($sd + 0x14) 4
            if ($hb) { $X.Handling = [double][BitConverter]::ToSingle($hb, 0) }
        }
    }
    $latCap = 0.0
    if ($X.GripSum -gt 0) {
        if (($flags -band 0x10000) -ne 0) {
            # arcade / Taurus: lim = L = gn x handling x surface grip x sum x 0.25
            $sg = $(if ($X.SurfGrip -and $surface -ge 0 -and $surface -le 7) { $X.SurfGrip[$surface] } else { 0.0 })
            if ($X.Handling -gt 0 -and $sg -gt 0 -and $groundG -gt 0) { $latCap = $groundG * $X.Handling * $sg * $X.GripSum * 0.25 }
        } else {
            $latCap = 7.84 * $X.GripSum
        }
    }

    # ---- damage taken, per side ----
    $sides = New-Object int[] 4
    for ($i = 0; $i -lt 4; $i++) {
        $sides[$i] = [BitConverter]::ToInt32($B, 0x138 + 4 * $i) + [BitConverter]::ToInt32($B, 0x148 + 4 * $i)
    }
    $hits = Tel-DiffDamage $X.PrevSides $sides
    $X.PrevSides = $sides

    # ---- weapons: find the player's record and instances every 3 s ----
    if (($X.WRec -eq 0 -or $X.WInst.Count -eq 0) -and ($T - $X.WScanT) -gt 3.0) {
        $X.WScanT = $T
        $X.WRec = 0; $X.WInst = @(); $X.PrevAmmo = $null; $X.LastAmmo = @()
        $nb = Tel-ReadBuf $Ctx 0x5da78c 4
        $nrec = $(if ($nb) { [BitConverter]::ToInt32($nb, 0) } else { 0 })
        if ($nrec -gt 150) { $nrec = 150 }
        if ($nrec -gt 0 -and $Ctx.Obj -ne 0) {
            $rb = Tel-ReadBuf $Ctx 0x5be4d8 ($nrec * 0x2c8)
            if ($rb) {
                for ($i = 0; $i -lt $nrec; $i++) {
                    if ([BitConverter]::ToUInt32($rb, $i * 0x2c8) -eq $objU) { $X.WRec = 0x5be4d8 + $i * 0x2c8; break }
                }
            }
        }
        if ($X.WRec -ne 0) {
            $ib = Tel-ReadBuf $Ctx 0x5da750 4
            $ninst = $(if ($ib) { [BitConverter]::ToInt32($ib, 0) } else { 0 })
            if ($ninst -gt 150) { $ninst = 150 }
            if ($ninst -gt 0) {
                $tb = Tel-ReadBuf $Ctx 0x5aab08 ($ninst * 0x4c)
                if ($tb) {
                    $own = @()
                    for ($i = 0; $i -lt $ninst; $i++) {
                        if ([BitConverter]::ToUInt32($tb, $i * 0x4c + 0x18) -eq [uint32]$X.WRec) { $own += $i }
                    }
                    $X.WInst = $own
                }
            }
        }
    }
    $shots = @(); $row = -1; $cycle = $false
    if ($X.WRec -ne 0 -and $X.WInst.Count -gt 0) {
        $rh = Tel-ReadBuf $Ctx $X.WRec 8
        if ($rh -and [BitConverter]::ToUInt32($rh, 0) -eq $objU) {
            $row = [BitConverter]::ToInt32($rh, 4)
            if ($X.PrevRow -ne -99 -and $row -ne $X.PrevRow -and $row -ge 0) { $cycle = $true }
            $X.PrevRow = $row
            $lo = ($X.WInst | Measure-Object -Minimum).Minimum
            $hi = ($X.WInst | Measure-Object -Maximum).Maximum
            $span = Tel-ReadBuf $Ctx (0x5aab08 + $lo * 0x4c) (($hi - $lo + 1) * 0x4c)
            if ($span) {
                $cur = @()
                foreach ($ix in $X.WInst) {
                    $o = ($ix - $lo) * 0x4c
                    $def = [BitConverter]::ToInt32($span, $o + 0x30)
                    if (-not $X.DefCache.ContainsKey($def)) {
                        $kl = 0; $dm = 0
                        if ($def -ge 0 -and $def -lt 400) {
                            $db = Tel-ReadBuf $Ctx (0x5d88d8 + $def * 0xd8 + 0x5c) 8
                            if ($db) { $kl = [BitConverter]::ToInt32($db, 0); $dm = [BitConverter]::ToInt32($db, 4) }
                        }
                        $X.DefCache[$def] = @($kl, $dm)
                    }
                    $cur += [pscustomobject]@{
                        Idx = $ix; Ammo = [BitConverter]::ToInt32($span, $o + 0x20)
                        Klass = $X.DefCache[$def][0]; Damage = $X.DefCache[$def][1]
                    }
                }
                $shots = Tel-DiffAmmo $X.PrevAmmo $cur
                $pa = @{}; foreach ($w in $cur) { $pa[$w.Idx] = $w.Ammo }
                $X.PrevAmmo = $pa
                $X.LastAmmo = $cur
            }
        } else {
            $X.WRec = 0; $X.WInst = @(); $X.LastAmmo = @()   # the record moved (respawn): rescan
        }
    }

    return [pscustomobject]@{
        Flags = $flags; Surface = $surface; Paved = $paved
        SurfaceGrip = $(if ($X.SurfGrip -and $surface -ge 0 -and $surface -le 7) { $X.SurfGrip[$surface] } else { 0.0 })
        Gear = $gear; RpmF = $rpmF; GearShift = $shift
        SteerK = $steerK; LatCap = $latCap; GripSum = $X.GripSum
        Hits = $hits; Shots = $shots; WeaponRow = $row; WeaponCycle = $cycle
        Ammo = $X.LastAmmo   # @(@{Idx; Ammo; Klass; Damage}) per weapon instance (web panel)
        ShotSource = $(if ($X.WRec -ne 0 -and $X.WInst.Count -gt 0) { 'ammo' } else { 'none' })
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
    # NOT RollRate/PitchRate, which is what these were called until they were
    # checked against a real drive. See the ANGULAR VELOCITY note in the header:
    # the engine has no suspension model, so neither of these tracks body roll or
    # pitch - they register rotation from impacts and from leaving the ground.
    $angVelX  = [double][BitConverter]::ToSingle($b, 0xC8)
    $yawRate  = [double][BitConverter]::ToSingle($b, 0xCC) * $script:TEL_YAW_SIGN
    $angVelZ  = [double][BitConverter]::ToSingle($b, 0xD0)
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

            # Heave: rate of change of VERTICAL velocity, m/s^2. This is the
            # motion-platform "heave" axis - landings, crests, and the drop of a
            # jump all live here. Same tick discipline as LongAccel.
            $Ctx.VyRate = ($vy - $Ctx.LastVy) / $dt

            # WORLD-frame acceleration, m/s^2, by differentiating the world
            # velocity vector. Exact, and it needs no orientation - which matters
            # because this entity has none to read (there is no rotation matrix
            # anywhere in the struct). Motion-sim protocols want world-frame
            # accelerations with gravity EXCLUDED, which is what this is: a parked
            # car reads (0,0,0).
            $Ctx.WAx = ($vx - $Ctx.LastVx) / $dt
            $Ctx.WAy = ($vy - $Ctx.LastVy) / $dt
            $Ctx.WAz = ($vz - $Ctx.LastVz) / $dt

            # ---- SIDESLIP, without needing any orientation ------------------
            # A skid is the car TRAVELLING in a different direction than it is
            # POINTING. We cannot read a facing vector - this engine has none -
            # but we do not need one:
            #
            #   * the velocity vector's heading rotates at d(heading)/dt
            #   * the car body rotates at the yaw rate
            #   * GRIPPED, those are the same number: the car goes where it points
            #   * SLIDING, they diverge, and the gap IS the sideslip rate
            #
            # This is a different quantity from the yaw-vs-commanded deviation
            # already computed in Tel-Slip. That one catches the car disobeying
            # the STEERING; this one catches the car disobeying its own NOSE, which
            # is what a skid actually is and why the first measure kept missing it.
            if ($speed -gt 2.0 -and $Ctx.LastHeading -ne 0.0) {
                $hNow = [math]::Atan2($vx, $vz)
                $dh = $hNow - $Ctx.LastHeading
                # shortest way round the circle - without this, every pass through
                # +/-pi reads as a violent slide
                while ($dh -gt [math]::PI)  { $dh -= 2 * [math]::PI }
                while ($dh -lt -[math]::PI) { $dh += 2 * [math]::PI }
                $Ctx.HeadingRate = $dh / $dt
                $Ctx.Slide = [math]::Abs($yawRate - $Ctx.HeadingRate)
                $Ctx.LastHeading = $hNow
            } elseif ($speed -gt 2.0) {
                $Ctx.LastHeading = [math]::Atan2($vx, $vz)
                $Ctx.HeadingRate = 0.0; $Ctx.Slide = 0.0
            } else {
                $Ctx.HeadingRate = 0.0; $Ctx.Slide = 0.0
            }

            # RPM is read further down (it lives in the FFB block, not the entity),
            # so gear-shift detection cannot run here. Carry the real tick interval
            # forward instead - shift rates must be differentiated against a sim
            # tick, never against a poll.
            $tickAdvanced = $true
            $tickDt = $dt

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

    # Surface, engine, damage, weapons and the engine's own steering law (2026-10-24).
    $xt = Tel-Extras $Ctx $b $t
    # The slide only counts while the ENGINE says the car is sliding: flag 0x2000 (the drift band, velocity
    # kept) or 0x2 (a full slide). On the grip path the engine snaps the velocity onto the heading, so any
    # yaw-vs-heading gap there is tick-alignment noise - and at walking pace that noise saturated the
    # oversteer channel (live run r1, 2026-10-24: oversteer 1.0 at 4-7 m/s with neither flag set).
    $slideUsed = $Ctx.Slide
    if ($xt.Flags -ne 0 -and ($xt.Flags -band 0x2002) -eq 0) { $slideUsed = 0.0 }
    $slip = Tel-Slip -Speed $speed -Steer $steer -YawRate $yawRate -Slide $slideUsed -SteerK $xt.SteerK -LatCap $xt.LatCap
    $expectedYaw = $slip.ExpectedYaw

    # Weapon-fire flag. A separate 1-byte read because it is a static global, not
    # part of the entity struct. Costs nothing measurable - the poll loop runs at
    # 3400 Hz - and if the address is wrong this just stays 0 forever, which leaves
    # the weapon channel silent rather than firing at random.
    # One 16-byte read from 0x5367DB covers weapon_fire (+0) and hardpoints 1-5 (+3..+7).
    # Reading a block rather than six bytes keeps this at one syscall.
    $fire = 0
    if ($script:TEL_FIRE_ADDR -ne 0) {
        $fb = $Ctx.FireBuf
        $fn = 0
        if ([I76Tel]::ReadProcessMemory($Ctx.H, [IntPtr]$script:TEL_FIRE_ADDR, $fb, 16, [ref]$fn)) {
            $fire = [int]($fb[0] -ne 0)
            # TEL_FIRE_ADDR2 is the first of the five hardpoint fire bytes (0x5367de..0x5367e2)
            $off2 = $script:TEL_FIRE_ADDR2 - $script:TEL_FIRE_ADDR
            if ($script:TEL_FIRE_ADDR2 -ne 0 -and $off2 -ge 0 -and ($off2 + 4) -lt 16) {
                for ($i = 0; $i -lt 5; $i++) { if ($fb[$off2 + $i] -ne 0) { $fire = $fire -bor 2 } }
            }
        }
    }

    # The ENGINE's own FFB state. 0x52bbd0 is its "force feedback device present"
    # flag, set once at startup. It matters here because the engine's weapon-fire
    # path calls into I7_SFRCE.DLL WITHOUT null-checking its effect object: if we
    # have taken the device exclusively, the effect handle underneath is dead and
    # the next shot faults at I7_SFRCE.DLL+0x2505 (0xC0000005). Confirmed twice in
    # the field, and predicted in docs/records/FFB-LAPTOP-RECON.md.
    $gameFfb = 0
    $gb = $Ctx.FireBuf
    $gn = 0
    if ([I76Tel]::ReadProcessMemory($Ctx.H, [IntPtr]0x52bbe4, $gb, 4, [ref]$gn)) {
        $gameFfb = [BitConverter]::ToInt32($gb, 0)
    }

    # ---- the engine's own effect slots -----------------------------------
    # A slot going 0 -> 1 is an effect STARTING: that is the event. Reading the
    # engine's decision rather than an input byte is what finally made weapon
    # feedback work.
    $fxFired = @()
    $fxActive = 0
    $fb2 = $Ctx.FxBuf
    $fn2 = 0
    if ([I76Tel]::ReadProcessMemory($Ctx.H, [IntPtr]$script:TEL_FX_BLOCK, $fb2, $fb2.Length, [ref]$fn2)) {
        # ENGINE RPM, at block +0x0C. Found by a whole-memory alternating scan
        # (ffb-find-rpm-wide.ps1): idle -> full revs -> idle -> full, in neutral.
        # It read 1050 -> 5998 -> 1050 -> 5999 against a dashboard tach showing
        # roughly 1.4k -> 6.1k, and nothing else in 794 survivors read in rpm
        # units at all.
        #
        # It is not in the vehicle entity - which is why every struct scan missed
        # it - but in the FFB EFFECT PARAMETER BLOCK. That is the answer to "where
        # does the native force feedback get its data": the game's own FFB is fed
        # engine speed. Bypassing the CALL at 0x52bbe4 does not stop the block
        # being filled, so this stays readable with the interposer running.
        #
        # Fixed address in the EXE's data section, so no pointer chase and no
        # per-run offset.
        $rpm = [BitConverter]::ToInt32($fb2, 0x0C)
        if ($rpm -lt 0 -or $rpm -gt 20000) { $rpm = 0 }   # block not yet filled
        $Ctx.Rpm = $rpm

        # ---- GEAR SHIFTS, without a gear variable ---------------------------
        # No gear field was ever found, and none is needed. An upshift is the one
        # thing in the whole car that makes ENGINE speed fall while ROAD speed
        # does not - the same sawtooth a whole memory scan was built to hunt for,
        # now just two numbers already in hand.
        #
        # The speed condition is what makes this honest. Revs also fall every time
        # the driver lifts off, and that is not a shift: on a lift the car slows
        # with the engine, on a shift it does not.
        #
        # A downshift is the mirror image - revs jump while road speed does not
        # rise - and needs a higher threshold, because ordinary acceleration
        # raises revs too and only a shift does it near-instantly.
        #
        # Differentiated against the SIM TICK, not the poll: at 20 Hz a poll-rate
        # derivative would divide a real rev change by a fraction of the interval
        # that produced it and read several times too fast.
        #
        # The decision itself is in Tel-DetectShift so it can be tested against
        # synthetic traces without a running game - the same reason Tel-Slip was
        # extracted. The risky part here is not the thresholds (rpmRate is logged,
        # so a real drive can replace those with numbers) but the LOGIC: telling a
        # shift from a lift-off, and firing once rather than every frame.
        $Ctx.Shift = 0
        if ($tickAdvanced -and $tickDt -gt 0) {
            $sh = Tel-DetectShift -Rpm $rpm -LastRpm $Ctx.LastRpm -Speed $speed `
                                  -LastSpeed $Ctx.LastSpeedShift -Dt $tickDt -Hold $Ctx.ShiftHold
            $Ctx.Shift     = $sh.Shift
            $Ctx.RpmRate   = $sh.RpmRate
            $Ctx.ShiftHold = $sh.Hold
            $Ctx.LastRpm = $rpm
            $Ctx.LastSpeedShift = $speed
        }
        for ($si = 0; $si -lt $script:TEL_FX_SLOTS; $si++) {
            $bo = $script:TEL_FX_BASE + $si * $script:TEL_FX_STRIDE
            $act = [BitConverter]::ToInt32($fb2, $bo)
            $id  = [BitConverter]::ToInt32($fb2, $bo + 0x0C)
            $mag = [BitConverter]::ToInt32($fb2, $bo + 0x14)
            if ($act -ne 0) { $fxActive++ }
            # A slot STAYS active between shots - measured, slots were non-zero on
            # 93% of samples across a 152 s drive - so a plain 0 -> 1 edge misses
            # every repeat fire in the same slot. Treat a changed id or magnitude
            # while active as a new event too.
            if ($act -ne 0 -and ($Ctx.FxPrev[$si] -eq 0 -or
                                 $Ctx.FxPrevId[$si] -ne $id -or
                                 $Ctx.FxPrevMag[$si] -ne $mag)) {
                $fxFired += [pscustomobject]@{
                    Slot = $si
                    Id   = $id
                    Param= [BitConverter]::ToSingle($fb2, $bo + 0x10)
                    Mag  = $mag
                }
            }
            $Ctx.FxPrev[$si] = $act
            $Ctx.FxPrevId[$si] = $id
            $Ctx.FxPrevMag[$si] = $mag
        }
    }

    # The engine's own gear and rpm win over the FFB-block copy and the rpm-sawtooth
    # detector: those need the block, which is only written while the 1997 DLL holds a
    # device (see Tel-Extras). Gear changes are then exact (eng+0x08 2 -> 3 is an upshift).
    if ($xt.RpmF -gt 0) { $Ctx.Rpm = [int]$xt.RpmF }
    if ($xt.Gear -ge 0) { $Ctx.Shift = $xt.GearShift }

    $understeer = $slip.Understeer
    $oversteer  = $slip.Oversteer

    return [pscustomobject]@{
        T           = $t
        Ent         = $Ctx.Ent
        Speed       = $speed
        SpeedMph    = $speed * 2.23694
        Vx          = $vx; Vy = $vy; Vz = $vz
        YawRate     = $yawRate
        AngVelX     = $angVelX
        AngVelZ     = $angVelZ
        # Rotation about the two non-vertical axes, combined. In this engine that
        # means "the car is being knocked about" - hits and airtime - not
        # suspension travel. Used as a secondary impact/airtime cue.
        Tumble      = ([math]::Abs($angVelX) + [math]::Abs($angVelZ))
        FireRaw     = $fire
        Firing      = ($fire -ne 0)
        # Effects the ENGINE started this frame, and how many are running.
        FxFired     = $fxFired
        FxActive    = $fxActive
        # True when the engine started any effect this frame - the reliable
        # "something happened" signal that the input flag never delivered.
        FxEvent     = ($fxFired.Count -gt 0)
        # Nonzero = the engine also has a live FFB device, so FIRING WILL CRASH IT
        # while we hold the wheel. See the note above.
        GameFfb     = $gameFfb
        Steer       = $steer
        Throttle    = $throttle
        # derived
        LongAccel   = $Ctx.LongAccel
        LongG       = $Ctx.LongAccel / 9.81
        HeaveAccel  = $Ctx.VyRate
        WorldAccelX = $Ctx.WAx
        WorldAccelY = $Ctx.WAy
        WorldAccelZ = $Ctx.WAz
        # Direction of travel in the world XZ plane, radians. Used as the heading
        # PROXY for motion-sim export: the engine exposes no orientation, and for a
        # car the velocity direction and the facing direction differ only by the
        # slip angle - which in this engine is near zero outside a spin.
        # Rate the VELOCITY vector rotates, and how far that is from the rate the
        # CAR rotates. Slide is the sideslip signal - see the note above.
        Rpm         = $Ctx.Rpm
        RpmRate     = $Ctx.RpmRate
        Shift       = $Ctx.Shift      # +1 upshift, -1 downshift, 0 otherwise
        HeadingRate = $Ctx.HeadingRate
        Slide       = $Ctx.Slide
        HeadingApprox = $(if ($speed -gt 1.0) { [math]::Atan2($vx, $vz) } else { 0.0 })
        LatAccel    = $latAccel
        LatG        = $latAccel / 9.81
        ExpectedYaw = $expectedYaw
        Understeer  = $understeer
        Oversteer   = $oversteer
        Jolt        = $Ctx.Jolt
        # Climb angle of the VELOCITY vector, radians. There is no usable
        # orientation in the entity (no rotation matrix - see the header), but the
        # direction of travel carries the terrain: vy/|v| is the sine of the slope
        # being driven. Motion rigs use this as the pitch cue. Zero when too slow
        # for the ratio to mean anything.
        TravelPitch = $(if ($speed -gt 2.0) {
                          $r = $vy / $speed
                          if ($r -gt 1.0) { $r = 1.0 } elseif ($r -lt -1.0) { $r = -1.0 }
                          [math]::Asin($r)
                        } else { 0.0 })
        # ---- 2026-10-24 (Tel-Extras) ----
        Flags          = $xt.Flags
        EngineRunning  = (($xt.Flags -band 0x1) -ne 0)
        EngineStarting = (($xt.Flags -band 0x8) -ne 0)
        SkidFlag       = (($xt.Flags -band 0x2) -ne 0)      # full slide (bit 2 of +0x454)
        DriftFlag      = (($xt.Flags -band 0x2000) -ne 0)   # the drift band: velocity kept, body yaws on
        AirFlag        = (($xt.Flags -band 0x4) -ne 0)
        OilFlag        = (($xt.Flags -band 0x400) -ne 0)
        Surface        = $xt.Surface
        Paved          = $xt.Paved
        SurfaceGrip    = $xt.SurfaceGrip
        Gear           = $xt.Gear
        SteerK         = $xt.SteerK
        LatCap         = $xt.LatCap
        Shots          = $xt.Shots
        ShotSource     = $xt.ShotSource
        Hits           = $xt.Hits
        WeaponRow      = $xt.WeaponRow
        WeaponCycle    = $xt.WeaponCycle
        Ammo           = $xt.Ammo
        Braking     = ($throttle -lt -0.05)
        Airborne    = ([math]::Abs($vy) -gt 2.0)
        Wheelbase   = $Ctx.Wheelbase
        # Seconds since the sim last advanced. The engine STOPS TICKING when the
        # window loses focus or the game is paused, but our force loop keeps
        # running on wall-clock time - so without this the oscillators free-run on
        # frozen telemetry and the wheel buzzes at a car that is not moving.
        # Field-reported: "+/-130 even when the game is not even focused".
        SinceTick   = $(if ($Ctx.LastTickT -gt 0) { $t - $Ctx.LastTickT } else { 0.0 })
        Ticks       = $Ctx.Ticks
        Polls       = $Ctx.Polls
    }
}

function Tel-SetEngineFfb {
    <#
      Turn the ENGINE's own force feedback on or off, in memory, reversibly.

      WHY THIS EXISTS: the engine's weapon-fire path dereferences its DirectInput
      effect object without a null check, so once we hold the wheel exclusively the
      first shot faults at I7_SFRCE.DLL+0x2505 and the game dies. Confirmed twice
      in the field.

      WHY A SINGLE FLAG IS ENOUGH, and why no code is patched: 0x52bbd0 is the
      engine's "FF device present" flag, and DISASSEMBLY OF ALL SIX READ SITES
      shows every one of them gates on it and bails cleanly when it is zero:

          0x445B10  test eax,eax / je   -> skips the effect call
          0x445B40  test eax,eax / je   -> ret
          0x445B60  cmp  ecx,eax / je   -> ret
          0x445B80  test eax,eax / je   -> ret
          0x445BA0  cmp  eax,edi / je   -> jumps straight to the epilogue
          0x445F70  cmp  eax,esi / jne  -> xor eax,eax; ret     (the play path)

      So zeroing it makes the whole subsystem a no-op: the effect object is never
      touched, so there is nothing to dereference. That is strictly safer than
      NOPing the init call at 0x402F93, which would leave the DLL unloaded and the
      surrounding state half-built, and far safer than patching the DLL itself.

      Writes 4 bytes to .data. No file is modified and no code is changed.
      Returns the PREVIOUS value so the caller can put it back.
    #>
    param($Ctx, [int]$Value)
    # Writes 0x52bbe4 - the I7FF_SIM_Effect FUNCTION POINTER - not 0x52bbd0.
    #
    # Both stop the crash, but only this one leaves the engine's own effect
    # decisions readable. Disassembly of the dispatcher at 0x446110:
    #
    #     mov  eax, [0x52bbe4]              ; the DLL entry point
    #     test eax, eax
    #     je   0x446155                     ; <- the engine ALREADY tolerates null
    #     push 0x4f2328                     ; one argument: the param block
    #     mov  dword ptr [0x4f2328], 0x16c  ; 364 = sizeof(struct)
    #     call eax
    #
    # Zeroing 0x52bbd0 made the gated callers bail long BEFORE this, so the param
    # block was never filled and the engine's events were invisible. Zeroing the
    # pointer instead lets every effect be built and merely skips the call into
    # I7_SFRCE.DLL - which is where the fault at +0x2505 lives. So: no crash, and
    # 0x4f2328 becomes a live feed of what the engine wanted the wheel to do.
    # See tools/ffb/ffb-watch-effects.ps1.
    #
    # Value 0 disables; pass the saved pointer back to restore.
    $old = Tel-ReadInt $Ctx 0x52bbe4
    $buf = [BitConverter]::GetBytes([int]$Value)
    $n = 0
    $ok = [I76Tel]::WriteProcessMemory($Ctx.H, [IntPtr]0x52bbe4, $buf, 4, [ref]$n)
    if (-not $ok -or $n -ne 4) { throw "could not write 0x52bbe4 (I7FF_SIM_Effect pointer)" }
    return $old
}

function Tel-Close {
    param($Ctx)
    if ($Ctx -and $Ctx.H -ne [IntPtr]::Zero) { [void][I76Tel]::CloseHandle($Ctx.H) }
}
