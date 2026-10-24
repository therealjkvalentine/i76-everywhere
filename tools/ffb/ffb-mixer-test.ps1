<#
  ffb-mixer-test.ps1 - exercise the force model against synthetic telemetry.

  WHY THIS EXISTS: judging a force model by driving is slow, unrepeatable, and
  needs a human holding the wheel. Most of what can be WRONG with it is not a
  matter of feel at all - it is sign errors, clipping, channels that never fire,
  and transients that never decay. All of those are checkable from a desk.

  So this feeds hand-built driving scenarios through Mix-Update and asserts the
  properties that must hold, with no game and no wheel involved. Run it after any
  change to FfbMixer.ps1.

      tools\ffb\ffb-mixer-test.ps1
      tools\ffb\ffb-mixer-test.ps1 -Trace      # dump every frame's channels

  A note on what this does NOT test: whether the result feels good. It cannot.
  It tests that the model does what it claims, which is the precondition for
  tuning feel rather than a substitute for it.
#>
param([switch]$Trace)

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $here 'FfbMixer.ps1')

$script:pass = 0
$script:fail = 0
function Check {
    param([string]$Name, [bool]$Cond, [string]$Detail = "")
    if ($Cond) { $script:pass++; Write-Host ("  PASS  " + $Name) -ForegroundColor Green }
    else { $script:fail++; Write-Host ("  FAIL  " + $Name + $(if ($Detail) { "  ($Detail)" } else { "" })) -ForegroundColor Red }
}

# A fake Tel-Sample. Only the fields Mix-Update reads.
function Fake {
    param(
        [double]$T, [double]$Speed = 0, [double]$Steer = 0, [double]$Throttle = 0,
        [double]$YawRate = 0, [double]$ExpectedYaw = 0, [double]$LongG = 0, [double]$LatG = 0,
        [double]$Understeer = 0, [double]$Oversteer = 0, [double]$Jolt = 0,
        [double]$AngVelX = 0, [double]$AngVelZ = 0, [double]$Vy = 0, [double]$Tumble = 0,
        [bool]$Firing = $false, $FxFired = $null, $FxEvent = $null
    )
    [pscustomobject]@{
        T = $T; Speed = $Speed; SpeedMph = $Speed * 2.23694; Steer = $Steer; Throttle = $Throttle
        YawRate = $YawRate; ExpectedYaw = $ExpectedYaw; LongG = $LongG; LatG = $LatG
        LongAccel = ($LongG * 9.81); LatAccel = ($LatG * 9.81); HeaveAccel = 0.0; TravelPitch = 0.0
        Understeer = $Understeer; Oversteer = $Oversteer; Jolt = $Jolt
        AngVelX = $AngVelX; AngVelZ = $AngVelZ; Vy = $Vy; Tumble = ($Tumble + [math]::Abs($AngVelX) + [math]::Abs($AngVelZ))
        Firing = $Firing; FireRaw = $(if ($Firing) { 1 } else { 0 })
        FxFired = $FxFired; FxEvent = $FxEvent; FxActive = 0
        Braking = ($Throttle -lt -0.05); Airborne = ([math]::Abs($Vy) -gt 2.0)
        Ticks = 0; Polls = 0; Wheelbase = 4.66
    }
}

# Run a scenario past the ramp-in so ramp scaling does not mask results.
function RunScenario {
    param([scriptblock]$SampleAt, [double]$Seconds = 2.0, $Mix = $null)
    if (-not $Mix) { $Mix = Mix-New }
    $dt = 1.0 / 60
    $last = $null
    for ($t = 0.0; $t -lt $Seconds; $t += $dt) {
        $s = & $SampleAt $t
        $last = Mix-Update $Mix $s
        if ($Trace -and ([int]($t / $dt) % 20) -eq 0) {
            Write-Host ("    t={0,5:0.00} force={1,6} " -f $t, $last.Force) -NoNewline
            foreach ($k in $last.Channels.Keys) { Write-Host ("{0}={1} " -f $k, $last.Channels[$k]) -NoNewline }
            Write-Host ""
        }
    }
    return [pscustomobject]@{ Out = $last; Mix = $Mix }
}

Write-Host "`n=== 1. parked and silent ===" -ForegroundColor Cyan
# Nothing happening must produce NOTHING. A wheel that hums at a standstill is
# the single most annoying failure mode and the easiest to ship by accident.
$r = RunScenario { param($t) Fake -T $t }
Check "parked produces zero force" ($r.Out.Force -eq 0) "got $($r.Out.Force)"
Check "parked peak stayed zero" ($r.Mix.PeakForce -eq 0) "peak $($r.Mix.PeakForce)"

Write-Host "`n=== 2. centering opposes steering ===" -ForegroundColor Cyan
# Steer right at speed: the wheel must push LEFT (negative), and harder at
# higher speed. Getting this sign wrong makes the wheel self-steer into the
# ditch, so it is the most important assertion in the file.
$rRight = RunScenario { param($t) Fake -T $t -Speed 15 -Steer 0.6 }
$rLeft  = RunScenario { param($t) Fake -T $t -Speed 15 -Steer -0.6 }
Check "steering right pushes back left" ($rRight.Out.Channels['center'] -lt 0) "center=$($rRight.Out.Channels['center'])"
Check "steering left pushes back right" ($rLeft.Out.Channels['center'] -gt 0) "center=$($rLeft.Out.Channels['center'])"
$rSlow = RunScenario { param($t) Fake -T $t -Speed 2 -Steer 0.6 }
Check "centering is weaker at low speed" `
    ([math]::Abs($rSlow.Out.Channels['center']) -lt [math]::Abs($rRight.Out.Channels['center'])) `
    "slow=$($rSlow.Out.Channels['center']) fast=$($rRight.Out.Channels['center'])"

Write-Host "`n=== 3. cornering load builds weight ===" -ForegroundColor Cyan
$rCorner = RunScenario { param($t) Fake -T $t -Speed 18 -Steer 0.5 -YawRate 0.5 -LatG 0.5 -ExpectedYaw 0.5 }
Check "cornering channel is non-zero" ($rCorner.Out.Channels['corner'] -ne 0) "corner=$($rCorner.Out.Channels['corner'])"
Check "cornering opposes the turn" ($rCorner.Out.Channels['corner'] -lt 0) "corner=$($rCorner.Out.Channels['corner'])"

Write-Host "`n=== 4. UNDERSTEER MAKES THE WHEEL GO LIGHT ===" -ForegroundColor Cyan
# The central design claim (see the header of FfbMixer.ps1). Same cornering
# situation, but with grip lost: the steady weight must DROP, not rise.
$gripped = RunScenario { param($t) Fake -T $t -Speed 18 -Steer 0.6 -YawRate 0.5 -LatG 0.5 -ExpectedYaw 0.5 -Understeer 0.0 }
$sliding = RunScenario { param($t) Fake -T $t -Speed 18 -Steer 0.6 -YawRate 0.5 -LatG 0.5 -ExpectedYaw 0.5 -Understeer 0.9 }
$wGrip = [math]::Abs($gripped.Out.Channels['center']) + [math]::Abs($gripped.Out.Channels['corner'])
$wSlip = [math]::Abs($sliding.Out.Channels['center']) + [math]::Abs($sliding.Out.Channels['corner'])
Check "steady weight collapses when the front slides" ($wSlip -lt $wGrip * 0.6) "gripped=$wGrip sliding=$wSlip"
Check "grip% reported below 100 while sliding" ($sliding.Out.Channels['grip%'] -lt 100) "grip=$($sliding.Out.Channels['grip%'])%"
Check "scrub buzz appears while sliding" ($sliding.Mix.PeakForce -gt 0 -and $sliding.Out.Channels.Contains('scrub')) ""

