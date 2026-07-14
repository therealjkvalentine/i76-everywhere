# Outreach draft — announcing the Mac port recipe

Target venues (checked July 2026):
- **interstate76.com forums** (alive — Tuesday Night Events as of Mar 2026): Tech Support or General
- **GOG forum**, Interstate series board (the "de-facto 20 FPS" thread audience)
- **VOGONS** (dgVoodoo / DOS-era Windows gaming crowd — they'll appreciate the wine details)
- **r/macgaming** (angle: "1997 Glide game on Apple Silicon, free stack")

Adjust the greeting per venue; the body below works for all four.

---

**Subject: Interstate '76 running on Apple Silicon Macs — free/open-source stack, physics-correct 20 FPS, full write-up + repo**

Hey all — I got I'76 Gold (GOG) running properly on an Apple Silicon Mac (M-series) with
free tooling only — no CrossOver license, no emulated Windows VM — and documented every
gotcha in a public repo so others can reproduce it:

**https://github.com/therealjkvalentine/mac-gaming-ports** → `games/interstate-76/`

A few findings along the way that might interest even the Windows folks:

- **The 2019 GOG `i76.exe` (MD5 60abf7bc...) is byte-identical to UCyborg's AiO patch final
  build** — so the 20 FPS physics limiter (I76PATCH.DLL) is already inside every GOG install.
  If you own it on GOG, you already have the frame-rate fix.
- The exe has an **undocumented `-gdi` renderer switch** (windowed software blit, added by the
  AiO work). On Wine/Mac this is gold: it avoids DirectDraw exclusive fullscreen entirely,
  which sidesteps Wine's hardcoded minimize-on-focus-loss for fullscreen apps.
- The shipping config is the game's own Glide renderer through GOG's bundled **OpenGLide**
  (bright 3dfx-gamma colors, 1280x960 window, instant start). Gotcha that cost us a day: Glide
  wrappers (OpenGLide *and* dgVoodoo) read their config from the process working directory —
  launch from the wrong CWD and they default to fullscreen and black-screen.
- Bonus research: **dgVoodoo2 also works under Wine on Apple Silicon** with three conditions:
  version ≤2.8.2 (2.81+ has an initialization regression under Wine — matches dxvk issue #5217 /
  wine bug 58731), DXVK for the D3D11 backend (wined3d's MoltenVK path refuses FL 10.1), and
  wrapping Glide only (two dgVoodoo swapchains in one window get stacked wrong by the Mac
  driver). We retired it in the end — OpenGLide is just as bright with none of the shader
  warmup — but the recipe is documented for anyone who needs dgVoodoo under Wine on a Mac.
- Mac keyboards send arrow keys as the game's "Grey"/numpad codes, so stock KEYBOARD.MAP
  steering is dead on a Mac — the repo has a one-shot script that swaps the arrow tokens.

The repo contains **no game files** (OpenRA-style): you bring your own GOG install and drop
it in a gitignored `game-data/` folder — the README explains exactly what goes where, and
there's a full research doc covering what's still open (per-launch shader warmup in the
dgVoodoo mode, and what a future MoltenVK/DXVK could do about it).

**Easiest path if you use AI tooling:** clone the repo, open a terminal in
`games/interstate-76/`, and point Claude Code (or similar) at it with something like
*"Set up Interstate '76 on this Mac following this folder's README — my GOG install zip is
at ~/Downloads/i76.zip"* — the docs were written to be agent-followable, every step is
scripted or spelled out. Manual path: README top to bottom, ~30 minutes.

Happy to answer questions or take PRs — especially interested if anyone has a dgVoodoo
2.79.3–2.8.2 binary archived (dege's old links 404), or wants to test on other M-chips.
