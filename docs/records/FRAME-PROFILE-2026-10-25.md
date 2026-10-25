# Frame profile, T05 ridge route (2026-10-25) - PARTIAL (console taken by the owner mid-lane)

Question (owner): "We are CPU- not GPU-constrained? What are the specific bottlenecks?" Measure only; no fixes.

## Set and method

- Test copy `i76-uncap-lab\test-gold`, `PLAY.bat` set (OWNER-2300-ALL, proxy STRLKUP.DLL md5 5d6f9828, dgVoodoo `wide` conf: Glide render target 6880x2880, 4x MSAA, window 3440x1440), `--no-headtrack --no-ffb`, opentrack not running. GPU: GTX 1080 Ti.
- Route: `autotest\t05-route-fps.ps1`'s launch + `tools\rc-draw\rcd_drive.py` (15 s ridge leg, then the hill leg 8945 -> 6385, 2.6 km at 22 m/s). The 120 fps cap never binds on this PC today (cap wait 0.00 ms in every 5 s window).
- Tools (lab `tools\frame-profile\`): `fp-run.ps1` (one boot + sidecars), `fp_sample.py` (external suspend sampler of the main thread: eip + stack scan for i76.exe call-chain frames + player x, ~380 samples/s, no admin; WPR/xperf need admin and the lane is not elevated, so ETW was not used), `fp_analyse.py` (buckets by module, by i76.exe function from `i76-map\symbols\functions.tsv`, and by frame phase = the outermost renderer root function on the validated call chain). Sidecars: `nvidia-smi -l 1`, `Get-Counter "\GPU Engine(pid_*)"`, the proxy's `I76_FPS_LOG 5`, `I76_TERRAIN_MORPH_LOG`, `I76_FRAME_LOG`.
- Raw data retained: lab `captures\frame-profile-20261025\` (`*.samples.tsv` raw eip/stack samples, `*.threads.tsv`, `*.gpu.csv`, `*.gpueng.csv`, `*.frames.csv`, `*.proxylog.txt`, `a1-sample.pie.txt`, `a1-sample.analysis.txt`).

## Runs so far (hill leg, whole 2.6 km)

| run | what | hill fps (median) | 1 % low |
|---|---|---|---|
| a1-sample | external sampler on, sidecars on | 84.4 | 52.8 |
| a1-clean / a2-clean | sidecars on, no sampler suspends | 85.6 / 87.2 | 44.9 / 52.3 |
| b1 / b2 (bare: no nvidia-smi, no Get-Counter) | | 74.0 / 73.2 (b2 leg cut at 1035 m) | 49.4 / 49.8 |

The sampler costs nothing measurable (84.4 vs 85.6 / 87.2). Run-to-run spread is 4-5 fps inside a sitting and the bare runs are 12 fps SLOWER than the runs with the nvidia-smi poll running (n 2 vs 2; the poll keeps the GPU at P0 / ~1.5 GHz; without it the clocks may idle down at 15 % load - open, see "Not yet measured"). The owner's 90-110 fps on this route was not reproduced today (74-87).

## Verdict (evidence so far): CPU-bound on ONE thread, GPU mostly idle

- The main thread is at 97-100 % of a core for the whole run in all four runs (GetThreadTimes per second); every other thread together adds 6-8 % of a core. Process total 1.03-1.06 cores. `cap wait 0.00 ms`: the frame is all work (11-13.5 ms avg per frame at 74-87 fps).
- GPU: nvidia-smi `utilization.gpu` p50 15 % / p90 19 % (max 45 %) over the active seconds, SM clock ~1.3-1.5 GHz, power 65-78 W; per-process 3D engine ~4.6 %. A 1080 Ti is nowhere near its limit at 6880x2880 4x MSAA for this scene.
- (Render-resolution bound test 1x vs 2x: NOT yet run, see below.)

## Where the main thread's time goes (hill leg, a1-sample, 67,589 samples, % of main-thread time)

| bucket | % | what it is |
|---|---|---|
| **PeekMessageA (win32u syscall, WinMain call site 0x403789)** | **23.6** | the loop's message pump; ~2.8 ms per frame inside one system call. The thread is 100 % busy, so it is CPU (kernel/win32k) work, not an idle wait. Cause NOT identified (see below) |
| terrain pass, proxy code (Strlkup.dll: morph, smooth shade, split hook; hot block +4b700) | 13.5 | proxy-measured own cost 1.6-2.0 ms per pass (`terrain-morph: own cost`), = 13-15 % of the frame: agrees |
| terrain pass, game code | 8.5 | `renderer_QueueTerrain` and callees: `renderer_SubdivideTerrainQuad` / `SplitTerrainEdge` (tessellation, incl. frames under the proxy's split hook), `renderer_EmitTerrainPolys`, `ShadeTerrainVertex`, `world_GetTerrainSampleRaw`, `rsqrt`, `math_PlaneFrom3PointsF`, `renderer_InsertDepthBucket`, clip |
| draw flush: dgVoodoo Glide2x.dll | 10.9 | the Glide -> D3D11 translation behind `grDrawTriangle` etc. (hot blocks +1a100, +1200) |
| draw flush: D3D11 / DXGI / NVIDIA user-mode driver | 5.5 | command building in the driver, on the same thread |
| draw flush: ZGLIDE.DLL | 3.8 | the Glide layer the game links |
| draw flush: game code (bucket walk, `renderer_DrawPolyHW`, object BSP) | 3.4 | |
| clutter (bushes) | 7.6 | proxy-measured 1.4-1.6 ms per frame (`clutter: 600 frames`), ~820 instances tested per frame, ~800 cells |
| sim / physics / AI / sound update (`shell_cb_10` -> ntdll etc.) | 5.2 | the 24 Hz sim is cheap; most of this is the voice/sound update's ntdll calls |
| loop body outside the phases (system calls 6.4, game 1.6, proxy 0.7, other) | ~9.8 | input, flip/present hook, misc |
| rear mirror 1.3, roads/decals 1.3, cockpit/HUD 0.9, sky 0.5 | ~4 | |

Caveats: eip-by-module is exact; the phase attribution rests on a call-chain scan that was validated against the exe FILE bytes in this analysis (proxy-patched call sites show their original target there, so a few DLL-eip samples can be attributed to a neighbouring phase; the next sample run saves the in-memory exe image and the analyser uses it). Time-in-syscall is placed at syscall return (a suspended thread stops when it returns to user mode), which is proportional to the time spent.

## Counts per frame (hill leg)

- Terrain vertices (`[0x6442ec]`, 5 ms samples, n ~20.9 k): mean 6,330, p50 6,590, p90 7,150, max 7,540 (a1 and a2 agree within 1 %). Fits the earlier ridge-vertex peak 6,633 at LOD 24.
- Clutter: ~820 instances tested per frame, ~750-900 cells (proxy `clutter:` lines).
- Triangles submitted (grDrawTriangle), draw records: NOT yet measured (needs the `I76_DRAW_PROBE` run, queued).
- Morph: ~1,500 vertex-passes morphing per main pass.

## Top hot spots so far (no fixes)

1. PeekMessageA in the WinMain pump - 23.6 % (~2.8 ms/frame), one syscall per frame, cause unknown.
2. Proxy terrain morph / shade / split hook inside the terrain pass - 13.5 %.
3. dgVoodoo Glide2x.dll + D3D11/driver translation of the Glide calls - 16.4 % together (CPU side of drawing; the GPU itself is idle).
4. Game terrain queue (tessellation + transform + shade) - 8.5 %.
5. Clutter - 7.6 %.

## Not yet measured (blocked: owner took the console 09:40; lane stays queued)

- `I76_DRAW_PROBE` counts (triangles, draw records per frame); in-process `I76_FPS_PROF` cross-check.
- Render-resolution bound test (conf variants `tools\frame-profile\conf-1x-aa4.conf`, `conf-1x-noaa.conf`, `conf-quarter-noaa.conf` via `fp-run.ps1 -Conf`): if fps and the PeekMessage share do not move with the pixel count the frame is CPU-bound by construction; if the PeekMessage share shrinks it is GPU/present back-pressure surfacing in the next system call.
- Kernel vs user split of the main thread (the sampler now logs it) to say whether PeekMessage time is kernel work.
- Why the bare runs are slower than the runs with the nvidia-smi poll.
