# sound

**Contract.** One DirectSound manager (0x5fce00; the pointer at 0x524564) keeps active and parked voice lists sorted
by priority. Game code requests sounds by name and object:
- `sound_PlayOnObjectSustained` 0x423230: repeat requests keep the running voice;
- 0x4250f0 and `sound_PlayOnObject` 0x4231f0: one-shots;
- `sound_PlayVehicleEvent` 0x422f20: vehicle events.

`sound_StartObjectSound` 0x421b40 starts a voice or refreshes an existing one. The per-frame sound update 0x421400
stops loops that were not refreshed that frame (keep-alive byte +0x74).

Static reading of md5 9a232dcc (2026-09-27): batches `physics-map-1` (sound_* event, engine, horn and ignition names)
and `range-n-1` (the manager, 117 names in 0x420000-0x42ffff), from reviewed read-only drafts.

## Manager

- **Voices.** `sound_AllocVoice` 0x422750 admits a voice or steals one by priority. The player's engine loop gets
  priority 0x4f.
- **Distance.** Voices 600 m or more from the listener are stopped (0x421c35, 360000 = 600^2). Loops evicted for
  distance or voice pressure are parked, not freed, and come back when they qualify again (0x422a90 / 0x422b40).
- **3D.** The listener follows the camera; buffer parameters are per voice. Volumes go through a percent-to-millibel
  table at 0x5fcc20.
- **Samples.** `sound_LoadSample` 0x425130 loads .wav / .gpw, sharing twins.
- **Engine sounds.** engsnd.dat rows (0x588e00, 0x60 bytes each) give each engine its loop (+0x0c), horn (+0x19) and
  three ignition sounds chosen by engine health (+0x26 / +0x38 / +0x4c, with times) (`sound_GetEngine*`).
- **Vehicle events** (`sound_PlayVehicleEvent`):

  | event | sound |
  |---|---|
  | 1 / 2 | start / stop the engine loop |
  | 3 | horn |
  | 4 | vland (player) |
  | 5 | vvcoll |
  | 6 | vbcoll |
  | 7 | vexplode |
  | 8 | vmgun |
  | 9 | vmissile |
  | 10 / 11 | skid loop start / stop (player) |
  | 16 | vcsign |

- **CB radio**: a queue (0x423620 and neighbours). It needs the voice level and channel count options (0x654b92,
  0x654b93) >= 2.
- **CD music**: MCI (0x423400, 0x424190 ...). The music-fix proxy redirects it to the GOG mp3 tracks
  (i76-everywhere `music-fix`).
- **Options** 0x654b90..0x654b93 (music, SFX, voice, channels): the value 1 is treated as 0 everywhere (0x4211b0,
  0x421a60, 0x424b60).

## Frame-rate notes

Sounds requested every frame while a state holds retrigger on the frame grid: the lock tones, the locked radar ping,
and skid / flat / damage. The proxy's `I76_FRAMERATE_FIXES` gates their starts to 20 Hz (`framerate.md`,
`camera.md`).

## Voices, engine, tyres, 3D and CB (static, md5 9a232dcc, 2026-09-27, gap sound-mission)

**Instance** (0x7c bytes): +0x14 flags, +0x18 frequency (Hz), +0x1c volume (%), +0x20 pan, +0x24 / +0x28 / +0x2c start /
update / stopped callbacks (events 1 / 2 / 3), +0x3c mode, +0x40 GAS volume, +0x48 sample rate, +0x5c object, +0x74 keep-alive.
- **Start** (`sound_StartVoice` 0x4220c0): freq = sample rate and volume = GAS volume (0x4220fa / 0x4220fd). The random
  pitch (x0.80..1.16) is rolled once, at start (0x42210d). The start callback gets event 1 (0x422132).
- **Every frame** (`shell_cb_10` 0x421400): volume and freq are reset to the GAS values (0x4215cc / 0x4215d8), the update
  callback gets event 2 (0x421613), and the result is applied (0x421624). A stopped buffer calls the stopped callback
  (event 3, 0x4215af).
- **Sustained loops** (mode 2) stop at the first update with no request since the last one. Keep-alive: 1 at start
  (0x4220f1), +1 per request (0x421c8b), tested and cleared every frame (0x42151e / 0x42155f).
- **Volume** (0x42182f..0x421854): millibels = T[trunc(vol% x L x 0.1)]. L = SFX level 0x654b91 (0x4213c8), or voice
  level 0x654b92 for flag 4 (0x4213d6). T[0] = -10000; T[i] = 400 x log2(i/100), i = 1..100 (0x421323..0x421376).
  That is -4 dB per halving, 0 dB at 100% x L 10.
- **3D** (`sound_Update3DPosition` 0x421900; deferred SetAllParameters 0x421a4c).
  - Position = the object's translation; velocity = `object_GetVelocity` (0x4219d6).
  - Min distance 10 m (0x421a2b). Flag 0x200 makes it 100 m (0x421a1c): the detached one-shots vvcoll / vbcoll /
    vexplode (0x42300d) and `sound_PlayOneShotAt` (0x4232f6), which drop their object after one positioning (0x4218a9).
  - Max distance 400 m (0x421a35); cones 360/360 (0x421252).
  - Listener: distance factor 1.0 (0x42122f), rolloff 1.0 (0x421248), Doppler 0.8 (0x421261). Position = the camera eye
    0x4c2890 (0x42249d); orientation = the camera matrix (0x4224c0); velocity = the **player car's** (0x422498).
  - DirectSound applies gain = min/d between min and max, and Doppler. The exe attenuates nothing itself. In the cockpit
    view (0x4c2724) the player's own voices sit on the listener (0x42194d..0x4219a0): centred, no Doppler.