Write-Host "`n=== 5. oversteer pushes toward the correction ===" -ForegroundColor Cyan
# Rear stepping out with a positive yaw rate: the push must be positive, i.e.
# the same sign as the rotation, which is the counter-steer direction. And it
# must NOT be attenuated by grip loss - it exists because of grip loss.
$rOver = RunScenario { param($t) Fake -T $t -Speed 18 -Steer 0.2 -YawRate 0.8 -ExpectedYaw 0.3 -LatG 0.6 -Oversteer 0.8 }
Check "oversteer channel fires" ($rOver.Out.Channels['oversteer'] -ne 0) "over=$($rOver.Out.Channels['oversteer'])"
Check "oversteer pushes with the rotation" ($rOver.Out.Channels['oversteer'] -gt 0) "over=$($rOver.Out.Channels['oversteer'])"

Write-Host "`n=== 5b. losing the car works via OVERSTEER, not just understeer ===" -ForegroundColor Cyan
# I'76 has no tyre model, so understeer effectively never occurs - replaying a
# real 959-sample drive showed Understeer never once passed 0.3 while Oversteer
# fired on 4.9%. Keying gripScale and scrub on understeer alone left the central
# "the wheel goes light" idea INERT in the only game it has to work in. These
# assert it responds to the signal that actually happens.
$gripped2 = RunScenario { param($t) Fake -T $t -Speed 18 -Steer 0.5 -YawRate 0.5 -LatG 1.5 -ExpectedYaw 0.5 }
$spun     = RunScenario { param($t) Fake -T $t -Speed 18 -Steer 0.5 -YawRate 1.6 -LatG 2.6 -ExpectedYaw 0.5 -Oversteer 0.9 }
Check "oversteer bleeds grip%" ($spun.Out.Channels['grip%'] -lt 100) "grip=$($spun.Out.Channels['grip%'])%"
$wGrip2 = [math]::Abs($gripped2.Out.Channels['center']) + [math]::Abs($gripped2.Out.Channels['corner'])
$wSpun  = [math]::Abs($spun.Out.Channels['center'])     + [math]::Abs($spun.Out.Channels['corner'])
Check "steady weight drops when the car is spun" ($wSpun -lt $wGrip2) "gripped=$wGrip2 spun=$wSpun"
$scrubSeen = $false
$m = Mix-New
for ($t = 0.0; $t -lt 1.5; $t += 1.0/60) {
    $o = Mix-Update $m (Fake -T $t -Speed 18 -Steer 0.5 -YawRate 1.6 -LatG 2.6 -ExpectedYaw 0.5 -Oversteer 0.9)
    if ([math]::Abs($o.Channels['scrub']) -gt 50) { $scrubSeen = $true }
}
Check "scrub buzz fires on a spin" $scrubSeen ""

Write-Host "`n=== 5c. channel gating is applied INSIDE the mixer ===" -ForegroundColor Cyan
# The interposer used to re-sum the breakdown to honour -Only/-Mute, which
# bypassed the slew limiter below. Gating now lives in Mix-Update, so .Force is
# the single authority for what reaches the device.
$mA = Mix-New
$onlyCenter = @{}
foreach ($c in @('center','corner','oversteer','brake','texture','scrub','judder','impact')) { $onlyCenter[$c] = $false }
$onlyCenter['center'] = $true
$gated = $null
for ($t = 0.0; $t -lt 2.0; $t += 1.0/60) {
    $gated = Mix-Update $mA (Fake -T $t -Speed 18 -Steer 0.6 -YawRate 0.5 -LatG 2.0 -ExpectedYaw 0.5) $onlyCenter
}
Check "muted channels are excluded from Force" `
    ([math]::Abs($gated.Force - $gated.Channels['center']) -lt 250) `
    "force=$($gated.Force) center=$($gated.Channels['center']) corner=$($gated.Channels['corner'])"
Check "muted channel still REPORTED for the panel" ($gated.Channels['corner'] -ne 0) "corner=$($gated.Channels['corner'])"

Write-Host "`n=== 6. braking adds weight, hard braking judders ===" -ForegroundColor Cyan
$rBrake = RunScenario { param($t) Fake -T $t -Speed 16 -Steer 0.3 -Throttle -0.9 -LongG -0.8 }
Check "brake channel fires under deceleration" ($rBrake.Out.Channels['brake'] -ne 0) "brake=$($rBrake.Out.Channels['brake'])"
$judderSeen = $false
$m = Mix-New
for ($t = 0.0; $t -lt 1.5; $t += 1.0/60) {
    $o = Mix-Update $m (Fake -T $t -Speed 16 -Steer 0.2 -Throttle -1 -LongG -0.9)
    if ([math]::Abs($o.Channels['judder']) -gt 50) { $judderSeen = $true }
}
Check "lockup judder appears under hard braking" $judderSeen ""
$noJudder = RunScenario { param($t) Fake -T $t -Speed 16 -Steer 0.2 -Throttle -0.2 -LongG -0.1 }
Check "no judder under light braking" ([math]::Abs($noJudder.Out.Channels['judder']) -lt 50) "judder=$($noJudder.Out.Channels['judder'])"

Write-Host "`n=== 7. texture scales with speed AND roughness ===" -ForegroundColor Cyan
# "Faster and bumpier feels more intense" has to mean both terms matter -
# speed alone would just be a constant hum at motorway pace.
# Roughness is driven by JOLT now, not by roll/pitch rate - those turned out to
# be impact rotation, not suspension. RoughRef is 16, so scale into that band.
function PeakTexture {
    param([double]$Speed, [double]$Rough)
    $m = Mix-New; $peak = 0
    for ($t = 0.0; $t -lt 1.5; $t += 1.0/60) {
        $o = Mix-Update $m (Fake -T $t -Speed $Speed -Jolt ($Rough * 16.0))
        $v = [math]::Abs($o.Channels['texture'])
        if ($v -gt $peak) { $peak = $v }
    }
    return $peak
}
$tSlowSmooth = PeakTexture 4 0.0
$tFastSmooth = PeakTexture 18 0.0
$tFastRough  = PeakTexture 18 0.7
Check "faster produces more texture" ($tFastSmooth -gt $tSlowSmooth) "slow=$tSlowSmooth fast=$tFastSmooth"
Check "rougher produces more texture" ($tFastRough -gt $tFastSmooth) "smooth=$tFastSmooth rough=$tFastRough"
Check "texture at a crawl is negligible" ($tSlowSmooth -lt 400) "got $tSlowSmooth"

Write-Host "`n=== 8. impacts fire once, kick hard, then decay ===" -ForegroundColor Cyan
# A collision must produce a big transient on the frame it happens, must not
# re-trigger every frame while the jolt reading stays high, and must return to
# silence on its own.
$m = Mix-New
$peak = 0; $triggers = 0; $tail = 0
for ($t = 0.0; $t -lt 2.5; $t += 1.0/60) {
    # jolt spikes between 1.0s and 1.15s, then stops
    $j = if ($t -ge 1.0 -and $t -lt 1.15) { 70 } else { 0 }
    $o = Mix-Update $m (Fake -T $t -Speed 14 -Jolt $j -YawRate 0.3)
    if ($o.Notes -match 'IMPACT') { $triggers++ }
    $v = [math]::Abs($o.Channels['impact'])
    if ($v -gt $peak) { $peak = $v }
    if ($t -gt 2.2) { $tail = [math]::Max($tail, $v) }
}
Check "impact triggered" ($triggers -ge 1) "triggers=$triggers"
Check "impact triggered ONCE, not per frame" ($triggers -le 2) "triggers=$triggers"
Check "impact kick is substantial" ($peak -gt 2000) "peak=$peak"
Check "impact decays to silence" ($tail -lt 50) "tail=$tail"

