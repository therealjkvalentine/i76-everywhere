# Sound interposer review against the sound spec (2026-10-01)

Scope: `sound-rumble/` (dsndrumble.c), `music-fix/` (strlkproxy.c: the MCI music path and the per-frame
sound gates), `smack-music-fix/`, `tools/winmm-cdaudio/`, `tools/i76-music.ps1`, `tools/gpw-envelopes.py`,
`tools/gpw-fingerprints.py`, read against `C:\Users\james\i76-map\subsystems\sound.md`,
`data\notes\terrain-text-sound.md`, `data\FORMATS.md` and the pristine image (md5 9a232dcc) disassembled with
`i76-map\tools\disasm.py` and a raw capstone pass for 0x424ca0. Read-only; the game was not run.

Legend. **VERIFIED** = an instruction or a logged live observation cited by address or file. **INFERRED** = my
reading of behaviour from those. **PROPOSED** = not built, not tested. Nothing in section 5 exists yet.

---------------------------------------------------------------------------------------------------
## 1. What each interposer does today, and its verification state

| interposer | what it does | state (from its README / CHANGELOG / source header) |
|---|---|---|
| `sound-rumble/dsndrumble.c` (proxy `dsound.dll`) | Wraps `IDirectSound`/`IDirectSoundBuffer`; on `Unlock` FNV-1a-hashes the PCM the game wrote, matches (length, hash) to a `.gpw` name from `rumble-fingerprints.ini`, picks a motor by the name's first letter, and on `Play` runs that sound's 25 ms RMS envelope (`rumble-envelopes.ini`) on an XInput pad; `Stop` ends looping voices; 60 Hz mixer thread, per-motor MAX, 0.30 dead-zone lift, gamma 2. | **EXPERIMENTAL, never run in-game** (header lines 18-20, README "Status"). Natively verified: fingerprint uniqueness over all 123 `.gpw`, FNV-1a parity DLL/Python, envelope generation. Unverified: the COM interception, that the game writes PCM verbatim. Mac-oriented (`install.sh` targets the Sikarugir wrapper). Not installed anywhere. |
| `music-fix/strlkproxy.c` music path (proxy `Strlkup.dll`) | IAT-patches i76.exe's `WINMM.dll!mciSendCommandA`, `auxGetNumDevs`, `auxGetDevCapsA`, `auxSetVolume`. Emulates a 17-track mixed-mode CD (track 1 data, 2..17 audio) with lengths and TOC from the real `music\N.mp3` via `mpegvideo`; `MCI_PLAY` plays `music\N.mp3`; `MCI_STATUS` answers MEDIA_PRESENT, MODE, NUMBER_OF_TRACKS, LENGTH, POSITION (TOC vs playhead), TYPE_TRACK; aux volume -> `setaudio i76cd volume to N`. | **VERIFIED live** (`docs/MUSIC.md`: `MCI_PLAY ... -> track 13` in a mission, then track 2; `0x524674`=1, `0x4ed890`=0xC0DE; `auxSetVolume -> 700/1000`). Deployed by `setup-windows.ps1`. The README's "Not yet observed: MCI_PLAY" and "Known limitation" (aux volume no-op) paragraphs are **stale**: both were resolved on 2026-08-08. |
| `music-fix/strlkproxy.c` sound gates (`I76_FRAMERATE_FIXES`) | `frame_sound_wrap` on the six `call 0x423230` sites (lock tones 0x4a405e/0x4a40ad; tyre/surface/flat/damage 0x43d54d/0x43d590/0x43d5ec/0x43d62b) lets a *new* start through only on the 20 Hz grid, passes loop refreshes every frame; `radar_ping_wrap` coalesces CRADAR.WAV (0x4605ee/0x4608f1) to one per grid frame. | **VERIFIED live** for the radar ping (commit 598367f: 60/s -> 20/s) and lock tones (README: "confirmed in play"); vehicle per-frame sounds: patched and booted, rate not separately measured (commit d76b600). Opt-in; not deployed to the playable install (README). |
| `smack-music-fix/smackproxy.c` (proxy `SMACKW32.DLL`) | Ordinal-exact forwarder; `_SmackOpen@12` broadcasts `MCI_STOP` to `MCI_ALL_DEVICE_ID` (and to GOG's `win32.dll` if loaded) so CD music stops for FMVs as the 1997 drive did. | CHANGELOG line 152: "Cutscene-music bug fixed". Written for the Mac/DxWnd build; Windows install is a manual rename. Whether it is installed on the Windows playable copy is not recorded anywhere I read. |
| `tools/winmm-cdaudio/` | A winmm proxy that emulated cdaudio over the MP3s. | Works standalone (15 self-test assertions, MUSIC.md) but **cannot load into i76.exe** (AppCompat shim engine preloads System32 winmm). **Only binaries are present** (`winmm.dll`, `.lib`, `.exp`, `.obj`, `build.log`); `winmm_proxy.c` is not in the tree and not tracked (`git ls-files` lists nothing under it). Superseded; MUSIC.md says do not deploy. |
| `tools/i76-music.ps1` | Plays `music\*.mp3` beside the game through `mpegvideo`, numerically sorted, optional mission-only via `[[[0x54a264]]+0x70]`. | Stopgap, **superseded** by the proxy; `PLAY-i76.ps1` suppresses it when `strlkup_orig.dll` exists. Its header still says "THE PROPER FIX would be a winmm.dll proxy ... needs a C compiler, which this machine does not have" -- both claims are retracted in MUSIC.md. |
| `tools/gpw-envelopes.py`, `tools/gpw-fingerprints.py` | Derive per-sound RMS envelopes (25 ms windows, peak-normalised) and (len, FNV-1a) fingerprints from the user's `I76.ZFS`. | Native-tested per the sound-rumble README; also consumed by `ffb-shim` for skid texture. Fine as data tools. |

---------------------------------------------------------------------------------------------------
## 2. Correctness against the spec

### 2.1 dsndrumble: classification is by buffer *content*, not by name or object

**VERIFIED (source).** `dsb_Unlock` hashes the bytes the game wrote on the first Lock/Unlock of each wrapped
buffer (`w->env < 0` guard, lines 282-291) and `dsb_Play` starts a rumble voice for the matched name. Nothing in
the DirectSound surface carries the object. The spec gives the game-side record that does:

- The manager `[0x524564]` keeps the active list at `mgr+0x1c` (0x421c51); each 0x7c-byte voice has `+4` name
  (compared with `_stricmp` at 0x421c68), `+0x3c` mode, `+0x5c` object, `+0x74` keep-alive, `+0x18` Hz,
  `+0x1c` vol%, `+0x48` sample rate (`sound.md` "Instance"; 0x4220fa/0x4220fd VERIFIED).
- "Is it the player's?" is decided at 0x421c9a..0x421cb1: `0x458c90(obj)` -> entity, `test byte [ent+0x10],0x10`,
  then `add [block+4],0x14` (the +20 player priority). `0x457530()` returns the player-object pointer-pointer
  (used at 0x421bc4 and by `frame_sound_wrap`). Either test gives "object-is-player" for free.

Consequences for the DirectSound proxy (all INFERRED from the two sources):

1. **No player/other distinction.** An AI car's `vmgun`/`vexplode` 350 m away rumbles like your own. DirectSound
   attenuates 3D buffers internally (`SetAllParameters`, 0x421a4c), not through `SetVolume`, so the proxy sees no
   distance either. It also does not wrap `IDirectSound3DBuffer` (`dsb_QI` returns the real interface), so it
   cannot read positions without more wrapping.
2. **Engine loops become a permanent floor.** `motor_of` sends `e*` to the heavy motor as "impact"; the stock
   engine loops are `ei*`/`e*` names (engsnd.dat +0x0c) and are mode-1 loops, so from ignition on the heavy motor
   sits at >= 0.30 (dead-zone lift applies to any active voice). `docs/SIM-RUMBLE-RESEARCH.md` ranks engine as the
   *quietest* floor. Same for `vcd*` surface loops (also motor 0, looping).
3. **Pitch changes break envelope timing.** The engine loop's frequency is rewritten every frame (0x424ca0, section
   3.2) and one-shots get a 0.80..1.16 random pitch (0x42211b); the proxy walks the envelope at 25 ms/window
   regardless, so the rumble no longer lines up with the sound. Minor for 8-bit 11 kHz effects.
