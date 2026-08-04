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
  I'76 has NO TYRE MODEL. Measured over a real drive, lateral acceleration is
  exactly proportional to steering input and independent of speed
  (latAccel = 29.3 * steer, R^2 = 0.9995 - see Telemetry.ps1's header). The
  engine treats the wheel as a lateral-acceleration command.

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
        SatGain       = 3200   # force at full lock, at or above SatRef speed
        SatRef        = 12.0   # m/s at which centering reaches full authority
        SatFloor      = 0.10   # fraction of SatGain kept at a standstill, so the
                               # wheel is not completely dead in the pits

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
        CornerGain    = 2600   # force at CornerRef lateral g
        CornerRef     = 2.80   # lateral g treated as "fully loaded" (measured max 2.99)

        # --- slip ----------------------------------------------------------
        UndersteerDrop = 0.75  # how much grip loss bleeds the steady channels.
                               # 0.75 = at full understeer, 25% weight remains.
        ScrubGain     = 900    # tyre-scrub buzz amplitude at full understeer
        ScrubHz       = 14.0
        OversteerGain = 2600   # counter-steer push at full oversteer

        # --- road texture ---------------------------------------------------
        # NYQUIST NOTE: the force loop tops out near 62 Hz (Start-Sleep
        # granularity - see ffb-interposer.ps1), so every oscillator frequency
        # here stays at or under ~15 Hz to keep 4+ samples per cycle. Set one to
        # 22 Hz and you do not get a 22 Hz buzz, you get an aliased beat that
        # feels like a fault in the wheel.
        TextureGain   = 1100   # amplitude at TexRef speed over rough ground
        TexRef        = 16.0   # m/s at which texture is at full amplitude
        TextureHz     = 11.0
        BumpGain      = 2000   # suspension-motion component (roll/pitch/heave)

        # --- braking --------------------------------------------------------
        BrakeGain     = 1500   # weight added under deceleration
        BrakeRef      = 0.60   # longitudinal g treated as "hard braking"
        JudderGain    = 1300   # lockup shimmy under heavy braking
        JudderHz      = 12.0

        # --- transients -----------------------------------------------------
        ImpactGain    = 9000   # peak force of a full-scale collision
        ImpactRef     = 55.0   # jolt (m/s^2) treated as a full-scale impact
        ImpactMs      = 260    # decay time of an impact
        KerbGain      = 2500

        # --- safety ---------------------------------------------------------
        Clamp         = 9500   # never exceed this; leaves headroom under 10000
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
    }
}

function Mix-Trigger {
    <#
      Queue a transient. Shape is 'jolt' (sharp attack, exponential decay) or
      'buzz' (decaying oscillation). Amp is signed for 'jolt' so an impact can
      have a direction.
    #>
    param($Mix, [string]$Shape, [double]$Amp, [int]$Ms, [double]$Hz = 30.0)
    $null = $Mix.Transients.Add([pscustomobject]@{
        Shape = $Shape; Amp = $Amp; Ms = $Ms; Hz = $Hz; Start = $Mix.LastT
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
    foreach ($k in @('center','corner','oversteer','brake','texture','scrub','judder','impact')) {
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
    $rough = [math]::Min(1.0, ([math]::Abs($Sample.RollRate) + [math]::Abs($Sample.PitchRate)) / 1.2)
    $heave = [math]::Min(1.0, [math]::Abs($Sample.Vy) / 3.0)
    $texN  = [math]::Min(1.0, $Sample.Speed / $Tune.TexRef)
    $texAmp = ($Tune.TextureGain * $texN * (0.25 + 0.75 * $rough)) + ($Tune.BumpGain * $heave * $texN)
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
    if ($outOfShape -gt 0.15) {
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
    if ($Sample.LongG -lt -0.45 -and $Sample.Speed -gt 4) {
        $Mix.JudderPhase += 2 * [math]::PI * $Tune.JudderHz * $dt
        if ($Mix.JudderPhase -gt (2 * [math]::PI)) { $Mix.JudderPhase -= 2 * [math]::PI }
        $jN = [math]::Min(1.0, ((-$Sample.LongG) - 0.45) / 0.5)
        $judder = $Tune.JudderGain * $jN * [math]::Sin($Mix.JudderPhase)
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

    # ---- transient summation ----------------------------------------------
    $trans = 0.0
    $dead = @()
    foreach ($tr in $Mix.Transients) {
        $age = ($t - $tr.Start) * 1000.0
        if ($age -ge $tr.Ms) { $dead += $tr; continue }
        $u = $age / $tr.Ms
        if ($tr.Shape -eq 'buzz') {
            $trans += $tr.Amp * [math]::Exp(-3.0 * $u) * [math]::Sin(2 * [math]::PI * $tr.Hz * ($age / 1000.0))
        } else {
            # sharp attack (first 12%), exponential decay after
            $env = if ($u -lt 0.12) { $u / 0.12 } else { [math]::Exp(-3.5 * ($u - 0.12)) }
            $trans += $tr.Amp * $env
        }
    }
    foreach ($d in $dead) { $Mix.Transients.Remove($d) }
    $ch['impact'] = [int]$trans

    # ---- combine -----------------------------------------------------------
    if (-not $gate['texture']) { $texture = 0.0 }
    if (-not $gate['scrub'])   { $scrub = 0.0 }
    if (-not $gate['judder'])  { $judder = 0.0 }
    if (-not $gate['impact'])  { $trans = 0.0 }
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
    $force *= $ramp
    if (-not $Mix.Enabled) { $force = 0 }

    if ($force -gt $Tune.Clamp) { $force = $Tune.Clamp }
    if ($force -lt -$Tune.Clamp) { $force = -$Tune.Clamp }
    if ([math]::Abs($force) -gt $Mix.PeakForce) { $Mix.PeakForce = [math]::Abs($force) }

    return [pscustomobject]@{
        Force    = [int]$force
        Steady   = [int]$steady
        Osc      = [int]$osc
        Ramp     = $ramp
        Channels = $ch
        Notes    = $notes
    }
}
