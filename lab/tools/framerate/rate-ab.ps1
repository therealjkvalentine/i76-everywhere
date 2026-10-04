<#
  rate-ab.ps1 - one unattended driver: a chosen MEASUREMENT under a chosen CONDITION SET, n runs each, every run a
  fresh boot through autotest\proxy-run.ps1 (i76-everywhere Strlkup.dll proxy, I76_MISSION boot), and a markdown
  results table with n, mean and spread per condition. A/A first: the first condition is run n times before any
  other, and the report states its spread as the noise floor every A/B delta is read against (memory rule:
  same-rate control run, report n).

  USAGE (physical console, sandbox game, nothing else running on it)
    tools\framerate\rate-ab.ps1 -Measure cactus                      # I76_COLL_WINDOW on the a01 cactus field
    tools\framerate\rate-ab.ps1 -Measure airborne -Runs 3            # t06 ramp jump, gain = observed / commanded rotation
    tools\framerate\rate-ab.ps1 -Measure mirror                      # sky px/s + cloud drift + mirror redraws/s, car still
    tools\framerate\rate-ab.ps1 -Measure dodge -Fire                 # g_idbg.dodge_calls per second in t01 with the AI
    tools\framerate\rate-ab.ps1 -Measure cactus2                     # I76_COLL_WINDOW, teleported straight approaches (a01)
    tools\framerate\rate-ab.ps1 -Measure airborne2                   # t06 ramp jump, gain from telemetry (flags 0x4, rot, body rates)
    tools\framerate\rate-ab.ps1 -Measure farengine                   # I76_FAR_ENGINE_DT: far AI car's time to cruise speed (t01)
    tools\framerate\rate-ab.ps1 -Measure colldedupe -Runs 2          # F3: contact repeats + damage per ram at buildings (t01)
    tools\framerate\rate-ab.ps1 -Measure hazard                      # F1: parked on a fire patch (a01; -Mission t01 = oil slick)
    tools\framerate\rate-ab.ps1 -Measure wmiss                       # F4: dead-weapon click requests / plays per second (t01)
    tools\framerate\rate-ab.ps1 -Measure airolls                     # F5: AI skid / horn rolls per second beside the mission's cars (t01)
    tools\framerate\rate-ab.ps1 -Measure cactus -DryRun              # print the proxy-run commands, touch nothing
    tools\framerate\rate-ab.ps1 -Measure cactus2 -DryRun             # ... plus the offline checks: ODEF plan + rate-ab-selftest.py
    tools\framerate\rate-ab.ps1 -Measure cactus -ReportOnly          # rebuild REPORT.md from results.csv
    tools\framerate\rate-ab.ps1 -Measure cactus -Switch I76_AI_FIXES -Conditions fixed60,fixed60+sw,fixed120,fixed120+sw

  CONDITIONS  (-Conditions, comma separated; '+sw' adds the switch under test, -Switch)
    stock20      -Set stock  I76_FPS_CAP=20                 the reference James plays (no fixes, 20 fps cap)
    stock60      -Set stock                                 no fixes, Glide's 60 Hz pacing
    fixed20      -Set fixed  I76_FPS_CAP=20                 the fixed set at a 20 fps cap (dodge: the stock-20 stand-in)
    fixed60      -Set fixed                                 hires clock, fixed step 24, framerate fixes, engine dt, interp
    fixed60+sw   -Set fixed  <switch>=1
    fixed120     -Set fixed  I76_GLIDE_REFRESH=120
    fixed120+sw  -Set fixed  I76_GLIDE_REFRESH=120 <switch>=1
  Default order: stock20, stock60, fixed60, fixed60+sw, fixed120 (dodge: fixed20, fixed60, fixed60+sw, fixed120, see
  below). The first listed condition is the A/A baseline. Every new switch needs the fixed set (the proxy refuses it
  otherwise and logs "not applied"), so stock+sw is rejected here.

  MEASUREMENTS  (what each reads, and what it reuses)
    cactus    mission a01. cactus-gauntlet.ps1 drives the 5-saguaro weave (its own control acquisition + steer
              calibration), writes <tag>.csv; analyze-cactus.py classifies (via rate-ab-analyse.py). Per run:
              hit_rate = hits / valid approaches. Switch default I76_COLL_WINDOW (P1-15 / coverage P1).
    airborne  mission t06. Waits for the scripted opening to hand over, places the car 150 m before ramp A
              (7930, 24, 42580, identity rotation, 28 m/s - the fr_probe.py --place port), then airborne-test.ps1
              samples attitude + angular velocity for -Seconds; analyse-airborne.py gives gain (observed deg /
              commanded deg in free fall), deg/s, deg/frame. Switch default I76_COLL_WINDOW (backlog P2-04).
    mirror    mission a01 (its start hold parks the car). After hand-over and the car at rest: sky-motion.ps1 (2-D
              shift search over the sky band, px/s per pair), plus from memory over the same window: cloud offsets
              0x507cd8 / 0x507c50 drift per second (capture 014's number, 0.0300/s stock 20) and the proxy's
              mirror_draws counter per second (only counts under I76_MIRROR_RATE). Switch default I76_MIRROR_RATE.
    dodge     mission t01 (Taurus + the mission's AI; a melee arena has no .msn so I76_MISSION cannot boot one).
              g_idbg.dodge_calls / dodge_yes / tick20_n over -Seconds, from the proxy debug block (address from the
              "render-interp: ... (debug block X)" log line). The counter lives in the I76_AI_FIXES wrapper and the
              block is filled by the render-interp wrapper, so EVERY dodge condition runs the fixed set with
              I76_AI_FIXES=1; conditions without '+sw' get I76_AI_DODGE_HOLD=0 (counted, passed through = stock
              behaviour), '+sw' holds the check to the 20 Hz grid. stock20/stock60 are rejected for this measurement.
              -Fire holds the fire key so dodge_yes (projectiles seen) means something.

    cactus2   mission a01 (the 89-saguaro training field; -Mission t01 has 9). The port of `cactus` to the direct boot:
              no steering, no steer calibration. rate-ab-live.py reads the saguaro positions from the mission's ODEF,
              and per approach (-Approaches 6) takes the car's own heading, picks an unused saguaro with a clear
              corridor, TELEPORTs (Local\I76Trainer one-shot, game thread) -ApproachDist 30 m before it, lets the car
              settle, TELEPORTs in place with velocity -CactusSpeed 15 m/s along the line and holds the throttle
              (input block + W). Every telemetry frame (Local\I76Telemetry) and event goes to <tag>.frames.csv /
              <tag>.events.csv; rate-ab-analyse.py cactus2 classifies: HIT = scenery-class I76TEL_EV_IMPACT on the
              player near the trunk OR v_min < 0.6 v_before; valid = on the trunk line (<= 1 m) at >= 70% of the set
              speed. hits_impact / hits_speed show the two signals separately. Adds I76_TELEMETRY=1 to every condition.
              -RelaunchAt m re-asserts the set speed m metres before the trunk (off; for a run whose approaches read SLOW).
    airborne2 mission t06, same ramp A placement as `airborne` (rotation written, position + velocity by the trainer
              TELEPORT, read back). The detector is telemetry: frames with step_count 0 (no physics step: the
              interpolated repeats) are dropped, a segment is consecutive step frames with flags bit 0x4, and
              gain = sum of rot[9] angle changes / sum of |body rate| x physics dt. Adds I76_TELEMETRY=1.
              Not the same number as `airborne` (pitch + roll end-to-end over mean |rate|): compare within a measure.
    farengine mission t01. The player is held -FarLift 800 m above its start (trainer FREEZE_POS), so every AI car is
              beyond the camera far radius + 25 m and takes physics_StepVehicleFar; the 0x54E11C table is sampled at
              ~50 Hz for -Seconds (30). Reports the furthest-travelling car's (-FarSlot n to choose) time to 90% of
              its cruise speed (90th percentile), the cruise speed, its minimum distance to the player (-FarMinDist
              625: closer is flagged, not averaged) and g_idbg.far_steps / s (the counter lives in the
              I76_FAR_ENGINE_DT wrapper: 0 without '+sw', and a '+sw' run where it stands still is flagged).
              Switch default I76_FAR_ENGINE_DT; default conditions add fixed120+sw.

  PER-FRAME-AUDIT-2026-10-03 acceptance measures (i76-everywhere docs; counters at the end of g_idbg, offsets computed
  from the struct in strlkproxy.c by rate-ab-selftest.py). All need the fixed set (the counters live in its wrappers and
  the block is copied by the render-interp wrapper); only `hazard` also accepts stock conditions (telemetry numbers only).
  Conditions without '+sw' set the fix's kill switch to 0 (counted, passed through = the behaviour before the fix);
  '+sw' leaves the fix on (the proxy default). hazard and wmiss have no kill switch: fixed20 / fixed60 / fixed120.
    colldedupe mission t01. Kill switch I76_COLL_DEDUPE. rate-ab-live.py `ram`: the cactus2 planner pointed at the
              mission's BUILDINGS (-RamPrefix b; a saguaro is a class 4 breakable that is knocked off and unregistered
              by its first contact, so it cannot show a repeat). Per ram (-Approaches 6): REPAIR, TELEPORT -ApproachDist
              60 m before the building along the car's heading, launch at -CactusSpeed 15 m/s, throttle off at the
              first contact, 1.5 s more. Per frame: g_idbg.coll_events / coll_dups, armour + chassis sum; IMPACT events.
              Reports dup_ratio (coll_dups / coll_events; audit: 0 at capped 20, ~0.6 at 60, ~0.8 at 120, with or without
              the dedupe - the counters do not depend on the switch), contact frames, player IMPACT events and damage
              per ram (sum of the events' f3), armour + chassis lost per ram. REPORT.md states 'MECHANISM NOT CONFIRMED'
              when the ratio is 0 at 120 fps with the switch off while contacts were seen.
              -RamPrefix vxktrac rams the parked tractor of t01 (the vehicle handler's damage site); -RamPrefix nsaguar
              -RamOnce -ApproachDist 30 the saguaros.
    hazard    mission a01 (its vgoon1 cars load Fire-Dropper; -Mission t01 loads Oil Slick with t01al01; -Hazard
              auto|fire|oil). The player's Landmines row is pointed at that definition in memory (instance +0x30 /
              +0x10 / +0x20, read back, restored; per-hit damage 5 instead of 15 so the car survives), fired for 0.06 s at rest, and after the 2 s shooter immunity the car
              is moved back in 0.5 m steps until the patch touches it, held there (FREEZE_POS, REPAIR every frame) for
              -Seconds 10 (cut to the patch's 20 s life). Reports ordnance IMPACT events per second per round dropped
              (audit: 20 with the fix at any fps), g_idbg.hazard_steps per second per projectile (20),
              hazard_impacts per second, hp per second per round, the oil flag share, EXPLOSION events per second.
    wmiss     mission t01. One of the player's weapons (a row with a hardpoint key) gets condition 0 in memory
              (instance +0xc, read back, restored), its key is held -Seconds 5. wmiss_req per second (= fps) and
              wmiss_play per second (audit: 20 at 60 and 120).
    airolls   mission t01. Kill switch I76_AI_ROLL_HOLD. The player is moved beside the mission's own cars (ODEF
              names t01*, not the one at the start; -NoNear leaves it at the start) with the trainer god flag, and
              skid_rolls / horn_rolls / tick20_n are sampled for -Seconds 30. Whether the AI enters dirt_brave against
              the player there is not known: a run with no rolls is reported as such, not averaged.
  NOT AUTOMATED - radar missile turn (F2), manual protocol: boot a mission that loads DrRadar (t13 / t16: gsradar on AI
  cars; `hazard`'s definition swap works for it too, by hand: instance +0x30 = the 'DrRadar' definition index, +0x10 =
  its damage), park 90 degrees off a parked target at ~300 m, select it as radar target (T), fire one missile, and log
  the missile object's forward row per frame (ordnance table 0x655280 -> projectile object +0x30); peak turn rate beyond
  150 m should read ~392 deg/s at capped 20 and at 60 / 120 with the fix (stock 120: ~2350). g_idbg.radar_turns must
  advance only while a missile is off its 0.998 dead band. Horn rolls (F5) need an AI car blocked behind another:
  watch horn_rolls in the airolls capture; it stays 0 unless that happens.

  OUTPUT  captures\rate-ab\<measure>[-Label]\  results.csv (one row per run), REPORT.md (the table), <cond>\<tag>.*
  (every raw capture, retained), <tag>.result.json (what the in-mission step measured, written before the game dies).
  Each run also records the proxy log lines of its switches (verify the write landed): a '+sw' run whose switch line
  is missing or says "not applied" is flagged, not averaged.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidateSet('cactus', 'airborne', 'mirror', 'dodge', 'cactus2', 'airborne2', 'farengine', 'colldedupe', 'hazard', 'wmiss', 'airolls')] [string]$Measure,
    [string]$Switch,
    [string[]]$Conditions,
    [int]$Runs = 2,
    [int]$Seconds = 20,
    [int]$Pairs = 5,
    [string]$Mission,
    [switch]$Fire,
    [double]$PlaceX = 7930.0, [double]$PlaceY = 24.0, [double]$PlaceZ = 42580.0, [double]$PlaceSpeed = 28.0,
    [switch]$NoPlace,
    [int]$Approaches = 6, [double]$CactusSpeed = 15.0, [double]$ApproachDist = 30.0, [double]$RelaunchAt = 0.0,
    [double]$FarLift = 800.0, [double]$FarMinDist = 625.0, [int]$FarSlot = -1,
    [string]$RamPrefix = 'b', [switch]$RamOnce,
    [ValidateSet('auto', 'fire', 'oil')] [string]$Hazard = 'auto',
    [switch]$NoNear,
    [string]$ToolsDir = 'C:\Users\james\i76-everywhere\tools',
    [string]$OutDir,
    [string]$Label,
    [int]$BootTimeout = 90,
    [switch]$DryRun,
    [switch]$ReportOnly
)
$ErrorActionPreference = 'Stop'
# paths resolved in the body: $PSScriptRoot is not reliable in a param() default under -File (autotest/README.md)
$RA_Fr       = $PSScriptRoot
$RA_Lab      = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$RA_Autotest = Join-Path $RA_Lab 'autotest'
$RA_ProxyRun = Join-Path $RA_Autotest 'proxy-run.ps1'
$RA_GameLog  = Join-Path $RA_Lab 'game\mciproxy.log'
$RA_Analyse  = Join-Path $RA_Fr 'rate-ab-analyse.py'
$RA_Live     = Join-Path $RA_Fr 'rate-ab-live.py'
$RA_SelfTest = Join-Path $RA_Fr 'rate-ab-selftest.py'
if ($Measure -eq 'farengine' -and -not $PSBoundParameters.ContainsKey('Seconds')) { $Seconds = 30 }
if (-not $PSBoundParameters.ContainsKey('Seconds')) { $d = @{ hazard = 10; wmiss = 5; airolls = 30 }[$Measure]; if ($d) { $Seconds = $d } }
if ($Measure -eq 'colldedupe' -and -not $PSBoundParameters.ContainsKey('ApproachDist')) { $ApproachDist = 60.0 }
if (-not $OutDir) { $OutDir = Join-Path $RA_Lab "captures\rate-ab\$Measure"; if ($Label) { $OutDir += "-$Label" } }
$RA_Results  = Join-Path $OutDir 'results.csv'
$RA_Report   = Join-Path $OutDir 'REPORT.md'

