<#
  ffb-bench.ps1 - feel the whole force range on YOUR wheel, and measure its floor.

  Every gain in this system is a number between 0 and 10000, and until now nobody
  had felt what those numbers mean on this particular wheel. "Barely perceptible"
  and "too strong" are the only measurements that matter and they live in your
  hands, so this puts known magnitudes there one at a time.

      tools\ffb\ffb-bench.ps1                 # the ladder: 250 -> 9500
      tools\ffb\ffb-bench.ps1 -Stiction       # find MinForce: where does it MOVE?
      tools\ffb\ffb-bench.ps1 -Hold 3000      # sit at one value and judge it
      tools\ffb\ffb-bench.ps1 -Compare        # against the game's own effects

  Needs the wheel free - quit the interposer first, and the game does not need to
  be running at all.

  ---------------------------------------------------------------------------
  THE TWO NUMBERS THIS EXISTS TO FIND
  ---------------------------------------------------------------------------
  MinForce - the belt drive's stiction floor. Below some magnitude a belt or gear
  wheel is commanded and the rim does not move; that force is spent and felt by
  nobody. -Stiction ramps slowly upward until you say it moved. Everything the
  model produces below that number was wasted, which is the likeliest single
  reason a carefully-built force model can read as "barely there".

  Working range - what fraction of 0..10000 is actually useful before the wheel
  is unpleasant or hits its thermal limit. The ladder walks it.

  ---------------------------------------------------------------------------
  THE REFERENCE POINT THE GAME ITSELF PROVIDES
  ---------------------------------------------------------------------------
  I'76's own authored effects (force\*.frc, decoded by tools/ffb/parse-frc.py)
  carry envelope values of +/-100 - percent of full scale. Cannon fire,
  explosions and tyre blowouts are authored at FULL MAGNITUDE. In DirectInput
  terms that is 10000, the top of this ladder.

  So the engine's own transients are the loudest thing this wheel is ever asked
  for, and they are a fair yardstick: our impacts should land near them, and our
  steady cornering should sit at 40-70% of range per sim-racing practice.

  SAFETY: hold the rim or let it move freely, but do not brace it hard. Forces
  release between steps, and [q] or Ctrl+C stops immediately.
#>
param(
    [switch]$Stiction,
    [int]$Hold = 0,
    [switch]$Compare,
    [double]$StepSeconds = 1.4,
    [int]$Max = 9500
)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $here 'FfbCore.ps1')
. (Join-Path $here 'FfbMixer.ps1')

