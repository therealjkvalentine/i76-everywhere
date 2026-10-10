<#
  make-golden.ps1 - run the REFERENCE force model (tools/ffb/FfbMixer.ps1) over the synthetic drives and write
  every input and every output, frame by frame, so the C# Core (tools/haptics/src/Haptics/Core/ReferenceMixer.cs)
  can be compared against it value for value.

  Nothing here is a copy of the model: FfbMixer.ps1 is dot-sourced as it is in the repo, so a change to it shows
  up as a golden mismatch in tests/Haptics.Tests until the C# port follows (or the change is reverted).

      powershell -NoProfile -ExecutionPolicy Bypass -File tools\haptics\tests\golden\make-golden.ps1
      ... -OutDir <dir>                 default tools\haptics\tests\golden\out (gitignored)
      ... -RealDrives <dir>             also replay drive2.csv / drive3.csv from that folder (ffb-replay.ps1's
                                        Build-Samples); those are captured telemetry and stay out of git

  The drives: every scenario of tools/ffb/ffb-mixer-test.ps1 (same inputs), the nine ffb-lfe-probe.ps1
  scenarios (same inputs, so the LFE renderer can be checked against probe WAVs), and a few added to pin the
  560dcd2 blast-decay/duck fix, the stale-sim gate and the RPM-driven engine note.
#>
param(
    [string]$OutDir = "",
    [string]$RealDrives = ""
)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = Resolve-Path (Join-Path $here '..\..\..\..')
$ffb = Join-Path $repo 'tools\ffb'
. (Join-Path $ffb 'FfbMixer.ps1')
. (Join-Path $ffb 'Telemetry.ps1')     # Tel-Slip, for the real-drive replays only
if (-not $OutDir) { $OutDir = Join-Path $here 'out' }
if (-not (Test-Path $OutDir)) { $null = New-Item -ItemType Directory -Path $OutDir }
Get-ChildItem $OutDir -Filter '*.csv' | Remove-Item -Force

$inv = [System.Globalization.CultureInfo]::InvariantCulture
function F($x) {
    if ($null -eq $x) { return '' }
    if ($x -is [bool]) { if ($x) { return '1' } else { return '0' } }
    if ($x -is [double] -or $x -is [single]) { return ([double]$x).ToString('R', $inv) }
    return [string]::Format($inv, '{0}', $x)
}
function Prop($o, [string]$n) { if ($o.PSObject.Properties[$n]) { return $o.$n } return $null }

# Same shape as ffb-mixer-test.ps1's Fake (only the fields Mix-Update reads).
function Fake {
    param(
        [double]$T, [double]$Speed = 0, [double]$Steer = 0, [double]$Throttle = 0,
        [double]$YawRate = 0, [double]$LongG = 0, [double]$LatG = 0,
        [double]$Understeer = 0, [double]$Oversteer = 0, [double]$Jolt = 0,
        [double]$Vy = 0, [bool]$Firing = $false, $FxFired = $null, $FxEvent = $null
    )
    [pscustomobject]@{
        T = $T; Speed = $Speed; Steer = $Steer; Throttle = $Throttle
        YawRate = $YawRate; LongG = $LongG; LatG = $LatG
        LongAccel = ($LongG * 9.81); LatAccel = ($LatG * 9.81); HeaveAccel = 0.0; TravelPitch = 0.0
        Understeer = $Understeer; Oversteer = $Oversteer; Jolt = $Jolt; Vy = $Vy
        Firing = $Firing; FxFired = $FxFired; FxEvent = $FxEvent
    }
}
function Fx([double]$Mag) { return ,@([pscustomobject]@{ Slot = 0; Id = 8; Param = 0.81; Mag = $Mag }) }

