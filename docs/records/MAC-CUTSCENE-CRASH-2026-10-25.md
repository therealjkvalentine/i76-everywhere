# Mac crash around the Taurus-pickup scene (T05 co-op), 2026-10-25

Report: the game crashed on the Mac when the cutscene after the Taurus pickup (or the one right after it) was triggered.
Evidence only, nothing reproduced or changed on the Mac. Lab copy: `captures\mac-cutscene-crash-20261025\` (mciproxy.log,
OpenGLid.log, ipxwrapper.log, I76PLYR.DEF, user.mel, save index, `tools\disasm.py`).

## 1. What the Mac was running
- Gold app in the Sikarugir wrapper, Wine "sikarugir 10.0 (revision 6)", DXVK off, MoltenVK-CX on, esync/msync on.
  Graphics path: dxwnd + OpenGLide (OpenGLid.log, 1728x1117 frame); no dgVoodoo in this app.
- Proxy `STRLKUP.DLL` md5 `5d6f9828df429a3d2112fc64532937e1` (installed 04:18 CDT, a known released build), `i76.exe` md5
  `6319abf7bf96e32f994fe7609cf99a7a`, `strlkup_orig.dll` `e5951e0f`, `i76shell.dll` `a300db63`, `u32x.dll` `06467bd2`.
- The 04:18 build logs `coop-script-guard: 5/5`, `host respawn request gate on`, `coop-chain: on`.

## 2. Which mission
The crashing session was a **co-op host** session (not single-player): `user.mel` = "Scene 5 (Co-op)", host + 1 human, mission
`coop05.lvl` (T05, the mission whose script names the `taurus` car; see ARCADE-PHYSICS.md). It ran 44 five-second log blocks
(~220 s) in `coop05.lvl`. Just before the crash the proxy's AI fill spawned a copy of `t05cc02` (the T05 flamer car, "Gas
Launcher") into the game, the music was paused (`MCI_PAUSE`), and the camera callback was `0x0048E190` mode 5 (every other
crash and the normal play lines show `0x00406AB0` mode 0 / mode 2). The log has no movie (smk/mve) line at all, so there is
**no evidence of a movie**; the camera change fits an in-engine scene camera. Which of the two scenes it was cannot be told
from this log (the proxy does not log script camera or cutscene starts).

## 3. The crash
```
CRASH: code 0xC0000005 at 0x0047A969 (exe+0x7A969) read addr 0x00000001 | eax 0000FF01 ebx 0012B25C ecx 000000A7 edx 00000003
       esi 00A6F918 edi 00000001 ebp 0012B260 esp 0012B24C | frame 84188 state 5 cam cb 0x0048E190 mode 5
```
- Class: **game crash**, an access violation inside `i76.exe`, caught by the proxy's exception filter (that is why it is logged).
  Not a hang, not a Wine/Sikarugir or macOS crash: no new `wine*.ips` / `.diag` report exists for today (the newest wine report
  is 2026-10-22; the Mac was up since 10-19). The proxy is in the handler only; the faulting instruction is exe code.
- Site: a software span/blit loop (`mov al,[edi]` then a 256-entry lookup at `0x62B2C0`, shade table via `[esi+eax]`) with the
  destination pointer `edi = 1`. So a draw routine was handed a bad destination (a freed or not yet built surface or object
  record), reached with the mode-5 camera. Not a known site: grep of docs and proxy source finds no `+0x7A969`.
- The stack dump is mostly a counting pattern (a stack frame of the blitter), so the caller is unknown. Needs the pre-crash
  frames, which the filter does not unwind.

## 4. Other crashes in the same log (older builds, for context)
| log line | build | site | read | session |
|---|---|---|---|---|
| 6995 | before the script guard | `+0x684BD` | 0x30 | co-op host, `coop11.lvl`, cam cb 0x406AB0 mode 0 |
| 10801 | before the script guard | `+0x684BD` | 0x30 | co-op host, `auto07.lvl`, same |
| 11908 | 5d6f9828 (guard on) | `+0x7A969` | 0x1 | co-op host, `coop05.lvl`, cam cb 0x48E190 mode 5 |

`+0x684BD` is the already-fixed host-death crash (LAN-FIXES-2026-10-24.md section 6, `I76_COOP_SCRIPT_GUARD`); both sightings
precede the guard's first appearance in this log (line 10842). The `+0x7A969` crash is new and is **not** that bug.

## 5. Known on PC?
No record of `+0x7A969`, of a T05 cutscene crash, or of a crash with camera callback `0x48E190` (grep of docs/records,
2026-10-25). TICK-FINISH-2026-10-18.md ran the T05 flamer cars t05cc02/03 idle for 120 s on the real renderer (5 boots) without
a crash, but never with the co-op AI fill spawning them or a scene camera.

## 6. Likely owner and next step
Likely owner: **our proxy/engine path (co-op AI fill spawning a T05 car into a scene whose camera is script-driven)**, not Wine
or the graphics wrapper: the fault is in `i76.exe` draw code with a garbage destination, and the same game does not draw
through the wrapper at that address. Unproven; n 1.
Next step (no Mac run): ask the owner whether it was single player or co-op (the log says co-op host); on the PC run T05 as
co-op host with `I76_COOP_AI` and the 5d6f9828 build, play to the Taurus pickup and the two scenes, with `mpfill` on and off
(same-rate control, n >= 3), and have the exception filter log the caller chain (frame walk from ebp) for the next crash.
