# tools/haptics/replays

`.i76rec` telemetry recordings (raw i76tel datagrams with host timestamps; format in
`src/Haptics/Transport/Recording.cs` and `design/i76rec.py`). Every offline run takes one of these as input.

* `haptics.ps1 synth --out replays\synthetic-v3.i76rec [--version 2|3] [--repeats N]` writes the scripted 20 s session
  (`Transport/Synthetic.cs`) as real v2 or v3 datagrams. It is regenerated on demand, so it is not committed.
* `haptics.ps1 record --udp --out replays\<name>.i76rec` captures a real session (owner test 5 in docs/OWNER-TEST-LIST.md).
  Real captures are evidence: keep them (memory note "retain and re-mine raw captures"); they hold only the player's
  own telemetry, no game assets.
* `haptics.ps1 decode <file> [--events]` summarises one; `python design/i76rec.py <file> --decode` reads it with
  `tools/telemetry/i76tel.py`.