4. **Twins and duplicates.** `sound_LoadSample` shares twin samples and the game may `DuplicateSoundBuffer`; the
   proxy wraps duplicates but a duplicate is never Locked, so `w->env` stays -1 and it never rumbles. Whether the
   game duplicates at all is unverified.
5. **Windows loadability.** The music-fix README records that dgVoodoo/AppCompat pin the search path to System32
   for winmm; `dsound.dll` is loaded later (module index 43 vs winmm 23, MUSIC.md) so an app-local copy *may* win,
   but this has never been tried. If it does not load, this path is dead on Windows irrespective of its logic.
6. The wrapper only forwards `IDirectSoundBuffer` (DX5 vtable). `QueryInterface` for `IID_IDirectSoundBuffer` on the
   wrapper returns the *unwrapped* object; harmless but it means a QI'd handle bypasses the proxy.

Verdict: the voice record already holds everything the proxy is trying to infer (name, object, player flag, Hz,
volume, mode, keep-alive), one `jmp` away in a DLL the game already loads. Section 4.1 replaces the inference with
a tap; retire dsndrumble rather than fix it.

### 2.2 strlkproxy music path vs the exe's own MCI machinery

Address reconciliation first. The brief names `0x424190` as `sound_UpdateCdAudioStatus`; the map has it at
**0x424550** (`functions/00424550.md`, accepted): `MCI_STATUS` item 4 (MODE) on `[0x4ed890]`, mapped through the
jump table 0x424658 to codes 1 open / 2 stopped / 3 playing / 4 paused / 5 other, stored to `0x524670` only on
change, returns 1 on change. **0x424190** is a different 651-byte function: it reads `0x524674`, issues
`MCI_STATUS` MODE itself (0x4241d8), closes the device on failure (0x4241fd, sets `0x4ed890`=-1, `0x524674`=0) and
then issues `MCI_PLAY` 0x806 with `MCI_FROM|MCI_TO` (0xc) from the TOC table `0x524590[]` (0x424242..0x42426d) --
the "play a run" path that `docs/MUSIC-TRACK-MAP.md` describes at 0x424684. VERIFIED by disassembly.

