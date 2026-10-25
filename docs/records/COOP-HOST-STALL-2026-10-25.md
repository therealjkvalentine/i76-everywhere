# Co-op host stall with a joiner present (I76_COOP_AT_PER_FRAME), 2026-10-25

Found by the coop-match lane (records/COOP-MATCH-SPEED-2026-10-25.md, "Found on the way"): with a joiner in the session the
host logged `coop-chain: no mission frames for N s in state 5 - dpReceive called from 0045336B` for 5 s to 77+ s at a time,
in every laptop run (coop01 and coop05, the key-off control too) and in one PC lanfix run; on coop05 the host never answered
the joiner's respawn request.

## What the log line means

`no mission frames` (strlkproxy.c, the dpReceive hook) fires when the proxy's frame counter (the frame hook at 0x4039b8,
once per display frame) has not moved for 5 s while dpReceive is still being called. 0x45336B is the return address of the
`call edi` (dpReceive) inside **net_Pump 0x4532c0**, the per-frame network pump the mission loop calls once at 0x403a33. net_Pump
loops dpReceive until it returns non-zero (empty / error; 2 is retried 3 times). So the line says: the main thread is inside
ONE net_Pump call and has been for N seconds. The host was not drawing either (no display frame ran); the "keeps drawing"
reading in the earlier record was wrong.

## Cause

1. **Where the main thread is.** Run hs1 (laptop, coop01, lab twin 7cb17b74, `I76_FPS_LOG=5` + `I76_FPS_PROF=1`): during
   every stall the fps watcher's stack of the main thread is
   `ntdll ZwWriteFile / ZwWaitForSingleObject < ipxwrapper.dll+a9xx < +6004/+6146 < +6744 < +6b23 < WIPX.DLL+1d04`, and the
   2 ms sampler puts 95-100 % of samples in ntdll in that chain. The pump is not waiting for the network; it is writing
   IPXWrapper's log.
2. **Why the log is that slow.** The lab's IPXWrapper instances (HKCU\Software\IPXWrappeG / H on the laptop and the PC, and
   every other lab letter E..N) carry `log_level` = 2 = LOG_DEBUG (IPXWrapper 0.7.2 common.h: CALL 1, DEBUG 2, INFO 4): one
   line per packet sent and received. log.c opens ipxwrapper.log with FILE_FLAG_WRITE_THROUGH and writes each line as 3
   WriteFiles under a process mutex + LockFileEx. Measured in the host's ipxwrapper.log during the hs1 stall (110 s window):
   ~60 lines/s in total, median 20 ms between lines; the main thread's lines are 2/3 of them (2228 "Sending packet", 1356
   x 214-byte and 573 x 114-byte payloads = the 'AT' packets, 568 "Received packet").
3. **Why it never ends: our own send inside the pump.** The host sends the mission cars ('AT', 2 cars a packet, ~13 packets a
   round on coop01) from the dpReceive hook, `coop_ai_host_send`, gated only by **100 ms of wall time**. At ~2 log lines x
   ~16 ms per send a round costs ~0.4 s, so the 100 ms gate is open on EVERY dpReceive call: every packet received inside
   net_Pump triggers a full round, and the joiner's next packet (~5 a second on the host's wire) has arrived by the time the
   round ends, so dpReceive returns a packet again and net_Pump never returns. The frame (and with it the AI, the scripts,
   the respawn answer) stops until the joiner happens to leave a gap. That is a feedback loop of the proxy's design, not of
   the stock netcode: the stock pump only processes what arrived.
4. **The owner's installs.** HKCU\Software\IPXWrapper on the PC has no log_level (INFO, the default: no per-packet lines) and
   the owner's Gold / Nitro folders have no ipxwrapper.log; no shipped script sets log_level. So the measured stall is the lab's
   debug logging times our send-inside-the-pump. The owner's "host restart freeze" (PC host, Mac joiners; LAN-FIXES s.5) is
   most likely not this (the Macs were not read: off limits), but any slow send path (a slow network stack, many cars) runs
   into the same loop, which is why the loop is fixed in the proxy and not only in the lab.

## Fix

`I76_COOP_AT_PER_FRAME` (default 1; host, with I76_COOP_AI): the 'AT' round still waits 100 ms of wall time, and now also for
a new mission frame (the frame counter; the switch installs the frame hook). A pump that receives many packets sends at
most one round. A round withheld for "no new frame" counts as held. `I76_COOP_AT_PER_FRAME=0` = as before (logged).
Diagnostics (always, with I76_COOP_AI): `net-pump: one net_Pump call took N ms (M packets; 'AT' rounds held ...; long pumps,
worst)` when one pump call held the frame for >= 1 s, at most every 5 s.

## Proof (laptop LAPTOP-HPK11OMS, coop01, n 3 joins + n 3 respawns per row)

