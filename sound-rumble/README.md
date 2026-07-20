# sound-rumble — gamepad rumble from the sounds the game actually plays

The **backup** rumble path (the primary one is the force-feedback-data shim in
[`../ffb-shim/`](../ffb-shim/), which is what's on by default). This one drives
the pad from the game's **real audio playback** instead of its physics stream.

## How it works

The game plays every effect through DirectSound: create a secondary buffer,
`Lock` it, write the `.gpw` PCM, `Unlock`, `Play`. This is a proxy `dsound.dll`
that sits in front of the real one and wraps `IDirectSound`/`IDirectSoundBuffer`:

1. on `Unlock`, it **fingerprints** the PCM the game just wrote (FNV-1a over the
   bytes) and matches it to a sound name (`tools/gpw-fingerprints.py`);
2. on `Play`, it starts a rumble **voice** playing that sound's amplitude
   envelope (`tools/gpw-envelopes.py`), categorised to a motor by what the sound
   is (weapons → buzz motor; explosions / impacts / tyres / engine → heavy motor);
3. a background thread mixes active voices (MAX per motor) and drives XInput.

So the rumble is literally whatever you can hear — including sounds the physics
stream doesn't model (UI, ambient, horn, specific weapon timbres).

## Status — EXPERIMENTAL, not verified in-game

Built and its testable parts validated natively:
- fingerprints are unique across all 123 `.gpw` (the only collisions are
  byte-identical files, which rumble the same anyway);
- the DLL's FNV-1a matches the Python table byte-for-byte (verified on real PCM);
- envelopes generate; the DLL builds freestanding (imports **KERNEL32 only** —
  safe in any prefix), exports `DirectSoundCreate`.

**Unverified (needs a live-game session):** the COM vtable interception, and the
assumption that the game writes the `.gpw` PCM into the buffer verbatim (if it
resamples/reformats, the fingerprint won't match and sounds won't be identified —
the DLL degrades gracefully to silence, it won't crash the audio path). Treat
this as a prototype to validate, not a shipping feature.

## Build

    brew install mingw-w64     # once
    ./build.sh                 # -> dsound.dll (32-bit, KERNEL32-only)

## Install (mutually exclusive with the ffb-shim rumble)

The ffb-shim and this proxy both drive the pad motor and **would fight**. To try
this path, first revert the ffb-shim (`../ffb-shim/install.sh --revert`), then:

    ./install.sh               # places dsound.dll + generates the fingerprint/
                               # envelope tables in the game dir
    ./install.sh --revert

**Wine caveat:** `dsound` is a Wine builtin, so Wine may load its own instead of
our app-dir copy. Force ours with `WINEDLLOVERRIDES="dsound=n,b"` in the launch
env (native first, builtin fallback). On Windows, rename the system `dsound.dll`
path handling isn't needed — the app-dir copy loads first. `install.sh` prints
the current override guidance.

## Files

- `dsndrumble.c` — the proxy (COM wrappers, fingerprint match, voice mixer thread)
- `dsound.def` — exports `DirectSoundCreate`
- `build.sh` / `install.sh`

Needs `rumble-envelopes.ini` + `rumble-fingerprints.ini` beside the DLL
(install.sh generates both from your own `I76.ZFS`; gitignored, never committed).
