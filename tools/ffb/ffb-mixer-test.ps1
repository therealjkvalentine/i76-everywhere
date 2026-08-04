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
        [double]$RollRate = 0, [double]$PitchRate = 0, [double]$Vy = 0
    )
    [pscustomobject]@{
        T = $T; Speed = $Speed; SpeedMph = $Speed * 2.23694; Steer = $Steer; Throttle = $Throttle
        YawRate = $YawRate; ExpectedYaw = $ExpectedYaw; LongG = $LongG; LatG = $LatG
        Understeer = $Understeer; Oversteer = $Oversteer; Jolt = $Jolt
        RollRate = $RollRate; PitchRate = $PitchRate; Vy = $Vy
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
function PeakTexture {
    param([double]$Speed, [double]$Rough)
    $m = Mix-New; $peak = 0
    for ($t = 0.0; $t -lt 1.5; $t += 1.0/60) {
        $o = Mix-Update $m (Fake -T $t -Speed $Speed -RollRate $Rough -PitchRate $Rough)
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

Write-Host "`n=== 9. safety: clamped, ramped, mutable ===" -ForegroundColor Cyan
# Everything at once, at absurd magnitudes, must still respect the clamp. This
# is the assertion that protects the user's hands.
$m = Mix-New
$maxSeen = 0
for ($t = 0.0; $t -lt 3.0; $t += 1.0/60) {
    $o = Mix-Update $m (Fake -T $t -Speed 40 -Steer 1.0 -Throttle -1.0 -YawRate 2.0 -LatG 3.0 `
        -ExpectedYaw 0.2 -LongG -3.0 -Understeer 1.0 -Oversteer 1.0 -Jolt 200 `
        -RollRate 3 -PitchRate 3 -Vy 6)
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

Write-Host ""
Write-Host ("=== {0} passed, {1} failed ===" -f $script:pass, $script:fail) `
    -ForegroundColor $(if ($script:fail -eq 0) { 'Green' } else { 'Red' })
if ($script:fail -gt 0) { exit 1 }
