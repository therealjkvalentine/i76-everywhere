<#
  ffb-lfe-probe.ps1 - render scripted driving scenarios through the LIVE signal
  path and write them out for spectral analysis.

  WHY THIS EXISTS: three separate causes of buzz have now been chased, and every
  one of them was invisible to the measurements taken at the time, because those
  measurements were of the OFFLINE renderer:

    * it interpolates parameters between frames, so it never showed the 60 Hz
      staircase the live path was applying
    * it fed heave as a hardcoded zero, so heave's 20 Hz jag could not appear
    * it needs a capture file, so it could only ever show driving that had
      already happened, not a controlled condition

  This runs LfeCore.RenderLive - the same smoother, the same per-sample stepping,
  the same limiter as LfeLive, with only waveOut missing - over synthetic
  telemetry built to isolate one condition at a time. Deterministic, repeatable,
  and it needs neither the game nor the operator.

  Scenarios are chosen to match how the buzz has actually been described:
  "on braking and accelerating, not when still".

      powershell -NoProfile -ExecutionPolicy Bypass -File tools\ffb\ffb-lfe-probe.ps1
      powershell -NoProfile -ExecutionPolicy Bypass -File tools\ffb\ffb-lfe-probe.ps1 -Only accel -Play -Device 0
#>
param(
    [string]$OutDir = "",
    [string]$Only = "",
    [double]$Seconds = 6.0,
    [int]$Rate = 16000,
    [int]$FrameHz = 60,
    [switch]$Play,
    [int]$Device = -1,
    [switch]$Solo,         # one source at a time, to attribute buzz to a source
    # Must track the shipped default, or the probe measures a build nobody runs.
    [double]$Drive = 1.5,
    [double]$Master = 0.9
)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $here 'Telemetry.ps1')
. (Join-Path $here 'FfbMixer.ps1')
. (Join-Path $here 'LfeSynth.ps1')

if (-not $OutDir) { $OutDir = Join-Path $here 'probe' }
if (-not (Test-Path $OutDir)) { $null = New-Item -ItemType Directory -Path $OutDir }
$tune = Mix-DefaultTune
[LfeCore]::ScrubHzCfg = [double]$tune.LfeScrubHz   # must be set BEFORE the core is built


# ---- scenarios -----------------------------------------------------------
# Each returns the driving state at time t. Speed and throttle are what a driver
# does; longG/jolt follow from them the way the telemetry would compute them, so
# the mixer sees a physically coherent picture rather than hand-set channels.
$SCEN = @(
  @{ Name='idle';    Desc='stationary, engine idling'
     F={ param($t) @{ Speed=0.0;  Throttle=0.0;  LongG=0.0 } } }
  @{ Name='cruise';  Desc='steady 40 mph, no input change'
     F={ param($t) @{ Speed=17.9; Throttle=0.35; LongG=0.0 } } }
  @{ Name='accel';   Desc='hard acceleration from rest'
     F={ param($t) @{ Speed=[math]::Min(30.0, 4.0*$t); Throttle=1.0; LongG=0.41 } } }
  @{ Name='brake';   Desc='hard braking from 30 m/s'
     F={ param($t) @{ Speed=[math]::Max(0.0, 30.0-7.0*$t); Throttle=0.0; LongG=-0.71 } } }
  @{ Name='bumps';   Desc='steady speed over rough ground'
     F={ param($t) @{ Speed=17.9; Throttle=0.35; LongG=0.0; Bump=$true } } }
  # REVVING STATIONARY was never tested, and it is the worst case in the whole
  # tune: engine frequency is idle+span*(speed/ref), so at zero speed it sits at
  # 20 Hz, where the measured rig curve asks for the largest boost of any band
  # (2.27x) - and 20 Hz puts its 3rd harmonic at 60 Hz, well inside the pass band
  # where no filter will hide it.
  @{ Name='rev';     Desc='stationary, blipping the throttle'
     # No `if` inside these scriptblocks: the closing brace of an if-block
     # terminates the scriptblock itself, and F silently stops being callable.
     F={ param($t) @{ Speed=0.0; Throttle=(1.0 - ([math]::Floor($t*1.5) % 2)); LongG=0.0 } } }
  @{ Name='weapon';  Desc='firing while cruising'
     F={ param($t) @{ Speed=17.9; Throttle=0.35; LongG=0.0; Fire=(([int]($t*2)) -ne ([int](($t-0.02)*2))) } } }
  @{ Name='collide'; Desc='cruising into a wall'
     F={ param($t) @{ Speed=(17.9 * [int]($t -lt 3.0)); Throttle=0.35; LongG=0.0
                      Crash=($t -ge 3.0 -and $t -lt 3.1) } } }
  @{ Name='slide';   Desc='four-wheel drift'
     F={ param($t) @{ Speed=17.9; Throttle=0.5; LongG=0.0; Slide=0.75 } } }
)

