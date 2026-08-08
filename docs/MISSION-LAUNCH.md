# Booting straight into a mission

**Working 2026-08-08.** Set one environment variable and the game skips the title
screen, the menus and the mission select, and drops you into a named mission:

```powershell
$env:I76_MISSION = "t01.msn"      # the training mission
$env:I76_SKIP_MOVIES = "1"        # optional, testing convenience
.\i76.exe -glide
```

Measured: **in the mission 10 seconds after launch**, player entity resolved.

This exists because testing anything that only happens in a mission — music,
force feedback, telemetry offsets, handling — otherwise costs a minute of
clicking through menus per iteration, done by hand, every time.

## The command line cannot do this

Worth stating plainly, because it is the first thing anyone tries. `i76.exe`
parses its command line for renderer and debug switches only. There is **no
argument that names a mission**; the string is never routed to the mission
loader. This was checked in the disassembly, not assumed.

The mechanism below is therefore a patch, not a supported flag.

## How it works

The engine keeps the mission name in a fixed buffer and clears it twice on the
way to the menu. Write the name and stop both clears, and the mission loader
finds a mission waiting for it.

| address | stock bytes | what it is | what we do |
|---|---|---|---|
| `0x005049f0` | — | 16-byte mission-name buffer | write the name (`t01.msn`) |
| `0x00402d33` | `88 0D F0 49 50 00` | `mov [0x5049f0], cl` — pre-parse clear | 6 × `NOP` |
| `0x0049d1e0` | `C6 00 00` | `mov byte [eax], 0` — parser clear | 3 × `NOP` |

Implemented in [`music-fix/strlkproxy.c`](../music-fix/strlkproxy.c)
(`apply_mission_launch`), which runs from `DllMain` — **before the exe's entry
point**, and so before anything reads the buffer.

Both patches verify the stock bytes before writing. If either does not match the
patch is abandoned and the game boots to the menu as normal, logging:

```
mission-launch ABORTED (n/2 patches applied) - booting to the menu
```

That matters because these addresses are correct for **this** build of `i76.exe`;
on a different build they would land in the middle of unrelated code, and a
silent partial patch is far worse than no patch.

## Skipping the intro movies, and the wrong way to do it

`I76_SKIP_MOVIES=1`. The intro (`introf01.smk`) and credits (`credf01.smk`) play
before the mission parser is ever reached, so an automated run spends a minute or
two watching them.

**The first attempt broke the game**, and the failure is instructive. The engine
skips a movie whose open fails:

```
0x403056  test eax,eax
0x403058  je 0x4030e0        ; open failed -> skip ahead
```

Making that jump unconditional (`0F 84` → `90 E9`) also takes it after a
*successful* open — leaving the movie subsystem half-initialised with a handle
never closed. The game then hung on the loading screen, which reached the field
as *"stuck on please stand by, no menu, no movie, no game"*.

The fix is to make the open genuinely fail, which is a path the engine already
handles: corrupt the first byte of each filename in the string table
(`0x4c25b0` → `X`, `0x4c25a4` → `X`) so the file cannot be found. Same outcome,
entirely inside behaviour the engine was written to expect.

**The general lesson**: to skip something, prefer driving the engine down a
failure path it already implements over jumping around its code. The engine
cleans up after its own failures; it does not clean up after ours.

## Mission names

`t01.msn` is the training mission. Campaign missions follow the same pattern in
the game folder; the parser takes the bare filename, 15 characters at most.

## Verifying it worked

The log (`I76MUSIC_LOG=1`, written to `mciproxy.log`) reports the attempt:

```
mission-launch: booting directly into 't01.msn'
```

To confirm the game actually got there rather than merely trying, read the player
entity through the telemetry chain in
[`tools/ffb/Telemetry.ps1`](../tools/ffb/Telemetry.ps1) — it resolves only in a
mission, which is what the 10-second measurement above is.

## A caution about testing this

Every earlier attempt to verify this mechanism was run over **Remote Desktop**,
where the game cannot initialise 3D and hangs before reaching any of it. The
conclusion recorded at the time — "the parser at `0x4b42b0` never runs" — was an
artefact of that and was wrong. See the RDP section in
[AGENTS.md](../AGENTS.md); check the session type before trusting any launch
result.