Write-Host "`n=== 8b. weapon fire: rising edge only ===" -ForegroundColor Cyan
# The fire flag stays SET while the trigger is held, so keying on its level would
# queue one transient per frame - a continuous roar instead of a shot.
$m = Mix-New
$peak = 0; $fires = 0
for ($t = 0.0; $t -lt 2.5; $t += 1.0/60) {
    # trigger held down for a full second
    $f = ($t -ge 1.0 -and $t -lt 2.0)
    $o = Mix-Update $m (Fake -T $t -Speed 14 -Firing $f)
    if ($o.Notes -match 'FIRE') { $fires++ }
    $v = [math]::Abs($o.Channels['weapon'])
    if ($v -gt $peak) { $peak = $v }
    if ($t -gt 2.3) { $tail = $v }
}
Check "weapon channel fires" ($fires -ge 1) "fires=$fires"
Check "held trigger fires ONCE, not per frame" ($fires -eq 1) "fires=$fires"
Check "weapon kick is substantial" ($peak -gt 800) "peak=$peak"
Check "weapon decays to silence" ($tail -lt 50) "tail=$tail"

# Fails safe: an unverified fire address means the flag never changes, and that
# must produce silence rather than anything spurious.
$m2 = Mix-New
$quiet = 0
for ($t = 0.0; $t -lt 1.5; $t += 1.0/60) {
    $o = Mix-Update $m2 (Fake -T $t -Speed 14 -Firing $false)
    $quiet = [math]::Max($quiet, [math]::Abs($o.Channels['weapon']))
}
Check "a flag that never changes stays silent" ($quiet -eq 0) "got $quiet"

Write-Host "`n=== 9. safety: clamped, ramped, mutable ===" -ForegroundColor Cyan
# Everything at once, at absurd magnitudes, must still respect the clamp. This
# is the assertion that protects the user's hands.
$m = Mix-New
$maxSeen = 0
for ($t = 0.0; $t -lt 3.0; $t += 1.0/60) {
    $o = Mix-Update $m (Fake -T $t -Speed 40 -Steer 1.0 -Throttle -1.0 -YawRate 2.0 -LatG 3.0 `
        -ExpectedYaw 0.2 -LongG -3.0 -Understeer 1.0 -Oversteer 1.0 -Jolt 200 `
        -AngVelX 3 -AngVelZ 3 -Vy 6)
    if ([math]::Abs($o.Force) -gt $maxSeen) { $maxSeen = [math]::Abs($o.Force) }
}
$clamp = (Mix-DefaultTune)['Clamp']
Check "force never exceeds the clamp" ($maxSeen -le $clamp) "max=$maxSeen clamp=$clamp"
Check "force never exceeds DirectInput range" ($maxSeen -le 10000) "max=$maxSeen"

# Ramp: the first frames must be quiet even in a violent scenario.
$m2 = Mix-New
$first = Mix-Update $m2 (Fake -T 0.0 -Speed 40 -Steer 1.0 -YawRate 2 -LatG 3 -Jolt 200)
Check "first frame is ramped to silence" ([math]::Abs($first.Force) -lt 200) "first=$($first.Force)"

# Mute must be absolute.
$m3 = Mix-New
$m3.Enabled = $false
$muted = Mix-Update $m3 (Fake -T 1.0 -Speed 30 -Steer 1 -YawRate 2 -LatG 3 -Jolt 200)
Check "mute forces exactly zero" ($muted.Force -eq 0) "got $($muted.Force)"

Write-Host "`n=== 9b. the force BUS is consistent with the wheel output ===" -ForegroundColor Cyan
# The bus is the device-independent output; the wheel is one renderer of it. If
# summing the bus does not reproduce Force, the "device processing last" claim is
# false and every other renderer inherits the drift.
$m = Mix-New
$o = $null
for ($t = 0.0; $t -lt 2.0; $t += 1.0/60) {
    $o = Mix-Update $m (Fake -T $t -Speed 18 -Steer 0.5 -YawRate 0.6 -LatG 1.5 -ExpectedYaw 0.6 -Jolt 6)
}
$busSum = ($o.Bus.Steady + $o.Bus.OscValue + $o.Bus.Transient) * 10000.0
Check "bus sum reproduces the wheel force" ([math]::Abs($busSum - $o.Force) -le 25) `
    ("bus {0:0} vs force {1}" -f $busSum, $o.Force)
Check "bus steady is normalized" ([math]::Abs($o.Bus.Steady) -le 1.0) "got $($o.Bus.Steady)"
Check "tactile bank has 4 oscillators with Hz (engine added 2026-10-24)" ($o.Bus.Tactile.Count -eq 4 -and $o.Bus.Tactile[0].Freq -gt 0) ""

# motion passthrough: raw SI values reach the bus untouched
$m2 = Mix-New
$o2 = Mix-Update $m2 (Fake -T 1.0 -Speed 20 -Steer 0.3 -YawRate 0.8 -LatG 2.0)
Check "motion carries yaw rate" ([math]::Abs($o2.Bus.Motion.YawRate - 0.8) -lt 0.001) "got $($o2.Bus.Motion.YawRate)"
Check "motion carries sway from latAccel" ([math]::Abs($o2.Bus.Motion.SwayA - (2.0*9.81)) -lt 0.5) "got $($o2.Bus.Motion.SwayA)"

# LFE: silent when parked, engine tracks speed, impact makes an impulse
$mQ = Mix-New
$oQ = Mix-Update $mQ (Fake -T 1.0)
Check "LFE engine silent parked with no throttle" ($oQ.Bus.Lfe.EngineAmp -eq 0) "got $($oQ.Bus.Lfe.EngineAmp)"
$mS = Mix-New
$oSlow = Mix-Update $mS (Fake -T 1.0 -Speed 8 -Throttle 0.8)
$oFast = Mix-Update $mS (Fake -T 1.1 -Speed 35 -Throttle 0.8)
Check "LFE engine frequency rises with speed" ($oFast.Bus.Lfe.EngineFreq -gt $oSlow.Bus.Lfe.EngineFreq) `
    ("slow {0} fast {1}" -f $oSlow.Bus.Lfe.EngineFreq, $oFast.Bus.Lfe.EngineFreq)
$mI = Mix-New
$imp = 0.0
for ($t = 0.0; $t -lt 1.6; $t += 1.0/60) {
    $j = if ($t -ge 1.0 -and $t -lt 1.1) { 120 } else { 0 }
    $oi = Mix-Update $mI (Fake -T $t -Speed 15 -Jolt $j -YawRate 0.2)
    if ($oi.Bus.Lfe.ImpulseAmp -gt $imp) { $imp = $oi.Bus.Lfe.ImpulseAmp }
}
Check "LFE impulse fires on impact" ($imp -gt 0.1) "peak $imp"

Write-Host "`n=== 9c. pad down-mix (the dumbed-down renderer) ===" -ForegroundColor Cyan
$pQ = Mix-RenderPad $oQ.Bus
Check "quiet bus -> silent pad" ($pQ.Left -eq 0 -and $pQ.Right -eq 0) "L=$($pQ.Left) R=$($pQ.Right)"
$mImp = Mix-New
$pImp = $null
for ($t = 0.0; $t -lt 1.15; $t += 1.0/60) {
    $j = if ($t -ge 1.0) { 150 } else { 0 }
    $oi = Mix-Update $mImp (Fake -T $t -Speed 15 -Jolt $j -YawRate 0.2)
    $pp = Mix-RenderPad $oi.Bus
    if ($null -eq $pImp -or $pp.Left -gt $pImp.Left) { $pImp = $pp }
}
Check "impact lands on the HEAVY motor" ($pImp.Left -gt 0.3) "L=$($pImp.Left)"
$mW = Mix-New
$pW = $null
for ($t = 0.0; $t -lt 1.1; $t += 1.0/60) {
    $oi = Mix-Update $mW (Fake -T $t -Speed 15 -Firing ($t -ge 1.0))
    $pp = Mix-RenderPad $oi.Bus
    if ($null -eq $pW -or $pp.Right -gt $pW.Right) { $pW = $pp }
}
Check "weapon fire lands on the BUZZ motor" ($pW.Right -gt 0.2) "R=$($pW.Right)"
Check "pad outputs bounded 0..1" ($pImp.Left -le 1.0 -and $pW.Right -le 1.0) ""