# the time grid the mixer test uses: an ACCUMULATED float, exactly as `for ($t = 0.0; $t -lt $S; $t += $dt)`
function Times([double]$Seconds = 2.0, [double]$Hz = 60.0) {
    $dt = 1.0 / $Hz; $out = New-Object System.Collections.ArrayList
    for ($t = 0.0; $t -lt $Seconds; $t += $dt) { $null = $out.Add($t) }
    return ,$out
}
# the grid ffb-lfe-probe.ps1 uses: t = i / FrameHz
function ProbeTimes { $out = New-Object System.Collections.ArrayList; for ($i = 0; $i -lt 360; $i++) { $null = $out.Add($i / [double]60) }; return ,$out }

$COLS_IN  = @('T','Speed','Steer','Throttle','YawRate','LongG','LatG','LongAccel','LatAccel','HeaveAccel','TravelPitch',
              'Understeer','Oversteer','Jolt','Vy','Rpm','Firing','FxEvent','FxMags','Shift','SinceTick','Active','Enabled')
$CH = @('grip%','center','corner','oversteer','brake','texture','scrub','judder','impact','weapon','shift')
$COLS_OUT = @('Force','Steady','Osc','Ramp') + ($CH | ForEach-Object { "ch_$_" }) + @('Notes',
              'b_Steady','b_OscValue','b_TexAmp','b_ScrubAmp','b_JudderAmp','b_Transient','b_TransientImpact','b_TransientWeapon',
              'm_SurgeA','m_SwayA','m_HeaveA','m_YawRate','m_Pitch','m_Speed',
              'l_EngineFreq','l_EngineAmp','l_RoadAmp','l_RoadFreq','l_ImpulseAmp','l_HeaveAmp','l_WeaponAmp','l_ScrubAmp','l_ExplodeAmp',
              'pad_L','pad_R','wheel','peak','blastEnv')

$script:drives = 0
$script:frames = 0
function Run-Drive {
    # $SampleAt receives ($t, $i). $EnabledAt (optional) receives $t and returns the mixer's Enabled flag.
    param([string]$Name, [scriptblock]$SampleAt, $TimeList, $Active = $null, [scriptblock]$EnabledAt = $null)
    $tune = Mix-DefaultTune
    $mix = Mix-New
    $path = Join-Path $OutDir ($Name + '.csv')
    $w = New-Object System.IO.StreamWriter($path, $false, (New-Object System.Text.UTF8Encoding($false)))
    $w.WriteLine((($COLS_IN + $COLS_OUT) -join ','))
    $activeStr = ''
    if ($null -ne $Active) { $activeStr = (@($Active.Keys | Where-Object { $Active[$_] }) -join ';'); if (-not $activeStr) { $activeStr = '-' } }
    $i = 0
    foreach ($t in $TimeList) {
        $s = & $SampleAt $t $i
        $en = $true
        if ($EnabledAt) { $en = [bool](& $EnabledAt $t) }
        $mix.Enabled = $en
        $o = Mix-Update $mix $s $Active
        $pad = Mix-RenderPad $o.Bus
        $wheel = Mix-RenderWheel $o $tune
        $mags = ''
        $fxf = Prop $s 'FxFired'
        if ($null -ne $fxf) { $mags = (@($fxf | ForEach-Object { F ([double]$_.Mag) }) -join ';'); if (-not $mags) { $mags = '-' } }
        $vals = @(
            (F $s.T), (F $s.Speed), (F $s.Steer), (F $s.Throttle), (F $s.YawRate), (F $s.LongG), (F $s.LatG),
            (F (Prop $s 'LongAccel')), (F (Prop $s 'LatAccel')), (F (Prop $s 'HeaveAccel')), (F (Prop $s 'TravelPitch')),
            (F $s.Understeer), (F $s.Oversteer), (F $s.Jolt), (F $s.Vy), (F (Prop $s 'Rpm')), (F ([bool](Prop $s 'Firing'))),
            (F (Prop $s 'FxEvent')), $mags, (F (Prop $s 'Shift')), (F (Prop $s 'SinceTick')), $activeStr, (F $en),
            (F $o.Force), (F $o.Steady), (F $o.Osc), (F ([double]$o.Ramp))
        )
        foreach ($c in $CH) { $vals += (F ([double]$o.Channels[$c])) }
        $vals += ($o.Notes -join '|')
        $b = $o.Bus
        $vals += @((F ([double]$b.Steady)), (F ([double]$b.OscValue)), (F ([double]$b.Tactile[0].Amp)), (F ([double]$b.Tactile[1].Amp)),
                   (F ([double]$b.Tactile[2].Amp)), (F ([double]$b.Transient)), (F ([double]$b.TransientImpact)), (F ([double]$b.TransientWeapon)))
        $m = $b.Motion
        $vals += @((F ([double]$m.SurgeA)), (F ([double]$m.SwayA)), (F ([double]$m.HeaveA)), (F ([double]$m.YawRate)), (F ([double]$m.Pitch)), (F ([double]$m.Speed)))
        $L = $b.Lfe
        $vals += @((F ([double]$L.EngineFreq)), (F ([double]$L.EngineAmp)), (F ([double]$L.RoadAmp)), (F ([double]$L.RoadFreq)),
                   (F ([double]$L.ImpulseAmp)), (F ([double]$L.HeaveAmp)), (F ([double]$L.WeaponAmp)), (F ([double]$L.ScrubAmp)), (F ([double]$L.ExplodeAmp)))
        $vals += @((F ([double]$pad.Left)), (F ([double]$pad.Right)), (F $wheel), (F ([double]$mix.PeakForce)), (F ([double]$mix.BlastEnv)))
        $w.WriteLine(($vals -join ','))
        $i++
    }
    $w.Close()
    $script:drives++
    $script:frames += $i
}