The poll (`0x423400`, VERIFIED): if `[0x524570]` and `GetTickCount >= [0x524578]`, re-arm +5000 ms when
`[0x524574]` (game state == 6, "in mission") else +60000 ms; call 0x423fb0; if its result is not 1 or 5, and
`[0x52456c]`==0, and the music option byte `[0x654b90] > 1`: call 0x424550; if the mode *changed* and
`[0x4ed800]` != -1: `sound_PlayCdTrack(state6 ? track : 2)` then `jmp 0x424090`.

What the proxy gets right (VERIFIED by reading both sides): `MCI_OPEN_TYPE_ID`, TOC via per-track POSITION, lengths
in the selected TMSF/MSF format, TYPE_TRACK data/audio, the same-track-already-playing guard (the engine re-issues
`MCI_PLAY` for the same track constantly: 116/105/80 times in the field log), track 1 -> silence, MODE answered
from the real `mpegvideo` state so 0x424550 sees genuine transitions.

Where it diverges:

- **(M1) `MCI_TO` is ignored, so the run is not reproduced.** `hook_mciSendCommandA` `case MCI_PLAY` reads only
  `dwFrom` (lines 405-416); the log shows `flags=0xC` = FROM|TO. The exe asks for tracks N..15 (N >= 15: N alone);
  the proxy plays N, then the mpegvideo device stops, 0x424550 sees 3 -> 2 on the next poll (<= 5 s in a mission,
  <= 60 s in menus) and the poll re-issues `MCI_PLAY` for the same N. Result: one song looping with a silent gap of
  up to 5 s (60 s in the office) instead of the album run documented in MUSIC-TRACK-MAP.md. INFERRED from the two
  sources; the gap length would show in `mciproxy.log` as the spacing between `PLAY track N` lines after a track
  ends. The track-map doc's "it DOES loop -- the whole run" is therefore true of the engine and false of this port.
- **(M2) Volume is lost on every track change.** `hook_auxSetVolume` applies `setaudio i76cd volume to N` only
  `if (g_open)` (line 144); `play_track` does `stop_track()` (closes the alias) then `open ... alias i76cd` /
  `play i76cd` with **no `setaudio`** (lines 344-347). The exe calls `auxSetVolume` at init (0x423d50) and when the
  slider moves, not per track, so after the first track change music plays at the mpegvideo default (full) until
  the slider is touched. VERIFIED by source; not yet heard. Trivial fix (P1).