. (Join-Path $RA_Autotest 'lib\focuslib.ps1')
. (Join-Path $RA_Autotest 'lib\inputlib.ps1')
. (Join-Path $RA_Autotest 'lib\memlib.ps1')

# ---- measurement table ------------------------------------------------------------------------------------------
$RA_MEAS = @{
    cactus   = @{ Mission = 'a01'; Switch = 'I76_COLL_WINDOW'; Primary = 'hit_rate'
                  Cols = @('hit_rate', 'hits', 'valid', 'approaches')
                  Reads = 'cactus-gauntlet.ps1 -> <tag>.csv (min_dist, v_before, v_min per approach); analyze-cactus.py verdicts' }
    airborne = @{ Mission = 't06'; Switch = 'I76_COLL_WINDOW'; Primary = 'gain'
                  Cols = @('gain', 'deg_s', 'deg_frame', 'segments', 'placed_dz')
                  Reads = 'place car at ramp A approach; airborne-test.ps1 -> <tag>.csv (eye angles, ang vel); analyse-airborne.summarise' }
    mirror   = @{ Mission = 'a01'; Switch = 'I76_MIRROR_RATE'; Primary = 'sky_px_s'
                  Cols = @('sky_px_s', 'cloud_u_s', 'cloud_v_s', 'mirror_draws_s', 'speed')
                  Reads = 'sky-motion.ps1 -> <tag>.csv (px/s per pair); cloud doubles 0x507cd8/0x507c50; g_idbg.mirror_draws' }
    dodge    = @{ Mission = 't01'; Switch = 'I76_AI_FIXES'; Primary = 'dodge_calls_s'
                  Cols = @('dodge_calls_s', 'dodge_yes_s', 'calls_per_tick', 'ticks_s', 'ai_cars')
                  Reads = 'g_idbg.dodge_calls / dodge_yes / tick20_n deltas over the window (debug block from the proxy log)' }
    cactus2  = @{ Mission = 'a01'; Switch = 'I76_COLL_WINDOW'; Primary = 'hit_rate'; Telemetry = $true; Live = 'cactus'
                  Cols = @('hit_rate', 'hits', 'valid', 'approaches', 'hits_impact', 'hits_speed', 'v_before', 'steps_frame')
                  Reads = 'ODEF saguaros; trainer TELEPORT onto a straight line + velocity; telemetry frames + IMPACT events -> <tag>.frames.csv / .events.csv; rate-ab-analyse.py cactus2' }
    airborne2 = @{ Mission = 't06'; Switch = 'I76_COLL_WINDOW'; Primary = 'gain'; Telemetry = $true; Live = 'airborne'
                  Cols = @('gain', 'deg_s', 'deg_step', 'segments', 'air_s', 'placed_dz')
                  Reads = 'ramp A placement by trainer TELEPORT; telemetry per physics step (flags 0x4, rot[9], body rates, step_count) -> <tag>.csv; rate-ab-analyse.py airborne2' }
    farengine = @{ Mission = 't01'; Switch = 'I76_FAR_ENGINE_DT'; Primary = 't_cruise_s'; Live = 'farengine'
                  Cols = @('t_cruise_s', 'cruise_ms', 'far_steps_s', 'min_dist_m', 'cars')
                  Reads = 'player held FarLift m up (trainer FREEZE_POS); 0x54E11C table sampled -> <tag>.csv; rate-ab-analyse.py farengine; g_idbg.far_steps' }
    # PER-FRAME-AUDIT-2026-10-03. Kill = the switch is a kill switch (default on): conditions without '+sw' set it to 0.
    # NeedsDbg = the numbers are g_idbg counters (fixed set only). LogCheck = proxy log lines a run must show.
    colldedupe = @{ Mission = 't01'; Switch = 'I76_COLL_DEDUPE'; Kill = $true; NeedsDbg = $true; Primary = 'dmg_ram'; Telemetry = $true; Live = 'ram'
                  Cols = @('dmg_ram', 'dup_ratio', 'events_ram', 'dups_ram', 'burst_ram', 'impacts_ram', 'hp_ram', 'v_contact', 'valid', 'rams')
                  Conditions = @('fixed20', 'fixed20+sw', 'fixed60', 'fixed60+sw', 'fixed120', 'fixed120+sw')
                  LogCheck = { param($c) if ($c.WithSwitch) { 'coll-dedupe: 6/6 sites repointed .*applied once per step' } else { 'coll-dedupe: 6/6 sites repointed .*counted, passed through' } }
                  Reads = 'rams at ODEF buildings (trainer TELEPORT + velocity); per frame g_idbg.coll_events / coll_dups + armour/chassis sum; IMPACT events -> <tag>.frames.csv / .events.csv; rate-ab-analyse.py colldedupe' }
    hazard   = @{ Mission = 'a01'; Switch = ''; Primary = 'impacts_round_s'; Telemetry = $true; Live = 'hazard'
                  Cols = @('impacts_round_s', 'steps_proj_s', 'hz_impacts_s', 'hp_round_s', 'impacts_s', 'rounds', 'shots', 'oil_frac', 'explosions_s', 'window_s', 'offset_m')
                  Conditions = @('fixed20', 'fixed60', 'fixed120')
                  LogCheck = { param($c) if ($c.Set -ne 'stock') { 'hazard-contact: 6/6 sites repointed' } }
                  Reads = 'dropper row pointed at the Fire-Dropper / Oil Slick definition, dropped at rest, car held on the patch; IMPACT (class 0x33) / EXPLOSION events + g_idbg.hazard_steps / hazard_impacts -> <tag>.frames.csv / .events.csv; rate-ab-analyse.py hazard' }
    wmiss    = @{ Mission = 't01'; Switch = ''; NeedsDbg = $true; Primary = 'wmiss_play_s'; Live = 'wmiss'
                  Cols = @('wmiss_play_s', 'wmiss_req_s', 'req_per_frame', 'play_per_tick', 'ticks_s')
                  Conditions = @('fixed20', 'fixed60', 'fixed120')
                  LogCheck = { param($c) 'perframe-fixes: 5/5 sites repointed' }
                  Reads = 'a weapon row at condition 0 (instance +0xc), its hardpoint key held; g_idbg.wmiss_req / wmiss_play / tick20_n -> <tag>.csv; rate-ab-analyse.py wmiss' }
    airolls  = @{ Mission = 't01'; Switch = 'I76_AI_ROLL_HOLD'; Kill = $true; NeedsDbg = $true; Primary = 'skid_rolls_s'; Live = 'counters'
                  Cols = @('skid_rolls_s', 'horn_rolls_s', 'skid_per_tick', 'horn_per_tick', 'ticks_s', 'near_m')
                  Conditions = @('fixed20', 'fixed20+sw', 'fixed60', 'fixed60+sw', 'fixed120', 'fixed120+sw')
                  LogCheck = { param($c) if ($c.WithSwitch) { 'perframe-fixes: 5/5 sites repointed .*held to the 20 Hz grid' } else { 'perframe-fixes: 5/5 sites repointed .*counted, every frame' } }
                  Reads = 'player beside the mission cars (trainer TELEPORT, god flag); g_idbg.skid_rolls / horn_rolls / tick20_n -> <tag>.csv; rate-ab-analyse.py airolls' }
}
$RA_M = $RA_MEAS[$Measure]
if (-not $Switch) { $Switch = $RA_M.Switch }
if ($RA_M.Kill) { $Switch = $RA_M.Switch }                                                              # a kill switch is the measure's own
if (-not $Mission) { $Mission = $RA_M.Mission }
if (-not $Conditions) {
    $Conditions = if ($RA_M.Conditions) { $RA_M.Conditions }
                  elseif ($Measure -eq 'dodge') { @('fixed20', 'fixed60', 'fixed60+sw', 'fixed120') }
                  elseif ($Measure -eq 'farengine') { @('stock20', 'stock60', 'fixed60', 'fixed60+sw', 'fixed120', 'fixed120+sw') }
                  else { @('stock20', 'stock60', 'fixed60', 'fixed60+sw', 'fixed120') }
}
$Conditions = @($Conditions | ForEach-Object { $_ -split ',' } | ForEach-Object { $_.Trim() } | Where-Object { $_ })