- **Cull**: d^2 >= 360000 from the **player car**, not the camera, refuses a start or parks a voice (0x421c35, 0x422bf1).
  Loop play blocks skip the start test (0x421bb1). While paused offline, only params flag 0x10 can start (0x421b8f).
- **Priority**: the play block adds onto the GAS priority (0x42204f); the player adds +0x14 (0x421cb1); the player's
  engine play block is 0x4f (0x424c51).

**Engine loop** (`sound_CreateEngineLoop` 0x424bc0 from `physics_InitEntity` 0x438fb8; restarted by event 1 through
0x424d20). It is a mode 1 loop (0x424c65), kept at entity+0x10c (0x424c90). A revable engsnd row (+8, 0x424c23) gets
0x424ca0 as its start and update callback (0x424c2f):
  f(Hz) = 8268.75 + 8268.75 x (rpm - 1050) / 4950   (rpm = engine+0x1c; 0x424cde..0x424d04; 0x4bccf8 = 1050,
  0x4bccfc = 1/4950, 0x4bcd00 = 8268.75, 0x4bcd04 = -8268.75)
- 8268.75 Hz (0.75 x 11025) at idle, 16537.5 at the 6000 free-rev cap, 7935 at rpm 850, 18208 at the 7000 limit.
- The value is absolute Hz, independent of the sample rate; the stock loops are all 11025 Hz mono. Non-revable rows
  (eitank, aheli, vballoon) play at the sample rate.
- **Volume ignores rpm and throttle.** It is the GAS volume every frame (100; eimarx 60). Throttle reaches the pitch only
  through rpm (the free-rev branch, engine.md). A vanished vehicle stops the voice (0x424cbf).
- Ignition (`entity_UpdateState` 0x465370): the sound plays (0x465419) and is timed at entity+0x450; at expiry, event 1
  starts the loop (0x4655f1). Engine off or death sends event 2 (0x4653ac, 0x465402).

**Tyre loops** (`physics_PlayTyreSounds` 0x43d500): player car only (0x43d51a), sustained (0x423230), constant volume
and pitch.
- Airborne (veh+0x454 bit 4): silent (0x43d530). Bit 2 (skid): skid[s] at any speed (0x43d539).
- Above 7.0 m/s only (veh+0xac, 0x43d559, 0x4bd1f4): not skidding, bit 0x2000 (lateral force at the grip limit, set at
  0x43b50c) gives turn[s], otherwise dust[s] (0x43d574..0x43d590); a flat front or rear wheel gives tflat.wav
  (0x43d5e7); throttle < -0.5 with brakes below half their base strength gives fdmg1.wav (0x43d5f4..0x43d626).
- Table 0x4bd0d0, by .ter surface (veh+0x45c), not WRLD. {skid, turn, dust}: 0 / 3 / 4 / 7 = tskid2, tturn2, vcddirt;
  1 = tskid3, tturn3, vcdsand; 2 / 6 = tskid1, tturn1, none; 5 = tskid4, tturn4, vcdgrav. tskid / tturn play at 50, vcd at 100.
- Bit 2 is set by: rolling against the gear direction above 1 m/s with drive (0x43abf5); a traction-solve slide
  (0x43b150); the player-only rest branch (0x43a9b5). vskid.wav (events 10 / 11) has no caller.
- Impacts (|impact|^2): vehicle-vehicle vvch2 > 2025 (0x434e0d), vvcre2 > 500 (0x434e2c), otherwise vvcbb3. Class 4:
  vnvco3; class 3: vnvcs5; other objects vnvcs3 > 500 (0x434e9b), otherwise vnvcs1.

**CB radio** (head 0x52457c; node 0x24 bytes: name[16], +0x10 speaker, +0x14 voice, +0x18 prio, +0x1c tick, +0x20 next).
- **Enqueue** (`sound_CbEnqueue` 0x423620):
  - The STOPCB latch 0x524580 rejects everything (0x423620). 'STOPCBXX' sets it and returns (0x423651), without stopping
    or flushing. It is cleared only by `sound_SetCbEnabled(1)` at each mission load (0x40323a).
  - A dead speaker (object+0x10 bit 0x200) is rejected (0x42366e). A voice or channel option <= 1 returns 1 without
    queueing (0x42368a / 0x423696).
- **Busy queue:** prio 5 is dropped (0x4236af); prio 6 is dropped when the head's prio < 5 (0x4236bd). Prio 1, or prio < 5
  when the head's prio >= 5, flushes everything, including the playing line (0x4236d1..0x423715). Prio 2 replaces the
  playing head, which is stopped; the new line inherits its next (0x423771..0x4237b8). Anything else is appended (0x4237c0).
- **Start:** prio 4 lines older than 10000 ms are dropped (0x4237f5). Lines play 2D at priority 10000 (0x42383f), voice
  level (flags 5, 0x423837), with the stopped callback 0x4238e0 (0x42382e). A line that fails to start (e.g. paused
  offline) is dropped. A player speaker shows the handset unless binoculars are up (0x423861).
- **0x4238e0** frees the head, skips dead speakers (0x423950) and stale prio 4 lines (0x42395c), and starts the next
  (0x4239aa).
- **Speaker dies mid-line.** The death paths (0x4640f3, 0x464ba7, 0x466206) call `sound_CbDropSpeaker` 0x423a90 before
  they set bit 0x200 (0x46413d, 0x464bf1, 0x46635a).
  - A playing line gets cmike.wav at prio 2 (0x423ab5..0x423abd): the line is cut, the click plays, and the queue is kept.
    The speaker's queued lines are freed (0x423afe).
  - After STOPCB, cmike is rejected, so the line plays to its end. A playing prio 5/6 head is flushed with the queue.
- killCB flushes everything (0x413587). The in-game menu flushes when the voice level is off (0x495252).
