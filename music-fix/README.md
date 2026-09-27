# In-mission music fix (base game) — a Strlkup.dll IAT hook

Restores Interstate '76's in-mission soundtrack on a machine with **no optical
drive** (i.e. most modern laptops), and kills the "Please insert CD 2" prompt.

## The problem

The base game plays its soundtrack as **CD audio through MCI** — it opens the
`cdaudio` device with `mciSendCommandA` and plays track N. GOG ships those tracks
as `music\N.mp3`, but with no CD drive the MCI `cdaudio` device won't open
(`MCIERR_CANNOT_LOAD_DRIVER`, 266), so there's no music and the game asks for the
disc. (The **Nitro Pack is unaffected** — it plays music through `audiere.dll`,
not MCI, which is why its music already works.)

## Why not just a winmm.dll proxy

The obvious fix — drop a `winmm.dll` next to the game — **does not work here**:
dgVoodoo hardens the process's DLL search path to `System32`, so the game binds
`mciSendCommandA` to the real `SysWOW64\winmm.dll` before an app-directory
`winmm.dll` can load. Verified with a module lister; DotLocal (`i76.exe.local`)
didn't override it either.

## How this works

`Strlkup.dll` is a tiny 5-export helper that **i76.exe imports statically**, so it
loads at process init. We proxy it: all five exports are forwarded to the renamed
original (`strlkup_orig.dll`), and in `DllMain` we rewrite i76.exe's Import Address
Table slot for `WINMM.dll!mciSendCommandA` to point at our own function. The loader
has already snapped that slot to the real winmm before any `DllMain` runs, and the
game doesn't call it until a mission starts, so the overwrite always wins.

Our hook emulates the `cdaudio` device:

- `MCI_OPEN "cdaudio"` → succeeds against a virtual device id.
- `MCI_PLAY` track N → plays `music\N.mp3` via the **mpegvideo** MCI device (which
  works fine with no CD). Track N maps directly to `music\N.mp3` (track 1 was the
  data track — there is no `1.mp3`).
- `MCI_STATUS … MEDIA_PRESENT` → reports a disc present, so the CD prompt never fires.
- Everything non-cdaudio is passed straight through to the real winmm.

## Deploy / revert

`setup-windows.ps1` deploys it automatically for the base game: it backs up the
original as `strlkup_orig.dll` and drops the proxy in as `Strlkup.dll`.

- **Revert:** restore `strlkup_orig.dll` over `Strlkup.dll` (delete the proxy,
  rename the backup back).
- **Diagnose:** set the environment variable `I76MUSIC_LOG=1` before launching to
  write `mciproxy.log` in the game folder — it records the IAT patch and every
  cdaudio MCI call (open / play / track number / status), which is the thing to
  read if music misbehaves.

## Build

A prebuilt 32-bit `Strlkup.dll` is committed here (it's our own code — it forwards
to the GOG `strlkup_orig.dll` by name, so it works on any GOG install). To rebuild
after editing `strlkproxy.c`, run `build.ps1` (needs w64devkit's 32-bit gcc).

## 2026-08-04: THREE bugs, found by logging every call

The hook had been installed and deployed for days while doing nothing. Making the
log record **every** call — not just cdaudio ones — turned "no music" into three
specific, sequential bugs. Each one was invisible behind the previous.

**1. `MCI_OPEN_TYPE_ID` was explicitly rejected.** `wants_cdaudio()` began:

```c
if (!(flags & MCI_OPEN_TYPE) || !p || (flags & MCI_OPEN_TYPE_ID)) return 0;
```

and the log showed the game opening five times with `flags 0x3000` =
`MCI_OPEN_TYPE | MCI_OPEN_TYPE_ID` — the *only* form it ever uses. The hook refused
the exact call it exists to catch. With `TYPE_ID` set, `lpstrDeviceType` is not a
string but an integer device id, so a string compare can never match and
dereferencing it would be a wild read — presumably why the original bailed rather
than risk it. Correct handling is to compare the low word against
`MCI_DEVTYPE_CD_AUDIO`.

**2. Per-track status answered `0`.** After the open worked, the log showed the game
asking eighteen per-track questions (`flags 0x110` = `MCI_STATUS_ITEM | MCI_TRACK`)
and then never playing. The handler's `default: dwReturn = 0` told it every track was
type 0 and length 0 — an empty disc. **Answering `MCI_OPEN` is necessary but nowhere
near sufficient: the engine validates the disc before touching it.**

**3. `MCI_STATUS_POSITION` + `MCI_TRACK` is a TOC query, not "where is playback".**
It asks *where track N starts on the disc*, and the engine derives each track's
length from consecutive starts. Returning the playback position (0 while stopped)
made all sixteen tracks zero-length. Now it returns cumulative start offsets, and
the values check out against the format the game selects — `MCI_FORMAT_TMSF`, packed
`track | m<<8 | s<<16 | f<<24`. Track 4 starts at 229896 ms → m3 s49 f67 →
`1127285508`, exactly what the game is handed. (Worth noting because in decimal those
TOC values look like garbage and are not.)

### Confirmed working

The engine's own state, before and after (addresses from
[MEMORY-MAP-INDEX.md](../docs/MEMORY-MAP-INDEX.md) Tier 1):