Write-Host "`n=== 8c. weapon force scales with the ENGINE's magnitude ===" -ForegroundColor Cyan
# The engine hands us its own authored magnitude per shot (5, 10, 60 observed).
# Scaling by it means every weapon feels different in the proportion the 1997
# authors chose - with no id-to-weapon mapping, which would cost several play
# sessions because a car only carries a few weapons at a time.
function FirePeak {
    param([int]$Mag)
    $m = Mix-New
    $peak = 0
    for ($t = 0.0; $t -lt 1.2; $t += 1.0/60) {
        # Assign then conditionally REPLACE. `$x = if (..) { @(..) } else { @() }`
        # collapses an empty array to $null in PowerShell's expression form, which
        # made this helper report zero while the mixer was firing correctly.
        $fx = @()
        if ($t -ge 0.5 -and $t -lt 0.55) { $fx = @([pscustomobject]@{ Slot=0; Id=8; Param=0.81; Mag=$Mag }) }
        $o = Mix-Update $m (Fake -T $t -Speed 14 -FxFired $fx -FxEvent ($fx.Count -gt 0))
        $v = [math]::Abs($o.Channels['weapon'])
        if ($v -gt $peak) { $peak = $v }
    }
    return $peak
}
$small = FirePeak 5
$norm  = FirePeak 10
$big   = FirePeak 60
Check "a nominal shot fires" ($norm -gt 500) "got $norm"
Check "a heavier shot hits harder" ($big -gt $norm) "mag60 $big vs mag10 $norm"
Check "a lighter shot hits softer" ($small -lt $norm) "mag5 $small vs mag10 $norm"
Check "the heaviest does not eat the whole clamp alone" ($big -lt 9500) "got $big"
# sqrt scaling: 60 vs 10 is 6x magnitude but should be ~2.45x force, not 6x
Check "scaling is compressed, not linear" (($big / [math]::Max(1,$norm)) -lt 4.0) `
    ("ratio {0:0.00}" -f ($big / [math]::Max(1,$norm)))

Write-Host "`n=== 9d. thermal idle guard ===" -ForegroundColor Cyan
# Thrustmaster documents thermal cut-back under sustained load. An always-on
# constant force against a wheel parked off-centre is exactly that, for no benefit.
$m = Mix-New
$out = $null
for ($t = 0.0; $t -lt 19.0; $t += 1.0/10) { $out = Mix-Update $m (Fake -T $t -Speed 0 -Steer 0.8) }
Check "still driving force while recently stationary" ([math]::Abs($out.Force) -gt 50) "force=$($out.Force)"
for ($t = 19.0; $t -lt 24.0; $t += 1.0/10) { $out = Mix-Update $m (Fake -T $t -Speed 0 -Steer 0.8) }
Check "faded out after the idle timeout" ($out.Force -eq 0) "force=$($out.Force)"
$out = Mix-Update $m (Fake -T 24.1 -Speed 12 -Steer 0.8 -YawRate 0.5 -LatG 1.5)
Check "movement restores it immediately" ([math]::Abs($out.Force) -gt 50) "force=$($out.Force)"

Write-Host "`n=== 9e. wheel renderer: belt-drive stiction compensation ===" -ForegroundColor Cyan
# MinForce belongs to the DEVICE, not the car - a pad and a shaker have no belt.
# It lives in Mix-RenderWheel so the bus stays pure; putting it in Mix-Update
# broke both the bus-consistency and channel-gating assertions, which is how the
# mistake was caught.
$tn = Mix-DefaultTune
# ABOVE the gate: a modest but meaningful force must be lifted clear of stiction.
$m = Mix-New
$o = $null
for ($t = 0.0; $t -lt 2.0; $t += 1.0/60) { $o = Mix-Update $m (Fake -T $t -Speed 14 -Steer 0.12) }
$rawF = [math]::Abs($o.Force)
$wheelF = [math]::Abs((Mix-RenderWheel $o $tn))
Check "a real force above the gate is lifted clear of stiction" `
    ($rawF -ge $tn.MinForceGate -and $wheelF -ge $tn.MinForce) `
    ("raw $rawF -> wheel $wheelF, gate $($tn.MinForceGate), MinForce $($tn.MinForce)")
Check "the lift does not change sign" ([math]::Sign((Mix-RenderWheel $o $tn)) -eq [math]::Sign($o.Force)) ""

# BELOW the gate: left alone. Lifting the always-on texture ripple to MinForce
# makes the wheel hum permanently and buries every transient - replaying a real
# drive with the gate removed dropped near-silence from 61% of samples to 0.2%.
$mTiny = Mix-New
$oTiny = $null
for ($t = 0.0; $t -lt 2.0; $t += 1.0/60) { $oTiny = Mix-Update $mTiny (Fake -T $t -Speed 6 -Steer 0.004) }
Check "a sub-gate ripple is NOT lifted (no permanent hum)" `
    ([math]::Abs($oTiny.Force) -lt $tn.MinForceGate -and (Mix-RenderWheel $oTiny $tn) -eq $oTiny.Force) `
    ("raw $($oTiny.Force) -> wheel $(Mix-RenderWheel $oTiny $tn)")

# silence must stay silence - a floor under nothing would hum at a standstill
$mQ = Mix-New
$oQ = $null
for ($t = 0.0; $t -lt 1.0; $t += 1.0/60) { $oQ = Mix-Update $mQ (Fake -T $t) }
Check "silence stays silent through the renderer" ((Mix-RenderWheel $oQ $tn) -eq 0) `
    ("got $(Mix-RenderWheel $oQ $tn)")

# ordering is preserved: a bigger model force is still bigger at the wheel
$mA = Mix-New; $mB = Mix-New
$oA = $null; $oB = $null
for ($t = 0.0; $t -lt 2.0; $t += 1.0/60) {
    $oA = Mix-Update $mA (Fake -T $t -Speed 14 -Steer 0.15)
    $oB = Mix-Update $mB (Fake -T $t -Speed 14 -Steer 0.55 -YawRate 0.5 -LatG 1.6 -ExpectedYaw 0.5)
}
Check "ordering preserved (bigger stays bigger)" `
    ([math]::Abs((Mix-RenderWheel $oB $tn)) -gt [math]::Abs((Mix-RenderWheel $oA $tn))) ""
Check "still clamped" ([math]::Abs((Mix-RenderWheel $oB $tn)) -le $tn.Clamp) ""

