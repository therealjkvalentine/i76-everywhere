<#
  ffb-find-rpm.ps1 - locate engine RPM (and, if it shows, gear) in the vehicle
  struct by value-scanning.

  WHY A SCAN AND NOT A DECOMPILE: docs/GHIDRA-MEMORY-MAP.md:149 is explicit -
  "RPM/gear/velocity: nothing anywhere; Gold-exe RE or value-scan required." The
  decompile has no vehicle struct at all. Velocity has since been found by scan;
  RPM and gear are what is left.

  THE DISCRIMINATOR: park the car IN NEUTRAL and blip the throttle.

  NEUTRAL IS NOT OPTIONAL, and getting this wrong cost a whole run. The first
  version of this script said "handbrake on, or nose against a wall" - which
  leaves the car IN GEAR. In gear this sim ties engine speed to wheel speed, so
  the revs sat pinned at idle and the scan correctly reported that nothing in
  0x400 bytes tracked the throttle. The null was real; the procedure was wrong.

  In neutral the engine is disconnected from the drivetrain and the throttle owns
  it outright - confirmed by observation: the tachometer moves and the engine
  note changes with the car stationary and out of gear. So RPM IS independent
  state, not something derived from road speed, and it is findable.

    While stationary, speed is zero and STAYS zero. So does every field derived
    from it - wheel contact points, velocity, yaw, lateral load, the lot. And in
    NEUTRAL the drivetrain is out of the picture too, so torque and drive force
    go quiet as well. RPM is then very nearly the only quantity in the struct
    that can swing across its full range while the car does not move an inch.

    That makes the parked rev a far sharper instrument than the two-phase
    compare in ffb-find-slip.ps1, which had to separate sliding from cornering
    while both were happening at speed - and which found nothing but fields we
    already knew. Here, almost everything is pinned to a constant by
    construction, and whatever moves is a short list.

  SCORING: Pearson correlation against throttle, over the parked frames only.
  RPM will not correlate perfectly - the engine has inertia, so revs lag the
  pedal and hang on the way down - but it should sit far above the noise.
  Throttle itself (+0xE4) will score ~1.0. That is not a false positive, it is
  the control: if +0xE4 does not top the list, the capture went wrong.

  BOTH INTERPRETATIONS: every offset is scored as float AND as int32. RPM is
  plausibly either, and a float scan alone would miss an integer tachometer.

  Read-only. This script never writes to the game.

  RUN IT: with the game running and a mission loaded.
      powershell -NoProfile -ExecutionPolicy Bypass -File tools\ffb\ffb-find-rpm.ps1
#>
param(
    [int]$IdleSeconds = 8,
    [int]$RevSeconds  = 18,
    [int]$DriveSeconds = 30,
    [int]$Range = 0x800,
    [int]$HZ = 30,
    [int]$Top = 14,
    # The rev phase alone settles RPM. Skip the 30s of driving when re-testing.
    [switch]$SkipDrive
)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $here 'Telemetry.ps1')

$OFF_SPEED    = 0xAC
$OFF_THROTTLE = 0xE4

$ctx = Tel-Open
Write-Host ("telemetry OK - entity 0x{0:X8}, scanning {1} bytes" -f $ctx.Ent, $Range) -ForegroundColor Green

