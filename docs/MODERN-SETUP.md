# Interstate '76 — modern-PC setup notes (for THIS copy)

Your build (verified 2026-06-08):
- **GOG release**, `i76.exe` dated 2019-09-01, MD5 `60abf7bc699da72476128ddce991a3d1`
  (this is a NEWER GOG build than the one the `i76fix` patcher targets — see warning below)
- Renderer: **OpenGLide 0.09rc5** (Glide→OpenGL wrapper GOG bundles)
- **No frame-rate cap is configured.** This is the whole problem.

## The one bug that matters

*(rewritten 2026-10-02: the earlier text here taught the "above ~30 FPS the sim over-integrates" folklore as
fact; it was measured false in the sandbox on 2026-09-27, i76-map `captures/014-framerate`, and confirmed in
play on 2026-10-02.)*

I'76's simulation is **dt-driven**, not fixed-step: physics runs in substeps of at most 50 ms derived from the
measured frame time, gravity is dt-correct (g = 9.8 at 20 and at 60 fps), and the Mission 5 jump clears at 60 fps
with the fixed physics step. What the stock game gets wrong above 20 fps is a long list of **per-frame effects**
that carry no dt — sky drift, free-look and zoom keys, keyboard throttle ramp, lock tones, radar ping, AI
throttle/steering gains and fire rate, flamers (effectively none at stock 60 fps), smoke, missile trails, HUD
digit roll, engine smoothing, clock jitter — and the ground-contact model is tuned for the stock ~42 ms physics
step, so **stock** 60 fps bleeds speed before a ramp and lands short. That is the kernel of the folklore.

**Two ways to play it right:**

- **Cap the frame rate at 20.** The community consensus, the GOG "de-facto" guide and the AiO patch all use it;
  it is known-good and it is how the playable install runs. (On the GOG 2019 exe the cap comes from the bundled
  `I76PATCH.DLL`; dgVoodoo's `FPSLimit` was recorded as ignored on this build, a result that is void since
  2026-10-03: the sandbox conf was being rejected when it was measured, see [FPS-120.md](FPS-120.md).)
- **The proxy's opt-in switch set** — `I76_HIRES_CLOCK`, `I76_FIXED_STEP=24`, `I76_FRAMERATE_FIXES`,
  `I76_ENGINE_DT_FIX`, `I76_RENDER_INTERP` ([music-fix/README.md](../music-fix/README.md) switch table, with
  per-switch measured evidence) — fixes each per-frame effect and holds the stock step at 60 fps. Sandbox-measured
  and **console-verified by the owner on 2026-10-02** (music, flamer, AI, jumps, body roll all good); **not deployed
  to the playable install**, so the 20 fps cap remains the default for play.

## ⚠️ Do NOT use i76fix's pre-patched exe / patcher on THIS copy
`immi101/i76fix` (the popular 25 FPS patcher) expects GOG `i76.exe` MD5
`9a232dcc...` (a 2017 build). **Yours is the 2019 build (`60abf7bc...`).** The patcher
writes to hard-coded byte offsets and "does not check the exe first," so it would
corrupt your binary; its pre-patched 2017 exe would also down-grade you to an older build.
Use one of the build-agnostic options below instead.

---

## Option A — keep this OpenGLide copy, add an external FPS cap (lowest risk)
Nothing in this folder changes; fully reversible.

**A1. NVIDIA Control Panel (you have a GTX 1080 Ti):**
- NVIDIA Control Panel → *Manage 3D settings* → *Program Settings* → Add → `i76.exe`.
- Set **Max Frame Rate = 25** (or 24). *(Older guides use "Vertical sync = Adaptive (half
  refresh rate)" which gives 30 on a 60 Hz screen — works but looser; prefer Max Frame Rate.)*

**A2. RivaTuner Statistics Server (RTSS)** — the most reliable external limiter:
- Install RTSS, Add `i76.exe`, set **Framerate limit = 25**.
- **Turn its on-screen display OFF** (any FPS overlay can crash I'76 at mission end).

Then launch the game as you do now. Verify on a jump mission.

## Option B — the dgVoodoo2 build I staged for you (best visuals + built-in cap)
I made a ready-to-run copy at **`C:\Users\james\Downloads\I76-dgvoodoo`** with
dgVoodoo2 + `FPSLimit = 20` already configured. See `WHAT-THIS-IS.txt` there.
- Run on the **physical console** (not RDP): right-click `PLAY-i76-dgvoodoo.bat` → Run as administrator.
- Pick a **4:3** resolution in `dgVoodooCpl.exe` (16:9 distorts the camera).
- Pause-menu mouse doesn't work in Glide mode → use Arrow keys + Enter.

## Option C — the AiO Unofficial Patch (one-stop, also fixes crashes/audio)
PCGamingWiki Community file #1349 / interstate76.com. Bundles a built-in 20 FPS limiter
**plus** crash, memory (>2 GB), and audio fixes, and covers the Nitro expansion. Requires a
manual download from those sites (couldn't be auto-fetched). Best if you also want the
audio/crash fixes, not just the cap.

---

## Play-through checklist (so it won't blow up at a critical moment)
1. Pick ONE capping method above and set it to ~20–25 FPS **before** starting the campaign.
2. Disable ALL FPS/recording overlays (RTSS/GeForce/Dxtory OSD) — they crash mission-end.
3. If a cap won't engage: turn off Windows **Fast Startup** (Power Options).
4. Sanity check: load a **jump mission** — if you clear the ramp, the cap is working.
5. RDP note: the original game's 3D won't init over Remote Desktop — play at the console.

## Sources
- PCGamingWiki: https://www.pcgamingwiki.com/wiki/Interstate_'76
- GOG "de-facto 20 FPS" thread (Dxtory @20): https://www.gog.com/forum/interstate_series/de_facto_solution_to_running_the_gog_version_of_interstate_76_and_interstate_76_nitro_flawlessly_a
- CahootsMalone dgVoodoo guide (GOG): https://github.com/CahootsMalone/interstate-76-stuff/blob/master/running-interstate-76-gog-release-using-dgvoodoo.md
- immi101/i76fix (25 FPS; 2017 build only): https://github.com/immi101/i76fix
- Shane Peelar RE write-up (20 FPS rationale): https://inbetweennames.net/blog/2021-05-04-interstate-76-reverse-engineering-efforts-the-story-so-far/
- r1sc/Open76 (reimplementation, physics WIP): https://github.com/r1sc/Open76
- AiO patch (PCGW Community #1349): https://community.pcgamingwiki.com/files/file/1349-interstate-76-nitro-pack-aio-patch/