# ---- ffb-mixer-test.ps1 scenarios (same inputs) -----------------------------
Run-Drive 'parked'           { param($t) Fake -T $t } (Times)
Run-Drive 'center_right'     { param($t) Fake -T $t -Speed 15 -Steer 0.6 } (Times)
Run-Drive 'center_left'      { param($t) Fake -T $t -Speed 15 -Steer -0.6 } (Times)
Run-Drive 'center_slow'      { param($t) Fake -T $t -Speed 2 -Steer 0.6 } (Times)
Run-Drive 'corner'           { param($t) Fake -T $t -Speed 18 -Steer 0.5 -YawRate 0.5 -LatG 0.5 } (Times)
Run-Drive 'gripped'          { param($t) Fake -T $t -Speed 18 -Steer 0.6 -YawRate 0.5 -LatG 0.5 -Understeer 0.0 } (Times)
Run-Drive 'sliding'          { param($t) Fake -T $t -Speed 18 -Steer 0.6 -YawRate 0.5 -LatG 0.5 -Understeer 0.9 } (Times)
Run-Drive 'oversteer'        { param($t) Fake -T $t -Speed 18 -Steer 0.2 -YawRate 0.8 -LatG 0.6 -Oversteer 0.8 } (Times)
Run-Drive 'gripped2'         { param($t) Fake -T $t -Speed 18 -Steer 0.5 -YawRate 0.5 -LatG 1.5 } (Times)
Run-Drive 'spun'             { param($t) Fake -T $t -Speed 18 -Steer 0.5 -YawRate 1.6 -LatG 2.6 -Oversteer 0.9 } (Times)
$onlyCenter = @{}
foreach ($c in @('center','corner','oversteer','brake','texture','scrub','judder','impact')) { $onlyCenter[$c] = $false }
$onlyCenter['center'] = $true
Run-Drive 'gated_center_only' { param($t) Fake -T $t -Speed 18 -Steer 0.6 -YawRate 0.5 -LatG 2.0 } (Times) -Active $onlyCenter
Run-Drive 'brake'            { param($t) Fake -T $t -Speed 16 -Steer 0.3 -Throttle -0.9 -LongG -0.8 } (Times)
Run-Drive 'judder'           { param($t) Fake -T $t -Speed 16 -Steer 0.2 -Throttle -1 -LongG -0.9 } (Times 1.5)
Run-Drive 'light_brake'      { param($t) Fake -T $t -Speed 16 -Steer 0.2 -Throttle -0.2 -LongG -0.1 } (Times)
Run-Drive 'texture_slow_smooth' { param($t) Fake -T $t -Speed 4 -Jolt 0.0 } (Times 1.5)
Run-Drive 'texture_fast_smooth' { param($t) Fake -T $t -Speed 18 -Jolt 0.0 } (Times 1.5)
Run-Drive 'texture_fast_rough'  { param($t) Fake -T $t -Speed 18 -Jolt (0.7 * 16.0) } (Times 1.5)
Run-Drive 'impact_once'      { param($t) Fake -T $t -Speed 14 -Jolt $(if ($t -ge 1.0 -and $t -lt 1.15) { 70 } else { 0 }) -YawRate 0.3 } (Times 2.5)
Run-Drive 'weapon_held'      { param($t) Fake -T $t -Speed 14 -Firing ($t -ge 1.0 -and $t -lt 2.0) } (Times 2.5)
Run-Drive 'weapon_never'     { param($t) Fake -T $t -Speed 14 -Firing $false } (Times 1.5)
Run-Drive 'everything_absurd' { param($t) Fake -T $t -Speed 40 -Steer 1.0 -Throttle -1.0 -YawRate 2.0 -LatG 3.0 -LongG -3.0 -Understeer 1.0 -Oversteer 1.0 -Jolt 200 -Vy 6 } (Times 3.0)
Run-Drive 'muted'            { param($t) Fake -T $t -Speed 30 -Steer 1 -YawRate 2 -LatG 3 -Jolt 200 } (Times 1.0) -EnabledAt { param($t) $t -lt 0.5 }
Run-Drive 'bus_consistency'  { param($t) Fake -T $t -Speed 18 -Steer 0.5 -YawRate 0.6 -LatG 1.5 -Jolt 6 } (Times)
Run-Drive 'lfe_engine_speed' { param($t) Fake -T $t -Speed $(if ($t -lt 1.0) { 8 } else { 35 }) -Throttle 0.8 } (Times)
Run-Drive 'lfe_impulse'      { param($t) Fake -T $t -Speed 15 -Jolt $(if ($t -ge 1.0 -and $t -lt 1.1) { 120 } else { 0 }) -YawRate 0.2 } (Times 1.6)
Run-Drive 'pad_impact'       { param($t) Fake -T $t -Speed 15 -Jolt $(if ($t -ge 1.0) { 150 } else { 0 }) -YawRate 0.2 } (Times 1.15)
Run-Drive 'pad_weapon'       { param($t) Fake -T $t -Speed 15 -Firing ($t -ge 1.0) } (Times 1.1)
Run-Drive 'fire_mag5'  { param($t) $fx = @(); if ($t -ge 0.5 -and $t -lt 0.55) { $fx = Fx 5 };  Fake -T $t -Speed 14 -FxFired $fx -FxEvent ($fx.Count -gt 0) } (Times 1.2)
Run-Drive 'fire_mag10' { param($t) $fx = @(); if ($t -ge 0.5 -and $t -lt 0.55) { $fx = Fx 10 }; Fake -T $t -Speed 14 -FxFired $fx -FxEvent ($fx.Count -gt 0) } (Times 1.2)
Run-Drive 'fire_mag60' { param($t) $fx = @(); if ($t -ge 0.5 -and $t -lt 0.55) { $fx = Fx 60 }; Fake -T $t -Speed 14 -FxFired $fx -FxEvent ($fx.Count -gt 0) } (Times 1.2)
$idleT = Times 24.0 10; $null = $idleT.Add(24.1)
Run-Drive 'idle_guard' { param($t) if ($t -lt 24.05) { Fake -T $t -Speed 0 -Steer 0.8 } else { Fake -T $t -Speed 12 -Steer 0.8 -YawRate 0.5 -LatG 1.5 } } $idleT
Run-Drive 'minforce_lift'    { param($t) Fake -T $t -Speed 14 -Steer 0.12 } (Times)
Run-Drive 'subgate_ripple'   { param($t) Fake -T $t -Speed 6 -Steer 0.004 } (Times)
Run-Drive 'shift_up'   { param($t) $d = 0; if ([math]::Abs($t - 0.8) -lt 0.009) { $d = 1 };  $s = Fake -T $t -Speed 20; $s | Add-Member -NotePropertyName Shift -NotePropertyValue $d -Force; $s } (Times 1.5)
Run-Drive 'shift_down' { param($t) $d = 0; if ([math]::Abs($t - 0.8) -lt 0.009) { $d = -1 }; $s = Fake -T $t -Speed 20; $s | Add-Member -NotePropertyName Shift -NotePropertyValue $d -Force; $s } (Times 1.5)
Run-Drive 'shift_zero' { param($t) $s = Fake -T $t -Speed 20; $s | Add-Member -NotePropertyName Shift -NotePropertyValue 0 -Force; $s } (Times 1.5)
Run-Drive 'no_shift_property' { param($t) Fake -T $t -Speed 20 } (Times 0.6)
$script:degen = New-Object System.Collections.ArrayList
foreach ($sp in @(0, 0.0001, 1e-9, 3, 200)) { foreach ($yw in @(0, 1e-9, -1e-9, 5)) { $null = $script:degen.Add(@($sp, $yw)) } }
$degT = New-Object System.Collections.ArrayList; for ($k = 1; $k -le 20; $k++) { $null = $degT.Add($k * 0.016) }
Run-Drive 'degenerate' { param($t, $i) Fake -T $t -Speed $script:degen[$i][0] -Steer 0.5 -YawRate $script:degen[$i][1] -LatG 2 -Understeer 0.5 -Oversteer 0.5 } $degT