function Capture {
    param([string]$Label, [int]$Seconds, [string]$Instruction)
    Write-Host ""
    Write-Host "--- $Label ---" -ForegroundColor Yellow
    foreach ($line in $Instruction -split "`n") { Write-Host "  $line" -ForegroundColor Yellow }
    Write-Host "  Press Enter when you are ready to start." -ForegroundColor Yellow
    [void](Read-Host)

    $buf = New-Object byte[] $Range
    $n = 0
    $rows = New-Object System.Collections.Generic.List[object]
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $last = -1
    while ($sw.Elapsed.TotalSeconds -lt $Seconds) {
        if ([I76Tel]::ReadProcessMemory($ctx.H, [IntPtr]$ctx.Ent, $buf, $Range, [ref]$n)) {
            $row = New-Object 'double[]' ($Range / 2)   # float half, then int half
            for ($o = 0; $o -lt $Range; $o += 4) {
                $f = [BitConverter]::ToSingle($buf, $o)
                if ([double]::IsNaN($f) -or [double]::IsInfinity($f) -or [math]::Abs($f) -gt 1e12) { $f = 0.0 }
                $row[$o / 4] = $f
                $row[($Range / 4) + ($o / 4)] = [double][BitConverter]::ToInt32($buf, $o)
            }
            $rows.Add([pscustomobject]@{
                Speed    = [BitConverter]::ToSingle($buf, $OFF_SPEED)
                Throttle = [BitConverter]::ToSingle($buf, $OFF_THROTTLE)
                V        = $row
            })
        }
        $el = [int]$sw.Elapsed.TotalSeconds
        if ($el -ne $last) { $last = $el; Write-Host ("`r    {0,3}s left  " -f ($Seconds - $el)) -NoNewline }
        Start-Sleep -Milliseconds ([int](1000 / $HZ))
    }
    Write-Host ""
    Write-Host ("    {0} frames" -f $rows.Count) -ForegroundColor DarkGray
    return $rows
}

# Offset naming: the first half of each row vector is the float reading of the
# struct, the second half the int32 reading of the same bytes.
$NSLOT = $Range / 4
function SlotName { param([int]$i)
    if ($i -lt $NSLOT) { return ("+0x{0:X3} f" -f ($i * 4)) }
    return ("+0x{0:X3} i" -f (($i - $NSLOT) * 4))
}
function SlotOffset { param([int]$i) if ($i -lt $NSLOT) { $i * 4 } else { ($i - $NSLOT) * 4 } }

$idle  = Capture "PHASE 1: PARKED IN NEUTRAL, IDLING" $IdleSeconds `
    ("Put the car in NEUTRAL, sit still, foot OFF the throttle.`n" +
     "This is the idle reference, and it has to be in the same state as phase 2`n" +
     "or the comparison is between two different things.")
$rev   = Capture "PHASE 2: PARKED IN NEUTRAL, REVVING" $RevSeconds `
    ("PUT THE CAR IN NEUTRAL FIRST. This phase does not work in gear - in gear`n" +
     "the engine is tied to the wheels and the revs will not budge.`n" +
     "`n" +
     "Then BLIP THE THROTTLE: hard on, all the way off, about once a second.`n" +
     "Watch the tachometer - if the needle is not swinging, the car is still in`n" +
     "gear and this phase will find nothing.")
$drive = if ($SkipDrive) {
    Write-Host ""
    Write-Host "--- PHASE 3 SKIPPED (-SkipDrive) ---" -ForegroundColor DarkGray
    @()
} else { Capture "PHASE 3: FULL-THROTTLE RUNS" $DriveSeconds `
    ("Do TWO OR THREE full-throttle runs from a standstill to top speed.`n" +
     "Brake to a stop between them. Straight line, no turning.`n" +
     "This is the phase that finds a tachometer - see the sawtooth scan below.") }

# ---- score ---------------------------------------------------------------
# Parked frames only. A field that moves because the car rolled is not evidence.
$parked = @($idle + $rev | Where-Object { [math]::Abs($_.Speed) -lt 0.5 })
Write-Host ""
Write-Host ("parked frames usable: {0} of {1}" -f $parked.Count, ($idle.Count + $rev.Count)) -ForegroundColor Cyan
if ($parked.Count -lt 30) {
    Write-Host "NOT ENOUGH PARKED FRAMES - the car was moving. Re-run and keep it still." -ForegroundColor Red
    Tel-Close $ctx; exit 1
}

$thr = $parked | ForEach-Object { [double]$_.Throttle }
$thrMean = ($thr | Measure-Object -Average).Average
$thrVar = 0.0
foreach ($x in $thr) { $thrVar += ($x - $thrMean) * ($x - $thrMean) }
if ($thrVar -lt 1e-6) {
    Write-Host "THROTTLE NEVER MOVED - phase 2 did not record any revving. Re-run." -ForegroundColor Red
    Tel-Close $ctx; exit 1
}

