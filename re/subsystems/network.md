# network (ANet session, packets, spawn points)

**Contract.** Multiplayer runs over ANet (anetdll.dll, the DirectPlay-style `dp*` API). `net_Pump` 0x4532c0 runs once
per frame and dispatches the received packets by type. Remote vehicles are driven by 'ST' state packets through the
network mirror 0x464890 and dead-reckoned between packets. `net_IsNetworkGame` 0x452d20 ([0x541030]) gates every
network-only branch elsewhere: component bonuses, weapon jams, the brake strength.

Static reading of md5 9a232dcc (2026-09-27), batch `range-t-1`: 119 names in 0x450000-0x457fff, from a reviewed
read-only draft (cluster T). Nothing was checked live. The 'ST' -> 0x464890 dispatch and the join-ring wrap were
re-read in disassembly.

## Also in this range

- The joystick driver table 0x4f53f8 (`input_*`, 0x450490-0x450ca0).
- The entity table 0x542830 (`entity_Register` ..., 0x457100-0x457630).
- Spawn and regen points (0x450f40-0x451a70). They also run offline in melee: respawn delay 5 s (0x4bdf30), a point
  is blocked within vehicle radius + 20 m, the regen radius is 10 m and the hold 30 s.

## Session

- **Player table** 0x541070, 16 x 0x48 bytes:

  | offset | field |
  |---|---|
  | +0 | dp id (0 = free) |
  | +2 | name[24] |
  | +0x1c | flags (bit 0 joining, bits 16..18 team) |
  | +0x20 | .vcf name |
  | +0x28 | vehicle object |
  | +0x2c | last heard |
  | +0x30 | smoothed one-way latency |
  | +0x34 | latest state time |
  | +0x38 | dead-reckoned-to time |
  | +0x3c / +0x3e | kills / deaths |
  | +0x40 | score (kill x 1000) |

- **Globals.** Local id 0x541028, host 0x541064, game group 0x541060. entity+0x480 is the owning player of a vehicle.
- **Join handshake** (`net_JoinHandshakeStep` 0x452f20). Beacons 0xcc43. After 5 s of silence a player makes itself
  host; the lowest id wins.
- **Clock.** The host's 'XX' pings (every 0.5 s) carry its sim time, which clients adopt (plus latency) through
  `simclock_SetSimTime` 0x49c8d0.
- **State rate.** The 'ST' send interval is mean latency / 3, clamped to [0.2, 0.5] s.
- **Anti-cheat.** Vehicle files (NVCL) are exchanged with a checksum; the host can boot a player ('BO', reason 1 =
  cheating).

## Packets

Types are two ASCII characters, low byte first (ANet `dppt_MAKE`). The header is u16 type, u8 sender role (3 client,
4 host), then an f32 time stamp; the body starts at +8.

| type | handler | effect |
|---|---|---|
| 'd1' / 'd2' / 'd5' | pump, inline | ANet system: add player / delete player / add player to the game group |
| 'd3' | handshake | system: add group (records the game group id) |
| 'RE' | 0x4568f0 | join request (host): auto-accept, CTRL-Y/N prompt, or answer 'JO' / 'JD' |
| 'JO' / 'JD' | sent only (0x455fa0 / 0x4560a0) | join accepted (sim time, mission, version '1.00') / denied; received outside the exe (shell DLL) |
| 'SR' | 0x456970 | spawn or respawn request to the host |
| 'SP' | 0x456b00 | spawn player: id, point, .vcf bytes |
| 'ST' | 0x456c10 | vehicle state (0x60 B: time, orientation, velocities, controls, flags) -> mirror 0x464890 / 0x46ce30 after a stale filter |
| 'SH' | 0x456d70 | weapon fire: fire mask, 3 target ids, lock target |
| 'SC' | 0x456790 | destroyed-structure bitmask by load-order index |
| 'CH' | 0x453df0 | chat |
| 'BO' | 0x456ea0 | booted by the host |
| 'XX' / 'YY' | pump, inline | ping / pong: latency = (now - echo) / 2, smoothed 0.2 / 0.8 |

## Latent bugs

- The join-prompt ring 0x541830 holds 32 twelve-byte entries, and the reader wraps its index with & 0x1f.
  `net_QueueJoinRequest` wraps the write index 0x541828 with & 0x3f (0x455956), so more than 31 queued prompts would
  overwrite 0x5419b0 (the read index) and beyond.