# ---- added: the 560dcd2 blast fix, the stale-sim gate, the RPM-driven engine ----
# A blast (effect magnitude >= LfeExplodeMag) while cruising on throttle. Before 560dcd2 the beds were zeroed on
# every frame without a blast; now they duck during the blast and come back.
Run-Drive 'blast_duck' { param($t) $fx = @(); if ($t -ge 1.0 -and $t -lt 1.02) { $fx = Fx 60 }
    Fake -T $t -Speed 15 -Throttle 0.5 -Jolt 3 -FxFired $fx -FxEvent $false } (Times 3.0)
Run-Drive 'blast_and_fire' { param($t) $fx = @(); if ([math]::Abs($t - 1.0) -lt 0.009) { $fx = Fx 60 }
    Fake -T $t -Speed 15 -Throttle 0.5 -FxFired $fx -FxEvent ($fx.Count -gt 0) } (Times 2.5)
Run-Drive 'stale_sim' { param($t) $s = Fake -T $t -Speed 15 -Steer 0.4 -YawRate 0.4 -LatG 1.0
    $s | Add-Member -NotePropertyName SinceTick -NotePropertyValue $(if ($t -gt 1.0) { 0.8 } else { 0.01 }) -Force; $s } (Times)
Run-Drive 'rpm_engine' { param($t) $s = Fake -T $t -Speed 10 -Throttle 0.6
    $s | Add-Member -NotePropertyName Rpm -NotePropertyValue (1050 + 4950 * [math]::Min(1.0, $t / 1.5)) -Force; $s } (Times)