$dev = $null
try {
    Write-Host "opening the wheel..." -ForegroundColor Cyan
    try { $dev = Ffb-Open }
    catch {
        Write-Host "COULD NOT ACQUIRE THE WHEEL: $_" -ForegroundColor Red
        Write-Host "Quit ffb-interposer.ps1 and close the Thrustmaster control panel." -ForegroundColor Yellow
        exit 2
    }
    Write-Host "ACQUIRED: $($dev.Name)" -ForegroundColor Green
    $canKeys = $true
    try { $null = [Console]::KeyAvailable } catch { $canKeys = $false }

    # ---- hold one value -------------------------------------------------
    if ($Hold -ne 0) {
        $m = [math]::Max(-$Max, [math]::Min($Max, $Hold))
        Write-Host ""
        Write-Host ("holding {0} ({1:0}% of {2}). Ctrl+C to stop." -f $m, ($m * 100.0 / $Max), $Max) -ForegroundColor Yellow
        while ($true) { $null = Ffb-Constant $dev $m; Start-Sleep -Milliseconds 200 }
    }

    # ---- stiction floor ---------------------------------------------------
    if ($Stiction) {
        Write-Host ""
        Write-Host "STICTION TEST - finding the floor below which the rim does not move." -ForegroundColor Yellow
        Write-Host "Let the wheel move FREELY - hands off, or resting weightlessly." -ForegroundColor Yellow
        Write-Host "Press ANY KEY the moment you see or feel it actually move." -ForegroundColor Yellow
        Write-Host ""
        if ($canKeys) { while ([Console]::KeyAvailable) { $null = [Console]::ReadKey($true) } }
        Start-Sleep -Seconds 2
        $found = 0
        # Alternate direction each step: a wheel already resting against its own
        # friction in one direction will break free at a different level than one
        # pushed the other way, and the honest floor is the larger of the two.
        for ($m = 100; $m -le 4000; $m += 100) {
            $sign = if ((($m / 100) % 2) -eq 0) { 1 } else { -1 }
            Write-Host ("`r  trying {0,5}  ({1,4:0.0}% of clamp) " -f $m, ($m * 100.0 / $Max)) -NoNewline
            $null = Ffb-Constant $dev ($m * $sign)
            $t0 = [System.Diagnostics.Stopwatch]::StartNew()
            while ($t0.Elapsed.TotalSeconds -lt 0.7) {
                if ($canKeys -and [Console]::KeyAvailable) { $null = [Console]::ReadKey($true); $found = $m; break }
                Start-Sleep -Milliseconds 30
            }
            $null = Ffb-Constant $dev 0
            if ($found) { break }
            Start-Sleep -Milliseconds 250
        }
        Write-Host ""
        Write-Host ""
        if ($found) {
            $suggest = [int]([math]::Round($found * 1.15 / 50) * 50)
            Write-Host ("the wheel broke free at about {0}" -f $found) -ForegroundColor Green
            Write-Host ("  -> set MinForce = {0} in FfbMixer.ps1 (the floor plus ~15% margin)" -f $suggest) -ForegroundColor Green
            Write-Host ("  -> that is {0:0.0}% of the {1} clamp" -f ($suggest * 100.0 / $Max), $Max) -ForegroundColor DarkGray
            Write-Host ""
            Write-Host "Everything the force model produced below that number was being" -ForegroundColor DarkGray
            Write-Host "commanded and felt by nobody." -ForegroundColor DarkGray
        } else {
            Write-Host "no keypress recorded - either nothing moved up to 4000 (check the" -ForegroundColor Yellow
            Write-Host "wheel and its power supply) or this console cannot read keys." -ForegroundColor Yellow
        }
        return
    }

    # ---- the game's own effects, for comparison ---------------------------
    if ($Compare) {
        Write-Host ""
        Write-Host "COMPARISON - what the GAME asks this wheel for, versus what we ask." -ForegroundColor Yellow
        Write-Host "I'76's authored effects carry envelope values of +/-100 percent, so its" -ForegroundColor DarkGray
        Write-Host "cannon fire and explosions are FULL SCALE. Ours should be judged against" -ForegroundColor DarkGray
        Write-Host "that, not against silence." -ForegroundColor DarkGray
        Write-Host ""
        $tune = Mix-DefaultTune
        $ref = @(
            @{ n = "our typical cornering (measured p90 on a real drive)"; v = 435 }
            @{ n = "our peak, before the 2026-08-08 gain rise";            v = 2354 }
            @{ n = "our steady pair at HALF lock, after the rise";         v = [int](($tune.SatGain + $tune.CornerGain) * 0.5) }
            @{ n = "our steady pair at FULL lock, after the rise";         v = [int]($tune.SatGain + $tune.CornerGain) }
            @{ n = "our full-scale impact (ImpactGain)";                   v = [int]$tune.ImpactGain }
            @{ n = "the GAME's own effects - cannon, explosion, blowout";  v = 10000 }
        )
        foreach ($r in $ref) {
            $v = [math]::Min($Max, $r.v)
            Write-Host ("  {0,5}  {1,4:0}%   {2}" -f $v, ($v * 100.0 / $Max), $r.n) -ForegroundColor Cyan
            foreach ($s in @(1, -1)) {
                $null = Ffb-Constant $dev ($v * $s)
                Start-Sleep -Milliseconds ([int]($StepSeconds * 500))
            }
            $null = Ffb-Constant $dev 0
            Start-Sleep -Milliseconds 400
            if ($canKeys -and [Console]::KeyAvailable) {
                if ([Console]::ReadKey($true).KeyChar -eq 'q') { break }
            }
        }
        return
    }

    # ---- the ladder --------------------------------------------------------
    Write-Host ""
    Write-Host "FORCE LADDER - each level held briefly, one way then the other." -ForegroundColor Yellow
    Write-Host "Note where you FIRST feel it, and where it stops being pleasant." -ForegroundColor Yellow
    Write-Host "[q] to stop early." -ForegroundColor Yellow
    Write-Host ""
    Start-Sleep -Seconds 2
    foreach ($m in @(250, 500, 750, 1000, 1500, 2000, 3000, 4000, 5000, 6500, 8000, 9500)) {
        if ($m -gt $Max) { break }
        $pct = $m * 100.0 / $Max
        $note = switch ($true) {
            ($m -le 750)  { "below or near a belt wheel's stiction floor" ; break }
            ($m -le 2000) { "quiet - light steering, road texture" ; break }
            ($m -le 5000) { "the 40-70% band sim practice puts cornering in" ; break }
            ($m -le 8000) { "heavy - kerbs, hard cornering" ; break }
            default       { "near full scale - where the GAME's own effects live" }
        }
        Write-Host ("  {0,5}  {1,4:0}%   {2}" -f $m, $pct, $note)
        foreach ($s in @(1, -1)) {
            $null = Ffb-Constant $dev ($m * $s)
            Start-Sleep -Milliseconds ([int]($StepSeconds * 500))
        }
        $null = Ffb-Constant $dev 0
        Start-Sleep -Milliseconds 350
        if ($canKeys -and [Console]::KeyAvailable) {
            if ([Console]::ReadKey($true).KeyChar -eq 'q') { break }
        }
    }
    Write-Host ""
    Write-Host "Now: the level you first felt is your MinForce (plus ~15% margin)," -ForegroundColor Green
    Write-Host "and the level that stopped being pleasant is your Clamp." -ForegroundColor Green
    Write-Host "Both live in Mix-DefaultTune in tools\ffb\FfbMixer.ps1." -ForegroundColor Green
}
finally {
    if ($dev) {
        try { $null = Ffb-Constant $dev 0 } catch { }
        try { Ffb-Stop $dev } catch { }
        try { Ffb-Close $dev } catch { }
        Write-Host ""
        Write-Host "wheel released." -ForegroundColor Cyan
    }
}