- **(M3) Interaction with the SMACKW32 stop.** `smackproxy` stops the mpegvideo device through its *own* winmm
  import (not the exe's patched IAT), so strlkproxy never learns of it: `g_open`/`g_playingTrack` stay set, and the
  next 0x424550 poll sees 3 -> 2 and restarts the mission track **during the cutscene** (<= 5 s if the state is
  still 6, else <= 60 s). INFERRED; applies only if both proxies are installed on the same copy, which no document
  states for Windows. P3 removes the race.
- **(M4) Cold-start "disc inserted" retry.** `0x524670` starts as the open code (1); the first poll after our
  `MCI_OPEN` returns 2 (stopped), and the 1 -> 2 transition runs `0x4249a0(0x524588)` up to three times with
  `_putch(7)` after each failure (functions/00424550.md). Harmless, but it means the TOC may be read twice at
  mission start; the log's eighteen per-track questions appearing twice would be this. INFERRED.
- **(M5) `MCI_STATUS_CURRENT_TRACK`** returns `g_curTrack` (the last *requested* track) rather than
  `g_playingTrack`; after a data-track request (`track < 2` -> silence) it reports 1 while nothing plays. Cosmetic;
  no reader of CURRENT_TRACK was found in the exe's listing (unverified claim: I did not grep every MCI_STATUS site).

### 2.3 smack-music-fix

Correct in isolation and at the right trigger (VERIFIED by source). On a copy with strlkproxy it is redundant in
principle -- strlkproxy already owns the MCI device -- and, per M3, the two can fight. `mciSendStringA("stop
cdaudio")` with no open `cdaudio` alias returns an error and is harmless. It also relies on `smackorg.dll` being
findable by `LoadLibraryA` from the game dir, which the dgVoodoo search-path hardening noted in the music-fix README
could defeat on Windows; untested.

### 2.4 The per-frame sound gates vs the spec

`frame_sound_wrap` reproduces `sound_StartObjectSound`'s own refresh test exactly: walk `[mgr+0x1c]`, match
`+0x5c == obj`, `_stricmp(+4, name) == 0`, `+0x3c == 2`, where the engine then does `inc byte [+0x74]`
(0x421c58..0x421c8b, VERIFIED). The null-object resolution through `0x457530()` matches 0x421bc4..0x421bd2. One
nuance: the engine resolves `obj == NULL` via the cached `[0x4c2908]` first; the wrapper always calls 0x457530.
Same result. The arg the wrapper names `flag` is a pointer in the engine (0x421b8f dereferences `[arg3+0x10]`);
passing it through unchanged is fine on x86-32. The gates are consistent with `sound.md` "Frame-rate notes".

### 2.5 Call-site census (for section 4.1)

Linear `E8` scan of .text, cross-checked against `functions.json` bodies (VERIFIED, 2026-10-01):
`sound_StartObjectSound` 0x421b40 has 22 direct callers; `sound_PlayVehicleEvent` 0x422f20 has 23 (0x436ff0 vland,
0x438fd0, 0x4515e0, 0x462660, 0x463a80, 0x464890, 0x465370 x4 ignition/engine, 0x466180, 0x4673d0, 0x46aa80,
0x46ac50 x3, 0x46b220 x2, 0x46c8b0, 0x46d590, 0x46f700); `sound_PlayOnObjectSustained` 0x423230 has 9;
`sound_PlayOnObject` 0x4231f0 has 14 (impacts 0x434bb0: vvch2/vvcre2/vvcbb3/vnvco3/vnvcs5/vnvcs3/vnvcs1/vvbo1);
0x4250f0 has 35 (15 in the damage-status HUD 0x45a450, all CWSTAT.WAV); `sound_PlayOneShotAt` 0x4232a0 has 4, all
in 0x4a7190 (weapon fire). Every one of them funnels into 0x421b40, and the DirectSound `Play` happens later in
`sound_StartVoice` 0x4220c0, called from the per-frame update 0x421400 (0x4214e0, args `(voice, 1)`, cdecl, `add
esp,8`) and from 0x422400. Stops go through 0x422d20 (callers 0x4211b0, 0x421a60, 0x422750 x2, 0x422b40, 0x425130 x3).

---------------------------------------------------------------------------------------------------
## 3. Known sound bugs the spec exposes, and whether each is worth a patch

### 3.1 Option value 1 is treated as 0 -- not worth a patch
VERIFIED at six sites: 0x4212dc (channels at init), 0x421391/0x42139e/0x4213a5 (music/SFX/voice at init),
0x421a76 (channels setter), 0x421afa/0x421b01/0x421b08 (`0x421ac0` level setter), 0x424b64 (music ->
`auxSetVolume(level*0xccc)`), plus the gates `cmp byte [0x654b90],1 / jbe` at 0x42344e (poll) and `jbe` at
0x42368a/0x423696 (CB needs voice and channels > 1). It is systematic, so it reads as the shell's slider convention
(1 = "off" notch) rather than an off-by-one; the shell owns the slider (`shell_cb_14..16`, exe-callbacks.md). Scale:
music 0..20 (x0xccc), SFX/voice 0..10 (the "L" in 3.5), channels = number of voices. Document it in MODDING-GUIDE;
do not patch.

### 3.2 Engine pitch is absolute Hz -- worth an opt-in patch if anyone ships higher-rate loops
VERIFIED (raw disassembly of the callback 0x424ca0, which Ghidra does not list as a function): on events 1 and 2,
`fld [engine+0x1c]` (rpm); `fsub [0x4bccf8]` (1050); `fmul [0x4bccfc]` (1/4950); `fmul [0x4bcd00]` (8268.75);
`fsub [0x4bcd04]` (-8268.75); `fstp [voice+0x18]`; and `or [voice+0x14],0x160`. The sample rate at `voice+0x48`
is never read. The callback pointer is stored at exactly two sites, both `b8 a0 4c 42 00`: **0x424c2f**
(`sound_CreateEngineLoop`) and **0x424d7d** (the event-1 restart 0x424d20). With a 44.1 kHz loop the game would
`SetFrequency(8268)` at idle, i.e. play it 5.3x slow; with 22.05 kHz, 2.7x slow. Stock loops are all 11025 Hz mono
(FORMATS-tables.md), so stock play is unaffected -- this bites only modders. The loader already accepts a plain
`.wav` when no `.gpw` exists (0x425130, terrain-text-sound.md section 2), so higher-rate replacements are otherwise
viable. Patch P5.

### 3.3 The 600 m cull is measured from the player car, not the camera -- low priority, opt-in
VERIFIED: 0x421bd2 `mov esi,[eax]` with `eax=[0x4c2908]` (player object), position deltas `fsub qword [esi+0x40/
0x48/0x50]`, `fcomp qword [0x4bccf0]` (360000.0) at 0x421c35 refuses a start; the same compare at 0x422bf1 parks a
running voice. The listener is the camera eye `[0x4c2890]` (0x42249d) with the player car's velocity (0x422498
`call 0x461e20`). So in a scripted cut-scene camera more than 600 m from the car, sounds near the camera are
refused and sounds near the car are at DirectSound's floor (max distance 400 m, rolloff 1: gain = 10/400 = -32 dB,
never silent). INFERRED consequence: near-silence with a faint, Doppler-shifted car. Only FSM cameras reach this;
cockpit/chase never do. Patch P6 is cheap (two 6-byte operand repoints) but the benefit is cut-scenes only.

