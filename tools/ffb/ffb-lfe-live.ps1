<#
  ffb-lfe-live.ps1 - drive the bass shakers WHILE YOU PLAY.

  Everything before this rendered a captured drive to a WAV after the fact. That
  is the right tool for inspecting a spectrum and a poor one for judging feel:
  by the time you hear it you are no longer driving, and the thing being judged -
  whether a force arrives at the moment the car does something - is exactly what
  a replay cannot tell you.

  This reads telemetry live and streams to the shaker, alongside the interposer
  driving the wheel. Read-only on game memory, so the two do not contend.

  HOW IT STAYS FED: synthesis runs on a dedicated C# audio thread inside LfeLive,
  not in the PowerShell loop. PowerShell only pushes parameters at ~60 Hz. That
  matters because PowerShell's timer granularity is around 15 ms and its garbage
  collector can pause longer than one buffer - either would be a dropout if the
  audio came from here. The audio thread keeps four buffers in flight and refills
  whichever has drained, so a late parameter update makes the shaker 16 ms stale
  rather than making it click.

  SAME DSP AS THE OFFLINE RENDER: both call LfeCore.Step, from LfeSynth.ps1. What
  you hear from ffb-lfe.ps1 and what you feel here cannot drift apart.

  RUN IT (with the game running, and the interposer too if you want both):
      powershell -NoProfile -ExecutionPolicy Bypass -File tools\ffb\ffb-lfe-live.ps1 -ListDevices
      powershell -NoProfile -ExecutionPolicy Bypass -File tools\ffb\ffb-lfe-live.ps1 -Device 0
  Ctrl-C to stop, or it exits on its own when the game closes.
#>
param(
    [switch]$ListDevices,
    [int]$Device = -1,
    [int]$Rate = 16000,        # 2x the offline rate: halves buffer latency for
                               # the same buffer count, and costs nothing here
    [int]$BufSamples = 256,    # 16 ms per buffer at 16 kHz
    [int]$Buffers = 4,         # ~64 ms of queue - enough to survive a GC pause,
                               # short enough that an impact still lands on time
    [double]$Master = 0.9,
    # PRE-LIMITER GAIN, into a soft knee at 0.8. Below the knee nothing is
    # touched at all, so the mix is only squashed to the extent it is driven
    # past it.
    # Measured on drive3.csv, RMS relative to the original build. This is the
    # squash/level trade-off, and it is the whole decision:
    #
    #     drive   RMS gain   limited   crest
    #      2.0      2.93x      1.1%    13.5 dB   fully natural
    #      2.8      3.87x      1.7%    11.1 dB   <- default: 2x the last build
    #      4.0      5.24x      2.4%     8.4 dB   noticeably compressed
    #      6.0      7.50x      8.6%     5.3 dB   squashed
    #
    # Peak output is already 90% of digital full scale at ANY of these - the
    # ceiling does not move, only how hard the mix is pressed against it. So
    # more loudness past about 4.0 is not available in software at any price;
    # it has to come from amplifier gain.
    [double]$Drive = 2.8,

    [int]$Hz = 60,
    [switch]$NoCompensate
)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $here 'Telemetry.ps1')
. (Join-Path $here 'FfbMixer.ps1')
. (Join-Path $here 'LfeSynth.ps1')

if ($ListDevices) {
    Write-Host ""
    Write-Host "output devices (pass the number as -Device):" -ForegroundColor Cyan
    Write-Host ("  {0,3}  {1}" -f '-1', 'system default (WAVE_MAPPER)')
    $d = [LfeOut]::Devices()
    for ($k = 0; $k -lt $d.Count; $k++) { Write-Host ("  {0,3}  {1}" -f $k, $d[$k]) }
    Write-Host ""
    Write-Host "Pick the one your SHAKERS are on." -ForegroundColor Yellow
    exit 0
}

$tune = Mix-DefaultTune
$ctx = Tel-Open
Write-Host ("telemetry OK - entity 0x{0:X8}" -f $ctx.Ent) -ForegroundColor Green

$devs = [LfeOut]::Devices()
$devName = if ($Device -lt 0 -or $Device -ge $devs.Count) { 'system default' } else { $devs[$Device] }

$live = New-Object LfeLive
$err = $live.Start($Device, $Rate,
    [double]$tune.LfeEngineJitter, [double]$tune.LfeImpactHz, [double]$tune.LfeWeaponHz,
    [double]$tune.LfeCarrierHz, 11.0, 85.0,
    $(if ($NoCompensate) { $null } else { [double[]]$tune.LfeRespHz }),
    [double[]]$tune.LfeRespRel,
    $(if ($NoCompensate) { 1.0 } else { [double]$tune.LfeCompMax }),
    $BufSamples, $Buffers)
