<#
  FfbMixer.ps1 - turn vehicle telemetry into one steering force.

  Telemetry.ps1 reads the car; FfbCore.ps1 drives the wheel; this decides what
  the wheel should DO. Kept separate so the force model can be rewritten without
  touching either the memory reads or the DirectInput plumbing.

      . tools\ffb\FfbMixer.ps1
      $mix = Mix-New
      $out = Mix-Update $mix $sample      # $out.Force is -10000..10000
      $out.Channels                        # per-channel breakdown, for the panel

  ---------------------------------------------------------------------------
  WHAT THIS ENGINE ACTUALLY SIMULATES (measured, and it changes the design)
  ---------------------------------------------------------------------------
  I'76 has NO TYRE MODEL. Measured over two real drives, the yaw rate is whichever
  of two limits binds - steering geometry below 27 mph, a lateral-acceleration
  ceiling above it (see docs/HANDLING-MODEL.md and Telemetry.ps1's header):

      yaw = sign(steer) * min( (v/L)*tan(|steer|*0.76), 31.0*|steer|/v )

  Above the crossover that upper branch means latAccel = 31.0 * steer: lateral g is
  proportional to steering input and INDEPENDENT of speed. The engine treats the
  wheel as a lateral-acceleration command.

  So understeer and oversteer in the sim-racing sense DO NOT OCCUR in normal
  driving: the car does precisely what it is asked, every frame. Two consequences
  the force model has to respect rather than pretend away:

   1. The `corner` channel is COLLINEAR with `center` - both are proportional to
      steering input. It reshapes the weight curve; it carries no independent
      information about grip, because there is no grip to have information about.

   2. The slip channels are really a LOSS-OF-CONTROL detector. What does happen in
      this game is spins, impacts and blown tyres, and those show as large
      deviations from the lateral-g relation (40 of 783 samples on a real drive,
      every one a spin or a hit). That is a genuinely useful signal here - you get
      spun by mines and rammed constantly - it just is not tyre slip.

  The note below on self-aligning torque still governs how those are EXPRESSED:
  when the car stops obeying the wheel, the wheel goes light.

  ---------------------------------------------------------------------------
  THE ONE IDEA THAT MATTERS: LOSING THE CAR MAKES THE WHEEL GO *LIGHT*
  ---------------------------------------------------------------------------
  The obvious way to signal slip is to add force - buzz the wheel when the car
  loses grip. That is backwards, and it is why a lot of custom FFB feels like a
  rumble pack bolted to a wheel.

  On a real car the weight you feel in your hands IS the front tyres' self-
  aligning torque, and that torque is a product of the slip angle. As a tyre
  approaches its limit the torque peaks and then COLLAPSES - past the peak the
  contact patch is sliding, not gripping, and it stops pushing back. Every
  driver knows the sensation: the wheel goes dead and light just before the nose
  runs wide.

  So understeer here does not add a signal. It ATTENUATES the steady channels
  (see $GripScale). You feel grip leave. That is the single most communicative
  thing a wheel can do, it needs no new effect primitive, and it is free.

  Oversteer is the opposite case and does add force - in the direction of the
  slide, because that is the direction the caster would drag the wheel and it is
  the correction you want to make anyway.

  ---------------------------------------------------------------------------
  HIERARCHY AND RESTRAINT (borrowed from the pad rumble mixer, i76-remap.ahk)
  ---------------------------------------------------------------------------
  That mixer works because continuous states are held LOW so transients read on
  top of them. Same discipline here:
    * steady channels (centering, cornering) are the floor and stay moderate;
    * texture rides on top at low amplitude, scaled by speed;
    * transients (impacts, kerbs, gunfire) are allowed to be loud because they
      are short and rare.
  If the steady floor is set loud, every transient disappears into it and the
  wheel just feels heavy and mute. Resist raising the gains to feel "more".

  ---------------------------------------------------------------------------
  ONE OUTPUT PRIMITIVE
  ---------------------------------------------------------------------------
  This wheel refuses periodic effects (CreateEffect(GUID_Sine) returns
  REGDB_E_CLASSNOTREG - see tools/ffb/README.md), so everything is summed into a
  single constant force that is rewritten every loop:

      force = steady + texture * osc(phase) + transients

  Vibration is therefore synthesised by ALTERNATING part of the sum, never by
  flipping the whole sum - flipping everything would cancel the steady feel and
  turn cornering load into a rattle.
#>

# ---------------------------------------------------------------------------
# Tunables. Every one of these is a feel decision, not a measurement, so they
# live in one table that the panel can edit live and save.
# ---------------------------------------------------------------------------
function Mix-DefaultTune {
    return @{
        Master        = 1.00   # global scale, 0..1. The kill switch is separate.

        # --- steady: centering / self-aligning torque -----------------------
        # RAISED 2026-08-08 after the first real drives read barely perceptible.
        # Reference points that decide these numbers:
        #   * the ENGINE'S OWN effects command +/-100 percent - full scale - for
        #     cannon fire, explosions and tyre blowouts (tools/ffb/parse-frc.py).
        #     We were peaking at 25% and typically running at 4.6%.
        #   * sim-racing practice puts normal cornering at 40-70% of range, with
        #     only kerbs and impacts near the ceiling.
        # At full lock and full speed authority the steady pair now sums to about
        # 8200 of a 9500 clamp; at half lock, roughly 4100 - which is the band.
        SatGain       = 5200   # force at full lock, at or above SatRef speed
        SatRef        = 9.0    # m/s at which centering reaches full authority.
                               # Lowered from 12: I'76's crossover is 12 m/s and a
                               # lot of driving happens below it, where the old
                               # curve left the wheel nearly dead.
        SatFloor      = 0.28   # fraction of SatGain kept at a standstill. 0.10 was
                               # too little - parking-speed steering had no weight
                               # at all, which reads as broken rather than light.

        # --- steady: cornering load ----------------------------------------
        # CornerRef was 0.55 g, which is a road-car number and WRONG for this
        # engine: measured lateral g runs to 2.99 at full lock (latAccel =
        # 29.3 * steer, see Telemetry.ps1), so 0.55 saturated this channel at 97%
        # of cornering samples - the wheel would have been one constant heavy
        # weight with no variation whatsoever.
        #
        # CornerGain is also deliberately lower than it looks like it should be.
        # Because lateral g is EXACTLY proportional to steering input in this
        # engine, this channel is collinear with `center` - it is not an
        # independent grip signal the way it would be in a game with a tyre model.
        # The two together give steer * (constant + f(speed)), which is a useful
        # reshaping, but gaining both up just doubles one force.
        CornerGain    = 3400   # force at CornerRef lateral g
        CornerRef     = 2.80   # lateral g treated as "fully loaded" (measured max 2.99)

        # --- slip ----------------------------------------------------------
        UndersteerDrop = 0.75  # how much grip loss bleeds the steady channels.
                               # 0.75 = at full understeer, 25% weight remains.
        ScrubGain     = 900    # tyre-scrub buzz amplitude at full understeer
        ScrubHz       = 14.0
        OversteerGain = 3600   # counter-steer push at full oversteer

        # --- road texture ---------------------------------------------------
        # NYQUIST NOTE: the force loop tops out near 62 Hz (Start-Sleep
        # granularity - see ffb-interposer.ps1), so every oscillator frequency
        # here stays at or under ~15 Hz to keep 4+ samples per cycle. Set one to
        # 22 Hz and you do not get a 22 Hz buzz, you get an aliased beat that
        # feels like a fault in the wheel.
        TextureGain   = 1500   # amplitude at TexRef speed over rough ground
        TexRef        = 16.0   # m/s at which texture is at full amplitude
        TextureHz     = 11.0
        RoughRef      = 10.0   # jolt treated as fully rough. Measured away from
                               # collisions: p50 2.6 / p75 9.3 / p90 15.9. 16 put
                               # ordinary driving at the very bottom of the curve.
        # Fraction of texture amplitude present regardless of roughness. WAS 0.25,
        # and that was the whole problem: measured on a real drive, 93% of the
        # texture amplitude was this constant term and only 7% was road. The
        # channel was a speed-driven hum wearing a road-texture label - which is
        # exactly what "noisy, bounces around, I can't tell surfaces apart" is.
        # At 0.06 it is a whisper of presence and the road carries the rest.
        TextureFloor  = 0.06
        BumpGain      = 1400   # vertical-motion component (Vy)

        # --- braking --------------------------------------------------------
        BrakeGain     = 2200   # weight added under deceleration
        BrakeRef      = 0.60   # longitudinal g treated as "hard braking"
        JudderGain    = 1300   # lockup shimmy under heavy braking
        JudderHz      = 12.0

        # --- transients -----------------------------------------------------
        ImpactGain    = 9000   # peak force of a full-scale collision
        # ImpactRef was 55, which put the trigger (ImpactRef*0.25) at 13.75 - right
        # on jolt's p90. On a real drive that fired 71 times in 77 seconds, roughly
        # once a second: a constant hammering, not collisions. The measured jolt
        # distribution has an empty gap between 40 and 60, so a trigger at 50 is a
        # natural break; it yields 6 events on the same drive, matching five
        # distinct collisions at t = 14.1, 17.0, 23.3, 28.6 and 34.6 s.
        # Full scale at 200 leaves the biggest observed hit (579) saturating.
        ImpactRef     = 200.0  # jolt treated as a full-scale impact; trigger at 25% of this
        ImpactMs      = 260    # decay time of an impact
        KerbGain      = 2500

        # --- weapon fire ----------------------------------------------------
        # Shaped from the engine's OWN authored effects (tools/ffb/parse-frc.py):
        # CANNON1..4 are UserDefined envelopes, EXPLOSN is a SawtoothDown, and the
        # weapon UI clicks are SquareHigh - i.e. short, sharp, percussive. So a
        # brief decaying buzz rather than a directional shove: a centrally-mounted
        # gun has no side to kick towards, and guessing one reads as a fault.
        WeaponGain    = 3400
        WeaponMs      = 140
        WeaponHz      = 13.0
        # Minimum gap between weapon kicks, ms. TWO fire flags are watched
        # (0x5367D0 and 0x5367DE - see Telemetry.ps1) because which one is the
        # input and which is downstream is not established. If they rise on the
        # same shot, without this the wheel would kick twice per trigger pull.
        WeaponBlankMs = 70

        # --- LFE / bass-shaker channel (bus only - no wheel output) ---------
        # Parametric low-frequency content for a tactile transducer.
        #
        # THE BAND. Puck-style shakers (Dayton BST-1, Aura AST-2B) are 20-80 Hz
        # devices with a resonance hump at 30-40 Hz; ButtKickers reach lower but
        # the practical design band is 20-100 Hz with the strongest output around
        # 30-50 Hz. Below ~20 Hz is an excursion hazard, not a feature - ButtKicker
        # warns infrasonic content can damage the driver - so nothing here is
        # authored below 25 Hz and ffb-lfe.ps1 high-passes at 22 Hz regardless.
        #
        # SEPARATION IS THE DESIGN RULE. Concurrent effects must sit apart in
        # frequency or they mask each other and the reader cannot tell them apart.
        # The two CONTINUOUS channels get non-overlapping bands, and the two
        # TRANSIENTS are further distinguished by envelope (a one-shot against a
        # steady hum reads as separate even where bands are close):
        #
        #     engine   25 -> 45 Hz   continuous, low        (the background)
        #     road     50 -> 70 Hz   continuous, noise bed  (above the engine)
        #     impact   32 Hz         one-shot, heavy thump
        #     weapon   85 Hz         one-shot, sharp crack
        #
        # An earlier version had the engine sweeping 24->52 Hz straight THROUGH
        # both transient frequencies, which is exactly the collision this avoids.
        #
        # Engine pitch tracks SPEED, not RPM, because the engine exposes no RPM.
        # The physically correct fundamental is the firing frequency
        # (RPM * cylinders / 120), which leaves the shaker band by mid-revs anyway,
        # so the standard practice is to compress idle->redline into ~25-55 Hz and
        # let amplitude carry load. Speed is a serviceable stand-in for that curve.
        LfeEngineIdleHz = 25.0  # fundamental at standstill
        LfeEngineMaxHz  = 45.0  # fundamental at LfeEngineRefSpd
        LfeEngineRefSpd = 40.0  # m/s at which the fundamental tops out
        LfeEngineAmp    = 0.45  # amplitude at full throttle
        LfeEngineJitter = 0.06  # +/- fraction of pitch wander. A perfectly steady
                                # tone numbs the skin and masks transients; ShakeIt
                                # ships noise randomisation for exactly this reason.
        LfeRoadLoHz     = 50.0  # road noise bed, quiet end
        LfeRoadHiHz     = 70.0  # road noise bed, rough end
        LfeRoadAmp      = 0.50  # road-rumble amplitude at RoughRef jolt
        LfeImpactAmp    = 1.00  # impact thump amplitude at full-scale jolt
        LfeImpactHz     = 32.0
        LfeWeaponHz     = 85.0

        # --- safety ---------------------------------------------------------
        # MIN FORCE - the single most likely reason this read "barely
        # perceptible" before. The T300 is BELT-DRIVEN, and belt and gear drives
        # have static friction that simply swallows low-amplitude signal: below
        # some threshold the motor is commanded but the rim does not move. iRacing
        # ships exactly this control and describes it as increasing "the feeling of
        # smaller forces without affecting the steering weight or larger forces",
        # and recommends its LINEAR mode for direct drive ONLY - a belt wheel wants
        # the non-linear boost.
        #
        # So any non-zero output is lifted to at least MinForce and the rest of the
        # range is compressed above it, which preserves ordering and the sign while
        # moving the quiet end above stiction. Set to 0 for a direct-drive wheel.
        # Measure your own floor with toolsfbfb-bench.ps1 rather than guessing.
        MinForce      = 900    # ~9% of clamp
        # ...but only for forces MEANT to be felt. Without this gate, MinForce
        # lifts the always-on texture ripple (active ~99% of the time at ~110)
        # straight to 900, and the wheel hums constantly: replaying a real drive
        # showed near-silence collapse from 61% of samples to 0.2%. A permanent
        # floor is precisely the "continuous states buried the transients" failure
        # this design is built to avoid. Below the gate the force is meant to be
        # imperceptible, so leave it there.
        MinForceGate  = 150
        Clamp         = 9500   # never exceed this; leaves headroom under 10000
        # Thermal idle guard. Thrustmaster documents thermal cut-back (KB 1744):
        # sustained load makes force feedback weaken and the base heat up. This
        # layer holds an always-on constant force, so a wheel left parked off-centre
        # - at a menu, mid-mission, walked away from - would push against its stop
        # indefinitely for no benefit. After this many seconds stationary the output
        # fades out, and comes straight back the moment the car moves.
        IdleFadeAfter = 20.0   # seconds stationary before fading
        IdleFadeOver  = 2.0    # seconds to fade out over
        RampMs        = 700    # fade in over this long on start / after a pause
        SlewMax       = 2600   # max force change per SECOND of steady output.
                               # Transients bypass this - see Mix-Update.
    }
}

function Mix-New {
    param($Tune = $null)
    if (-not $Tune) { $Tune = Mix-DefaultTune }
    return [pscustomobject]@{
        Tune       = $Tune
        Phase      = 0.0        # texture oscillator phase, radians
        ScrubPhase = 0.0
        JudderPhase= 0.0
        Transients = New-Object System.Collections.ArrayList
        LastForce  = 0.0
        LastT      = 0.0
        StartT     = -1.0
        Enabled    = $true
        PeakForce  = 0.0
        LastJolt   = 0.0
        LastFiring = $false
        LastFireT  = -10.0
        StillSince = -1.0
    }
}

function Mix-Trigger {
    <#
      Queue a transient. Shape is 'jolt' (sharp attack, exponential decay) or
      'buzz' (decaying oscillation). Amp is signed for 'jolt' so an impact can
      have a direction.
    #>
    param($Mix, [string]$Shape, [double]$Amp, [int]$Ms, [double]$Hz = 30.0, [string]$Kind = 'impact')
    $null = $Mix.Transients.Add([pscustomobject]@{
        Shape = $Shape; Amp = $Amp; Ms = $Ms; Hz = $Hz; Start = $Mix.LastT; Kind = $Kind
    })
}

function Mix-Update {
    <#
      One force decision. $Sample is a Tel-Sample result. Returns:
        .Force     int, -10000..10000, ready for Ffb-Constant
        .Channels  ordered hashtable of each channel's contribution
        .Notes     short strings describing anything notable this frame
    #>
    param($Mix, $Sample, $Active = $null)

    # Channel gating (-Only / -Mute) belongs HERE, not in the caller.
    #
    # ffb-interposer.ps1 used to honour those flags by re-summing $out.Channels
    # itself. That silently bypassed the slew limiter: $Channels holds the values
    # as computed, but the rate limit further down is applied to THIS function's
    # own running sum. So every live run was driving the wheel with unrate-limited
    # steady force, and only the returned .Force - which nothing used - was
    # correct. Gating inside keeps one code path for the force that reaches the
    # device.
    #
    # $Channels still reports the true computed value of a muted channel, so the
    # panel can show what it would have contributed.
    $gate = @{}
    foreach ($k in @('center','corner','oversteer','brake','texture','scrub','judder','impact','weapon')) {
        $gate[$k] = if ($null -eq $Active) { $true } else { [bool]$Active[$k] }
    }

    # NOT named $T. PowerShell variable names are CASE-INSENSITIVE, so $T and the
    # timestamp $t below are the same variable - naming this $T silently replaced
    # the whole tune table with a number, every gain read back as $null, and
    # 0/$null produced NaN forces. Caught by ffb-mixer-test.ps1, which is the
    # entire reason that file exists.
    $Tune = $Mix.Tune
    $t = $Sample.T
    $dt = if ($Mix.LastT -gt 0) { $t - $Mix.LastT } else { 0.016 }
    if ($dt -le 0 -or $dt -gt 0.5) { $dt = 0.016 }
    $Mix.LastT = $t
    if ($Mix.StartT -lt 0) { $Mix.StartT = $t }

    $ch = [ordered]@{}
    $notes = @()

    # ---- grip scale: the collapse of self-aligning torque -----------------
    # See the header. Losing the car bleeds the steady channels toward silence
    # instead of adding a signal of its own.
    #
    # Driven by EITHER understeer or oversteer, because in this engine understeer
    # effectively never happens. Replaying a real 959-sample drive
    # (ffb-replay.ps1) showed Understeer never once exceeded 0.3, so a gripScale
    # keyed on understeer alone sat at exactly 1.0 for the entire drive and the
    # whole "the wheel goes light" idea was inert. Oversteer - spins, impacts,
    # blown tyres - fired on 4.9% of samples and is what actually occurs.
    #
    # Physically this is the same event: in a spin the front tyres stop generating
    # alignment torque, so the wheel goes light. The oversteer channel then loads
    # up in the counter-steer direction on top of that, which is exactly how
    # catching a slide feels - dead, then a push toward the correction.
    $outOfShape = [math]::Max($Sample.Understeer, $Sample.Oversteer)
    $gripScale = 1.0 - ($outOfShape * $Tune.UndersteerDrop)
    $ch['grip%'] = [math]::Round($gripScale * 100)

    # ---- 1. centering / self-aligning torque ------------------------------
    # Opposes the steering input, so the wheel pushes back toward centre. Rises
    # with speed and saturates: at a crawl there is almost nothing, which is
    # correct - a parked car's heavy steering is friction, not caster.
    $spdN = [math]::Min(1.0, $Sample.Speed / $Tune.SatRef)
    $satAuthority = $Tune.SatFloor + (1.0 - $Tune.SatFloor) * $spdN
    $sat = -$Sample.Steer * $Tune.SatGain * $satAuthority * $gripScale
    $ch['center'] = [int]$sat

    # ---- 2. cornering load -------------------------------------------------
    # Lateral g pushes the wheel against the direction of rotation. This is the
    # channel that makes a bend feel like it has weight.
    $latN = [math]::Min(1.0, [math]::Abs($Sample.LatG) / $Tune.CornerRef)
    $corner = 0.0
    if ([math]::Abs($Sample.YawRate) -gt 0.001) {
        $corner = -[math]::Sign($Sample.YawRate) * $latN * $Tune.CornerGain * $gripScale
    }
    $ch['corner'] = [int]$corner

    # ---- 3. oversteer counter-steer ---------------------------------------
    # Pushes toward the correction. Deliberately NOT scaled by gripScale: this
    # channel exists because grip was lost.
    $over = 0.0
    if ($Sample.Oversteer -gt 0.01) {
        $over = [math]::Sign($Sample.YawRate) * $Sample.Oversteer * $Tune.OversteerGain
        if ($Sample.Oversteer -gt 0.35) { $notes += "OVERSTEER" }
    }
    $ch['oversteer'] = [int]$over

    # ---- 4. braking weight -------------------------------------------------
    # Deceleration transfers weight onto the front axle, which loads the tyres
    # and adds steering weight. Sign follows the existing steering direction so
    # it reinforces whatever the wheel is already doing rather than yanking.
    $brake = 0.0
    if ($Sample.LongG -lt -0.05) {
        $brakeN = [math]::Min(1.0, (-$Sample.LongG) / $Tune.BrakeRef)
        $brake = -[math]::Sign($Sample.Steer) * $brakeN * $Tune.BrakeGain
        if ($brakeN -gt 0.7) { $notes += "HARD BRAKE" }
    }
    $ch['brake'] = [int]$brake

    if (-not $gate['center'])    { $sat = 0.0 }
    if (-not $gate['corner'])    { $corner = 0.0 }
    if (-not $gate['oversteer']) { $over = 0.0 }
    if (-not $gate['brake'])     { $brake = 0.0 }
    $steady = ($sat + $corner + $over + $brake)

    # ---- 5. road texture (oscillating) ------------------------------------
    # Amplitude scales with speed AND with how much the suspension is actually
    # working, so smooth tarmac at speed stays calm while broken ground at the
    # same speed comes alive. That is what "faster and bumpier feels more
    # intense" has to mean - speed alone would just be a constant hum.
    # Roughness comes from JOLT - the frame-to-frame change in the velocity vector -
    # and NOT from roll/pitch rate, which is what this used to read. Measured over a
    # real drive, the engine has no suspension model: those fields sit at p50 0.000
    # / p90 0.10 and only move when you hit something, so a texture channel driven
    # off them was silent exactly when texture is supposed to be present.
    #
    # Jolt away from collisions has a genuine working range - p50 2.6, p75 9.3,
    # p90 15.9 - so RoughRef maps that band onto 0..1. Large jolts are handled
    # separately by the impact transient, so this is deliberately clamped well
    # below collision magnitudes.
    $rough = [math]::Min(1.0, $Sample.Jolt / $Tune.RoughRef)
    # Vy peaked at 0.77 m/s across 77 s of driving, so the old /3.0 divisor made
    # this term all but unreachable.
    $heave = [math]::Min(1.0, [math]::Abs($Sample.Vy) / 0.8)
    $texN  = [math]::Min(1.0, $Sample.Speed / $Tune.TexRef)
    $texAmp = ($Tune.TextureGain * $texN * ($Tune.TextureFloor + (1.0 - $Tune.TextureFloor) * $rough)) + ($Tune.BumpGain * $heave * $texN)
    $Mix.Phase += 2 * [math]::PI * $Tune.TextureHz * $dt
    if ($Mix.Phase -gt (2 * [math]::PI)) { $Mix.Phase -= 2 * [math]::PI }
    $texture = $texAmp * [math]::Sin($Mix.Phase)
    $ch['texture'] = [int]$texture

    # ---- 6. tyre scrub buzz (understeer) ----------------------------------
    # A small, fast buzz on top of the LIGHTNESS. The lightness is the primary
    # cue; this just adds the sound-of-rubber quality so it reads as sliding
    # rather than as a broken FFB cable.
    # Keyed on $outOfShape, not on Understeer. Same reason as gripScale above: on a
    # real drive this channel NEVER FIRED ONCE, because understeer does not exist
    # in this engine. Tyres scrubbing sideways is exactly what happens in a spin,
    # so the buzz belongs on the signal that actually occurs.
    $scrub = 0.0
    $scrubAmp = 0.0
    if ($outOfShape -gt 0.15) {
        $scrubAmp = $Tune.ScrubGain * $outOfShape
        $Mix.ScrubPhase += 2 * [math]::PI * $Tune.ScrubHz * $dt
        if ($Mix.ScrubPhase -gt (2 * [math]::PI)) { $Mix.ScrubPhase -= 2 * [math]::PI }
        $scrub = $Tune.ScrubGain * $outOfShape * [math]::Sin($Mix.ScrubPhase)
        if ($Sample.Oversteer -gt 0.4) { $notes += "SPIN" }
        elseif ($Sample.Understeer -gt 0.4) { $notes += "PLOUGHING" }
    }
    $ch['scrub'] = [int]$scrub

    # ---- 7. brake judder ---------------------------------------------------
    # No ABS in 1997. Under heavy braking the wheels lock and release, and that
    # shimmy is a genuine cue that you are past the limit.
    $judder = 0.0
    $judderAmp = 0.0
    if ($Sample.LongG -lt -0.45 -and $Sample.Speed -gt 4) {
        $Mix.JudderPhase += 2 * [math]::PI * $Tune.JudderHz * $dt
        if ($Mix.JudderPhase -gt (2 * [math]::PI)) { $Mix.JudderPhase -= 2 * [math]::PI }
        $jN = [math]::Min(1.0, ((-$Sample.LongG) - 0.45) / 0.5)
        $judderAmp = $Tune.JudderGain * $jN
        $judder = $judderAmp * [math]::Sin($Mix.JudderPhase)
    }
    $ch['judder'] = [int]$judder

    # ---- 8. impacts --------------------------------------------------------
    # Fired from the velocity-vector discontinuity, which catches glancing hits
    # that barely change speed. Direction comes from which way the car was
    # rotated by the hit, so a hit on the left kicks the wheel left.
    if ($Sample.Jolt -gt $Tune.ImpactRef * 0.25 -and $Mix.LastJolt -le $Tune.ImpactRef * 0.25) {
        $mag = [math]::Min(1.0, $Sample.Jolt / $Tune.ImpactRef)
        $dir = if ([math]::Abs($Sample.YawRate) -gt 0.05) { [math]::Sign($Sample.YawRate) } else { 1 }
        Mix-Trigger $Mix 'jolt' ($dir * $mag * $Tune.ImpactGain) $Tune.ImpactMs
        $notes += ("IMPACT {0:0}%" -f ($mag * 100))
    }
    $Mix.LastJolt = $Sample.Jolt

    # ---- 9. weapon fire ----------------------------------------------------
    # RISING EDGE only. The flag stays set for as long as the trigger is held, so
    # keying on its level would produce one transient per frame - a continuous
    # roar instead of a shot. Held fire therefore gives one kick, which is the
    # honest behaviour until a per-shot counter is found.
    #
    # Fails safe: if TEL_FIRE_ADDR is wrong the flag never changes, this never
    # fires, and the channel is silent. It is not possible for a wrong address to
    # produce spurious kicks.
    # PREFER THE ENGINE'S OWN EVENT. FxEvent is true on the frame the engine
    # STARTED an effect - after input handling, weapon logic, ammo and damage
    # rules have all run. The input flag at 0x5367d0 is the fallback, and it is
    # the one that produced no weapon response in the field: a button moving is
    # not the same thing as a weapon firing.
    $firing = if ($null -ne $Sample.FxEvent) { [bool]$Sample.FxEvent } else { [bool]$Sample.Firing }
    if ($firing -and -not $Mix.LastFiring) {
        if ((($t - $Mix.LastFireT) * 1000.0) -ge $Tune.WeaponBlankMs) {
            Mix-Trigger $Mix 'buzz' $Tune.WeaponGain ([int]$Tune.WeaponMs) $Tune.WeaponHz 'weapon'
            $Mix.LastFireT = $t
            $notes += "FIRE"
        }
    }
    $Mix.LastFiring = $firing

    # ---- transient summation ----------------------------------------------
    $transImpact = 0.0
    $transWeapon = 0.0
    $dead = @()
    foreach ($tr in $Mix.Transients) {
        $age = ($t - $tr.Start) * 1000.0
        if ($age -ge $tr.Ms) { $dead += $tr; continue }
        $u = $age / $tr.Ms
        $v = 0.0
        if ($tr.Shape -eq 'buzz') {
            $v = $tr.Amp * [math]::Exp(-3.0 * $u) * [math]::Sin(2 * [math]::PI * $tr.Hz * ($age / 1000.0))
        } else {
            # sharp attack (first 12%), exponential decay after
            $env = if ($u -lt 0.12) { $u / 0.12 } else { [math]::Exp(-3.5 * ($u - 0.12)) }
            $v = $tr.Amp * $env
        }
        if ($tr.Kind -eq 'weapon') { $transWeapon += $v } else { $transImpact += $v }
    }
    foreach ($d in $dead) { $Mix.Transients.Remove($d) }
    $ch['impact'] = [int]$transImpact
    $ch['weapon'] = [int]$transWeapon

    # ---- combine -----------------------------------------------------------
    if (-not $gate['texture']) { $texture = 0.0 }
    if (-not $gate['scrub'])   { $scrub = 0.0 }
    if (-not $gate['judder'])  { $judder = 0.0 }
    if (-not $gate['impact'])  { $transImpact = 0.0 }
    if (-not $gate['weapon'])  { $transWeapon = 0.0 }
    $trans = $transImpact + $transWeapon
    $osc = $texture + $scrub + $judder

    # Slew-limit the STEADY part only. Steady forces should never step, but a
    # rate limit on an impact would file the edge off exactly the thing that
    # makes it read as an impact - so transients and oscillators bypass it.
    $maxStep = $Tune.SlewMax * $dt
    $d = $steady - $Mix.LastForce
    if ($d -gt $maxStep) { $steady = $Mix.LastForce + $maxStep }
    elseif ($d -lt -$maxStep) { $steady = $Mix.LastForce - $maxStep }
    $Mix.LastForce = $steady

    $force = ($steady + $osc + $trans) * $Tune.Master

    # Fade in from zero. A wheel that snaps to full cornering load the instant
    # the interposer attaches is startling and, with hands resting on it, rude.
    $ramp = [math]::Min(1.0, (($t - $Mix.StartT) * 1000.0) / [math]::Max(1, $Tune.RampMs))

    # STALE SIM GATE. If the engine has not advanced a tick recently the game is
    # paused or unfocused: telemetry is frozen, but this loop and its oscillators
    # keep running on wall-clock time, so texture/scrub/judder would carry on
    # buzzing against a car that is not moving. Field-reported as the wheel
    # bouncing +/-130 with the game not even in focus. Frozen data is not new
    # information, so emit nothing.
    if ($null -ne $Sample.SinceTick -and $Sample.SinceTick -gt 0.5) { $ramp = 0.0 }

    # Thermal idle guard - see IdleFadeAfter. Track how long the car has been
    # stationary and fade the output out, so a parked wheel is not held against
    # its stop for minutes. Any movement resets it instantly.
    if ($Sample.Speed -gt 0.5) { $Mix.StillSince = -1.0 }
    elseif ($Mix.StillSince -lt 0) { $Mix.StillSince = $t }
    if ($Mix.StillSince -ge 0) {
        $still = $t - $Mix.StillSince
        if ($still -gt $Tune.IdleFadeAfter) {
            $fade = 1.0 - (($still - $Tune.IdleFadeAfter) / [math]::Max(0.1, $Tune.IdleFadeOver))
            if ($fade -lt 0) { $fade = 0 }
            if ($fade -lt $ramp) { $ramp = $fade }
        }
    }
    $force *= $ramp
    if (-not $Mix.Enabled) { $force = 0 }

    if ($force -gt $Tune.Clamp) { $force = $Tune.Clamp }
    if ($force -lt -$Tune.Clamp) { $force = -$Tune.Clamp }
    if ([math]::Abs($force) -gt $Mix.PeakForce) { $Mix.PeakForce = [math]::Abs($force) }

    # ---- THE FORCE BUS ------------------------------------------------------
    # The device-independent output. Everything below is derived from the SAME
    # values that produced $force, so a renderer that sums the bus reproduces the
    # wheel force exactly - asserted by test. Units are normalized (forces -1..1,
    # amplitudes 0..1, frequencies Hz, motion in SI) so device processing really
    # is the last stage:
    #
    #   wheel      = (Steady + OscValue + Transient) * 10000   <- today's output
    #   pad rumble = Mix-RenderPad (left=heavy/low, right=buzz/high)
    #   motion rig = Motion block, raw SI; rig-side software does the cueing
    #   bass shaker= Lfe block, parametric (freq+amp), synthesised downstream
    $N = 10000.0
    $mScale = $Tune.Master * $ramp
    if (-not $Mix.Enabled) { $mScale = 0.0 }
    $bus = [pscustomobject]@{
        # kinesthetic: the signed low-frequency force a hand steers against
        Steady    = [math]::Round(($steady * $mScale) / $N, 4)
        # tactile: instantaneous summed oscillator value, and the bank behind it
        OscValue  = [math]::Round(($osc * $mScale) / $N, 4)
        Tactile   = @(
            @{ Name='texture'; Freq=$Tune.TextureHz; Amp=[math]::Round([math]::Abs($texAmp*$mScale)/$N,4) }
            @{ Name='scrub';   Freq=$Tune.ScrubHz;   Amp=[math]::Round(($scrubAmp*$mScale)/$N,4) }
            @{ Name='judder';  Freq=$Tune.JudderHz;  Amp=[math]::Round(($judderAmp*$mScale)/$N,4) }
        )
        # transients: instantaneous envelope values, signed
        Transient = [math]::Round((($transImpact + $transWeapon) * $mScale) / $N, 4)
        TransientImpact = [math]::Round(($transImpact * $mScale) / $N, 4)
        TransientWeapon = [math]::Round(($transWeapon * $mScale) / $N, 4)
        # motion platform: raw SI quantities; washout/tilt is the RIG's job
        Motion = [pscustomobject]@{
            SurgeA  = [math]::Round($Sample.LongAccel, 3)                    # m/s^2, +fwd
            SwayA   = [math]::Round($Sample.LatAccel, 3)                     # m/s^2, +left/right per sign
            HeaveA  = [math]::Round($(if ($null -ne $Sample.HeaveAccel) { $Sample.HeaveAccel } else { 0.0 }), 3)  # m/s^2
            YawRate = [math]::Round($Sample.YawRate, 4)                      # rad/s
            Pitch   = [math]::Round($(if ($null -ne $Sample.TravelPitch) { $Sample.TravelPitch } else { 0.0 }), 4) # rad, terrain
            Speed   = [math]::Round($Sample.Speed, 3)                        # m/s
        }
        # bass shaker: parametric. EngineFreq tracks speed like a '97 engine note.
        Lfe = [pscustomobject]@{
            EngineFreq = [math]::Round($Tune.LfeEngineIdleHz + ($Tune.LfeEngineMaxHz - $Tune.LfeEngineIdleHz) *
                           [math]::Min(1.0, $Sample.Speed / $Tune.LfeEngineRefSpd), 1)
            EngineAmp  = [math]::Round($Tune.LfeEngineAmp * [math]::Max(0.12, [math]::Abs($Sample.Throttle)) *
                           $(if ($Sample.Speed -gt 0.5 -or [math]::Abs($Sample.Throttle) -gt 0.05) { 1.0 } else { 0.0 }), 3)
            RoadAmp    = [math]::Round([math]::Min(1.0, $Tune.LfeRoadAmp * $rough * [math]::Min(1.0, $Sample.Speed / $Tune.TexRef)), 3)
            RoadFreq   = [math]::Round($Tune.LfeRoadLoHz + ($Tune.LfeRoadHiHz - $Tune.LfeRoadLoHz) * $rough, 1)
            ImpulseAmp = [math]::Round([math]::Min(1.0, [math]::Abs($transImpact) / $N * ($Tune.LfeImpactAmp * $N / [math]::Max(1,$Tune.ImpactGain))), 3)
            ImpulseFreq= $Tune.LfeImpactHz
            WeaponAmp  = [math]::Round([math]::Min(1.0, [math]::Abs($transWeapon) / [math]::Max(1,$Tune.WeaponGain)), 3)
            WeaponFreq = $Tune.LfeWeaponHz
        }
    }

    return [pscustomobject]@{
        Force    = [int]$force
        Steady   = [int]$steady
        Osc      = [int]$osc
        Ramp     = $ramp
        Channels = $ch
        Notes    = $notes
        Bus      = $bus
    }
}


function Mix-RenderPad {
    <#
      Down-mix the bus for a two-motor XInput pad - the "device processing is the
      last phase" degradation path. Returns Left / Right in 0..1.

      The mapping follows the field-proven i76-remap.ahk rumble design:
      LEFT motor carries the heavy/low-frequency world (engine, road, impacts,
      the magnitude of steady load), RIGHT carries the light/high-frequency buzz
      (scrub, judder, weapon fire). A pad cannot render a signed force, so the
      kinesthetic channel degrades to unsigned weight on the heavy motor at a
      fraction - enough to feel loaded, not enough to bury transients, which is
      the same hierarchy rule as everywhere else in this system.
    #>
    param($Bus)
    $left  = 0.0
    $right = 0.0
    # heavy: LFE content + impact transients + a fraction of the steady load
    $left += $Bus.Lfe.EngineAmp * 0.5
    $left += $Bus.Lfe.RoadAmp * 0.6
    $left += [math]::Abs($Bus.TransientImpact)
    $left += [math]::Abs($Bus.Steady) * 0.25
    # buzz: the tactile bank + weapon fire
    foreach ($t in $Bus.Tactile) {
        if ($t.Name -eq 'texture') { $right += $t.Amp * 0.5 } else { $right += $t.Amp }
    }
    $right += [math]::Abs($Bus.TransientWeapon)
    if ($left -gt 1.0) { $left = 1.0 }
    if ($right -gt 1.0) { $right = 1.0 }
    return [pscustomobject]@{ Left = [math]::Round($left,4); Right = [math]::Round($right,4) }
}


function Mix-RenderWheel {
    <#
      Render the model's output for a BELT-DRIVEN wheel.

      MinForce lives HERE and not in Mix-Update, because it is a property of the
      DEVICE, not of the car. The T300 is belt-driven and belt and gear drives have
      static friction that swallows low-amplitude signal - below some threshold the
      motor is commanded and the rim does not move, which is the single likeliest
      reason this read "barely perceptible" in the field. A pad motor and a bass
      shaker have no such floor, so applying it in the shared path would corrupt
      every other renderer.

      Putting it here keeps the promise the bus makes: $out.Force is the pure model
      output, the bus sums to exactly that, and device compensation is the last
      stage. Both facts are asserted by ffb-mixer-test.ps1 - and it was those two
      assertions failing that caught MinForce being in the wrong place.

      Set MinForce to 0 for a direct-drive wheel, which does not need it and reads
      the boost as a dead zone in reverse. Measure your own floor with
      toolsfbfb-bench.ps1.
    #>
    param($Out, $Tune)
    $f = [double]$Out.Force
    if ($Tune.MinForce -gt 0 -and [math]::Abs($f) -ge $Tune.MinForceGate) {
        # Lift the quiet end above stiction and compress the rest above it, which
        # preserves both ordering and sign. Silence stays silence: the point is to
        # make small forces felt, not to put a floor under nothing.
        $mag = [math]::Abs($f)
        $lifted = $Tune.MinForce + $mag * (1.0 - ($Tune.MinForce / $Tune.Clamp))
        if ($lifted -gt $mag) { $f = $lifted * [math]::Sign($f) }
    }
    if ($f -gt $Tune.Clamp) { $f = $Tune.Clamp }
    if ($f -lt -$Tune.Clamp) { $f = -$Tune.Clamp }
    return [int]$f
}