# proxy switches this driver may set; cleared before every run because proxy-run.ps1 only clears its own list
$RA_NEW_SWITCHES = @('I76_COLL_WINDOW', 'I76_AI_FIXES', 'I76_AI_DODGE_HOLD', 'I76_FAR_ENGINE_DT', 'I76_MIRROR_RATE', 'I76_GLIDE_REFRESH', 'I76_FPS_CAP',
                      'I76_COLL_DEDUPE', 'I76_AI_ROLL_HOLD')
# proxy log tag per switch, to verify each took effect (strlkproxy.c mlog strings)
$RA_LOGTAG = @{ I76_COLL_WINDOW = 'coll-window'; I76_AI_FIXES = 'ai-fixes'; I76_FAR_ENGINE_DT = 'far-engine-dt'; I76_MIRROR_RATE = 'mirror-rate'
                I76_GLIDE_REFRESH = 'glide-refresh'; I76_FPS_CAP = 'fps-cap'; I76_TELEMETRY = 'telemetry: on' }
# debug block layout (strlkproxy.c g_idbg): 120-byte header, 16 x 112-byte ring, then the counters
# (rate-ab-selftest.py recomputes every offset here from the g_idbg declaration in the source and fails on a mismatch)
$RA_DBG = @{ Size = 1996; ping_req = 1912; ping_play = 1916; ping_frames = 1920; flame_hits = 1924; flame_dmg = 1928
             aifire_calls = 1932; aifire_yes = 1936; tick20_n = 1940; dodge_calls = 1944; dodge_yes = 1948; mirror_draws = 1952; far_steps = 1956
             hazard_impacts = 1960; hazard_steps = 1964; radar_turns = 1968; wmiss_req = 1972; wmiss_play = 1976; skid_rolls = 1980; horn_rolls = 1984
             coll_events = 1988; coll_dups = 1992 }

function RA-Condition([string]$name) {
    if ($name -notmatch '^(stock|fixed)(20|60|120)(\+sw)?$') { throw "condition '$name': expected stock|fixed + 20|60|120 [+sw]" }
    $set = $Matches[1]; $fps = [int]$Matches[2]; $sw = [bool]$Matches[3]
    $envs = [ordered]@{}
    if ($fps -eq 20) { $envs['I76_FPS_CAP'] = '20' }
    if ($fps -eq 120) { $envs['I76_GLIDE_REFRESH'] = '120' }
    if ($RA_M.NeedsDbg -and $set -eq 'stock') { throw "condition '$name': $Measure reads g_idbg counters that only exist under the fixed set (I76_RENDER_INTERP copies the block) - use fixed$fps" }
    if ($RA_M.Kill) {
        if ($set -eq 'stock') { throw "condition '$name': $Switch only exists under the fixed set - use fixed$fps" }
        if (-not $sw) { $envs[$Switch] = '0' }                                                           # '+sw' = the fix on = the proxy default
    } elseif ($sw) {
        if (-not $Switch) { throw "condition '$name': $Measure has no switch to add - use fixed$fps" }
        if ($set -eq 'stock') { throw "condition '$name': $Switch needs the fixed set (the proxy logs 'not applied' without it) - use fixed$fps+sw" }
        $envs[$Switch] = '1'
    }
    if ($Measure -eq 'dodge') {
        if ($set -eq 'stock') { throw "condition '$name': the dodge counter lives in the I76_AI_FIXES wrapper and the debug block needs I76_RENDER_INTERP, neither exists under the stock set - use fixed$fps (I76_AI_DODGE_HOLD=0 = stock behaviour, counted)" }
        $envs['I76_AI_FIXES'] = '1'
        if (-not $sw) { $envs['I76_AI_DODGE_HOLD'] = '0' }
    }
    if ($RA_M.Telemetry) { $envs['I76_TELEMETRY'] = '1' }                                                # the measurement's data source, every condition
    [pscustomobject]@{ Name = $name; Set = $set; Fps = $fps; WithSwitch = $sw; Env = $envs
                       EnvText = (($envs.Keys | ForEach-Object { "$_=$($envs[$_])" }) -join ' ') }
}