$results = New-Object System.Collections.Generic.List[object]
$total = $NSLOT * 2
for ($i = 0; $i -lt $total; $i++) {
    $mean = 0.0
    foreach ($r in $parked) { $mean += $r.V[$i] }
    $mean /= $parked.Count

    $var = 0.0; $cov = 0.0; $mn = [double]::MaxValue; $mx = [double]::MinValue
    for ($k = 0; $k -lt $parked.Count; $k++) {
        $d = $parked[$k].V[$i] - $mean
        $var += $d * $d
        $cov += $d * ($thr[$k] - $thrMean)
        if ($parked[$k].V[$i] -lt $mn) { $mn = $parked[$k].V[$i] }
        if ($parked[$k].V[$i] -gt $mx) { $mx = $parked[$k].V[$i] }
    }
    if ($var -lt 1e-9) { continue }   # pinned constant while parked - not RPM
    $r = $cov / [math]::Sqrt($var * $thrVar)

    $results.Add([pscustomobject]@{
        Slot = $i; Name = (SlotName $i); Off = (SlotOffset $i)
        R = $r; AbsR = [math]::Abs($r); Min = $mn; Max = $mx
    })
}

Write-Host ""
Write-Host "=== fields that MOVE while parked, ranked by correlation with throttle ===" -ForegroundColor Cyan
Write-Host "(+0xE4 f is the throttle itself and MUST be at the top - it is the control)" -ForegroundColor DarkGray
Write-Host ""
Write-Host ("  {0,-12} {1,7}  {2,14}  {3,14}   {4}" -f 'field','r','parked min','parked max','through the gears')
Write-Host ("  " + ("-" * 88))