| | before | after |
|---|---|---|
| `0x524674` music-active flag | `0` | **`1`** |
| `0x4ed890` MCI device handle | `0xFFFFFFFF` | **`0x0000C0DE`** |
| `0x4ed894` aux-volume device | `0xFFFFFFFF` | `0x00000000` |

`0xC0DE` is `FAKE_CD_ID` — the engine stored our virtual device's handle. It opens
the device, sets `TMSF`, reads the full TOC for tracks 1..17, queries our fake
`AUXCAPS_CDAUDIO` aux device, and sets volume (so the in-game music slider now
works: `auxSetVolume(0xB337B337) -> 700/1000`).

**Not yet observed: `MCI_PLAY`.** Every test above was at the title/menu, and the
base game plays its soundtrack in missions. Load one with `I76MUSIC_LOG=1` (the
launcher sets it) and the log will show either `MCI_PLAY … -> track N`, which is
done, or another status query answered wrongly — in which case the log names it.

## Earlier finding: the hook was installed and NEVER CALLED

With `I76MUSIC_LOG=1`, `mciproxy.log` after a full session read exactly one line:

```
--- strlkproxy: IAT patch mciSendCommandA old=75511840 new=73ff16c0 ---
```

The patch lands. Then nothing — no `MCI_OPEN`, no `MCI_PLAY`, in a mission or
anywhere else. **The game is not failing at CD audio, it is declining to attempt
it**, so hooking `mciSendCommandA` alone cannot be enough.

The cause is almost certainly the **aux gate**. The game imports
`auxGetNumDevs` / `auxGetDevCapsA` / `auxSetVolume`, and on a machine with no
optical drive the real `auxGetNumDevs()` returns **0** (measured). On 90s hardware
CD audio was mixed in *analogue* and its level set through an `aux` device, so "no
aux device" meant "no CD audio present" — and the engine checks that before it ever
opens the MCI device.

`strlkproxy.c` now also hooks those three, advertising exactly one
`AUXCAPS_CDAUDIO` aux device **when the system has none** (so a machine with real
aux hardware is untouched), and translating `auxSetVolume` to
`setaudio <alias> volume to N` — which also fixes the volume limitation below.

**This is written but NOT YET BUILT OR CONFIRMED.** See the build note.

## Building the aux change: needs 32-bit gcc

The committed `Strlkup.dll` predates the aux hooks. Rebuilding needs a **32-bit
gcc** (w64devkit), which is not installed here.

**MSVC cannot substitute, despite being available.** The five exports are
*forwarders* to `strlkup_orig.dll`, and `link.exe` refuses to emit them from either
form:

```
strlkup.def : error LNK2001: unresolved external symbol StrLookupCreate   (.def forwarder syntax)
LINK        : error LNK2001: unresolved external symbol StrLookupCreate   (/EXPORT:name=strlkup_orig.name)
```

It insists the symbols exist locally rather than treating a dotted target as a
forward. gcc/dlltool reads the `.def` correctly, which is why the original was built
that way.

Two ways forward, neither started:

1. **Install w64devkit** (portable, no installer) and run `build.ps1` — it prefers
   gcc and only falls back to MSVC.
2. **Drop linker forwarders entirely**: implement the five exports as
   `__declspec(naked)` stubs that `jmp` to `GetProcAddress(strlkup_orig, …)`. On x86
   a plain jump preserves the stack frame for any calling convention and any
   argument list, so the signatures never need to be known. `StrLookup_Global_Object`
   is DATA and would need separate handling.

`build.ps1` is now **non-destructive** — it builds to `Strlkup.build.dll`, verifies
the architecture, and only then replaces `Strlkup.dll`. It previously built straight
over the committed, deployed binary and destroyed it on each failure.

## Known limitation

The game sets music volume via `auxSetVolume` on the aux device; with no aux
device that's a no-op, so it can't attenuate our mpegvideo playback — music plays
at the mpegvideo device's volume. If it's too loud, a follow-up is to also hook
`auxSetVolume` and translate it to `setaudio <alias> volume to …` on the mpegvideo
alias. (Left out for now: get music playing first.)

## Opt-in: high-resolution sim clock (`I76_HIRES_CLOCK=1`, 2026-09-26)