# ---- small readers ----------------------------------------------------------------------------------------------
function RA-F64($ctx, [int64]$addr) {
    $b = New-Object byte[] 8; $n = 0
    if ([I76Mem]::ReadProcessMemory($ctx.H, [IntPtr]$addr, $b, 8, [ref]$n) -and $n -eq 8) { [BitConverter]::ToDouble($b, 0) } else { [double]::NaN }
}
function RA-WriteBytes($ctx, [int64]$addr, [byte[]]$bytes) {
    $n = 0
    [void][I76Mem]::WriteProcessMemory($ctx.H, [IntPtr]$addr, $bytes, $bytes.Length, [ref]$n)
    return ($n -eq $bytes.Length)
}
function RA-DebugBlockAddr([int]$fromLine = 0) {
    if (-not (Test-Path $RA_GameLog)) { return 0 }
    $lines = Get-Content $RA_GameLog
    if ($fromLine -lt $lines.Count) { $lines = $lines[$fromLine..($lines.Count - 1)] } else { $lines = @() }
    $m = $lines | Select-String -Pattern 'render-interp: .*debug block (?:0x)?([0-9A-Fa-f]+)' | Select-Object -Last 1
    if ($m) { [Convert]::ToInt64($m.Matches[0].Groups[1].Value, 16) } else { 0 }
}
function RA-Counters($ctx, [int64]$addr) {
    if (-not $addr) { return $null }
    $b = New-Object byte[] $RA_DBG.Size; $n = 0
    if (-not ([I76Mem]::ReadProcessMemory($ctx.H, [IntPtr]$addr, $b, $b.Length, [ref]$n)) -or $n -ne $b.Length) { return $null }
    $o = [ordered]@{ frame = [BitConverter]::ToUInt32($b, 0) }
    foreach ($k in 'tick20_n', 'dodge_calls', 'dodge_yes', 'mirror_draws', 'far_steps', 'aifire_calls', 'aifire_yes') { $o[$k] = [BitConverter]::ToUInt32($b, $RA_DBG[$k]) }
    [pscustomobject]$o
}
function RA-Fps($ctx, [int]$f0, [datetime]$t0) {
    $dt = ((Get-Date) - $t0).TotalSeconds
    if ($dt -le 0) { return 0 }
    [math]::Round(((Mem-I32 $ctx 0x5A7E1C) - $f0) / $dt, 2)
}
# the direct mission boot runs a scripted opening (camera mode 0x4c2720 = 0x48e190 while the script drives); wait
# for the hand-over as fr_probe.py --place does, up to $max s. Returns seconds waited.
function RA-WaitHandover($ctx, [int]$max = 60) {
    $sw = [Diagnostics.Stopwatch]::StartNew(); $seen = $false
    while ($sw.Elapsed.TotalSeconds -lt $max) {
        $m = Mem-I32 $ctx 0x4C2720
        if ($m -eq 0x48E190) { $seen = $true } elseif ($seen -or $sw.Elapsed.TotalSeconds -gt 3) { break }
        Start-Sleep -Milliseconds 250
    }
    Start-Sleep -Seconds 1
    [math]::Round($sw.Elapsed.TotalSeconds, 1)
}
function RA-Python([string[]]$argv) {
    $out = @(& python @argv)                                   # stderr stays on the console: 2>&1 on a native exe throws under -EA Stop in 5.1
    $json = ($out | Where-Object { "$_" -match '^\{' } | Select-Object -Last 1)
    if (-not $json) { throw "rate-ab-analyse.py gave no JSON: $($out -join ' / ')" }
    "$json" | ConvertFrom-Json
}

# rate-ab-live.py: progress lines to the console as they come, the last JSON line back as an object
function RA-LiveRun([string[]]$argv) {
    $json = $null
    & python -u $RA_Live @argv | ForEach-Object { if ("$_" -match '^\{') { $json = "$_" } else { Write-Host "  $_" } }
    if (-not $json) { throw "rate-ab-live.py gave no JSON (python error above?)" }
    $json | ConvertFrom-Json
}

# ---- the in-mission measurements (called from proxy-run's -Run, i.e. with the game up and the player entity live) ----
function RA-Cactus($ctx, [string]$Tag, [string]$Dir) {
    $f0 = Mem-I32 $ctx 0x5A7E1C; $t0 = Get-Date
    & (Join-Path $RA_Fr 'cactus-gauntlet.ps1') -Tag $Tag -OutDir $Dir
    $fps = RA-Fps $ctx $f0 $t0
    $csv = Join-Path $Dir "$Tag.csv"
    if (-not (Test-Path $csv)) { return [ordered]@{ status = 'no-csv (gauntlet aborted: control or steer calibration)'; fps = $fps } }
    $a = RA-Python @($RA_Analyse, 'cactus', $Dir)
    $r = $a.runs.$Tag
    if (-not $r) { return [ordered]@{ status = 'no-approaches'; fps = $fps } }
    [ordered]@{ status = 'ok'; fps = $fps; hit_rate = $r.hit_rate; hits = $r.hits; valid = $r.valid; approaches = $r.approaches }
}

function RA-Airborne($ctx, [string]$Tag, [string]$Dir) {
    $hand = RA-WaitHandover $ctx
    $dz = $null
    if (-not $NoPlace) {
        # fr_probe.py --place, ported: pose + velocity written 6x (a write inside the render window is undone by the interp restore)
        $w = Mem-Open -Write
        try {
            $pobj = Mem-I32 $ctx (Mem-I32 $ctx 0x54A264)
            $e = Mem-PlayerEntity $ctx
            $rot = New-Object byte[] 36; $pos = New-Object byte[] 24; $vel = New-Object byte[] 24
            foreach ($i in 0, 4, 8) { [BitConverter]::GetBytes([single]1.0).CopyTo($rot, $i * 4) }        # identity: right +x, up +y, forward +z (ramp A)
            [BitConverter]::GetBytes([double]$PlaceX).CopyTo($pos, 0); [BitConverter]::GetBytes([double]$PlaceY).CopyTo($pos, 8); [BitConverter]::GetBytes([double]$PlaceZ).CopyTo($pos, 16)
            [BitConverter]::GetBytes([single]$PlaceSpeed).CopyTo($vel, 8)                                 # velocity (0, 0, +z)
            for ($k = 0; $k -lt 6; $k++) {
                [void](RA-WriteBytes $w ($pobj + 0x18) $rot); [void](RA-WriteBytes $w ($pobj + 0x40) $pos); [void](RA-WriteBytes $w ($e + 0xBC) $vel)
                Start-Sleep -Milliseconds 12
            }
            $dz = [math]::Round((RA-F64 $ctx ($pobj + 0x50)) - $PlaceZ, 2)                                  # read back: did the write land?
            Write-Host ("  placed at ({0},{1},{2}) after {3} s hand-over; read-back dz={4} m" -f $PlaceX, $PlaceY, $PlaceZ, $hand, $dz)
        } finally { Mem-Close $w }
    }
    $f0 = Mem-I32 $ctx 0x5A7E1C; $t0 = Get-Date
    & (Join-Path $RA_Fr 'airborne-test.ps1') -Label $Tag -Seconds $Seconds -OutDir $Dir
    $fps = RA-Fps $ctx $f0 $t0
    $csv = Join-Path $Dir "$Tag.csv"
    if (-not (Test-Path $csv)) { return [ordered]@{ status = 'no-csv'; fps = $fps; placed_dz = $dz } }
    $a = RA-Python @($RA_Analyse, 'airborne', $csv)
    $st = if ($a.segments -gt 0) { 'ok' } else { 'no-airborne-segments' }
    [ordered]@{ status = $st; fps = $fps; gain = $a.gain; deg_s = $a.deg_s; deg_frame = $a.deg_frame; segments = $a.segments; placed_dz = $dz; handover_s = $hand }
}

function RA-Mirror($ctx, [string]$Tag, [string]$Dir, [int]$logStart) {
    $hand = RA-WaitHandover $ctx
    $sw = [Diagnostics.Stopwatch]::StartNew()                                                               # the shift search needs a parked car
    do { $spd = (Mem-Player $ctx).Speed; if ($spd -lt 0.3) { break }; Start-Sleep -Milliseconds 500 } while ($sw.Elapsed.TotalSeconds -lt 20)
    $dbg = RA-DebugBlockAddr $logStart
    $c0 = RA-Counters $ctx $dbg; $u0 = RA-F64 $ctx 0x507CD8; $v0 = RA-F64 $ctx 0x507C50
    $f0 = Mem-I32 $ctx 0x5A7E1C; $t0 = Get-Date
    & (Join-Path $RA_Fr 'sky-motion.ps1') -Tag $Tag -Pairs $Pairs -GapSeconds 1.0 -OutDir $Dir
    $dt = ((Get-Date) - $t0).TotalSeconds
    $fps = RA-Fps $ctx $f0 $t0
    $c1 = RA-Counters $ctx $dbg; $u1 = RA-F64 $ctx 0x507CD8; $v1 = RA-F64 $ctx 0x507C50
    $csv = Join-Path $Dir "$Tag.csv"
    if (-not (Test-Path $csv)) { return [ordered]@{ status = 'no-csv'; fps = $fps } }
    $pps = @(Import-Csv $csv | ForEach-Object { [double]$_.px_per_s })
    $mean = if ($pps.Count) { [math]::Round(($pps | Measure-Object -Average).Average, 2) } else { $null }
    $md = if ($c0 -and $c1) { [math]::Round(($c1.mirror_draws - $c0.mirror_draws) / $dt, 2) } else { $null }
    $st = if ($spd -ge 0.3) { "moving ($([math]::Round($spd,1)) m/s): shifts include car motion" } else { 'ok' }
    [ordered]@{ status = $st; fps = $fps; sky_px_s = $mean; cloud_u_s = [math]::Round(($u1 - $u0) / $dt, 4); cloud_v_s = [math]::Round(($v1 - $v0) / $dt, 4)
                mirror_draws_s = $md; speed = [math]::Round($spd, 2); pairs = $pps.Count; debug_block = ('0x{0:X}' -f $dbg); handover_s = $hand }
}