# a direct-drive wheel opts out
$dd = Mix-DefaultTune; $dd.MinForce = 0
Check "MinForce=0 passes the model force through untouched" `
    ((Mix-RenderWheel $o $dd) -eq $o.Force) "got $(Mix-RenderWheel $o $dd) vs $($o.Force)"

Write-Host "`n=== 10. no NaN or infinity escapes ===" -ForegroundColor Cyan
# Division by a near-zero speed or wheelbase is the classic way a force model
# emits NaN, and NaN written to a wheel is undefined behaviour in someone's hands.
# Counts THROWS as failures too. The first version of this check only looked at
# $o.Force, so when Mix-Update threw partway through (the NaN did not survive to
# the return) $o was $null, $null.Force read as 0, and the check passed while the
# bug it was written to catch was live on the very next line. A test that cannot
# fail is worse than no test.
$m = Mix-New
$bad = 0; $threw = 0; $frame = 0
foreach ($sp in @(0, 0.0001, 1e-9, 3, 200)) {
    foreach ($yw in @(0, 1e-9, -1e-9, 5)) {
        $frame++
        try {
            $o = Mix-Update $m (Fake -T ($frame * 0.016) -Speed $sp -Steer 0.5 -YawRate $yw `
                                     -LatG 2 -Understeer 0.5 -Oversteer 0.5)
            if ($null -eq $o) { $threw++ }
            elseif ([double]::IsNaN([double]$o.Force) -or [double]::IsInfinity([double]$o.Force)) { $bad++ }
        } catch { $threw++ }
    }
}
Check "no NaN/Inf across degenerate inputs" ($bad -eq 0) "$bad bad frames"
Check "no exceptions across degenerate inputs" ($threw -eq 0) "$threw throwing frames"

# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "=== 10. gear changes ===" -ForegroundColor Cyan

# Shift is fed straight from Tel-Sample (+1 up, -1 down), so the mixer side is
# what is tested here: that an event produces one hit of the right size, that a
# downshift is softer, and - the one that actually bit - that NO shift produces
# nothing at all.
function ShiftPeak {
    param([int]$Dir)
    $m = Mix-New
    $peak = 0.0
    for ($t = 0.0; $t -lt 1.5; $t += 1.0/60) {
        $d = 0
        if ([math]::Abs($t - 0.8) -lt 0.009) { $d = $Dir }
        $s = Fake -T $t -Speed 20
        $s | Add-Member -NotePropertyName Shift -NotePropertyValue $d -Force
        $o = Mix-Update $m $s
        $v = [math]::Abs($o.Channels['shift'])
        if ($v -gt $peak) { $peak = $v }
    }
    return $peak
}
$shUp = ShiftPeak 1
$shDn = ShiftPeak -1
$shNo = ShiftPeak 0
$tn = Mix-DefaultTune

Check "an upshift produces a hit"            ($shUp -gt 100) "got $shUp"
Check "a downshift produces a hit"           ($shDn -gt 100) "got $shDn"
Check "a downshift is softer than an upshift" ($shDn -lt $shUp) "$shDn vs $shUp"
Check "a shift does not hit as hard as a weapon" ($shUp -lt $tn.WeaponGain) "$shUp vs $($tn.WeaponGain)"
Check "no shift means no force"              ($shNo -eq 0) "got $shNo"

# The regression that motivated the null guard: in PowerShell `$null -ne 0` is
# TRUE, so a sample with NO Shift property at all fired a gear change every
# single frame - a parked car produced 2293 of force from nowhere. Every other
# test in this file uses a Fake without a Shift property, which is why five of
# them failed at once and why this is worth pinning explicitly.
$mNo = Mix-New
$noShiftPeak = 0.0
for ($t = 0.0; $t -lt 0.6; $t += 1.0/60) {
    $o = Mix-Update $mNo (Fake -T $t -Speed 20)   # no Shift property whatsoever
    $v = [math]::Abs($o.Channels['shift'])
    if ($v -gt $noShiftPeak) { $noShiftPeak = $v }
}
Check "a sample with no Shift property is silent" ($noShiftPeak -eq 0) "got $noShiftPeak"

# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "=== 11. shift DETECTION (Tel-DetectShift) ===" -ForegroundColor Cyan

# The thresholds here are provisional and a real drive will replace them. What
# these pin is the LOGIC, which is what would waste a play session if wrong:
# telling a gear change from a lift-off, and firing once instead of every frame.
. (Join-Path $here 'Telemetry.ps1')

$TICK = 0.05   # the sim runs at 20 Hz; shifts must differentiate against that

# An upshift: revs collapse in one tick while the car keeps gaining speed.
$r = Tel-DetectShift -Rpm 3800 -LastRpm 6000 -Speed 22.0 -LastSpeed 21.7 -Dt $TICK -Hold 0
Check "an upshift is detected" ($r.Shift -eq 1) "shift=$($r.Shift) rate=$($r.RpmRate)"

# A LIFT-OFF: revs fall, but so does road speed. This is the false positive that
# would otherwise fire on every corner entry in the game.
$r = Tel-DetectShift -Rpm 5850 -LastRpm 6000 -Speed 21.0 -LastSpeed 21.6 -Dt $TICK -Hold 0
Check "lifting off is NOT a shift" ($r.Shift -eq 0) "shift=$($r.Shift) rate=$($r.RpmRate)"

# A downshift: revs jump while the car is slowing.
$r = Tel-DetectShift -Rpm 4200 -LastRpm 2500 -Speed 18.0 -LastSpeed 19.2 -Dt $TICK -Hold 0
Check "a downshift is detected" ($r.Shift -eq -1) "shift=$($r.Shift) rate=$($r.RpmRate)"

# Ordinary acceleration also raises revs - and must not read as a downshift.
$r = Tel-DetectShift -Rpm 3250 -LastRpm 3000 -Speed 15.0 -LastSpeed 14.6 -Dt $TICK -Hold 0
Check "accelerating is NOT a downshift" ($r.Shift -eq 0) "shift=$($r.Shift) rate=$($r.RpmRate)"

# The refractory: while a shift is still ramping down, no second event.
$r = Tel-DetectShift -Rpm 3600 -LastRpm 3800 -Speed 22.4 -LastSpeed 22.0 -Dt $TICK -Hold 0.30
Check "one shift is one event" ($r.Shift -eq 0) "shift=$($r.Shift)"
Check "the refractory counts down" ($r.Hold -lt 0.30 -and $r.Hold -ge 0) "hold=$($r.Hold)"

# Standing still, nothing counts - revving in neutral is not a gear change.
$r = Tel-DetectShift -Rpm 2000 -LastRpm 6000 -Speed 0.0 -LastSpeed 0.0 -Dt $TICK -Hold 0
Check "a parked rev is not a shift" ($r.Shift -eq 0) "shift=$($r.Shift)"

# First frame: no previous RPM to differentiate against.
$r = Tel-DetectShift -Rpm 3800 -LastRpm 0 -Speed 22.0 -LastSpeed 21.7 -Dt $TICK -Hold 0
Check "the first frame emits nothing" ($r.Shift -eq 0 -and $r.RpmRate -eq 0) "shift=$($r.Shift)"

# A zero dt must not divide by zero.
$r = Tel-DetectShift -Rpm 3800 -LastRpm 6000 -Speed 22.0 -LastSpeed 21.7 -Dt 0 -Hold 0
Check "a zero tick interval is safe" ($r.Shift -eq 0 -and $r.RpmRate -eq 0) "shift=$($r.Shift)"

# ===========================================================================
# 2026-10-24: the owner's first T300 drive (docs/records/FFB-WHEEL-2026-10-24.md)
# ===========================================================================
# A Fake with the Tel-Extras fields set. $X: hashtable of property -> value.
function FakeX {
    param([double]$T, [hashtable]$P = @{}, [hashtable]$X = @{})
    $s = Fake -T $T @P
    foreach ($k in $X.Keys) { $s | Add-Member -NotePropertyName $k -NotePropertyValue $X[$k] -Force }
    return $s
}
# Run a scenario: $At = { param($t) hashtable of extras }, base fields in $P.
# Returns per-channel peaks (abs), first-nonzero sign, frame count where nonzero.
function RunX {
    param([scriptblock]$At, [hashtable]$P = @{}, [double]$Seconds = 2.0, [string[]]$Watch = @(), $Tune = $null)
    $m = Mix-New $Tune
    $peak = @{}; $sign = @{}; $nz = @{}; $pos = @{}; $neg = @{}; $last = $null; $notes = @()
    foreach ($w in $Watch) { $peak[$w] = 0.0; $sign[$w] = 0; $nz[$w] = 0; $pos[$w] = $false; $neg[$w] = $false }
    for ($t = 0.0; $t -lt $Seconds; $t += 1.0/60) {
        $x = & $At $t
        $o = Mix-Update $m (FakeX -T $t -P $P -X $x)
        $notes += $o.Notes
        foreach ($w in $Watch) {
            $v = [double]$o.Channels[$w]
            if ([math]::Abs($v) -gt $peak[$w]) { $peak[$w] = [math]::Abs($v) }
            if ($v -ne 0) { $nz[$w]++; if ($sign[$w] -eq 0) { $sign[$w] = [math]::Sign($v) } }
            if ($v -gt 30) { $pos[$w] = $true }; if ($v -lt -30) { $neg[$w] = $true }
        }
        $last = $o
    }
    return [pscustomobject]@{ Peak = $peak; Sign = $sign; Nz = $nz; Pos = $pos; Neg = $neg; Last = $last; Mix = $m; Notes = $notes }
}

Write-Host "`n=== 12. surface: pavement at PavementScale, off-road unchanged, no step ===" -ForegroundColor Cyan
$stockRoll = @(0.03, 0.10, 0.01, 0.03, 0.08, 0.20, 0.01, 0.03)
Check "stock table: types 2 and 6 are paved" ((Tel-SurfacePaved 2 $stockRoll) -and (Tel-SurfacePaved 6 $stockRoll)) ""
Check "stock table: dirt / sand / gravel are not" (-not (Tel-SurfacePaved 0 $stockRoll) -and -not (Tel-SurfacePaved 1 $stockRoll) -and -not (Tel-SurfacePaved 5 $stockRoll)) ""
Check "a level that renumbers its tarmac is followed" ((Tel-SurfacePaved 4 @(0.03,0.10,0.03,0.03,0.01,0.20,0.03,0.03)) -and -not (Tel-SurfacePaved 2 @(0.03,0.10,0.03,0.03,0.01,0.20,0.03,0.03))) ""
Check "no table: the fixed index set" ((Tel-SurfacePaved 2 $null) -and -not (Tel-SurfacePaved 3 $null)) ""
Check "out-of-range surface is not paved" (-not (Tel-SurfacePaved 9 $stockRoll) -and -not (Tel-SurfacePaved -1 $stockRoll)) ""
function TexAmp {
    param($Paved, [double]$Sec = 3.0)
    $m = Mix-New; $o = $null
    for ($t = 0.0; $t -lt $Sec; $t += 1.0/60) {
        $x = if ($null -eq $Paved) { @{} } else { @{ Paved = $Paved } }
        $o = Mix-Update $m (FakeX -T $t -P @{ Speed = 20; Jolt = 5; Vy = 0.3 } -X $x)
    }
    return $o.Bus.Tactile[0].Amp
}
$aOff = TexAmp $false; $aPav = TexAmp $true; $aOld = TexAmp $null
$tn = Mix-DefaultTune
Check "pavement texture = PavementScale x off-road" ([math]::Abs($aPav / [math]::Max(1e-9, $aOff) - $tn.PavementScale) -lt 0.03) ("off {0} paved {1}" -f $aOff, $aPav)
Check "a sample without the field is off-road (old behaviour kept)" ([math]::Abs($aOld - $aOff) -lt 1e-6) ("old {0} off {1}" -f $aOld, $aOff)
# Cross onto tarmac at t = 2.0 s: the factor must glide, never step.
$m = Mix-New; $maxJump = 0.0; $prev = $null; $at3tau = $null
for ($t = 0.0; $t -lt 5.0; $t += 1.0/60) {
    $o = Mix-Update $m (FakeX -T $t -P @{ Speed = 20; Jolt = 5 } -X @{ Paved = ($t -ge 2.0) })
    $sp = [double]$o.Channels['surf%']
    if ($null -ne $prev -and [math]::Abs($sp - $prev) -gt $maxJump) { $maxJump = [math]::Abs($sp - $prev) }
    $prev = $sp
    if ($null -eq $at3tau -and $t -ge (2.0 + 3 * $tn.SurfaceFadeMs / 1000.0)) { $at3tau = $sp }
}
Check "crossing the road edge is a crossfade (< 5 points per frame)" ($maxJump -lt 5) "largest frame step $maxJump"
Check "the crossfade settles (within 6 points of target after 3 tau)" ([math]::Abs($at3tau - 100 * $tn.PavementScale) -le 6) "surf% $at3tau"
Check "the LFE road bed follows the surface too" ($o.Bus.Lfe.RoadAmp -ge 0) ""

Write-Host "`n=== 13. weapons from the ammo counters, per class ===" -ForegroundColor Cyan
$prevA = @{ 3 = 350; 4 = 2000; 5 = 0x0fffffff }
$curA = @(
    [pscustomobject]@{ Idx = 3; Ammo = 349; Klass = 2; Damage = 45 },
    [pscustomobject]@{ Idx = 4; Ammo = 2005; Klass = 2; Damage = 15 },
    [pscustomobject]@{ Idx = 5; Ammo = 0x0fffffff; Klass = 4; Damage = 220 },
    [pscustomobject]@{ Idx = 9; Ammo = 10; Klass = 3; Damage = 100 })
$sh = Tel-DiffAmmo $prevA $curA
Check "a spent round is a shot" ($sh.Count -eq 1 -and $sh[0].Idx -eq 3 -and $sh[0].Rounds -eq 1 -and $sh[0].Klass -eq 2) "got $($sh.Count)"
Check "first sight of a weapon is not a shot" ((Tel-DiffAmmo $null $curA).Count -eq 0) ""
function ShotAt { param([double]$T0, [int]$K, [int]$D) return { param($t) if ([math]::Abs($t - $T0) -lt 0.008) { @{ ShotSource = 'ammo'; Shots = @([pscustomobject]@{ Klass = $K; Damage = $D; Rounds = 1; Idx = 1 }) } } else { @{ ShotSource = 'ammo' } } }.GetNewClosure() }
$mg  = RunX (ShotAt 1.0 2 15) @{ Speed = 10 } 2.0 @('weapon')
$can = RunX (ShotAt 1.0 2 45) @{ Speed = 10 } 2.0 @('weapon')
$mor = RunX (ShotAt 1.0 3 100) @{ Speed = 10 } 2.0 @('weapon')
$rkt = RunX (ShotAt 1.0 4 220) @{ Speed = 10 } 2.0 @('weapon')
$drp = RunX (ShotAt 1.0 6 0) @{ Speed = 10 } 2.0 @('weapon')
Check "a gun shot kicks" ($mg.Peak['weapon'] -gt 1000) "peak $($mg.Peak['weapon'])"
Check "the recoil pushes AND pulls (CANNON shape)" ($mg.Pos['weapon'] -and $mg.Neg['weapon']) ""
Check "a 20mm (45) hits harder than a 30cal (15)" ($can.Peak['weapon'] -gt $mg.Peak['weapon']) ("{0} vs {1}" -f $can.Peak['weapon'], $mg.Peak['weapon'])
Check "a mortar is the heaviest gun" ($mor.Peak['weapon'] -gt $can.Peak['weapon']) ("{0} vs {1}" -f $mor.Peak['weapon'], $can.Peak['weapon'])
Check "a rocket fires" ($rkt.Peak['weapon'] -gt 1000) "peak $($rkt.Peak['weapon'])"
Check "a dropper clunks" ($drp.Peak['weapon'] -gt 500) "peak $($drp.Peak['weapon'])"
Check "a shot decays to silence" ([math]::Abs($mg.Last.Channels['weapon']) -lt 30) "end $($mg.Last.Channels['weapon'])"
Check "under the clamp" ($mor.Peak['weapon'] -le $tn.Clamp) ""
# flamer: continuous while the ammo keeps falling, silent 0.2 s after it stops
$fl = RunX { param($t) if ($t -ge 0.5 -and $t -lt 1.5) { @{ ShotSource = 'ammo'; Shots = @([pscustomobject]@{ Klass = 5; Damage = 2; Rounds = 1; Idx = 1 }) } } else { @{ ShotSource = 'ammo' } } } @{ Speed = 10 } 2.2 @('weapon')
Check "a flamer is a continuous bed while firing" ($fl.Nz['weapon'] -gt 50 -and $fl.Peak['weapon'] -le $tn.FlameGain + 1) ("frames {0} peak {1}" -f $fl.Nz['weapon'], $fl.Peak['weapon'])
Check "and stops when firing stops" ([math]::Abs($fl.Last.Channels['weapon']) -lt 1) "end $($fl.Last.Channels['weapon'])"
# the FFB-block slot edge must not kick a second time when the ammo path is live
$dup = RunX { param($t) $x = (& (ShotAt 1.0 2 45) $t); if ([math]::Abs($t - 1.0) -lt 0.008) { $x['FxEvent'] = $true; $x['FxFired'] = @([pscustomobject]@{ Slot = 0; Id = 8; Param = 0.8; Mag = 10 }) } else { $x['FxEvent'] = $false }; $x } @{ Speed = 10 } 2.0 @('weapon')
Check "ammo path + FFB-block edge = ONE kick, not two" ([math]::Abs($dup.Peak['weapon'] - $can.Peak['weapon']) -lt 5) ("{0} vs {1}" -f $dup.Peak['weapon'], $can.Peak['weapon'])
$fxOnly = RunX { param($t) if ([math]::Abs($t - 1.0) -lt 0.008) { @{ ShotSource = 'none'; FxEvent = $true; FxFired = @([pscustomobject]@{ Slot = 0; Id = 8; Param = 0.8; Mag = 10 }) } } else { @{ ShotSource = 'none'; FxEvent = $false } } } @{ Speed = 10 } 2.0 @('weapon')
Check "no weapon record: the FFB-block edge still fires (fallback)" ($fxOnly.Peak['weapon'] -gt 1000) "peak $($fxOnly.Peak['weapon'])"
$cyc = RunX { param($t) @{ WeaponCycle = ([math]::Abs($t - 1.0) -lt 0.008) } } @{ Speed = 10 } 2.0 @('weapon')
Check "weapon cycle clicks (WPNCYCLE ramp: both signs, short)" ($cyc.Pos['weapon'] -and $cyc.Neg['weapon'] -and $cyc.Nz['weapon'] -le 6) ("frames {0}" -f $cyc.Nz['weapon'])

Write-Host "`n=== 14. hits taken ===" -ForegroundColor Cyan
$hd = Tel-DiffDamage @(100, 80, 80, 60) @(100, 50, 80, 60)
Check "a loss on the left is a left hit" ($hd.Count -eq 1 -and $hd[0].Side -eq 1 -and $hd[0].Hp -eq 30) ""
Check "a repair is not a hit" ((Tel-DiffDamage @(100, 50, 80, 60) @(100, 80, 80, 60)).Count -eq 0) ""
function HitAt { param([double]$T0, [int]$Side, [int]$Hp) return { param($t) if ([math]::Abs($t - $T0) -lt 0.008) { @{ Hits = @([pscustomobject]@{ Side = $Side; Hp = $Hp }) } } else { @{} } }.GetNewClosure() }
$hl = RunX (HitAt 1.0 1 40) @{ Speed = 10 } 2.0 @('hit')
$hr = RunX (HitAt 1.0 2 40) @{ Speed = 10 } 2.0 @('hit')
$hf = RunX (HitAt 1.0 0 40) @{ Speed = 10 } 2.0 @('hit')
$hBig = RunX (HitAt 1.0 1 90) @{ Speed = 10 } 2.0 @('hit')
$hSmall = RunX (HitAt 1.0 1 5) @{ Speed = 10 } 2.0 @('hit')
Check "a left hit kicks one way, a right hit the other" ($hl.Sign['hit'] -eq 1 -and $hr.Sign['hit'] -eq -1) ("L {0} R {1}" -f $hl.Sign['hit'], $hr.Sign['hit'])
Check "a front hit is a buzz (both signs)" ($hf.Pos['hit'] -and $hf.Neg['hit']) ""
Check "more damage, harder hit" ($hBig.Peak['hit'] -gt $hSmall.Peak['hit']) ("{0} vs {1}" -f $hBig.Peak['hit'], $hSmall.Peak['hit'])
Check "a hit decays to silence" ([math]::Abs($hl.Last.Channels['hit']) -lt 30) ""
# a flamer's 1 hp ticks: accumulate, kick at most once per refractory window
$tr = RunX { param($t) if ($t -ge 0.5 -and $t -lt 1.5) { @{ Hits = @([pscustomobject]@{ Side = 1; Hp = 1 }) } } else { @{} } } @{ Speed = 10 } 2.0 @('hit')
$hitNotes = @($tr.Notes | Where-Object { $_ -like 'HIT*' }).Count
Check "small ticks accumulate, not one kick per tick" ($hitNotes -ge 1 -and $hitNotes -le [math]::Ceiling(1000 / $tn.HitRefractMs) + 1) "kicks $hitNotes for 60 ticks"
# collision: the jolt impact and the damage in the same frame are one event
$col = RunX { param($t) $x = (& (HitAt 1.0 1 40) $t); $x } @{ Speed = 15; YawRate = 0.2 } 2.0 @('hit', 'impact')
$colJ = $null
$m = Mix-New; $hitPk = 0; $impPk = 0
for ($t = 0.0; $t -lt 2.0; $t += 1.0/60) {
    $j = if ([math]::Abs($t - 1.0) -lt 0.008) { 120 } else { 0 }
    $x = if ([math]::Abs($t - 1.0) -lt 0.008) { @{ Hits = @([pscustomobject]@{ Side = 1; Hp = 40 }) } } else { @{} }
    $o = Mix-Update $m (FakeX -T $t -P @{ Speed = 15; YawRate = 0.2; Jolt = $j } -X $x)
    if ([math]::Abs($o.Channels['hit']) -gt $hitPk) { $hitPk = [math]::Abs($o.Channels['hit']) }
    if ([math]::Abs($o.Channels['impact']) -gt $impPk) { $impPk = [math]::Abs($o.Channels['impact']) }
}
Check "a collision kicks once (impact), not twice (impact + hit)" ($impPk -gt 1000 -and $hitPk -eq 0) "impact $impPk hit $hitPk"

Write-Host "`n=== 15. landing ===" -ForegroundColor Cyan
function AirX { param([double]$Up, [double]$Down, [double]$Vy) return { param($t) @{ AirFlag = ($t -ge $Up -and $t -lt $Down) } }.GetNewClosure() }
function LandRun {
    param([double]$Up, [double]$Down, [double]$Vy, [double]$J = 0)
    $m = Mix-New; $lp = 0; $ip = 0; $sg = $false
    for ($t = 0.0; $t -lt 2.5; $t += 1.0/60) {
        $air = ($t -ge $Up -and $t -lt $Down)
        # NOT $vy: PowerShell names are case-insensitive, and $vy would overwrite $Vy
        $vNow = if ($air) { $Vy } else { 0.0 }
        $jj = if ([math]::Abs($t - $Down) -lt 0.009) { $J } else { 0 }
        $o = Mix-Update $m (FakeX -T $t -P @{ Speed = 15; Vy = $vNow; Jolt = $jj; YawRate = 0.2 } -X @{ AirFlag = $air })
        if ([math]::Abs($o.Channels['landing']) -gt $lp) { $lp = [math]::Abs($o.Channels['landing']) }
        if ([math]::Abs($o.Channels['impact']) -gt $ip) { $ip = [math]::Abs($o.Channels['impact']) }
    }
    return @($lp, $ip)
}
$lHard = LandRun 1.0 1.6 -6.0
$lSoft = LandRun 1.0 1.6 -2.0
$lHop  = LandRun 1.0 1.05 -6.0
$lSlow = LandRun 1.0 1.6 -0.5
$lJolt = LandRun 1.0 1.6 -6.0 120
Check "a landing thumps" ($lHard[0] -gt 1500) "peak $($lHard[0])"
Check "a harder landing thumps harder" ($lHard[0] -gt $lSoft[0]) ("{0} vs {1}" -f $lHard[0], $lSoft[0])
Check "a 50 ms hop is not a landing" ($lHop[0] -eq 0) "peak $($lHop[0])"
Check "a slow touchdown is silent" ($lSlow[0] -eq 0) "peak $($lSlow[0])"
Check "the touchdown jolt does not also fire an impact" ($lJolt[0] -gt 1500 -and $lJolt[1] -eq 0) ("landing {0} impact {1}" -f $lJolt[0], $lJolt[1])

Write-Host "`n=== 16. ignition and engine rumble ===" -ForegroundColor Cyan
$ig = RunX { param($t) @{ EngineStarting = ($t -ge 1.0 -and $t -lt 1.3); EngineRunning = ($t -ge 1.3) } } @{} 3.5 @('ignition')
Check "the starting flag cranks" ($ig.Peak['ignition'] -gt 1500) "peak $($ig.Peak['ignition'])"
Check "the crank lasts about IgnitionMs, then stops" ([math]::Abs($ig.Nz['ignition'] / 60.0 - $tn.IgnitionMs / 1000.0) -lt 0.15 -and $ig.Last.Channels['ignition'] -eq 0) ("{0:0.00} s" -f ($ig.Nz['ignition'] / 60.0))
Check "only one crank for one start (no second from the running edge)" (@($ig.Notes | Where-Object { $_ -eq 'IGNITION' }).Count -eq 1) ""
$igA = RunX { param($t) @{ EngineStarting = $true; EngineRunning = $false } } @{} 2.0 @('ignition')
Check "attaching mid-start does not crank" ($igA.Peak['ignition'] -eq 0) ""
$igR = RunX { param($t) @{ EngineStarting = $false; EngineRunning = ($t -ge 1.0) } } @{} 2.5 @('ignition')
Check "a running edge without a starting edge still cranks (shorter)" ($igR.Peak['ignition'] -gt 1000 -and $igR.Nz['ignition'] -lt $ig.Nz['ignition']) ""
$en = RunX { param($t) @{ EngineRunning = $true } } @{ Speed = 0.6 } 2.0 @('engine')
$enOff = RunX { param($t) @{ EngineRunning = $false } } @{ Speed = 0.6 } 2.0 @('engine')
$enFast = RunX { param($t) @{ EngineRunning = $true } } @{ Speed = 25 } 2.0 @('engine')
Check "a running engine rumbles at idle" ($en.Peak['engine'] -gt 0.6 * $tn.EngineGain -and $en.Peak['engine'] -le $tn.EngineGain + 1) "peak $($en.Peak['engine'])"
Check "a stopped engine is silent" ($enOff.Peak['engine'] -eq 0) ""
Check "the rumble has faded by EngineFadeSpd" ($enFast.Peak['engine'] -eq 0) "peak $($enFast.Peak['engine'])"
function Crossings { param([double]$Rpm)
    $m = Mix-New; $n = 0; $p = 0
    for ($t = 0.0; $t -lt 2.0; $t += 1.0/60) {
        $s = FakeX -T $t -P @{ Speed = 1 } -X @{ EngineRunning = $true }
        $s | Add-Member -NotePropertyName Rpm -NotePropertyValue $Rpm -Force
        $v = (Mix-Update $m $s).Channels['engine']
        if ($p -le 0 -and $v -gt 0) { $n++ }; $p = $v
    }
    return $n
}
Check "the rumble pitch rises with rpm" ((Crossings 6500) -gt (Crossings 900)) ("{0} vs {1}" -f (Crossings 6500), (Crossings 900))
$nf = RunX { param($t) @{} } @{ Speed = 0.6 } 2.0 @('engine', 'ignition', 'hit', 'landing', 'weapon')
Check "an old-format sample (no new fields) fires none of the new channels" (($nf.Peak.Values | Measure-Object -Sum).Sum -eq 0) ""

Write-Host "`n=== 17. bus still sums to the wheel with every channel live ===" -ForegroundColor Cyan
$m = Mix-New; $worst = 0.0
for ($t = 0.0; $t -lt 3.0; $t += 1.0/60) {
    $x = @{ EngineRunning = $true; Paved = $true; ShotSource = 'ammo' }
    if ([math]::Abs($t - 1.0) -lt 0.008) { $x['Shots'] = @([pscustomobject]@{ Klass = 2; Damage = 45; Rounds = 1; Idx = 1 }) }
    if ([math]::Abs($t - 1.5) -lt 0.008) { $x['Hits'] = @([pscustomobject]@{ Side = 2; Hp = 30 }) }
    $s = FakeX -T $t -P @{ Speed = 12; Steer = 0.3; YawRate = 0.4; LatG = 0.5; Jolt = 4 } -X $x
    $s | Add-Member -NotePropertyName Shift -NotePropertyValue $(if ([math]::Abs($t - 2.0) -lt 0.008) { 1 } else { 0 }) -Force
    $o = Mix-Update $m $s
    $bs = ($o.Bus.Steady + $o.Bus.OscValue + $o.Bus.Transient) * 10000.0
    if ([math]::Abs($bs - $o.Force) -gt $worst) { $worst = [math]::Abs($bs - $o.Force) }
}
Check "bus sum = wheel force through shots, hits, a shift, engine and surface" ($worst -le 25) "worst gap $worst"

Write-Host "`n=== 18. the steering reference is the ENGINE's law when it is known ===" -ForegroundColor Cyan
# physics_ComputeSteerYawRate 0x43ce10: w = steer * s * K, capped at steer * lim / s.
# The owner's car: K 0.19 (from his own drive: 2.198 rad/s at full lock, 11.58 m/s),
# lim 37.5. A drive that follows that law exactly must read as NO loss of control,
# and with the RC folder's fitted (a 31, lock 0.76) the same drive is the 82 % false
# oversteer the owner felt as "the jerk".
$K = 0.19; $lim = 37.5
# the fallback as the RC folder had it (its ffb-calib.json), whatever this checkout's calibration says
$savedA = $script:TEL_LAT_GAIN; $savedL = $script:TEL_STEER_LOCK
$script:TEL_LAT_GAIN = 31.0; $script:TEL_STEER_LOCK = 0.76
$okN = 0; $badN = 0; $n = 0
foreach ($v in @(4.0, 8.0, 11.6, 14.0, 18.0, 25.0)) {
    foreach ($st in @(-1.0, -0.6, -0.3, 0.3, 0.6, 1.0)) {
        $w = $st * $v * $K
        if ([math]::Abs($w * $v) -gt [math]::Abs($st) * $lim) { $w = $st * $lim / $v }
        $n++
        $e = Tel-Slip -Speed $v -Steer $st -YawRate $w -SteerK $K -LatCap $lim
        if ($e.Oversteer -eq 0 -and $e.Understeer -eq 0) { $okN++ }
        $f = Tel-Slip -Speed $v -Steer $st -YawRate $w
        if ($f.Oversteer -gt 0 -or $f.Understeer -gt 0) { $badN++ }
    }
}
Check "on the engine's law: zero false slip (both regimes, both ways)" ($okN -eq $n) "$okN of $n clean"
Check "the old fitted fallback reads the same car as slipping (the reported jerk)" ($badN -gt 0) "$badN of $n flagged"
# the owner's own operating point: full lock, 11.58 m/s, 2.198 rad/s (his calibration drive)
$own = Tel-Slip -Speed 11.58 -Steer 1.0 -YawRate 2.198
$ownX = Tel-Slip -Speed 11.58 -Steer 1.0 -YawRate 2.198 -SteerK $K -LatCap $lim
Check "his steady full-lock turn: flagged by the fitted fallback, clean on the law" (($own.Oversteer + $own.Understeer) -gt 0 -and ($ownX.Oversteer + $ownX.Understeer) -eq 0) ("fallback U {0:0.00} O {1:0.00}" -f $own.Understeer, $own.Oversteer)
$sp = Tel-Slip -Speed 15 -Steer 0.5 -YawRate (0.5 * $lim / 15 + 0.8) -SteerK $K -LatCap $lim
Check "a real spin still reads as oversteer on the exact law" ($sp.Oversteer -gt 0.5) "over $($sp.Oversteer)"
$script:TEL_LAT_GAIN = $savedA; $script:TEL_STEER_LOCK = $savedL

Write-Host ""
Write-Host ("=== {0} passed, {1} failed ===" -f $script:pass, $script:fail) `
    -ForegroundColor $(if ($script:fail -eq 0) { 'Green' } else { 'Red' })
if ($script:fail -gt 0) { exit 1 }