Not music, but this DLL is the one hook point every install already loads. The whole simulation is dt-driven:
`simclock_Update` (0x49c920) reads `GetTickCount` once per frame, and physics runs in substeps of at most 50 ms
derived from that dt (i76-map batch `simclock-stepper`). `GetTickCount` steps in 15–16 ms no matter what
`timeBeginPeriod` says (measured on this machine), so at 20 fps dt reads 47 or 63 ms, and at 60 fps most frames read
0 (clamped to 1 ms) or 15.6 ms. The 2017 Galaxy exe also stores seconds-since-boot as a 32-bit float, so dt snaps to
a 62.5 ms grid after 7 days of uptime. GOG's 2019 AiO build fixes that second problem by masking the tick; nothing
fixes the first.

With `I76_HIRES_CLOCK=1` set, DllMain repoints only simclock's two `call [GetTickCount]` sites at a
QueryPerformanceCounter clock (ms since process start). It supports both layouts: Galaxy 0x49c85f/0x49c929 and
AiO 0x49c85d/0x49c927. Each site's bytes are verified before writing, so any other build is left alone.

**Status:** the write was verified in the sandbox (2/2 sites read back as `call [ptr] -> hires_clock_ms`, log line
`hires-clock: 2/2`). It has **not** been played yet. Next console test: the same mission with and without the flag, at
20 and at 40–60 fps. Compare how smooth it feels and the dt at 0x4fe428 (it should read about 50 ms steadily instead
of 47/63).

## Opt-in: frame-rate-independent engine response (`I76_ENGINE_DT_FIX=1`, 2026-09-26)

The engine/gearbox update 0x46a320 (i76-map `physics_UpdateEngine`) runs once per physics substep but smooths RPM and
torque with the **whole frame's** dt. At 20 fps a frame has two substeps, so the engine responds about twice as fast per
second as at 60 fps, and GetTickCount jitter flips it between one and two substeps even at 20 fps. The flag repoints
that one `call simclock_GetDt` (0x46a333, the same bytes in the Galaxy and AiO builds) at a function returning
2 × sim_dt / substep count. That reproduces the two-substep (20 fps) response at any frame rate.

**Status:** the write was verified in the sandbox together with `I76_HIRES_CLOCK` (`engine-dt-fix: 1/1`). It has not
been played. Test at 60 fps with and without it: time the throttle from standstill to 100 km/h in the same car.

## Playing above 20 fps: the recommended switch set (2026-09-27)

Measured in the sandbox (i76-map `captures/014-framerate`). All of these are off unless their variable is set.