if ($err) {
    Write-Host "COULD NOT OPEN AUDIO: $err" -ForegroundColor Red
    Write-Host "Run with -ListDevices and pick one that exists." -ForegroundColor Red
    Tel-Close $ctx; exit 1
}
$live.Master = $Master
$live.Drive  = $Drive

Write-Host ("streaming to {0} at {1} Hz, {2} x {3}-sample buffers ({4:0} ms)" -f `
    $devName, $Rate, $Buffers, $BufSamples, (1000.0 * $Buffers * $BufSamples / $Rate)) -ForegroundColor Green
Write-Host ("drive {0:0.0}x into a soft knee at 0.6 - peaks compress, they do not clip" -f $Drive) -ForegroundColor DarkGray
Write-Host ("bands: engine {0}-{1}  heave {2}  impact {3}  road {4}-{5}  weapon {6} Hz" -f `
    $tune.LfeEngineIdleHz, $tune.LfeEngineMaxHz, $tune.LfeCarrierHz, $tune.LfeImpactHz,
    $tune.LfeRoadLoHz, $tune.LfeRoadHiHz, $tune.LfeWeaponHz) -ForegroundColor DarkGray
if ($NoCompensate) {
    Write-Host "response compensation OFF - raw, for A/B against a compensated run" -ForegroundColor Yellow
}
Write-Host ""
Write-Host "Ctrl-C to stop." -ForegroundColor Yellow
Write-Host ""

$mix = Mix-New
$sleepMs = [int](1000 / $Hz)
$lastPrint = 0.0
$sw = [System.Diagnostics.Stopwatch]::StartNew()

try {
    while ($true) {
        $s = Tel-Sample $ctx
        if ($null -eq $s) {
            # Game gone or between missions. Silence rather than a held tone -
            # a stuck drone is worse than nothing and sounds like a crash.
            $live.EngineAmp = 0; $live.RoadAmp = 0
            $live.ImpulseAmp = 0; $live.WeaponAmp = 0; $live.HeaveAmp = 0
            # Same exit test the interposer uses (ffb-interposer.ps1:398).
            if ($ctx.Proc.HasExited) { Write-Host "`nthe game exited." -ForegroundColor Cyan; break }
            Start-Sleep -Milliseconds 200
            continue
        }

        $o = Mix-Update $mix $s
        $L = $o.Bus.Lfe
        $live.EngineFreq = [double]$L.EngineFreq
        $live.EngineAmp  = [double]$L.EngineAmp
        $live.RoadFreq   = [double]$(if ($null -ne $L.RoadFreq) { $L.RoadFreq } else { 60.0 })
        $live.RoadAmp    = [double]$L.RoadAmp
        $live.ImpulseAmp = [double]$L.ImpulseAmp
        $live.WeaponAmp  = [double]$L.WeaponAmp
        $live.HeaveAmp   = [double]$(if ($null -ne $L.HeaveAmp) { $L.HeaveAmp } else { 0.0 })

        $now = $sw.Elapsed.TotalSeconds
        if ($now - $lastPrint -gt 0.25) {
            $lastPrint = $now
            Write-Host ("`r  {0,5:0} mph   engine {1,4:0.0}Hz {2,4:0.00}   road {3,4:0.00}   impact {4,4:0.00}   weapon {5,4:0.00}   heave {6,4:0.00}   " -f `
                $s.SpeedMph, $live.EngineFreq, $live.EngineAmp, $live.RoadAmp,
                $live.ImpulseAmp, $live.WeaponAmp, $live.HeaveAmp) -NoNewline
        }
        Start-Sleep -Milliseconds $sleepMs
    }
}
finally {
    # Always stop the audio thread and close the device. Leaving waveOut open
    # holds the interface until the process dies, and this process may well be
    # killed rather than exited.
    Write-Host ""
    if ($live.core -and $live.core.Samples -gt 0) {
        Write-Host ("peak {0:0.00} before limiting, {1:0.00}% of samples limited" -f `
            $live.core.PeakAbs, (100.0 * $live.core.Limited / $live.core.Samples)) -ForegroundColor DarkGray
        Write-Host "  a few % limited is the knee working. Tens of % means -Drive is too high." -ForegroundColor DarkGray
    }
    $live.Stop()
    Tel-Close $ctx
    Write-Host "shaker released." -ForegroundColor Cyan
}
