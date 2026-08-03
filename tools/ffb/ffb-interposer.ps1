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

  Live keys: [space] mute  [+/-] master  [r] reload tune  [s] save tune  [q] quit

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
    # Channel names: center corner oversteer brake texture scrub judder impact
    [string[]]$Only = @(),
    [string[]]$Mute = @(),
    [switch]$NoPanel,
    [string]$Log = "",
    [string]$Tune = "",
    [int]$Seconds = 0        # 0 = until [q] or Ctrl+C
)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $here 'Telemetry.ps1')
. (Join-Path $here 'FfbMixer.ps1')
if (-not $DryRun) { . (Join-Path $here 'FfbCore.ps1') }

$ALL_CH = @('center','corner','oversteer','brake','texture','scrub','judder','impact')

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

$telCtx = $null
$dev    = $null
$logSw  = $null
try {
    $telCtx = Tel-Open
    Write-Host ("telemetry OK - entity 0x{0:X8}, wheelbase {1:0.00} m, track {2:0.00} m" -f `
        $telCtx.Ent, $telCtx.Wheelbase, $telCtx.Track) -ForegroundColor Green

    $tuneTable = Mix-DefaultTune
    if ($Tune -and (Test-Path $Tune)) {
        $j = Get-Content $Tune -Raw | ConvertFrom-Json
        foreach ($p in $j.PSObject.Properties) { $tuneTable[$p.Name] = $p.Value }
        Write-Host "tune loaded from $Tune" -ForegroundColor Green
    }
    $tuneTable['Master'] = $Master
    $mix = Mix-New $tuneTable

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

    if ($Log) {
        $logSw = [System.IO.StreamWriter]::new($Log, $false)
        $logSw.WriteLine("t,speed,mph,steer,throttle,longG,latG,yaw,expectYaw,understeer,oversteer,jolt," +
                         "center,corner,oversteer_f,brake,texture,scrub,judder,impact,force")
    }

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

    if ($canDraw) { Clear-Host }

    while ($true) {
        $frameStart = $sw.Elapsed.TotalSeconds
        if ($Seconds -gt 0 -and $frameStart -gt $Seconds) { break }

        $s = Tel-Sample $telCtx
        if ($s) {
            $lastS = $s
            $out = Mix-Update $mix $s

            # Apply channel gating by rebuilding the sum from the breakdown, so
            # -Only / -Mute are exact rather than approximate.
            $f = 0.0
            foreach ($c in $ALL_CH) {
                if ($active[$c] -and $out.Channels.Contains($c)) { $f += [double]$out.Channels[$c] }
            }
            $f = $f * $tuneTable['Master'] * $out.Ramp
            if (-not $mix.Enabled) { $f = 0 }
            $lim = $tuneTable['Clamp']
            if ($f -gt $lim) { $f = $lim } elseif ($f -lt -$lim) { $f = -$lim }
            $force = [int]$f

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
                        } else {
                            $null = $noteHist.Insert(0, ("{0,7:0.0}s  DEVICE LOST hr=0x{1:X8}" -f $frameStart, $hr))
                        }
                    }
                } else { $lostCount = 0 }
            }

            foreach ($nt in $out.Notes) {
                $null = $noteHist.Insert(0, ("{0,7:0.0}s  {1}" -f $frameStart, $nt))
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
                    ('{0:0.000}' -f $s.Jolt)
                )
                foreach ($c in $ALL_CH) { $cols += [string][int]$out.Channels[$c] }
                $cols += [string]$force
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

        # ---- panel ---------------------------------------------------------
        if ($canDraw -and $frameStart -ge $nextDraw) {
            $nextDraw = $frameStart + 0.07     # ~14 Hz; the force loop runs far faster
            [Console]::SetCursorPosition(0, 0)
            $mode = if ($DryRun) { "DRY RUN (wheel untouched)" } else { "LIVE -> $($dev.Name)" }
            $lines = New-Object System.Collections.ArrayList
            $null = $lines.Add(("  I76 FFB INTERPOSER   {0}" -f $mode))
            $null = $lines.Add(("  entity 0x{0:X8}   wheelbase {1:0.00} m   sim ticks {2}" -f `
                $telCtx.Ent, $telCtx.Wheelbase, $(if ($lastS) { $lastS.Ticks } else { 0 })))
            $null = $lines.Add(("  " + ("-" * 74)))
            if ($lastS) {
                $null = $lines.Add(("   speed {0,6:0.0} mph ({1,5:0.0} m/s)    throttle {2,6:0.00}    steer {3,6:0.00}" -f `
                    $lastS.SpeedMph, $lastS.Speed, $lastS.Throttle, $lastS.Steer))
                $null = $lines.Add(("   long g {0,6:0.00}   lat g {1,6:0.00}   jolt {2,6:0.0}   {3}{4}" -f `
                    $lastS.LongG, $lastS.LatG, $lastS.Jolt,
                    $(if ($lastS.Braking) { "BRAKING " } else { "" }),
                    $(if ($lastS.Airborne) { "AIRBORNE" } else { "" })))
                $null = $lines.Add(("   yaw {0,7:0.000} rad/s   expected {1,7:0.000}   grip {2,3:0}%   U {3,4:0.00} O {4,4:0.00}" -f `
                    $lastS.YawRate, $lastS.ExpectedYaw, $lastOut.Channels['grip%'],
                    $lastS.Understeer, $lastS.Oversteer))
            } else {
                $null = $lines.Add("   (no telemetry - paused, at a menu, or between missions)")
                $null = $lines.Add(""); $null = $lines.Add("")
            }
            $null = $lines.Add(("  " + ("-" * 74)))
            if ($lastOut) {
                foreach ($c in $ALL_CH) {
                    $v = [double]$lastOut.Channels[$c]
                    $tag = if ($active[$c]) { " " } else { "x" }
                    $null = $lines.Add(("  {0}{1,-10}{2,7}  |{3}|" -f $tag, $c, [int]$v, (Bar $v 5000)))
                }
                $null = $lines.Add(("  " + ("-" * 74)))
                $null = $lines.Add(("   FORCE {0,7}  {1}   peak {2,5:0}" -f `
                    $lastForce, (CenterBar $lastForce 9500), $mix.PeakForce))
            }
            $null = $lines.Add(("  " + ("-" * 74)))
            $null = $lines.Add(("   loop {0,5:0.0} Hz   master {1:0.00}   {2}" -f `
                $rateNow, $tuneTable['Master'],
                $(if ($mix.Enabled) { "ARMED " } else { "MUTED " })))
            $null = $lines.Add("   [space] mute  [+/-] master  [s] save tune  [q] quit")
            $null = $lines.Add(("  " + ("-" * 74)))
            $null = $lines.Add("   events:")
            foreach ($n in $noteHist) { $null = $lines.Add("     $n") }
            for ($i = $noteHist.Count; $i -lt 6; $i++) { $null = $lines.Add("") }
            foreach ($ln in $lines) { Write-Host $ln.PadRight(78) }
        }

        # ---- live keys -----------------------------------------------------
        # Probed once, not per frame: [Console]::KeyAvailable throws outright
        # when stdin is redirected (piped, or run from a harness rather than a
        # terminal), and a throw here would take down a loop that is holding the
        # wheel. No console just means no hotkeys.
        while ($canKeys -and [Console]::KeyAvailable) {
            $k = [Console]::ReadKey($true)
            switch ($k.KeyChar) {
                ' ' { $mix.Enabled = -not $mix.Enabled; if (-not $DryRun -and -not $mix.Enabled) { $null = Ffb-Constant $dev 0 } }
                '+' { $tuneTable['Master'] = [math]::Min(1.5, $tuneTable['Master'] + 0.05) }
                '=' { $tuneTable['Master'] = [math]::Min(1.5, $tuneTable['Master'] + 0.05) }
                '-' { $tuneTable['Master'] = [math]::Max(0.0, $tuneTable['Master'] - 0.05) }
                's' {
                    $p = Join-Path $here 'ffb-tune.json'
                    ($tuneTable | ConvertTo-Json) | Set-Content -Path $p -Encoding ASCII
                    $null = $noteHist.Insert(0, "        saved tune -> ffb-tune.json")
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
    if ($dev) {
        try { $null = Ffb-Constant $dev 0 } catch { }
        try { Ffb-Stop $dev } catch { }
        try { Ffb-Close $dev } catch { }
        Write-Host "wheel released." -ForegroundColor Cyan
    }
    if ($logSw) { $logSw.Flush(); $logSw.Close(); Write-Host "log -> $Log" -ForegroundColor Cyan }
    if ($telCtx) { Tel-Close $telCtx }
}
