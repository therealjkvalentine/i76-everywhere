# Co-op spawn / respawn at the host's speed (I76_COOP_MATCH_SPEED), 2026-10-25

Owner (2026-10-25): "If easy: co-op spawn/respawn at the same speed as the host player, in addition to the position being just
behind the player's path." Until now the joiner (and a co-op player who respawns) was placed behind the host (`I76_COOP_NEAR_HOST`,
records/LAN-FIXES-2026-10-24.md s.3) but at rest, so the host drove away from it.

## What it does

`I76_COOP_MATCH_SPEED` (default 1; acts with `I76_COOP_NEAR_HOST`, i.e. with `I76_COOP_CHAIN`, Gold only, in coopNN.lvl /
autoNN.lvl). At both placements near the host (the join move `coop_near_after_join` and the respawn spawn `coop_spawn_near_host`):

- velocity entity+0xbc = the placement heading (= the host's heading) x the host's horizontal speed; +0xac |v|, +0xb0 1/|v|;
  body rates +0xc8..+0xd0 = 0; every wheel's ground speed w+0x20 = |v| (<re-archive> subsystems/physics.md, the veh+ / w+ table).
  The car still drops the 1.5 m from the placement height; the air step keeps the velocity and the landing snaps it to the heading.
- The host's velocity as the joiner has it: the host car's entity+0xbc (the 'ST' mirror; every placement in the runs below
  read it), else the joiner's trail of the host (the last second).
- **Guards** (placed at rest as before, a `coop-match-speed: ... at rest - <why>` line): the host below 1 m/s; airborne
  (flag 0x4, > 3 m over the terrain, or |vy| > 4 m/s); reversing; sliding sideways (> 15 deg between velocity and heading);
  faster than the joiner's car can go (min(72.5 m/s = the 3rd-gear rev limit, (P x power mult / (m x 0.1 x drag))^1/3); loose).
- Every placement is watched: `+0.5 s` and `+5 s` lines with the joiner's speed, the host's and the distance between them; if
  the spawn path had left the velocity below half the target on the first pump call, it is put back (logged; never happened).
- `I76_COOP_MATCH_SPEED=0`: at rest, as before (logged).

## Test (laptop the laptop bench, both peers windowed on its console desktop)

Harness: lab `tools\coop-match\cm.py` on the lanfix / mpo harness (lab copies game-mpo-c host, game-mpo-d joiner, IPXWrapper
G / H on UDP 54810, `I76_SKIP_MOVIES` + `I76_SKIP_CUTSCENES` + `I76_FFB_OFF`, muted), run in the laptop's console session under
its own scheduled task (`cm-start.ps1` / `cm-job.ps1`, the bench lock `<bench>\.fps-lock`). The host drives with the lab
twin's cruise block (`I76_LAB_CRUISE`, lab only: throttle key bang-bang to 26.8 m/s, heading held). Lab twin = this source +
shellclick + cruise (5c27a715 / 7cb17b74). Each run: the host cruises, B joins (host re-placed on the straight when B's car
exists), B is killed by a fall, B respawns (host re-placed 2.5 s after the death). Captures: lab
`captures\coop-match-20261025\{m1,m2,m3,g1,c1}` (results.jsonl, run.log, both proxy logs).

Speeds are the proxy's own `coop-match-speed` lines on the joiner (the host's speed = its car as the joiner has it).