function RA-Dodge($ctx, [string]$Tag, [string]$Dir, [int]$logStart) {
    $hand = RA-WaitHandover $ctx
    $dbg = RA-DebugBlockAddr $logStart
    if (-not $dbg) { return [ordered]@{ status = 'no-debug-block (render-interp line missing: fixed set required)' } }
    $ai = @(Mem-Entities $ctx).Count - 1
    [void](Force-Foreground $ctx.Proc.MainWindowHandle)
    $c0 = RA-Counters $ctx $dbg; $f0 = Mem-I32 $ctx 0x5A7E1C; $t0 = Get-Date
    $sw = [Diagnostics.Stopwatch]::StartNew()
    try {
        while ($sw.Elapsed.TotalSeconds -lt $Seconds) {
            if ($Fire) { Key-Down $VK.ENTER }                                                             # fire is Enter (input.map), not Space
            Start-Sleep -Milliseconds 200
        }
    } finally { if ($Fire) { Key-Up $VK.ENTER } }
    $dt = $sw.Elapsed.TotalSeconds
    $c1 = RA-Counters $ctx $dbg; $fps = RA-Fps $ctx $f0 $t0
    if (-not $c0 -or -not $c1) { return [ordered]@{ status = 'debug-block-unreadable'; fps = $fps } }
    $calls = $c1.dodge_calls - $c0.dodge_calls; $yes = $c1.dodge_yes - $c0.dodge_yes; $ticks = $c1.tick20_n - $c0.tick20_n
    $csvOut = Join-Path $Dir "$Tag.csv"
    "tag,seconds,fps,dodge_calls,dodge_yes,tick20_n,ai_cars,fire`n$Tag,$([math]::Round($dt,2)),$fps,$calls,$yes,$ticks,$ai,$([int][bool]$Fire)" | Set-Content $csvOut
    [ordered]@{ status = 'ok'; fps = $fps; dodge_calls_s = [math]::Round($calls / $dt, 2); dodge_yes_s = [math]::Round($yes / $dt, 2)
                calls_per_tick = $(if ($ticks) { [math]::Round($calls / $ticks, 3) } else { $null }); ticks_s = [math]::Round($ticks / $dt, 2)
                ai_cars = $ai; debug_block = ('0x{0:X}' -f $dbg); handover_s = $hand }
}

# ---- telemetry measurements (rate-ab-live.py records, rate-ab-analyse.py judges) -------------------------------------
function RA-Cactus2($ctx, [string]$Tag, [string]$Dir) {
    $hand = RA-WaitHandover $ctx
    [void](Force-Foreground $ctx.Proc.MainWindowHandle)
    $f0 = Mem-I32 $ctx 0x5A7E1C; $t0 = Get-Date
    $live = RA-LiveRun @('cactus', '--pid', $ctx.Proc.Id, '--mission', $Mission, '--out', (Join-Path $Dir $Tag), '--speed', $CactusSpeed,
                         '--dist', $ApproachDist, '--approaches', $Approaches, '--relaunch-at', $RelaunchAt, '--tools', $ToolsDir)
    $fps = RA-Fps $ctx $f0 $t0
    if ($live.status -ne 'ok') { return [ordered]@{ status = $live.status; fps = $fps; handover_s = $hand } }
    $a = RA-Python @($RA_Analyse, 'cactus2', (Join-Path $Dir "$Tag.frames.csv"))
    $a.table -split "`n" | ForEach-Object { Write-Host "    $_" }
    $st = if ($a.valid -gt 0) { 'ok' } else { "no-valid-approaches ($($a.approaches) run: $($a.miss) off the line; $($a.slow) slow)" }
    [ordered]@{ status = $st; fps = $fps; hit_rate = $a.hit_rate; hits = $a.hits; valid = $a.valid; approaches = $a.approaches
                hits_impact = $a.hits_impact; hits_speed = $a.hits_speed; v_before = $a.v_before; steps_frame = $a.steps_frame
                acquired = $live.acquired; notes = ($live.notes -join '; '); handover_s = $hand }
}

function RA-Airborne2($ctx, [string]$Tag, [string]$Dir) {
    $hand = RA-WaitHandover $ctx
    [void](Force-Foreground $ctx.Proc.MainWindowHandle)
    $argv = @('airborne', '--pid', $ctx.Proc.Id, '--out', (Join-Path $Dir $Tag), '--seconds', $Seconds, '--tools', $ToolsDir)
    if ($env:I76_FIXED_STEP) { $argv += @('--fixed-step', $env:I76_FIXED_STEP) }                         # proxy-run set it in this process
    if (-not $NoPlace) { $argv += @('--place', $PlaceX, $PlaceY, $PlaceZ, $PlaceSpeed) }
    $live = RA-LiveRun $argv
    if ($live.status -ne 'ok') { return [ordered]@{ status = $live.status; placed_dz = $live.placed_dz; handover_s = $hand } }
    $a = RA-Python @($RA_Analyse, 'airborne2', (Join-Path $Dir "$Tag.csv"))
    $a.text -split "`n" | ForEach-Object { Write-Host "    $_" }
    $st = if ($a.segments -gt 0) { 'ok' }
          elseif ($live.placed_ok -eq $false) { "placement-failed (read-back dz $($live.placed_dz) m); no airborne segments" }
          else { "no-airborne-segments ($($a.airborne_frames) of $($a.step_frames) step frames airborne; $($a.segments_seen) segments seen; none long enough)" }
    [ordered]@{ status = $st; fps = $a.fps; gain = $a.gain; deg_s = $a.deg_s; deg_step = $a.deg_step; segments = $a.segments; air_s = $a.air_s
                placed_dz = $live.placed_dz; placed_ok = $live.placed_ok; handover_s = $hand }
}

function RA-FarEngine($ctx, [string]$Tag, [string]$Dir, [int]$logStart) {
    $hand = RA-WaitHandover $ctx
    $dbg = RA-DebugBlockAddr $logStart                                                                   # 0 under the stock set: far_steps is then not read
    $argv = @('farengine', '--pid', $ctx.Proc.Id, '--out', (Join-Path $Dir $Tag), '--seconds', $Seconds, '--lift', $FarLift)
    if ($dbg) { $argv += @('--dbg', ('0x{0:X}' -f $dbg)) }
    $live = RA-LiveRun $argv
    if ($live.status -ne 'ok') { return [ordered]@{ status = $live.status; handover_s = $hand } }
    $argv = @($RA_Analyse, 'farengine', (Join-Path $Dir "$Tag.csv")); if ($FarSlot -ge 0) { $argv += $FarSlot }
    $a = RA-Python $argv
    $a.text -split "`n" | ForEach-Object { Write-Host "    $_" }
    $st = if ($null -eq $a.t_cruise_s) { "no-ai-motion ($($a.cars) cars in the table; none reached 3 m/s)" }
          elseif ($null -ne $a.min_dist_m -and $a.min_dist_m -lt $FarMinDist) { "near (slot $($a.slot) came within $([math]::Round($a.min_dist_m)) m: not the far path)" }
          elseif ($env:I76_FAR_ENGINE_DT -and -not ($a.far_steps_s -gt 0)) { 'far-path-not-taken (g_idbg.far_steps did not advance)' }
          else { 'ok' }
    [ordered]@{ status = $st; fps = $a.fps; t_cruise_s = $a.t_cruise_s; cruise_ms = $a.cruise_ms; far_steps_s = $a.far_steps_s; min_dist_m = $a.min_dist_m
                cars = $a.cars; slot = $a.slot; moving_at_start = $a.moving_at_start; lifted_m = $live.lifted_m; debug_block = ('0x{0:X}' -f $dbg); handover_s = $hand }
}

# ---- PER-FRAME-AUDIT-2026-10-03 acceptance measures --------------------------------------------------------------------
function RA-CollDedupe($ctx, [string]$Tag, [string]$Dir, [int]$logStart) {
    $hand = RA-WaitHandover $ctx
    $dbg = RA-DebugBlockAddr $logStart
    if (-not $dbg) { return [ordered]@{ status = 'no-debug-block (render-interp line missing: fixed set required)' } }
    [void](Force-Foreground $ctx.Proc.MainWindowHandle)
    $f0 = Mem-I32 $ctx 0x5A7E1C; $t0 = Get-Date
    $argv = @('ram', '--pid', $ctx.Proc.Id, '--mission', $Mission, '--out', (Join-Path $Dir $Tag), '--speed', $CactusSpeed, '--dist', $ApproachDist,
              '--approaches', $Approaches, '--prefix', $RamPrefix, '--tools', $ToolsDir, '--dbg', ('0x{0:X}' -f $dbg))
    if ($RamOnce) { $argv += '--once' }
    if ($RamPrefix -like 'nsaguar*') { $argv += @('--lat-tol', 0.25) }
    $live = RA-LiveRun $argv
    $fps = RA-Fps $ctx $f0 $t0
    if ($live.status -ne 'ok') { return [ordered]@{ status = $live.status; fps = $fps; handover_s = $hand } }
    $a = RA-Python @($RA_Analyse, 'colldedupe', (Join-Path $Dir "$Tag.frames.csv"))
    $a.table -split "`n" | ForEach-Object { Write-Host "    $_" }
    $st = if ($a.valid -le 0) { "no-valid-rams ($($a.rams) run: $($a.no_contact) without a contact)" }
          elseif ($live.events_lost -gt 0) { "events-lost ($($live.events_lost) telemetry events left the ring unread: impacts and damage undercount)" }
          else { 'ok' }
    [ordered]@{ status = $st; fps = $fps; dmg_ram = $a.dmg_ram; dup_ratio = $a.dup_ratio; events_ram = $a.events_ram; dups_ram = $a.dups_ram
                burst_ram = $a.burst_ram; impacts_ram = $a.impacts_ram; hp_ram = $a.hp_ram; v_contact = $a.v_contact; valid = $a.valid; rams = $a.rams
                zero_step_frac = $a.zero_step_frac; events_lost = $live.events_lost; notes = ($live.notes -join '; '); debug_block = ('0x{0:X}' -f $dbg); handover_s = $hand }
}