# ---- ffb-lfe-probe.ps1 scenarios (same inputs, t = i/60 for 6 s) --------------
function Probe-Sample($st, [double]$t, [int]$i) {
    $sp = [double]$st.Speed; $lg = [double]$st.LongG; $la = $lg * 9.81
    $jolt = [math]::Abs($la)
    if ($st.Bump -and ($i % 11) -eq 0) { $jolt += 8.0 + 6.0 * $script:probeRnd.NextDouble() }
    $vy = 0.0
    if ($st.Bump -and ($i % 11) -eq 0) { $vy = 0.35 * ($script:probeRnd.NextDouble() - 0.5) }
    if ($st.Crash) { $jolt += 180.0 }
    $over = [double]$(if ($null -ne $st.Slide) { $st.Slide } else { 0.0 })
    $fx = @()
    if ($st.Fire) { $fx = @([pscustomobject]@{ Slot=0; Id=8; Param=0.8; Mag=10.0 }) }
    [pscustomobject]@{
        T=$t; Speed=$sp; Steer=$(if ($over -gt 0) { 0.4 } else { 0.0 }); Throttle=[double]$st.Throttle
        YawRate=$(if ($over -gt 0) { 1.4 } else { 0.0 }); Vy=$vy
        LongG=$lg; LongAccel=$la; LatG=0.0; LatAccel=0.0; HeaveAccel=($vy * 20.0); TravelPitch=0.0
        Understeer=0.0; Oversteer=$over; Jolt=$jolt; Firing=[bool]$st.Fire; FxEvent=[bool]$st.Fire; FxFired=$fx
    }
}
$PROBE = @(
  @{ Name='idle';    F={ param($t) @{ Speed=0.0;  Throttle=0.0;  LongG=0.0 } } }
  @{ Name='cruise';  F={ param($t) @{ Speed=17.9; Throttle=0.35; LongG=0.0 } } }
  @{ Name='accel';   F={ param($t) @{ Speed=[math]::Min(30.0, 4.0*$t); Throttle=1.0; LongG=0.41 } } }
  @{ Name='brake';   F={ param($t) @{ Speed=[math]::Max(0.0, 30.0-7.0*$t); Throttle=0.0; LongG=-0.71 } } }
  @{ Name='bumps';   F={ param($t) @{ Speed=17.9; Throttle=0.35; LongG=0.0; Bump=$true } } }
  @{ Name='rev';     F={ param($t) @{ Speed=0.0; Throttle=(1.0 - ([math]::Floor($t*1.5) % 2)); LongG=0.0 } } }
  @{ Name='weapon';  F={ param($t) @{ Speed=17.9; Throttle=0.35; LongG=0.0; Fire=(([int]($t*2)) -ne ([int](($t-0.02)*2))) } } }
  @{ Name='collide'; F={ param($t) @{ Speed=(17.9 * [int]($t -lt 3.0)); Throttle=0.35; LongG=0.0; Crash=($t -ge 3.0 -and $t -lt 3.1) } } }
  @{ Name='slide';   F={ param($t) @{ Speed=17.9; Throttle=0.5; LongG=0.0; Slide=0.75 } } }
)
foreach ($p in $PROBE) {
    $script:probeRnd = New-Object System.Random 1976
    $script:probeF = $p.F
    Run-Drive ('probe_' + $p.Name) { param($t, $i) Probe-Sample (& $script:probeF $t) $t $i } (ProbeTimes)
}