Harness: lab `tools\coop-match\cm.py match` (host cruising at 17 m/s, joiner joins, is killed by a fall, respawns), started by lab
`tools\host-stall\hsrun.sh` / `hs-job.ps1` (the bench lock `C:\i76-bench\.fps-lock`; the laptop's console desktop; `-IpxLog N`
sets instances G / H to log_level N for the job and puts the old value back, read back in `runs\cm-<tag>.ipx.txt`). Every boot
`I76_SKIP_MOVIES` + `I76_SKIP_CUTSCENES` + `I76_FFB_OFF`, `I76_FPS_LOG=5`. Twin = proxy source + shellclick + lab cruise.

| batch | proxy (lab twin) | IPXWrapper log | switch | runs with a stall | longest | host fps after the join | deaths / respawns | CRASH |
|---|---|---|---|---|---|---|---|---|
| hs1 (n 1, sampler) | 7cb17b74 (= 5dca9d79 source) | debug (2) | - | 1 of 1 | 25 s (15 lines) | 0.1-1.4 | fall did not kill | 0 |
| hs2 | 7cb17b74 | info (3) | - | **0 of 3** | - | 4-11 | 3 / 3 | 0 |
| fb (control) | f89adc17 (fix source) | debug (2) | **0** | **3 of 3** | 10 s (12 lines) | 0.1-2.8 | 3 / 3 | 0 |
| fa | f89adc17 | debug (2) | 1 | **0 of 3** | - | 2.4-4.8 | 3 / 3 | 0 |
| fc | f89adc17 | info (3) | 1 | 0 of 3 | - | 3-10 | 3 / 3 | 0 |
| ga | 1af3879b (= commit ea0d483) | debug (2) | 1 | **0 of 3** | - | 2.2-6.1 | 3 / 3 | 0 |

- In fb the new `net-pump:` line logs single pump calls of 1.0-1.8 s on the host (2-7 packets each); none in fa / fc / ga.
- The earlier record's runs (m1, m2, m3, g1, c1: lab twin 7cb17b74 / 5c27a715, debug logging) all stalled; the PC lanfix
  run that stalled used the PC's instance G / H, also log_level 2.
- **Joiner placement unchanged:** every join of fa / fb / fc / ga (n 12) was moved 25 m behind the host at the host's 17.0 m/s
  (joiner 16.0-17.0 m/s at +0.5 s); respawns came back 21-40 m from the host (n 12). The +5 s gap and the respawn speeds
  vary with the harness (the host's cruise block re-places it 2.5 s after the death; at 3-10 host fps the bang-bang cruise
  lags), the same with the old proxy at info logging (hs2 join gap -15..-19 m at +5 s, fc -12..-17 m).
- 0 CRASH lines in every game log (17 runs incl. the n 1 sampler runs hs1 and fp, 34 boots).
- **What remains:** with the switch on and debug logging the host runs at 2-5 fps (one round a frame still costs ~0.25 s of
  log writes). At info logging the host drops from ~20 fps to 4-10 fps once the joiner is in the mission: the sampler (run fp)
  puts 72-85 % of the host's time in win32u.dll (the present / GPU wait) and 2-4 % in i76.exe, i.e. two windowed games on the
  laptop's one integrated GPU. That is the instrument, not the netcode.

## Lab note (not changed here)

Every lab IPXWrapper instance key carries `log_level` 2. It costs ~16-20 ms per packet line on the main thread, so any lab
co-op timing (fps, latency, placement drift) is measured under that load. Set log_level 4 (or delete the value) for timing
runs; `hs-job.ps1 -IpxLog 4` does it per job. Left at 2 because other lanes read the packet logs (internet / Deck spikes).

## Builds and installs

- Commit **ea0d483** (proxy source; main 91db8e4 adds only a comment). Product build `builds\nitro-port-20261021\build.ps1
  -Ref 91db8e4` (and -Ref ea0d483): **d738caac568709daeba5033553358b00**, built twice each, byte-identical.
- Installed in lab **test-gold** `Interstate 76\STRLKUP.DLL` (was 5dca9d79, kept in `_rollback\coop-host-stall-20261025\`),
  md5 read back; VERSION.md / AGENTS.md there updated. Not in dev-gold, not in main, not on the Macs: it goes with the next
  family rollout together with I76_COOP_MATCH_SPEED (both host + joiner on the same md5).
- Lab twins: `builds\host-stall-20261025\Strlkup-hsfix.dll` f89adc17 (5184173 + the patch), `Strlkup-hs-ea0d483.dll` 1af3879b.
- Captures: lab `captures\coop-host-stall-20261025\{hs1,hs2,fa,fb,fc,fp,ga}` (results.jsonl, run.log, both proxy logs,
  ipx.txt) + `hs-ipx-c.log` / `hs-ipx-d.log` (the laptop instances' ipxwrapper.log through hs1) + `laptop-bins\` (the
  laptop's SysWOW64 ntdll / KernelBase and ipxwrapper.dll, for symbolising the samples).
- The PC was not used as host: the cause is in the host's own send loop and reproduced on the laptop; the PC's lab instances
  have the same log_level.