function RA-Hazard($ctx, [string]$Tag, [string]$Dir, [int]$logStart) {
    $hand = RA-WaitHandover $ctx
    $dbg = RA-DebugBlockAddr $logStart                                                                   # 0 under the stock set: telemetry numbers only
    [void](Force-Foreground $ctx.Proc.MainWindowHandle)
    $argv = @('hazard', '--pid', $ctx.Proc.Id, '--out', (Join-Path $Dir $Tag), '--seconds', $Seconds, '--hazard', $Hazard, '--tools', $ToolsDir)
    if ($dbg) { $argv += @('--dbg', ('0x{0:X}' -f $dbg)) }
    $live = RA-LiveRun $argv
    if ($live.status -ne 'ok') { return [ordered]@{ status = $live.status; hazard = $live.hazard; rounds = $live.rounds; restored = $live.restored; handover_s = $hand } }
    $a = RA-Python @($RA_Analyse, 'hazard', (Join-Path $Dir "$Tag.frames.csv"))
    $a.text -split "`n" | ForEach-Object { Write-Host "    $_" }
    $st = if (-not $a.rounds) { 'no-rounds-counted (no SHOT event and no ammo used)' }
          elseif ($live.events_lost -gt 0) { "events-lost ($($live.events_lost) telemetry events left the ring unread: the per-second figures undercount)" }
          elseif ($a.window_s -lt 3) { "short-window ($([math]::Round($a.window_s, 1)) s on the patch)" }
          else { 'ok' }
    [ordered]@{ status = $st; fps = $a.fps; impacts_round_s = $a.impacts_round_s; steps_proj_s = $a.steps_proj_s; hz_impacts_s = $a.hz_impacts_s
                hp_round_s = $a.hp_round_s; impacts_s = $a.impacts_s; rounds = $a.rounds; shots = $a.shots; oil_frac = $a.oil_frac
                explosions_s = $a.explosions_s; window_s = $a.window_s; offset_m = $a.offset_m; hazard = $live.hazard; swapped = $live.swapped
                restored = $live.restored; events_lost = $live.events_lost; debug_block = ('0x{0:X}' -f $dbg); handover_s = $hand }
}

function RA-Wmiss($ctx, [string]$Tag, [string]$Dir, [int]$logStart) {
    $hand = RA-WaitHandover $ctx
    $dbg = RA-DebugBlockAddr $logStart
    if (-not $dbg) { return [ordered]@{ status = 'no-debug-block (render-interp line missing: fixed set required)' } }
    [void](Force-Foreground $ctx.Proc.MainWindowHandle)
    $live = RA-LiveRun @('wmiss', '--pid', $ctx.Proc.Id, '--out', (Join-Path $Dir $Tag), '--seconds', $Seconds, '--dbg', ('0x{0:X}' -f $dbg))
    if ($live.status -ne 'ok') { return [ordered]@{ status = $live.status; handover_s = $hand } }
    $a = RA-Python @($RA_Analyse, 'wmiss', (Join-Path $Dir "$Tag.csv"))
    Write-Host "    $($a.text)"
    $st = if (-not ($a.wmiss_req_s -gt 0)) { "no-requests (key $($live.row + 1) held on a dead row and wmiss_req stood still: key not seen, or the row is not the one the key fires)" }
          elseif ($live.rewrites -gt 0) { "condition-came-back ($($live.rewrites) rewrites: something repaired the weapon)" }
          else { 'ok' }
    [ordered]@{ status = $st; fps = $a.fps; wmiss_play_s = $a.wmiss_play_s; wmiss_req_s = $a.wmiss_req_s; req_per_frame = $a.req_per_frame
                play_per_tick = $a.play_per_tick; ticks_s = $a.ticks_s; row = $live.row; restored = $live.restored; debug_block = ('0x{0:X}' -f $dbg); handover_s = $hand }
}

function RA-AiRolls($ctx, [string]$Tag, [string]$Dir, [int]$logStart) {
    $hand = RA-WaitHandover $ctx
    $dbg = RA-DebugBlockAddr $logStart
    if (-not $dbg) { return [ordered]@{ status = 'no-debug-block (render-interp line missing: fixed set required)' } }
    $argv = @('counters', '--pid', $ctx.Proc.Id, '--out', (Join-Path $Dir $Tag), '--seconds', $Seconds, '--mission', $Mission, '--tools', $ToolsDir, '--dbg', ('0x{0:X}' -f $dbg))
    if (-not $NoNear) { $argv += @('--near', '--god') }
    $live = RA-LiveRun $argv
    if ($live.status -ne 'ok') { return [ordered]@{ status = $live.status; handover_s = $hand } }
    $a = RA-Python @($RA_Analyse, 'airolls', (Join-Path $Dir "$Tag.csv"))
    Write-Host "    $($a.text)"
    $st = if (-not ($a.skid_rolls_s -gt 0) -and -not ($a.horn_rolls_s -gt 0)) { "no-rolls (no AI car was in dirt_brave against a vehicle, nor blocked, in $Seconds s; nearest vehicle $([math]::Round([double]$a.near_m)) m)" } else { 'ok' }
    [ordered]@{ status = $st; fps = $a.fps; skid_rolls_s = $a.skid_rolls_s; horn_rolls_s = $a.horn_rolls_s; skid_per_tick = $a.skid_per_tick
                horn_per_tick = $a.horn_per_tick; ticks_s = $a.ticks_s; near_m = $a.near_m; placed = $live.placed; debug_block = ('0x{0:X}' -f $dbg); handover_s = $hand }
}

# entry point for proxy-run's -Run scriptblock. Writes <Dir>\<Tag>.result.json so the result survives the game being killed.
function RA-Measure([string]$Measure, [string]$Tag, [string]$Dir, [int]$LogStart) {
    New-Item -ItemType Directory -Force $Dir | Out-Null
    $res = $null
    $ctx = Mem-Open
    try {
        $res = switch ($Measure) {
            'cactus'   { RA-Cactus $ctx $Tag $Dir }
            'airborne' { RA-Airborne $ctx $Tag $Dir }
            'mirror'   { RA-Mirror $ctx $Tag $Dir $LogStart }
            'dodge'    { RA-Dodge $ctx $Tag $Dir $LogStart }
            'cactus2'  { RA-Cactus2 $ctx $Tag $Dir }
            'airborne2' { RA-Airborne2 $ctx $Tag $Dir }
            'farengine' { RA-FarEngine $ctx $Tag $Dir $LogStart }
            'colldedupe' { RA-CollDedupe $ctx $Tag $Dir $LogStart }
            'hazard'   { RA-Hazard $ctx $Tag $Dir $LogStart }
            'wmiss'    { RA-Wmiss $ctx $Tag $Dir $LogStart }
            'airolls'  { RA-AiRolls $ctx $Tag $Dir $LogStart }
        }
    } catch {
        $res = [ordered]@{ status = "error: $($_.Exception.Message)" }
    } finally { Mem-Close $ctx }
    $res | ConvertTo-Json -Compress | Set-Content (Join-Path $Dir "$Tag.result.json")
    Write-Host ("  [{0}] {1}" -f $Tag, ($res | ConvertTo-Json -Compress))
}