function Render-Scenario {
    param($Sc)
    $n = [int]($Seconds * $FrameHz)
    $ef=New-Object double[] $n; $ea=New-Object double[] $n
    $rf=New-Object double[] $n; $ra=New-Object double[] $n
    $ia=New-Object double[] $n; $wa=New-Object double[] $n; $ha=New-Object double[] $n
    $scA=New-Object double[] $n   # NOT $sc - collides with the $Sc parameter
    $mix = Mix-New
    $prevSpeed = $null
    $rnd = New-Object System.Random 1976

    for ($i = 0; $i -lt $n; $i++) {
        $t = $i / [double]$FrameHz
        $st = & $Sc.F $t
        $sp = [double]$st.Speed
        $lg = [double]$st.LongG
        $la = $lg * 9.81

        # Jolt as Telemetry computes it: the magnitude of the acceleration
        # vector. Under pure straight-line driving that IS the longitudinal
        # term, which is exactly the coupling that made throttle sound rough.
        $jolt = [math]::Abs($la)
        # A bump adds acceleration the driver did not command - the only thing
        # that should reach the road bed now.
        if ($st.Bump -and ($i % 11) -eq 0) { $jolt += 8.0 + 6.0 * $rnd.NextDouble() }

        $vy = 0.0
        if ($st.Bump -and ($i % 11) -eq 0) { $vy = 0.35 * ($rnd.NextDouble() - 0.5) }

        if ($st.Crash) { $jolt += 180.0 }
        $over = [double]$(if ($null -ne $st.Slide) { $st.Slide } else { 0.0 })
        $fx = @()
        if ($st.Fire) { $fx = @([pscustomobject]@{ Slot=0; Id=8; Param=0.8; Mag=10.0 }) }

        $s = [pscustomobject]@{
            T=$t; Speed=$sp; SpeedMph=$sp*2.23694; Steer=$(if ($over -gt 0) { 0.4 } else { 0.0 })
            Throttle=[double]$st.Throttle
            YawRate=$(if ($over -gt 0) { 1.4 } else { 0.0 }); AngVelX=0.0; AngVelZ=0.0; Vy=$vy
            LongG=$lg; LongAccel=$la; LatG=0.0; LatAccel=0.0
            HeaveAccel=($vy * 20.0); TravelPitch=0.0
            ExpectedYaw=0.0; Understeer=0.0; Oversteer=$over
            Jolt=$jolt; Firing=[bool]$st.Fire; FxEvent=[bool]$st.Fire; FxFired=$fx
            Braking=($lg -lt -0.05); Airborne=$false
            Ticks=$i; Polls=$i; Wheelbase=4.662
        }
        $o = Mix-Update $mix $s
        $L = $o.Bus.Lfe
        $ef[$i]=[double]$L.EngineFreq; $ea[$i]=[double]$L.EngineAmp
        $rf[$i]=[double]$(if ($null -ne $L.RoadFreq) { $L.RoadFreq } else { 60.0 })
        $ra[$i]=[double]$L.RoadAmp
        $ia[$i]=[double]$L.ImpulseAmp; $wa[$i]=[double]$L.WeaponAmp
        $ha[$i]=[double]$(if ($null -ne $L.HeaveAmp) { $L.HeaveAmp } else { 0.0 })
        $scA[$i]=[double]$(if ($null -ne $L.ScrubAmp) { $L.ScrubAmp } else { 0.0 })
        $prevSpeed = $sp
    }

    # Solo mode: keep one source, silence the rest, so a spectrum names its own
    # culprit instead of showing the mixture.
    $sets = if ($Solo) {
        @(@{S='all';K=@()}, @{S='engine';K=@('r','i','w','h','s')}, @{S='road';K=@('e','i','w','h','s')},
          @{S='heave';K=@('e','r','i','w','s')}, @{S='weapon';K=@('e','r','i','h','s')},
          @{S='impact';K=@('e','r','w','h','s')}, @{S='scrub';K=@('e','r','i','w','h')})
    } else { @(@{S='all';K=@()}) }

    foreach ($set in $sets) {
        $e2=$ea.Clone(); $r2=$ra.Clone(); $i2=$ia.Clone(); $w2=$wa.Clone(); $h2=$ha.Clone(); $s2=$scA.Clone()
        foreach ($k in $set.K) {
            switch ($k) {
                'e' { for ($j=0;$j -lt $n;$j++){$e2[$j]=0.0} }
                'r' { for ($j=0;$j -lt $n;$j++){$r2[$j]=0.0} }
                'i' { for ($j=0;$j -lt $n;$j++){$i2[$j]=0.0} }
                'w' { for ($j=0;$j -lt $n;$j++){$w2[$j]=0.0} }
                'h' { for ($j=0;$j -lt $n;$j++){$h2[$j]=0.0} }
                's' { for ($j=0;$j -lt $n;$j++){$s2[$j]=0.0} }
            }
        }
        $pcm = [LfeCore]::RenderLive($ef,$e2,$rf,$r2,$i2,$w2,$h2,$s2,
            $Rate, $FrameHz, $Master, $Drive,
            [double]$tune.LfeEngineJitter, [double]$tune.LfeImpactHz, [double]$tune.LfeWeaponHz,
            [double]$tune.LfeCarrierHz, 11.0, 85.0,
            [double[]]$tune.LfeRespHz, [double[]]$tune.LfeRespRel, [double]$tune.LfeCompMax)

        $name = if ($set.S -eq 'all') { $Sc.Name } else { "$($Sc.Name)-$($set.S)" }
        $path = Join-Path $OutDir "$name.wav"
        $fs=[System.IO.File]::Create($path); $bw=New-Object System.IO.BinaryWriter($fs)
        $bytes=$pcm.Length*2
        $bw.Write([char[]]'RIFF'); $bw.Write([uint32](36+$bytes)); $bw.Write([char[]]'WAVE')
        $bw.Write([char[]]'fmt '); $bw.Write([uint32]16); $bw.Write([uint16]1); $bw.Write([uint16]1)
        $bw.Write([uint32]$Rate); $bw.Write([uint32]($Rate*2)); $bw.Write([uint16]2); $bw.Write([uint16]16)
        $bw.Write([char[]]'data'); $bw.Write([uint32]$bytes)
        foreach ($sm in $pcm) { $bw.Write([int16]$sm) }
        $bw.Flush(); $bw.Close(); $fs.Close()

        $m = [LfeCore]::LastRender
        Write-Host ("  {0,-18} peak {1,5:0.00}  limited {2,5:0.00}%  -> {3}" -f `
            $name, $m.PeakAbs, (100.0*$m.Limited/[math]::Max(1,$m.Samples)), (Split-Path -Leaf $path))

        if ($Play -and $set.S -eq 'all') {
            $bts = New-Object byte[] ($pcm.Length*2)
            [Buffer]::BlockCopy($pcm, 0, $bts, 0, $bts.Length)
            $null = [LfeOut]::Play($bts, $Rate, $Device)
        }
    }
}

Write-Host ""
Write-Host ("probing the LIVE signal path - {0}s per scenario at {1} Hz" -f $Seconds, $Rate) -ForegroundColor Cyan
Write-Host ""
foreach ($sc in $SCEN) {
    if ($Only -and $sc.Name -ne $Only) { continue }
    Write-Host ("{0} - {1}" -f $sc.Name, $sc.Desc) -ForegroundColor Yellow
    Render-Scenario $sc
}
Write-Host ""
Write-Host ("wrote to {0}" -f $OutDir) -ForegroundColor Green
Write-Host "-Solo splits each scenario per source, so a spectrum names its own culprit." -ForegroundColor DarkGray