### 3.4 Per-frame retriggers -- fixed
Lock tones, radar ping, tyre/surface/flat/damage: gated in strlkproxy (section 2.4). Remaining per-frame sites not
gated: none found in `sound.md`; the CWSTAT.WAV status chirps (0x45a450, 15 sites) fire on component state changes,
not per frame (INFERRED from the `_off` string pairs; not traced).

### 3.5 Other findings from sound.md and the listings
- **Volume law and default balance.** 0x42182f..0x421854: millibel = `T[trunc(vol% x 0.1 x L)]`, `T[i] = 400 x
  log2(i/100)` (-4 dB per halving, gentler than amplitude's -6 dB), L = SFX level `[mgr+0x14]` or voice level
  `[mgr+0x18]` for flag 4. I76PLYR.DEF defaults are music 3, SFX **4**, voice **10**, channels 8. So at defaults a
  100% effect sits at `T[40]` = -529 mB (-5.3 dB) while a CB line (flags 5, voice level) sits at `T[100]` = 0 dB and
  plays 2D at priority 10000 (0x42383f/0x423837). The engine loop plays at GAS volume 100 (eimarx 60) every frame
  with no rpm or throttle term (0x4215cc). INFERRED: the "CB louder than everything" impression is the defaults,
  and the in-game sliders already fix it. **I found no written complaint about CB-vs-engine balance in this repo**
  (grep of docs/ for loud/quiet/drown/balance/hear: nothing sound-related). So a mix patch is an opportunity (4.2),
  not a bug fix.
- **Random pitch per frame is dead code.** 0x4215e0: if `[voice+0x44] == 2` the per-frame update re-rolls
  `rand()%10` every frame (0x4215e6..0x421606). The corpus value is always -1 -> default 0, so no stock sound uses
  it; a modder setting the GAS random-pitch field to 2 would get a warbling sound. Note for MODDING-GUIDE.
- **Listener velocity under world cameras.** The listener's velocity is always the player car's (0x422498), so a
  static script camera has a moving listener: Doppler (factor 0.8, 0x421261) on approaching objects is wrong in
  cut-scenes. INFERRED; small; P7 lists an optional zeroing.
- **CB STOPCB latch.** `STOPCBXX` sets `0x524580` and is cleared only by `sound_SetCbEnabled(1)` at mission load;
  after it, a speaker's death `cmike.wav` (prio 2) is rejected so the line plays to its end (sound.md). Authored
  behaviour; not a bug.
- **`vskid.wav` events 10/11 have no caller** (sound.md). Dead feature; nothing to do.
- **400..600 m band.** Between DirectSound's 400 m max distance and the 600 m cull every voice sits at the same
  -32 dB floor; then it is cut. Audible as a step only for loops that drive away (AI engine loops). Cosmetic.

---------------------------------------------------------------------------------------------------
## 4. Opportunities

### 4.1 An event tap in strlkproxy instead of inferring from DirectSound buffers (PROPOSED)
Tap `sound_StartVoice` 0x4220c0 (the moment a voice actually starts or is un-parked: `voice` arg, cdecl) and
`sound_StopVoice` 0x422d20 (`voice, reason`), not the request wrappers: one start event per audible start, one stop
per loop end, regardless of which of the 22+23+9+14+35+4 request sites asked. From the voice record publish
`{name = voice+4, obj = voice+0x5c, is_player = (obj == *0x457530()) or (0x458c90(obj)+0x10 & 0x10), pos =
0x458d60(obj) (3 floats, as 0x421bde does), hz = voice+0x18, vol = voice+0x1c, mode = voice+0x3c, prio =
voice+0x34, t = g_frame}` as a key=value UDP datagram to `127.0.0.1:17677` (next to the ffb-shim's 17676 so
`tools/ffb-udp-listen.py` and `tools/ffb/FfbMixer.ps1`/`LfeSynth.ps1` can consume both). Distance to the camera
is for the consumer: it already reads the player entity. Both prologues are relocatable (section 5, P4), and the
proxy already has the 6-byte-trampoline pattern (`g_cam_tramp` for 0x472990). This gives the LFE layer named
events with ownership and position, which dsndrumble can never have, and makes `rumble-fingerprints.ini`
unnecessary (envelopes stay useful as textures).

### 4.2 Mix: per-name volume table and documented defaults (PROPOSED)
`sound_LoadSample` 0x425130 fills `voice+0x30..+0x48` from the GAS header (volume at +0x40; 0x4215cc re-reads it
every frame, so a load-time override sticks). Wrap the one `call 0x425130` at 0x421d08 (bytes `e8 23 34 00 00`) to
scale `+0x40` by an INI entry keyed on `voice+4` (e.g. `eimarx=60`, `cmike=80`), under `I76_SOUND_MIX=<file>`.
No engine arithmetic changes. Independently, record in MODDING-GUIDE that SFX 4 / voice 10 are the stock defaults
and what the -4 dB/halving table does; most "balance" complaints are a slider away.

### 4.3 Higher sample-rate audio
Music already plays at the MP3s' native rate through `mpegvideo`; nothing to raise. If a user has a lossless rip,
`play_track` could prefer `music\N.wav`/`N.flac` when present (mpegvideo plays WAV; FLAC needs a codec) -- a
four-line change, no engine impact. Effects: `.wav` replacements at 22.05/44.1 kHz load (section 3.2) and play at
their own rate for every non-engine sound; the engine loops need P5 first. Note `gpw-fingerprints.py` and
dsndrumble break on any replaced sound (content hash), another reason to prefer 4.1.

### 4.4 Open items from the music-fix README, triaged
- "Not yet observed: MCI_PLAY" -- closed 2026-08-08 (MUSIC.md log). Delete.
- "Known limitation: aux volume no-op" -- closed by the aux trio; but see M2 (volume not re-applied per track).
- "Building the aux change: needs 32-bit gcc" -- stale: MUSIC.md records the x86 `cl.exe` route via `vswhere`.
- `MUSIC-TRACK-MAP.md` "experiment": the live log (`MCI_PLAY ... -> track 13` then `track 2`) is consistent with
  the WRLD table (a mission starting at 13 = M13, then the office falling back to 2) but does not name the mission;
  one line of `mlog` with the current mission name next to `PLAY track N` would settle the table without ears.

---------------------------------------------------------------------------------------------------
## 5. Prioritised change list (everything here is PROPOSED)

Verification for every exe patch: `patch_bytes` compares the listed old bytes before writing and the log line reads
back the site (`verify-the-write-landed`); run on the sandbox copy, never the playable install.

| # | change | file / function | patch site and bytes to expect (pristine md5 9a232dcc) | live verification | risk |
|---|---|---|---|---|---|
| **P1** | Re-apply music volume after each `open` | `music-fix/strlkproxy.c` `play_track` | none (C only): after `open ... alias i76cd` issue `setaudio i76cd volume to g_volume` | `I76MUSIC_LOG=1`: a `str ok: setaudio` line follows every `PLAY track N`; move the slider, change mission, music level follows | nil |
| **P2** | Honour `MCI_TO`: play the run N..dwTo as the engine asks, advancing to the next `music\N.mp3` when `status i76cd mode` leaves `playing`; answer MODE = PLAY across the whole run, CURRENT_TRACK = the file playing; the same-run guard keys on (from, to) | `strlkproxy.c` `hook_mciSendCommandA` MCI_PLAY, `playing_now`, new `advance_run()` polled from the existing frame hook or on each MCI_STATUS | none (C only) | log shows `PLAY track 9` then `advance -> 10 ... 14`, then a STOP transition and the engine's re-issued `MCI_PLAY` for 9 (M01); gap between tracks < 1 s; no 5 s silences | low: more MCI string traffic at track boundaries; keep the data-track rule |
| **P3** | Movie coordination: hook i76.exe's `SMACKW32.DLL` import ordinal 14 (`_SmackOpen@12`) and 18 (`_SmackClose@4`) in strlkproxy; on open `stop_track()` and set `g_movie`; while `g_movie` answer MODE = PLAY so 0x423400/0x424550 do not restart; on close clear it | `strlkproxy.c` DllMain (`patch_iat` needs an ordinal variant: `IMAGE_ORDINAL_FLAG32`) | IAT slot (data), no code bytes | play a mission into its cut-scene: log shows `SmackOpen -> stop`, no `PLAY track` until `SmackClose`; music resumes on the engine's own next `MCI_PLAY` | low; makes smack-music-fix redundant on Windows |
| **P4** | Event tap (4.1), opt-in `I76_SOUND_EVENTS=1` | `strlkproxy.c`: `start_voice_hook(voice, k)` and `stop_voice_hook(voice, reason)` with 6- and 5-byte trampolines | 0x4220c0: `a1 e8 d7 4e 00 53` (`mov eax,[0x4ed7e8]; push ebx`) -> `e9 rel32 90`, trampoline runs the 6 bytes then `jmp 0x4220c6`. 0x422d20: `56 8b 74 24 08` (`push esi; mov esi,[esp+8]`) -> `e9 rel32`, trampoline then `jmp 0x422d25`. Both cdecl: 0x4220c0 is called `(voice, 1)` with `add esp,8` at 0x4214e5; 0x422d20 `(voice, 0x20)` at 0x4212fe | `tools/ffb-udp-listen.py --port 17677 --raw` while driving: one `start` per audible effect with `player=1` for your own and `player=0` for AI cars, `stop` when a skid loop ends; counts should match the ring's voice list | medium: a trampoline in the hottest sound function; the 5-byte 0x422d20 prologue reads `[esp+8]` after `push esi`, which the trampoline preserves because it is entered by `jmp` from the detour, not `call` -- keep the wrapper naked or re-push args exactly as the existing `cam_set_hook` does |
| **P5** | Engine pitch scaled by sample rate, opt-in `I76_FIX_ENGINE_PITCH_RATE=1`: proxy callback = 0x424ca0's logic with `f = rate x (0.75 + 0.75 x (rpm-1050)/4950)`, `rate = voice+0x48` (11025 reproduces the stock numbers exactly) | `strlkproxy.c` `engine_pitch_cb(voice, event)` (cdecl, 2 args, returns `voice != 0` on event 2 as 0x424d07 does; event 3 -> 0; keeps `or [voice+0x14],0x160` and the health byte copy `[voice+0x76] = [engine+8]`) | **0x424c2f** `b8 a0 4c 42 00` and **0x424d7d** `b8 a0 4c 42 00` -> `b8 <cb>` | stock loops: `voice+0x18` reads 8268.75 at idle as before (debug ring); drop a 22050 Hz `eimarx.wav` into `addon\` and listen: correct pitch instead of half speed | low: two immediates; the callback must mirror 0x424ca0's early-outs (`0x467440(obj)` null -> `0x421e70(voice)` stop) |
| **P6** | Cull relative to the camera under script/world cameras: repoint the 360000.0 operand at both cull sites to a proxy double set each frame (360000 for cockpit 0x406ab0 / chase 0x407ad0 / free-look, 1e12 otherwise), opt-in `I76_CULL_FROM_CAMERA=1` | `strlkproxy.c` frame hook (camera mode already known to `apply_render_interp`) | 0x421c35 `dc 1d f0 cc 4b 00` and 0x422bf1 `dc 1d f0 cc 4b 00` (`fcomp qword [0x4bccf0]`) -> `dc 1d <addr of g_cull_d2>` | a mission with a far FSM camera (jump/cut-scene): sounds near the camera are heard; count admitted voices via `[mgr+0x1c]` in the ring | low-medium: more voices admitted under world cameras; priority stealing (0x422750) still caps at the channels option |
| **P7** | Listener velocity zero under world cameras | `strlkproxy.c` | 0x422498 `e8 83 f9 03 00` (`call 0x461e20`) -> wrapper returning (0,0,0) when the camera is not cockpit/chase | hard to hear; skip unless P6 lands and cut-scenes sound odd | low |
| **P8** | Per-name volume table (4.2), opt-in `I76_SOUND_MIX=<ini>` | `strlkproxy.c` wrapper around `sound_LoadSample` | 0x421d08 `e8 23 34 00 00` (`call 0x425130`) -> `e8 <wrap>`; wrapper calls 0x425130 then scales `voice+0x40` by the entry for `voice+4` | ring: `voice+0x1c` and the `SetVolume` argument change for the named sound only | low |
| **P9** | Retire `sound-rumble/` (mark README "superseded by the event tap") and remove `motor_of`'s `e*` heavy mapping if it is kept for Mac | `sound-rumble/README.md`, `dsndrumble.c` | none | n/a | nil |
| **P10** | Docs: delete the three stale README sections (4.4), fix `i76-music.ps1`'s header claims, record the SFX 4 / voice 10 defaults and the 1 == 0 convention in MODDING-GUIDE, add `winmm_proxy.c` to the tree or delete the binaries (`tools/winmm-cdaudio/` is untracked binaries only) | `music-fix/README.md`, `tools/i76-music.ps1`, `docs/MODDING-GUIDE.md`, `docs/MUSIC.md` | none | n/a | nil |

Ordering rationale: P1-P3 are correctness fixes in C with no exe bytes and a log-only test; P4 unblocks the rumble
and LFE work the repo keeps circling (ffb-shim, dsndrumble and the PowerShell telemetry are three attempts at the
same signal); P5 and P6 are real engine bugs that no stock player hits; P7-P8 are polish.