$ranked = $results | Sort-Object -Property AbsR -Descending | Select-Object -First $Top
foreach ($c in $ranked) {
    # describe phase 3 - does it climb with speed, or saw back on each shift?
    $dv = $drive | ForEach-Object { $_.V[$c.Slot] }
    $desc = 'no drive data'
    if ($dv.Count -gt 4) {
        $dmn = ($dv | Measure-Object -Minimum).Minimum
        $dmx = ($dv | Measure-Object -Maximum).Maximum
        # count direction reversals - a tachometer sawtooths as it shifts up,
        # while speed and anything proportional to it climbs monotonically
        $falls = 0
        for ($k = 4; $k -lt $dv.Count; $k++) {
            if ($dv[$k] -lt $dv[$k-4] - ([math]::Abs($dmx - $dmn) * 0.05)) { $falls++ }
        }
        $pct = if ($dv.Count -gt 4) { [math]::Round(100.0 * $falls / ($dv.Count - 4)) } else { 0 }
        $desc = ("{0,10:0.###} .. {1,-10:0.###} falls {2,3}%" -f $dmn, $dmx, $pct)
    }
    $col = if ($c.Off -eq $OFF_THROTTLE) { 'DarkGray' }
           elseif ($c.AbsR -gt 0.6) { 'Green' } else { 'Gray' }
    Write-Host ("  {0,-12} {1,7:0.000}  {2,14:0.###}  {3,14:0.###}   {4}" -f `
        $c.Name, $c.R, $c.Min, $c.Max, $desc) -ForegroundColor $col
}

Write-Host ""
Write-Host "HOW TO READ THIS:" -ForegroundColor Cyan
Write-Host "  RPM should show: high |r|, a parked range that spans idle to redline," -ForegroundColor Gray
Write-Host "  and - the giveaway - a HIGH 'falls' percentage through the gears, because" -ForegroundColor Gray
Write-Host "  a tachometer drops on every upshift while road speed only climbs." -ForegroundColor Gray
Write-Host "  A field that correlates with throttle but NEVER falls in phase 3 is far" -ForegroundColor Gray
Write-Host "  more likely to be drive force or acceleration than engine speed." -ForegroundColor Gray
Write-Host ""
$strong = @($results | Where-Object { $_.AbsR -gt 0.5 -and $_.Off -ne $OFF_THROTTLE })
if ($strong.Count -eq 0) {
    Write-Host "  NOTHING BUT THROTTLE CORRELATED. Before widening the scan, check the" -ForegroundColor Yellow
    Write-Host "  most likely cause: WAS THE CAR IN NEUTRAL? In gear, engine speed is" -ForegroundColor Yellow
    Write-Host "  tied to wheel speed and the revs cannot move at a standstill, so this" -ForegroundColor Yellow
    Write-Host "  scan has nothing to see. That is what happened on the first run." -ForegroundColor Yellow
    Write-Host "  If the tachometer WAS swinging, RPM lives outside these $Range bytes -" -ForegroundColor Yellow
    Write-Host "  re-run with a larger -Range, or it sits in a sub-struct reached by" -ForegroundColor Yellow
    Write-Host "  pointer, which needs a pointer-chasing scan." -ForegroundColor Yellow
}
Write-Host ""
Write-Host "  GEAR, if present, is an int a few slots from RPM: a small integer (0-4)" -ForegroundColor Gray
Write-Host "  that is CONSTANT while parked and steps up in phase 3. It will not appear" -ForegroundColor Gray
Write-Host "  in the list above - constants while parked are filtered out by design -" -ForegroundColor Gray
Write-Host "  so it is reported separately below." -ForegroundColor Gray

# ---- sawtooth scan: the signature of a tachometer -------------------------
# The parked rev only finds RPM if RPM is INDEPENDENT STATE. If this engine
# derives it from road speed and gear - which a 1997 automatic plausibly does -
# then revving while stationary changes nothing and the parked scan is blind to
# it. That is exactly what the first run of this script found: of 0x400 bytes,
# only throttle and steer moved at all.
#
# This scan does not care which it is. However RPM is computed, it must SAWTOOTH:
# it climbs with speed, then DROPS on every upshift, while road speed carries on
# climbing straight through. Nothing else in a vehicle struct does that - speed,
# drive force and acceleration all rise monotonically under full throttle.
#
# So: count sharp falls that happen while speed is RISING.
Write-Host ""
Write-Host "=== sawtooth scan: fields that DROP while road speed keeps climbing ===" -ForegroundColor Cyan

$dspd = @($drive | ForEach-Object { [double]$_.Speed })
$dTop = if ($dspd.Count) { ($dspd | Measure-Object -Maximum).Maximum } else { 0 }
if ($dspd.Count -lt 20) {
    Write-Host "  phase 3 too short to analyse." -ForegroundColor Red
} elseif ($dTop -lt 5.0) {
    Write-Host ("  THE CAR NEVER MOVED IN PHASE 3 (max speed {0:0.0} m/s)." -f $dTop) -ForegroundColor Red
    Write-Host "  Re-run and drive for phase 3 - this scan needs gear changes." -ForegroundColor Red
} else {
    Write-Host ("  phase 3: {0} frames, speed 0 .. {1:0.0} m/s ({2:0} mph)" -f `
        $dspd.Count, $dTop, ($dTop * 2.23694)) -ForegroundColor DarkGray
    Write-Host ""

    $W = 3   # frames to look back. At 30 Hz that is 100 ms - a shift is quicker.
    $saw = New-Object System.Collections.Generic.List[object]
    for ($i = 0; $i -lt $total; $i++) {
        $dv = @($drive | ForEach-Object { $_.V[$i] })
        $mn = ($dv | Measure-Object -Minimum).Minimum
        $mx = ($dv | Measure-Object -Maximum).Maximum
        $span = $mx - $mn
        if ($span -le 0) { continue }                      # constant - not a tacho
        if ([math]::Abs($mx) -gt 1e9) { continue }         # pointer or garbage

        # a drop worth counting is a real fraction of the field's own range
        $thr = $span * 0.12
        $drops = 0
        for ($k = $W; $k -lt $dv.Count; $k++) {
            if (($dv[$k] - $dv[$k - $W]) -lt -$thr -and ($dspd[$k] - $dspd[$k - $W]) -gt 0.15) {
                $drops++
            }
        }
        if ($drops -lt 2) { continue }        # need at least two upshifts
        if ($drops -gt 40) { continue }       # that is oscillation, not a gearbox

        # and it must broadly TRACK speed the rest of the time, or it is just noise
        $fm = ($dv | Measure-Object -Average).Average
        $sm = ($dspd | Measure-Object -Average).Average
        $corr = 0.0; $fv = 0.0; $sv = 0.0
        for ($k = 0; $k -lt $dv.Count; $k++) {
            $a = $dv[$k] - $fm; $b = $dspd[$k] - $sm
            $corr += $a * $b; $fv += $a * $a; $sv += $b * $b
        }
        if ($fv -gt 1e-9 -and $sv -gt 1e-9) { $corr = $corr / [math]::Sqrt($fv * $sv) }

        $saw.Add([pscustomobject]@{
            Name = (SlotName $i); Off = (SlotOffset $i); Drops = $drops
            Min = $mn; Max = $mx; Corr = $corr })
    }

    if ($saw.Count -eq 0) {
        Write-Host "  NOTHING SAWTOOTHS. No field drops while speed climbs." -ForegroundColor Yellow
        Write-Host "  That is strong evidence the tachometer is computed inside the HUD" -ForegroundColor Gray
        Write-Host "  draw and never stored - in which case synthesising RPM from speed" -ForegroundColor Gray
        Write-Host "  is cheaper than continuing to hunt for it." -ForegroundColor Gray
    } else {
        Write-Host ("  {0,-12} {1,6}  {2,7}  {3,12}  {4,12}" -f 'field','drops','r/speed','min','max')
        Write-Host ("  " + ("-" * 60))
        foreach ($c in ($saw | Sort-Object Drops -Descending | Select-Object -First 20)) {
            $col = if ($c.Drops -ge 2 -and $c.Drops -le 12) { 'Green' } else { 'Gray' }
            Write-Host ("  {0,-12} {1,6}  {2,7:0.00}  {3,12:0.###}  {4,12:0.###}" -f `
                $c.Name, $c.Drops, $c.Corr, $c.Min, $c.Max) -ForegroundColor $col
        }
        Write-Host ""
        Write-Host "  2-6 drops with a positive r is the shape of a tachometer:" -ForegroundColor Gray
        Write-Host "  a few upshifts per run, rising with speed in between." -ForegroundColor Gray
    }
}

# ---- gear hunt -----------------------------------------------------------
# Opposite signature to RPM: still while parked, stepping while driving. Scanned
# as BOTH int and float - a gearbox is as likely to be stored as its ratio (2.5,
# 1.8, 1.0) as an index, and the previous int-only pass would have missed that.
Write-Host ""
Write-Host "=== gear candidates: constant while parked, few discrete steps under way ===" -ForegroundColor Cyan
$gearHits = New-Object System.Collections.Generic.List[object]
for ($i = 0; $i -lt $total; $i++) {
    $pv = @($parked | ForEach-Object { $_.V[$i] })
    $pMin = ($pv | Measure-Object -Minimum).Minimum
    if ($pMin -ne (($pv | Measure-Object -Maximum).Maximum)) { continue }
    if ([math]::Abs($pMin) -gt 10) { continue }      # an index or a ratio, not a pointer
    $dv = @($drive | ForEach-Object { $_.V[$i] })
    if ($dv.Count -lt 4) { continue }
    $dmn = ($dv | Measure-Object -Minimum).Minimum
    $dmx = ($dv | Measure-Object -Maximum).Maximum
    if ($dmx -le $dmn -or [math]::Abs($dmx) -gt 10) { continue }
    $steps = @($dv | Sort-Object -Unique).Count
    if ($steps -lt 2 -or $steps -gt 8) { continue }  # a gearbox has a few states
    $gearHits.Add([pscustomobject]@{
        Name = (SlotName $i); Parked = $pMin; DMin = $dmn; DMax = $dmx; Steps = $steps })
}
if ($gearHits.Count -eq 0) {
    Write-Host "  none - nothing small stepped between parked and driving." -ForegroundColor DarkGray
} else {
    foreach ($g in ($gearHits | Sort-Object Steps -Descending | Select-Object -First 12)) {
        Write-Host ("  {0,-12}  parked {1,7:0.###}   driving {2:0.###}..{3:0.###}   {4} distinct values" -f `
            $g.Name, $g.Parked, $g.DMin, $g.DMax, $g.Steps) -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "Paste the whole output back. Read-only - nothing was written to the game." -ForegroundColor Cyan
Tel-Close $ctx