# ---- stats + report -----------------------------------------------------------------------------------------------
function RA-Stats([double[]]$xs) {
    $xs = @($xs | Where-Object { $null -ne $_ -and -not [double]::IsNaN($_) })
    if (-not $xs.Count) { return $null }
    $m = ($xs | Measure-Object -Average).Average
    $sd = if ($xs.Count -gt 1) { [math]::Sqrt((($xs | ForEach-Object { ($_ - $m) * ($_ - $m) }) | Measure-Object -Sum).Sum / ($xs.Count - 1)) } else { $null }
    [pscustomobject]@{ n = $xs.Count; mean = $m; sd = $sd; min = ($xs | Measure-Object -Minimum).Minimum; max = ($xs | Measure-Object -Maximum).Maximum }
}
function RA-Fmt($x, [int]$d = 3) { if ($null -eq $x -or ($x -is [double] -and [double]::IsNaN($x))) { '-' } else { ('{0:N' + $d + '}') -f [double]$x } }
function RA-CondMean($rows, [string]$cond, [string]$col) {
    $xs = @($rows | Where-Object { $_.cond -eq $cond -and $_.status -eq 'ok' -and $_.switch_ok -ne 'False' -and $null -ne $_.$col -and $_.$col -ne '' } | ForEach-Object { [double]$_.$col })
    if ($xs.Count) { ($xs | Measure-Object -Average).Average } else { $null }
}
function RA-Ratio($a, $b) { if ($null -ne $a -and $null -ne $b -and [double]$b -ne 0) { 'x' + (RA-Fmt ([double]$a / [double]$b) 2) } else { '-' } }
# what the audit predicted against what was measured, per measure (appended to REPORT.md)
function RA-Acceptance($rows) {
    $L = New-Object System.Collections.Generic.List[string]
    $conds = @($rows.cond | Select-Object -Unique)
    switch ($Measure) {
        'colldedupe' {
            $L.Add(''); $L.Add('Acceptance (i76-everywhere docs/records/PER-FRAME-AUDIT-2026-10-03.md, F3; 24 physics steps/s):')
            $exp = @{ 20 = '0'; 60 = '~0.6'; 120 = '~0.8' }
            foreach ($fps in 20, 60, 120) {
                $r = RA-CondMean $rows "fixed$fps" 'dup_ratio'; $e = RA-CondMean $rows "fixed$fps" 'events_ram'
                $L.Add("- $fps fps, I76_COLL_DEDUPE=0: dup ratio $(RA-Fmt $r 2) (audit: $($exp[$fps])), $(RA-Fmt $e 1) contact frames per ram, $(RA-Fmt (RA-CondMean $rows "fixed$fps" 'impacts_ram') 1) player IMPACT events per ram")
            }
            $r = RA-CondMean $rows 'fixed120' 'dup_ratio'; $e = RA-CondMean $rows 'fixed120' 'events_ram'
            if ($null -eq $e -or $e -le 0) { $L.Add('- mechanism: NOT MEASURED (no valid ram with counted contacts at fixed120 with I76_COLL_DEDUPE=0)') }
            elseif ($null -eq $r -or $r -le 0.02) { $L.Add("- **MECHANISM NOT CONFIRMED**: the dup ratio is $(RA-Fmt $r 2) at 120 fps with the switch off although contacts were counted ($(RA-Fmt $e 1) per ram). Per the audit F3 should then be withdrawn (or re-tested on a vehicle: -RamPrefix vxktrac).") }
            else { $L.Add("- mechanism confirmed: contacts repeat on frames without a physics step (dup ratio $(RA-Fmt $r 2) at 120 fps with the switch off)") }
            $base = RA-CondMean $rows 'fixed20' 'dmg_ram'
            $aa = RA-Stats @($rows | Where-Object { $_.cond -eq 'fixed20' -and $_.status -eq 'ok' -and $_.dmg_ram -ne '' } | ForEach-Object { [double]$_.dmg_ram })
            $L.Add("- damage per ram (sum of the player IMPACT events' hp), capped 20 with the switch off: $(RA-Fmt $base 1) (A/A sd $(if ($aa) { RA-Fmt $aa.sd 1 } else { '-' })); with the dedupe at 20: $(RA-Fmt (RA-CondMean $rows 'fixed20+sw' 'dmg_ram') 1)")
            foreach ($fps in 60, 120) {
                $off = RA-CondMean $rows "fixed$fps" 'dmg_ram'; $on = RA-CondMean $rows "fixed$fps+sw" 'dmg_ram'
                $L.Add("- $fps fps: passed through $(RA-Fmt $off 1) = $(RA-Ratio $off $base) of capped 20 (audit: up to x$(if ($fps -eq 60) { 3 } else { 5 })); with the dedupe $(RA-Fmt $on 1) = $(RA-Ratio $on $base) (audit: x1.0 within the A/A spread)")
            }
            $L.Add('- the rams hit different buildings at different angles: compare conditions by the mean over all rams, and read hp_ram (armour + chassis only) against dmg_ram (which includes component hp).')
        }
        'hazard' {
            $L.Add(''); $L.Add('Acceptance (PER-FRAME-AUDIT-2026-10-03 F1): with the fix every patch steps on the 20 Hz grid, so per round dropped the player takes 20 ordnance IMPACT events per second at any frame rate (stock: one per frame), and g_idbg.hazard_steps runs at 20 per second per projectile.')
            foreach ($c in $conds) {
                $L.Add("- ${c}: $(RA-Fmt (RA-CondMean $rows $c 'impacts_round_s') 1) IMPACT /s per round, $(RA-Fmt (RA-CondMean $rows $c 'hp_round_s') 1) hp /s per round, hazard_steps $(RA-Fmt (RA-CondMean $rows $c 'steps_proj_s') 1) /s per projectile, contact effects $(RA-Fmt (RA-CondMean $rows $c 'hz_impacts_s') 1) /s, oil flag $(RA-Fmt (RA-CondMean $rows $c 'oil_frac') 2) of frames")
            }
            $L.Add('- an oil slick does no damage: if its row shows 0 IMPACT events, read steps per projectile, the contact effects and the oil flag instead. The drive-through test (10 passes at 30 m/s, traction loss on every pass) is not automated.')
        }
        'wmiss' {
            $L.Add(''); $L.Add('Acceptance (PER-FRAME-AUDIT-2026-10-03 F4): wmiss_req = frame rate, wmiss_play = 20 /s at any frame rate.')
            foreach ($c in $conds) {
                $L.Add("- ${c}: wmiss_play $(RA-Fmt (RA-CondMean $rows $c 'wmiss_play_s') 1) /s ($(RA-Fmt (RA-CondMean $rows $c 'play_per_tick') 2) per 20 Hz tick), wmiss_req $(RA-Fmt (RA-CondMean $rows $c 'wmiss_req_s') 1) /s ($(RA-Fmt (RA-CondMean $rows $c 'req_per_frame') 2) per frame)")
            }
            $L.Add('- the click cadence by ear is not automated (the test instance is silent).')
        }
        'airolls' {
            $L.Add(''); $L.Add('Acceptance (PER-FRAME-AUDIT-2026-10-03 F5): rolls per 20 Hz tick with the hold = capped 20; with I76_AI_ROLL_HOLD=0 they scale with fps / 20.')
            foreach ($fps in 20, 60, 120) {
                $off = RA-CondMean $rows "fixed$fps" 'skid_per_tick'; $on = RA-CondMean $rows "fixed$fps+sw" 'skid_per_tick'
                $L.Add("- $fps fps: skid rolls per tick $(RA-Fmt $off 3) every frame, $(RA-Fmt $on 3) held ($(RA-Ratio $off $on)); horn rolls per tick $(RA-Fmt (RA-CondMean $rows "fixed$fps" 'horn_per_tick') 3) / $(RA-Fmt (RA-CondMean $rows "fixed$fps+sw" 'horn_per_tick') 3)")
            }
            $L.Add('- the share of frames an AI car spends in dirt_brave against a vehicle differs run to run (it is the A/A spread); entries into behaviour 7 per minute and the blocked-car horn case are not automated.')
        }
    }
    $L
}

function RA-Report {
    if (-not (Test-Path $RA_Results)) { Write-Host "no results at $RA_Results" -ForegroundColor Yellow; return }
    $rows = @(Import-Csv $RA_Results)
    $primary = $RA_M.Primary; $cols = $RA_M.Cols
    $order = @($Conditions) + @($rows.cond | Select-Object -Unique | Where-Object { $Conditions -notcontains $_ })
    $L = New-Object System.Collections.Generic.List[string]
    $L.Add("# rate-ab: $Measure - switch under test $(if ($Switch) { $Switch } else { '(none)' })$(if ($RA_M.Kill) { ' (kill switch: conditions without +sw run it at 0)' })")
    $L.Add('')
    $L.Add("mission $Mission; $(Get-Date -Format 'yyyy-MM-dd HH:mm'); results $RA_Results")
    $L.Add("reads: $($RA_M.Reads)")
    $L.Add('')
    $base = $null
    $L.Add("| condition | set | env | n (ok/total) | fps | $primary mean | sd | min..max | vs A/A | " + (($cols | Where-Object { $_ -ne $primary } | ForEach-Object { "$_ mean" }) -join ' | ') + ' | switch verified |')
    $L.Add('|---|---|---|---|---|---|---|---|---|' + (($cols | Where-Object { $_ -ne $primary } | ForEach-Object { '---' }) -join '|') + '|---|')
    foreach ($c in $order) {
        $rs = @($rows | Where-Object { $_.cond -eq $c })
        if (-not $rs.Count) { continue }
        $ok = @($rs | Where-Object { $_.status -eq 'ok' -and $_.switch_ok -ne 'False' })
        $s = RA-Stats @($ok | ForEach-Object { if ($_.$primary -ne '') { [double]$_.$primary } })
        $fps = RA-Stats @($ok | ForEach-Object { if ($_.fps -ne '') { [double]$_.fps } })
        $vs = '-'
        if ($s) {
            if (-not $base) { $base = $s; $vs = "A/A: sd $(RA-Fmt $s.sd) (noise floor)" }
            else {
                $d = $s.mean - $base.mean
                $flag = if ($null -ne $base.sd -and $base.sd -gt 0) { if ([math]::Abs($d) -gt 2 * $base.sd) { 'outside 2 sd' } else { 'within 2 sd' } } else { 'no A/A spread' }
                $vs = "$(RA-Fmt $d) ($flag)"
            }
        }
        $others = ($cols | Where-Object { $_ -ne $primary } | ForEach-Object { $col = $_; $st = RA-Stats @($ok | ForEach-Object { if ($_.$col -ne '') { [double]$_.$col } }); if ($st) { RA-Fmt $st.mean 2 } else { '-' } }) -join ' | '
        $ver = (@($rs | ForEach-Object { $_.switch_ok }) | Select-Object -Unique) -join '/'
        $envText = ($rs[0].env); $set = $rs[0].set
        $L.Add("| $c | $set | $envText | $($ok.Count)/$($rs.Count) | $(if ($fps) { RA-Fmt $fps.mean 1 } else { '-' }) | $(if ($s) { RA-Fmt $s.mean } else { '-' }) | $(if ($s) { RA-Fmt $s.sd } else { '-' }) | $(if ($s) { "$(RA-Fmt $s.min)..$(RA-Fmt $s.max)" } else { '-' }) | $vs | $others | $ver |")
    }
    $L.Add('')
    $L.Add('Reading: the first row is the A/A control (one condition, n runs); its sd is the spread of the measurement itself. A later row whose delta sits within 2 sd of it has not been shown to differ. n counts only runs with status ok and a verified switch; the raw per-run rows (and failures) are in results.csv.')
    foreach ($line in @(RA-Acceptance $rows)) { $L.Add($line) }
    $bad = @($rows | Where-Object { $_.status -ne 'ok' -or $_.switch_ok -eq 'False' })
    if ($bad.Count) { $L.Add(''); $L.Add('Excluded runs:'); foreach ($b in $bad) { $L.Add("- $($b.tag): $($b.status); switch_ok=$($b.switch_ok); proxy: $($b.proxy_log)") } }
    $enc = New-Object Text.UTF8Encoding $false
    [IO.File]::WriteAllText($RA_Report, ($L -join "`n") + "`n", $enc)
    Write-Host ''; $L | ForEach-Object { Write-Host $_ }
    Write-Host "`nwrote $RA_Report" -ForegroundColor Green
}