| variable | fixes | evidence |
|---|---|---|
| `I76_HIRES_CLOCK=1` | jittery dt: 15.6 ms GetTickCount steps and float32 uptime decay | dt exact (50.00 ms at 20 fps, 16/17 ms at 60 fps) |
| `I76_FIXED_STEP=24` | chassis/cockpit buzz, jump behaviour: physics always steps in 41.7 ms slices, the mean step of stock play at 20 fps | stock 20 fps actually steps 46.9 ms (80%) / 31.2 ms (GetTickCount frame dts split by the stepper); 24 Hz body motion as calm as stock 20 (at rest 0.83-0.86 in 3 of 4 runs vs 0.45-0.84), acceleration unchanged. The first choice, 40 (25 ms), made jumps fall short and the body feel quick in play |
| `I76_FRAMERATE_FIXES=1` | sky drift, free-look camera keys, zoom key, keyboard throttle ramp, missile-lock tones, radar lock ping (locked on it pinged every frame: 60/s at 60 fps; coalesced to 20/s as at 20 fps), per-frame vehicle sounds, AI throttle and steering gains, flamers (stream ageing on the 20 Hz grid, stock-20 shape, damage 20 times a second from the main pass only: stock applied it per rendered frame, and again in the rear-mirror pass), smoke puffs (updated on the 20 Hz grid, drawn smoothly in between), missile-trail fade | clouds 0.0300 /s at 60 fps = 20 fps (stock 0.0899); sky, free-look confirmed in play; smoke puffs age 19.1 steps/s at 60 fps (stock 57.8; stock 20 fps: 20), i76-map capture 014 `smoke_*.json`; flamers not yet checked in play |
| `I76_ENGINE_DT_FIX=1` | engine RPM/torque smoothing counted per substep | static; consistent with the fixed step |
| `I76_RENDER_INTERP=1` | the 40 Hz judder the fixed step leaves at 60 fps: vehicles and the cockpit/chase camera are drawn between their last two physics poses | every frame: 31-33% of frames without motion -> 0%, roughness 1.00 -> 0.04-0.06 (n = 2 missions) |
| `I76_FPS_CAP=n` | optional precise frame cap (dgVoodoo's FPSLimit did not cap this build) | held 20.0 fps exactly |

```powershell
$env:I76_HIRES_CLOCK = "1"; $env:I76_FIXED_STEP = "24"; $env:I76_FRAMERATE_FIXES = "1"; $env:I76_ENGINE_DT_FIX = "1"; $env:I76_RENDER_INTERP = "1"
```

In the sandbox, `i76-uncap-lab\TEST-FRAMERATE.bat` runs this set, the same set without interpolation, stock 60 fps and
stock 20 fps, and restores the sandbox afterwards.

AI throttle chatter at 60 fps: 26.2 (stock) vs 1.56 at 20 fps. `I76_HIRES_CLOCK` alone brings it to 9.0, and adding
the fixed step to 5.3 (n = 3 each, still above 20 fps). With the fixed step alone, the physics advances on two
frames out of three at 60 fps (40 Hz), which shows as judder; `I76_RENDER_INTERP` removes it. Nothing here is deployed
to the playable install.

## Opt-in: render interpolation (`I76_RENDER_INTERP=1`, needs `I76_FIXED_STEP`, 2026-09-27)

Each object's pose is a 0x40-byte transform at object+0x18: a 3x3 float rotation (rows = right, up, forward) and
three position doubles. The physics writes it directly, so there is no separate render copy to interpolate. The proxy
therefore swaps an interpolated pose in around the render call and restores the physics pose right after; the
simulation never sees it.

- **Vehicle tick.** Class table slot 0x4f7788 (type 1, `entity_TickVehicle`) points at a wrapper that keeps each
  vehicle's pose from before its last 25 ms step.
- **Render.** The `call 0x401c90` at 0x403e69 (render(&camera)) is wrapped. Each vehicle ticked this frame, and still
  in the live-object list, is drawn at `lerp(previous, current, leftover / step)`. The rotation is re-orthonormalised.
  Display latency is one physics step (0.25-0.34 m at 17-30 m/s).
- **Camera.** The camera mode runs once per frame from the frame loop (`call [0x4c2720]` at 0x403e16, and on one
  path from inside the player's tick at 0x46391f). Both calls are wrapped so the mode runs with the player at its
  drawn pose, which is what a lagging chase camera needs. The first version moved the finished camera rigidly with
  the player instead; that was exact for the cockpit (1.317 m ± 0.0000 from the drawn car) but left the chase car
  wobbling against the camera, reported in play. Measured on the chase camera: car-vs-camera jerk median
  0.029 -> 0.002 m/frame^2, 95th percentile 0.34 -> 0.005. The rigid carry (via a detour of SetTransform 0x472990)
  remains as a fallback for a frame whose camera was set some other way; script cameras (`fsm_Cam*`) are left alone.
- **Guards.** A vehicle that moved more than 8 m in one step (respawn or teleport) is drawn without blending. So is one
  ticked without the fixed stepper.

The log line `render-interp: 3/3 hooks, on (debug block XXXXXXXX)` gives the address of a debug block. It holds a
16-frame ring of true and drawn positions, which `captures/014-framerate/fr_probe.py --interp` and `interp.py` read.

**Script and world cameras** (second play test: the car jittered under the jump camera and in cut-scenes).
- The FSM camera actions that `fsm_ActionDispatch` calls (0x413118..0x413327) run with every car on its drawn pose,
  and so does the frame-loop camera update.
- World cameras (anything but cockpit 0x406ab0, chase 0x407ad0 and free-look) draw cars on a quadratic B-spline
  through the last three physics poses, not the linear blend. The physics path weaves by up to 16° per step, and
  straight segments showed a kink every 41.7 ms. Per-frame direction change p95 went 23.5° -> 11.2°, for about half a
  step more lag, only in those views.
- `I76_INTERP_SMOOTH=0` turns the spline off; `=2` uses it everywhere.

**Exact frame dt.** With `I76_HIRES_CLOCK` the frame hook replaces the whole-millisecond dt (16/17 ms at 60 fps) with
the exact QPC interval, offline only.

**Engine dt with the fixed step.** `I76_ENGINE_DT_FIX` hands the engine 0.05 s per substep when the fixed step is
on, which is what stock at 20 fps does (every substep sees the whole ~50 ms frame).

**Saving.** Play the sandbox through `i76.exe`, not `i76_pristine_fix.exe`: only `i76.exe` imports `u32x.dll`
(save-screen mouse translation, ghosting fix), and saves failed in the first test session because the launcher
used the other exe.

**Not yet covered.** Things spawned at the true pose during the sim can sit up to one step ahead of the drawn car:
muzzle flashes, projectiles, smoke. Wheel/suspension animation follows the body but is not interpolated itself. AI cars
are interpolated, but only the player's poses have been measured. Multiplayer is untested.