| placement | scene | host m/s | joiner +0.5 s | host +0.5 s | distance +0.5 s -> +5 s |
|---|---|---|---|---|---|
| join (m1 r0) | coop05 T05 straight | 26.8 | 26.8 | 26.8 | 25.0 -> 25.5 (+0.4) |
| join (m1 r2) | coop05 | 26.8 | 26.8 | 26.7 | 25.0 -> 24.0 (-1.0) |
| join (m2) | coop05 | 26.8 | 26.8 | 26.7 | 25.0 -> 24.1 (-0.8) |
| join (m3 r0) | coop01 T01 | 17.0 | 17.0 | 17.0 | 24.3 -> 23.8 (-0.5) |
| join (m3 r1) | coop01 | 17.0 | 17.0 | 17.0 | 25.0 -> 24.3 (-0.7) |
| join (m3 r2) | coop01 | 17.0 | 17.0 | 17.0 | 24.3 -> 23.9 (-0.4) |
| join (g1) | coop01 | 17.0 | 17.0 | 17.0 | 25.0 -> 22.2 (-2.8) |
| respawn (m2) | coop05 (host off the straight) | 5.7 | 5.7 | 5.7 | 20.2 -> (+5 s line not reached) |
| respawn (m3 r0) | coop01 | 16.2 | 16.2 | 16.2 | 20.4 -> 36.9 (+16.4; the host 14.5 m/s at +5 s, see below) |
| respawn (m3 r2) | coop01 | 24.5 | 24.5 | 25.2 | 20.1 -> 25.2 (+5.0; the host speeding up to 29.7) |
| **control, key off** (c1 join) | coop01 | 17.0 | **0.0** | 17.0 | 31.7 -> 76.4 (**+44.7**) |

- Joins: n 7 placed at the host's speed, joiner within 0-3 % of the host at +0.5 s, the gap held within 1 m over 4.5 s in 6 of 7
  (2.8 m in one). Respawns at speed: n 3, within 0-3 % at +0.5 s.
- The 60 mph rows are T05 (coop05). The T01 host only reaches 17.0 m/s (61 km/h) under the lab cruise; that is the instrument,
  not this feature.
- 0 CRASH lines in every game log of the batches (9 runs, 18 game boots); "spawn path left ... put back" never fired.

**Guard cases.** "Host at rest" ran by itself 3 times (m3 r1 0.5 m/s; g1 x2 0.0 m/s): placed at rest with the logged reason, as
designed. A forced airborne / sliding / reversing host (g1: trainer teleports on the host until B's respawn) did not reach the
joiner as motion: the joiner saw the host at 0.0 m/s and chose "at rest" for the right reason, but for the wrong situation. So the
airborne, slide, reverse and top-speed branches are **not verified live**; they are small and each logs its reason when it fires.

## Found on the way (not this feature)

- **Host sim stalls with a joiner present** (`coop-chain: no mission frames for N s in state 5 - dpReceive called from 0045336B`,
  rendering continues): every laptop run, coop05 and coop01, the key-off control too (c1: 17 lines); the PC lanfix
  scale-n10-coop05 run had it twice (15 s). In m1 (coop05) it lasted the rest of each run and the host never answered the joiner's
  respawn request (the joiner's +5 s "host" figures were its dead reckoning). The host does not run this feature's code (joiner
  only). Possibly the owner's "host restart freeze" family (LAN-FIXES s.5). **Solved** in records/COOP-HOST-STALL-2026-10-25.md: the host was inside one net_Pump call (not drawing), sending an 'AT' round on every received packet while the lab's IPXWrapper debug log made each round cost ~0.4 s; `I76_COOP_AT_PER_FRAME` (ea0d483).
- On the laptop (Windows 11 26200) the lab copies crashed at the first Glide context on a private desktop (DDRAW+0x4AB0A with
  dgVoodoo 2.87.3, MSCTF+0x2E1C8 with 2.87.5); on the console's own desktop with 2.87.5 they ran. The laptop copies carry 2.87.5.

## Builds and installs

- Proxy **5dca9d79e0ab3f42bf729dfed6223154** = i76-everywhere 4a57eb9 (`builds\nitro-port-20261021\build.ps1 -Tag cms-4a57eb9 -Ref 4a57eb9`,
  built twice, byte-identical).
- Installed in lab `dev-gold` (was b53d1271) and `test-gold` (was 5d6f9828), md5 read back; the old DLLs are in each folder's
  `_rollback\coop-match-20261025\`; AGENTS.md / VERSION.md there updated.
- **Not** in main (`Games\I76\Interstate 76 Gold`, 5d6f9828): it goes with the next promotion, as a family rollout with the Macs
  on the same md5.