# ---- the plan -------------------------------------------------------------------------------------------------------
$plan = @()
$conds = @($Conditions | ForEach-Object { RA-Condition $_ })
foreach ($c in $conds) { for ($r = 1; $r -le $Runs; $r++) { $plan += [pscustomobject]@{ Cond = $c; Run = $r; Tag = ('{0}fps-{1}-run{2}' -f $c.Fps, $c.Name, $r) } } }
if ($Runs -lt 2) { Write-Host "Runs=${Runs}: no A/A spread can be reported with one run per condition" -ForegroundColor Yellow }

if ($ReportOnly) { RA-Report; return }

Write-Host ("rate-ab: measure={0} switch={1} mission={2} runs/condition={3} conditions: {4}" -f $Measure, $Switch, $Mission, $Runs, ($conds.Name -join ', ')) -ForegroundColor Cyan
Write-Host ("  reads: {0}" -f $RA_M.Reads)
Write-Host ("  A/A first: {0} x{1} before any other condition" -f $conds[0].Name, $Runs)
Write-Host ("  out: {0}" -f $OutDir)
$i = 0
foreach ($step in $plan) {
    $i++; $c = $step.Cond
    $dir = Join-Path $OutDir $c.Name
    $envLit = '@{ ' + (($c.Env.Keys | ForEach-Object { "$_ = '$($c.Env[$_])'" }) -join '; ') + ' }'
    $runLit = "{ RA-Measure -Measure '$Measure' -Tag '$($step.Tag)' -Dir '$dir' -LogStart <mciproxy.log line count at launch> }"
    $cmd = "& '$RA_ProxyRun' -Mission $Mission -Set $($c.Set) -Env $envLit -Hold 0 -BootTimeout $BootTimeout -Run $runLit"
    if ($DryRun) {
        Write-Host ("[dry-run] {0}/{1} {2}" -f $i, $plan.Count, $step.Tag) -ForegroundColor Yellow
        Write-Host ("  clear env: {0}" -f ($RA_NEW_SWITCHES -join ' '))
        Write-Host ("  {0}" -f $cmd)
        continue
    }
    Write-Host ("===== {0}/{1} {2}  (set {3}; {4}) =====" -f $i, $plan.Count, $step.Tag, $c.Set, $c.EnvText) -ForegroundColor Cyan
    foreach ($v in $RA_NEW_SWITCHES) { Remove-Item "Env:$v" -ErrorAction SilentlyContinue }
    New-Item -ItemType Directory -Force $dir | Out-Null
    $resFile = Join-Path $dir "$($step.Tag).result.json"
    if (Test-Path $resFile) { Remove-Item $resFile -Force }                                               # never reuse a stale result
    $RA_LogStart = if (Test-Path $RA_GameLog) { @(Get-Content $RA_GameLog).Count } else { 0 }
    $run = [scriptblock]::Create("RA-Measure -Measure '$Measure' -Tag '$($step.Tag)' -Dir '$dir' -LogStart $RA_LogStart")
    $envHt = @{}; foreach ($k in $c.Env.Keys) { $envHt[$k] = $c.Env[$k] }                                 # proxy-run declares [hashtable]
    $err = $null
    try { & $RA_ProxyRun -Mission $Mission -Set $c.Set -Env $envHt -Hold 0 -BootTimeout $BootTimeout -Run $run }
    catch { $err = $_.Exception.Message; Write-Host "  proxy-run failed: $err" -ForegroundColor Red }
    foreach ($v in $RA_NEW_SWITCHES) { Remove-Item "Env:$v" -ErrorAction SilentlyContinue }
    # the proxy log lines of this run that name our switches: did each take effect?
    $plog = @()
    if (Test-Path $RA_GameLog) {
        $all = @(Get-Content $RA_GameLog)
        if ($all.Count -gt $RA_LogStart) { $plog = @($all[$RA_LogStart..($all.Count - 1)] | Where-Object { $_ -match 'coll-window|coll-dedupe|perframe-fixes|hazard-contact|ai-fixes|mirror-rate|far-engine-dt|glide-refresh|fps-cap|fixed-step|render-interp|framerate-fixes|mission-launch|telemetry:|trainer:|CRASH|crash:' } | Select-Object -Unique) }
    }
    $swOk = 'n/a'
    foreach ($k in $c.Env.Keys) {
        if (-not $RA_LOGTAG[$k]) { continue }
        $line = $plog | Where-Object { $_ -match [regex]::Escape($RA_LOGTAG[$k]) } | Select-Object -First 1
        $good = [bool]($line -and ($line -notmatch 'not applied|NOT |ABORTED|hook failed|needs I76_'))
        if ($swOk -eq 'n/a') { $swOk = [string]$good } elseif (-not $good) { $swOk = 'False' }
    }
    if ($RA_M.LogCheck) {                                                                                 # the fix under test logged what this condition expects
        foreach ($rx in @(& $RA_M.LogCheck $c | Where-Object { $_ })) {
            if ($plog | Where-Object { $_ -match $rx } | Select-Object -First 1) { if ($swOk -eq 'n/a') { $swOk = 'True' } }
            else { $swOk = 'False'; Write-Host "  proxy log: no line matching /$rx/" -ForegroundColor Red }
        }
    }
    $res = if (Test-Path $resFile) { Get-Content $resFile -Raw | ConvertFrom-Json } else { $null }
    $row = [ordered]@{ tag = $step.Tag; cond = $c.Name; run = $step.Run; set = $c.Set; env = $c.EnvText; mission = $Mission
                       status = $(if ($res) { $res.status } elseif ($err) { "proxy-run: $err" } else { 'no result (boot failed or measurement never ran)' })
                       fps = $(if ($res) { $res.fps } else { $null }) }
    foreach ($k in $RA_M.Cols) { $row[$k] = $(if ($res -and $res.PSObject.Properties[$k]) { $res.$k } else { $null }) }
    $row.switch_ok = $swOk; $row.proxy_log = ($plog -join ' | ') -replace ',', ';'; $row.when = (Get-Date -Format 's')
    [pscustomobject]$row | Export-Csv -NoTypeInformation -Append -Path $RA_Results
    Write-Host ("  recorded {0}: status={1} fps={2} {3}={4} switch_ok={5}" -f $step.Tag, $row.status, $row.fps, $RA_M.Primary, $row[$RA_M.Primary], $swOk)
    Start-Sleep -Seconds 3
}
if ($DryRun -and $RA_M.Live) {
    # the offline half of a telemetry measurement, with no game: header layouts, the mission's ODEF and the approach plan,
    # then the analysers on synthetic telemetry
    Write-Host ("[dry-run] in each run: python rate-ab-live.py {0} --pid <game> --out <dir>\<tag> ...; then python rate-ab-analyse.py {1} <capture>" -f $RA_M.Live, $Measure) -ForegroundColor Yellow
    if ($RA_M.LogCheck) { foreach ($c in $conds) { Write-Host ("[dry-run] {0}: the proxy log must show /{1}/" -f $c.Name, ((@(& $RA_M.LogCheck $c | Where-Object { $_ }) -join '/ and /'))) } }
    $dargs = @($RA_M.Live, '--dry-run', '--mission', $Mission, '--seconds', $Seconds, '--tools', $ToolsDir)
    if ($Measure -eq 'cactus2') { $dargs += @('--speed', $CactusSpeed, '--dist', $ApproachDist, '--approaches', $Approaches) }
    if ($Measure -eq 'airborne2' -and -not $NoPlace) { $dargs += @('--place', $PlaceX, $PlaceY, $PlaceZ, $PlaceSpeed) }
    if ($Measure -eq 'farengine') { $dargs += @('--lift', $FarLift) }
    if ($Measure -eq 'colldedupe') { $dargs += @('--speed', $CactusSpeed, '--dist', $ApproachDist, '--approaches', $Approaches, '--prefix', $RamPrefix); if ($RamOnce) { $dargs += '--once' } }
    if ($Measure -eq 'hazard') { $dargs += @('--hazard', $Hazard) }
    if ($Measure -eq 'airolls' -and -not $NoNear) { $dargs += @('--near', '--god') }
    & python -u $RA_Live @dargs | ForEach-Object { Write-Host "  $_" }
    Write-Host '[dry-run] rate-ab-selftest.py (analysers on synthetic telemetry):' -ForegroundColor Yellow
    & python -u $RA_SelfTest | ForEach-Object { Write-Host "  $_" }
    if ($LASTEXITCODE) { Write-Host '[dry-run] SELFTEST FAILED' -ForegroundColor Red }
}
if ($DryRun) {
    Write-Host ("[dry-run] {0} runs planned, nothing launched. Table columns: condition | set | env | n | fps | {1} mean | sd | min..max | vs A/A | {2} | switch verified" -f $plan.Count, $RA_M.Primary, (($RA_M.Cols | Where-Object { $_ -ne $RA_M.Primary }) -join ' | ')) -ForegroundColor Yellow
    return
}
RA-Report