# ---- optional: real captured drives (ffb-replay.ps1 Build-Samples, full capture) ----
if ($RealDrives) {
    foreach ($nm in @('drive2', 'drive3')) {
        $csv = Join-Path $RealDrives "$nm.csv"
        if (-not (Test-Path $csv)) { Write-Host "  (no $csv)" -ForegroundColor DarkGray; continue }
        $raw = @(Import-Csv $csv)
        $script:realRows = New-Object System.Collections.ArrayList
        $tl = New-Object System.Collections.ArrayList
        foreach ($r in $raw) {
            $sp = [double]$r.speed; $st = [double]$r.steer; $yw = [double]$r.yaw
            $slip = Tel-Slip -Speed $sp -Steer $st -YawRate $yw -Slide 0.0
            $null = $script:realRows.Add([pscustomobject]@{
                T = [double]$r.t; Speed = $sp; Steer = $st; Throttle = [double]$r.throttle; YawRate = $yw
                Vy = [double]$r.vy; LongG = [double]$r.longG; LatG = ($yw * $sp) / 9.81
                Understeer = $slip.Understeer; Oversteer = $slip.Oversteer; Jolt = [double]$r.jolt })
            $null = $tl.Add([double]$r.t)
        }
        Run-Drive ('real_' + $nm) { param($t, $i) $script:realRows[$i] } $tl
    }
}

Write-Host ("golden: {0} drives, {1} frames -> {2}" -f $script:drives, $script:frames, $OutDir) -ForegroundColor Green
